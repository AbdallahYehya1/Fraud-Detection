# Fraud Detection and Investigation Platform

**Council blueprint for Abdallah Yehya — 8 November 2026; execution constraints updated 9 November**

Build a reproducible fintech portfolio product that scores recorded mobile-money transactions, prioritizes a limited analyst review queue, and assembles evidence for human investigation.

**Status:** council planning complete; canonical PaySim v2 downloaded and its schema, counts, time coverage, and account recurrence profiled. The publisher's licence and balance warning were verified directly through its public API. No application or fraud model has been implemented or trained. Detailed findings are in [the measured data audit](PaySim_Data_Audit.json); [the original archive](data/PaySim_v2.zip) is ready locally.

**Confirmed execution constraints:** target a focused working MVP within seven days and keep the complete local version free of paid services, including local AI inference. The current computer reports approximately 15.8 GiB RAM. Exact daily availability and local model performance remain unconfirmed. The [seven-day sprint](Fraud_Detection_Seven_Day_Sprint.md) governs release scope and sequence; the broader architecture and extensions below remain a reference roadmap.

Read this blueprint with [the data and learning guide](Fraud_Detection_Data_and_Learning_Guide.md). The [implementation backlog](fraud-project-backlog.json) records task dependencies and completion criteria.

## 1. Council decision

Three specialist agents reviewed fraud operations, data/ML/evaluation, and engineering/AI/reliability. The lead consolidated scope, learning, delivery, and portfolio presentation.

The council recommends **PaySim first, an analyst workbench second, and a bounded AI assistant third**. Use ULB later as an independently trained real-data benchmark.

This is a recorded-transaction monitoring demonstration. Its strongest evidence will be reproducible evaluation, honest handling of simulator limitations, useful investigation screens, and reliable software.

The council identified four design constraints:

1. Exclude all four PaySim balance columns and their derivatives from the primary model. The publisher's current API description explicitly instructs this because detected fraudulent transactions are cancelled.
2. Hourly simulation steps do not establish transaction order inside an hour. Historical features use strictly earlier steps.
3. Build recipient-history features first. The acquired file supports strictly earlier-step sender history on only 0.146% of rows, compared with 56.466% for recipients. Rich sender histories and transfer-chain demonstrations are not supported by that finding alone.
4. The assistant cannot see the hidden fraud label, future records, or unrestricted database access.

PaySim's [creator repository](https://github.com/EdgarLopezPhD/PaySim) establishes its simulation origin and links the canonical release. The [ULB fraud handbook](https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_2_Background/FDS.html) provides the domain foundation for detection and subsequent review.

## 2. Business problem and user

**User:** a fraud analyst reviewing suspicious recorded transactions.

**Problem:** the transaction stream is much larger than the analyst's review capacity. The product must prioritize a manageable set and explain the available evidence.

**User story:** “Show me the most useful transactions to investigate within my review budget, let me inspect what supports each alert, and record my decision.”

The demonstrable outcome is a functioning prioritization and investigation workflow on named datasets. Actual fraud prevention, money recovered, Egyptian-market validity, AML detection, and real analyst productivity are separate questions that this dataset alone cannot establish.

Fraud, credit default, and AML are different tasks. This release concerns transaction fraud. Chargebacks, identity verification, lending decisions, device fingerprints, IP addresses, and customer documents are outside its data scope.

## 3. First release and optional extensions

**Required core**

- Verified dataset intake and an explicit feature contract.
- Reproducible chronological train/validation/test partitions.
- Transparent rules and logistic-regression baselines.
- One stronger CPU model, evaluated against the same baselines.
- Recorded-transaction replay with restart and duplicate handling.
- A typed scoring API with model and policy versions.
- Ranked alerts, a transaction detail screen, and human review cases.
- Evidence references, case notes, and an append-only application audit log.
- Evaluation report, setup instructions, and a short recorded demonstration.

**Current seven-day assistant scope:** a small locally running evidence assistant is included, subject to an early hardware/integration check and a compact independent holdout suite. Its outputs must meet the same source/label boundaries as the broader design below.

**Broader extensions after the seven-day release**

