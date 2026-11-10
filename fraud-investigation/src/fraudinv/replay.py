"""Recorded-transaction replay with checkpoint recovery (T13).

* Warm-up: a run starting at step s0 loads full prior recipient history from
  every unlabelled row with step < s0 (split-v1 history rule).
* Each simulation hour commits atomically: events, scores with score-time
  feature vectors, history-state update and the cursor. An interruption inside
  an hour rolls the whole hour back; resume restarts at cursor + 1.
* Day-end finalization of each (partition, simulation_day) segment is its own
  idempotent transaction; resume finalizes any completed segment left open.
Labels are never read by this module.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd
import psycopg

from . import config, splits
from .events import event_prefix as make_prefix
from .serving import FrozenModel, load_frozen, score_rows, tie_key, to_cents

COLUMNS = ["source_row", "step", "type", "amount", "nameOrig", "nameDest"]
WARMUP_RULE = "full prior warm-up: every unlabelled row with step < first_step (split-v1)"


class SimulatedCrash(RuntimeError):
    """Raised by fault injection inside an hour transaction."""


@dataclass(frozen=True)
class Source:
    parquet: Path
    prefix: str

    @classmethod
    def default(cls) -> "Source":
        src = config.data_source()
        return cls(config.paths().events_parquet, make_prefix(src["dataset_key"], src["csv"]["sha256"]))

    def rows(self, first: int, last: int) -> pd.DataFrame:
        with duckdb.connect() as con:
            df = con.execute(
                f"SELECT {', '.join(COLUMNS)} FROM read_parquet('{self.parquet.as_posix()}') "
                f"WHERE step BETWEEN {int(first)} AND {int(last)} ORDER BY source_row").df()
        df["event_id"] = self.prefix + "-" + df["source_row"].astype(str).str.zfill(7)
        return df

    def warmup(self, first_step: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Per-recipient aggregates and last-24-step counts from steps < first_step."""
        src = f"read_parquet('{self.parquet.as_posix()}')"
        with duckdb.connect() as con:
            con.execute("SET memory_limit='1GB'")
            hist = con.execute(f"""
                SELECT nameDest AS name_dest, count(*) AS prior_count,
                       sum(CAST(round(amount * 100) AS BIGINT)) AS prior_cents, max(step) AS last_step
                FROM {src} WHERE step < {int(first_step)} GROUP BY 1""").df()
            window = con.execute(f"""
                SELECT nameDest AS name_dest, step, count(*) AS n FROM {src}
                WHERE step >= {int(first_step) - 24} AND step < {int(first_step)} GROUP BY 1, 2""").df()
        return hist, window


def _segment_end(partition: str, day: int, run_last: int) -> int:
    lo, hi = splits.partitions()[partition]
    return min(24 * (day + 1), hi, run_last)


def create_run(conn: psycopg.Connection, run_id: str, first_step: int, last_step: int,
               capacity: int = 100, source: Source | None = None, frozen: FrozenModel | None = None) -> dict:
    _require_autocommit(conn)
    source = source or Source.default()
    frozen = frozen or load_frozen()
    rec = frozen.record
    started = time.perf_counter()
    hist, window = source.warmup(first_step)
    with conn.transaction():
        conn.execute("""
            INSERT INTO app.model_version (model_version, artifact_sha256, feature_contract, history_feature_table,
                                           split_protocol, policy_version, features, model_columns, frozen_record)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (model_version) DO NOTHING""",
            (rec["model_version"], rec["artifact"]["sha256"], rec["feature_contract"], rec["history_feature_table"],
             rec["split_protocol"], frozen.policy_version, json.dumps(rec["features"]),
             json.dumps(rec["model_columns"]), json.dumps(rec)))
        conn.execute("""
            INSERT INTO app.replay_run (run_id, dataset_key, csv_sha256, model_version, policy_version,
                                        daily_capacity, first_step, last_step, warmup_rule, warmup_through_step,
                                        committed_through_step, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'created')""",
            (run_id, config.data_source()["dataset_key"], rec["csv_sha256"], rec["model_version"],
             frozen.policy_version, capacity, first_step, last_step, WARMUP_RULE, first_step - 1, first_step - 1))
        with conn.cursor().copy("COPY app.recipient_history (run_id, name_dest, prior_count, prior_cents, last_step) "
                                "FROM STDIN") as cp:
            for r in hist.itertuples(index=False):
                cp.write_row((run_id, r.name_dest, int(r.prior_count), int(r.prior_cents), int(r.last_step)))
        with conn.cursor().copy("COPY app.recipient_step_count (run_id, name_dest, step, n) FROM STDIN") as cp:
            for r in window.itertuples(index=False):
                cp.write_row((run_id, r.name_dest, int(r.step), int(r.n)))
        conn.execute("INSERT INTO app.audit_event (run_id, actor, action, new_state) VALUES (%s, 'system', "
                     "'replay_created', %s)", (run_id, json.dumps({"first_step": first_step, "last_step": last_step,
                                                                   "warmup_recipients": len(hist)})))
    return {"run_id": run_id, "warmup_recipients": len(hist), "warmup_window_rows": len(window),
            "seconds": round(time.perf_counter() - started, 2)}


