"""Fresh-setup reproduction check (T17/T18).

Copies source/config only (no .venv, data, models, reports, node_modules, .env) to a new folder,
builds a new venv from requirements.lock, reruns the pipeline from the verified raw CSV into a new
data directory, and compares key results with this checkout's reports. The final-test step here
reproduces the already-frozen pipeline; it is not used for any further selection.

Usage: .venv\\Scripts\\python scripts\\fresh_setup_check.py <empty-target-dir>
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
COPY = ["src", "config", "sql", "tests", "eval", "fixtures", "pyproject.toml", "requirements.lock", "README.md",
        "docker-compose.yml", ".env.example", ".gitignore", "web/src", "web/index.html", "web/package.json",
        "web/package-lock.json", "web/tsconfig.json", "web/vite.config.ts"]


def sh(cmd: list[str], cwd: Path, env: dict, log: list, timeout: int = 3600) -> subprocess.CompletedProcess:
    t = time.perf_counter()
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, shell=(os.name == "nt" and cmd[0] == "npm"))
    log.append({"cmd": " ".join(cmd[1:] if cmd[0].endswith("python.exe") else cmd), "returncode": p.returncode,
                "seconds": round(time.perf_counter() - t, 1), "tail": (p.stdout + p.stderr)[-600:]})
    print(f"  [{p.returncode}] {log[-1]['cmd']} ({log[-1]['seconds']}s)", flush=True)
    return p


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def main(target: Path) -> int:
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"{target} must be empty")
    started = time.perf_counter()
    for item in COPY:
        src, dst = APP / item, target / item
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
        elif src.exists():
            shutil.copy2(src, dst)
    log: list = []
    env = {k: v for k, v in os.environ.items() if not k.startswith(("FRAUDINV_", "VIRTUAL_ENV"))}
    env.update({"FRAUDINV_RAW_ARCHIVE": str((APP / "../outputs/data/PaySim_v2.zip").resolve()),
                "FRAUDINV_RAW_CSV": str((APP / "../work/data/raw/paysim-v2.csv").resolve()),
                "FRAUDINV_DATA_DIR": str(target / "data")})
    sh([sys.executable, "-m", "venv", ".venv"], target, env, log)
    py = str(target / ".venv" / "Scripts" / "python.exe") if os.name == "nt" else str(target / ".venv/bin/python")
    sh([py, "-m", "pip", "install", "--quiet", "-r", "requirements.lock"], target, env, log)
    sh([py, "-m", "pip", "install", "--quiet", "--no-deps", "-e", ".[dev]"], target, env, log)
    for step in (["verify"], ["ingest"], ["audit", "--skip-verify"], ["features"], ["evaluate-dev"], ["select"],
                 ["freeze"], ["final-test"]):
        sh([py, "-m", "fraudinv", *step], target, env, log)
    sh([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"], target, env, log)
    sh(["npm", "ci", "--no-fund", "--no-audit"], target / "web", env, log)
    sh(["npm", "run", "build"], target / "web", env, log)

    o, n = APP / "reports", target / "reports"
    cmp = {}
    a0, a1 = load(o / "day1/data_quality_audit.json"), load(n / "day1/data_quality_audit.json")
    cmp["audit_partition_support"] = a0["partition_support"]["by_partition"] == a1["partition_support"]["by_partition"]
    cmp["audit_recipient_history"] = a0["recipient_history"]["overall"] == a1["recipient_history"]["overall"]
    cmp["audit_duplicates"] = a0["duplicates"]["exact_all_columns"] == a1["duplicates"]["exact_all_columns"]
    d0, d1 = load(o / "day2/validation_report.json"), load(n / "day2/validation_report.json")
    cmp["dev_report_ranking"] = {m: d0["methods"][m].get("ranking") == d1["methods"][m].get("ranking") for m in d0["methods"]}
    s0, s1 = load(o / "day3/selection_report.json"), load(n / "day3/selection_report.json")
    cmp["selection_decision"] = s0["decision"]["champion"] == s1["decision"]["champion"]
    cmp["selection_candidate_aps"] = [c["validation_ap"] for c in s0["candidates"]] == [c["validation_ap"] for c in s1["candidates"]]
    f0, f1 = load(o / "frozen/selection.json"), load(n / "frozen/selection.json")
    cmp["frozen_validation_ap"] = f0["validation_ap_reproduced"] == f1["validation_ap_reproduced"]
    cmp["frozen_artifact_sha256_identical"] = f0["artifact"]["sha256"] == f1["artifact"]["sha256"]
    t0, t1 = load(o / "day3/final_test_report.json"), load(n / "day3/final_test_report.json")
    cmp["final_test_point_metrics"] = {
        m: (t0["methods"][m]["ranking"] == t1["methods"][m]["ranking"]
            and t0["methods"][m]["capacity"]["100"]["all_segments"] == t1["methods"][m]["capacity"]["100"]["all_segments"])
        for m in t0["methods"]}
    cmp["final_test_bootstrap"] = t0["bootstrap"]["intervals"] == t1["bootstrap"]["intervals"]

    def flat(x):
        return all(flat(v) for v in x.values()) if isinstance(x, dict) else bool(x)
    result = {"report": "day7-fresh-setup", "target": str(target), "steps": log,
              "all_steps_succeeded": all(s["returncode"] == 0 for s in log), "comparisons": cmp,
              "all_comparisons_equal": flat(cmp), "total_seconds": round(time.perf_counter() - started, 1),
              "notes": ["DB integration tests skip in the fresh copy because .env (local credentials) is not copied; "
                        "they pass in the main checkout.",
                        "final-test in the copy re-scores the frozen pipeline to check reproducibility; no selection "
                        "or tuning uses it."]}
    out = APP / "reports" / "day7" / "fresh_setup.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"all_steps_succeeded": result["all_steps_succeeded"],
                      "all_comparisons_equal": result["all_comparisons_equal"], "comparisons": cmp,
                      "total_seconds": result["total_seconds"]}, indent=2))
    return 0 if result["all_steps_succeeded"] and result["all_comparisons_equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
