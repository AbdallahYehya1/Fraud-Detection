# Seven-day release plan

**Updated 9 November 2026 — Abdallah Yehya**

**Confirmed constraints:** target a working release within one week; keep a version that works without paid services, including local AI inference.

The release target is a focused portfolio MVP: repeatable fraud evaluation, versioned scoring, recorded-transaction replay, an analyst queue, case evidence, human dispositions, and a bounded local investigation assistant.

The earlier 84–120-hour estimate described the broader core roadmap. This sprint narrows that scope; it does not assume the same amount of work becomes faster by changing the deadline. Working estimate: **43–57 focused hours across seven days**, with existing Python/backend experience and the dataset already acquired. This is a planning estimate, not a completion guarantee. Day 7 includes integration and repair time.

Use relative days below. If implementation begins on 9 November, the target demonstration is 15 November 2026.

## Scope to ship

- Canonical PaySim v2; its original archive, provenance and initial full-file audit are already available.
- Frozen chronological partitions and explicit prohibited-feature checks.
- Rules, seeded random ranking, logistic regression, and one CPU booster with a small search budget.
- A small initial recipient-history feature set, supported by measured coverage and strictly earlier steps.
- AP, review-capacity metrics, false-alert workload, and simulator-artifact diagnostics on the frozen population.
- One scoring service, one local database, one replay command, and three UI views: overview, queue, and case detail.
- Human case decisions, notes, optimistic update checks, and append-only audit events.
- A local AI assistant with a small read-only evidence tool set, source references, and an independent holdout evaluation.
- Reproducible setup, data/model cards, a results report, and a short demonstration recording.

## Day 1 — Freeze the contract and check local AI feasibility

**Estimate: 6–8 hours.**

Finish non-finite-value checks, document duplicate semantics, and measure recipient-history coverage by time/type/class. Freeze split boundaries and feature/time rules before fitting.

Run a small local-inference smoke test early: load a candidate model, complete a short grounded summary, exercise a typed read-only tool, and measure memory and latency. Stop model training during this test. Do not spend the day comparing LLMs.

The computer reports approximately 15.8 GiB physical RAM; only about 2.7 GiB was available during the planning check. This supports checking the actual workload rather than promising a model will fit alongside every development process.

**Exit:** frozen data contract, documented data limitations, and evidence that the proposed free inference path works—or a clearly identified hardware/integration issue to resolve before the assistant milestone.

## Day 2 — Build the evaluation before tuning

**Estimate: 7–9 hours.**

Implement the all-negative sanity reference, native policy comparator, amount/type rule, seeded random daily ranking, and logistic regression. Compute AP, precision/recall at daily capacity, false alerts per 1,000 legitimate records, and per-type/time results.

Keep native policy workload separate from top-K ranking. Include mixed-hour diagnostics because 320 observed hours contain only positives. Define candidate population, daily boundaries, deterministic tie handling, and partial-day treatment.

**Exit:** one reproducible development report using validation only. No final test performance is inspected.

## Day 3 — Select and freeze the model

**Estimate: 7–9 hours.**

Add only a small supported recipient-history feature set, such as earlier-step count/amount in one window plus missing-history indicators. Compare one histogram-based booster with the baselines.

Start training experiments on a documented development subset when needed. Final validation and testing retain their natural prevalence and frozen populations. Keep searches bounded; a more complicated model is not a release requirement if it does not improve the comparison.

Freeze preprocessing, model, history initialization, and review policy; run the final evaluation. If implementation changes later invalidate the evaluation, document the rerun and avoid using test results for further tuning.

**Exit:** model artifact, exact feature/policy versions, final report, and documented limitations. Scores remain ranking scores; calibrated probabilities are deferred.

## Day 4 — Deliver scoring and reliable replay

**Estimate: 6–8 hours.**

Implement the minimal API and local persistence. The service computes features; clients cannot submit labels, forbidden balances, arbitrary history aggregates, or widened cutoffs.

Implement the recorded replay as a command rather than a separate orchestration service. Persist score-time vectors, model/policy versions, scoring step, and case-evidence cutoff.

