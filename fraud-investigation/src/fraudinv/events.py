"""Stable event identity.

An event ID is derived from the dataset key, the first 8 hex digits of the
verified CSV SHA-256, and the 0-based data-row position in the original file
(header excluded): ``PS2-16910f90-0000000``. It is a project identifier, not an
original bank transaction ID. It is assigned before any sort or filter.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

ROW_WIDTH = 7  # 6,362,620 rows fit in 7 digits


def event_prefix(dataset_key: str, csv_sha256: str) -> str:
    return f"{dataset_key}-{csv_sha256[:8]}"


def event_id(prefix: str, source_row: int) -> str:
    return f"{prefix}-{source_row:0{ROW_WIDTH}d}"


def attach_event_ids(df: pd.DataFrame, prefix: str, start_row: int = 0) -> pd.DataFrame:
    """Return a copy with ``source_row`` and ``event_id`` for rows in file order."""
    if "source_row" in df.columns or "event_id" in df.columns:
        raise ValueError("event identity already assigned; reassigning would break provenance")
    out = df.copy()
    rows = np.arange(start_row, start_row + len(out), dtype=np.int64)
    out.insert(0, "source_row", rows)
    out.insert(0, "event_id", [event_id(prefix, int(r)) for r in rows])
    return out


def tie_break_rank(event_ids: pd.Series) -> pd.Series:
    """Label-independent deterministic tie-break key: first 16 hex of sha256(event_id)."""
    return event_ids.map(lambda e: hashlib.sha256(e.encode()).hexdigest()[:16])
