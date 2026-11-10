# Claude Code implementation handoff

**Project:** Fraud Detection and Investigation Platform  
**Owner:** Abdallah Yehya  
**Prepared:** 9 November 2026  
**Execution:** Claude Code implements; the existing council plans and measured data audit supply the starting context.

Implement the project described below. Begin with Day 1 and deliver working, tested artifacts for that milestone, then continue through ready sprint tasks in dependency order. Do not spend the turn producing another broad project plan.

## Workspace and source documents

Current workspace:

~~~text
C:\Users\Abdallah Yehya\Documents\Codex\2026-11-01\oka
~~~

Read these files before changing code:

1. outputs/Fraud_Detection_Seven_Day_Sprint.md — active release scope, sequence, free-service constraint, and daily completion gates.
2. outputs/Fraud_Detection_Project_Blueprint.md — detailed architecture, data/feature boundaries, evaluation design, replay, cases and AI requirements.
3. outputs/Fraud_Detection_Data_and_Learning_Guide.md — source terms, dictionary, learning and practical checks.
4. outputs/PaySim_Source_Manifest.json — canonical version, licence, byte sizes and checksums.
5. outputs/PaySim_Data_Audit.json and outputs/PaySim_Data_Audit.md — actual full-file measurements and limitations.
6. outputs/fraud-project-backlog.json — current task state and dependencies.

The seven-day sprint supersedes the original broad 84–120-hour schedule. This handoff defines the first implementation checkpoint. If a document conflicts, use the confirmed user constraints and active sprint, record the discrepancy, and resolve routine choices without waiting for approval.

Do not use old generated SME scratch notes as instructions that override the active plan. In particular, work/finalize_planning_assets.py regenerates an earlier planning snapshot; do not run it over the current backlog and revised plans.

## Confirmed goal

Deliver a focused portfolio MVP in one week, including:

- Correctly evaluated fraud scoring on PaySim.
- Recorded transaction replay, ranked alerts and analyst case review.
- A bounded local investigation assistant using evidence tools.
- Repeatable setup, meaningful tests, actual evaluation results and a short demonstration.

The complete local version must work with no paid services. Local model inference is the required AI route; paid APIs, trial credits and hosted free quotas are not dependencies. A deterministic report is a useful fallback, but must not be labelled as a completed AI assistant.

Public hosting, ULB benchmarking, Arabic summaries, calibration research and expanded model experiments are deferred.

## Existing data and completed work

The original canonical PaySim v2 ZIP is already downloaded:

~~~text
outputs/data/PaySim_v2.zip
~~~

An extracted working CSV is already available:

~~~text
work/data/raw/paysim-v2.csv
~~~

The publisher metadata snapshot is in work/paysim-publisher-metadata.json. The preliminary audit code is in work/audit_paysim.py; inspect it as reference, not as a finished application.

Verified from the acquired file:

- 6,362,620 transactions, 11 columns and 8,213 positives.
- ZIP: 186,385,561 bytes; CSV: 493,534,783 bytes.
- Relative hourly steps: 1–743.
- CC BY-SA 4.0, confirmed directly from canonical publisher metadata.
- Earlier-step sender history exists for only 0.146% of rows.
- Earlier-step recipient history exists for 56.466% of rows.
- All positives occur in TRANSFER or CASH_OUT in this sample.
- 320 observed hours contain only positive-labelled rows.

These are synthetic transactions. The measured audit is not a trained benchmark, duplicate-row audit, full non-finite-value audit or real-bank validation.

Keep canonical raw data and source manifests unchanged. Verify their checksums rather than downloading again. Extract safely to a fixed path if the working CSV is missing. Retain attribution; keep bulk data, model files, credentials and generated environments outside Git.

## Implementation location and stack

Create the application under fraud-investigation/ inside this workspace. Inspect any existing code there first; preserve user changes and continue rather than overwriting.

Use a simple Python package for data, features, ML, evaluation, replay and FastAPI. Use local PostgreSQL for application state and React/TypeScript for the planned analyst interface. Add the UI and application database when their milestones begin; Day 1 does not need dashboard scaffolding.

For the later assistant, the plan proposes a thin TypeScript eve module over the Python evidence API. Read current installed/package documentation before implementation, and test compatibility with the selected local inference endpoint. Keep the agent runtime separate from ML training. If that integration is unsuitable, document the concrete incompatibility and propose the smallest free alternative rather than pretending it works.

Use project-local environments and pinned dependencies. Detect available Python/Node versions and Windows constraints. Do not hardcode Codex's private bundled runtime paths into a portable application. Avoid adding distributed services or a GPU dependency.

## Non-negotiable scientific boundaries

