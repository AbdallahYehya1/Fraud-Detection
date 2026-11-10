# Fraud investigation MVP

A portfolio MVP that scores recorded **synthetic** mobile-money transactions (PaySim v2),
prioritizes a limited analyst review queue, and assembles evidence for human review.
Everything runs locally with no paid service, including AI inference.

**Problem.** Analysts can review only a fixed number of transactions a day. The product ranks
recorded transactions, finalizes a daily top-K queue, shows the evidence available at review time
(including what is missing), records human decisions in an append-only audit log, and offers a
bounded local assistant that summarizes a case from read-only evidence tools.

**Results (synthetic test partition, run once):** at 100 reviews/day the frozen model found
1,189 of 4,250 positives (precision 73.5%, recall 28.0%, AP 0.335) versus 670 for an amount/type
rule and 115 for seeded random ranking. Many test hours contain only fraud-labelled rows, a simulator
artifact; in mixed-label hours alone it found 505 of 2,000 (AP 0.241). The replay and API reproduce
offline scores exactly. The local assistant passed 10 of 12 cases on each of two separate holdout sets.
On both, its answers contained no writes, label claims or unsupported numbers, and on the second set no
invalid citations of any form. Details: [docs/evaluation.md](docs/evaluation.md).

| document | contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | components, data boundaries, runtime |
| [docs/data_card.md](docs/data_card.md) | source, licence, fields used/excluded, measured quality, simulator artifacts |
| [docs/model_card.md](docs/model_card.md) | champion-v1, selection, final test, limitations |
| [docs/evaluation.md](docs/evaluation.md) | ranking, replay consistency, assistant evaluation, performance |
| [docs/demo_script.md](docs/demo_script.md) | 3–5 minute demonstration script |
| [docs/checkpoints](docs/checkpoints/) | daily checkpoints: commands run, results, failures, limitations |

**Recorded walkthrough:** [captioned demo](../outputs/Fraud_Detection_Demo.mp4) · [recording notes and limitations](../outputs/Fraud_Detection_Demo_Notes.md).

**Requirements:** Windows 11 (tested), Python 3.13, Node 22.9+, Docker Desktop, about 16 GB RAM.
The local assistant also needs Ollama 0.40.15 and `qwen3:4b` (~2.5 GB download). The full
quick start is under "Setup" and the sections that follow.

## Data

PaySim v2, E. A. Lopez-Rojas, A. Elmir and S. Axelsson, *PaySim: A financial mobile money
simulator for fraud detection*, EMSS 2016. Licence: CC BY-SA 4.0. The records are synthetic;
they are not real customer data and say nothing about any real bank or market.
The publisher instructs excluding all four balance columns from fraud prediction because
detected fraud was cancelled; this project excludes them and every derivative.

Raw data is never copied into this package. By default the app reads the planning workspace's
verified copies (`../outputs/data/PaySim_v2.zip`, `../work/data/raw/paysim-v2.csv`). Override with:

| variable | meaning |
|---|---|
| `FRAUDINV_RAW_ARCHIVE` | path to the original `PaySim_v2.zip` |
| `FRAUDINV_RAW_CSV` | path to the extracted CSV (created with `verify --extract` if missing) |
| `FRAUDINV_DATA_DIR` | generated Parquet/caches (default `./data`, git-ignored) |

