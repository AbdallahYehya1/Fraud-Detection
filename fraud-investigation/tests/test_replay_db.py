"""Replay, recovery and serving-consistency tests against the local PostgreSQL test database.

Uses a synthetic fixture (not PaySim rows) written as Parquet in the same schema, and the
frozen champion model. Skipped if the database or the frozen model is unavailable.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import psycopg
import pytest

from fraudinv import data, db, replay
from fraudinv.history import FEATURES, recipient_history

pytestmark = pytest.mark.db
TEST_DB = "fraudinv_test_unit"
PREFIX = "FIX-00000000"
ROW_OFFSET = 9_000_000


def fixture_frame() -> pd.DataFrame:
    """Steps 1-30; recurring recipients so history, 24-step window and novelty all vary."""
    rng = np.random.default_rng(20261109)
    rows = []
    types = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]
    for step in range(1, 31):
        for _ in range(int(rng.integers(8, 20))):
            t = types[int(rng.integers(0, 5))]
            dest = f"M{int(rng.integers(1, 40))}" if t == "PAYMENT" else f"C{int(rng.integers(1, 25))}"
            if rng.random() < 0.15:
                dest = f"C{int(rng.integers(1000, 100000))}"  # mostly-new recipients
            rows.append({"step": step, "type": t, "amount": round(float(rng.uniform(1, 2e6)), 2),
                         "nameOrig": f"C{int(rng.integers(1, 10**9))}", "nameDest": dest})
    df = pd.DataFrame(rows)
    df.insert(0, "source_row", np.arange(ROW_OFFSET, ROW_OFFSET + len(df), dtype=np.int64))
    return df


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    if not data.FROZEN_SELECTION.exists():
        pytest.skip("no frozen model")
    try:
        db.drop_database(TEST_DB)
        db.create_database(TEST_DB)
        db.migrate(TEST_DB)
    except (psycopg.OperationalError, KeyError) as exc:
        pytest.skip(f"database unavailable: {exc}")
    frame = fixture_frame()
    path = tmp_path_factory.mktemp("fx") / "events.parquet"
    frame.to_parquet(path, index=False)
    source = replay.Source(path, PREFIX)
    old = os.environ.get("FRAUDINV_DB_NAME")
    os.environ["FRAUDINV_DB_NAME"] = TEST_DB
    yield {"source": source, "frame": frame}
    if old is None:
        os.environ.pop("FRAUDINV_DB_NAME", None)
    else:
        os.environ["FRAUDINV_DB_NAME"] = old


@pytest.fixture
def conn(env):
    with db.connect("app", TEST_DB, autocommit=True) as c:
        yield c


def snapshot(conn, run_id):
    scores = conn.execute("SELECT event_id, score, feature_sha256, scoring_step FROM app.score WHERE run_id = %s "
                          "ORDER BY event_id", (run_id,)).fetchall()
    alerts = conn.execute("SELECT partition_name, simulation_day, rank, event_id, capacity FROM app.alert "
                          "WHERE run_id = %s ORDER BY 1, 2, 3", (run_id,)).fetchall()
    cases = conn.execute("SELECT replace(case_id, run_id, ''), event_id, scoring_step, case_evidence_cutoff_step "
                         "FROM app.review_case WHERE run_id = %s ORDER BY 1", (run_id,)).fetchall()
    return scores, alerts, cases


def test_interrupted_replay_matches_uninterrupted(env, conn):
    src = env["source"]
    replay.create_run(conn, "A", 20, 30, capacity=6, source=src)
    done = replay.run_replay(conn, "A", source=src)
    assert done["status"] == "completed" and done["segments_finalized"] == [("train", 0), ("train", 1)]

    replay.create_run(conn, "B", 20, 30, capacity=6, source=src)
    with pytest.raises(replay.SimulatedCrash):
        replay.run_replay(conn, "B", source=src, fail_at=(23, 5))
    run = replay.get_run(conn, "B")
    assert run["status"] == "failed" and run["committed_through_step"] == 22
    # the partial hour was rolled back completely
    assert conn.execute("SELECT count(*) FROM app.score WHERE run_id = 'B' AND scoring_step = 23").fetchone()[0] == 0
    resumed = replay.run_replay(conn, "B", source=src)
    assert resumed["status"] == "completed"

    a, b = snapshot(conn, "A"), snapshot(conn, "B")
    assert a[0] == b[0]                      # identical scores and feature hashes
    assert a[1] == b[1] and len(a[1]) > 0    # identical day-end queues
    assert a[2] == b[2]                      # identical unique cases
    n_events = len(env["frame"].query("20 <= step <= 30"))
    assert len(b[0]) == n_events             # no duplicate scores


def test_finalization_and_rerun_are_idempotent(env, conn):
    src = env["source"]
    before = snapshot(conn, "A")
    audits = conn.execute("SELECT count(*) FROM app.audit_event WHERE run_id = 'A'").fetchone()[0]
    run = replay.get_run(conn, "A")
    assert replay.finalize_segment(conn, run, "train", 0) is False
    again = replay.run_replay(conn, "A", source=src)
    assert again["rows_scored"] == 0 and again["segments_finalized"] == []
    assert snapshot(conn, "A") == before
    assert conn.execute("SELECT count(*) FROM app.audit_event WHERE run_id = 'A'").fetchone()[0] == audits


def test_crash_between_hour_commit_and_finalization_recovers(env, conn, monkeypatch):
    src = env["source"]
    replay.create_run(conn, "C", 20, 30, capacity=6, source=src)
    real = replay.finalize_segment
    calls = {"n": 0}

    def flaky(c, run, part, day):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("crash before day-end finalization")
        return real(c, run, part, day)

    monkeypatch.setattr(replay, "finalize_segment", flaky)
    with pytest.raises(RuntimeError):
        replay.run_replay(conn, "C", source=src)
    assert replay.get_run(conn, "C")["committed_through_step"] == 24
    assert conn.execute("SELECT count(*) FROM app.day_finalization WHERE run_id = 'C'").fetchone()[0] == 0
    monkeypatch.setattr(replay, "finalize_segment", real)
    out = replay.run_replay(conn, "C", source=src)
    assert out["segments_finalized"][0] == ("train", 0)
    assert snapshot(conn, "C") == snapshot(conn, "A")


def test_replay_features_and_scores_match_offline(env, conn):
    from fraudinv.serving import load_frozen

    frame = env["frame"]
    offline = frame.join(recipient_history(frame))
    window = offline[(offline["step"] >= 20) & (offline["step"] <= 30)].copy()
    window["offline_score"] = load_frozen().score(window)
    rows = conn.execute("SELECT t.source_row, s.score, s.features FROM app.score s JOIN app.transaction_event t "
                        "USING (event_id) WHERE s.run_id = 'A'").fetchall()
    online = pd.DataFrame(rows, columns=["source_row", "score", "features"])
    m = window.merge(online, on="source_row")
    assert len(m) == len(window)
    assert (m["score"] == m["offline_score"]).all()
    for f in FEATURES:
        got = np.array([np.nan if x[f] is None else x[f] for x in m["features"]], dtype=float)
        exp = m[f].astype(float).to_numpy()
        assert ((got == exp) | (np.isnan(got) & np.isnan(exp))).all(), f


def test_api_score_matches_replay_and_enforces_state(env, conn):
    from fastapi.testclient import TestClient

    from fraudinv import api

    src = env["source"]
    replay.create_run(conn, "D", 20, 30, capacity=6, source=src)
    replay.run_replay(conn, "D", source=src, max_steps=3)          # paused through step 22
    assert replay.get_run(conn, "D")["committed_through_step"] == 22
    client = TestClient(api.app)
    ev = env["frame"].query("step == 23").iloc[0]
    body = {"run_id": "D", "transaction": {"step": 23, "type": ev["type"], "amount": f"{ev['amount']:.2f}",
                                           "name_orig": ev["nameOrig"], "name_dest": ev["nameDest"]}}
    r = client.post("/score", json=body)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["persisted"] is False and "isFraud" not in r.text
    # wrong step: state is not at step - 1
    late = body | {"transaction": body["transaction"] | {"step": 25}}
    assert client.post("/score", json=late).status_code == 409
    assert client.post("/score", json=body | {"run_id": "nope"}).status_code == 404
    replay.run_replay(conn, "D", source=src)
    eid = f"{PREFIX}-{int(ev['source_row']):07d}"
    persisted = conn.execute("SELECT score, feature_sha256 FROM app.score WHERE run_id = 'D' AND event_id = %s",
                             (eid,)).fetchone()
    assert persisted == (got["score"], got["feature_sha256"])
    tx = client.get(f"/transactions/{eid}").json()
    assert set(tx) == {"event_id", "source_row", "step", "type", "amount", "name_orig", "name_dest", "unit",
                       "simulation_day", "id_note"}
    assert client.get("/alerts", params={"run_id": "D"}).status_code == 200


def test_serving_role_cannot_read_truth_or_rewrite_audit(env, conn):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("SELECT count(*) FROM truth.label")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("DELETE FROM app.audit_event")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("UPDATE app.score SET score = 1")
    with db.connect("eval", TEST_DB) as ev:
        ev.execute("SELECT count(*) FROM truth.label")


def test_replay_refuses_non_autocommit_and_label_columns(env):
    with db.connect("app", TEST_DB) as c, pytest.raises(ValueError, match="autocommit"):
        replay.run_replay(c, "A", source=env["source"])
    from fraudinv.serving import load_frozen, score_rows

    with db.connect("app", TEST_DB, autocommit=True) as c, pytest.raises(ValueError, match="forbidden"):
        score_rows(c, load_frozen(), "A", pd.DataFrame({"step": [21], "type": ["TRANSFER"], "amount": [1.0],
                                                        "nameDest": ["C1"], "isFraud": [1]}), 21)


def test_analyst_workflow_end_to_end(env, conn):
    """replay -> score -> alert -> case evidence -> human disposition -> audit (T15/T16)."""
    import json
    import threading

    from fastapi.testclient import TestClient

    from fraudinv import api, cases

    with db.connect("admin", TEST_DB, autocommit=True) as admin:
        token = cases.add_analyst(admin, "tester", "Test Analyst")
        other = cases.add_analyst(admin, "tester2", "Second Analyst")
    client = TestClient(api.app)
    auth = {"Authorization": f"Bearer {token}"}

    q = client.get("/cases", params={"run_id": "A"}).json()
    # capacity 6 pro-rated over 5 and 6 observed hours -> 1 + 2 cases
    expected = conn.execute("SELECT sum(alerts) FROM app.day_finalization WHERE run_id = 'A'").fetchone()[0]
    assert q["total"] == expected == 3
    assert [(i["simulation_day"], i["rank"]) for i in q["items"]] == [(0, 1), (1, 1), (1, 2)]
    novel = next((i for i in q["items"] if i["dest_has_prior"] == 0), None)
    case_id = (novel or q["items"][0])["case_id"]
    ev = client.get(f"/cases/{case_id}/evidence").json()
    text = json.dumps(ev).lower()
    assert not any(k in text for k in ("isfraud", "is_fraud", "isflagged", "oldbalance", "newbalance"))
    c = ev["case"]
    assert c["case_evidence_cutoff_step"] >= c["scoring_step"]
    assert ev["recipient_history"]["score_time"]["steps"][1] == c["scoring_step"] - 1
    assert ev["recipient_history"]["review_time"]["steps"] == [c["scoring_step"], c["case_evidence_cutoff_step"]]
    assert all(r["step"] < c["scoring_step"] for r in ev["recipient_history"]["score_time"]["records"])
    assert ev["recipient_history"]["score_time"]["matches_score_time_count"]
    if novel:
        assert any("No earlier records for recipient" in m for m in ev["missing_information"])

    url = f"/cases/{case_id}"
    # authentication
    assert client.post(f"{url}/transition", json={"expected_version": 1, "status": "in_review"}).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert client.post(f"{url}/transition", json={"expected_version": 1, "status": "in_review"},
                       headers=bad).status_code == 401
    # start review, then a stale write is rejected with the current version
    r = client.post(f"{url}/transition", json={"expected_version": 1, "status": "in_review"}, headers=auth)
    assert r.status_code == 200 and r.json()["version"] == 2
    stale = client.post(f"{url}/transition", json={"expected_version": 1, "status": "escalated"}, headers=auth)
    assert stale.status_code == 409 and stale.json()["current_version"] == 2
    # rules: closing needs a disposition; disposition only when closing; label fields are not accepted
    assert client.post(f"{url}/transition", json={"expected_version": 2, "status": "closed"},
                       headers=auth).status_code == 422
    assert client.post(f"{url}/transition", json={"expected_version": 2, "status": "escalated",
                                                  "disposition": "no_action"}, headers=auth).status_code == 422
    assert client.post(f"{url}/transition", json={"expected_version": 2, "status": "escalated", "isFraud": 1},
                       headers=auth).status_code == 422

    # concurrent writers with the same expected version: exactly one wins
    results = []

    def attempt(tok):
        results.append(TestClient(api.app).post(f"{url}/transition", json={"expected_version": 2, "status": "escalated"},
                                                headers={"Authorization": f"Bearer {tok}"}).status_code)
    threads = [threading.Thread(target=attempt, args=(t,)) for t in (token, other)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [200, 409]

    note = "<script>alert(1)</script> check recipient"
    r = client.post(f"{url}/transition", json={"expected_version": 3, "status": "closed",
                                               "disposition": "suspicious_in_demo", "note": note}, headers=auth)
    assert r.status_code == 200 and r.json()["version"] == 4
    assert client.post(f"{url}/transition", json={"expected_version": 4, "status": "in_review"},
                       headers=auth).status_code == 409  # closed is terminal in the MVP
    assert client.post(f"{url}/notes", json={"body": "follow-up"}, headers=auth).status_code == 200

    final = client.get(f"{url}/evidence").json()
    assert final["case"]["status"] == "closed" and final["case"]["disposition"] == "suspicious_in_demo"
    assert [n["body"] for n in final["notes"]] == [note, "follow-up"]       # stored verbatim; UI escapes
    actions = [(a["action"], (a["new_state"] or {}).get("status")) for a in final["audit"]]
    assert actions == [("case_transition", "in_review"), ("case_transition", "escalated"),
                       ("case_transition", "closed"), ("note_added", None)]
    assert final["audit"][0]["actor"] == "tester" and final["audit"][0]["prior_state"]["version"] == 1
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("DELETE FROM app.audit_event WHERE case_id = %s", (case_id,))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("UPDATE app.case_note SET body = 'x'")
