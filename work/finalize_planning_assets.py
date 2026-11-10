from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
audit_path = OUT / "PaySim_Data_Audit.json"
audit = json.loads(audit_path.read_text(encoding="utf-8"))
metadata = json.loads((ROOT / "work" / "paysim-publisher-metadata.json").read_text(encoding="utf-8-sig"))
steps = audit["by_step"]
pure = [r for r in steps if r["rows"] == r["positives"]]
test = audit["proposed_temporal_windows_not_yet_frozen"]["test_proposal"]
test_steps = [r for r in steps if test["first_step"] <= r["step"] <= test["last_step"]]
test_pure = [r for r in test_steps if r["rows"] == r["positives"]]
mixed = [r for r in test_steps if 0 < r["positives"] < r["rows"]]
audit["simulation_activity_diagnostics"] = {
    "all_hours_with_only_positive_rows": len(pure),
    "positive_rows_in_those_hours": sum(r["positives"] for r in pure),
    "proposed_test_observed_hours": len(test_steps),
    "proposed_test_hours_with_only_positive_rows": len(test_pure),
    "proposed_test_positives_in_those_hours": sum(r["positives"] for r in test_pure),
    "proposed_test_mixed_hours_rows": sum(r["rows"] for r in mixed),
    "proposed_test_mixed_hours_positives": sum(r["positives"] for r in mixed),
    "interpretation": "Evaluator-only artifact diagnostic; not a serving filter or model result."
}
audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
manifest = {
    "dataset_id": metadata["ref"],
    "title": metadata["title"],
    "publisher": "Edgar Lopez-Rojas",
    "version": metadata["currentVersionNumber"],
    "source_url": audit["source_url"],
    "metadata_url": audit["metadata_url"],
    "download_url": "https://www.kaggle.com/api/v1/datasets/download/ealaxi/paysim1?datasetVersionNumber=2",
    "retrieved_date_local": "2026-11-08",
    "license_name": metadata["licenseName"],
    "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
    "license_verification": "Confirmed from canonical publisher API on retrieval date.",
    "balance_warning_verification": "Publisher explicitly excludes all four balance fields because detected fraudulent transactions are cancelled.",
    "synthetic": True,
    "original_archive_modified": False,
    "archive_relative_path": "data/PaySim_v2.zip",
    "archive_bytes": audit["archive_bytes"],
    "archive_sha256": audit["archive_sha256"],
    "original_csv_name": audit["original_csv_name"],
    "csv_bytes": audit["csv_bytes"],
    "csv_sha256": audit["csv_sha256"],
    "rows_verified": audit["rows"],
    "columns_verified": audit["columns"],
    "citation": 'E. A. Lopez-Rojas, A. Elmir, and S. Axelsson. PaySim: A financial mobile money simulator for fraud detection. EMSS, 2016.',
    "project_data_guide": "Fraud_Detection_Data_and_Learning_Guide.md",
    "scope": "Provenance and initial full-file profile; no model benchmark.",
}
(OUT / "PaySim_Source_Manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
data_readme = """# PaySim version 2 — original dataset archive

The original publisher archive is saved as [PaySim_v2.zip](PaySim_v2.zip).

Publisher: Edgar Lopez-Rojas. Canonical source: https://www.kaggle.com/datasets/ealaxi/paysim1

Version: 2. Downloaded directly from Kaggle on 8 November 2026 without credentials. The archive is unchanged.

Licence: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0), verified through the canonical publisher API. Licence: https://creativecommons.org/licenses/by-sa/4.0/

Retain attribution and the licence notice when sharing the data; apply the relevant share-alike requirements when sharing adapted data. The simulator's source-code licence is separate.

Citation: E. A. Lopez-Rojas, A. Elmir, and S. Axelsson. “PaySim: A financial mobile money simulator for fraud detection.” EMSS, 2016.

These are synthetic mobile-money transactions. The publisher instructs excluding all four balance columns from fraud prediction because detected fraudulent transactions are cancelled.

The extracted CSV contains 6,362,620 rows, 11 columns, and 8,213 positive labels. It is approximately 494 MB; the archive is approximately 186 MB. Checksums and exact byte counts are in [the source manifest](../PaySim_Source_Manifest.json); the measured initial profile is in [the data audit](../PaySim_Data_Audit.json).

No fraud model was trained during this planning/data-collection session.
"""
(OUT / "data" / "README.md").write_text(data_readme, encoding="utf-8")
summary = f"""# PaySim initial data audit

**Measured from canonical version 2 on 8 November 2026. No model trained.**

- Rows: {audit['rows']:,}; columns: {len(audit['columns'])}.
- Positive fraud labels: {audit['positive_labels']:,} ({100*audit['positive_fraction']:.4f}%).
- Existing policy flags: {audit['policy_flagged']:,}; this count alone is not its precision.
- CSV: {audit['csv_bytes']:,} bytes; ZIP: {audit['archive_bytes']:,} bytes.
- Relative hourly steps: {audit['min_step']}–{audit['max_step']}, with {audit['observed_steps']} observed hours.
- Missing cells: {sum(audit['missing_values'].values())}; negative amounts: {audit['negative_amount_rows']}.
- Distinct sender references: {audit['account_recurrence']['nameOrig']['distinct_ids']:,}.
- Rows with strictly earlier-step sender history: {audit['account_recurrence']['nameOrig']['rows_with_strictly_earlier_step_history']:,} ({100*audit['account_recurrence']['nameOrig']['fraction_with_strictly_earlier_step_history']:.3f}%).
- Distinct recipient references: {audit['account_recurrence']['nameDest']['distinct_ids']:,}.
- Rows with strictly earlier-step recipient history: {audit['account_recurrence']['nameDest']['rows_with_strictly_earlier_step_history']:,} ({100*audit['account_recurrence']['nameDest']['fraction_with_strictly_earlier_step_history']:.3f}%).

**Implication:** focus available history features on recipients; do not promise rich sender histories or verified transfer chains. The recurrence calculation concerns the same source column/role and does not establish usefulness for prediction.

**Simulator artifact:** {len(pure)} hours contain only positive-labelled records. In the proposed final window, {len(test_pure)} hours contain only positives and contribute {sum(r['positives'] for r in test_pure):,} of {test['positives']:,} positives. Keep whole-window results and evaluator-only mixed-hour diagnostics. A label-defined diagnostic subset is never an input to serving or the assistant.

**Proposed chronological partitions, not yet frozen**

"""
for name, window in audit["proposed_temporal_windows_not_yet_frozen"].items():
    summary += f"- {name}: steps {window['first_step']}–{window['last_step']}; {window['rows']:,} rows; {window['positives']:,} positives; prevalence {100*window['positive_fraction']:.4f}%.\n"
summary += """

The class-support metadata above has been inspected; model/policy performance has not. Test prevalence differs substantially from development prevalence. Freeze the protocol before fitting and use prevalence-matched references.

**Open checks:** duplicate semantics, non-finite numeric values beyond missingness, time/class-specific history coverage, and final feature/policy/split decisions. No real-bank validation or fraud savings are established.

[Machine-readable audit](PaySim_Data_Audit.json) · [Source manifest](PaySim_Source_Manifest.json) · [Dataset attribution](data/README.md)
"""
(OUT / "PaySim_Data_Audit.md").write_text(summary, encoding="utf-8")

raw_tasks = [
("T01","M0","Freeze product scope","draft",[],["Recorded replay and analyst prioritization; units and supported claims documented."]),
("T02","M0","Acquire canonical PaySim and provenance","complete",["T01"],["Original version-2 archive, publisher licence/warning and SHA-256 saved."]),
("T03","M1","Initial full-file profile","complete",["T02"],["Schema, row/type/label/step counts and same-role account recurrence reproduced."]),
("T04","M1","Complete data-quality checks","not_started",["T03"],["Non-finite values and duplicate semantics investigated with explicit rejection policy."]),
("T05","M1","Profile recipient-history coverage","not_started",["T03"],["Strict earlier-step coverage measured by split, transaction type and class; sender limitations retained."]),
("T06","M1","Freeze feature contract and chronological protocol","draft",["T04","T05"],["All balances/derivatives, labels, policy flags and raw IDs excluded; exact cutoffs and warm-up rule recorded."]),
("T07","M2","Implement meaningful baselines","not_started",["T06"],["All-negative, native policy, amount/type rule, seeded daily random ranking and logistic regression reported."]),
("T08","M2","Implement capacity and artifact evaluation","not_started",["T06"],["AP, daily top-K, false alerts per 1000, per-time/type, mixed-hour and prevalence references tested on development."]),
("T09","M3","Build eligible history features","not_started",["T05","T06"],["Only supported recipient/prior-step features; no same-hour or future influence; measured ablations."]),
("T10","M3","Compare one CPU booster","not_started",["T07","T08","T09"],["Same population and capacity; limited model search; validation evidence determines choice."]),
("T11","M3","Freeze champion, policy and final evaluation","not_started",["T10"],["Versions pinned; final test report run once after selection; uncertainty/limitations reported."]),
("T12","M4","Define application schema and typed API","not_started",["T06"],["Truth isolated; model vector/version stored; server owns history features and evidence cutoffs."]),
("T13","M4","Implement replay and history checkpoint recovery","not_started",["T11","T12"],["Mid-hour interruption matches uninterrupted run; day-finalization and event writes idempotent."]),
("T14","M4","Verify serving and offline feature consistency","not_started",["T13"],["Fixture scores match; illegal inputs and label access fail explicitly."]),
("T15","M5","Build analyst queue and case evidence","not_started",["T13"],["Missing histories honest; scoring time and case evidence time separated."]),
("T16","M5","Build human disposition and audit flow","not_started",["T15"],["Authenticated human actions, optimistic update versions, and append-only audit entries."]),
("T17","M6","Run end-to-end and performance checks","not_started",["T14","T16"],["Replay-to-review fixture passes; hardware, batch time and API latency measured."]),
("T18","M6","Publish reproducible portfolio release","not_started",["T17"],["Readme, setup, data/model cards, evaluation, architecture and recorded demo verified."]),
("T19","M7","Author optional assistant development/holdout cases","optional",["T15"],["30–50 authored evidence tasks with isolated holdout and numeric/source expectations."]),
("T20","M7","Implement bounded read-only assistant","optional",["T18","T19"],["Typed tools enforce case/run and cutoff; no truth/raw SQL/mutations; no paid dependency for core."]),
("T21","M7","Evaluate assistant and cost limits","optional",["T20"],["Numeric facts reconcile; citations valid; failures/abstention tested; no observed leakage or unauthorized writes."]),
("T22","M8","Run independent ULB benchmark","optional",["T18"],["Separate data/schema/model and temporal report; no merged rows or unsupported transfer claim."])
]
backlog = {
 "created_date":"2026-11-08",
 "status":"planning_and_data_collection_only",
 "core_estimate_hours":{"min":84,"max":120},
 "weekly_hours_assumption":{"min":10,"max":15,"confirmed":False},
 "immediate_next":["T04","T05","T06"],
 "tasks":[{"id":i,"milestone":m,"title":t,"status":s,"dependencies":d,"completion_criteria":c}
          for i,m,t,s,d,c in raw_tasks]
}
(OUT / "fraud-project-backlog.json").write_text(json.dumps(backlog, indent=2), encoding="utf-8")
print(json.dumps({"files_created":["PaySim_Source_Manifest.json","PaySim_Data_Audit.md","data/README.md","fraud-project-backlog.json"],"pure_positive_hours":len(pure),"tasks":len(raw_tasks)}, indent=2))
