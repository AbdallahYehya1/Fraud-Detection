"""Offline score-time feature table (T09), built in DuckDB.

Implements the same contract as ``fraudinv.history`` (strictly earlier steps,
same-step rows never visible, integer-cent sums) for all 6.36M rows without
loading string keys into pandas. Only unlabelled fields are read. Output is
keyed by ``source_row`` and stored under the data directory.
"""
from __future__ import annotations

import time
from pathlib import Path

import duckdb

from . import config

FEATURE_VERSION = "features-v1"
HISTORY_COLUMNS = ["dest_has_prior", "dest_prior_count", "dest_prior_amount_sum",
                   "dest_prior_count_24h", "dest_steps_since_last"]


def feature_parquet() -> Path:
    return config.paths().data_dir / "features" / f"history_{FEATURE_VERSION}.parquet"


HISTORY_SQL = """
WITH ev AS (SELECT source_row, step, nameDest, CAST(round(amount * 100) AS BIGINT) AS cents
            FROM read_parquet('{src}') {where}),
per AS (SELECT nameDest, step, count(*) AS n, sum(cents) AS c FROM ev GROUP BY 1, 2),
h AS (
  SELECT nameDest, step,
         coalesce(sum(n) OVER w_all, 0) AS prior_n,
         coalesce(sum(c) OVER w_all, 0) AS prior_c,
         coalesce(sum(n) OVER (PARTITION BY nameDest ORDER BY step
                               RANGE BETWEEN 24 PRECEDING AND 1 PRECEDING), 0) AS prior_24h,
         lag(step) OVER (PARTITION BY nameDest ORDER BY step) AS last_step
  FROM per
  WINDOW w_all AS (PARTITION BY nameDest ORDER BY step ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING))
SELECT ev.source_row,
       CAST(h.prior_n > 0 AS TINYINT) AS dest_has_prior,
       CAST(h.prior_n AS BIGINT) AS dest_prior_count,
       CAST(h.prior_c AS DOUBLE) / 100.0 AS dest_prior_amount_sum,
       CAST(h.prior_24h AS BIGINT) AS dest_prior_count_24h,
       CAST(ev.step - h.last_step AS DOUBLE) AS dest_steps_since_last
FROM ev JOIN h USING (nameDest, step)
"""


def build(out: Path | None = None, max_step: int | None = None, memory_limit: str = "2GB") -> dict:
    """Build the history feature table. ``max_step`` limits input rows (history inside the subset only)."""
    started = time.perf_counter()
    src = config.paths().events_parquet
    out = out or feature_parquet()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.paths().data_dir / "duckdb_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    where = f"WHERE step <= {int(max_step)}" if max_step else ""
    sql = HISTORY_SQL.format(src=src.as_posix(), where=where)
    with duckdb.connect() as con:
        con.execute(f"SET memory_limit='{memory_limit}'; SET threads=4; SET temp_directory='{tmp.as_posix()}'")
        con.execute(f"COPY ({sql} ORDER BY source_row) TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
        rows = con.execute(f"SELECT count(*) FROM read_parquet('{out.as_posix()}')").fetchone()[0]
    return {"path": str(out), "rows": rows, "feature_version": FEATURE_VERSION,
            "elapsed_seconds": round(time.perf_counter() - started, 2)}
