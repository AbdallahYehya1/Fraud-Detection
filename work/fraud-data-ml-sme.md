# Data, ML, and evaluation SME findings

Prepared 8 November 2026. Planning research only: no raw PaySim or ULB file was downloaded or profiled during this council review. Counts below are published reference expectations, not locally reproduced measurements.

## Recommendation and critical scope decisions

Keep PaySim as the first engineering/replay dataset, but make data audit a genuine milestone before promising model performance. Describe the product as **offline transaction replay, fraud-risk prioritization, and evidence-assisted investigation**. It does not establish live authorization performance, real fraud savings, Egyptian market validation, or comprehensive fraud coverage.

Conservatively exclude **all four balance columns** and every balance-derived feature from the main score. Indexed reproductions of the original Kaggle card contain a warning that detected fraudulent transfers are cancelled and that all four balance columns must not be used for fraud detection. I could not render the original card directly to independently capture that warning. Make original-card capture an acquisition task, while adopting the safer feature boundary immediately. Independently, post-transaction balances are unavailable before execution and risk revealing outcomes. An optional later retrospective experiment can measure these artifacts, explicitly separate from the main benchmark.

PaySim remains suitable for demonstrating ingestion, temporal evaluation, model delivery, queue ranking, auditability, and source-backed case summaries. Its usefulness for rich per-sender behaviour is uncertain until IDs are audited: a published empirical study reports roughly 6.35 million distinct customer names in 6.36 million rows. Do not promise repeated sender histories or account takeover detection based on long histories before measuring recurrence.

## Dataset acquisition and provenance

### PaySim

- Canonical download: https://www.kaggle.com/datasets/ealaxi/paysim1
- Creator repository, including link to the dataset and description of simulation calibrated using aggregate real transaction logs: https://github.com/EdgarLopezPhD/PaySim
- Creator's foundational paper: https://www.msc-les.org/proceedings/emss/2016/EMSS2016_249.pdf
- Expected public sample: 6,362,620 rows, 11 columns, 8,213 fraud labels and 6,354,407 non-fraud labels, approximately 0.129% fraud. A paper that actually experimented on the sample documents these counts: https://www.mdpi.com/2227-7390/11/5/1184
- Common filename: `PS_20174392719_1491204439457_log.csv`; identify by source/version/schema and checksum rather than depending only on a filename.
- Common public CSV size is approximately 494 MB; compressed archive and in-memory size differ. Verify actual bytes after acquisition. Do not repeat third-party claims of 2.5 GB as an established file size.
- Kaggle download can require free account sign-in. There is no purchase price shown for the public release. Do not request, store, or commit the user's authentication token in the repository.
- Dataset licence is commonly reported as CC BY-SA 4.0 by metadata copies, but the original Kaggle card did not render for this review. **Capture the original current licence notice and version before redistributing data.** The creator simulator code is GPL-3.0; that does not establish the dataset licence.
- No creator-owned, clearly licensed, no-account mirror of the exact PaySim sample was verified. Avoid treating arbitrary GitHub/Hugging Face mirrors as authoritative.

At acquisition, record canonical URL, publisher, dataset identifier/version, retrieval date, archive/file byte sizes, SHA-256, licence notice/copy/link, citation, column list, row count, positive count, step coverage, and any upstream warning. Keep raw files immutable and outside Git; publish a downloader/readme and a tiny independently generated fixture instead.

### ULB / Worldline credit-card transactions (separate second benchmark)

- Original card: https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
- Verified official TensorFlow tutorial that hosts a direct mirror and reproduces 284,807 rows / 492 positives: https://www.tensorflow.org/tutorials/structured_data/imbalanced_data
- No-account CSV URL used by that official tutorial: https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv
- Expected CSV approximately 151 MB, 31 columns: `Time`, `V1` to `V28`, `Amount`, `Class`. Real anonymized European transactions from two days in September 2013. Original feature meanings for V1-V28 are unavailable.
- Original Kaggle source identifies an Open Database licence for database and Database Contents licence for contents; capture exact notices during acquisition. A mirror does not replace original terms.
- Train and evaluate a **separate model and schema**. Do not concatenate PaySim and ULB rows, reuse incompatible feature mappings, or imply PaySim model transfer was proven. The meaningful cross-dataset result is reproducibility of a methodology, not identical-model external validation.
- ULB supports imbalanced classification; it cannot support named merchant/location/device explanations. Existing PCA components were generated upstream; their training provenance cannot be reconstructed from the release.
- TensorFlow tutorial's random split is educational. Our project uses chronological validation instead; take the download source and learning material without copying an unsuitable validation design.

