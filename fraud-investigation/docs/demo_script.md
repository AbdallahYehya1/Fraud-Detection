# Demo script (3–5 minutes)

This script uses only existing features and supported claims. The captioned recording is produced from the real local browser workflow; see the recording follow-up in the Day 7 checkpoint for the delivered file and verification.

## Before recording

```powershell
docker compose --env-file .env up -d
$env:CUDA_VISIBLE_DEVICES="-1"; $env:OLLAMA_HOST="127.0.0.1:11434"; $env:OLLAMA_MODELS="$PWD\.tools\ollama-models"; .\.tools\ollama\ollama.exe serve   # separate terminal
.venv\Scripts\python -m uvicorn fraudinv.api:app --host 127.0.0.1 --port 8765
```

Open **http://127.0.0.1:8765** (use `127.0.0.1`, not `localhost`, on this machine) and sign in with the token in `.tools/analyst-demo.token`. Close memory-heavy apps first: the local model needs about 4.3 GB of RAM. Warm the model once by asking any question.

## Script

1. **Problem (20 s).** "Analysts can review only a limited number of transactions a day. This workbench ranks recorded transactions, builds a daily review queue and assembles evidence for a human decision. The data is synthetic PaySim v2 — no real customers."
2. **Overview (40 s).** Show the dataset, model and policy cards, then the replay run (873,533 transactions, steps 356–408, 221 cases). Point at the separated **Offline evaluation** panel: on the untouched test partition the model found 1,189 of 4,250 positives at 100 reviews per day, versus 670 for the amount/type rule. Mention the simulator caveat (fraud-only hours) and that the mixed-hours column is the conservative view.
3. **Queue (30 s).** Open day 15. Show the rank, score and the "no earlier record" tag. Note that capacity is fixed by policy and ties are broken deterministically.
4. **Case detail (60 s).** Open a "no earlier record" case (e.g. `d15 · r010`). Show:
   - the transaction in simulation units;
   - model evidence labelled "association, not proof";
   - computed facts F1–F6;
   - the explicit missing-information list;
   - recipient history before scoring vs after scoring (review-time);
   - "No earlier records available in this dataset."
5. **Assistant (60 s).** Ask "Summarize this case." While it runs, explain that it runs locally, read-only, bound to this case and its evidence cutoff. Numbers and evidence references are checked by the deterministic guard; wording still needs human review. Show the cited answer and ref list. Identify the appended [System] scope line as system text, not model-generated competence.
6. **Decision and audit (40 s).** Start review, add a note, close with the disposition "needs more information". Show the audit entries, actor, prior/new state and version. This is a human demonstration decision, not confirmation of fraud.
7. **Close (20 s).** "The workflow is reproducible: frozen splits and features, a one-time test evaluation, replay matching offline scores, and 101 passing automated tests. The fresh assistant holdout remains 10/12. Its two failures and the short-note-paraphrase limitation are documented; a small evaluation does not establish universal safety."

For a recording, use a fresh demo case outside the saved assistant evaluation cases. Do not rerun the holdout or overwrite evaluation reports to obtain footage. Keep analyst credentials out of the recording.

## Claims to avoid

No real-world fraud prevention, savings, staffing, or accuracy figures beyond those in `docs/evaluation.md`. Don't call the template report AI output, and don't describe scores as probabilities.