def _commit_hour(conn, frozen: FrozenModel, run: dict, rows: pd.DataFrame, step: int,
                 fail_after_scores: int | None) -> int:
    with conn.transaction():
        locked = conn.execute("SELECT committed_through_step FROM app.replay_run WHERE run_id = %s FOR UPDATE",
                              (run["run_id"],)).fetchone()[0]
        if locked != step - 1:
            raise RuntimeError(f"cursor at {locked}; cannot commit step {step}")
        conn.cursor().executemany(
            "INSERT INTO app.transaction_event (event_id, source_row, step, type, amount, name_orig, name_dest) "
            "VALUES (%s, %s, %s, %s, round(%s::numeric, 2), %s, %s) ON CONFLICT (event_id) DO NOTHING",
            [(r.event_id, int(r.source_row), int(r.step), r.type, float(r.amount), r.nameOrig, r.nameDest)
             for r in rows.itertuples(index=False)])
        scored = score_rows(conn, frozen, run["run_id"], rows[["step", "type", "amount", "nameDest"]], step)
        part = splits.assign_partition([step])[0]
        day = int(splits.simulation_day([step])[0])
        params = [(run["run_id"], eid, step, part, day, frozen.version, frozen.record["feature_contract"],
                   frozen.policy_version, float(s), json.dumps(f), h, tie_key(eid))
                  for eid, s, f, h in zip(rows["event_id"], scored["score"], scored["features"],
                                          scored["feature_sha256"])]
        sql = ("INSERT INTO app.score (run_id, event_id, scoring_step, partition_name, simulation_day, model_version, "
               "feature_contract, policy_version, score, features, feature_sha256, tie_key) "
               "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
        if fail_after_scores is not None:
            conn.cursor().executemany(sql, params[:fail_after_scores])
            raise SimulatedCrash(f"injected crash in step {step} after {fail_after_scores} of {len(params)} scores")
        conn.cursor().executemany(sql, params)
        # history update: this hour becomes visible only to later steps
        agg = (pd.DataFrame({"d": rows["nameDest"].to_numpy(), "c": to_cents(rows["amount"])})
               .groupby("d").agg(n=("c", "size"), c=("c", "sum")).reset_index())
        conn.cursor().executemany(
            "INSERT INTO app.recipient_history AS h (run_id, name_dest, prior_count, prior_cents, last_step) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (run_id, name_dest) DO UPDATE SET "
            "prior_count = h.prior_count + excluded.prior_count, prior_cents = h.prior_cents + excluded.prior_cents, "
            "last_step = excluded.last_step",
            [(run["run_id"], d, int(n), int(c), step) for d, n, c in agg.itertuples(index=False)])
        conn.cursor().executemany(
            "INSERT INTO app.recipient_step_count (run_id, name_dest, step, n) VALUES (%s, %s, %s, %s)",
            [(run["run_id"], d, step, int(n)) for d, n, _ in agg.itertuples(index=False)])
        conn.execute("DELETE FROM app.recipient_step_count WHERE run_id = %s AND step < %s",
                     (run["run_id"], step - 23))
        conn.execute("UPDATE app.replay_run SET committed_through_step = %s, status = 'running', updated_at = now() "
                     "WHERE run_id = %s", (step, run["run_id"]))
    return len(rows)


def finalize_segment(conn, run: dict, partition: str, day: int) -> bool:
    """Day-end top-K for one segment. Returns False if it was already finalized (idempotent)."""
    with conn.transaction():
        first, last, hours = conn.execute(
            "SELECT min(scoring_step), max(scoring_step), count(DISTINCT scoring_step) FROM app.score "
            "WHERE run_id = %s AND partition_name = %s AND simulation_day = %s",
            (run["run_id"], partition, day)).fetchone()
        if hours == 0:
            return False
        capacity = splits.segment_capacity(run["daily_capacity"], hours)
        ranked = conn.execute(
            "SELECT event_id, scoring_step FROM app.score WHERE run_id = %s AND partition_name = %s "
            "AND simulation_day = %s ORDER BY score DESC, tie_key ASC LIMIT %s",
            (run["run_id"], partition, day, capacity)).fetchall()
        inserted = conn.execute(
            "INSERT INTO app.day_finalization (run_id, partition_name, simulation_day, first_step, last_step, "
            "observed_hours, capacity, alerts) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING RETURNING 1",
            (run["run_id"], partition, day, first, last, hours, capacity, len(ranked))).fetchone()
        if not inserted:
            return False
        cutoff = _segment_end(partition, day, run["last_step"])
        for rank, (eid, sstep) in enumerate(ranked, start=1):
            conn.execute("INSERT INTO app.alert (run_id, event_id, partition_name, simulation_day, rank, capacity, "
                         "policy_version) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                         (run["run_id"], eid, partition, day, rank, capacity, run["policy_version"]))
            conn.execute("INSERT INTO app.review_case (case_id, run_id, event_id, scoring_step, "
                         "case_evidence_cutoff_step) VALUES (%s, %s, %s, %s, %s)",
                         (f"{run['run_id']}/{partition}/d{day}/r{rank:03d}", run["run_id"], eid, sstep, cutoff))
        conn.execute("INSERT INTO app.audit_event (run_id, actor, action, new_state) VALUES (%s, 'system', "
                     "'day_finalized', %s)", (run["run_id"], json.dumps(
                         {"partition": partition, "day": day, "capacity": capacity, "alerts": len(ranked),
                          "observed_hours": hours})))
    return True


def backfill_evidence(conn, source: Source, run_id: str, partition: str, day: int) -> int:
    """Itemize same-role records (step <= case cutoff) for a segment's alerted accounts.

    Copies label-free rows from the source into app.transaction_event so case evidence can list
    history from before the replay window. Recipient-history state (and thus scores) is untouched.
    Idempotent: existing events are skipped.
    """
    rows = conn.execute(
        "SELECT t.name_dest, t.name_orig, c.case_evidence_cutoff_step FROM app.review_case c "
        "JOIN app.alert a USING (run_id, event_id) JOIN app.transaction_event t USING (event_id) "
        "WHERE c.run_id = %s AND a.partition_name = %s AND a.simulation_day = %s",
        (run_id, partition, day)).fetchall()
    if not rows:
        return 0
    dests = sorted({r[0] for r in rows})
    origs = sorted({r[1] for r in rows})
    cutoff = max(r[2] for r in rows)
    with duckdb.connect() as con:
        df = con.execute(
            f"SELECT {', '.join(COLUMNS)} FROM read_parquet('{source.parquet.as_posix()}') "
            f"WHERE step <= ? AND (list_contains(?, nameDest) OR list_contains(?, nameOrig))",
            [cutoff, dests, origs]).df()
    df["event_id"] = source.prefix + "-" + df["source_row"].astype(str).str.zfill(7)
    with conn.transaction():
        cur = conn.cursor()
        cur.executemany(
            "INSERT INTO app.transaction_event (event_id, source_row, step, type, amount, name_orig, name_dest) "
            "VALUES (%s, %s, %s, %s, round(%s::numeric, 2), %s, %s) ON CONFLICT (event_id) DO NOTHING",
            [(r.event_id, int(r.source_row), int(r.step), r.type, float(r.amount), r.nameOrig, r.nameDest)
             for r in df.itertuples(index=False)])
    return len(df)


def _pending_segments(conn, run: dict) -> list[tuple[str, int]]:
    """Segments whose last step is committed but which are not yet finalized."""
    done = run["committed_through_step"]
    rows = conn.execute(
        "SELECT DISTINCT s.partition_name, s.simulation_day FROM app.score s "
        "LEFT JOIN app.day_finalization f USING (run_id, partition_name, simulation_day) "
        "WHERE s.run_id = %s AND f.run_id IS NULL ORDER BY 2", (run["run_id"],)).fetchall()
    return [(p, d) for p, d in rows if _segment_end(p, d, run["last_step"]) <= done]


def _require_autocommit(conn: psycopg.Connection) -> None:
    # In a non-autocommit session, conn.transaction() would become a savepoint inside an
    # implicit outer transaction, and an "hour commit" would not be durable on its own.
    if not conn.autocommit:
        raise ValueError("replay needs an autocommit connection (each hour is its own transaction)")


def get_run(conn, run_id: str) -> dict:
    cur = conn.execute("SELECT * FROM app.replay_run WHERE run_id = %s", (run_id,))
    row = cur.fetchone()
    if row is None:
        raise KeyError(run_id)
    return dict(zip([d.name for d in cur.description], row))


def run_replay(conn: psycopg.Connection, run_id: str, source: Source | None = None,
               frozen: FrozenModel | None = None, max_steps: int | None = None,
               fail_at: tuple[int, int] | None = None) -> dict:
    """Process hours after the cursor. ``fail_at=(step, n)`` injects a crash after n scores of that step."""
    _require_autocommit(conn)
    source = source or Source.default()
    frozen = frozen or load_frozen()
    run = get_run(conn, run_id)
    if run["model_version"] != frozen.version:
        raise RuntimeError("run was created with a different model version")
    started = time.perf_counter()
    finalized = [seg for seg in _pending_segments(conn, run) if finalize_segment(conn, run, *seg)]
    for seg in finalized:
        backfill_evidence(conn, source, run_id, *seg)
    start = run["committed_through_step"] + 1
    end = run["last_step"] if max_steps is None else min(run["last_step"], start + max_steps - 1)
    rows_done = 0
    if start <= end:
        rows = source.rows(start, end)
        for step in range(start, end + 1):
            hour = rows[rows["step"] == step]
            fail = fail_at[1] if fail_at and fail_at[0] == step else None
            try:
                rows_done += _commit_hour(conn, frozen, run, hour, step, fail)
            except Exception as exc:
                with conn.transaction():
                    conn.execute("UPDATE app.replay_run SET status = 'failed', error = %s, updated_at = now() "
                                 "WHERE run_id = %s", (str(exc)[:500], run_id))
                raise
            run["committed_through_step"] = step
            part = splits.assign_partition([step])[0]
            day = int(splits.simulation_day([step])[0])
            if _segment_end(part, day, run["last_step"]) == step and finalize_segment(conn, run, part, day):
                finalized.append((part, day))
                backfill_evidence(conn, source, run_id, part, day)
    status = "completed" if run["committed_through_step"] == run["last_step"] else "paused"
    with conn.transaction():
        conn.execute("UPDATE app.replay_run SET status = %s, error = NULL, updated_at = now() WHERE run_id = %s",
                     (status, run_id))
    return {"run_id": run_id, "status": status, "committed_through_step": run["committed_through_step"],
            "rows_scored": rows_done, "segments_finalized": finalized,
            "seconds": round(time.perf_counter() - started, 2)}