## Setup (Windows, PowerShell)

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install --no-deps -e ".[dev]"
```

Pinned versions are in `pyproject.toml`; the full resolved set is in `requirements.lock`.
`python scripts/fresh_setup_check.py <empty-dir>` rebuilds everything in a clean copy and compares
the results with this checkout's reports.

## Commands

```powershell
.venv\Scripts\python -m fraudinv verify            # size + SHA-256 of archive and CSV
.venv\Scripts\python -m fraudinv ingest            # typed Parquet with source_row (≈7 s)
.venv\Scripts\python -m fraudinv audit             # Day 1 data-quality audit -> reports/day1/
.venv\Scripts\python -m fraudinv evaluate-dev      # Day 2 baselines, validation only -> reports/day2/
.venv\Scripts\python -m fraudinv features          # label-free recipient-history table (≈4 s)
.venv\Scripts\python -m fraudinv select            # Day 3 selection on validation -> reports/day3/
.venv\Scripts\python -m fraudinv freeze            # refit, verify, hash -> reports/frozen/selection.json
.venv\Scripts\python -m fraudinv final-test        # one-time test evaluation (refuses a second run)
.venv\Scripts\python -m pytest -q                  # tests (real-data gates skip if no Parquet)
.venv\Scripts\python -m fraudinv.ai_smoke          # local-inference smoke test (needs local Ollama)
```

## Database, replay and API

```powershell
.venv\Scripts\python -m fraudinv db-env                      # random local passwords -> .env (git-ignored)
docker compose --env-file .env up -d                         # postgres:18.4-alpine on 127.0.0.1:55432
.venv\Scripts\python -m fraudinv db-migrate                  # schema, roles, grants (idempotent)
.venv\Scripts\python -m fraudinv replay-create --run-id demo-test-d14-16 --first-step 356 --last-step 408
.venv\Scripts\python -m fraudinv replay-run --run-id demo-test-d14-16   # resumes from the committed cursor
.venv\Scripts\python -m fraudinv day4-check                  # real-data crash/resume + offline parity check
.venv\Scripts\python -m uvicorn fraudinv.api:app --host 127.0.0.1 --port 8765
```

### Analyst workbench (React/TypeScript)

```powershell
cd web; npm ci; npm run build; cd ..                         # Vite 6.4.5 build -> web/dist (Node 22.9+)
.venv\Scripts\python -m fraudinv analyst-add demo --name "Demo Analyst"   # token -> .tools/analyst-demo.token
.venv\Scripts\python -m fraudinv evaluate-run --run-id demo-test-d14-16   # evaluator-only aggregates
.venv\Scripts\python -m uvicorn fraudinv.api:app --host 127.0.0.1 --port 8765   # UI + API at http://127.0.0.1:8765
```

For UI development, run `npm run dev` in `web/` (port 5173, proxies `/api` to 8765). Sign in with the
token file's contents; it is a local demo credential, not production authentication.
Use `127.0.0.1` rather than `localhost`: on this machine `localhost` added about 2.3 s per new connection.

The serving role (`fraudinv_app`) has no access to the `truth` schema; labels are read only by
`fraudinv_eval` for offline evaluation. Port 8000 is used by another local service on this machine.

## Local AI (free, on-device)

Ollama 0.40.15 runs from `.tools/ollama/` with models in `.tools/ollama-models/` (both git-ignored),
bound to `127.0.0.1`. On this machine CUDA fails with NVIDIA driver 546.30, so CUDA is hidden and
Ollama uses its Vulkan GPU backend:

```bash
CUDA_VISIBLE_DEVICES=-1 OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/.tools/ollama-models" OLLAMA_CONTEXT_LENGTH=4096 ./.tools/ollama/ollama.exe serve
```

With the server running, the bounded assistant is available on each case page (signed in) and from the CLI:

```powershell
.venv\Scripts\python -m fraudinv assistant-ask demo-test-d14-16/test/d16/r010 "Summarize this case."
.venv\Scripts\python -m fraudinv assistant-eval --split dev       # development cases; may be rerun
.venv\Scripts\python -m fraudinv assistant-eval --freeze          # record prompt/tools/guard/model identity
.venv\Scripts\python -m fraudinv assistant-eval --split holdout   # once, only with the frozen identity
```

The assistant is read-only (read-only DB session, serving role without label access), bound to one case and
its evidence cutoff, and every answer passes a deterministic guard; see `docs/checkpoints/day-06.md`.

`qwen3:4b` always reasons. Leave thinking at its default so reasoning stays out of `content`.
The loaded model uses ~4.3 GB of host RAM, so stop the server before training.

## Contracts

* [config/split_protocol.yaml](config/split_protocol.yaml) — frozen whole-hour partitions
  (train 1–281, validation 282–355, test 356–743), simulation-day convention, partial-day
  capacity rule, history warm-up, seeds.
* [config/feature_contract.yaml](config/feature_contract.yaml) — allowed/forbidden inputs,
  units, candidate history features. Enforced by `fraudinv.contract`.
* Event ID = `PS2-<first 8 hex of CSV SHA-256>-<0-based data-row position>`, e.g.
  `PS2-16910f90-0000042`. It is a project identifier, not a bank transaction ID.

## Conventions

* Amounts are **simulation currency units**; steps are **relative simulation hours**. No
  calendar dates, currencies, devices or identities are inferred.
* History uses strictly earlier steps; rows inside one hour are simultaneous.
* `isFraud` is evaluator/training truth only; `isFlaggedFraud` is a policy comparator only.
* Generated reports live under `reports/`; bulk data, models, `.venv` and `.tools` are git-ignored.
