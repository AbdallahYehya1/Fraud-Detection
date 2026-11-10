"""Analyst cases: evidence assembly, authentication and dispositions (T15/T16).

Evidence keeps three kinds of information apart:
* score-time facts - the frozen feature values stored with the score (history with step < scoring_step);
* eligible earlier records - itemized rows with step < scoring_step;
* review-time records - rows after scoring up to case_evidence_cutoff_step (never used by the score).
Only allowlisted transaction fields leave this module; labels and balances are not stored in app.*.
"""
from __future__ import annotations

import hashlib
import json
import secrets

import psycopg

from . import splits

UNIT = "simulation currency units"
TRANSITIONS = {"new": {"in_review"}, "in_review": {"escalated", "closed", "new"},
               "escalated": {"in_review", "closed"}, "closed": set()}
DISPOSITIONS = ("needs_more_information", "suspicious_in_demo", "no_action")
RECORD_LIMIT = 50


class CaseError(Exception):
    def __init__(self, status: int, message: str, **extra):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def add_analyst(admin: psycopg.Connection, analyst_id: str, display_name: str) -> str:
    """Create an analyst (admin role) and return a new bearer token; only its hash is stored."""
    token = secrets.token_urlsafe(32)
    admin.execute("INSERT INTO app.analyst (analyst_id, display_name, token_sha256) VALUES (%s, %s, %s) "
                  "ON CONFLICT (analyst_id) DO UPDATE SET token_sha256 = excluded.token_sha256, active = true",
                  (analyst_id, display_name, token_hash(token)))
    return token


def authenticate(conn: psycopg.Connection, token: str | None) -> dict:
    if not token:
        raise CaseError(401, "missing bearer token")
    row = conn.execute("SELECT analyst_id, display_name FROM app.analyst WHERE token_sha256 = %s AND active",
                       (token_hash(token),)).fetchone()
    if row is None:
        raise CaseError(401, "unknown or inactive analyst token")
    return {"analyst_id": row[0], "display_name": row[1]}


def _records(conn, column: str, account: str, lo: int, hi: int, exclude: str) -> dict:
    """Same-role records for ``account`` with lo <= step <= hi, newest first (itemized, capped)."""
    assert column in ("name_dest", "name_orig")
    total, amount_sum = conn.execute(
        f"SELECT count(*), coalesce(sum(amount), 0)::text FROM app.transaction_event "
        f"WHERE {column} = %s AND step BETWEEN %s AND %s AND event_id <> %s",
        (account, lo, hi, exclude)).fetchone()
    rows = conn.execute(
        f"SELECT event_id, step, type, amount::text, name_orig, name_dest FROM app.transaction_event "
        f"WHERE {column} = %s AND step BETWEEN %s AND %s AND event_id <> %s "
        f"ORDER BY step DESC, source_row DESC LIMIT %s", (account, lo, hi, exclude, RECORD_LIMIT)).fetchall()
    keys = ["event_id", "step", "type", "amount", "name_orig", "name_dest"]
    return {"count": int(total), "amount_sum": amount_sum, "shown": len(rows), "steps": [lo, hi],
            "records": [dict(zip(keys, r)) for r in rows]}


def case_row(conn, case_id: str) -> dict:
    cur = conn.execute(
        "SELECT c.case_id, c.run_id, c.event_id, c.status, c.disposition, c.version, c.scoring_step, "
        "c.case_evidence_cutoff_step, c.assigned_to, c.created_at, c.updated_at, a.rank, a.capacity, "
        "a.simulation_day, a.partition_name, a.policy_version, s.score, s.model_version, s.feature_contract, "
        "s.features, s.feature_sha256 FROM app.review_case c JOIN app.alert a USING (run_id, event_id) "
        "JOIN app.score s USING (run_id, event_id) WHERE c.case_id = %s", (case_id,))
    row = cur.fetchone()
    if row is None:
        raise CaseError(404, f"unknown case {case_id}")
    return dict(zip([d.name for d in cur.description], row))