## PaySim field contract

`step`: integer simulation hour. Treat as relative simulation time; published samples commonly range 1-743 while upstream prose mentions 744 simulated steps. Measure actual range. Never silently assign real calendar dates.

`type`: categorical transaction type, normally `CASH_IN`, `CASH_OUT`, `DEBIT`, `PAYMENT`, `TRANSFER`. Confirm exact spellings in file.

`amount`: numeric simulated amount in an unspecified local currency. Display as **simulation currency units**, not EGP/USD. Reject invalid negative/non-finite values under a documented schema policy.

`nameOrig`, `nameDest`: opaque synthetic account identifiers. Preserve for joins/evidence; exclude raw ID values from the core predictor. A prefix identifying merchant/customer can be considered only if its definition is confirmed and it is known at the replay scoring moment. Never invent real names.

`oldbalanceOrg`, `newbalanceOrig`, `oldbalanceDest`, `newbalanceDest`: retain in quarantined raw data if permitted; exclude from core scoring and all derived scoring variables. Recipient merchant balance zeros can reflect unavailable information, so zeros are not uniformly true zero balances.

`isFraud`: binary evaluation/training target; hidden from serving input, agent tools, feature computation, and analyst screen until explicit evaluation reveal.

`isFlaggedFraud`: simulator business-rule flag. Evaluate separately as a historical comparator; never feed it into ML or the investigation assistant as ground truth. It encodes a policy rule, not verified fraud.

Create deterministic `transaction_id` from dataset version and original row position. Freeze that mapping before sorting/filtering. It is a key, not a feature.

## Permitted main feature set

Start with `type`, `log1p(amount)`, and cautiously defined time-of-day proxies derived from relative simulation hour. Keep raw `step` as an explicit ablation: it may learn generator/time artifacts and will not extrapolate like a calendar.

Candidate additions after recurrence audit: prior-step recipient transaction count and amount totals over 24/168 hours, sender history count/amount where history exists, prior sender-to-recipient count, recipient novelty and history-missing flags. Strictly use `history.step < current.step`. Score a whole hour from the previous-hour state, then update state; rows inside an hour lack independently documented ordering, so using earlier CSV rows in the same hour introduces an invented event order. Compute denominators and missing-history conventions explicitly.

Exclude future counts, full-dataset frequencies/means, target encodings fitted over all periods, current-hour aggregates, future account balances, and any fraudulent-label history that would not yet have been confirmed. Label-derived features should be absent in v1; label delay is not supplied by PaySim.

Separate replay events (`observed_at`) from any simulated review-confirmation timestamp (`confirmed_at`) if adding label-delay experiments. Synthetic reviewer decisions must remain labelled synthetic and are never a source of independently validated labels.

## Data audit checklist and stop/go gate

1. Verify checksum, source/version, exact schema, row count, type values and label domains.
2. Profile missing/infinite/negative fields and detect parsing changes; retain a reasoned rejection/quarantine count.
3. Produce transaction counts, positive counts and fraud prevalence per simulation hour/day and transaction type. Look for sparse tails, class-pure hours, and generator discontinuities.
4. Profile sender/recipient cardinality, recurrence, pair recurrence and historical-feature coverage. Report cold-start proportions.
5. Distinguish exact duplicated rows from genuine identical transactions. Investigate before removal; freeze a documented duplicate policy.
6. Publish a feature-availability manifest listing accepted/excluded columns and reasons. Tests must fail if prohibited fields enter the model pipeline.
7. Freeze train/validation/test cutoffs and all transformation fit scopes.

If no usable positives/negatives exist in the proposed final time window or all history features are empty, document the observed issue and redesign the evaluation before modelling. Do not search cutoffs to maximize scores. This audit is a decision milestone, not a promise that PaySim has no problems.

## Evaluation protocol

