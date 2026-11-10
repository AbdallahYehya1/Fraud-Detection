# Day 2 development report — validation only (generated)

Protocol `split-v1`, feature contract `features-v1`. Test partition accessed: **False**. Scores are ranking scores, not probabilities.

Training rows 3,820,599 (3,193 positives); validation rows 1,293,285 (770 positives). Daily top-K applies to each (partition, simulation day) segment over all transaction types; partial segments get pro-rated capacity.

## Ranking and capacity on validation

| method | AP | ROC-AUC | K/day | alerts | true pos. | precision | recall | false alerts /1000 legit |
|---|---|---|---|---|---|---|---|---|
| all_negative | 0.0006 | 0.500 | 50 | 155 | 1 | 0.65% | 0.13% | 0.119 |
| all_negative | 0.0006 | 0.500 | 100 | 308 | 1 | 0.32% | 0.13% | 0.238 |
| all_negative | 0.0006 | 0.500 | 200 | 616 | 1 | 0.16% | 0.13% | 0.476 |
| seeded_random | 0.0006 | 0.501 | 50 | 155 | 0 | 0.00% | 0.00% | 0.120 |
| seeded_random | 0.0006 | 0.501 | 100 | 308 | 0 | 0.00% | 0.00% | 0.238 |
| seeded_random | 0.0006 | 0.501 | 200 | 616 | 1 | 0.16% | 0.13% | 0.476 |
| amount_type_rule | 0.0038 | 0.851 | 50 | 155 | 4 | 2.58% | 0.52% | 0.117 |
| amount_type_rule | 0.0038 | 0.851 | 100 | 308 | 8 | 2.60% | 1.04% | 0.232 |
| amount_type_rule | 0.0038 | 0.851 | 200 | 616 | 12 | 1.95% | 1.56% | 0.467 |
| logistic_regression | 0.0031 | 0.883 | 50 | 155 | 2 | 1.29% | 0.26% | 0.118 |
| logistic_regression | 0.0031 | 0.883 | 100 | 308 | 4 | 1.30% | 0.52% | 0.235 |
| logistic_regression | 0.0031 | 0.883 | 200 | 616 | 6 | 0.97% | 0.78% | 0.472 |

Native `isFlaggedFraud` policy on validation (own workload, not a top-K ranking): 0 alerts, 0 true positives of 770 positives (precision n/a, recall 0.00%).
Constant-score AP reference (prevalence): 0.000595. Accuracy if nothing is alerted: 99.94%.

## Logistic regression

Features ['type_onehot', 'log1p_amount'] (contract-validated columns ['type_onehot=CASH_IN', 'type_onehot=CASH_OUT', 'type_onehot=DEBIT', 'type_onehot=PAYMENT', 'type_onehot=TRANSFER', 'log1p_amount']); class_weight=balanced; C selected on validation AP from [0.01, 1.0, 100.0] → **0.01** (APs [0.003106, 0.003106, 0.003106]).

Coefficients (standardized log-amount): `type_onehot=CASH_IN` -4.9218, `type_onehot=CASH_OUT` 2.6525, `type_onehot=DEBIT` -0.2922, `type_onehot=PAYMENT` -4.1266, `type_onehot=TRANSFER` 4.0374, `log1p_amount` 0.5151

Amount/type rule types (from training labels only): ['CASH_OUT', 'TRANSFER'].

## Complete days only (sensitivity)

| method | K/day | alerts | true pos. | precision | recall |
|---|---|---|---|---|---|
| all_negative | 50 | 100 | 0 | 0.00% | 0.00% |
| all_negative | 100 | 200 | 0 | 0.00% | 0.00% |
| all_negative | 200 | 400 | 0 | 0.00% | 0.00% |
| seeded_random | 50 | 100 | 0 | 0.00% | 0.00% |
| seeded_random | 100 | 200 | 0 | 0.00% | 0.00% |
| seeded_random | 200 | 400 | 1 | 0.25% | 0.20% |
| amount_type_rule | 50 | 100 | 0 | 0.00% | 0.00% |
| amount_type_rule | 100 | 200 | 0 | 0.00% | 0.00% |
| amount_type_rule | 200 | 400 | 0 | 0.00% | 0.00% |
| logistic_regression | 50 | 100 | 0 | 0.00% | 0.00% |
| logistic_regression | 100 | 200 | 0 | 0.00% | 0.00% |
| logistic_regression | 200 | 400 | 0 | 0.00% | 0.00% |

