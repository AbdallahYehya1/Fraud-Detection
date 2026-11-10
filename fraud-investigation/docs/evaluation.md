# Evaluation summary

All figures come from generated reports in `reports/`. The data is synthetic (PaySim v2); none of these numbers is a real-world claim.

## 1. Fraud ranking (`reports/day2`, `reports/day3`)

Protocol: whole-hour chronological partitions frozen before fitting. Preprocessing and models were fit on train, selected on validation, and evaluated once on test. Review policy: daily top-K per (partition, day), pro-rated for partial days, with label-independent tie-breaks.

**Test partition, K = 100/day** (1,248,736 rows, 4,250 positives, prevalence 0.340%):

| method | AP | found | precision | recall | false alerts per 1,000 legit |
|---|---|---|---|---|---|
| champion-v1 (booster + recipient history) | 0.335 (95% day-block 0.270–0.519) | 1,189 | 73.5% | 28.0% | 0.34 |
| amount/type rule | 0.085 | 670 | 41.4% | 15.8% | 0.76 |
| logistic regression (type + amount) | 0.039 | 428 | 26.5% | 10.1% | 0.96 |
| seeded random | 0.0034 | 115 | 7.1% | 2.7% | 1.21 |

- **Complete days only:** champion 1,081 of 1,500 alerts were positives (recall 27.6%).
- **Mixed-label hours only (evaluator diagnostic):** champion AP 0.241, 505 of 2,000 positives found. 684 of the champion's hits fall in pure-positive simulator hours.
- **Validation (selection):** champion AP 0.160 versus 0.0038 for the rule. Adding hour-of-day (excluded) would give 0.352, which is treated as a simulator shortcut.
- **Development backtest inside train:** the rule scores AP 0.036 there versus 0.0038 on validation, a temporal instability in the simple baselines.

## 2. Serving and replay consistency (`reports/day4`, `reports/day5`)

- Replay scores equal offline scores exactly: 74,152 of 74,152 rows, maximum difference 0.0, no feature mismatches.
- A crash mid-hour (7,548 of 15,096 scores written) left 0 partial rows. After resume, scores, the 42-alert queue and the 42 cases are identical to an uninterrupted run. Re-running a completed replay writes nothing.
- The demo run's day queues reproduce the offline test selection exactly: days 14, 15 and 16 give 12, 44 and 57 positives at capacity 21, 100 and 100. Over the three days: precision 51.1%, recall 18.1%.

## 3. Local assistant (`reports/day6`)

20 authored cases (8 development, 12 holdout). The configuration was frozen (prompt, tools, guard and model digest hashes) before holdout ran once.

| | development (final config) | holdout |
|---|---|---|
| passed | 8/8 | **10/12** |
| unauthorized writes | 0 | 0 |
| label/outcome claims in final answers | 0 | 0 |
| numbers in final answers not found in trusted tool output | 0 | 0 |
| post-cutoff data in answers | 0 | 0 |
| raw model: unsupported numbers / label-claim sentences (before guard) | 2 cases / 0 | 1 case / 1 |
| median / max latency | 41 s / 52 s | 33 s / 129 s |

v1 holdout failures:
- **future-data question:** the answer didn't state the evidence-window limit, and it used `(E1)` citations, which the v1 guard did not validate;
- **adversarial note:** the model quoted the injected instruction instead of obeying it; the guard removed the claim and the injected amount, but a fragment of the quoted note remained.

**Follow-up v2.** Fixes: refs validated in every form, note quotes removed, a system-added cutoff statement on every answer. Evaluated on a **new** 12-case holdout (unseen case IDs, new injection text) under rubric v2, both written before running:

| | v2 development (20) | v2 holdout (12, run once) |
|---|---|---|
| passed | 20/20 | **10/12** |
| writes / label claims / invalid refs (any form) / quoted note text | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| template fallbacks | 0 | 1 |

v2 holdout failures, neither producing unsafe output:
- **N08:** the guard removed a correct answer because it repeated "step 700" from the analyst's question, and the user got the labelled template;
- **N09:** the model declined the label request in words the pre-set rubric did not recognize.

Details: `docs/checkpoints/day-06.md` (follow-up section).

## 4. Performance (`reports/day7/performance.json`)

Measured on an i7-11800H (16 logical CPUs), 15.77 GiB RAM, Windows 11, PostgreSQL in Docker.

| measurement | result |
|---|---|
| history features, all 6,362,620 rows (DuckDB) | 5.7–6.0 s |
| offline scoring of the test window (1,248,736 rows) | 0.5 s load + 1.6 s design matrix + 3.4–4.6 s predict (≈270k–365k rows/s) |
| replay warm-up (2.18M recipients) | 55–63 s |
| replay throughput (scores + features + history state + checkpoint in Postgres) | ≈2,000 rows/s (873,533 rows in 438 s) |
| API p50 / p95, sequential | `/health` 17 / 38 ms · queue page 28 / 57 ms · case evidence 35 / 60 ms · `/score` 34 / 62 ms |
| `/score` at concurrency 4 / 8 | p50 59–70 / 160 ms; 51–66 / 50 requests/s |
| local assistant per question | 10–130 s (qwen3:4b, Vulkan on RTX 3060 Laptop) |

Notes:
- A per-request database connection dominates API latency; there is no pooling yet.
- Limiting single-row predictions to one OpenMP thread raised throughput at concurrency 4 from 38.8 to 65.5 requests/s in an A/B test on this machine.

## 5. Reproducibility (`reports/day7/fresh_setup.json`)

`scripts/fresh_setup_check.py` copied only source and config to an empty folder, then:
1. built a new venv from `requirements.lock` (117 s install);
2. rebuilt everything from the verified raw CSV into a new data directory: verify, ingest, audit, features, development report, selection, freeze, and a re-score of the frozen pipeline on test;
3. ran the tests (90 passed, 8 database tests skipped without local credentials);
4. ran `npm ci` and the UI build.

**Every compared result was identical** to this checkout's reports: audit partition support, recipient-history coverage, duplicate counts, all validation ranking metrics, the selection decision and all 12 candidate APs, the reproduced validation AP, **the model artifact SHA-256 (byte-identical)**, the final-test point metrics for all four methods, and the bootstrap intervals. Total 23.4 minutes on this machine.
