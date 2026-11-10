"""Day 4 exit check on real PaySim rows (T13/T14), in a disposable database.

1. Uninterrupted replay of steps 356-365 (run A).
2. Same window with a crash halfway through step 357, then resume (run B).
3. A and B must have identical scores/feature hashes, day-end queues and cases.
4. Replay scores and feature values must equal the offline pipeline exactly.
5. Re-running a completed replay must write nothing.
"""
from __future__ import annotations

import json
import time

import duckdb
import numpy as np
import pandas as pd

from . import config, db, replay
from .features import feature_parquet
from .history import FEATURES
from .runtime import environment, machine_memory_gib, peak_rss_mib
from .serving import load_frozen

CHECK_DB = "fraudinv_day4_check"
FIRST, LAST, CRASH_STEP = 356, 365, 357


def _snapshot(conn, run_id):
    q = {"scores": "SELECT event_id, score, feature_sha256 FROM app.score WHERE run_id = %s ORDER BY 1",
         "alerts": "SELECT partition_name, simulation_day, rank, event_id FROM app.alert WHERE run_id = %s ORDER BY 1, 2, 3",
         "cases": "SELECT replace(case_id, run_id, ''), event_id, scoring_step, case_evidence_cutoff_step "
                  "FROM app.review_case WHERE run_id = %s ORDER BY 1"}
    return {k: conn.execute(v, (run_id,)).fetchall() for k, v in q.items()}


def run() -> dict:
    started = time.perf_counter()
    out: dict = {"check": "day4-replay-consistency", "window": [FIRST, LAST], "environment": environment()}
    db.drop_database(CHECK_DB)
    db.create_database(CHECK_DB)
    db.migrate(CHECK_DB)
    frozen = load_frozen()
    with db.connect("app", CHECK_DB, autocommit=True) as conn:
        out["create_A"] = replay.create_run(conn, "A", FIRST, LAST, frozen=frozen)
        out["replay_A"] = replay.run_replay(conn, "A", frozen=frozen)
        out["create_B"] = replay.create_run(conn, "B", FIRST, LAST, frozen=frozen)
        hour = int(conn.execute("SELECT count(*) FROM app.transaction_event WHERE step = %s",
                                (CRASH_STEP,)).fetchone()[0])
        try:
            replay.run_replay(conn, "B", frozen=frozen, fail_at=(CRASH_STEP, hour // 2))
            crashed = False
        except replay.SimulatedCrash as exc:
            crashed = str(exc)
        b = replay.get_run(conn, "B")
        partial = conn.execute("SELECT count(*) FROM app.score WHERE run_id = 'B' AND scoring_step = %s",
                               (CRASH_STEP,)).fetchone()[0]
        out["interruption"] = {"crash": crashed, "status_after_crash": b["status"],
                               "cursor_after_crash": b["committed_through_step"],
                               "scores_left_for_crashed_step": partial, "rows_in_crashed_step": hour}
        out["resume_B"] = replay.run_replay(conn, "B", frozen=frozen)
        a_snap, b_snap = _snapshot(conn, "A"), _snapshot(conn, "B")
        out["interrupted_equals_uninterrupted"] = {k: a_snap[k] == b_snap[k] for k in a_snap}
        out["counts"] = {k: len(v) for k, v in a_snap.items()}
        rerun = replay.run_replay(conn, "A", frozen=frozen)
        out["rerun_completed_A"] = {"rows_scored": rerun["rows_scored"], "segments": rerun["segments_finalized"],
                                    "unchanged": _snapshot(conn, "A") == a_snap}
        online = pd.DataFrame(conn.execute(
            "SELECT t.source_row, s.score, s.features FROM app.score s JOIN app.transaction_event t "
            "USING (event_id) WHERE s.run_id = 'A'").fetchall(), columns=["source_row", "score", "features"])
        out["segments"] = [dict(zip(["partition", "day", "first_step", "last_step", "hours", "capacity", "alerts"], r))
                           for r in conn.execute("SELECT partition_name, simulation_day, first_step, last_step, "
                                                 "observed_hours, capacity, alerts FROM app.day_finalization "
                                                 "WHERE run_id = 'A' ORDER BY 2").fetchall()]
        out["memory_during"] = machine_memory_gib()

    with duckdb.connect() as con:
        off = con.execute(f"""
            SELECT e.source_row, e.step, e.type, e.amount, f.* EXCLUDE (source_row)
            FROM read_parquet('{config.paths().events_parquet.as_posix()}') e
            JOIN read_parquet('{feature_parquet().as_posix()}') f USING (source_row)
            WHERE e.step BETWEEN {FIRST} AND {LAST}""").df()
    off["offline_score"] = frozen.score(off)
    m = off.merge(online, on="source_row")
    mism = {}
    for f in FEATURES:
        got = np.array([np.nan if x[f] is None else x[f] for x in m["features"]], dtype=float)
        exp = m[f].astype(float).to_numpy()
        mism[f] = int((~((got == exp) | (np.isnan(got) & np.isnan(exp)))).sum())
    out["offline_parity"] = {"offline_rows": len(off), "replay_rows": len(online), "matched": len(m),
                             "max_abs_score_diff": float(np.abs(m["score"] - m["offline_score"]).max()),
                             "exactly_equal_scores": int((m["score"] == m["offline_score"]).sum()),
                             "feature_mismatches": mism}
    out["passed"] = (bool(out["interruption"]["crash"]) and out["interruption"]["scores_left_for_crashed_step"] == 0
                     and all(out["interrupted_equals_uninterrupted"].values())
                     and out["rerun_completed_A"]["rows_scored"] == 0 and out["rerun_completed_A"]["unchanged"]
                     and len(m) == len(off) == len(online) and out["offline_parity"]["max_abs_score_diff"] == 0.0
                     and not any(mism.values()))
    out["runtime"] = {"total_seconds": round(time.perf_counter() - started, 2), "peak_python_process_mib": peak_rss_mib()}
    path = config.REPORTS_DIR / "day4" / "replay_consistency.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    db.drop_database(CHECK_DB)
    return out
