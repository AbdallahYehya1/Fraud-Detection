# Model card — champion-v1

## Summary

| | |
|---|---|
| Model | scikit-learn 1.7.2 `HistGradientBoostingClassifier` (learning rate 0.1, 15 leaves, 200 iterations, balanced class weights, no early stopping, seed 20261109) |
| Inputs (`features-v1`) | transaction type (one-hot), log1p(amount), recipient has an earlier record, log1p(earlier recipient count), log1p(earlier recipient amount sum), log1p(recipient count in previous 24 steps), log1p(steps since recipient's last record; missing if none) |
| History rule | strictly earlier steps; rows in the same hour never see each other; full prior warm-up |
| Output | a **ranking score**, not a calibrated probability |
| Policy (`policy-v1`) | daily top-100 per (partition, simulation day), pro-rated for partial days, ties by sha256(event_id) |
| Artifact | `models/champion-v1.joblib`, SHA-256 `883fd97c…af536a`, 372,896 bytes; trusted build only, verified on every load |
| Training data | train partition, steps 1–281 (3,820,599 rows, 3,193 positives) of synthetic PaySim v2 |

## Intended use

Ranking recorded **synthetic** transactions for a limited daily analyst review queue in a portfolio demonstration. It is not intended for real payments, authorization decisions, or judgements about real people.

## Selection (validation only; `reports/day3/day3_report.md`)

The rules were registered before any history or booster model was scored (`config/selection_protocol.yaml`): 8 logistic-regression and 4 booster candidates.

| model | validation AP | recall at 100/day |
|---|---|---|
| amount/type rule | 0.0038 | 1.0% |
| logistic regression, type + amount | 0.0031 | 0.5% |
| logistic regression + recipient history | 0.0121 | 2.0% |
| **booster + recipient history (selected)** | **0.1604** | **14.0%** |
| ablation, not eligible: + hour of day | 0.3520 | 30.4% |

Refitting the selection reproduced its validation AP exactly.

## Final test (run once, after freezing)

1,248,736 rows, 4,250 positives, prevalence 0.340%. Intervals are 95% day-block bootstrap ranges (200 resamples over 17 day segments).

| method | AP | found at 100/day | precision | recall | false alerts per 1,000 legitimate |
|---|---|---|---|---|---|
| **champion-v1** | **0.335** (0.270–0.519) | 1,189 / 4,250 | 73.5% | 28.0% | 0.34 |
| amount/type rule | 0.085 (0.043–0.186) | 670 | 41.4% | 15.8% | 0.76 |
| logistic regression, type + amount | 0.039 | 428 | 26.5% | 10.1% | 0.96 |
| seeded random ranking | 0.0034 | 115 | 7.1% | 2.7% | 1.21 |
| native `isFlaggedFraud` (own workload) | — | 13 of 13 alerts | 100% | 0.31% | 0 |

Evaluator-only diagnostic: 684 of the champion's 1,189 hits fall in pure-positive simulator hours. In mixed-label hours alone, AP is 0.241 and the champion finds 505 of 2,000 positives.

## Consistency

The serving path and the replay reproduce offline scores exactly: 74,152 of 74,152 rows, maximum difference 0.0. Each day's replay queue equals the offline test selection for that day.

## Limitations and risks

- Synthetic data; the main signal (recipient novelty) may be a generator property. No real-world performance, savings or staffing claim follows.
- Validation and test prevalence differ by about 5.7×, so absolute AP is not comparable across them.
- Pure-positive hours inflate whole-window metrics; read the mixed-hour row as the conservative view.
- Scores are uncalibrated; per-case feature contributions are not computed.
- A small bounded search (12 candidates) was used, so a better model may exist; none was tried after the test run.
- `isFlaggedFraud` and all balance fields are excluded by design.
