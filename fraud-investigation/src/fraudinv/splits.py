"""Frozen chronological partitions and simulation-day helpers."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config


def partitions() -> dict[str, tuple[int, int]]:
    raw = config.split_protocol()["partitions"]
    return {name: (int(b["first_step"]), int(b["last_step"])) for name, b in raw.items()}


def validate_partitions(bounds: dict[str, tuple[int, int]], min_step: int, max_step: int) -> None:
    """Partitions must be ordered, contiguous, whole-hour and cover the observed range."""
    ordered = sorted(bounds.values())
    if ordered[0][0] != min_step or ordered[-1][1] != max_step:
        raise ValueError(f"partitions {ordered} do not cover {min_step}-{max_step}")
    for (lo, hi), (nlo, _) in zip(ordered, ordered[1:]):
        if lo > hi or nlo != hi + 1:
            raise ValueError(f"partitions not contiguous: {ordered}")


def assign_partition(steps: pd.Series | np.ndarray) -> np.ndarray:
    steps = np.asarray(steps)
    out = np.full(steps.shape, None, dtype=object)
    for name, (lo, hi) in partitions().items():
        out[(steps >= lo) & (steps <= hi)] = name
    if (out == None).any():  # noqa: E711 - elementwise comparison on object array
        raise ValueError("step outside frozen partitions")
    return out


def simulation_day(steps: pd.Series | np.ndarray) -> np.ndarray:
    return (np.asarray(steps) - 1) // 24


def segment_capacity(k: int, observed_hours: int) -> int:
    """Pro-rated daily capacity for a partial partition-day segment (half rounds up)."""
    return max(1, math.floor(k * observed_hours / 24 + 0.5))
