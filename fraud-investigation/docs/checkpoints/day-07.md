# Day 7 checkpoint — verification, performance, documentation

**Date:** 10 November 2026. **Scope:** T17, T18.

| task | status | evidence |
|---|---|---|
| T17 End-to-end and performance checks | complete | `tests/test_replay_db.py::test_analyst_workflow_end_to_end` (replay → score → alert → evidence → disposition → audit); [reports/day7/performance.json](../../reports/day7/performance.json); [reports/day7/fresh_setup.json](../../reports/day7/fresh_setup.json) |
| T18 Reproducible portfolio release | **complete** (recording follow-up below) | README, [architecture](../architecture.md), [data card](../data_card.md), [model card](../model_card.md), [evaluation](../evaluation.md), [demo script](../demo_script.md). The recording and T21 follow-ups were completed in the subsequent follow-ups; see below. |

At the initial Day 7 check, T21 was partial. The Day 6 follow-up subsequently completed the fixes and a fresh 10/12 holdout; its reported failures remain documented.

## Performance (measured, `reports/day7/performance.json`)

Hardware: i7-11800H (16 logical CPUs), 15.77 GiB RAM (2.4–2.9 GiB free during the run), Windows 11, PostgreSQL 18.4 in Docker.

| measurement | result |
|---|---|
| history features, 6,362,620 rows | 5.7–6.0 s |
| offline scoring, test window (1,248,736 rows) | load 0.5 s, design matrix 1.3–1.6 s, predict 3.4–4.6 s (270k–365k rows/s); peak working set 1.4 GiB |
| replay | warm-up 55–63 s; ≈2,000 rows/s (873,533 rows in 438 s) |
| API sequential p50/p95 | health 17/38 ms, overview 20/39 ms, queue page 28/57 ms, case evidence 35/60 ms, `/score` 34/62 ms |
| `/score` concurrency 4 | p50 59–70 ms, 51–66 requests/s (two runs) |
| `/score` concurrency 8 | p50 160 ms, 50 requests/s |
| local assistant | 10–130 s per question |

**Two findings from the measurement:**
1. **My first concurrency measurement was wrong:** 776 ms p50 and 5 requests/s. The client created a new httpx client per request, which costs about 240 ms on this machine; a shared client fixed it. Separately, `localhost` adds about 2.3 s per new connection here (`127.0.0.1` doesn't), so the docs now say to use `127.0.0.1`.
2. **An evidence-based server change:** single-row predictions now run with one OpenMP thread (`serving.SMALL_BATCH`). In an A/B test at concurrency 4 this raised throughput from 38.8 to 65.5 requests/s and lowered p50 from 94 to 59 ms, with no change to sequential latency. Scores are unchanged: the exact replay/offline equality tests still pass. Large batches keep all threads.

## Fresh-setup reproduction (`scripts/fresh_setup_check.py`)

A clean copy (source and config only; no venv, data, models, reports, `node_modules` or `.env`) went through 14 steps, all exit code 0, in 1,406 s:
- venv from `requirements.lock` (117 s install);
- verify, ingest (18.5 s), audit (41 s), features (7 s), evaluate-dev (128 s), select (443 s), freeze (53 s), final-test re-score (551 s);
- pytest: 90 passed, 8 database tests skipped (no credentials copied);
- `npm ci` and the UI build.

**All comparisons are identical:** audit support, coverage and duplicates; all validation ranking metrics; the selection decision and all 12 candidate APs; the reproduced validation AP; **the model artifact SHA-256**; final-test point metrics for all four methods; bootstrap intervals.

Re-scoring the test partition in the copy is a reproducibility check of the already-frozen pipeline; it feeds no selection or tuning.

## Release documentation

- **README:** problem, headline results with caveats, document index, requirements, setup from the lockfile, commands for every stage, database/UI/assistant, contracts and conventions.
- **Data card:** licence and citation, field use, measured quality, partitions, simulator artifacts.
- **Model card:** configuration, intended use, selection table, final test with intervals, mixed-hour diagnostic, consistency, limitations.
- **Architecture:** diagram, enforced boundaries, components, runtime.
- **Evaluation:** ranking, replay consistency, assistant evaluation, performance, reproducibility.
- **Demo script:** 3–5 minutes; uses only existing features and supported claims, and lists claims to avoid.

## Tests

98 passed in the main checkout (including 8 database tests); 90 passed + 8 skipped in the fresh copy.

## What remains open (honest list)

1. **Demo recording (T18)** — completed; see recording follow-up below.
2. **Assistant follow-ups (T21)** — completed and evaluated on a fresh holdout; see the Day 6 follow-up. Remaining competence/guard limitations are disclosed.
3. **Optional eve adapter:** needs Node.js ≥ 24 (installed 22.9.0).
4. **Engineering:** API database connection pooling; demo token authentication only; closed cases cannot be reopened.
5. **Repository:** the folder is not a Git repository. `.gitignore` already excludes data, models, `.env`, `.venv`, `.tools`, `node_modules` and `web/dist`. Creating the repository and the first commit is for you to decide.
6. **Deferred by plan:** ULB benchmark (T22), calibration, Arabic summaries, public hosting.


---

## Recording follow-up — 10 November 2026

T18 is complete. The actual local browser workflow was recorded and delivered as [a captioned MP4](../../../outputs/Fraud_Detection_Demo.mp4), approximately 4 min 40 s, with [captions](../../../outputs/Fraud_Detection_Demo.srt) and [verification](../../../outputs/Fraud_Detection_Demo_Verification.json).

The video shows the overview and frozen evaluation, a ranked queue, case evidence and history timing, an actual local qwen3:4b response, and a human review ending with needs more information and its audit trail. The assistant response took 59.77 seconds; its case version/notes/audit counts did not change. The human subsequently changed the synthetic demo case through the UI.

Verification: 101 tests passed (one dependency deprecation warning) in 9.95 seconds. No holdout evaluation was rerun. The original holdout, new holdout and frozen identity files kept their pre-recording SHA-256 values. Full video decoding succeeded, and sampled frames were visually checked.

The recording explicitly retains the synthetic-data caveat, ranking-score semantics, simulator artifact, 10/12 fresh holdout result, and the remaining question-number/refusal-grading/short-paraphrase limitations. Editorial captions are in a separate lower band. No audio or generation speedup is used; no analyst credential is shown. One chapter edit joins the human-review continuation after a capture-selector error; the live assistant response was not regenerated.

No fraud model, assistant guard, grading rubric or evaluation result was changed to make this recording.
