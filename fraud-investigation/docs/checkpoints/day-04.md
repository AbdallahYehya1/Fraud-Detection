# Day 4 checkpoint — scoring service, persistence and recoverable replay

**Date:** 9–10 November 2026. **Scope:** T12, T13, T14. All results below are measured on this machine.

| task | status | evidence |
|---|---|---|
| T12 Schema and typed API | complete | [sql/001_schema.sql](../../sql/001_schema.sql), `src/fraudinv/db.py`, `src/fraudinv/api.py`, `tests/test_api_contract.py` (22) |
| T13 Replay and checkpoint recovery | complete | `src/fraudinv/replay.py`, `tests/test_replay_db.py` (7), [reports/day4/replay_consistency.json](../../reports/day4/replay_consistency.json) |
| T14 Serving/offline consistency | complete | same report (`offline_parity`), `tests/test_replay_db.py::test_replay_features_and_scores_match_offline`, `::test_api_score_matches_replay_and_enforces_state` |

## Infrastructure

- PostgreSQL `postgres:18.4-alpine@sha256:9a8afca5…de15` (published 2026-07-07, digest checked against Docker Hub) via [docker-compose.yml](../../docker-compose.yml): bound to `127.0.0.1:55432`, 768 MiB memory limit, named volume.
- Docker Desktop 4.91.0 was not running; started with `docker desktop start`.
- `python -m fraudinv db-env` writes random local passwords to the git-ignored `.env`; `.env.example` documents the keys. Passwords are never printed.
- New pinned dependencies: fastapi 0.121.0, uvicorn 0.38.0, psycopg[binary] 3.2.12 (pydantic 2.14.3 resolved). `requirements.lock` refreshed.

## Design decisions

- **Truth isolation by role, not convention.** Schema `app` holds serving/replay/case state with no labels or balances. Schema `truth` is readable only by `fraudinv_eval`. The serving role `fraudinv_app` gets `InsufficientPrivilege` on `truth.label` (tested).
- **Append-only audit.** `app.audit_event` rejects UPDATE/DELETE/TRUNCATE by trigger for every role, admin included. The serving role also lacks UPDATE on scores, alerts, events, finalizations and notes.
- **Server-owned history.** `app.recipient_history` (count, integer cents, last step) and `app.recipient_step_count` (last 24 steps) per run. A run starting at step *s0* is warmed up from every unlabelled row with step < *s0*: 2,178,399 recipients and 399,061 window rows for *s0* = 356.
- **Atomic hours.** One transaction per simulation hour: events (shared, `ON CONFLICT DO NOTHING`), scores with the raw feature values plus the exact model input vector (`features` jsonb, `feature_sha256`), the history update, and the cursor `committed_through_step`. Replay requires an autocommit connection so each hour is a real top-level transaction, not a savepoint.
- **Idempotent day-end queue.** Each (partition, simulation_day) segment is finalized in its own transaction. The `day_finalization` primary key gates it, so a repeat inserts nothing. Capacity is pro-rated by observed hours, ties broken by `sha256(event_id)`. Cases store `scoring_step` and `case_evidence_cutoff_step` (the segment's last step) separately. Resume finalizes any segment whose last hour was committed before a crash.
- **API.** `POST /score` accepts only `run_id` plus `{step, type, amount, name_orig, name_dest}` (extra fields forbidden; amounts must be finite, ≥ 0, with ≤ 2 decimals). It scores against the run's state only when that state ends at `step − 1` (otherwise 409). It is a non-persisting preview; the replay command is the persistent path and uses the same `serving.score_rows`. Other endpoints: `GET /health`, `/model-info`, `/replays/{id}`, `/alerts`, `/transactions/{id}` (allowlisted fields). Case and disposition endpoints are Day 5.
- Port 8000 is taken by another local HTTPS service, so the API is documented on **127.0.0.1:8765**.

## Commands run and results

| command | result |
|---|---|
| `docker compose --env-file .env up -d` + `python -m fraudinv db-migrate` | healthy; `001_schema.sql` applied; a second migrate applies nothing |
| role probe | app→truth: InsufficientPrivilege; app DELETE audit: InsufficientPrivilege; admin UPDATE audit: rejected by trigger. The probe left one audit row, so the volume was recreated to start clean |
| trial replay 356–365 (test DB) | warm-up 55.4 s; 74,152 rows in 34.4 s; 2 segments × 21 alerts; offline comparison exact |
| `pytest -q` | first run 1 failed / 28 passed: my `/model-info` assertion matched `"balanced"`. Fixed to check the actual field names → **88 passed, 0 skipped** |
| `python -m fraudinv day4-check` (real rows, disposable DB) | **passed**, 229 s total (details below) |
| `replay-create` + `replay-run` demo `demo-test-d14-16`, steps 356–408 | warm-up 60.3 s; **873,533 rows in 437.8 s (~2,000 rows/s)**; 3 segments finalized (21 + 100 + 100 = 221 alerts and cases) |
| uvicorn on 127.0.0.1:8765, 200 sequential `/score` calls (step 409) | **p50 30.9 ms, p95 47.5 ms, max 102.7 ms** (each request opens a DB connection); label injection → 422; stale step → 409 |

## Real-data exit gate (`reports/day4/replay_consistency.json`)

- Crash injected in step 357 after 7,548 of 15,096 score inserts → run `failed`, cursor stayed at 356, **0** partial scores left for step 357.
- After resume: scores and feature hashes, day-end queue (42 alerts) and cases (42) are **identical** to the uninterrupted run; 74,152 scores, no duplicates.
- Re-running the completed replay scored 0 rows, finalized nothing, and changed nothing.
- **Offline parity:** 74,152 of 74,152 replay scores exactly equal the offline champion scores (max difference 0.0); 0 mismatches on each of the five history features.

## Resources

- Database size after the demo run: 1,574 MB (mostly per-score jsonb feature vectors and warm-up state); container 300 MiB of its 768 MiB limit.
- Peak Python working set during the check: 659 MiB. Free host RAM during replay: ~1.7 GiB. Ollama was stopped throughout.

## Limitations and open items

- `/score` opens a connection per request; pooling is deferred to the Day 7 performance pass (T17).
- Each run copies its own warm-up (~1 minute). That's fine for the MVP; a shared warm-up snapshot is possible later.
- Replay throughput (~2,000 rows/s) means the full 1.25M-row test window would take ~10 minutes; the demo uses 53 hours.
- Truth labels are not loaded into `truth.label` yet; the evaluation view (Day 5) loads them with the eval role.

## Next (Day 5)

T15 analyst queue and case evidence, then T16 human dispositions with optimistic versions and audit entries: React/TypeScript UI (overview, queue, case detail) over this API. Then T19 (assistant evaluation cases), which depends on T15.
