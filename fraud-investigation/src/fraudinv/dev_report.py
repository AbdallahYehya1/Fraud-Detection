"""Day 2 development report (T07/T08): baselines evaluated on validation only.

The test partition is never loaded here (``data.load_partition`` refuses it).
A development backtest inside the training window (fit 1-209, evaluate
210-281) gives a second, earlier look at temporal stability.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, data, evaluation as ev
from .baselines import BASE_FEATURES, amount_type_rule, base_matrix, logistic_pipeline, model_columns, \
    rule_types_from_training
from .contract import FeatureContract
from .runtime import environment, peak_rss_mib

CAPACITIES = [50, 100, 200]
C_GRID = [0.01, 1.0, 100.0]
BACKTEST = {"fit": (1, 209), "evaluate": (210, 281)}


def _strip(report: dict) -> dict:
    report = dict(report)
    report.pop("selected", None)
    return report


def evaluate_scores(frame: pd.DataFrame, score: np.ndarray, detail: bool = True) -> dict:
    y = frame["isFraud"].to_numpy()
    out = {"ranking": ev.ranking_metrics(y, score), "capacity": {}}
    for k in CAPACITIES:
        rep = ev.daily_capacity_report(frame, y, score, k)
        sel = rep["selected"]
        out["capacity"][str(k)] = _strip(rep) if detail else {
            kk: rep[kk] for kk in ("k", "all_segments", "complete_days_only")}
        if k == 100 and detail:
            out["by_type_k100"] = ev.breakdown(frame, y, score, sel, "type")
            out["mixed_hour_diagnostics_k100"] = ev.mixed_hour_diagnostics(frame, y, score, sel)
    return out


def _frame(df: pd.DataFrame) -> pd.DataFrame:
    df = data.add_event_ids(df.reset_index(drop=True))
    df["tie_key"] = ev.tie_keys(df["event_id"])
    return df


def run(out_dir: Path) -> dict:
    started = time.perf_counter()
    proto = config.split_protocol()
    seed = int(proto["seeds"]["global"])
    contract = FeatureContract.load()
    timings = {}

    t = time.perf_counter()
    cols = ["source_row", "step", "type", "amount"]
    train = data.load_partition("train", columns=cols)
    valid = _frame(data.load_partition("validation", columns=cols))
    timings["load"] = round(time.perf_counter() - t, 2)

    result: dict = {"report": "day2-development", "partition_evaluated": "validation",
                    "test_partition_accessed": False,
                    "protocol": proto["protocol_version"], "feature_contract": contract.version,
                    "capacities_per_day": CAPACITIES, "environment": environment(),
                    "population": {"train_rows": len(train), "train_positives": int(train["isFraud"].sum()),
                                   "validation_rows": len(valid),
                                   "validation_positives": int(valid["isFraud"].sum())},
                    "methods": {}}
    yv = valid["isFraud"].to_numpy()

    # 1. all-negative sanity reference
    zero = np.zeros(len(valid))
    m = evaluate_scores(valid, zero, detail=False)
    m["accuracy_if_nothing_alerted"] = float(1 - yv.mean())
    m["note"] = ("Constant score: AP equals prevalence; top-K under a constant score is the tie-break "
                 "order, i.e. a label-independent arbitrary selection. The all-negative policy itself "
                 "alerts nothing.")
    result["methods"]["all_negative"] = m

    # 2. native policy comparator (own workload, not a ranking)
    result["methods"]["native_policy"] = ev.native_policy_report(yv, valid["isFlaggedFraud"].to_numpy())

    # 3. seeded random daily ranking
    t = time.perf_counter()
    rnd = ev.seeded_random_scores(valid["event_id"], int(proto["seeds"]["random_daily_ranking"]))
    result["methods"]["seeded_random"] = evaluate_scores(valid, rnd)
    timings["random"] = round(time.perf_counter() - t, 2)

    # 4. amount/type rule (type set from training labels only)
    types = rule_types_from_training(train)
    rule = amount_type_rule(valid, types)
    result["methods"]["amount_type_rule"] = {"types_from_training": types, **evaluate_scores(valid, rule)}

    # 5. logistic regression on the base feature set, C chosen on validation AP
    t = time.perf_counter()
    xt, yt = base_matrix(train), train["isFraud"].to_numpy()
    xv = base_matrix(valid)
    grid = []
    best = None
    for c in C_GRID:
        pipe = logistic_pipeline(contract, c, seed).fit(xt, yt)
        contract.check_frame_columns(model_columns(pipe))
        score = pipe.predict_proba(xv)[:, 1]
        ap = ev.ranking_metrics(yv, score)["average_precision"]
        grid.append({"C": c, "validation_average_precision": ap})
        if best is None or ap > best[0]:
            best = (ap, c, pipe, score)
    _, c_best, pipe, score = best
    coefs = dict(zip(model_columns(pipe), pipe.named_steps["model"].coef_[0].round(4).tolist()))
    result["methods"]["logistic_regression"] = {
        "features": BASE_FEATURES, "model_columns": model_columns(pipe), "C_grid": grid, "C_selected": c_best,
        "coefficients": coefs, "intercept": float(pipe.named_steps["model"].intercept_[0]),
        **evaluate_scores(valid, score)}
    timings["logistic_regression"] = round(time.perf_counter() - t, 2)

    # 6. development backtest inside the training window
    t = time.perf_counter()
    fit_lo, fit_hi = BACKTEST["fit"]
    ev_lo, ev_hi = BACKTEST["evaluate"]
    bt_fit = train[(train["step"] >= fit_lo) & (train["step"] <= fit_hi)]
    bt_eval = train[(train["step"] >= ev_lo) & (train["step"] <= ev_hi)].copy()
    bt_eval["partition"] = "backtest_eval"
    bt_eval = _frame(bt_eval)
    bt_types = rule_types_from_training(bt_fit)
    bt_pipe = logistic_pipeline(contract, c_best, seed).fit(base_matrix(bt_fit), bt_fit["isFraud"].to_numpy())
    bt_scores = {
        "seeded_random": ev.seeded_random_scores(bt_eval["event_id"], int(proto["seeds"]["random_daily_ranking"])),
        "amount_type_rule": amount_type_rule(bt_eval, bt_types),
        "logistic_regression": bt_pipe.predict_proba(base_matrix(bt_eval))[:, 1],
    }
    result["development_backtest"] = {
        "fit_steps": BACKTEST["fit"], "evaluate_steps": BACKTEST["evaluate"],
        "fit_positives": int(bt_fit["isFraud"].sum()), "evaluate_rows": len(bt_eval),
        "evaluate_positives": int(bt_eval["isFraud"].sum()), "rule_types": bt_types,
        "C": c_best, "methods": {k: evaluate_scores(bt_eval, s, detail=False) for k, s in bt_scores.items()}}
    timings["backtest"] = round(time.perf_counter() - t, 2)

    result["runtime"] = {"sections_seconds": timings, "total_seconds": round(time.perf_counter() - started, 2),
                         "peak_python_process_mib": peak_rss_mib()}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "validation_report.json").write_text(json.dumps(result, indent=2, default=_json), encoding="utf-8")
    return result


def _json(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)