def evidence(conn: psycopg.Connection, case_id: str) -> dict:
    c = case_row(conn, case_id)
    t = conn.execute("SELECT event_id, source_row, step, type, amount::text, name_orig, name_dest "
                     "FROM app.transaction_event WHERE event_id = %s", (c["event_id"],)).fetchone()
    tx = dict(zip(["event_id", "source_row", "step", "type", "amount", "name_orig", "name_dest"], t))
    s, cutoff = c["scoring_step"], c["case_evidence_cutoff_step"]
    f = c["features"]
    rec_prior = _records(conn, "name_dest", tx["name_dest"], 1, s - 1, tx["event_id"])
    rec_review = _records(conn, "name_dest", tx["name_dest"], s, cutoff, tx["event_id"])
    snd_prior = _records(conn, "name_orig", tx["name_orig"], 1, s - 1, tx["event_id"])
    snd_review = _records(conn, "name_orig", tx["name_orig"], s, cutoff, tx["event_id"])
    rec_prior["matches_score_time_count"] = rec_prior["count"] == f["dest_prior_count"]

    missing = []
    if not f["dest_has_prior"]:
        missing.append(f"No earlier records for recipient {tx['name_dest']} before step {s} in this dataset.")
    if snd_prior["count"] == 0:
        missing.append(f"No earlier records for sender {tx['name_orig']} before step {s} in this dataset.")
    if not rec_prior["matches_score_time_count"]:
        missing.append("Itemized earlier recipient records are incomplete in this demo database; "
                       "the score-time count is authoritative.")
    missing.append("Device, location, identity and customer data are not part of this dataset.")
    missing.append("Balance fields are excluded (publisher warning: affected by cancelled fraud).")

    facts = [
        {"id": "F1", "fact": f"{tx['type']} of {tx['amount']} {UNIT} at simulation step {tx['step']} "
                             f"(day {int(splits.simulation_day([tx['step']])[0])}).", "source": tx["event_id"]},
        {"id": "F2", "fact": f"Recipient had {int(f['dest_prior_count'])} earlier recipient-role record(s) totalling "
                             f"{f['dest_prior_amount_sum']:.2f} {UNIT} before step {s}.", "source": "score-time features"},
        {"id": "F3", "fact": f"Recipient had {int(f['dest_prior_count_24h'])} recipient-role record(s) in steps "
                             f"{s - 24}-{s - 1}.", "source": "score-time features"},
        {"id": "F4", "fact": ("Recipient's latest earlier record was "
                              f"{int(f['dest_steps_since_last'])} step(s) before scoring."
                              if f["dest_steps_since_last"] is not None else
                              "Recipient has no earlier record, so steps-since-last is missing."),
         "source": "score-time features"},
        {"id": "F5", "fact": f"Sender had {snd_prior['count']} earlier sender-role record(s) before step {s}.",
         "source": "transaction_event (same role)"},
        {"id": "F6", "fact": f"Ranked {c['rank']} of capacity {c['capacity']} in {c['partition_name']} day "
                             f"{c['simulation_day']} (policy {c['policy_version']}).", "source": "alert"},
    ]
    return {
        "case": {k: c[k] for k in ("case_id", "run_id", "status", "disposition", "version", "assigned_to",
                                   "scoring_step", "case_evidence_cutoff_step", "created_at", "updated_at")},
        "transaction": tx | {"unit": UNIT},
        "model_evidence": {
            "score": c["score"], "rank": c["rank"], "capacity": c["capacity"],
            "simulation_day": c["simulation_day"], "partition": c["partition_name"],
            "model_version": c["model_version"], "feature_contract": c["feature_contract"],
            "policy_version": c["policy_version"], "feature_sha256": c["feature_sha256"],
            "score_time_features": {k: v for k, v in f.items() if k != "model_input"},
            "model_input": f["model_input"],
            "semantics": "Ranking score, not a probability. Feature values describe model inputs (associations); "
                         "they do not establish intent or confirm fraud. Per-case contributions are not computed "
                         "for this model.",
        },
        "computed_facts": facts,
        "recipient_history": {"score_time": rec_prior, "review_time": rec_review,
                              "note": "Same-role recurrence only; it does not establish a money-flow chain. "
                                      "Rows in the scoring step itself are listed as review-time (order inside an "
                                      "hour is unknown)."},
        "sender_history": {"score_time": snd_prior, "review_time": snd_review},
        "missing_information": missing,
        "notes": notes(conn, case_id),
        "audit": audit(conn, case_id),
    }


def notes(conn, case_id: str) -> list[dict]:
    rows = conn.execute("SELECT note_id, actor, body, created_at FROM app.case_note WHERE case_id = %s "
                        "ORDER BY note_id", (case_id,)).fetchall()
    return [{"note_id": r[0], "actor": r[1], "body": r[2], "created_at": r[3], "trust": "analyst-authored, untrusted text"}
            for r in rows]


def audit(conn, case_id: str) -> list[dict]:
    rows = conn.execute("SELECT audit_id, actor, action, prior_state, new_state, at FROM app.audit_event "
                        "WHERE case_id = %s ORDER BY audit_id", (case_id,)).fetchall()
    keys = ["audit_id", "actor", "action", "prior_state", "new_state", "at"]
    return [dict(zip(keys, r)) for r in rows]