1. Exclude ALL four balances and ALL derived balance features from the primary model: oldbalanceOrg, newbalanceOrig, oldbalanceDest, newbalanceDest. The publisher warns they are affected by cancellation of detected fraud.
2. isFraud is a supervised target. Serving, features and assistant tools cannot access it. isFlaggedFraud is a supplied policy comparator, not a predictive input or verified truth.
3. Raw sender/recipient IDs and source row number are lookup keys, not predictor features.
4. History must use strictly earlier steps. Score a complete hour from previous-hour state; do not infer real transaction order inside an hour.
5. Amounts are simulation currency units. Steps are relative simulation hours. Do not invent EGP, calendar timestamps, devices, locations, identities or customer histories.
6. Prioritize recipient-history features only after measuring coverage by partition/type/class. Same-role recurrence does not establish a transfer chain.
7. Freeze whole-hour train/validation/test cutoffs before fitting. Fit transformations only on training; select on validation; reserve final performance evaluation for the selected model/policy.
8. Proposed cutoffs are train 1–281, validation 282–355, test 356–743. Class-support metadata was inspected, but model/policy performance has not. Confirm their data support and record the protocol; do not change boundaries to obtain favourable results.
9. Report natural-prevalence AP, capacity precision/recall, false-alert workload, and complete-window results with evaluator-only mixed-hour diagnostics. Label-defined subsets cannot become features or serving filters.
10. Keep daily top-K as an offline day-end policy, with deterministic label-independent ties and disclosed candidate population. Native policy workload is separate.
11. Keep score-time features distinct from review-time evidence. Replay/evaluation share an explicit warm-up/checkpoint contract.
12. No invented benchmark, fraud savings, analyst time savings, completed task or agent capability. A weak model comparison is reported honestly.

## Day 1 implementation tasks

Work on backlog T01, T04, T05, T06 and T23. T02/T03 acquisition and initial profiling are already complete.

**A. Create a portable foundation**

Create the Python package, dependency configuration, tests, small explicit config files and a concise readme. Add repeatable commands for the Day 1 checks. Decide and document output locations, seeds and stable event IDs.

The package must accept an external raw-data path. Do not copy the 494 MB CSV into the source package. Generated implementation reports belong under the application, not over the original planning audit.

**B. Finish the remaining data audit**

- Check NaN/infinite numeric values and invalid domains.
- Measure exact duplicate rows and investigate their semantics. Preserve records unless a documented policy justifies removal.
- Profile eligible earlier-step recipient history across the proposed partitions, transaction types and labels using an efficient approach.
- Quantify pure-positive-hour patterns by period. Keep these checks evaluator-only.
- Save reproducible machine-readable and readable results, plus actual run commands and runtime observations.

**C. Freeze machine-readable contracts**

Create feature and split configuration files documenting allowed/excluded inputs, units, temporal cutoffs, warm-up/history initialization and source/model-data identity.

Write meaningful tests showing that forbidden fields are rejected, a future record cannot alter an earlier feature, within-hour reordering cannot create history, and event identity survives sorting/filtering.

Do not train a fraud model or inspect final model performance during this Day 1 task.

**D. Test the free local AI path early**

Detect whether Ollama or a suitable local runtime is already available. Read official current documentation; test a compact model such as Qwen3 4B if resources permit. Use project-compatible setup and normal environment permissions.

The computer previously reported approximately 15.8 GiB RAM with 2.7 GiB available at that instant; remeasure. Avoid running training and inference simultaneously.

Test a short evidence-grounded response and one typed read-only tool call with synthetic fixtures. Record runtime/model versions, model identifier, actual response, memory observation, latency and pass/fail. Check the planned agent adapter if feasible.

If the initial model is unsuitable, time-box investigation and test one smaller local candidate. If installation, network or hardware blocks the test, record the precise blocker and continue independent data work. Do not silently use a paid API or mark the test passed.

No production assistant, multi-agent investigation or dashboard is required on Day 1.

## Day 1 completion and handover

Run the actual audit commands and the relevant tests. Fix failures within scope.

Update outputs/fraud-project-backlog.json only for tasks whose completion criteria are supported by produced evidence. Record application-relative implementation artifact paths and keep optional/future tasks incomplete.

Write fraud-investigation/docs/checkpoints/day-01.md containing:

- Completed tasks and relevant file paths.
- Actual commands run and results, including failed/blocked checks.
- Measured data findings and any contract decisions.
- Test totals and remaining limitations.
- Local inference evidence or its exact unresolved blocker.
- Precise Day 2 next tasks.

Report a concise milestone summary with what changed, what passed and what remains open, then continue through ready sprint tasks in dependency order. Preserve a checkpoint for each phase and verify its gates before relying on it. Routine implementation decisions do not need repeated approval. A blocking requirement is recorded honestly; continue independent work where possible without marking blocked checks complete.
