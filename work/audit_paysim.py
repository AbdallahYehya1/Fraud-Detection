"""Acquire no credentials; verify the already downloaded public PaySim archive."""
from pathlib import Path
import hashlib
import json
import shutil
import time
import zipfile
import gc
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
RAW = ROOT / "work" / "data" / "raw"
DATA_OUT = OUT / "data"
DATA_OUT.mkdir(parents=True, exist_ok=True)
archive = RAW / "paysim-v2.zip"
delivered_archive = DATA_OUT / "PaySim_v2.zip"
if archive.exists() and not delivered_archive.exists():
    assert archive.resolve().is_relative_to(ROOT.resolve())
    assert delivered_archive.resolve().is_relative_to(ROOT.resolve())
    shutil.move(str(archive), str(delivered_archive))
archive = delivered_archive
csv_path = RAW / "paysim-v2.csv"
started = time.perf_counter()

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

with zipfile.ZipFile(archive) as zf:
    csv_entries = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if len(csv_entries) != 1:
        raise ValueError(f"Expected one CSV; found {csv_entries}")
    original_name = csv_entries[0]
    if not csv_path.exists():
        with zf.open(original_name) as source, csv_path.open("wb") as target:
            shutil.copyfileobj(source, target, length=8 * 1024 * 1024)

expected = ["step", "type", "amount", "nameOrig", "oldbalanceOrg",
            "newbalanceOrig", "nameDest", "oldbalanceDest", "newbalanceDest",
            "isFraud", "isFlaggedFraud"]
header = list(pd.read_csv(csv_path, nrows=0).columns)
assert header == expected, header
step_frames = []
type_frames = []
row_count = positive_count = flag_count = 0
missing = {name: 0 for name in header}
negative_amount = 0
label_values = set()
flag_values = set()
minimum_amount, maximum_amount = float("inf"), float("-inf")
for chunk in pd.read_csv(csv_path, chunksize=250_000):
    row_count += len(chunk)
    positive_count += int(chunk["isFraud"].sum())
    flag_count += int(chunk["isFlaggedFraud"].sum())
    label_values.update(int(x) for x in chunk["isFraud"].unique())
    flag_values.update(int(x) for x in chunk["isFlaggedFraud"].unique())
    for field, count in chunk.isna().sum().items():
        missing[field] += int(count)
    negative_amount += int((chunk["amount"] < 0).sum())
    minimum_amount = min(minimum_amount, float(chunk["amount"].min()))
    maximum_amount = max(maximum_amount, float(chunk["amount"].max()))
    step_frames.append(chunk.groupby("step").agg(
        rows=("isFraud", "size"), positives=("isFraud", "sum"),
        policy_flagged=("isFlaggedFraud", "sum")))
    type_frames.append(chunk.groupby("type").agg(
        rows=("isFraud", "size"), positives=("isFraud", "sum"),
        policy_flagged=("isFlaggedFraud", "sum")))
    if row_count % 1_000_000 == 0:
        print(f"Profiled {row_count:,} rows", flush=True)
steps = pd.concat(step_frames).groupby(level=0).sum().sort_index()
types = pd.concat(type_frames).groupby(level=0).sum().sort_index()
cutoffs = [int(steps.index[(steps["rows"].cumsum() >= row_count * frac)][0])
           for frac in (0.6, 0.8)]
windows = {}
for name, low, high in (
    ("train_proposal", int(steps.index.min()), cutoffs[0]),
    ("validation_proposal", cutoffs[0] + 1, cutoffs[1]),
    ("test_proposal", cutoffs[1] + 1, int(steps.index.max())),
):
    block = steps.loc[(steps.index >= low) & (steps.index <= high)]
    n, p = int(block["rows"].sum()), int(block["positives"].sum())
    windows[name] = {"first_step": low, "last_step": high,
                    "rows": n, "positives": p,
                    "positive_fraction": p / n if n else None}

recurrence = {}
del chunk, step_frames, type_frames
gc.collect()
for role in ("nameOrig", "nameDest"):
    print(f"Auditing {role} recurrence", flush=True)
    ids = pd.read_csv(csv_path, usecols=["step", role],
                      dtype={"step": "int16", role: "str"})
    counts = ids[role].value_counts()
    first_steps = ids.groupby(role, sort=False)["step"].transform("min")
    prior_rows = int((ids["step"] > first_steps).sum())
    recurrence[role] = {
        "distinct_ids": int(len(counts)),
        "ids_with_multiple_rows": int((counts > 1).sum()),
        "rows_on_ids_with_multiple_rows": int(counts[counts > 1].sum()),
        "rows_with_strictly_earlier_step_history": prior_rows,
        "fraction_with_strictly_earlier_step_history": prior_rows / row_count,
    }
    del ids, counts, first_steps
    gc.collect()

result = {
    "audit_date_local": "2026-11-08",
    "status": "downloaded_and_profiled_no_model_training",
    "source_url": "https://www.kaggle.com/datasets/ealaxi/paysim1",
    "metadata_url": "https://www.kaggle.com/api/v1/datasets/view/ealaxi/paysim1",
    "publisher_version": 2,
    "publisher_license": "CC BY-SA 4.0",
    "original_csv_name": original_name,
    "archive_path": str(archive),
    "working_csv_path": str(csv_path),
    "archive_bytes": archive.stat().st_size,
    "csv_bytes": csv_path.stat().st_size,
    "archive_sha256": sha256(archive),
    "csv_sha256": sha256(csv_path),
    "columns": header,
    "rows": row_count,
    "positive_labels": positive_count,
    "negative_labels": row_count - positive_count,
    "positive_fraction": positive_count / row_count,
    "policy_flagged": flag_count,
    "label_values": sorted(label_values),
    "policy_flag_values": sorted(flag_values),
    "min_step": int(steps.index.min()),
    "max_step": int(steps.index.max()),
    "observed_steps": len(steps),
    "missing_values": missing,
    "negative_amount_rows": negative_amount,
    "min_amount": minimum_amount,
    "max_amount": maximum_amount,
    "by_type": {str(k): {str(c): int(v) for c, v in row.items()}
                for k, row in types.iterrows()},
    "by_step": [{"step": int(k), **{str(c): int(v) for c, v in row.items()}}
                for k, row in steps.iterrows()],
    "proposed_temporal_windows_not_yet_frozen": windows,
    "account_recurrence": recurrence,
    "limitations": [
        "Not a duplicate-row audit, trained benchmark, or local-bank validation.",
        "No within-hour event order is asserted.",
        "No non-finite numeric-value audit beyond missing-value checks was performed.",
        "Published license and balance warning confirmed from publisher metadata.",
        "Proposed split windows require development-protocol approval before training.",
    ],
    "elapsed_seconds": round(time.perf_counter() - started, 2),
}
(OUT / "PaySim_Data_Audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
summary = {k: result[k] for k in (
    "rows", "positive_labels", "positive_fraction", "csv_bytes", "min_step",
    "max_step", "by_type", "account_recurrence",
    "proposed_temporal_windows_not_yet_frozen", "elapsed_seconds")}
print(json.dumps(summary, indent=2), flush=True)
