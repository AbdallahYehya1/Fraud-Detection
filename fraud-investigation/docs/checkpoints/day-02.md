# Day 2 checkpoint — evaluation before tuning

**Date:** 9 November 2026. **Scope:** T07, T08. Validation only; the test partition was not read.

| task | status | evidence |
|---|---|---|
| T07 Meaningful baselines | complete | [reports/day2/validation_report.md](../../reports/day2/validation_report.md), `src/fraudinv/baselines.py` |
| T08 Capacity and artifact evaluation | complete | `src/fraudinv/evaluation.py`, `tests/test_evaluation.py` (8 tests) |

## Command

`python -m fraudinv evaluate-dev` — 68.7 s total; logistic regression grid 22.6 s; peak Python working set 1,609 MiB.

## Validation results (770 positives in 1,293,285 rows; prevalence 0.060%)

| method | AP | K=100/day: true pos. of 770 | precision | recall |
|---|---|---|---|---|
| constant score (prevalence reference) | 0.0006 | — | — | — |
| native `isFlaggedFraud` | — | 0 alerts in validation | n/a | 0% |
| seeded random daily ranking | 0.0006 | 0 | 0.00% | 0.00% |
| amount/type rule (types from training labels) | 0.0038 | 8 | 2.60% | 1.04% |
| logistic regression (type + log amount) | 0.0031 | 4 | 1.30% | 0.52% |

All alerting methods use 308 alerts at K=100 (pro-rated across one 7-hour, two full and one 19-hour segment). Both baselines are weak. CASH_OUT positives rank well within their type (AP 0.35), but large legitimate TRANSFERs use up the daily budget. Every hit came on day 14.

**Development backtest** inside training (fit 1–209, evaluate 210–281): rule AP 0.036 / 69 hits; LR AP 0.013 / 36 hits. That is stronger than on validation, so there is a temporal-stability gap.

## Design decisions

- Candidate population: every row of the segment (all types). Ties go to ascending `sha256(event_id)`.
- Native policy is reported at its own workload, never as a top-K ranking.
- Recall is shown as n/a on a population with no positives; precision is n/a when there are no alerts.
- Hour-mix diagnostics (pure-positive / mixed / no-positive hours) are computed from labels inside the evaluator only.
- `data.load_partition("test")` raises unless `allow_test=True` **and** a frozen selection record exists. Development code never passes the flag.
