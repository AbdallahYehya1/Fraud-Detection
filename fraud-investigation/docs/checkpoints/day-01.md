# Day 1 checkpoint — data contract and local-AI feasibility

**Date:** 9 November 2026. **Scope:** backlog T01, T04, T05, T06, T23. No fraud model was trained or scored for Day 1.

## Outcome

| task | status | evidence |
|---|---|---|
| T01 Freeze product scope | complete | [README.md](../../README.md) (scope, units, supported claims), [config/feature_contract.yaml](../../config/feature_contract.yaml) `units` |
| T04 Data-quality checks | complete | [reports/day1/data_quality_audit.md](../../reports/day1/data_quality_audit.md) / `.json`, `src/fraudinv/audit.py` |
| T05 Recipient-history coverage | complete | same report, "Recipient-history coverage"; parity test `tests/test_data_snapshot.py` |
| T06 Feature contract and chronological protocol | complete (frozen) | [config/split_protocol.yaml](../../config/split_protocol.yaml), [config/feature_contract.yaml](../../config/feature_contract.yaml), `src/fraudinv/contract.py`, tests |
| T23 Local-AI feasibility | **partial** — local inference and typed tool calls work on both endpoints; one citation-fidelity failure; eve not yet run | [reports/day1/local_ai_smoke_qwen3_4b.json](../../reports/day1/local_ai_smoke_qwen3_4b.json), `src/fraudinv/ai_smoke.py`, "Local inference" below |

## What was built

- Python package `fraudinv` (src layout, Python 3.13.6, project-local `.venv`, pinned deps in `pyproject.toml`, resolved set in `requirements.lock`).
- `python -m fraudinv verify | ingest | audit` commands. Raw data stays outside the package; paths are configurable with `FRAUDINV_RAW_ARCHIVE`, `FRAUDINV_RAW_CSV`, `FRAUDINV_DATA_DIR`.
- Typed Parquet (`data/interim/paysim_v2_events.parquet`, git-ignored) with `source_row` = 0-based data-row position assigned while streaming in file order.
- Event ID: `PS2-16910f90-<7-digit source_row>` (dataset key + first 8 hex of CSV SHA-256 + row position).
- Reference history implementation (`fraudinv.history`): vectorized and incremental versions of the same strictly-earlier-step contract, integer-cent sums.

## Commands run and results

| command | result |
|---|---|
| `py -3.13 -m venv .venv` + `pip install -e ".[dev]"` | ok |
| `python -m fraudinv verify` | archive 186,385,561 B and CSV 493,534,783 B; both SHA-256 match the manifest |
| `python -m fraudinv audit` (first run) | ok, 25.4 s; exposed three defects in my own reporting (integer counts rendered as floats, decimals miscounted for scientific notation, peak-memory probe returned None) — fixed |
| `python -m fraudinv audit` (final) | ok, 19.6–22.9 s total; Parquet ingest 7.0 s; peak Python working set 1,573 MiB (DuckDB capped at 2 GB, 4 threads) |
| `python -m pytest -q` (Day 1 scope) | first run 2 failed / 41 passed: one wrong expected value in my test (24-step window), and one **real bug** — `recipient_history` aligned results by position instead of index label, so shuffled input got swapped values. Fixed; 43 passed, later 48 with AI grader tests |
| Ollama download (official GitHub release v0.40.15, `ollama-windows-amd64.zip`, 1,614,941,966 B) | downloaded to `.tools/downloads/`; SHA-256 `9ca74a7a…221c6` matches GitHub's published digest |
| Extract + `ollama.exe --version` | first denied by the session permission policy; run after your approval ("Yes, run it"). Client 0.40.15 |
| `ollama serve` (127.0.0.1 only, models in `.tools/ollama-models`, context 4096) + `ollama pull qwen3:4b` | ok; Q4_K_M, 2,497,293,931 B, digest `359d7dd4…74fae7`, capabilities completion/tools/thinking |
| `python -m fraudinv.ai_smoke` run 1 (CUDA) | **failed to load**: `CUDA error: device kernel image is invalid`, runner exit 0xc0000409 — consistent with driver 546.30 < documented 551.61 |
| run 1 (Vulkan, `CUDA_VISIBLE_DEVICES=-1`, `think:false`) | loaded 37/37 layers on the RTX 3060 via Vulkan. Reported 1/4 fail, but my grader was wrong: it graded reasoning text that leaked into `content`. Kept as `local_ai_smoke_qwen3_4b_run1_think_false.json` |
| run 2 (Vulkan, thinking at model default, stricter grader) | **3 of 4 passed**; wrong-ID check failed on an invalid citation (details below) |

