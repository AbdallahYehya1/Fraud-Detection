"""Readable Markdown for the Day 3 selection and one-time final test."""
from __future__ import annotations

import json
from pathlib import Path

from . import config


def _f(x, pct=False, nd=4):
    if x is None:
        return "n/a"
    return f"{100 * x:.2f}%" if pct else f"{x:.{nd}f}"


def write_markdown(path: Path) -> None:
    d3 = config.REPORTS_DIR / "day3"
    sel = json.loads((d3 / "selection_report.json").read_text(encoding="utf-8"))
    fin = json.loads((d3 / "final_test_report.json").read_text(encoding="utf-8"))
    fr = fin["frozen_selection"]
    L = ["# Day 3 — selection on validation and one-time final test (generated)", "",
         "## Selection (validation only)", "",
         f"Protocol `{sel['selection_protocol']}` (config/selection_protocol.yaml, written before any history or "
         f"booster model was scored). Amount/type rule validation AP: {_f(sel['amount_type_rule_validation_ap'])}.", "",
         "| candidate | features | validation AP | ROC-AUC | K=100 recall | K=100 precision | fit s |",
         "|---|---|---|---|---|---|---|"]
    for c in sel["candidates"]:
        L.append(f"| {c['kind']} {json.dumps(c['params'])} | {c['feature_set']} | {_f(c['validation_ap'])} | "
                 f"{_f(c['validation_auc'], nd=3)} | {_f(c['validation_recall_k100'], True)} | "
                 f"{_f(c['validation_precision_k100'], True)} | {c['fit_seconds']} |")
    for a in sel["ablations"]:
        L.append(f"| **ablation, not eligible** | {a['id']} | {_f(a['validation_ap'])} | | "
                 f"{_f(a['validation_recall_k100'], True)} | | |")
    L += ["", f"Decision: **{sel['decision']['champion']}** — {sel['decision']['reason']}.", "",
          "The hour-of-day ablation roughly doubles validation AP. Pure-positive simulator hours are concentrated "
          "at night (Day 1 audit), so this gain is treated as a simulator shortcut and the feature stays excluded.",
          "", "## Frozen selection", "",
          f"- Model `{fr['model_version']}`: {fr['kind']} {json.dumps(fr['params'])}",
          f"- Features: {fr['features']} → columns {fr['model_columns']}",
          f"- Versions: contract `{fr['feature_contract']}`, history table `{fr['history_feature_table']}`, split "
          f"`{fr['split_protocol']}`, selection `{fr['selection_protocol']}`, policy `{fr['review_policy']['version']}` "
          f"(daily top-{fr['review_policy']['k']})",
          f"- Artifact `{fr['artifact']['path']}` sha256 `{fr['artifact']['sha256']}` (scikit-learn {fr['artifact']['sklearn']})",
          f"- Refit reproduced validation AP exactly: {fr['validation_ap_reproduced']}",
          f"- Frozen at {fr['frozen_at_utc']}; test accessed before freeze: {fr['test_partition_accessed_before_freeze']}",
          f"- {fr['score_semantics']}", "",
          "## Final test (run once)", "",
          f"Population: all {fin['population']['rows']:,} test rows (steps 356–743), {fin['population']['positives']:,} "
          f"positives, prevalence {_f(fin['population']['prevalence'], True)} — about 5.7× the validation prevalence. "
          f"Constant-score AP reference = {_f(fin['constant_score_ap_reference'])}.", "",
          "| method | AP | ROC-AUC | K/day | alerts | true pos. | precision | recall | false alerts /1000 legit |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name, m in fin["methods"].items():
        for k, c in m["capacity"].items():
            a = c["all_segments"]
            L.append(f"| {name} | {_f(m['ranking']['average_precision'])} | {_f(m['ranking']['roc_auc'], nd=3)} | {k} | "
                     f"{a['alerts']:,} | {a['true_positives']:,} | {_f(a['precision'], True)} | {_f(a['recall'], True)} | "
                     f"{_f(a['false_alerts_per_1000_legitimate'], nd=3)} |")
    npol = fin["native_policy"]
    L += ["", f"Native `isFlaggedFraud` policy (own workload): {npol['alerts']} alerts, {npol['true_positives']} true "
              f"positives (precision {_f(npol['precision'], True)}, recall {_f(npol['recall'], True)}).", "",
          "### Day-block bootstrap (95% percentile intervals)", "",
          f"{fin['bootstrap']['resamples']} resamples of the {fin['bootstrap']['segments']} test day segments, "
          f"seed {fin['bootstrap']['seed']}.", "",
          "| method | AP | K=100 recall | K=100 precision |", "|---|---|---|---|"]
    for name, iv in fin["bootstrap"]["intervals"].items():
        L.append(f"| {name} | {_f(iv['average_precision']['p2.5'])}–{_f(iv['average_precision']['p97.5'])} | "
                 f"{_f(iv['recall_k100']['p2.5'], True)}–{_f(iv['recall_k100']['p97.5'], True)} | "
                 f"{_f(iv['precision_k100']['p2.5'], True)}–{_f(iv['precision_k100']['p97.5'], True)} |")
    L += ["", "### Complete days only (K=100)", "", "| method | alerts | true pos. | precision | recall |", "|---|---|---|---|---|"]
    for name, m in fin["methods"].items():
        a = m["capacity"]["100"]["complete_days_only"]
        L.append(f"| {name} | {a['alerts']:,} | {a['true_positives']:,} | {_f(a['precision'], True)} | {_f(a['recall'], True)} |")
    L += ["", "### By transaction type (K=100)", "", "| method | type | rows | positives | AP | true pos. | alerts |",
          "|---|---|---|---|---|---|---|"]
    for name in ("champion", "amount_type_rule"):
        for t in fin["methods"][name]["by_type_k100"]:
            L.append(f"| {name} | {t['type']} | {t['rows']:,} | {t['positives']:,} | {_f(t['average_precision'])} | "
                     f"{t['cap_true_positives']:,} | {t['cap_alerts']:,} |")
    L += ["", "### Evaluator-only hour-mix diagnostics (K=100)", "",
          "| method | hour kind | rows | positives | selected true pos. | AP within subset |", "|---|---|---|---|---|---|"]
    for name, m in fin["methods"].items():
        for kind, dd in m["mixed_hour_diagnostics_k100"].items():
            ap = dd["ranking"]["average_precision"] if dd["ranking"] else None
            L.append(f"| {name} | {kind} | {dd['rows']:,} | {dd['positives']:,} | {dd['selected_true_positives']:,} | {_f(ap)} |")
    L += ["", "### Per day segment (champion, K=100)", "", "| day | hours | capacity | positives | true pos. | precision | recall |",
          "|---|---|---|---|---|---|---|"]
    for s in fin["methods"]["champion"]["capacity"]["100"]["segments"]:
        L.append(f"| {s['day']} | {s['hours']} | {s['capacity']} | {s['positives']} | {s['true_positives']} | "
                 f"{_f(s['precision'], True)} | {_f(s['recall'], True)} |")
    L += ["", "## Reading these results", "",
          "- Synthetic PaySim data; no real-bank validity, fraud savings or analyst-time claims follow from these numbers.",
          "- Test prevalence is ~5.7× validation, so test AP is not comparable to validation AP in absolute terms.",
          "- A large share of the champion's test hits fall in pure-positive simulator hours; the mixed-hour row is the "
          "more conservative view. Both are evaluator-only diagnostics.",
          "- The main signal is recipient novelty: in the Day 1 audit, 0% of validation/test positive TRANSFERs had an "
          "earlier-step recipient record versus ~88% of legitimate TRANSFERs. That pattern may be specific to the simulator.",
          "- Scores are ranking scores; calibration is deferred.",
          f"- Final test runtime {fin['runtime']['total_seconds']}s; peak Python working set {fin['runtime']['peak_python_process_mib']} MiB.", ""]
    path.write_text("\n".join(L), encoding="utf-8")
