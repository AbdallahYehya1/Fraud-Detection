"""Ranking and review-capacity evaluation.

Scores are ranking scores. Daily top-K is an offline day-end policy applied to
each (partition, simulation_day) segment of the full population; capacity for
partial segments is pro-rated (``splits.segment_capacity``). Equal scores are
ordered by the label-independent ``tie_key`` (sha256 of event_id). Native
policy flags are reported separately with their own denominators.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from .splits import segment_capacity


def tie_keys(event_ids: pd.Series) -> np.ndarray:
    """uint64 from the first 16 hex digits of sha256(event_id); deterministic, label-free."""
    return np.fromiter((int(hashlib.sha256(e.encode()).hexdigest()[:16], 16) for e in event_ids),
                       dtype=np.uint64, count=len(event_ids))


def seeded_random_scores(event_ids: pd.Series, seed: int) -> np.ndarray:
    """Label-independent uniform scores in [0, 1) from sha256(seed:event_id)."""
    return np.fromiter((int(hashlib.sha256(f"{seed}:{e}".encode()).hexdigest()[:13], 16) / 16**13
                        for e in event_ids), dtype=np.float64, count=len(event_ids))


def ranking_metrics(y: np.ndarray, score: np.ndarray) -> dict:
    y = np.asarray(y)
    out = {"rows": int(len(y)), "positives": int(y.sum()), "prevalence": float(y.mean()) if len(y) else None}
    if 0 < y.sum() < len(y):
        out["average_precision"] = float(average_precision_score(y, score))
        out["roc_auc"] = float(roc_auc_score(y, score))
    else:
        out["average_precision"] = out["roc_auc"] = None
    return out


def select_daily_topk(frame: pd.DataFrame, score: np.ndarray, k: int) -> pd.DataFrame:
    """Return per-row selection for a daily capacity ``k``.

    ``frame`` needs: partition, day, step, tie_key. Output adds rank_in_segment,
    capacity, selected, segment_hours. Labels are not read here.
    """
    df = frame[["partition", "day", "step", "tie_key"]].copy()
    df["score"] = score
    # descending score, then ascending tie key: lexsort keys go last-to-first
    order = np.lexsort((df["tie_key"].to_numpy(), -df["score"].to_numpy(),
                        df["day"].to_numpy(), df["partition"].astype(str).to_numpy()))
    df = df.iloc[order]
    seg = df.groupby(["partition", "day"], sort=False, observed=True)
    df["rank_in_segment"] = seg.cumcount() + 1
    hours = seg["step"].transform("nunique")
    df["segment_hours"] = hours
    df["capacity"] = hours.map({h: segment_capacity(k, int(h)) for h in hours.unique()})
    df["selected"] = df["rank_in_segment"] <= df["capacity"]
    return df.loc[frame.index, ["rank_in_segment", "capacity", "segment_hours", "selected"]]


def capacity_metrics(y: np.ndarray, selected: np.ndarray) -> dict:
    y, selected = np.asarray(y).astype(bool), np.asarray(selected).astype(bool)
    tp = int((y & selected).sum())
    alerts = int(selected.sum())
    pos = int(y.sum())
    neg = int((~y).sum())
    fp = alerts - tp
    return {"alerts": alerts, "true_positives": tp, "false_alerts": fp, "positives": pos,
            "legitimate": neg,
            "precision": tp / alerts if alerts else None,
            "recall": tp / pos if pos else None,
            "false_alerts_per_1000_legitimate": 1000 * fp / neg if neg else None}


def daily_capacity_report(frame: pd.DataFrame, y: np.ndarray, score: np.ndarray, k: int) -> dict:
    sel = select_daily_topk(frame, score, k)
    full = capacity_metrics(y, sel["selected"])
    complete = (sel["segment_hours"] == 24).to_numpy()
    days = []
    for (part, day), idx in frame.groupby(["partition", "day"], observed=True).groups.items():
        m = capacity_metrics(y[frame.index.get_indexer(idx)], sel.loc[idx, "selected"])
        days.append({"partition": part, "day": int(day), "hours": int(sel.loc[idx, "segment_hours"].iloc[0]),
                     "capacity": int(sel.loc[idx, "capacity"].iloc[0]), **m})
    return {"k": k, "all_segments": full,
            "complete_days_only": capacity_metrics(y[complete], sel["selected"].to_numpy()[complete]),
            "segments": days, "selected": sel["selected"].to_numpy()}


def native_policy_report(y: np.ndarray, flag: np.ndarray) -> dict:
    """The supplied isFlaggedFraud policy at its own native workload (not a top-K ranking)."""
    return {"policy": "isFlaggedFraud (native)", **capacity_metrics(y, flag)}


def breakdown(frame: pd.DataFrame, y: np.ndarray, score: np.ndarray, selected: np.ndarray, by: str) -> list[dict]:
    rows = []
    for key, idx in frame.groupby(by, observed=True).groups.items():
        pos = frame.index.get_indexer(idx)
        rows.append({by: key if not isinstance(key, np.integer) else int(key),
                     **ranking_metrics(y[pos], score[pos]), **{f"cap_{k}": v for k, v in
                                                               capacity_metrics(y[pos], selected[pos]).items()}})
    return rows


def hour_label_mix(frame: pd.DataFrame, y: np.ndarray) -> np.ndarray:
    """Evaluator-only: 'pure_positive', 'mixed' or 'no_positive' per row's hour."""
    tmp = pd.DataFrame({"step": frame["step"].to_numpy(), "y": y})
    g = tmp.groupby("step")["y"].agg(["sum", "size"])
    kind = np.where(g["sum"] == g["size"], "pure_positive", np.where(g["sum"] > 0, "mixed", "no_positive"))
    return tmp["step"].map(pd.Series(kind, index=g.index)).to_numpy()


def mixed_hour_diagnostics(frame: pd.DataFrame, y: np.ndarray, score: np.ndarray, selected: np.ndarray) -> dict:
    """Evaluator-only diagnostics. Never used as a feature or serving filter."""
    kind = hour_label_mix(frame, y)
    out = {}
    for k in ("mixed", "pure_positive", "no_positive"):
        m = kind == k
        out[k] = {"rows": int(m.sum()), "positives": int(y[m].sum()),
                  "selected_true_positives": int((y[m].astype(bool) & selected[m]).sum()),
                  "ranking": ranking_metrics(y[m], score[m]) if m.any() else None}
    return out
