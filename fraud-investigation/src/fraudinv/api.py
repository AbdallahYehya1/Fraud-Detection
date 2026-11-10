"""Typed scoring and evidence API (T12/T14). Runs as the serving DB role, which cannot read truth.

Start: ``.venv\\Scripts\\python -m uvicorn fraudinv.api:app --host 127.0.0.1 --port 8000``
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated, Iterator, Literal

import pandas as pd
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import cases, config, db, splits
from .serving import load_frozen, score_rows

TxType = Literal["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]
AccountRef = Annotated[str, Field(pattern=r"^[CM][0-9]+$", max_length=20)]
UNIT = "simulation currency units"

app = FastAPI(title="Fraud investigation MVP", version="0.1.0",
              description="Synthetic PaySim v2 data. Scores are ranking scores, not probabilities.")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TransactionIn(Strict):
    """Allowed transaction fields only. Labels, balances, history aggregates and cutoffs are rejected."""
    step: Annotated[int, Field(ge=1, le=743)]
    type: TxType
    amount: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]
    name_orig: AccountRef
    name_dest: AccountRef


class ScoreRequest(Strict):
    run_id: Annotated[str, Field(min_length=1, max_length=100)]
    transaction: TransactionIn


class ScoreResponse(Strict):
    run_id: str
    model_version: str
    feature_contract: str
    policy_version: str
    scoring_step: int
    score: float
    score_semantics: str
    features: dict
    feature_sha256: str
    persisted: bool


def get_conn() -> Iterator[psycopg.Connection]:
    try:
        conn = db.connect("app", autocommit=True)
    except psycopg.OperationalError as exc:
        raise HTTPException(503, f"database unavailable: {exc.__class__.__name__}") from exc
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[psycopg.Connection, Depends(get_conn)]


def _run(conn, run_id: str) -> dict:
    cur = conn.execute("SELECT * FROM app.replay_run WHERE run_id = %s", (run_id,))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(404, f"unknown run {run_id}")
    return dict(zip([d.name for d in cur.description], row))


@app.get("/health")
def health(conn: Conn) -> dict:
    conn.execute("SELECT 1")
    frozen = load_frozen()
    return {"status": "ok", "database": "ok", "model_version": frozen.version}


@app.get("/model-info")
def model_info() -> dict:
    r = load_frozen().record
    return {k: r[k] for k in ("model_version", "kind", "params", "features", "model_columns", "feature_contract",
                              "history_feature_table", "split_protocol", "selection_protocol", "review_policy",
                              "score_semantics", "frozen_at_utc")} | {"artifact_sha256": r["artifact"]["sha256"]}


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest, conn: Conn) -> ScoreResponse:
    """Score one transaction against the run's committed state (preview; not persisted).

    History must end exactly at step - 1 so a whole hour is scored from previous-hour state;
    the replay command is the persistent path and uses the same scoring function.
    """
    run = _run(conn, req.run_id)
    t = req.transaction
    if run["committed_through_step"] != t.step - 1:
        raise HTTPException(409, f"run state is through step {run['committed_through_step']}; "
                                 f"only step {run['committed_through_step'] + 1} can be scored")
    frozen = load_frozen()
    if run["model_version"] != frozen.version:
        raise HTTPException(409, "run model version differs from the loaded model")
    rows = pd.DataFrame([{"step": t.step, "type": t.type, "amount": float(t.amount), "nameDest": t.name_dest}])
    scored = score_rows(conn, frozen, req.run_id, rows, t.step).iloc[0]
    return ScoreResponse(run_id=req.run_id, model_version=frozen.version,
                         feature_contract=frozen.record["feature_contract"], policy_version=frozen.policy_version,
                         scoring_step=t.step, score=float(scored["score"]),
                         score_semantics=frozen.record["score_semantics"], features=scored["features"],
                         feature_sha256=scored["feature_sha256"], persisted=False)


@app.get("/replays/{run_id}")
def replay_status(run_id: str, conn: Conn) -> dict:
    run = _run(conn, run_id)
    counts = conn.execute(
        "SELECT (SELECT count(*) FROM app.score WHERE run_id = %(r)s), "
        "(SELECT count(*) FROM app.alert WHERE run_id = %(r)s), "
        "(SELECT count(*) FROM app.day_finalization WHERE run_id = %(r)s)", {"r": run_id}).fetchone()
    return {**{k: run[k] for k in ("run_id", "model_version", "policy_version", "daily_capacity", "first_step",
                                   "last_step", "warmup_rule", "committed_through_step", "status", "error")},
            "scores": counts[0], "alerts": counts[1], "finalized_segments": counts[2]}


@app.get("/alerts")
def alerts(conn: Conn, run_id: str, day: int | None = None,
           limit: Annotated[int, Query(ge=1, le=500)] = 100) -> list[dict]:
    _run(conn, run_id)
    cur = conn.execute(
        "SELECT a.simulation_day, a.rank, a.capacity, a.event_id, t.step, t.type, t.amount::text, s.score, "
        "c.case_id, c.status FROM app.alert a JOIN app.score s USING (run_id, event_id) "
        "JOIN app.transaction_event t USING (event_id) JOIN app.review_case c USING (run_id, event_id) "
        "WHERE a.run_id = %s AND (%s::int IS NULL OR a.simulation_day = %s) "
        "ORDER BY a.simulation_day, a.rank LIMIT %s", (run_id, day, day, limit))
    cols = ["simulation_day", "rank", "capacity", "event_id", "step", "type", "amount", "score", "case_id", "status"]
    return [dict(zip(cols, r)) | {"unit": UNIT} for r in cur.fetchall()]


@app.exception_handler(cases.CaseError)
def _case_error(request: Request, exc: cases.CaseError) -> JSONResponse:
    return JSONResponse({"detail": exc.message, **exc.extra}, status_code=exc.status)


def current_analyst(conn: Conn, authorization: Annotated[str | None, Header()] = None) -> dict:
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
    return cases.authenticate(conn, token)


Analyst = Annotated[dict, Depends(current_analyst)]
Status = Literal["new", "in_review", "escalated", "closed"]


class TransitionIn(Strict):
    expected_version: Annotated[int, Field(ge=1)]
    status: Status
    disposition: Literal["needs_more_information", "suspicious_in_demo", "no_action"] | None = None
    note: Annotated[str, Field(min_length=1, max_length=4000)] | None = None


class NoteIn(Strict):
    body: Annotated[str, Field(min_length=1, max_length=4000)]


@app.get("/me")
def me(analyst: Analyst) -> dict:
    return analyst


@app.get("/overview")
def overview(conn: Conn) -> dict:
    frozen = load_frozen().record
    runs = conn.execute(
        "SELECT r.run_id, r.status, r.first_step, r.last_step, r.committed_through_step, r.daily_capacity, "
        "r.model_version, r.policy_version, r.updated_at, "
        "(SELECT count(*) FROM app.day_finalization f WHERE f.run_id = r.run_id), "
        "(SELECT json_object_agg(status, n) FROM (SELECT status, count(*) n FROM app.review_case c "
        " WHERE c.run_id = r.run_id GROUP BY status) x) FROM app.replay_run r ORDER BY r.created_at DESC").fetchall()
    keys = ["run_id", "status", "first_step", "last_step", "committed_through_step", "daily_capacity",
            "model_version", "policy_version", "updated_at", "finalized_segments", "cases_by_status"]
    src = config.data_source()
    return {"dataset": {"name": "PaySim v2 (synthetic)", "licence": src["licence"], "key": src["dataset_key"],
                        "csv_sha256": src["csv"]["sha256"], "unit": cases.UNIT, "time": "relative simulation hours"},
            "model": {k: frozen[k] for k in ("model_version", "kind", "features", "feature_contract",
                                             "split_protocol", "score_semantics")},
            "policy": frozen["review_policy"],
            "runs": [dict(zip(keys, r)) | {"cases_by_status": r[10] or {}} for r in runs]}


@app.get("/evaluation")
def evaluation(run_id: str | None = None) -> dict:
    """Offline, evaluator-produced aggregates only. Not available to investigation tools."""
    out: dict = {"scope": "Offline evaluation of synthetic data. Aggregates only; no per-case labels."}
    final = config.REPORTS_DIR / "day3" / "final_test_report.json"
    if final.exists():
        r = json.loads(final.read_text(encoding="utf-8"))
        out["frozen_test"] = {
            "population": r["population"], "constant_score_ap_reference": r["constant_score_ap_reference"],
            "methods": {m: {"average_precision": v["ranking"]["average_precision"],
                            "k100": v["capacity"]["100"]["all_segments"],
                            "k100_complete_days": v["capacity"]["100"]["complete_days_only"],
                            "mixed_hours": {kk: {x: d[x] for x in ("rows", "positives", "selected_true_positives")}
                                            for kk, d in v["mixed_hour_diagnostics_k100"].items()}}
                        for m, v in r["methods"].items()},
            "bootstrap": r["bootstrap"]["intervals"], "native_policy": r["native_policy"]}
    if run_id:
        from .evaluate_run import report_path

        p = report_path(run_id)
        out["run"] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    return out


@app.get("/cases")
def list_cases(conn: Conn, run_id: str, status: Status | None = None, day: int | None = None,
               limit: Annotated[int, Query(ge=1, le=500)] = 100,
               offset: Annotated[int, Query(ge=0)] = 0) -> dict:
    _run(conn, run_id)
    return cases.queue(conn, run_id, status, day, limit, offset)


@app.get("/cases/{case_id:path}/evidence")
def case_evidence(case_id: str, conn: Conn) -> dict:
    return cases.evidence(conn, case_id)


@app.post("/cases/{case_id:path}/transition")
def case_transition(case_id: str, body: TransitionIn, conn: Conn, analyst: Analyst) -> dict:
    return cases.transition(conn, case_id, analyst, body.expected_version, body.status, body.disposition, body.note)


@app.post("/cases/{case_id:path}/notes")
def case_note(case_id: str, body: NoteIn, conn: Conn, analyst: Analyst) -> dict:
    return cases.add_note(conn, case_id, analyst, body.body)


class AssistantIn(Strict):
    question: Annotated[str, Field(min_length=1, max_length=500)]


@app.post("/cases/{case_id:path}/assistant")
def case_assistant(case_id: str, body: AssistantIn, conn: Conn, analyst: Analyst) -> dict:
    """Run the bounded local assistant (read-only; local inference only). Requires an analyst."""
    from . import assistant

    cases.case_row(conn, case_id)  # 404 for unknown cases before any inference
    res = assistant.investigate(case_id, body.question)
    return {k: res.get(k) for k in ("case_id", "question", "mode", "answer", "tool_calls", "seconds", "model",
                                    "config_sha256", "error")} | {
        "refs": {r: v.get("kind") for r, v in (res.get("refs") or {}).items()},
        "tool_trace": [{k: t[k] for k in ("tool", "ok", "error", "ms")} for t in res.get("tool_trace") or []],
        "guard": {k: (res.get("guard") or {}).get(k) for k in ("removed", "valid_refs_cited")},
        "label": ("Local AI assistant (" + assistant.MODEL + "), checked by a deterministic guard"
                  if res.get("mode") == "assistant" else "Template report - not AI output")}


@app.get("/transactions/{event_id}")
def transaction(event_id: str, conn: Conn) -> dict:
    row = conn.execute("SELECT event_id, source_row, step, type, amount::text, name_orig, name_dest "
                       "FROM app.transaction_event WHERE event_id = %s", (event_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"unknown transaction {event_id}")
    keys = ["event_id", "source_row", "step", "type", "amount", "name_orig", "name_dest"]
    out = dict(zip(keys, row))
    out.update({"unit": UNIT, "simulation_day": int(splits.simulation_day([out["step"]])[0]),
                "id_note": "project event ID derived from dataset hash and source row; not a bank transaction ID"})
    return out


# Built analyst UI (web/dist), served from the same local process when present.
_DIST = config.APP_ROOT / "web" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="ui")