## Measured data findings (full file, 6,362,620 rows)

- **Values/domains:** 0 NaN, 0 ±inf, 0 nulls, 0 unparseable numbers, 0 negative values in amount or any balance; 0 unknown types, 0 malformed account IDs, 0 self-transfers, steps 1–743 all observed, labels strictly 0/1.
- **Precision:** numbers ≥ 10,000,000 are written in Java scientific notation (5,650 amounts, e.g. `4.196370815E7`). After expanding exponents, every amount and balance has at most 2 decimal places → integer cents are exact.
- **Zero amounts:** 16 rows, all `CASH_OUT` and all labelled positive. Retained (amount ≥ 0 is in-domain); noted as a simulator artifact. No amount==0 feature is allowed.
- **Duplicates:** 0 exact duplicate rows across all 11 columns; 0 groups with identical non-label values and conflicting labels; 0 repeated (step, type, amount, sender, recipient). Positive TRANSFER/CASH_OUT rows share (step, amount) in 4,272 pairs but never share an account ID (TRANSFER recipient = CASH_OUT sender: 0) — no linkable chain.
- **Rejection policy:** no source rows are removed. Serving will reject rows with unknown type, non-finite/negative amount, malformed IDs or out-of-range step, with a reason code.
- **Policy flag:** 16 flagged, all labelled positive (3 train, 0 validation, 13 test).
- **Partition support (frozen):** train 1–281: 3,820,599 rows / 3,193 positives (0.084%); validation 282–355: 1,293,285 / 770 (0.060%); test 356–743: 1,248,736 / 4,250 (0.340%). Positives only in TRANSFER and CASH_OUT in every partition.
- **Recipient history (strictly earlier step):** 56.47% of all rows; 37.0% within 24 steps. Legitimate TRANSFER/CASH_OUT/CASH_IN/DEBIT: 84–92%. PAYMENT (merchant recipients): <0.1%. **Positive TRANSFER: 0.25% train, 0% validation, 0% test.** Positive CASH_OUT: 72–75%.
- **24-step window drifts:** coverage for legitimate rows falls 44.9% → 30.8% → 19.3% across partitions (late-period volume drops), so windowed counts are non-stationary. All-history coverage is stable (~56–57%).
- **Same-step-only recurrence** (would leak under naive counting): e.g. 32 of 1,587 positive train TRANSFERs. The contract excludes same-step rows.
- **Sender history:** 0.089% / 0.208% / 0.256% of rows by partition — excluded from v1 features.
- **Pure-positive hours (evaluator-only):** train 108 of 281 hours (1,174 positives), validation 17 of 74 (196), test 195 of 388 (2,250). They are concentrated in night hours (`(step-1) mod 24` = 2–7: 26–27 of 31 such hours each), so hour-of-day is ablation-only.
- **Cross-check:** DuckDB window counts equal the pandas reference on steps 1–48 (1,029,493 rows, 0 mismatches).

## Contract decisions

- Partitions kept exactly as proposed; whole-hour, contiguous, covering 1–743. Not moved.
- Cutoffs fall mid-day (281, 355), giving 5 partial (partition, day) segments; daily capacity is pro-rated `floor(K·hours/24 + 0.5)`, results reported with and without partial segments.
- History warm-up: features at step *s* use every unlabelled row with step < *s*, regardless of partition; replay starting mid-file uses the same full prior warm-up.
- Excluded predictors: all four balances and any feature whose declared inputs touch them; `isFraud`; `isFlaggedFraud`; raw `nameOrig`/`nameDest`; `source_row`; `event_id`; raw `step`; account prefixes; sender history (unsupported).
- The candidate recipient-history features were written into the contract **before** the audit was run. The audit's class-by-partition coverage (which the handoff requested) includes test-window class counts; feature *selection* used validation only.

## Tests (Day 1 scope: 43 at Day 1 close, plus 5 offline AI-grader tests)

- Forbidden fields rejected by name and by declared lineage (a neutrally named balance derivative fails) — 22 tests.
- Future record cannot alter earlier features; within-hour reordering (20 shuffles) cannot create history; 50 same-hour rows see no history; label flips don't change features; labels refused by the incremental state.
- Event IDs survive sorting/filtering and chunked assignment; tie-break key is label-independent.
- Partitions contiguous/whole-hour; safe extraction ignores a `../escape.csv` archive entry; checksum mismatch detected.
- Real-data gates (skip without Parquet): frozen partition counts; complete unique `source_row`.

## Local inference (T23) — runs locally; one open defect

