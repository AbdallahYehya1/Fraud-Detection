# Data and learning guide

**Companion to the Fraud Detection and Investigation Platform blueprint — 8 November 2026**

**Execution update, 9 November:** the active target is a seven-day MVP with no paid services, including local AI inference. Follow the [seven-day sprint](Fraud_Detection_Seven_Day_Sprint.md); use the longer learning path selectively during each implementation task.

This guide distinguishes published expectations, measured PaySim findings, and checks that remain open. The council acquired canonical PaySim version 2 and profiled the full file. ULB remains an optional online source and has not been downloaded here.

## 1. PaySim acquisition

**Canonical dataset:** [Synthetic Financial Datasets for Fraud Detection](https://www.kaggle.com/datasets/ealaxi/paysim1).

**Publisher context:** [creator's simulator repository](https://github.com/EdgarLopezPhD/PaySim), [original EMSS paper](https://www.msc-les.org/proceedings/emss/2016/EMSS2016_249.pdf).

Published sample expectations:

- 6,362,620 rows and 11 columns.
- 8,213 fraud labels and 6,354,407 non-fraud labels, approximately 0.129% positive.
- Approximately 494 MB uncompressed CSV; archive size and memory usage differ.
- Common filename: PS_20174392719_1491204439457_log.csv.
- Relative hourly steps across roughly one simulated month. Measure actual min/max: public prose and observed sample descriptions differ around 743/744.

These counts were reproduced from the acquired file. Counts are also documented by a [published modelling experiment](https://www.mdpi.com/2227-7390/11/5/1184). The measured audit and checksums are saved in [PaySim_Data_Audit.json](PaySim_Data_Audit.json).

**Access:** [the publisher's original version-2 archive is saved locally](data/PaySim_v2.zip), with [attribution](data/README.md). The council downloaded it directly from the public Kaggle versioned endpoint without credentials. Web UI access can differ. The canonical dataset page remains the source of truth for future versions.

**Rights and source notices:** the canonical [Kaggle metadata API](https://www.kaggle.com/api/v1/datasets/view/ealaxi/paysim1) directly confirmed CC BY-SA 4.0, current version 2, and the creator's field warning. A metadata summary is preserved in [PaySim_Source_Manifest.json](PaySim_Source_Manifest.json). The simulator repository's GPL-3.0 applies to its code and is a separate notice.

The publisher description explicitly instructs excluding all four balance columns because detected fraudulent transactions are cancelled. The primary model excludes these fields and every derivative.

Store the raw archive unchanged. Compute a SHA-256; record bytes, retrieval date, version and schema. Preserve metadata in the repository and keep bulk raw files and authentication credentials out of it. Before redistributing any source rows, resolve the current source terms.

## 2. PaySim dictionary and use

- **step:** relative simulation hour. Used for chronology; never converted into an asserted real timestamp.
- **type:** CASH_IN, CASH_OUT, DEBIT, PAYMENT, or TRANSFER, subject to exact file verification. Primary categorical predictor.
- **amount:** amount in unspecified simulation currency units. Eligible predictor; validate sign and finiteness.
- **nameOrig:** opaque synthetic sender reference. Lookup/history key, excluded as a raw predictor.
- **nameDest:** opaque synthetic recipient reference. Lookup/history key, excluded as a raw predictor.
- **oldbalanceOrg:** raw simulator sender balance field. Excluded from core prediction.
- **newbalanceOrig:** raw simulator sender balance field. Excluded from core prediction.
- **oldbalanceDest:** raw simulator recipient balance field. Excluded from core prediction.
- **newbalanceDest:** raw simulator recipient balance field. Excluded from core prediction.
- **isFraud:** binary supervised target; evaluator/training access only.
- **isFlaggedFraud:** existing simulator policy flag; comparator only, not a model input or verified fraud label.

All balance-derived variables are excluded too. A zero in a merchant-related field can reflect unavailable information; its meaning must be profiled.

Create a project event ID from immutable dataset identity and original row position. Preserve the mapping before filtering/sorting.

The full-file audit found strictly earlier-step sender history for only 9,266 transactions (0.146%), versus recipient history for 3,592,717 (56.466%). Focus candidate features on recipient activity and missing-history indicators. These measurements concern recurrence in the same sender or recipient role, not proven money-transfer chains. Compute window-specific coverage and validation benefit before selecting features.

The initial audit also found 320 hours containing only positive-labelled records. Such simulator activity patterns may make time/traffic features appear more powerful than they would be in a real service. Add mixed-hour diagnostics, seeded random capacity baselines, and explicit feature ablations. Keep all label-based subsets inside evaluation, never inside live feature selection or the assistant's evidence.

## 3. ULB second benchmark

**Original source:** [ULB/Worldline Credit Card Fraud Detection](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud).

**Verified no-login route:** the [official TensorFlow imbalanced-data tutorial](https://www.tensorflow.org/tutorials/structured_data/imbalanced_data) uses [this direct CSV](https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv).

Published expectations:

- 284,807 real anonymized card transactions; 492 positives.
- Two days in September 2013, European cardholders.
- Approximately 151 MB CSV.
- Time, Amount, V1–V28, and Class: 31 columns.

The source lists Open Database terms for the database and Database Contents terms for contents. Preserve exact notices at intake; the TensorFlow mirror does not replace original terms.

V1–V28 do not have published ordinary business meanings. Do not turn them into claims about merchant location, devices, or customer intent. Fit a separate model with separate temporal partitions and report. This is a second benchmark for the engineering/evaluation method; it does not prove that a PaySim model transfers to real card transactions.

Use the TensorFlow page as a learning and download source. Its instructional random split is not the project's temporal evaluation design.

## 4. Project-authored data

**Demo policy:** review capacities, queue ordering, case statuses, escalation definitions, and evidence rules. Version it and label it fictional.

**Software fixtures:** independently generated data for invalid rows, duplicated events, timestamp/step boundaries, missing history, model errors, and replay interruption.

**Assistant tasks:** approximately 30–50 authored questions with allowed evidence IDs and expected factual constraints. Development and holdout sets remain separate.

**Review annotations:** simulated case notes/dispositions. Store who created them and when; keep them separate from source fraud truth.

**Experiment manifests:** code/version, package lock, seeds, dataset hash, split boundaries, sampling, accepted feature names, calibration method if used, model hash and policy.

## 5. Minimum intake report

Answer these questions before modelling:

1. Does the downloaded archive match the intended publisher and release?
2. What do licence and warning notices actually say?
3. Do rows, columns, labels, types, bytes, and step range match expectations?
4. What is the fraud prevalence for each type and time block?
5. Are there missing, non-finite, malformed, or unusual values?
6. How many sender/recipient IDs recur, and how many transactions have usable earlier-step history?
7. Are duplicate rows accidental duplicates or legitimate identical observations?
8. Where can whole-hour chronological cutoffs be placed with enough class support?
9. Which proposed features are known at scoring time and independent of outcomes?
10. What cannot this dataset support?

Save the report, the query/script that produces it, and a manifest. A screenshot alone is not reproducible.

## 6. Skills to have before training

**Python and tabular data:** load files, select types, group records, handle missing data, join by key, write Parquet, and use configuration/seeds. Exercise: reproduce all expected counts with one repeatable command.

**Fraud vocabulary:** mobile-money flow, transaction alert versus account case, false alert, confirmation delay, review capacity, and fraud versus credit default. Exercise: explain the product to a fraud analyst in five sentences.

**Classification:** train/validation/test, logistic regression, regularization, class imbalance, precision, recall, false-positive rate, AP, and ROC-AUC. Exercise: calculate the confusion matrix and explain a capacity tradeoff.

**Leakage and time:** future information, outcome-affected features, training-only fitting, chronological splitting, and same-hour ambiguity. Exercise: introduce an intentionally forbidden column and make the feature contract reject it.

You already have relevant backend, SQL, and web-project experience from earlier work. Revise gaps rather than restarting a general software curriculum.

## 7. Learn during implementation

**M2/M3 — Modelling:** pipelines, class weighting, tree boosting, threshold/ranking policy, probability calibration, and reproducible experiments. Exercise: compare rules, logistic regression, and one booster on the same frozen validation population.

**M4 — Delivery:** typed API requests, input validation, model loading, stable IDs, SQL uniqueness constraints, transactions, history checkpoints, and train/serve consistency. Exercise: interrupt replay mid-hour and resume with identical features and no duplicated cases.

**M5/M6 — Product and verification:** accessible React forms, paginated queues, case state transitions, optimistic update versions, audit events, useful integration tests, and simple performance measurement. Exercise: another person follows the readme and reproduces one complete case.

**M7 — Optional AI:** tool calling, structured outputs, trusted calculations, source citations, missing evidence, injection-resistant boundaries, token budgets, and independent holdout evaluation. Exercise: a request for hidden labels is denied by tools and handled clearly in the output.

The project does not require training an LLM or learning every MLOps platform.

## 8. Free learning path with direct resources

Use short selections as needed, then implement the corresponding project task. There is no paid-course prerequisite.

**A. Domain and correct evaluation**

- [Practical Fraud Detection Handbook](https://fraud-detection-handbook.github.io/fraud-detection-handbook/): read Chapters 2–5 selectively, then Chapter 6 for imbalance.
- [Fraud-detection system overview](https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_2_Background/FDS.html).
- [Baseline implementation](https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_3_GettingStarted/BaselineModeling.html).
- [Review-capacity metrics](https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_4_PerformanceMetrics/TopKBased.html).
- [Temporal validation strategies](https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_5_ModelValidationAndSelection/ValidationStrategies.html).

**B. Video revision for ML**

- [StatQuest's official video index](https://statquest.org/video-index/): select Confusion Matrix; Sensitivity/Specificity/Precision/Recall; Logistic Regression; Decision Trees; Gradient Boosting; XGBoost Classification. It links the creator's YouTube lessons.
- [DataTalks.Club ML Zoomcamp video playlist](https://www.youtube.com/playlist?list=PL3MmuxUbc_hIhxl5Ji8t4O6lPAOpHaCLR), linked from the [official course repository](https://github.com/DataTalksClub/machine-learning-zoomcamp). Focus on classification, evaluation, trees, and deployment. Course completion is optional.

**C. Reliable implementation references**

- [scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html): fit transformations only on training data.
- [scikit-learn evaluation](https://scikit-learn.org/stable/modules/model_evaluation.html): match metric names and denominators.
- [Probability calibration](https://scikit-learn.org/stable/modules/calibration.html): distinguish risk scores from evaluated probabilities.
- [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/) and [testing](https://fastapi.tiangolo.com/tutorial/testing/): typed requests, responses, and end-to-end fixtures.
- [React learning guide](https://react.dev/learn): forms, state, lists, and component composition.

**D. Production revision and optional assistant**

- [DataTalks.Club MLOps video playlist](https://www.youtube.com/playlist?list=PL3MmuxUbc_hIUISrluw_A7wDSmfOhErJK), linked from the [official repository](https://github.com/DataTalksClub/mlops-zoomcamp). Select tracking, deployment, monitoring, and testing; extra cloud platforms are not prerequisites.
- [eve getting started](https://eve.dev/docs/getting-started), [tools](https://eve.dev/docs/tools), and [evals](https://eve.dev/docs/evals): optional assistant milestone only.

Suggested learning allocation is approximately 20–30% of each milestone's time when revising familiar concepts. If core classification concepts are new, extend the plan rather than skipping the practical exercises.

## 9. Questions you should be able to answer in an interview

1. What makes this fraud problem different from credit risk or AML?
2. Why can a very high accuracy be unhelpful on this dataset?
3. Why did you exclude all four balances?
4. Why does one simulation hour belong entirely to one split?
5. What happens when an account has no earlier history?
6. Why did you choose this review capacity, and how do results change at another capacity?
7. Which model beat which baseline, on what exact population?
8. Is the output calibrated probability or a ranking score?
9. What can the assistant retrieve, and how do you test its statements?
10. How do you resume a replay without duplicates?
11. What does your ULB experiment establish, and what does it leave untested?
12. What results are simulated, and what would a fintech need to validate locally?

## 10. First implementation session

Complete the following before building the dashboard:

- [x] Confirm a seven-day MVP target and a complete local version with no paid services.
- [ ] Check RAM and free disk; choose a development sample accordingly.
- [x] Open the canonical PaySim release and capture its current source notice.
- [x] Download and preserve the raw archive; compute its SHA-256.
- [x] Read the header and verify initial field domains.
- [x] Produce full-file basic counts and recurrence summaries.
- [ ] Write the feature exclusion list and strict earlier-step rule.
- [ ] Record proposed chronological split boundaries.

**Immediate output:** a reproducible data audit and a source/version manifest. Performance claims begin only after the evaluation protocol is frozen and run.

**Local AI addition:** [Ollama local endpoint](https://docs.ollama.com/api/openai-compatibility), [tool calling](https://docs.ollama.com/capabilities/tool-calling), and a candidate [Qwen3 4B model](https://ollama.com/library/qwen3:4b). Test memory, latency, agent-runtime compatibility, and evidence fidelity early. Free local inference is the required path; cloud trial quotas are not a dependency.
