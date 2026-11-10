"""Freeze the champion (T11) and run the one-time final test evaluation.

``freeze`` refits the selected candidate on train, checks it reproduces the
recorded validation AP, saves the artifact with its hash, and writes
``reports/frozen/selection.json``. ``final_test`` refuses to run before that
record exists and refuses a second run unless a rerun reason is recorded.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn

from . import config, data, evaluation as ev
from .baselines import amount_type_rule, base_matrix, logistic_pipeline, rule_types_from_training
from .contract import FeatureContract
from .dev_report import _frame, _json, evaluate_scores
from .features import FEATURE_VERSION
from .model_select import design_matrix, fit_score, load_with_history, selection_protocol
from .runtime import environment, peak_rss_mib
from .source import sha256

MODEL_DIR = config.APP_ROOT / "models"
SELECTION_REPORT = config.REPORTS_DIR / "day3" / "selection_report.json"
FINAL_REPORT = config.REPORTS_DIR / "day3" / "final_test_report.json"
BOOTSTRAP = {"resamples": 200, "seed": 20261109}


def _champion(report: dict) -> dict:
    cid = report["decision"]["champion"]
    return next(c for c in report["candidates"] if c["id"] == cid)


def freeze() -> dict:
    report = json.loads(SELECTION_REPORT.read_text(encoding="utf-8"))
    champ = _champion(report)
    seed = int(config.split_protocol()["seeds"]["global"])
    contract = FeatureContract.load()
    train = load_with_history("train")
    valid = _frame(load_with_history("validation"))
    model, score, cols, fit_s = fit_score({"kind": champ["kind"], "params": champ["params"]},
                                          train, valid, champ["features"], contract, seed)
    ap = ev.ranking_metrics(valid["isFraud"].to_numpy(), score)["average_precision"]
    if abs(ap - champ["validation_ap"]) > 1e-12:
        raise RuntimeError(f"refit AP {ap} differs from recorded {champ['validation_ap']}")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    path = MODEL_DIR / "champion-v1.joblib"
    joblib.dump(model, path)
    record = {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_version": "champion-v1",
        "candidate_id": champ["id"], "kind": champ["kind"], "params": champ["params"],
        "features": champ["features"], "model_columns": cols,
        "feature_contract": contract.version, "history_feature_table": FEATURE_VERSION,
        "split_protocol": config.split_protocol()["protocol_version"],
        "selection_protocol": selection_protocol()["selection_version"],
        "review_policy": {"version": "policy-v1", "rule": "daily top-K per (partition, simulation_day) segment",
                          "k": 100, "partial_segments": "pro-rated", "tie_break": "sha256(event_id) ascending",
                          "reported_capacities": [50, 100, 200]},
        "score_semantics": "ranking score (class-weighted booster); not a calibrated probability",
        "seed": seed, "csv_sha256": config.data_source()["csv"]["sha256"],
        "artifact": {"path": path.relative_to(config.APP_ROOT).as_posix(), "sha256": sha256(path),
                     "bytes": path.stat().st_size, "sklearn": sklearn.__version__,
                     "numpy": np.__version__, "joblib": joblib.__version__},
        "validation_ap_reproduced": ap, "refit_seconds": fit_s,
        "test_partition_accessed_before_freeze": False,
    }
    data.FROZEN_SELECTION.parent.mkdir(parents=True, exist_ok=True)
    data.FROZEN_SELECTION.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def _bootstrap(frame, y, scores: dict[str, np.ndarray], selected: dict[str, np.ndarray]) -> dict:
    rng = np.random.default_rng(BOOTSTRAP["seed"])
    groups = [frame.index.get_indexer(ix) for ix in
              frame.groupby(["partition", "day"], observed=True).groups.values()]
    draws = {m: {"average_precision": [], "recall_k100": [], "precision_k100": []} for m in scores}
    for _ in range(BOOTSTRAP["resamples"]):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        yy = y[idx]
        for m, s in scores.items():
            cap = ev.capacity_metrics(yy, selected[m][idx])
            draws[m]["average_precision"].append(ev.ranking_metrics(yy, s[idx])["average_precision"])
            draws[m]["recall_k100"].append(cap["recall"])
            draws[m]["precision_k100"].append(cap["precision"])
    out = {}
    for m, d in draws.items():
        out[m] = {k: {"p2.5": float(np.nanpercentile(np.array(v, dtype=float), 2.5)),
                      "p97.5": float(np.nanpercentile(np.array(v, dtype=float), 97.5))} for k, v in d.items()}
    return {"method": "day-segment block bootstrap", **BOOTSTRAP, "segments": len(groups), "intervals": out}


def final_test(rerun_reason: str | None = None) -> dict:
    if FINAL_REPORT.exists() and not rerun_reason:
        raise RuntimeError(f"{FINAL_REPORT} exists; the final test runs once (pass a recorded rerun reason)")
    record = json.loads(data.FROZEN_SELECTION.read_text(encoding="utf-8"))
    path = config.APP_ROOT / record["artifact"]["path"]
    if sha256(path) != record["artifact"]["sha256"]:
        raise RuntimeError("frozen model artifact hash mismatch")
    if sklearn.__version__ != record["artifact"]["sklearn"]:
        raise RuntimeError("scikit-learn version differs from the frozen artifact")
    started = time.perf_counter()
    contract = FeatureContract.load()
    seed = record["seed"]
    model = joblib.load(path)
    train = load_with_history("train")
    test = _frame(load_with_history("test", allow_test=True))
    y = test["isFraud"].to_numpy()

    booster = record["kind"] == "hist_gradient_boosting"
    x = design_matrix(test, record["features"], booster, contract.transaction_types)
    if list(x.columns) != record["model_columns"]:
        raise RuntimeError("test design matrix columns differ from the frozen model")
    scores = {"champion": model.predict_proba(x)[:, 1]}
    types = rule_types_from_training(train)
    scores["amount_type_rule"] = amount_type_rule(test, types)
    lr = logistic_pipeline(contract, 0.01, seed).fit(base_matrix(train), train["isFraud"].to_numpy())
    scores["logistic_regression_base"] = lr.predict_proba(base_matrix(test))[:, 1]
    scores["seeded_random"] = ev.seeded_random_scores(test["event_id"],
                                                      int(config.split_protocol()["seeds"]["random_daily_ranking"]))
    del train

    methods = {name: evaluate_scores(test, s, detail=True) for name, s in scores.items()}
    selected = {name: ev.select_daily_topk(test, s, 100)["selected"].to_numpy() for name, s in scores.items()}
    result = {
        "report": "day3-final-test", "frozen_selection": record, "rerun_reason": rerun_reason,
        "population": {"partition": "test", "rows": len(test), "positives": int(y.sum()),
                       "prevalence": float(y.mean())},
        "environment": environment(), "rule_types_from_training": types,
        "methods": methods,
        "native_policy": ev.native_policy_report(y, test["isFlaggedFraud"].to_numpy()),
        "constant_score_ap_reference": float(y.mean()),
        "bootstrap": _bootstrap(test, y, scores, selected),
    }
    result["runtime"] = {"total_seconds": round(time.perf_counter() - started, 2),
                         "peak_python_process_mib": peak_rss_mib()}
    FINAL_REPORT.write_text(json.dumps(result, indent=2, default=_json), encoding="utf-8")
    return result