Test a mid-hour interruption and resume. Completed-hour results, history progress, and checkpoints must be consistent. Day-end queue finalization is idempotent.

**Exit:** matching offline/API scores on fixtures and a replay that resumes without duplicate or changed cases.

## Day 5 — Make the analyst workflow usable

**Estimate: 6–8 hours.**

Build overview, queue, and case detail. Show the original transaction, available recipient history, computed facts, source IDs, and missing-information states.

Add human dispositions and case notes with audit events. Keep dataset truth in the evaluation boundary; it must not appear in investigation responses.

**Exit:** a transaction moves through replay → score → alert → case evidence → human disposition → audit.

## Day 6 — Add and evaluate the local assistant

**Estimate: 6–8 hours.**

Use the local model path tested on Day 1. Retain the planned thin agent module over the Python evidence service; test compatibility with the chosen local endpoint rather than assuming it from a shared protocol.

Limit the assistant to a few read-only tools and short tasks: summarize this case, retrieve eligible history, explain the available model evidence, and identify missing context.

Author approximately 20 compact evaluation cases for this MVP, separated into development and holdout groups. Cover normal summaries, wrong IDs, missing history, arithmetic facts, future-data requests, hidden-label requests, adversarial notes, and tool failure.

**Exit:** a genuine locally running assistant with measured source fidelity and failure handling. Every numeric statement agrees with trusted tool output; no observed hidden-label/future-data access or unauthorized mutation in the holdout tests.

A deterministic report remains available if inference fails. It keeps the workbench usable, but does not count as completing the AI milestone. Report an unresolved assistant issue honestly rather than labelling a template as an agent.

## Day 7 — Verify, document and record

**Estimate: 5–7 hours.**

Use this day for integration fixes, the meaningful leakage/replay tests, a fresh setup check, and measured service performance.

Write concise setup instructions and the data/model cards. Record a three-to-five-minute demonstration showing the complete analyst flow and one evidence-grounded assistant exchange. Public hosting is not required for this release.

**Exit:** a reviewable local portfolio MVP, reproducible results, and a clear record of any unresolved requirement. Completion depends on these gates, not the calendar alone.

## Free AI implementation path

Use local Ollama inference as the first candidate, with a compact model such as Qwen3 4B subject to the Day 1 test. The [publisher's model page](https://ollama.com/library/qwen3:4b) lists a roughly 2.5 GB quantized download and an Apache 2.0 licence. Actual runtime memory exceeds the model file size.

Ollama documents a [local compatible endpoint](https://docs.ollama.com/api/openai-compatibility) and [tool calling](https://docs.ollama.com/capabilities/tool-calling). Those capabilities establish a plausible integration route, not proof that a specific model/runtime combination is already tested in this project.

Use local inference only for the required free path. Model downloads, existing hardware, disk, electricity, and internet are still resources; there is no paid inference service dependency. A hosted free tier or trial credit is not a prerequisite.

If Qwen3 4B is too heavy or fails tool evaluation, select a smaller local candidate and test it against the same tasks. Keep prompts and retrieved context short, and run training/inference at separate times. Do not substitute a paid API silently.

## Keep after the seven-day release

- Independent ULB benchmark and any richer synthetic dataset.
- Arabic summaries and multilingual evaluation.
- Probability calibration and delayed-feedback research.
- More feature windows, large tuning searches, and additional model families.
- Public hosting, organizational accounts, and a larger administration interface.
- Expanded 30–50-case assistant research suite and more autonomous investigation.

## Learning during the sprint

Use short, task-specific revision alongside implementation. Prioritize precision/recall/AP, temporal leakage, model pipelines, SQL constraints/transactions, API validation, and evidence-based tool calling.

The [learning guide](Fraud_Detection_Data_and_Learning_Guide.md) includes free videos and exercises. Use the relevant lesson when a task exposes a gap; the sprint does not require completing full courses.

**First task:** complete the remaining data checks and freeze the feature/evaluation contract, while checking local AI feasibility early.
