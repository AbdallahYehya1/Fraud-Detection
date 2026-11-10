# Data card — PaySim v2 as used in this project

## Source and rights

- **Dataset:** Synthetic Financial Datasets For Fraud Detection (PaySim), publisher Edgar Lopez-Rojas, version 2. Canonical page: https://www.kaggle.com/datasets/ealaxi/paysim1
- **Licence:** CC BY-SA 4.0, verified from the publisher's metadata API on 8 November 2026. Attribution and share-alike apply to any shared adaptation of the data.
- **Citation:** E. A. Lopez-Rojas, A. Elmir and S. Axelsson. *PaySim: A financial mobile money simulator for fraud detection.* EMSS, 2016.
- **Files:** original archive 186,385,561 bytes, SHA-256 `f7eef9ff…596613d`; CSV `PS_20174392719_1491204439457_log.csv` 493,534,783 bytes, SHA-256 `16910f90…4eea6b`. Both are verified by `python -m fraudinv verify`. Raw files are never modified or copied into the application.

## What the data is (and is not)

- **Synthetic** mobile-money transactions produced by an agent-based simulator. It is not real customer data, and it supports no claim about any real bank, country, currency or customer behaviour.
- 6,362,620 rows × 11 columns; 8,213 rows labelled positive (0.129%).
- `step` is a **relative simulation hour** (1–743 observed); no calendar time is asserted, and order within an hour is unknown.
- `amount` is in **simulation currency units** (no currency is established). Values ≥ 10,000,000 are written in Java scientific notation in the CSV; after expansion every amount has at most 2 decimal places.

## Field use in this project

| field | use |
|---|---|
| step | time index; partitions, history windows, simulation day = floor((step−1)/24) |
| type | predictor (5 known types; unknown types rejected) |
| amount | predictor (log1p) |
| nameOrig, nameDest | lookup keys for history and evidence only, never predictors |
| oldbalanceOrg, newbalanceOrig, oldbalanceDest, newbalanceDest | **excluded** with all derivatives (publisher warning: affected by cancellation of detected fraud); not shown in cases |
| isFraud | training/evaluation target only; stored in a separate database schema the serving role cannot read |
| isFlaggedFraud | historical policy comparator only |

Project event ID: `PS2-16910f90-<0-based source row>`, assigned in original file order. It is not a bank transaction ID.

## Measured quality (full file; `reports/day1/data_quality_audit.md`)

- 0 missing, NaN, ±inf, unparseable or negative values; 0 unknown types or malformed IDs; labels strictly 0/1.
- 0 exact duplicate rows; 0 rows with identical non-label values but conflicting labels. No rows were removed.
- 16 zero-amount rows, all positive CASH_OUT (kept; noted as a simulator artifact).
- All positives are TRANSFER or CASH_OUT. All 16 policy flags are positive TRANSFERs.

## Partitions (frozen before fitting; `config/split_protocol.yaml`)

| partition | steps | rows | positives | prevalence |
|---|---|---|---|---|
| train | 1–281 | 3,820,599 | 3,193 | 0.084% |
| validation | 282–355 | 1,293,285 | 770 | 0.060% |
| test | 356–743 | 1,248,736 | 4,250 | 0.340% |

Test prevalence is about 5.7× validation (legitimate volume falls late in the simulation).

## Known simulator artifacts and limits

- **Pure-positive hours:** 320 of 743 hours contain only positive rows, concentrated at night (hour-of-day 2–7). They hold 2,250 of 4,250 test positives. They are reported as evaluator-only diagnostics, and hour-of-day is excluded from the model.
- **Recipient novelty:** 0% of validation/test positive TRANSFERs have an earlier record for their recipient, versus about 88% of legitimate TRANSFERs. This is the model's strongest signal and may be specific to the generator.
- **Sparse sender history:** only 0.09–0.26% of rows have an earlier sender record. Sender history is shown as evidence, never used as a feature.
- **No chains:** positive TRANSFER recipients never appear as positive CASH_OUT senders by ID; same-role recurrence is not a money flow.
- **Windowed counts drift:** 24-step recipient-history coverage falls from 44.9% to 19.3% across partitions.
