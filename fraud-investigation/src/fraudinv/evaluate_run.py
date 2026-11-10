"""Offline evaluation of a replay run's finalized queue (evaluator role only).

Loads truth labels for the run window into ``truth.label`` and writes aggregate
metrics per day segment to reports/day5/. Serving code and the API never read
truth; the API only serves this aggregate report file.
"""
from __future__ import annotations

import json
import time

import duckdb

from . import config, db
from .events import event_prefix

REPORT_DIR = config.REPORTS_DIR / "day5"


def report_path(run_id: str):
    return REPORT_DIR / f"run_evaluation_{run_id}.json"


def load_truth(conn, first: int, last: int) -> int:
    src = config.data_source()
    prefix = event_prefix(src["dataset_key"], src["csv"]["sha256"])
    with duckdb.connect() as con:
        df = con.execute(f"SELECT source_row, isFraud, isFlaggedFraud FROM read_parquet("
                         f"'{config.paths().events_parquet.as_posix()}') WHERE step BETWEEN ? AND ?",
                         [first, last]).df()
    with conn.transaction():
        conn.cursor().executemany(
            "INSERT INTO truth.label (event_id, is_fraud, is_flagged_fraud) VALUES (%s, %s, %s) "
            "ON CONFLICT (event_id) DO NOTHING",
            [(f"{prefix}-{int(r.source_row):07d}", int(r.isFraud), int(r.isFlaggedFraud))
             for r in df.itertuples(index=False)])
    return len(df)


def evaluate(run_id: str) -> dict:
    started = time.perf_counter()
    with db.connect("eval", autocommit=True) as conn:
        run = conn.execute("SELECT first_step, last_step, model_version, policy_version, daily_capacity "
                           "FROM app.replay_run WHERE run_id = %s", (run_id,)).fetchone()
        if run is None:
            raise KeyError(run_id)
        first, last, model_version, policy, k = run
        loaded = load_truth(conn, first, last)
        segs = conn.execute("""
            SELECT f.partition_name, f.simulation_day, f.first_step, f.last_step, f.observed_hours, f.capacity,
                   (SELECT count(*) FROM app.score s WHERE s.run_id = f.run_id AND s.partition_name = f.partition_name
                       AND s.simulation_day = f.simulation_day) AS population,
                   (SELECT count(*) FROM app.score s JOIN truth.label l USING (event_id) WHERE s.run_id = f.run_id
                       AND s.partition_name = f.partition_name AND s.simulation_day = f.simulation_day
                       AND l.is_fraud = 1) AS positives,
                   (SELECT count(*) FROM app.alert a JOIN truth.label l USING (event_id) WHERE a.run_id = f.run_id
                       AND a.partition_name = f.partition_name AND a.simulation_day = f.simulation_day
                       AND l.is_fraud = 1) AS true_positives,
                   f.alerts
            FROM app.day_finalization f WHERE f.run_id = %s ORDER BY f.simulation_day""", (run_id,)).fetchall()
    keys = ["partition", "day", "first_step", "last_step", "hours", "capacity", "population", "positives",
            "true_positives", "alerts"]
    segments = [dict(zip(keys, r)) for r in segs]
    for s in segments:
        s["precision"] = s["true_positives"] / s["alerts"] if s["alerts"] else None
        s["recall"] = s["true_positives"] / s["positives"] if s["positives"] else None
    tot = {k2: sum(s[k2] for s in segments) for k2 in ("population", "positives", "true_positives", "alerts")}
    tot["precision"] = tot["true_positives"] / tot["alerts"] if tot["alerts"] else None
    tot["recall"] = tot["true_positives"] / tot["positives"] if tot["positives"] else None

    # cross-check against the one-time offline test report for the same day segments
    offline = json.loads((config.REPORTS_DIR / "day3" / "final_test_report.json").read_text(encoding="utf-8"))
    off = {(s["partition"], s["day"]): s for s in offline["methods"]["champion"]["capacity"][str(k)]["segments"]}
    checks = []
    for s in segments:
        o = off.get((s["partition"], s["day"]))
        if o and o["hours"] == s["hours"]:
            checks.append({"day": s["day"], "offline_true_positives": o["true_positives"],
                           "replay_true_positives": s["true_positives"],
                           "offline_capacity": o["capacity"], "replay_capacity": s["capacity"],
                           "match": o["true_positives"] == s["true_positives"] and o["capacity"] == s["capacity"]})
    result = {"report": "day5-run-evaluation", "run_id": run_id, "model_version": model_version,
              "policy_version": policy, "daily_capacity": k, "steps": [first, last], "labels_loaded": loaded,
              "scope": "Evaluator-only aggregates for a recorded replay of synthetic data. No per-case labels are "
                       "exposed to the investigation workflow.",
              "segments": segments, "total": tot, "offline_segment_crosscheck": checks,
              "seconds": round(time.perf_counter() - started, 2)}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path(run_id).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
