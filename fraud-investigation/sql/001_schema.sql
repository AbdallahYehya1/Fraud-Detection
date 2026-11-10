-- Application schema (T12). Applied by `python -m fraudinv db-migrate` as the admin role.
-- app.*   : serving/replay/case state. Contains no labels and no balance fields.
-- truth.* : evaluator-only labels. The serving role has no privilege on this schema.

CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS truth;
REVOKE ALL ON SCHEMA truth FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE TABLE app.model_version (
    model_version         text PRIMARY KEY,
    artifact_sha256       char(64) NOT NULL,
    feature_contract      text NOT NULL,
    history_feature_table text NOT NULL,
    split_protocol        text NOT NULL,
    policy_version        text NOT NULL,
    features              jsonb NOT NULL,
    model_columns         jsonb NOT NULL,
    frozen_record         jsonb NOT NULL,
    registered_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.replay_run (
    run_id                 text PRIMARY KEY,
    dataset_key            text NOT NULL,
    csv_sha256             char(64) NOT NULL,
    model_version          text NOT NULL REFERENCES app.model_version,
    policy_version         text NOT NULL,
    daily_capacity         integer NOT NULL CHECK (daily_capacity > 0),
    first_step             integer NOT NULL CHECK (first_step BETWEEN 1 AND 743),
    last_step              integer NOT NULL CHECK (last_step BETWEEN first_step AND 743),
    warmup_rule            text NOT NULL,
    warmup_through_step    integer NOT NULL CHECK (warmup_through_step = first_step - 1),
    committed_through_step integer NOT NULL
        CHECK (committed_through_step BETWEEN first_step - 1 AND last_step),
    status                 text NOT NULL CHECK (status IN ('created', 'running', 'paused', 'completed', 'failed')),
    error                  text,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now()
);

-- Recorded transactions, shared by every run. Project event IDs, not bank IDs.
CREATE TABLE app.transaction_event (
    event_id   text PRIMARY KEY,
    source_row bigint NOT NULL UNIQUE CHECK (source_row >= 0),
    step       integer NOT NULL CHECK (step BETWEEN 1 AND 743),
    type       text NOT NULL CHECK (type IN ('CASH_IN', 'CASH_OUT', 'DEBIT', 'PAYMENT', 'TRANSFER')),
    amount     numeric(14, 2) NOT NULL CHECK (amount >= 0),
    name_orig  text NOT NULL CHECK (name_orig ~ '^[CM][0-9]+$'),
    name_dest  text NOT NULL CHECK (name_dest ~ '^[CM][0-9]+$')
);
CREATE INDEX transaction_event_dest_step ON app.transaction_event (name_dest, step);
CREATE INDEX transaction_event_orig_step ON app.transaction_event (name_orig, step);
CREATE INDEX transaction_event_step ON app.transaction_event (step);

-- Server-owned recipient history per run (strictly earlier steps; label-free).
CREATE TABLE app.recipient_history (
    run_id      text NOT NULL REFERENCES app.replay_run ON DELETE CASCADE,
    name_dest   text NOT NULL,
    prior_count bigint NOT NULL CHECK (prior_count > 0),
    prior_cents bigint NOT NULL CHECK (prior_cents >= 0),
    last_step   integer NOT NULL,
    PRIMARY KEY (run_id, name_dest)
);
CREATE TABLE app.recipient_step_count (
    run_id    text NOT NULL REFERENCES app.replay_run ON DELETE CASCADE,
    name_dest text NOT NULL,
    step      integer NOT NULL,
    n         integer NOT NULL CHECK (n > 0),
    PRIMARY KEY (run_id, name_dest, step)
);

CREATE TABLE app.score (
    run_id           text NOT NULL REFERENCES app.replay_run ON DELETE CASCADE,
    event_id         text NOT NULL REFERENCES app.transaction_event,
    scoring_step     integer NOT NULL,
    partition_name   text NOT NULL,
    simulation_day   integer NOT NULL,
    model_version    text NOT NULL REFERENCES app.model_version,
    feature_contract text NOT NULL,
    policy_version   text NOT NULL,
    score            double precision NOT NULL,
    features         jsonb NOT NULL,
    feature_sha256   char(64) NOT NULL,
    tie_key          char(16) NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, event_id)
);
CREATE INDEX score_queue ON app.score (run_id, partition_name, simulation_day, score DESC, tie_key);

CREATE TABLE app.day_finalization (
    run_id         text NOT NULL REFERENCES app.replay_run ON DELETE CASCADE,
    partition_name text NOT NULL,
    simulation_day integer NOT NULL,
    first_step     integer NOT NULL,
    last_step      integer NOT NULL,
    observed_hours integer NOT NULL,
    capacity       integer NOT NULL,
    alerts         integer NOT NULL,
    finalized_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, partition_name, simulation_day)
);

CREATE TABLE app.alert (
    run_id         text NOT NULL,
    event_id       text NOT NULL,
    partition_name text NOT NULL,
    simulation_day integer NOT NULL,
    rank           integer NOT NULL CHECK (rank > 0),
    capacity       integer NOT NULL,
    policy_version text NOT NULL,
    PRIMARY KEY (run_id, event_id),
    UNIQUE (run_id, partition_name, simulation_day, rank),
    FOREIGN KEY (run_id, event_id) REFERENCES app.score (run_id, event_id) ON DELETE CASCADE
);

CREATE TABLE app.review_case (
    case_id                   text PRIMARY KEY,
    run_id                    text NOT NULL,
    event_id                  text NOT NULL,
    status                    text NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'in_review', 'escalated', 'closed')),
    disposition               text CHECK (disposition IN
        ('needs_more_information', 'suspicious_in_demo', 'no_action')),
    version                   integer NOT NULL DEFAULT 1 CHECK (version > 0),
    scoring_step              integer NOT NULL,
    case_evidence_cutoff_step integer NOT NULL CHECK (case_evidence_cutoff_step >= scoring_step),
    created_at                timestamptz NOT NULL DEFAULT now(),
    updated_at                timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, event_id),
    FOREIGN KEY (run_id, event_id) REFERENCES app.alert (run_id, event_id) ON DELETE CASCADE
);

CREATE TABLE app.case_note (
    note_id    bigserial PRIMARY KEY,
    case_id    text NOT NULL REFERENCES app.review_case ON DELETE CASCADE,
    actor      text NOT NULL,
    body       text NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Append-only audit log: updates and deletes are rejected for every role.
CREATE TABLE app.audit_event (
    audit_id    bigserial PRIMARY KEY,
    case_id     text,
    run_id      text,
    actor       text NOT NULL,
    action      text NOT NULL,
    prior_state jsonb,
    new_state   jsonb,
    at          timestamptz NOT NULL DEFAULT now()
);
CREATE FUNCTION app.reject_audit_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_event is append-only';
END $$;
CREATE TRIGGER audit_event_append_only BEFORE UPDATE OR DELETE ON app.audit_event
    FOR EACH ROW EXECUTE FUNCTION app.reject_audit_change();
CREATE TRIGGER audit_event_no_truncate BEFORE TRUNCATE ON app.audit_event
    FOR EACH STATEMENT EXECUTE FUNCTION app.reject_audit_change();

-- Evaluator-only truth. Never joined by serving code.
CREATE TABLE truth.label (
    event_id         text PRIMARY KEY,
    is_fraud         smallint NOT NULL CHECK (is_fraud IN (0, 1)),
    is_flagged_fraud smallint NOT NULL CHECK (is_flagged_fraud IN (0, 1))
);
