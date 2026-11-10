# Fraud-risk SME findings

Research date: 8 November 2026. This is a planning assessment, not an audit of downloaded dataset files. Recommendations below are design choices unless marked as source findings.

## Recommended business scope

Build a **retrospective mobile-money fraud monitoring and investigation workbench**. The user is a fraud analyst reviewing a finite queue of suspicious, already recorded transactions. The system scores a chronological replay, ranks alerts, assembles related transaction evidence, and records a human review outcome.

Define scoring time before modelling. The first release should score an offline chronological replay of recorded transactions. Exclude **all four balance columns** (`oldbalanceOrg`, `newbalanceOrig`, `oldbalanceDest`, `newbalanceDest`) and every derivative from the primary model. This is the council's conservative simulator-artifact control; post-transaction timing does not make an artifact valid. Preserve those columns only in a separate investigation snapshot, clearly labelled as simulator-recorded balances, with no assertion that they are reliable evidence of criminal conduct. A creator warning to exclude all four is quoted by multiple independent projects, but direct Kaggle card rendering was unavailable in this SME's checks, so verify and archive the primary wording at data intake. Treat `isFlaggedFraud` as a separate existing-rule comparator, not as an ordinary input in the primary new model. Hide `isFraud` from scoring and agent tools.

This scope is consistent with the ULB handbook's distinction between authorization controls, subsequent model scoring, and human investigation [S2]. It does not establish live payment blocking, prevented fraud losses, local-bank validity, or actual fraud-team effectiveness.

## Data-supported claims and limits

The PaySim authors describe simulation calibrated to aggregates of a real African mobile-money service. They model CASH_IN, CASH_OUT, DEBIT, PAYMENT, and TRANSFER; the original paper describes one-hour simulator steps across roughly one month [S1]. Its public creator repository identifies the simulator and links the Kaggle dataset [S5].

Suitable claims: reproducible scoring on a named synthetic dataset; chronological evaluation; review-capacity comparisons; a functioning evidence/review interface; measured model-serving and assistant behavior.

Unsupported claims: observed Egyptian customer behaviour; Egyptian-pound amounts unless presented as an explicitly hypothetical UI scenario; AML effectiveness; chargeback prediction; verified customer identity or account takeover; creditworthiness; actual money recovered or loss prevented. Those outcomes require additional data.

Before design is frozen, audit fraud prevalence by step/type, missing-value conventions, merchant balance fields, account repetition, duplicate records, and whether labels or balance mechanics create shortcuts. Never turn a zero or absent balance into a confident fraud explanation without evidence that its meaning is known.

PaySim has no verified exact order inside an hourly step. Build history features from strictly earlier steps. If the UI imposes an order within a step, label it as a replay ordering choice; it must not enable same-hour hindsight in features. Audit how often sender and recipient IDs recur before promising account-history features or transfer-to-cashout tracing. A sparse case should explicitly display the history that exists. Do not fabricate additional transactions or infer that an absent link proves no fraud. ULB should be a later independent benchmark with its own schema, model, and report, not rows appended to PaySim or a claim that a PaySim model generalizes to real card data.

PaySim remains a reasonable first engineering dataset even if customer histories are sparse, provided the workbench focuses on individual alerts and available evidence. If the product requires rich histories, a gated alternative is the ULB handbook's published transaction simulator [S6]. It explicitly models recurring customer and terminal identifiers, timestamps, amounts, and time-dependent fraud scenarios. Use it as a separately reported synthetic dataset; do not silently add its histories to PaySim.

## Evaluation that resembles the operational problem

Report precision, recall, and average precision on the untouched future period; overall accuracy is a weak headline for rare fraud. Add transaction-level precision/recall at daily capacities such as 50, 100, and 200 reviews. These capacities are proposed scenarios, not observed staffing requirements. ULB's handbook defines daily precision top-k in terms of investigator capacity and explains why repeated transactions from the same account can distort workload [S3].

