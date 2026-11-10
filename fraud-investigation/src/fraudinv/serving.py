"""Shared scoring core for the API and the replay command (T12/T14).

Features come only from the run's server-side recipient-history state in
PostgreSQL (strictly earlier steps). Callers supply transaction fields only;
labels, balances, history aggregates and evidence cutoffs are not inputs.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
import psycopg
import sklearn
from threadpoolctl import threadpool_limits

from . import config, data
from .contract import FeatureContract
from .history import FEATURES as HISTORY_FEATURES
from .model_select import design_matrix
from .source import sha256

WINDOW_STEPS = 24
SMALL_BATCH = 256


class ModelIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class FrozenModel:
    record: dict
    model: object
    contract: FeatureContract

    @property
    def version(self) -> str:
        return self.record["model_version"]

    @property
    def policy_version(self) -> str:
        return self.record["review_policy"]["version"]

    def matrix(self, frame: pd.DataFrame) -> pd.DataFrame:
        booster = self.record["kind"] == "hist_gradient_boosting"
        x = design_matrix(frame, self.record["features"], booster, self.contract.transaction_types)
        if list(x.columns) != self.record["model_columns"]:
            raise ModelIntegrityError(f"design columns {list(x.columns)} differ from frozen model")
        return x

    def score(self, frame: pd.DataFrame) -> np.ndarray:
        return self.predict(self.matrix(frame))

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        # Small batches (API requests) run single-threaded: concurrent requests each starting a full
        # OpenMP pool oversubscribe the CPU. Large batches (replay hours, offline) keep all threads.
        if len(x) < SMALL_BATCH:
            with threadpool_limits(limits=1, user_api="openmp"):
                return self.model.predict_proba(x)[:, 1]
        return self.model.predict_proba(x)[:, 1]


@lru_cache(maxsize=1)
def load_frozen() -> FrozenModel:
    record = json.loads(data.FROZEN_SELECTION.read_text(encoding="utf-8"))
    path = config.APP_ROOT / record["artifact"]["path"]
    if sha256(path) != record["artifact"]["sha256"]:
        raise ModelIntegrityError("model artifact hash does not match the frozen record")
    if sklearn.__version__ != record["artifact"]["sklearn"]:
        raise ModelIntegrityError(f"scikit-learn {sklearn.__version__} != frozen {record['artifact']['sklearn']}")
    contract = FeatureContract.load()
    contract.validate_feature_set(record["features"])
    return FrozenModel(record, joblib.load(path), contract)


def tie_key(event_id: str) -> str:
    return hashlib.sha256(event_id.encode()).hexdigest()[:16]


def to_cents(amounts) -> np.ndarray:
    return np.rint(np.asarray(amounts, dtype=np.float64) * 100).astype(np.int64)


def history_features(conn: psycopg.Connection, run_id: str, rows: pd.DataFrame, step: int) -> pd.DataFrame:
    """History features for rows of ``step`` from the run's committed state (steps < step)."""
    dests = sorted(set(rows["nameDest"]))
    found = conn.execute(
        """
        SELECT d.name_dest, h.prior_count, h.prior_cents, h.last_step,
               coalesce((SELECT sum(c.n) FROM app.recipient_step_count c
                         WHERE c.run_id = %(run)s AND c.name_dest = d.name_dest
                           AND c.step >= %(lo)s AND c.step < %(step)s), 0) AS c24
        FROM unnest(%(dests)s::text[]) AS d(name_dest)
        LEFT JOIN app.recipient_history h ON h.run_id = %(run)s AND h.name_dest = d.name_dest
        """, {"run": run_id, "dests": dests, "lo": step - WINDOW_STEPS, "step": step}).fetchall()
    state = {d: (n, c, last, c24) for d, n, c, last, c24 in found}
    out = []
    for dest in rows["nameDest"]:
        n, cents, last, c24 = state[dest]
        if not n:
            out.append((0, 0, 0.0, int(c24), np.nan))
        else:
            if last >= step:
                raise RuntimeError(f"history for {dest} includes step {last} >= scored step {step}")
            out.append((1, int(n), int(cents) / 100.0, int(c24), float(step - last)))
    return pd.DataFrame(out, columns=HISTORY_FEATURES, index=rows.index).astype(
        {"dest_has_prior": np.int8, "dest_prior_count": np.int64, "dest_prior_count_24h": np.int64})


def feature_payload(row: pd.Series, vector: np.ndarray, columns: list[str]) -> tuple[dict, str]:
    """Persisted score-time features: raw contract values plus the exact model input vector."""
    def clean(v):
        v = float(v)
        return None if math.isnan(v) else v
    payload = {"type": str(row["type"]), "amount": float(row["amount"]),
               **{f: clean(row[f]) for f in HISTORY_FEATURES},
               "model_input": dict(zip(columns, (clean(v) for v in vector)))}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload, hashlib.sha256(canonical.encode()).hexdigest()


def score_rows(conn: psycopg.Connection, frozen: FrozenModel, run_id: str, rows: pd.DataFrame,
               step: int) -> pd.DataFrame:
    """Score one complete step. ``rows`` needs step, type, amount, nameDest (no labels)."""
    forbidden = {"isFraud", "isFlaggedFraud", "oldbalanceOrg", "newbalanceOrig",
                 "oldbalanceDest", "newbalanceDest"} & set(rows.columns)
    if forbidden:
        raise ValueError(f"scoring input contains forbidden fields {sorted(forbidden)}")
    frame = rows.join(history_features(conn, run_id, rows, step))
    x = frozen.matrix(frame)
    frame["score"] = frozen.predict(x)
    payloads = [feature_payload(r, v, list(x.columns)) for (_, r), v in zip(frame.iterrows(), x.to_numpy())]
    frame["features"] = [p for p, _ in payloads]
    frame["feature_sha256"] = [h for _, h in payloads]
    return frame