Measured on 9 November 2026 with no paid or hosted service. The server was bound to `127.0.0.1` and the test refuses non-local URLs. Report: `reports/day1/local_ai_smoke_qwen3_4b.json`.

- **Machine:** 15.77 GiB RAM, i7-11800H, RTX 3060 Laptop (6 GiB VRAM), NVIDIA driver 546.30.
- **Runtime:** Ollama 0.40.15 standalone build in `.tools/ollama/` (SHA-256 verified; no installer, no autostart). Model `qwen3:4b`, Q4_K_M, digest `359d7dd4bcda…74fae7`, context 4096.
- **GPU path:** CUDA fails on this driver (`device kernel image is invalid`). Ollama's **Vulkan** backend works: 37/37 layers offloaded, 3.18 GB placed in VRAM. Updating the NVIDIA driver to ≥ 551.61 may enable CUDA; not tried.
- **Thinking control:** this model declares thinking values `[True]` only. `think:false` / `reasoning_effort:"none"` do not disable reasoning; they move it into `content`, ending with `</think>`. With thinking at the default, reasoning stays in a separate field (`thinking` natively, `reasoning` on `/v1`) and `content` is clean. The assistant must not request think-off for this model.

| check | result | latency | notes |
|---|---|---|---|
| warm load | ok | 11.8 s cold (9.9 s load); 1.5 s warm | ~66–70 output tokens/s |
| grounded summary (evidence in prompt) | **pass** | 22.8 s | 1,552 output tokens, mostly reasoning; numbers all supported; cites [E1], [E3] |
| typed tool call, native `/api/chat` | **pass** | 6.7 s call + 16.7 s answer | exactly one `get_case_evidence({"case_id":"CASE-FIX-001"})`; cites [E1] [E2] [E3]; no unsupported numbers |
| same, OpenAI-compatible `/v1/chat/completions` (eve route) | **pass** | 6.8 s + 16.4 s | arguments arrive as a JSON string and parse; `reasoning` field separated |
| wrong case ID (tool returns `case_not_found`) | **fail** | 4.7 s + 3.4 s | correctly says "CASE-FIX-999 was not found", invents no figures, but appends an invalid citation `[E1]` |

- **Answer quality:** the summaries never asserted fraud, kept the ranking-score caveat and stated the missing sender/device data. The invalid citation shows citations can't be trusted from the model alone. The Day 6 assistant needs a deterministic post-check that rejects or strips any ref not returned by a tool in that turn; the stricter grader in `ai_smoke.check_answer` already detects this.
- **Grader correction (disclosed):** the first Vulkan run counted the grounded summary as failed because my grader read leaked reasoning text. I changed the grader to score only the final answer, fail on any leaked reasoning, and fail on citations not backed by returned evidence. The last rule is stricter than the original wrong-ID criterion, and it is what turned that check into a fail. Both runs are kept.
- **Memory:** free RAM was 0.47–0.62 GiB while the model was loaded. The `llama-server` runner held 4.0–4.3 GB of host working set even with every layer on the GPU. Training and inference must not run together on this machine. After stopping the server, 4.61 GiB was free.
- **Leftover process:** a 0-MiB `llama-server` (PID 14104) from the failed CUDA load could not be stopped (access denied). It should clear on its own or at reboot.
- **eve adapter:** current docs describe the local route (`@ai-sdk/openai-compatible` → `http://localhost:11434/v1`), and the endpoint passed the tool-call test above. eve itself needs **Node.js ≥ 24** (installed: 22.9.0), so the adapter was not run. Whether the AI SDK provider handles the separate `reasoning` field is unverified.
- **Smaller-candidate test:** not run. `qwen3:4b` did not fail on capability; the open issue is citation fidelity, which the planned deterministic check handles. If RAM pressure becomes a blocker, `qwen3:1.7b` is the next candidate.

To start the server again:

```bash
CUDA_VISIBLE_DEVICES=-1 OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/.tools/ollama-models" OLLAMA_CONTEXT_LENGTH=4096 ./.tools/ollama/ollama.exe serve
```

## Remaining limitations

- Synthetic data only; no real-bank validity or savings claims.
- AI gate partially met: inference, tool calls and grounding work; citation fidelity on error results and the eve adapter are open for Day 6.
- No PostgreSQL is installed (Docker 29.8.0 is present); needed from Day 4.

## Next tasks (as written at Day 1 close)

T07/T08 (Day 2) and T09–T11 (Day 3) were unblocked and have since been completed — see [day-02.md](day-02.md) and [day-03.md](day-03.md). Still open: Day 4 T12–T14 (needs a PostgreSQL decision); T23 follow-ups (eve on Node 24, citation post-check) carry into Day 6.
