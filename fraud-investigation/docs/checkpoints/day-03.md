# Day 3 checkpoint — selection, freeze and one-time final test

**Date:** 9 November 2026. **Scope:** T09, T10, T11. Full report: [reports/day3/day3_report.md](../../reports/day3/day3_report.md).

| task | status | evidence |
|---|---|---|
| T09 Eligible history features | complete | `src/fraudinv/features.py` (DuckDB, 6,362,620 rows in 3.4 s, label-free); parity test against the pandas reference on all 5 features; ablation ladder in the selection report |
| T10 One CPU booster compared | complete | [config/selection_protocol.yaml](../../config/selection_protocol.yaml); [reports/day3/selection_report.json](../../reports/day3/selection_report.json) (12 candidates + 1 ablation, 286 s) |
| T11 Freeze champion, policy, final evaluation | complete | [reports/frozen/selection.json](../../reports/frozen/selection.json); [reports/day3/final_test_report.json](../../reports/day3/final_test_report.json) |

## Order of operations (gate check)

1. Wrote `selection_protocol.yaml` (metric, tie rule, baseline gate, candidates, bounded booster search). This was after seeing the Day 2 base-feature validation results and before any history or booster model was scored.
2. Changed the hour-of-day ablation from one-hot LR to an integer column in booster config 1, also before any run, because the ~1 GB one-hot matrix did not fit in ~2 GiB of free RAM. The change is recorded in the protocol file.
3. `python -m fraudinv select` (validation only).
4. `python -m fraudinv freeze`: refit reproduced validation AP **exactly** (0.1603848023307718); artifact SHA-256 recorded. Re-frozen once to store the artifact path in POSIX form; same hash, test still untouched.
5. `python -m fraudinv final-test` ran once (396 s; peak working set 1,457 MiB). A second invocation is refused unless a rerun reason is supplied (verified).

## Validation selection

| candidate | features | AP | K=100 recall |
|---|---|---|---|
| LR | base | 0.0031 | 0.52% |
| LR | + recipient novelty | 0.0119 | 2.73% |
| LR | + all-history count/sum | 0.0120 | 2.21% |
| LR | + 24-step count, steps-since-last | 0.0121 | 1.95% |
| booster (15 leaves, balanced) | base_history | 0.1525 | 13.12% |
| **booster (15 leaves, balanced)** | **base_history_window** | **0.1604** | **14.03%** |
| booster (31 leaves, unweighted) | base_history / _window | 0.053 / 0.044 | 9.1% / 8.4% |
| ablation, not eligible: + hour_of_day | | 0.3520 | 30.39% |

Champion `champion-v1`: HistGradientBoosting(lr 0.1, 15 leaves, 200 iterations, balanced class weights, no early stopping, seed 20261109). Features: type one-hot, log1p amount, recipient has-prior, prior count, prior amount sum, 24-step count, steps since last. Policy `policy-v1`: daily top-100 per segment.

## Final test (1,248,736 rows, 4,250 positives, prevalence 0.340%)

| method | AP (95% day-block interval) | K=100: hits / 1,617 alerts | precision | recall | false alerts /1000 legit |
|---|---|---|---|---|---|
| **champion** | **0.335** (0.270–0.519) | 1,189 | 73.5% | 28.0% | 0.34 |
| amount/type rule | 0.085 (0.043–0.186) | 670 | 41.4% | 15.8% | 0.76 |
| LR base | 0.039 | 428 | 26.5% | 10.1% | 0.96 |
| seeded random | 0.0034 | 115 | 7.1% | 2.7% | 1.21 |
| native policy (own workload) | — | 13 / 13 alerts | 100% | 0.31% | 0 |

Complete days only: champion 1,081/1,500, recall 27.6%.

**Simulator-artifact diagnostic (evaluator-only):** 684 of the champion's 1,189 hits are in pure-positive hours. In mixed hours alone, the champion's AP is 0.241 and it finds 505 of 2,000 positives; the rule's AP there is 0.038.

## Limitations

- Test prevalence is ~5.7× validation, so absolute AP is not comparable across partitions.
- The dominant signal is recipient novelty for TRANSFER positives (0% have an earlier recipient record). This may be a PaySim generator property rather than transferable fraud behaviour.
- Scores are ranking scores; calibration is deferred. No real-bank validity, fraud savings or staffing claims.
- The bootstrap resamples 17 day segments; intervals are wide.
