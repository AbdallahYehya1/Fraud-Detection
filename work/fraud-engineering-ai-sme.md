# Engineering and AI SME findings

Planning review, 8 November 2026. This is a proposed architecture and verification plan; no application, model benchmark, or raw-data audit was performed.

## Council recommendation

Build a useful local fraud review product before adding an LLM: offline data pipeline and model, deterministic transaction replay, scoring API, analyst queue, case evidence. Then add a bounded investigation assistant as an optional module. This keeps the core runnable for $0 and lets recruiters assess ML, backend, and product work separately from model-provider access.

The MVP is one Python application with modules, one local PostgreSQL database, one React/TypeScript interface, and dataset/model files. Local analytical files may be Parquet; the database stores replayed transactions, scores, cases, and audit events. Do not copy all exploratory data into the application database during the first milestone. A single-process replay worker is sufficient. Kafka, Kubernetes, a vector database, a feature-store service, and distributed microservices add little to the first demonstration.

## Scoring and evidence contract

Freeze a feature-availability definition before training. The council's revised primary experiment is offline recorded replay and analyst case prioritization, not live authorization. Exclude ALL FOUR original balance columns and balance-derived fields from the primary model: the dataset card warns that cancellation of detected fraud can affect these fields, including old balances. Current transaction type and amount are the minimal clean inputs; use hour information only in a documented experiment. Sender/recipient IDs support grouping and evidence retrieval rather than being treated as meaningful identity or ordinary numeric predictors. Audit actual sender recurrence before committing to account-history features; only then add summaries calculated from strictly earlier steps. `isFraud` is evaluator-only truth; `isFlaggedFraud` belongs to the policy baseline and must not leak into the model or assistant. The data/ML SME finalizes exact admissible fields.

PaySim provides hour steps, not real timestamps. Use `step` as the authentic time field. Any UI clock or calendar mapping is explicitly illustrative. Within-hour ordering is not established by the hour field. Safest first version: score a whole step using history from strictly earlier steps, then commit the whole step to feature history. Do not infer sequence precision from invented timestamps.

State what is observable in the replay record and what would be observable in a real service separately. A secondary balance-inclusive diagnostic can measure sensitivity to known synthetic artifacts, but it must remain visibly separate from the primary model. A late investigation may display source balance fields as flagged contextual evidence with the source warning; neither the assistant nor the analyst should treat those values as verified explanations of how the fraud occurred.

Use a stable synthetic event identifier derived from dataset version/file hash plus source row number. These are application identifiers, not purported original bank transaction IDs. Preserve original amount precision with Decimal/NUMERIC or integer scaled units after the source precision is verified. Keep the source's unspecified monetary unit; an Egyptian-language interface does not make the source amounts EGP. Floating-point model features are separate from exact display/accounting amounts.

## Small domain model

- `dataset_manifest`: source URL, version, downloaded filename, SHA-256, row count, schema version, licence reference, ingestion time, validation report.
- `model_versions`: model ID/hash, feature-contract version, training dataset hash and split bounds, code commit, environment lock, seeds, metrics reference, threshold-policy version. A prediction is a probability only if calibrated and evaluated as such; otherwise call it a risk score.
- `replay_runs`: run ID, dataset/model/policy versions, step interval, replay progress, started/stopped/error status.
- `transactions`: stable transaction ID, source row, step, type, amount, sender/recipient reference, admissible fields, run ID.
- `scores`: transaction/run/model/policy IDs, raw score, decision tier, score-time feature snapshot/hash, timestamp of application processing.
- `alerts` and `cases`: reason codes, evidence references, status, assignee, notes, analyst disposition. Use states such as new, reviewing, escalated, and closed. Analyst judgement is separate from hidden dataset truth.
- `case_events`: append-only record of actor, action, case, before/after state references, and time. Do not call a normal database audit log cryptographically immutable.
- Evaluation truth lives in offline files or a separate schema/role with no serving or agent access. Public case/evidence DTOs contain an explicit allowlist of fields; never serialize a raw training row.

## Minimal API and repeatability

- `GET /health`, `GET /model-info`.
- `POST /score`: validated typed transaction input; rejects unknown label fields and invalid amounts/types. Returns score, policy decision, model version, and reason/evidence IDs.
- `POST /replays`, `POST /replays/{id}/pause`, `GET /replays/{id}`: local replay control.
- `GET /alerts`, `GET /cases/{id}`, `GET /transactions/{id}`, `GET /accounts/{id}/history`: filtered, paginated, access-controlled reads with an enforced evidence cutoff.
- `POST /cases/{id}/disposition`: authenticated human action with input version/expected state to prevent accidental overwrite; records an audit event.

