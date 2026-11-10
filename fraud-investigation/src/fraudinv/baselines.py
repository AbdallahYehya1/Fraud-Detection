"""Day 2 baselines (T07). Every model input passes the feature contract."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from .contract import FeatureContract

BASE_FEATURES = ["type_onehot", "log1p_amount"]


def rule_types_from_training(train: pd.DataFrame) -> list[str]:
    """Transaction types with at least one training positive (training labels only)."""
    pos = train.loc[train["isFraud"] == 1, "type"].astype(str)
    return sorted(pos.unique())


def amount_type_rule(df: pd.DataFrame, types: list[str]) -> np.ndarray:
    """Authored rule as a ranking: larger amounts first within the rule types; others last."""
    in_types = df["type"].astype(str).isin(types).to_numpy()
    return np.where(in_types, np.log1p(df["amount"].to_numpy()), -1.0)


def base_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Raw inputs for the base feature set: only ``type`` and ``amount`` leave this function."""
    return pd.DataFrame({"type": df["type"].astype(str).to_numpy(),
                         "amount": df["amount"].to_numpy(np.float64)}, index=df.index)


def logistic_pipeline(contract: FeatureContract, c: float, seed: int) -> Pipeline:
    contract.validate_feature_set(BASE_FEATURES)
    pre = ColumnTransformer([
        ("type_onehot", OneHotEncoder(categories=[list(contract.transaction_types)],
                                      handle_unknown="error", sparse_output=False), ["type"]),
        ("log1p_amount", Pipeline([("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                                   ("scale", StandardScaler())]), ["amount"]),
    ], verbose_feature_names_out=True)
    return Pipeline([("features", pre),
                     ("model", LogisticRegression(C=c, class_weight="balanced", max_iter=2000,
                                                  solver="lbfgs", random_state=seed))])


def model_columns(pipe: Pipeline) -> list[str]:
    """Feature names in contract notation, e.g. ``type_onehot=TRANSFER``."""
    names = []
    for n in pipe.named_steps["features"].get_feature_names_out():
        block, raw = n.split("__", 1)
        names.append(f"{block}={raw.split('_', 1)[1]}" if block == "type_onehot" else block)
    return names
