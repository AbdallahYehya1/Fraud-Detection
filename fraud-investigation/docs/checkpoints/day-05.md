# Day 5 checkpoint — analyst queue, case evidence and human dispositions

**Date:** 10 November 2026. **Scope:** T15, T16.

| task | status | evidence |
|---|---|---|
| T15 Analyst queue and case evidence | complete | `src/fraudinv/cases.py`, `src/fraudinv/api.py`, `web/src/{Overview,Queue,CaseView}.tsx`, `tests/test_replay_db.py::test_analyst_workflow_end_to_end`, browser check below |
| T16 Human disposition and audit flow | complete | [sql/002_workflow.sql](../../sql/002_workflow.sql), `cases.transition` / `add_note`, same end-to-end test |

## What was built

- **Migration 002:** `app.analyst` (stores only the SHA-256 of each bearer token; the serving role cannot insert or alter analysts), `closed_needs_disposition` constraint, `assigned_to`, note author foreign key, queue/audit indexes.
- **Evidence** (`GET /cases/{id}/evidence`), allowlisted fields only:
  - **score-time facts:** the frozen feature values stored with the score (F1–F6);
  - **eligible earlier records:** step < scoring step;
  - **review-time records:** scoring step up to `case_evidence_cutoff_step`, labelled as not used by the score; same-hour rows are listed here because order within an hour is unknown;
  - explicit missing-information statements (no earlier recipient/sender record, no device/identity data, balances excluded); notes marked as untrusted analyst text; the append-only audit trail.
- **Workflow:** `POST /cases/{id}/transition` with `expected_version`. Allowed transitions: new→in_review; in_review→escalated/closed/new; escalated→in_review/closed. Closing requires a disposition (`needs_more_information`, `suspicious_in_demo`, `no_action`); closed is terminal in the MVP. The case update, optional note and audit event commit in one transaction, with the row locked `FOR UPDATE`. A stale version returns 409 with the current version and status. `POST /cases/{id}/notes` writes a note plus an audit event.
- **Authentication (demo):** bearer token per analyst (`python -m fraudinv analyst-add <id>` writes it to a git-ignored file under `.tools/`). Missing or unknown tokens return 401. This is local demo authentication, not production identity.
- **Itemized evidence backfill:** when a day is finalized, earlier same-role rows for its alerted accounts are copied (label-free) from the source into `app.transaction_event`, so evidence can list history from before the replay window. This doesn't change history state or scores. `python -m fraudinv evidence-backfill` repairs it idempotently. Demo run: 41 + 479 + 468 rows in 1.3 s; each case reports whether the itemized count matches the score-time count.
- **Evaluation boundary:** `python -m fraudinv evaluate-run` runs as `fraudinv_eval`, loads `truth.label` for the run window (873,533 labels, 37 s) and writes aggregate metrics only (`reports/day5/run_evaluation_demo-test-d14-16.json`). The API's `/evaluation` serves those aggregates and the frozen test summary; it never returns per-case labels, and the serving role still cannot read `truth`.
- **UI** (`web/`, React 19.1.10, TypeScript 5.9.3, Vite 6.4.5, all pinned and at least two weeks old; Vite 7 would need Node ≥ 22.12, this machine has 22.9). Three views:
  - **Overview:** dataset/model/policy, run progress and case counts, plus a visibly separate "offline evaluation" panel;
  - **Queue:** run/day/status filters, rank, score, recipient-novelty tag;
  - **Case detail:** transaction, model evidence ("association, not proof"), facts, missing information, recipient and sender history (score-time vs review-time), action panel, notes, audit trail.

  Hash routing; light/dark themes; the built UI is served by FastAPI from the same process.

## Measured results

- **Replay queue vs offline evaluation:** each finalized day reproduces the one-time offline test evaluation exactly. Day 14: 12 true positives at capacity 21; day 15: 44 at 100; day 16: 57 at 100. Over the three days: 113 of 626 positives found with 221 alerts (precision 51.1%, recall 18.1%). Synthetic data; evaluator-only aggregates.
- **Browser check** (built-in browser, `http://localhost:8765`):
  - Overview showed the run (873,533 rows, 221 new cases) and the evaluation panel;
  - the day-15 queue listed 100 cases by rank;
  - case `d15 · r010` showed "No earlier records available in this dataset" for recipient and sender, the missing-information list, empty notes/audit, and a "Sign in…" prompt instead of actions;
  - an invalid token produced "Token not recognised";
  - no console errors.
- **Not checked in the browser:** the signed-in action flow. Reading the demo token file into this session was blocked as credential handling, and I did not work around it. That flow is covered by the automated end-to-end test; you can sign in with the token from `.tools/analyst-demo.token` to try it. Screenshots timed out because the app window was hidden, so visual layout (including narrow widths) was not inspected.
- **`npm run build`:** typecheck clean; 210 kB JS (65 kB gzipped).
- **Tests: 89 passed.** First run 1 failed: my test expected 12 cases, but pro-rated capacity over the 5- and 6-hour fixture days correctly gives 3. Fixed the expectation, not the code. The new end-to-end test covers:
  - the queue, and evidence with no label or balance fields and correctly split score-time/review-time steps;
  - 401 without a token and with a bad token;
  - 409 on a stale version; 422 when closing without a disposition, when setting a disposition while not closing, or when sending `isFraud`;
  - **two concurrent writers with the same version: exactly one 200 and one 409**;
  - close with disposition and note, then 409 on any change to the closed case;
  - notes stored verbatim (an HTML string is rendered escaped by React);
  - audit sequence and actor; serving role denied DELETE on audit and UPDATE on notes.

## Day 5 exit

A transaction moves through replay → score → alert → case evidence → human disposition → audit. This is demonstrated by `test_analyst_workflow_end_to_end` and by the demo run in the main database. Dataset truth stays inside the evaluator boundary.

## Limitations

- Demo token authentication only; no sessions, roles, expiry or rate limiting.
- Per-case model contributions are not computed for the booster; the case shows score-time inputs and says so.
- Itemized sender/recipient history exists only for alerted accounts (backfilled), which is enough for case review.
- Closed cases cannot be reopened.

## Next (Day 6)

T19: author ~20 assistant evaluation cases (development/holdout) over this evidence API. T20: bounded local assistant (qwen3:4b via Ollama/Vulkan) with read-only tools (`get_case_evidence`, `get_transaction`, `get_prior_account_history`, `get_model_evidence`) and a deterministic check that strips any citation not returned by a tool. The eve adapter still needs Node ≥ 24. T21 evaluates holdout fidelity.
