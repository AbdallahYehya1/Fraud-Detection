-- Day 5 analyst workflow (T15/T16).
-- Demo authentication: each analyst has a random bearer token; only its SHA-256 is stored.

CREATE TABLE app.analyst (
    analyst_id   text PRIMARY KEY CHECK (analyst_id ~ '^[a-z][a-z0-9_-]{1,31}$'),
    display_name text NOT NULL,
    token_sha256 char(64) NOT NULL UNIQUE,
    active       boolean NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE app.review_case
    ADD COLUMN assigned_to text REFERENCES app.analyst,
    ADD CONSTRAINT closed_needs_disposition CHECK (status <> 'closed' OR disposition IS NOT NULL);

ALTER TABLE app.case_note ADD CONSTRAINT case_note_actor_fk FOREIGN KEY (actor) REFERENCES app.analyst;

CREATE INDEX audit_event_case ON app.audit_event (case_id, audit_id);
CREATE INDEX case_note_case ON app.case_note (case_id, note_id);
CREATE INDEX review_case_queue ON app.review_case (run_id, status);
