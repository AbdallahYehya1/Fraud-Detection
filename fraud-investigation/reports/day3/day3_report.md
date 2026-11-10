# Day 3 — selection on validation and one-time final test (generated)

## Selection (validation only)

Protocol `selection-v1` (config/selection_protocol.yaml, written before any history or booster model was scored). Amount/type rule validation AP: 0.0038.

| candidate | features | validation AP | ROC-AUC | K=100 recall | K=100 precision | fit s |
|---|---|---|---|---|---|---|
| logistic_regression {"C": 0.01} | base | 0.0031 | 0.883 | 0.52% | 1.30% | 3.49 |
| logistic_regression {"C": 1.0} | base | 0.0031 | 0.883 | 0.52% | 1.30% | 4.0 |
| logistic_regression {"C": 0.01} | base_novelty | 0.0119 | 0.914 | 2.73% | 6.82% | 3.74 |
| logistic_regression {"C": 1.0} | base_novelty | 0.0119 | 0.914 | 2.73% | 6.82% | 4.48 |
| logistic_regression {"C": 0.01} | base_history | 0.0120 | 0.917 | 2.21% | 5.52% | 5.62 |
| logistic_regression {"C": 1.0} | base_history | 0.0120 | 0.918 | 2.08% | 5.19% | 8.06 |
| logistic_regression {"C": 0.01} | base_history_window | 0.0121 | 0.916 | 1.95% | 4.87% | 8.38 |
| logistic_regression {"C": 1.0} | base_history_window | 0.0121 | 0.916 | 1.95% | 4.87% | 8.3 |
| hist_gradient_boosting {"learning_rate": 0.1, "max_leaf_nodes": 15, "max_iter": 200, "class_weight": "balanced"} | base_history | 0.1525 | 0.955 | 13.12% | 32.79% | 18.8 |
| hist_gradient_boosting {"learning_rate": 0.1, "max_leaf_nodes": 31, "max_iter": 200, "class_weight": null} | base_history | 0.0533 | 0.786 | 9.09% | 22.73% | 18.72 |
| hist_gradient_boosting {"learning_rate": 0.1, "max_leaf_nodes": 15, "max_iter": 200, "class_weight": "balanced"} | base_history_window | 0.1604 | 0.955 | 14.03% | 35.06% | 19.55 |
| hist_gradient_boosting {"learning_rate": 0.1, "max_leaf_nodes": 31, "max_iter": 200, "class_weight": null} | base_history_window | 0.0441 | 0.779 | 8.44% | 21.10% | 19.0 |
| **ablation, not eligible** | ablation:history_window_plus_hour | 0.3520 | | 30.39% | | |

Decision: **hist_gradient_boosting:base_history_window:{"class_weight": "balanced", "learning_rate": 0.1, "max_iter": 200, "max_leaf_nodes": 15}** — highest AP band (>= 0.157177); then K=100 recall, then simpler model.

The hour-of-day ablation roughly doubles validation AP. Pure-positive simulator hours are concentrated at night (Day 1 audit), so this gain is treated as a simulator shortcut and the feature stays excluded.

## Frozen selection

- Model `champion-v1`: hist_gradient_boosting {"learning_rate": 0.1, "max_leaf_nodes": 15, "max_iter": 200, "class_weight": "balanced"}
- Features: ['type_onehot', 'log1p_amount', 'dest_has_prior', 'dest_prior_count', 'dest_prior_amount_sum', 'dest_prior_count_24h', 'dest_steps_since_last'] → columns ['type_onehot=CASH_IN', 'type_onehot=CASH_OUT', 'type_onehot=DEBIT', 'type_onehot=PAYMENT', 'type_onehot=TRANSFER', 'log1p_amount', 'dest_has_prior', 'dest_prior_count', 'dest_prior_amount_sum', 'dest_prior_count_24h', 'dest_steps_since_last']
- Versions: contract `features-v1`, history table `features-v1`, split `split-v1`, selection `selection-v1`, policy `policy-v1` (daily top-100)
- Artifact `models/champion-v1.joblib` sha256 `883fd97cb5ac5f8c26b38a4976072706825c53a3308216a3493f3c94b9af536a` (scikit-learn 1.7.2)
- Refit reproduced validation AP exactly: 0.1603848023307718
- Frozen at 2026-11-09T20:57:13+00:00; test accessed before freeze: False
- ranking score (class-weighted booster); not a calibrated probability