def transition(conn: psycopg.Connection, case_id: str, analyst: dict, expected_version: int, status: str,
               disposition: str | None, note: str | None) -> dict:
    """Optimistic state change; writes the case update, optional note and audit event atomically."""
    if disposition is not None and disposition not in DISPOSITIONS:
        raise CaseError(422, f"unknown disposition {disposition}")
    if status == "closed" and disposition is None:
        raise CaseError(422, "closing a case requires a disposition")
    if status != "closed" and disposition is not None:
        raise CaseError(422, "a disposition is recorded only when closing")
    with conn.transaction():
        cur = conn.execute("SELECT status, disposition, version FROM app.review_case WHERE case_id = %s FOR UPDATE",
                           (case_id,)).fetchone()
        if cur is None:
            raise CaseError(404, f"unknown case {case_id}")
        prior = {"status": cur[0], "disposition": cur[1], "version": cur[2]}
        if prior["version"] != expected_version:
            raise CaseError(409, "case was changed by someone else; reload before acting",
                            current_version=prior["version"], current_status=prior["status"])
        if status not in TRANSITIONS[prior["status"]]:
            raise CaseError(409, f"transition {prior['status']} -> {status} is not allowed",
                            current_version=prior["version"], current_status=prior["status"])
        conn.execute("UPDATE app.review_case SET status = %s, disposition = %s, version = version + 1, "
                     "assigned_to = %s, updated_at = now() WHERE case_id = %s AND version = %s",
                     (status, disposition, analyst["analyst_id"], case_id, expected_version))
        new = {"status": status, "disposition": disposition, "version": expected_version + 1}
        note_id = None
        if note:
            note_id = conn.execute("INSERT INTO app.case_note (case_id, actor, body) VALUES (%s, %s, %s) "
                                   "RETURNING note_id", (case_id, analyst["analyst_id"], note)).fetchone()[0]
            new["note_id"] = note_id
        run_id = conn.execute("SELECT run_id FROM app.review_case WHERE case_id = %s", (case_id,)).fetchone()[0]
        conn.execute("INSERT INTO app.audit_event (case_id, run_id, actor, action, prior_state, new_state) "
                     "VALUES (%s, %s, %s, 'case_transition', %s, %s)",
                     (case_id, run_id, analyst["analyst_id"], json.dumps(prior), json.dumps(new)))
    return new


def add_note(conn: psycopg.Connection, case_id: str, analyst: dict, body: str) -> dict:
    with conn.transaction():
        row = conn.execute("SELECT run_id FROM app.review_case WHERE case_id = %s", (case_id,)).fetchone()
        if row is None:
            raise CaseError(404, f"unknown case {case_id}")
        note_id = conn.execute("INSERT INTO app.case_note (case_id, actor, body) VALUES (%s, %s, %s) "
                               "RETURNING note_id", (case_id, analyst["analyst_id"], body)).fetchone()[0]
        conn.execute("INSERT INTO app.audit_event (case_id, run_id, actor, action, new_state) "
                     "VALUES (%s, %s, %s, 'note_added', %s)",
                     (case_id, row[0], analyst["analyst_id"], json.dumps({"note_id": note_id, "chars": len(body)})))
    return {"note_id": note_id}


def queue(conn, run_id: str, status: str | None, day: int | None, limit: int, offset: int) -> dict:
    where, params = ["c.run_id = %s"], [run_id]
    if status:
        where.append("c.status = %s")
        params.append(status)
    if day is not None:
        where.append("a.simulation_day = %s")
        params.append(day)
    clause = " AND ".join(where)
    total = conn.execute(f"SELECT count(*) FROM app.review_case c JOIN app.alert a USING (run_id, event_id) "
                         f"WHERE {clause}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT c.case_id, c.status, c.disposition, c.version, c.assigned_to, a.simulation_day, a.rank, "
        f"a.capacity, t.event_id, t.step, t.type, t.amount::text, s.score, "
        f"(s.features->>'dest_has_prior')::numeric::int AS dest_has_prior "
        f"FROM app.review_case c JOIN app.alert a USING (run_id, event_id) JOIN app.score s USING (run_id, event_id) "
        f"JOIN app.transaction_event t USING (event_id) WHERE {clause} "
        f"ORDER BY a.simulation_day, a.rank LIMIT %s OFFSET %s", params + [limit, offset]).fetchall()
    keys = ["case_id", "status", "disposition", "version", "assigned_to", "simulation_day", "rank", "capacity",
            "event_id", "step", "type", "amount", "score", "dest_has_prior"]
    return {"total": total, "items": [dict(zip(keys, r)) | {"unit": UNIT} for r in rows]}