- Use whole-hour chronological groups. A starting design is approximately 60% of rows in early whole hours for training, 20% of subsequent rows for validation, and the final 20% for test. Choose boundaries using timestamps/counts, never target performance. Percentages of hour range need not equal percentages of rows. Record exact hours and class counts after inspection.
- Keep final test untouched for model/feature/threshold selection. Use rolling earlier validation windows if enough positives and volume support them. If calibrating, split the validation period chronologically into calibration and policy-selection segments, or use a clearly documented cross-fitting approach.
- Fit preprocessing, imputation, category vocabulary, transformations, sampling strategies, and models only on training. Missing categories must be handled at inference.
- Preserve natural prevalence in validation/test. A 50/50 training experiment is allowed only with clearly stated weights or correction and probability recalibration on representative data. Do not present balanced-set precision as deployed alert precision.
- Tune a review policy on validation, e.g. up to 100 highest scores per replay day or a fixed maximum alert fraction. Report capacity curves rather than promise 100/day is a real company's requirement. Batch daily top-K uses end-of-day information and must be described as offline queue prioritization, not instant authorization.
- Compare all methods on identical test rows, feature timing, transaction types, alert capacity, and labels. Retain all transaction types for whole-traffic reporting; a TRANSFER/CASH_OUT-only model is a separate scoped experiment, with that denominator visible.

Baselines: all-negative sanity check; historical `isFlaggedFraud` comparator; a separately implemented transparent amount/type rule; regularized logistic regression. First stronger model: one CPU tree booster (e.g. histogram gradient boosting / LightGBM), not a suite of deep networks. Isolation Forest is optional later and must fit without test leakage.

Primary metrics: **average precision (AP)**, precision and recall under the chosen capacity policy, false alerts per 1,000 legitimate transactions, total alerts, and positive count. Name AP explicitly: scikit-learn's `average_precision_score` is not trapezoidal PR-AUC (https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html). Secondary: ROC-AUC, confusion matrix, per-type/time-window slices, and calibration/Brier score if publishing probabilities. A raw class-weighted score is a ranking score until calibrated.

Value-weighted recall is sum of simulated fraud amounts flagged divided by total simulated fraud amount, not money saved. Any expected-cost calculation must state hypothetical investigation cost, missed-fraud loss, false-positive friction and recovery assumptions. Provide sensitivity across several assumptions. Report precision/recall uncertainty (e.g. temporal-block bootstrap where enough blocks exist) and positive counts; a one-month simulator cannot establish year-round robustness.

Evidence-backed validation reference for chronological splits and label delays: https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_3_GettingStarted/BaselineModeling.html

## Practical compute plan (planning estimates)

CPU models require no GPU. Prefer 16 GB RAM and several GB free disk; 8 GB can work with chunked ingestion, column pruning, compact numeric types and training subsets. A roughly 494 MB text file can consume multiple GB after parsing string IDs and building copies.

Use DuckDB/Arrow/Parquet for audit and stored feature tables, small categoricals for `type`, numeric model matrices without raw IDs, and batch evaluation. Begin with 100k-300k rows for pipeline debugging and label it a development sample. Final held-out metrics should cover the whole frozen test population. Sample training only after split, retain natural evaluation prevalence, and log sampling weights/configuration. Constrain model search to a small, documented set and record peak memory/time on the actual machine.

## Alternative dataset assessment

The Fraud Detection Handbook simulator is useful if recurring customer/terminal histories become essential: https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_3_GettingStarted/SimulatedDataset.html. Its authors supply reproducible generation and controlled time-dependent scenarios. The main repo explicitly licenses notebook code GPL v3.0 and prose/images CC BY-SA 4.0: https://github.com/Fraud-Detection-Handbook/fraud-detection-handbook. The separate raw-data repo shows no dataset licence on its readable root (https://github.com/Fraud-Detection-Handbook/simulated-data-raw), so do not assume it inherits those terms. If adopted, generate a reproducible test corpus under the documented code terms and resolve dataset redistribution terms explicitly. It is optional, not needed for the first milestone.

BAF is a different bank-account-opening task, not a replacement for transaction replay. Current third-party notices conflict about non-commercial/share-alike/no-derivatives conditions, and original dataset card did not render. Do not switch the main project to BAF solely for its row count.

## Skills the user should learn for this track

Python/Pandas and SQL aggregations; chunked tabular data handling; probability and confusion matrices; imbalanced learning and AP; chronological validation and data leakage; leakage-safe feature construction; logistic regression and tree ensembles; calibration versus ranking; reproducible pipelines/configuration/seeds; data and model versioning; serving the same preprocessing with a model; measuring throughput and inference latency; concise documentation of limitations.

The free Fraud Detection Handbook is the most directly relevant domain curriculum: chapters 2 (problem), 3 (baseline), 4 (metrics), 5 (validation), 6 (imbalance). Treat it as a learning source, not permission to copy benchmark protocols without adapting to PaySim.