Add uniqueness constraints on run/event/model/policy combinations and use conflict-safe inserts for retries. Freeze a feature snapshot with each score. A replay restart on the same input must not create duplicate scores, alerts, or cases. A deliberate new model comparison uses a distinct run or model version. Mark scoring failures explicitly; do not silently score a broken record as low risk.

## Optional investigation assistant

The applicable build-agents skill requires new agents to use eve unless the user chooses another framework or an established agent stack is being modified. For this new optional module, use a thin TypeScript eve agent that calls the existing Python evidence API. Do not move ML training into the agent runtime. Verify the installed package docs before implementation; current official docs specify Node.js 24+ and model access.

Give the assistant only a small read-only tool set, for example `get_case_evidence`, `get_transaction`, `get_account_activity`, and `compare_to_reference_statistics`. Tools return typed records with source IDs, cutoff step, units, and data/model version. Trusted code calculates sums, counts, percentiles, windows, and model explanations. The assistant interprets those results and cites their IDs. Avoid unrestricted NL2SQL, shell/file tools, arbitrary URLs, account changes, payment actions, or case closure by the agent.

Each request has a tool-call budget, duration/token ceiling, bounded query ranges and a case/run identity enforced by the server. Treat analyst notes and external text as data, never authority. An unknown account, unavailable history, or tool timeout produces an explicit evidence gap. Feature contributions describe model behaviour, not causal proof of fraud. Never reveal hidden labels to help the assistant write a convincing case summary. English first; Arabic summaries can be evaluated later without retraining the underlying ML model.

If model access is unavailable, a deterministic report assembled from the same evidence remains usable; identify it as a report template rather than presenting it as an AI agent. The working core does not depend on an LLM.

## Meaningful tests and release gates

1. Data and feature checks: schema mismatch, labels or forbidden fields in serving input, future-step row introduced into a historical query, duplicate source IDs, missing/invalid data, same preprocessing at train and serve.
2. Replay checks: interrupt/restart, exact duplicate delivery, same event under another run/model, step-boundary state, failed-record reporting. Verify counts and case uniqueness, not just endpoint status codes.
3. API checks: malformed amounts/types, missing case, unauthorized mutation, pagination limits, stale disposition update, model version in every prediction. FastAPI supports TestClient/pytest for these flows.
4. Artifact reproducibility: dataset checksum, locked environment, split manifest, frozen threshold, model/feature version. Load only trusted model artifacts produced by the project; pickle/joblib can execute code, and scikit-learn does not support arbitrary cross-version loading.
5. End-to-end check: frozen replay fixture -> score -> alert -> evidence -> human disposition -> audit event. Compare case evidence to the exact input records.
6. Assistant evaluation: prepare roughly 30-50 authored tasks covering normal summaries, insufficient evidence, malformed tool arguments, unavailable account, future-data requests, label requests, adversarial notes, arithmetic traps, and tool failure. Keep development and holdout cases separate. Score tool choice, numeric accuracy, valid citations, unsupported assertions, abstention, time, and token cost. Proposed release gates: no label/future-data leakage and no unauthorized writes on the test suite; all reported numeric facts reconcile to tool output. These are goals to measure, not claimed results.

## Cost and delivery

- Core local data, CPU training, replay, API, DB, and UI: $0 in service fees using existing hardware, subject to dataset access/licence terms verified separately. Start with a sample and measure RAM/runtime before full training. No GPU required for baseline/tabular models.
- Optional LLM assistant: needs model access. Use the default Vercel AI Gateway route required by the skill; exact model, quota, prices, and authentication are checked when implemented. Do not promise unlimited free access or use a paid provider silently.
- Hosting: local recording and repository are enough for a reproducible portfolio milestone. A public sample deployment is a later decision; free hosting quotas and memory/sleep behaviour must be rechecked then. Public demos should expose a seeded synthetic sample with rate-limited reads and controlled/resettable mutations.
- Secrets stay server-side and outside git. The demo contains synthetic account references rather than real customer documents. Synthetic data does not remove the need to restrict case-write tools or protect model-provider credentials.

## Primary references checked

- FastAPI testing: https://fastapi.tiangolo.com/tutorial/testing/
- scikit-learn model persistence: https://scikit-learn.org/stable/model_persistence.html
- scikit-learn metrics: https://scikit-learn.org/stable/modules/model_evaluation.html
- PostgreSQL conflict handling: https://www.postgresql.org/docs/current/sql-insert.html
- Pydantic types and Decimal: https://docs.pydantic.dev/latest/api/standard_library_types/
- eve getting started: https://eve.dev/docs/getting-started
- eve typed tools: https://eve.dev/docs/tools
- eve evaluation support: https://eve.dev/docs/evals

The architecture, schema, test cases, and release targets above are council design recommendations, not requirements imposed by these products or evidence of implementation.
