"""Partition loading with a test-access guard.

The test partition can be read only after a frozen selection record exists
(``reports/frozen/selection.json``) and the caller passes ``allow_test=True``.
Development code paths never pass that flag.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from . import config, splits
from .events import event_prefix

FROZEN_SELECTION = config.REPORTS_DIR / "frozen" / "selection.json"
SCORE_TIME_COLUMNS = ["source_row", "step", "type", "amount", "nameOrig", "nameDest"]
EVALUATION_COLUMNS = ["isFraud", "isFlaggedFraud"]


class TestAccessError(PermissionError):
    pass


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'; SET threads=4")
    return con


def load_steps(first: int, last: int, columns: list[str], parquet: Path | None = None) -> pd.DataFrame:
    parquet = parquet or config.paths().events_parquet
    cols = ", ".join(columns)
    with _connect() as con:
        return con.execute(
            f"SELECT {cols} FROM read_parquet('{parquet.as_posix()}') "
            f"WHERE step BETWEEN {int(first)} AND {int(last)} ORDER BY source_row").df()


def check_access(name: str, allow_test: bool) -> None:
    if name == "test":
        if not allow_test:
            raise TestAccessError("test partition is sealed; development code must not read it")
        if not FROZEN_SELECTION.exists():
            raise TestAccessError(f"no frozen selection at {FROZEN_SELECTION}; freeze model/policy first")


def load_partition(name: str, with_labels: bool = True, allow_test: bool = False,
                   columns: list[str] | None = None) -> pd.DataFrame:
    check_access(name, allow_test)
    lo, hi = splits.partitions()[name]
    cols = (columns or SCORE_TIME_COLUMNS) + (EVALUATION_COLUMNS if with_labels else [])
    df = load_steps(lo, hi, cols)
    df["type"] = df["type"].astype("category")
    df["partition"] = name
    df["day"] = splits.simulation_day(df["step"])
    return df


def add_event_ids(df: pd.DataFrame) -> pd.DataFrame:
    src = config.data_source()
    prefix = event_prefix(src["dataset_key"], src["csv"]["sha256"])
    df["event_id"] = prefix + "-" + df["source_row"].astype(str).str.zfill(7)
    return df
