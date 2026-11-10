"""Day 7 performance measurements (T17) on this machine. Label-free; writes reports/day7/performance.json."""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb
import httpx

from . import config, features
from .features import feature_parquet
from .runtime import environment, machine_memory_gib, peak_rss_mib
from .serving import load_frozen

PORT = 8766
RUN_ID = "demo-test-d14-16"


def _pct(values: list[float]) -> dict:
    v = sorted(values)
    return {"n": len(v), "p50_ms": round(statistics.median(v), 1), "p95_ms": round(v[max(0, int(0.95 * len(v)) - 1)], 1),
            "max_ms": round(v[-1], 1)}


def batch_scoring() -> dict:
    """Score every row of steps 356-743 with the frozen model from the label-free feature table."""
    t0 = time.perf_counter()
    with duckdb.connect() as con:
        df = con.execute(f"""
            SELECT e.source_row, e.step, e.type, e.amount, f.* EXCLUDE (source_row)
            FROM read_parquet('{config.paths().events_parquet.as_posix()}') e
            JOIN read_parquet('{feature_parquet().as_posix()}') f USING (source_row)
            WHERE e.step BETWEEN 356 AND 743""").df()
    t1 = time.perf_counter()
    frozen = load_frozen()
    x = frozen.matrix(df)
    t2 = time.perf_counter()
    frozen.model.predict_proba(x)
    t3 = time.perf_counter()
    return {"rows": len(df), "load_seconds": round(t1 - t0, 2), "design_matrix_seconds": round(t2 - t1, 2),
            "predict_seconds": round(t3 - t2, 2), "rows_per_second_predict": round(len(df) / (t3 - t2)),
            "peak_python_process_mib": peak_rss_mib()}


def feature_build() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out = features.build(Path(tmp) / "hist.parquet")
    return {"rows": out["rows"], "seconds": out["elapsed_seconds"]}


def api_latency() -> dict:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "fraudinv.api:app", "--host", "127.0.0.1",
                             "--port", str(PORT), "--log-level", "warning"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{PORT}"
    try:
        c = httpx.Client(base_url=base, timeout=60)
        for _ in range(60):
            try:
                if c.get("/health").status_code == 200:
                    break
            except httpx.TransportError:
                time.sleep(0.5)
        case_ids = [i["case_id"] for i in c.get("/cases", params={"run_id": RUN_ID, "limit": 200}).json()["items"]]
        with duckdb.connect() as con:
            rows = con.execute(f"SELECT type, amount, nameOrig, nameDest FROM read_parquet("
                               f"'{config.paths().events_parquet.as_posix()}') WHERE step = 409 LIMIT 200").fetchall()
        score_bodies = [{"run_id": RUN_ID, "transaction": {"step": 409, "type": t, "amount": f"{a:.2f}",
                                                            "name_orig": o, "name_dest": d}} for t, a, o, d in rows]

        def timed(fn):
            s = time.perf_counter()
            r = fn()
            if r.status_code != 200:
                raise RuntimeError(f"{r.status_code} {r.text[:200]}")
            return 1000 * (time.perf_counter() - s)

        out = {}
        for _ in range(5):  # warm-up
            c.get("/health")
        out["health"] = _pct([timed(lambda: c.get("/health")) for _ in range(100)])
        out["overview"] = _pct([timed(lambda: c.get("/overview")) for _ in range(50)])
        out["queue_page_50"] = _pct([timed(lambda d=d: c.get("/cases", params={"run_id": RUN_ID, "day": d, "limit": 50}))
                                     for d in (14, 15, 16) * 20])
        out["case_evidence"] = _pct([timed(lambda i=i: c.get(f"/cases/{i}/evidence")) for i in case_ids[:200]])
        out["score_sequential"] = _pct([timed(lambda b=b: c.post("/score", json=b)) for b in score_bodies])
        # one shared, thread-safe client: creating an httpx client per request costs ~240 ms here
        shared = httpx.Client(base_url=base, timeout=60, limits=httpx.Limits(max_connections=8))
        for workers in (4, 8):
            with ThreadPoolExecutor(workers) as pool:
                t0 = time.perf_counter()
                lat = list(pool.map(lambda b: timed(lambda: shared.post("/score", json=b)), score_bodies))
                wall = time.perf_counter() - t0
            out[f"score_concurrency_{workers}"] = {**_pct(lat), "throughput_per_second": round(len(lat) / wall, 1)}
        out["client_note"] = ("Measured with persistent HTTP clients against 127.0.0.1. A new client per request "
                              "added ~240 ms; addressing 'localhost' added ~2.3 s per new connection on this machine.")
        return out
    finally:
        proc.terminate()
        proc.wait(timeout=30)


def run() -> dict:
    started = time.perf_counter()
    day4 = json.loads((config.REPORTS_DIR / "day4" / "replay_consistency.json").read_text(encoding="utf-8"))
    result = {"report": "day7-performance", "environment": environment(),
              "hardware_note": "Intel i7-11800H (16 logical CPUs), 15.77 GiB RAM, RTX 3060 Laptop 6 GiB "
                               "(GPU used only by local LLM inference, via Vulkan)",
              "memory_at_start": machine_memory_gib(),
              "feature_build": feature_build(), "batch_scoring_test_window": batch_scoring(),
              "replay": {"source": "reports/day4/replay_consistency.json and docs/checkpoints/day-04.md",
                         "warmup_seconds": day4["create_A"]["seconds"],
                         "steps_356_365_rows": day4["replay_A"]["rows_scored"],
                         "steps_356_365_seconds": day4["replay_A"]["seconds"],
                         "demo_run_rows": 873533, "demo_run_seconds": 437.83},
              "api_latency": api_latency(), "memory_at_end": machine_memory_gib()}
    result["total_seconds"] = round(time.perf_counter() - started, 2)
    out = config.REPORTS_DIR / "day7" / "performance.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