Evaluate a second queue grouped by sender account, with a documented score aggregation rule and maximum cases per day. Do not compare transaction precision with account precision as if they were the same metric. Report daily variation, the number of positive examples, and precision/recall per transaction type and amount range. If limiting modelling to TRANSFER/CASH_OUT is justified by the downloaded file, retain a whole-stream report so the easy exclusion of other types is visible.

A retrospective fraud-amount coverage metric can be `sum(amount for fraud records selected) / sum(amount for fraud records)`. It is a flagged-value proxy, not recoverable loss. Linked transfer and cash-out events may represent the same underlying money and must not be added together as unique loss without an explicitly defined linkage method.

For an optional economics scenario, use transparent assumed cost of review and assumed uncovered fraud exposure, show multiple settings, and label outputs simulated. Do not infer a real bank's false-positive cost or recovery rate from PaySim.

Select model, threshold, and review policy using validation only, then lock the test period. Train on past records and document assumed label availability; a delayed-feedback replay can be a later sensitivity test. The ULB handbook explains chronological blocks, label delays, and concept drift [S4].

## Investigator workflow and assistant contract

1. Analyst opens a ranked alert queue showing transaction ID, score, amount, type, and scoring/model version.
2. Case view shows the original transaction, prior-step account history, linked records, and deterministic reason codes. Distinguish observed facts, model associations, and hypotheses. Feature importance is not evidence of a criminal cause.
3. Assistant retrieves approved evidence by ID, produces a structured case summary, cites every factual claim, identifies missing context, and proposes an investigation question. It may abstain.
4. Analyst records open/in-review/escalated/closed outcomes with a note. Review outcomes are demo annotations; dataset labels remain a separate evaluator-only ground-truth field.
5. Every retrieval and review mutation has an audit entry. Human confirmation governs any proposed case change; this prototype need not contact customers or alter balances.

Suggested tools: `get_transaction`, `get_prior_account_history`, `get_related_transactions`, `get_model_evidence`, and `get_review_guidance`. Guidance must be clearly authored demo policy, not a purported bank policy. The tools exclude future records, hidden test labels, unrestricted SQL, and invented identity/location information. Agent access to labels would invalidate its evaluation.

Assistant acceptance tests should cover correct retrieval IDs, numeric fidelity, supported citations, missing data, tool failure, misleading user text, and abstention. Compare assistant summaries with deterministic case summaries on the same prepared cases. Claim time savings only after a documented controlled exercise, with participants and limitations reported.

## What the learner needs to know

Domain vocabulary: mobile-money flows, transaction versus account alerts, authorized versus recorded transactions, review capacity, false positives, fraud versus credit default versus AML, delayed confirmation, case resolution.

Evaluation concepts: label leakage, point-in-time correctness, rare classes, precision/recall and average precision, threshold selection, daily capacity, score calibration, validation versus final testing, and simulator artifacts.

Product concepts: a score is a prioritization signal; explanations require available evidence; human feedback is not automatically verified truth; operational decisions and model versions must be reproducible.

The valuable differentiators are the chronological data contract, capacity-aware evaluation, controlled evidence assistant, and reliable analyst workbench. A single model notebook does not demonstrate those operational capabilities. PaySim remains a good practical first dataset, provided the product is described precisely as a synthetic retrospective monitoring demonstration.

## Sources

- S1. PaySim authors' original EMSS 2016 paper: https://www.msc-les.org/proceedings/emss/2016/EMSS2016_249.pdf
- S2. ULB practical fraud-detection handbook, system layers: https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_2_Background/FDS.html
- S3. ULB handbook, precision top-k: https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_4_PerformanceMetrics/TopKBased.html
- S4. ULB handbook, validation strategies: https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_5_ModelValidationAndSelection/ValidationStrategies.html
- S5. PaySim creator repository: https://github.com/EdgarLopezPhD/PaySim
- S6. ULB handbook, transaction simulator: https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_3_GettingStarted/SimulatedDataset.html