- Expanded autonomous investigation and larger assistant evaluation.
- English/Arabic summary comparison.
- Separate ULB training and evaluation.
- Calibration experiments, delayed-label scenarios, or a richer synthetic history dataset.
- Public deployment using a bounded synthetic sample.

Start with a modular application and one replay worker. Additional infrastructure needs a demonstrated bottleneck before adoption.

## 4. Data assets needed

**D1 — PaySim, primary engineering and modelling dataset.** Published sample: 6,362,620 rows, 11 columns, approximately 494 MB CSV, 8,213 fraud labels. The records are synthetic mobile-money transactions, not observed Egyptian customer data. [Canonical download](https://www.kaggle.com/datasets/ealaxi/paysim1); [published experiment documenting counts](https://www.mdpi.com/2227-7390/11/5/1184).

The local audit reproduced those counts. The archive is 186,385,561 bytes; the extracted CSV is 493,534,783 bytes. The publisher metadata identifies version 2 and CC BY-SA 4.0. See [data attribution and access](data/README.md).

**D2 — ULB/Worldline card transactions, optional second benchmark.** Published sample: 284,807 real anonymized transactions, 492 fraud cases, 31 columns, approximately 151 MB CSV. An [official TensorFlow tutorial](https://www.tensorflow.org/tutorials/structured_data/imbalanced_data) uses a [direct CSV mirror](https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv). The original [publisher card](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) remains the provenance and licence reference.

**D3 — Authored review guidance.** Write a short fictional demo policy defining queue capacity, escalation options, evidence standards, and missing-history treatment. Label it as project-authored guidance, not a real bank policy.

**D4 — Independently generated software fixtures.** Create small synthetic records for duplicate delivery, invalid input, missing history, step boundaries, unknown types, and replay recovery. Keep these distinct from model evaluation data.

**D5 — Case-summary evaluation set.** Author 30–50 evidence-based tasks after the evidence API exists. Keep development cases and holdout cases separate. Include ordinary summaries, insufficient context, label requests, future-data requests, contradictory notes, arithmetic traps, and tool failures.

**D6 — Analyst demo annotations.** Human review decisions, notes, and audit events generated while demonstrating the product. They are annotations, not automatically confirmed fraud labels or representative banking investigations.

No private bank integration or customer-data collection is needed for the core. The companion guide contains the field dictionary, acquisition checklist, source links, and licence-verification status.

## 5. Data intake gate

Before training, produce a dataset manifest and audit report containing:

- Canonical source, publisher, release/version, download date, citation, and current licence notice.
- Original filename, archive/file sizes, SHA-256, exact column names, and row count.
- Fraud/non-fraud counts, transaction types, and actual step range.
- Missing, non-finite, negative, zero, duplicate, and out-of-domain values.
- Volumes and fraud prevalence by step, simulation day, and transaction type.
- Sender/recipient cardinality, recurrence, pair recurrence, and cold-start proportions.
- Coverage of every proposed historical feature.
- Accepted/rejected records and documented reasons.

Keep raw data unchanged. A source-row identifier is assigned before sorting or filtering. Identical-looking transactions are investigated before deduplication; equality alone does not establish accidental duplication.

**Pass:** provenance is captured, the schema is understood, feature availability is documented, and usable chronological windows exist.

**Adapt:** if sender history is mostly absent, show the history that actually exists and focus on transaction and destination evidence. If a later richer-history dataset is adopted, report it as a separate synthetic experiment.

Dataset access and licence capture require actual source evidence. The current PaySim notice has now been verified; apply its attribution and share-alike requirements. Keep bulk raw archives outside Git.

**Completed during planning:** canonical acquisition, publisher licence/warning confirmation, checksum generation, schema/count/type/step profiling, missing-value and negative-amount checks, and exact sender/recipient recurrence measurements.

**Measured implications:** there are 6,353,307 distinct sender IDs; only 9,266 rows have strictly earlier-step sender history. Recipients have 2,722,362 distinct IDs, with 3,592,717 rows having earlier-step recipient history. These are same-role recurrence measures; they do not measure cross-role transfer chains or guarantee that history predicts fraud. All 8,213 positives are in TRANSFER or CASH_OUT in this sample. Keep whole-stream evaluation visible.

**Still open:** non-finite-value checks beyond missingness, duplicate-row semantics, historical-window feature coverage, source-unit conventions, and freezing the evaluation protocol. The audit is a useful initial profile, not a complete data-quality certification.

**Important simulator artifact:** 320 of 743 observed hours contain only positive-labelled rows. In the proposed test window, 195 of 388 hours are fraud-only and contain 2,250 of its 4,250 positives. This requires explicit mixed-hour diagnostics and ablations of time/traffic features. The main report still covers the complete frozen window; label-defined diagnostic subsets are evaluator-only and cannot become serving filters.

## 6. Feature and time contract

**Primary model inputs**

- Transaction type.
- Amount, with a train-defined transformation such as log1p.
- Relative-hour or recent traffic features only in documented ablations, because the observed pure-fraud hours can create shortcuts.
- Historical counts, amounts, novelty, or recipient activity only after the recurrence audit supports them.

**Excluded from primary inputs**

- oldbalanceOrg, newbalanceOrig, oldbalanceDest, newbalanceDest.
- Every ratio, delta, or condition derived from those balance fields.
- isFraud: training/evaluation target only.
- isFlaggedFraud: historical policy comparator only.
- Raw sender/recipient identifiers and source row number as predictors.
- Future/current-hour aggregates, full-file frequencies, and label-derived history.

Retain identifiers for joins and evidence retrieval. Any merchant/customer prefix feature needs a confirmed meaning and explicit approval in the feature contract.

Use history.step < transaction.step. Score an entire simulation hour using the previous-hour state, then update history. A stable ordering within an hour may support replay cursors, but cannot create additional historical information.

PaySim's currency is not established as EGP or USD. Display **simulation currency units**. Its time is a relative simulation hour; use simulation day labels derived from a documented convention, without fabricating real calendar dates.

Balance fields may remain in immutable raw storage. The first public case view should omit them to keep the evidence contract simple. A later raw-data diagnostic may display them with the simulator warning; such a diagnostic is separate from model reasons.

For a bounded replay beginning partway through the file, use a recorded warm-up/checkpoint containing all permitted earlier history, or explicitly choose a cold start. Evaluation and serving must use the same initialization rule. Unlabelled records may update history after their hour is scored; truth labels never enter that state.

## 7. Modelling and evaluation protocol

**Step A — Freeze temporal partitions.** Select whole-hour cutoffs near 60% / 20% / 20% of cumulative row volume, then inspect window composition. Volume across steps is uneven, so percentages of the step range are not a substitute for row-based boundaries. Keep all rows from one hour in one partition.

The raw-file profile proposes train steps 1–281 (3,820,599 rows; 3,193 positives), validation 282–355 (1,293,285; 770), and test 356–743 (1,248,736; 4,250). These are data-driven proposals, not a frozen protocol. Positive prevalence changes from approximately 0.0836% to 0.0595% to 0.3403%; test prevalence is about 5.72 times validation. Class-support metadata has already been inspected; model/policy performance has not. Freeze cutoffs before fitting, and do not move them to improve a result.

**Step B — Protect final testing.** Use training to fit preprocessing and model parameters. Use validation to choose features, model, and review policy. Before any final test result is inspected, record split bounds, feature version, model configuration, and policy. Report class support in each window.

**Step C — Add a development-time backtest.** Where class support permits, make an earlier train/validation pair inside the development period. This gives a check on temporal instability without repeatedly tuning against the final test.

**Step D — Fit a small model set.**

1. All-negative sanity check: establishes prevalence and the misleading high accuracy of ignoring rare fraud.
2. Existing isFlaggedFraud policy: report its native flagged set and workload separately; its binary output is not a natural top-K ranking. Any capacity-matched expansion or restriction needs a separate, disclosed policy.
3. Authored amount/type rule: tune only on validation.
4. Regularized logistic regression: preprocessing fitted on training only.
5. One histogram-based gradient-boosting model. Start with scikit-learn to limit dependencies; compare another CPU booster only for a concrete reason.

Also evaluate seeded random daily ranking at the same review capacities. Derive its label-independent ordering from a stable event-ID hash and seed. This contextualizes strong apparent results on days dominated by simulated fraud. Report prevalence as the constant-score AP reference.

Do not train a neural network before these comparisons. Class weighting and threshold selection are the first imbalance tools. Any resampling belongs inside training only, with natural prevalence preserved in validation and test. A training sample must be recorded with its selection rules and weights.

**Step E — Pick the review policy.** Compare daily review capacities such as 50, 100, and 200 transactions. These are hypothetical scenarios, not staffing claims. Daily top-K is an offline, end-of-day ranking policy. A replay can show scores as hours arrive and finalize the daily queue at the day boundary. Do not present that queue as an instantaneous authorization policy.

If a separate immediate threshold policy is explored, select it on validation and report it separately. Do not mix daily top-K and threshold metrics.

Define simulation day as floor((step - 1) / 24), publish partial-day treatment, and name the candidate population. Resolve equal scores by a stable, label-independent transaction-ID ordering. Finalize each day's top-K once, idempotently, at its last available step. Native policy alerts and capacity-ranked model alerts keep separate denominators.

**Primary measures**

- Average precision (AP), explicitly named.
- Precision and recall at the selected review capacity.
- False alerts per 1,000 legitimate transactions.
- Number of alerts, reviewed records, positives, and covered days.

**Supporting measures**

- ROC-AUC and confusion matrix.
- Per-type, amount-range, day, and cold-start results.
- Daily variability; temporal-block uncertainty estimates where enough days exist.
- Whole-stream results alongside any separately scoped TRANSFER/CASH_OUT experiment.
- Whole-window results alongside evaluator-only mixed-label-hour and pure-positive-hour diagnostics. These explain simulator artifacts; they are not alternative production populations.
- Optional deduplicated account-case metrics with the grouping rule disclosed.
- Batch runtime, peak memory, scoring throughput, and p50/p95 API latency on named hardware.

AP is not interchangeable with trapezoidal PR-AUC. A class-weighted score is a risk-ranking score. Optional calibration uses model/hyperparameter selection inside temporal training folds, the first chronological validation segment for calibration, a later validation segment for review-policy selection, and untouched final testing. Freeze the base model after calibration; refitting requires recalibration. Confirm adequate positive support in each slice. The uncalibrated ranking core does not need this extension. References: [metrics](https://scikit-learn.org/stable/modules/model_evaluation.html), [calibration](https://scikit-learn.org/stable/modules/calibration.html), [temporal validation](https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_5_ModelValidationAndSelection/ValidationStrategies.html).

**Metric example, not a project result:** 20 confirmed frauds among 100 reviewed transactions means 20% precision. If there were 40 frauds in the evaluated population, recall is 50%. Show both values and the actual counts.

If fewer than K candidates exist, report the actual number reviewed and name the denominator. On a day with no positive labels, recall is undefined; show it as not applicable, not zero or 100%.

Do not preselect a target such as “99% accuracy.” If the stronger model fails to improve on rules, publish the result, investigate the data and feature limitations, and preserve the honest comparison.

## 8. Economics and financial claims

Optional value coverage is:

sum of simulated fraud amounts selected / sum of simulated fraud amounts in the evaluated population.

This is retrospective amount coverage, not prevented loss. Transfer and cash-out records may refer to the same underlying money, so summing them does not establish unique loss.

An optional cost simulation may vary review cost, false-alert friction, missed-fraud exposure, and assumed recovery. Display every assumption and sensitivity range. Use simulation currency units and avoid presenting assumed inputs as a bank's actual economics.

## 9. Product flow and screens

1. **Overview:** dataset/model/policy versions, replay progress, queue size, and clearly separated evaluation results.
2. **Alert queue:** rank, transaction ID, simulation hour/day, amount, type, risk score, and review status.
3. **Case detail:** selected transaction, eligible history, source references, computed facts, and model associations.
4. **Review action:** new → in review → escalated or closed. Record a disposition such as “needs more information,” “suspicious in this demo,” or “no action,” with an analyst note.
5. **Audit history:** actor, action, case, prior/new state references, and application time.
6. **Evaluation view:** labeled historical results for a frozen run. Access is separate from investigation tools.

Facts, model associations, and analyst hypotheses must have different labels. Feature contributions explain model behaviour; they do not establish criminal intent.

Sparse history is a legitimate case state. Show “No earlier records available in this dataset” where that is the measured fact. Do not invent a customer profile to fill the screen.

## 10. Architecture and data boundaries

~~~mermaid
flowchart TD
  A[Canonical raw CSV and manifest] --> B[Audit and immutable row IDs]
  B --> C[Chronological split and eligible features]
  C --> D[Baseline and model training]
  D --> E[Frozen model, feature and policy versions]
  B --> F[Replay events without truth labels]
  E --> G[Python scoring and evidence service]
  F --> G
  G --> H[PostgreSQL: runs, scores, alerts and cases]
  H --> I[React analyst interface]
  H --> J[Optional read-only AI evidence tools]
  K[Separate evaluation truth] --> L[Offline evaluation report]
  E --> L
  H --> L
~~~

**Core stack**

- Python for ingestion, feature preparation, training, evaluation, and replay.
- DuckDB and Parquet for efficient local analytical data, where useful.
- scikit-learn for the initial preprocessing and model pipeline.
- FastAPI/Pydantic for typed service contracts.
- PostgreSQL for application state and audit events.
- React/TypeScript for the analyst interface, reusing your existing web skills.
- pytest, a locked environment, and Git for repeatability.

Notebook exploration should become repeatable commands or scripts before release. Full exploratory data need not be loaded into PostgreSQL; begin application replay with a bounded subset.

**Optional assistant:** a thin TypeScript eve module over the existing evidence API, following the applied agent-building guidance. Model training remains in Python. Verify the installed framework's documentation and model access when this milestone begins. [Official agent docs](https://eve.dev/docs/getting-started).

## 11. Storage and API contracts

Store dataset manifests; model/feature/policy versions; replay runs; transactions; scores; alerts; cases; and case audit events.

Every score records its transaction ID, run ID, model version, feature-contract version, policy version, and the actual small score-time feature vector. A hash supplements that vector rather than replacing it.

Persist scoring_step separately from case_evidence_cutoff_step. A day-end case may use facts available by review time, while the model's earlier score-time features remain frozen. Agent tools enforce the stored case-evidence cutoff; a caller cannot widen it.

Use a deterministic event key from dataset identity/hash plus original row position. A generated application ID must not be described as an original bank transaction identifier.

Keep evaluator truth in an offline file or separate database schema/role. Serving and assistant credentials must not read it. Construct response fields from an allowlist rather than serializing entire raw rows.

Suggested endpoints:

- GET /health and GET /model-info.
- POST /score.
- POST /replays, GET /replays/{id}, POST /replays/{id}/pause.
- GET /alerts, GET /cases/{id}, GET /transactions/{id}.
- GET /accounts/{id}/history with a server-enforced cutoff.
- POST /cases/{id}/disposition for an authenticated human.

POST /score accepts allowed transaction fields and a bound run identity. The service computes historical features from the run's recorded state. Reject client-supplied labels, balance inputs, precomputed historical aggregates, and arbitrary evidence cutoffs.

Retries use uniqueness constraints and conflict-safe writes. Commit completed-hour scoring results, history-state progress, and checkpoint atomically, or rebuild history deterministically before resuming. Day-end queue finalization is idempotent. An interrupted replay resumes without duplicate scores or cases and with identical features. A deliberate comparison with a different model gets a distinct run. Failed scoring remains visible as an error.

Keep original decimal precision in storage/display; choose a scale only after auditing source precision. Model matrices can use floating point independently of exact amount presentation.

## 12. Optional investigation assistant

The assistant's task is to gather allowed evidence and draft a case summary.

**Read-only tools**

- get_case_evidence(case_id).
- get_transaction(transaction_id).
- get_prior_account_history(account_id, before_step).
- get_model_evidence(score_id).
- get_review_guidance(policy_version).

The server binds every call to a permitted case/run and enforces evidence time, result limits, and field restrictions. Deterministic code calculates counts, sums, windows, percentiles, and model contributions.

**Structured output**

- Case and transaction IDs.
- Observed facts, each with evidence references.
- Model associations, identified as associations.
- Missing information.
- Investigation questions or next checks.
- A clear abstention where evidence is insufficient.

The assistant cannot retrieve truth labels, close cases, change balances, contact customers, execute arbitrary SQL, or browse arbitrary links. Analyst notes are untrusted case content. Constrain tool calls, output length, run duration, and model usage.

Evaluate development and holdout tasks separately for correct tool use, valid source IDs, numerical agreement with tools, unsupported claims, missing-data handling, and adversarial requests. Release goals are zero observed label/future-data leaks and unauthorized writes in the holdout suite, and reconciliation of all reported numeric facts. These are proposed gates, not achieved results or universal guarantees.

The core includes a deterministic evidence report. If no model access is available, that report remains useful and is labelled as a template rather than a live AI assistant.

## 13. Tests that protect the project

1. A forbidden field added to the feature set fails validation.
2. Injecting a future-step transaction does not change an earlier feature or case summary.
3. Reordering rows inside an hour does not change prior-hour features.
4. Training and serving transformations agree on a fixed fixture.
5. Interrupting replay halfway through an hour, then resuming, produces the same features, scores, unique cases, and day-end queue as an uninterrupted run.
6. An invalid amount, unknown type, nonexistent case, and stale case update have explicit outcomes.
7. Serving/agent roles cannot retrieve truth labels.
8. A complete fixture traverses replay → score → alert → evidence → human disposition → audit.
9. Optional assistant outputs are checked against a held-out evidence set.
10. A fresh local setup can reproduce the frozen report using the declared data/model versions.

Model artifacts must come from the project's trusted build process. Pin versions; arbitrary cross-version loading of serialized models is not a repeatability strategy. [scikit-learn persistence guidance](https://scikit-learn.org/stable/model_persistence.html).

## 14. Broader milestones and estimated effort

These ranges assume existing Python/backend experience and include focused revision of familiar material.

**M0 — Scope and provenance: 4–6 hours.** Freeze the user story, dataset links, source notices, units, scoring moment, and exclusions. Source acquisition and licence/warning verification are already complete. Exit: a one-page scope and manifest.

**M1 — Intake and data audit: 10–14 hours.** Acquire data, verify schema, profile temporal/type/class distributions and account recurrence, choose partition boundaries. Exit: reproducible audit, split manifest, feature contract, and an honest decision on history support.

**M2 — Baselines and evaluation: 14–20 hours.** Implement rules, seeded random ranking, logistic regression, AP, capacity metrics, and temporal/simulator-artifact diagnostics. Exit: validation report with counts and a working evaluation command.

**M3 — Features and champion model: 14–20 hours.** Add only supported past-step features; compare one booster; freeze the model/policy. Exit: versioned artifacts and a final untouched-test report.

**M4 — API and replay: 14–20 hours.** Serve scores, persist versions, replay records without labels, recover after interruption. Exit: retry-safe fixture and API/feature consistency checks.

**M5 — Analyst workbench: 16–22 hours.** Build queue, case evidence, human dispositions, and audit history. Exit: working end-to-end review flow with missing-history states.

**M6 — Release and portfolio: 12–18 hours.** Improve documentation, targeted tests, failure reporting, performance measurements, and demo recording. Exit: another person can reproduce and explain the core.

**Broader core total: approximately 84–120 hours.** This remains the estimate for the fuller scope above. The user now targets one week; the [seven-day sprint](Fraud_Detection_Seven_Day_Sprint.md) selects a narrower release estimated at 43–57 focused hours, including a bounded local assistant. The shorter deadline is not a guarantee or a claim that the full roadmap now takes less effort.

**M7 — Optional assistant: 16–24 hours.** Implement bounded tools, model access, and independent evidence evaluation.

**M8 — Optional ULB benchmark: 8–12 hours.** Separate intake/schema/model/report; compare methodology without claiming model transfer.

For the current execution sequence, follow the seven-day plan and its daily completion gates. Additional research and product features remain in the roadmap.

## 15. Superseding first-week plan

The following former intake-only week is retained as a task reference. The [seven-day release plan](Fraud_Detection_Seven_Day_Sprint.md) now replaces it as the active schedule.

1. **Scope, 1 hour:** write the user story, scoring moment, and supported claims.
2. **Domain revision, 2 hours:** read the handbook's system overview and learn precision, recall, AP, capacity, and label leakage.
3. **Source review, 1 hour:** review the already saved PaySim archive, licence, warning, manifest, and measured initial audit.
4. **Intake completion, 2–3 hours:** load a development sample, establish stable row IDs, and verify remaining non-finite/duplicate policies.
5. **Profile completion, 3–4 hours:** measure recipient-history coverage by window/type/class and document the observed pure-fraud-hour artifact.
6. **Contract, 1–2 hours:** document usable fields, time boundaries, and proposed split cutoffs.
7. **Checkpoint, 1 hour:** explain findings in a short readme; identify whether historical features are supported.

If PaySim access is delayed, use the official ULB mirror to practise intake and imbalanced metrics in a separate scratch experiment. Keep the project dataset decision explicit.

The first implementation deliverable is completion of the data audit and frozen feature/split contracts. Basic acquisition and profiling were completed during this planning session.

## 16. Learning strategy

Build while revising. Before model training, be able to explain class imbalance, precision/recall, temporal validation, and feature availability. Learn pipelines and tree models while building M2/M3; revise APIs, SQL, and testing while building M4/M5. Learn tool calling only for M7.

The companion guide gives a short prerequisite checklist, free video links, reading selections, and a practical exercise for each topic. Completing a long course before beginning this project is unnecessary.

## 17. Budget and hardware

**Core service budget: $0 using existing hardware.** Data files, open-source packages, local PostgreSQL, CPU training, replay, and the UI can run locally. There is no mandatory paid course, paid API, hosted database, or GPU.

**Hardware observation, 9 November:** the computer reports approximately 15.8 GiB physical RAM, with approximately 2.7 GiB available at the moment checked. Local assistant feasibility must be measured early. Training and inference can run at separate times. Several GB of disk are needed for dataset copies, environments and model files.

Measure runtime and RAM on the actual computer before full training or a model search. Begin with 100k–300k development rows; preserve the full frozen test population for final evaluation.

**Confirmed free path:** use local model inference for the assistant, with an early smoke test; see the sprint's verified local-endpoint references. No paid API, trial credit or hosted free quota is a dependency. Public hosting is deferred. If the model fails locally, keep the evidence report available and mark the AI gate unresolved; a template is not a completed assistant.

A local recording, source repository, and reproducible report are sufficient for the first portfolio release. Do not provision or buy services merely to satisfy the plan.

## 18. Portfolio evidence and completion

Ship:

- A readme with the business problem, scope, architecture, setup, and demo.
- Dataset and model cards, including synthetic-data disclosure and feature exclusions.
- A reproducible audit and frozen evaluation report.
- Versioned model/policy references and meaningful automated checks.
- A three-to-five-minute demonstration of replay, alert, evidence, and human disposition.
- A limitations section explaining sparse history, source units/time, and absent real-bank validation.
- Optional assistant evaluation and a separate ULB report.

**Interview discussion points:** why AP and capacity matter; how leakage was prevented; why rows in one hour are grouped; how missing account history changes the UI; how replay retries work; how the assistant cites evidence; what failed and what you changed.

Use measured results in the eventual CV description. Example structure after implementation: “Built a fraud-review platform over [verified count] synthetic transactions, compared [methods] under chronological validation, and delivered versioned scoring, replay, and analyst case review.” Fill brackets only with achieved facts.

**Core completion gate:** a fresh setup reproduces the report, serving and evaluation remain separated, the analyst workflow completes, and every public claim matches measured evidence.

**Next implementation task:** complete the remaining M1 checks and frozen feature/split contracts, alongside the Day 1 local-AI feasibility check. Follow the [seven-day sprint](Fraud_Detection_Seven_Day_Sprint.md).
