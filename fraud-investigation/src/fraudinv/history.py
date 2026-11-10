"""Recipient-history features using strictly earlier steps.

Two implementations of the same contract:

* ``recipient_history`` - vectorized, for offline feature building.
* ``RecipientHistoryState`` - incremental, for replay/serving. Score a whole
  step from the state, then ``update`` the state with that step.

Rows within one step are simultaneous: neither implementation lets a row see
another row from the same step. Amount sums use integer cents, so results are
exact and independent of row order. Labels never enter either implementation.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

WINDOW_STEPS = 24
FEATURES = ["dest_has_prior", "dest_prior_count", "dest_prior_amount_sum",
            "dest_prior_count_24h", "dest_steps_since_last"]
REQUIRED = ["step", "nameDest", "amount"]


def to_cents(amount: pd.Series | np.ndarray) -> np.ndarray:
    return np.rint(np.asarray(amount, dtype=np.float64) * 100).astype(np.int64)


def recipient_history(df: pd.DataFrame) -> pd.DataFrame:
    """Return history features aligned to ``df.index``."""
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise KeyError(f"missing columns {missing}")
    work = pd.DataFrame({"nameDest": df["nameDest"].to_numpy(),
                         "step": df["step"].to_numpy(np.int64),
                         "cents": to_cents(df["amount"])})
    per_step = (work.groupby(["nameDest", "step"], sort=True)
                .agg(n=("cents", "size"), c=("cents", "sum")).reset_index())
    grp = per_step.groupby("nameDest", sort=False)
    per_step["cum_n"] = grp["n"].cumsum()
    per_step["prior_n"] = per_step["cum_n"] - per_step["n"]
    per_step["prior_c"] = grp["c"].cumsum() - per_step["c"]
    per_step["last_step"] = grp["step"].shift(1)

    # rows with step <= s - 25 are outside the 24-step window [s-24, s-1]
    left = per_step[["nameDest", "step"]].assign(lookup=per_step["step"] - (WINDOW_STEPS + 1))
    left = left.sort_values("lookup")
    right = per_step[["nameDest", "step", "cum_n"]].rename(
        columns={"step": "rstep", "cum_n": "old_n"}).sort_values("rstep")
    old = pd.merge_asof(left, right, left_on="lookup", right_on="rstep",
                        by="nameDest", direction="backward")
    old["old_n"] = old["old_n"].fillna(0).astype(np.int64)
    per_step = per_step.merge(old[["nameDest", "step", "old_n"]], on=["nameDest", "step"])
    per_step["prior_24h"] = per_step["prior_n"] - per_step["old_n"]

    # ``work`` has a RangeIndex, so "pos" is the row position in ``df``; realign by position
    out = work[["nameDest", "step"]].rename_axis("pos").reset_index().merge(
        per_step[["nameDest", "step", "prior_n", "prior_c", "last_step", "prior_24h"]],
        on=["nameDest", "step"], how="left").sort_values("pos")
    out.index = df.index
    result = pd.DataFrame(index=df.index)
    result["dest_has_prior"] = (out["prior_n"] > 0).astype(np.int8)
    result["dest_prior_count"] = out["prior_n"].astype(np.int64)
    result["dest_prior_amount_sum"] = out["prior_c"].astype(np.int64) / 100.0
    result["dest_prior_count_24h"] = out["prior_24h"].astype(np.int64)
    result["dest_steps_since_last"] = (out["step"] - out["last_step"]).astype("float64")
    return result


@dataclass
class _DestState:
    count: int = 0
    cents: int = 0
    last_step: int | None = None
    recent: deque = field(default_factory=deque)  # (step, count) for the last 24 steps


class RecipientHistoryState:
    """Incremental history for replay. Holds only unlabelled fields."""

    def __init__(self) -> None:
        self._dest: dict[str, _DestState] = {}
        self.through_step: int = 0  # every step <= through_step has been applied

    def features(self, rows: pd.DataFrame, step: int) -> pd.DataFrame:
        """Features for rows of ``step``; requires the state to end at step - 1 or earlier."""
        if step <= self.through_step:
            raise ValueError(f"state already includes step {self.through_step}; cannot score step {step}")
        if (rows["step"] != step).any():
            raise ValueError("all rows must belong to the scored step")
        values = []
        for dest in rows["nameDest"]:
            s = self._dest.get(dest)
            if s is None or s.count == 0:
                values.append((0, 0, 0.0, 0, np.nan))
                continue
            in_window = sum(n for st, n in s.recent if st >= step - WINDOW_STEPS)
            values.append((1, s.count, s.cents / 100.0, in_window, float(step - s.last_step)))
        out = pd.DataFrame(values, columns=FEATURES, index=rows.index)
        return out.astype({"dest_has_prior": np.int8, "dest_prior_count": np.int64,
                           "dest_prior_count_24h": np.int64})

    def update(self, rows: pd.DataFrame, step: int) -> None:
        """Apply one complete step after it has been scored."""
        if step <= self.through_step:
            raise ValueError(f"step {step} already applied (through {self.through_step})")
        if "isFraud" in rows.columns or "isFlaggedFraud" in rows.columns:
            raise ValueError("labels/policy flags must not enter history state")
        cents = to_cents(rows["amount"])
        for dest, c in zip(rows["nameDest"], cents):
            s = self._dest.setdefault(dest, _DestState())
            s.count += 1
            s.cents += int(c)
            s.last_step = step
            if s.recent and s.recent[-1][0] == step:
                s.recent[-1] = (step, s.recent[-1][1] + 1)
            else:
                s.recent.append((step, 1))
            while s.recent and s.recent[0][0] < step - WINDOW_STEPS + 1:
                s.recent.popleft()
        self.through_step = step