## Per segment at K=100

| method | partition | day | hours | capacity | positives | true pos. | recall |
|---|---|---|---|---|---|---|---|
| seeded_random | validation | 11 | 7 | 29 | 86 | 0 | 0.00% |
| seeded_random | validation | 12 | 24 | 100 | 242 | 0 | 0.00% |
| seeded_random | validation | 13 | 24 | 100 | 246 | 0 | 0.00% |
| seeded_random | validation | 14 | 19 | 79 | 196 | 0 | 0.00% |
| amount_type_rule | validation | 11 | 7 | 29 | 86 | 0 | 0.00% |
| amount_type_rule | validation | 12 | 24 | 100 | 242 | 0 | 0.00% |
| amount_type_rule | validation | 13 | 24 | 100 | 246 | 0 | 0.00% |
| amount_type_rule | validation | 14 | 19 | 79 | 196 | 8 | 4.08% |
| logistic_regression | validation | 11 | 7 | 29 | 86 | 0 | 0.00% |
| logistic_regression | validation | 12 | 24 | 100 | 242 | 0 | 0.00% |
| logistic_regression | validation | 13 | 24 | 100 | 246 | 0 | 0.00% |
| logistic_regression | validation | 14 | 19 | 79 | 196 | 4 | 2.04% |

## By transaction type at K=100

| method | type | rows | positives | AP | true pos. | alerts |
|---|---|---|---|---|---|---|
| amount_type_rule | CASH_IN | 285,430 | 0 | n/a | 0 | 0 |
| amount_type_rule | CASH_OUT | 456,641 | 385 | 0.3486 | 4 | 4 |
| amount_type_rule | DEBIT | 9,044 | 0 | n/a | 0 | 0 |
| amount_type_rule | PAYMENT | 433,249 | 0 | n/a | 0 | 0 |
| amount_type_rule | TRANSFER | 108,921 | 385 | 0.0030 | 4 | 304 |
| logistic_regression | CASH_IN | 285,430 | 0 | n/a | 0 | 0 |
| logistic_regression | CASH_OUT | 456,641 | 385 | 0.3486 | 0 | 0 |
| logistic_regression | DEBIT | 9,044 | 0 | n/a | 0 | 0 |
| logistic_regression | PAYMENT | 433,249 | 0 | n/a | 0 | 0 |
| logistic_regression | TRANSFER | 108,921 | 385 | 0.0030 | 4 | 308 |

## Evaluator-only hour-mix diagnostics at K=100

Label-defined subsets explain simulator artifacts; they are never features or serving filters.

| method | hour kind | rows | positives | selected true pos. | AP within subset |
|---|---|---|---|---|---|
| seeded_random | mixed | 1,262,867 | 574 | 0 | 0.0005 |
| seeded_random | pure_positive | 196 | 196 | 0 | n/a |
| seeded_random | no_positive | 30,222 | 0 | 0 | n/a |
| amount_type_rule | mixed | 1,262,867 | 574 | 8 | 0.0031 |
| amount_type_rule | pure_positive | 196 | 196 | 0 | n/a |
| amount_type_rule | no_positive | 30,222 | 0 | 0 | n/a |
| logistic_regression | mixed | 1,262,867 | 574 | 4 | 0.0024 |
| logistic_regression | pure_positive | 196 | 196 | 0 | n/a |
| logistic_regression | no_positive | 30,222 | 0 | 0 | n/a |

## Development backtest inside training

Fit steps (1, 209) (2339 positives), evaluate steps (210, 281) (1,164,429 rows, 854 positives). C=0.01.

| method | AP | K=100 true pos. | K=100 recall |
|---|---|---|---|
| seeded_random | 0.0007 | 0 | 0.00% |
| amount_type_rule | 0.0361 | 69 | 8.08% |
| logistic_regression | 0.0126 | 36 | 4.22% |

## Runtime
Total 68.69s ({'load': 3.31, 'random': 8.06, 'logistic_regression': 23.73, 'backtest': 23.11}); peak Python working set 1607.4 MiB.
