"""Day 3 selection (T09/T10) on validation, following config/selection_protocol.yaml.

Fits every protocol candidate on train, scores validation, applies the
pre-registered selection rule, and records ablations. The test partition is
not read here.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import config, data, evaluation as ev, splits
from .baselines import amount_type_rule, rule_types_from_training
from .contract import FeatureContract
from .dev_report import _frame, _json, evaluate_scores
from .features import feature_parquet
from .runtime import environment, peak_rss_mib

LOG_COLUMNS = {"log1p_amount": "amount", "dest_prior_count": "dest_prior_count",
               "dest_prior_amount_sum": "dest_prior_amount_sum", "dest_prior_count_24h": "dest_prior_count_24h",
               "dest_steps_since_last": "dest_steps_since_last"}


def selection_protocol() -> dict:
    return config.load_yaml("selection_protocol.yaml")


def load_with_history(name: str, allow_test: bool = False) -> pd.DataFrame:
    """Partition rows joined to the label-free history feature table by source_row."""
    data.check_access(name, allow_test)
    lo, hi = splits.partitions()[name]
    ev_path, f_path = config.paths().events_parquet, feature_parquet()
    with duckdb.connect() as con:
        con.execute("SET memory_limit='2GB'; SET threads=4")
        df = con.execute(f"""
            SELECT e.source_row, e.step, e.type, e.amount, e.isFraud, e.isFlaggedFraud,
                   f.dest_has_prior, f.dest_prior_count, f.dest_prior_amount_sum,
                   f.dest_prior_count_24h, f.dest_steps_since_last
            FROM read_parquet('{ev_path.as_posix()}') e
            JOIN read_parquet('{f_path.as_posix()}') f USING (source_row)
            WHERE e.step BETWEEN {lo} AND {hi} ORDER BY e.source_row""").df()
    df["type"] = df["type"].astype("category")
    df["partition"] = name
    df["day"] = splits.simulation_day(df["step"])
    return df


def design_matrix(df: pd.DataFrame, features: list[str], for_booster: bool, types: tuple[str, ...]) -> pd.DataFrame:
    """Transform contract features into model columns. Only declared inputs are read."""
    cols: dict[str, np.ndarray] = {}
    for f in features:
        if f == "type_onehot":
            t = df["type"].astype(str).to_numpy()
            unknown = set(np.unique(t)) - set(types)
            if unknown:
                raise ValueError(f"unknown transaction types {unknown}")
            for name in types:
                cols[f"type_onehot={name}"] = (t == name).astype(np.float64)
        elif f == "dest_has_prior":
            cols[f] = df[f].to_numpy(np.float64)
        elif f == "hour_of_day":
            if not for_booster:
                raise ValueError("hour_of_day ablation is defined for the booster only")
            cols[f] = ((df["step"].to_numpy() - 1) % 24).astype(np.float64)
        elif f in LOG_COLUMNS:
            v = np.log1p(df[LOG_COLUMNS[f]].to_numpy(np.float64))
            if f == "dest_steps_since_last" and not for_booster:
                v = np.nan_to_num(v, nan=0.0)
            cols[f] = v
        else:
            raise KeyError(f"no transform for {f}")
    return pd.DataFrame(cols, index=df.index)


def make_model(kind: str, params: dict, seed: int, columns: list[str]):
    if kind == "logistic_regression":
        scale = [c for c in columns if "=" not in c and c != "dest_has_prior"]
        pre = ColumnTransformer([("scale", StandardScaler(), scale)], remainder="passthrough")
        return Pipeline([("pre", pre), ("model", LogisticRegression(
            C=params["C"], class_weight="balanced", max_iter=3000, random_state=seed))])
    return HistGradientBoostingClassifier(
        learning_rate=params["learning_rate"], max_leaf_nodes=params["max_leaf_nodes"],
        max_iter=params["max_iter"], class_weight=params["class_weight"], early_stopping=False,
        random_state=seed)


def candidates(proto: dict) -> list[dict]:
    out = []
    for fs in proto["feature_sets"]:
        for c in proto["models"]["logistic_regression"]["C"]:
            out.append({"kind": "logistic_regression", "feature_set": fs, "params": {"C": c}})
    hgb = proto["models"]["hist_gradient_boosting"]
    for fs in hgb["feature_sets"]:
        for cfg in hgb["configs"]:
            out.append({"kind": "hist_gradient_boosting", "feature_set": fs, "params": dict(cfg)})
    return out


def fit_score(cand: dict, train: pd.DataFrame, valid: pd.DataFrame, feats: list[str], contract: FeatureContract,
              seed: int, allow_ablation: bool = False):
    contract.validate_feature_set(feats, allow_ablation=allow_ablation)
    booster = cand["kind"] == "hist_gradient_boosting"
    xt = design_matrix(train, feats, booster, contract.transaction_types)
    contract.check_frame_columns(xt.columns, allow_ablation=allow_ablation)
    xv = design_matrix(valid, feats, booster, contract.transaction_types)
    model = make_model(cand["kind"], cand["params"], seed, list(xt.columns))
    t = time.perf_counter()
    model.fit(xt, train["isFraud"].to_numpy())
    fit_s = time.perf_counter() - t
    return model, model.predict_proba(xv)[:, 1], list(xt.columns), round(fit_s, 2)


def choose(results: list[dict], rule_ap: float, proto: dict) -> dict:
    eligible = [r for r in results if r["eligible"]]
    best_ap = max(r["validation_ap"] for r in eligible)
    near = [r for r in eligible if r["validation_ap"] >= best_ap * 0.98]
    order = {"logistic_regression": 0, "hist_gradient_boosting": 1}
    near.sort(key=lambda r: (-r["validation_recall_k100"], order[r["kind"]], len(r["features"])))
    pick = near[0]
    if pick["validation_ap"] <= rule_ap:
        return {"champion": "amount_type_rule", "reason": "no learned model beat the rule's validation AP"}
    return {"champion": pick["id"], "reason": f"highest AP band (>= {best_ap * 0.98:.6f}); then K=100 recall, "
                                              "then simpler model", "near_band": [r["id"] for r in near]}


def run(out_dir: Path) -> dict:
    started = time.perf_counter()
    proto = selection_protocol()
    seed = int(config.split_protocol()["seeds"]["global"])
    contract = FeatureContract.load()
    train = load_with_history("train")
    valid = _frame(load_with_history("validation"))
    yv = valid["isFraud"].to_numpy()

    types = rule_types_from_training(train)
    rule_score = amount_type_rule(valid, types)
    rule_ap = ev.ranking_metrics(yv, rule_score)["average_precision"]

    results, models = [], {}
    for i, cand in enumerate(candidates(proto)):
        feats = proto["feature_sets"][cand["feature_set"]]
        model, score, cols, fit_s = fit_score(cand, train, valid, feats, contract, seed)
        m = evaluate_scores(valid, score, detail=False)
        cid = f"{cand['kind']}:{cand['feature_set']}:{json.dumps(cand['params'], sort_keys=True)}"
        results.append({"id": cid, "kind": cand["kind"], "feature_set": cand["feature_set"], "features": feats,
                        "params": cand["params"], "model_columns": cols, "fit_seconds": fit_s, "eligible": True,
                        "validation_ap": m["ranking"]["average_precision"], "validation_auc": m["ranking"]["roc_auc"],
                        "validation_recall_k100": m["capacity"]["100"]["all_segments"]["recall"],
                        "validation_precision_k100": m["capacity"]["100"]["all_segments"]["precision"],
                        "capacity": m["capacity"]})
        models[cid] = (model, score)
        print(f"  [{i + 1}] {cid}: AP={results[-1]['validation_ap']:.5f} "
              f"recall@100={results[-1]['validation_recall_k100']:.4f} fit={fit_s}s", flush=True)

    decision = choose(results, rule_ap, proto)
    champion = decision["champion"]

    # ablation: hour_of_day (never eligible)
    abl = []
    for name, feats in proto["ablation_only"].items():
        cand = {"kind": "hist_gradient_boosting", "params": dict(proto["models"]["hist_gradient_boosting"]["configs"][0])}
        _, score, cols, fit_s = fit_score(cand, train, valid, feats, contract, seed, allow_ablation=True)
        m = evaluate_scores(valid, score, detail=False)
        abl.append({"id": f"ablation:{name}", "features": feats, "eligible": False,
                    "validation_ap": m["ranking"]["average_precision"],
                    "validation_recall_k100": m["capacity"]["100"]["all_segments"]["recall"]})

    detail = None
    if champion in models:
        detail = evaluate_scores(valid, models[champion][1], detail=True)
    result = {"report": "day3-selection", "partition_evaluated": "validation", "test_partition_accessed": False,
              "selection_protocol": proto["selection_version"], "feature_contract": contract.version,
              "environment": environment(), "amount_type_rule_validation_ap": rule_ap,
              "amount_type_rule_types": types, "candidates": results, "ablations": abl,
              "decision": decision, "champion_validation_detail": detail}
    result["runtime"] = {"total_seconds": round(time.perf_counter() - started, 2),
                         "peak_python_process_mib": peak_rss_mib()}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "selection_report.json").write_text(json.dumps(result, indent=2, default=_json), encoding="utf-8")
    result["_models"] = models
    return result