## Final test (run once)

Population: all 1,248,736 test rows (steps 356–743), 4,250 positives, prevalence 0.34% — about 5.7× the validation prevalence. Constant-score AP reference = 0.0034.

| method | AP | ROC-AUC | K/day | alerts | true pos. | precision | recall | false alerts /1000 legit |
|---|---|---|---|---|---|---|---|---|
| champion | 0.3347 | 0.949 | 50 | 808 | 716 | 88.61% | 16.85% | 0.074 |
| champion | 0.3347 | 0.949 | 100 | 1,617 | 1,189 | 73.53% | 27.98% | 0.344 |
| champion | 0.3347 | 0.949 | 200 | 3,234 | 1,776 | 54.92% | 41.79% | 1.172 |
| amount_type_rule | 0.0846 | 0.871 | 50 | 808 | 413 | 51.11% | 9.72% | 0.317 |
| amount_type_rule | 0.0846 | 0.871 | 100 | 1,617 | 670 | 41.43% | 15.76% | 0.761 |
| amount_type_rule | 0.0846 | 0.871 | 200 | 3,234 | 1,012 | 31.29% | 23.81% | 1.785 |
| logistic_regression_base | 0.0387 | 0.892 | 50 | 808 | 286 | 35.40% | 6.73% | 0.419 |
| logistic_regression_base | 0.0387 | 0.892 | 100 | 1,617 | 428 | 26.47% | 10.07% | 0.955 |
| logistic_regression_base | 0.0387 | 0.892 | 200 | 3,234 | 641 | 19.82% | 15.08% | 2.084 |
| seeded_random | 0.0034 | 0.499 | 50 | 808 | 57 | 7.05% | 1.34% | 0.603 |
| seeded_random | 0.0034 | 0.499 | 100 | 1,617 | 115 | 7.11% | 2.71% | 1.207 |
| seeded_random | 0.0034 | 0.499 | 200 | 3,234 | 226 | 6.99% | 5.32% | 2.417 |

Native `isFlaggedFraud` policy (own workload): 13 alerts, 13 true positives (precision 100.00%, recall 0.31%).

### Day-block bootstrap (95% percentile intervals)

200 resamples of the 17 test day segments, seed 20261109.

| method | AP | K=100 recall | K=100 precision |
|---|---|---|---|
| champion | 0.2697–0.5194 | 24.82%–30.89% | 65.76%–82.07% |
| amount_type_rule | 0.0431–0.1862 | 11.90%–20.02% | 31.31%–53.13% |
| logistic_regression_base | 0.0213–0.1009 | 6.95%–14.45% | 18.76%–37.65% |
| seeded_random | 0.0019–0.0111 | 0.37%–7.41% | 0.99%–19.35% |

### Complete days only (K=100)

| method | alerts | true pos. | precision | recall |
|---|---|---|---|---|
| champion | 1,500 | 1,081 | 72.07% | 27.55% |
| amount_type_rule | 1,500 | 570 | 38.00% | 14.53% |
| logistic_regression_base | 1,500 | 330 | 22.00% | 8.41% |
| seeded_random | 1,500 | 19 | 1.27% | 0.48% |

### By transaction type (K=100)

| method | type | rows | positives | AP | true pos. | alerts |
|---|---|---|---|---|---|---|
| champion | CASH_IN | 276,810 | 0 | n/a | 0 | 0 |
| champion | CASH_OUT | 423,501 | 2,125 | 0.4101 | 707 | 727 |
| champion | DEBIT | 8,899 | 0 | n/a | 0 | 0 |
| champion | PAYMENT | 431,087 | 0 | n/a | 0 | 0 |
| champion | TRANSFER | 108,439 | 2,125 | 0.2089 | 482 | 890 |
| amount_type_rule | CASH_IN | 276,810 | 0 | n/a | 0 | 0 |
| amount_type_rule | CASH_OUT | 423,501 | 2,125 | 0.4302 | 330 | 330 |
| amount_type_rule | DEBIT | 8,899 | 0 | n/a | 0 | 0 |
| amount_type_rule | PAYMENT | 431,087 | 0 | n/a | 0 | 0 |
| amount_type_rule | TRANSFER | 108,439 | 2,125 | 0.0584 | 340 | 1,287 |

### Evaluator-only hour-mix diagnostics (K=100)

| method | hour kind | rows | positives | selected true pos. | AP within subset |
|---|---|---|---|---|---|
| champion | mixed | 1,242,924 | 2,000 | 505 | 0.2411 |
| champion | pure_positive | 2,250 | 2,250 | 684 | n/a |
| champion | no_positive | 3,562 | 0 | 0 | n/a |
| amount_type_rule | mixed | 1,242,924 | 2,000 | 237 | 0.0378 |
| amount_type_rule | pure_positive | 2,250 | 2,250 | 433 | n/a |
| amount_type_rule | no_positive | 3,562 | 0 | 0 | n/a |
| logistic_regression_base | mixed | 1,242,924 | 2,000 | 136 | 0.0163 |
| logistic_regression_base | pure_positive | 2,250 | 2,250 | 292 | n/a |
| logistic_regression_base | no_positive | 3,562 | 0 | 0 | n/a |
| seeded_random | mixed | 1,242,924 | 2,000 | 10 | 0.0017 |
| seeded_random | pure_positive | 2,250 | 2,250 | 105 | n/a |
| seeded_random | no_positive | 3,562 | 0 | 0 | n/a |

### Per day segment (champion, K=100)

| day | hours | capacity | positives | true pos. | precision | recall |
|---|---|---|---|---|---|---|
| 14 | 5 | 21 | 54 | 12 | 57.14% | 22.22% |
| 15 | 24 | 100 | 252 | 44 | 44.00% | 17.46% |
| 16 | 24 | 100 | 320 | 57 | 57.00% | 17.81% |
| 17 | 24 | 100 | 268 | 94 | 94.00% | 35.07% |
| 18 | 24 | 100 | 256 | 91 | 91.00% | 35.55% |
| 19 | 24 | 100 | 236 | 78 | 78.00% | 33.05% |
| 20 | 24 | 100 | 272 | 64 | 64.00% | 23.53% |
| 21 | 24 | 100 | 256 | 51 | 51.00% | 19.92% |
| 22 | 24 | 100 | 216 | 49 | 49.00% | 22.69% |
| 23 | 24 | 100 | 280 | 77 | 77.00% | 27.50% |
| 24 | 24 | 100 | 240 | 66 | 66.00% | 27.50% |
| 25 | 24 | 100 | 272 | 91 | 91.00% | 33.46% |
| 26 | 24 | 100 | 280 | 93 | 93.00% | 33.21% |
| 27 | 24 | 100 | 248 | 75 | 75.00% | 30.24% |
| 28 | 24 | 100 | 260 | 62 | 62.00% | 23.85% |
| 29 | 24 | 100 | 268 | 89 | 89.00% | 33.21% |
| 30 | 23 | 96 | 272 | 96 | 100.00% | 35.29% |

## Reading these results

- Synthetic PaySim data; no real-bank validity, fraud savings or analyst-time claims follow from these numbers.
- Test prevalence is ~5.7× validation, so test AP is not comparable to validation AP in absolute terms.
- A large share of the champion's test hits fall in pure-positive simulator hours; the mixed-hour row is the more conservative view. Both are evaluator-only diagnostics.
- The main signal is recipient novelty: in the Day 1 audit, 0% of validation/test positive TRANSFERs had an earlier-step recipient record versus ~88% of legitimate TRANSFERs. That pattern may be specific to the simulator.
- Scores are ranking scores; calibration is deferred.
- Final test runtime 396.46s; peak Python working set 1456.7 MiB.
