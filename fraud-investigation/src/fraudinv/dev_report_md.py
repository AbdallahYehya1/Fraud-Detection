"""Readable Markdown for the Day 2 development (validation-only) report."""
from __future__ import annotations

from pathlib import Path


def _f(x, pct=False, nd=4):
    if x is None:
        return "n/a"
    return f"{100 * x:.2f}%" if pct else (f"{x:,}" if isinstance(x, int) else f"{x:.{nd}f}")


def write_markdown(r: dict, path: Path) -> None:
    pop = r["population"]
    L = ["# Day 2 development report — validation only (generated)", "",
         f"Protocol `{r['protocol']}`, feature contract `{r['feature_contract']}`. "
         f"Test partition accessed: **{r['test_partition_accessed']}**. Scores are ranking scores, not probabilities.",
         "",
         f"Training rows {pop['train_rows']:,} ({pop['train_positives']:,} positives); validation rows "
         f"{pop['validation_rows']:,} ({pop['validation_positives']:,} positives). Daily top-K applies to each "
         "(partition, simulation day) segment over all transaction types; partial segments get pro-rated capacity.",
         "", "## Ranking and capacity on validation", "",
         "| method | AP | ROC-AUC | K/day | alerts | true pos. | precision | recall | false alerts /1000 legit |",
         "|---|---|---|---|---|---|---|---|---|"]
    for name, m in r["methods"].items():
        if "ranking" not in m:
            continue
        for k, c in m["capacity"].items():
            a = c["all_segments"]
            L.append(f"| {name} | {_f(m['ranking']['average_precision'])} | {_f(m['ranking']['roc_auc'], nd=3)} | {k} | "
                     f"{a['alerts']:,} | {a['true_positives']} | {_f(a['precision'], True)} | {_f(a['recall'], True)} | "
                     f"{_f(a['false_alerts_per_1000_legitimate'], nd=3)} |")
    np_ = r["methods"]["native_policy"]
    L += ["", f"Native `isFlaggedFraud` policy on validation (own workload, not a top-K ranking): "
              f"{np_['alerts']} alerts, {np_['true_positives']} true positives of {np_['positives']} positives "
              f"(precision {_f(np_['precision'], True)}, recall {_f(np_['recall'], True)}).",
          f"Constant-score AP reference (prevalence): {_f(r['methods']['all_negative']['ranking']['prevalence'], nd=6)}. "
          f"Accuracy if nothing is alerted: {_f(r['methods']['all_negative']['accuracy_if_nothing_alerted'], True)}."]
    lr = r["methods"]["logistic_regression"]
    L += ["", "## Logistic regression", "",
          f"Features {lr['features']} (contract-validated columns {lr['model_columns']}); class_weight=balanced; "
          f"C selected on validation AP from {[g['C'] for g in lr['C_grid']]} → **{lr['C_selected']}** "
          f"(APs {[round(g['validation_average_precision'], 6) for g in lr['C_grid']]}).",
          "", "Coefficients (standardized log-amount): " + ", ".join(f"`{k}` {v}" for k, v in lr["coefficients"].items()),
          "", f"Amount/type rule types (from training labels only): {r['methods']['amount_type_rule']['types_from_training']}."]
    L += ["", "## Complete days only (sensitivity)", "", "| method | K/day | alerts | true pos. | precision | recall |",
          "|---|---|---|---|---|---|"]
    for name, m in r["methods"].items():
        if "ranking" not in m:
            continue
        for k, c in m["capacity"].items():
            a = c["complete_days_only"]
            L.append(f"| {name} | {k} | {a['alerts']:,} | {a['true_positives']} | {_f(a['precision'], True)} | {_f(a['recall'], True)} |")
    L += ["", "## Per segment at K=100", "", "| method | partition | day | hours | capacity | positives | true pos. | recall |",
          "|---|---|---|---|---|---|---|---|"]
    for name in ("seeded_random", "amount_type_rule", "logistic_regression"):
        for s in r["methods"][name]["capacity"]["100"]["segments"]:
            L.append(f"| {name} | {s['partition']} | {s['day']} | {s['hours']} | {s['capacity']} | {s['positives']} | "
                     f"{s['true_positives']} | {_f(s['recall'], True)} |")
    L += ["", "## By transaction type at K=100", "", "| method | type | rows | positives | AP | true pos. | alerts |",
          "|---|---|---|---|---|---|---|"]
    for name in ("amount_type_rule", "logistic_regression"):
        for t in r["methods"][name]["by_type_k100"]:
            L.append(f"| {name} | {t['type']} | {t['rows']:,} | {t['positives']} | {_f(t['average_precision'])} | "
                     f"{t['cap_true_positives']} | {t['cap_alerts']} |")
    L += ["", "## Evaluator-only hour-mix diagnostics at K=100", "",
          "Label-defined subsets explain simulator artifacts; they are never features or serving filters.", "",
          "| method | hour kind | rows | positives | selected true pos. | AP within subset |", "|---|---|---|---|---|---|"]
    for name in ("seeded_random", "amount_type_rule", "logistic_regression"):
        for kind, d in r["methods"][name]["mixed_hour_diagnostics_k100"].items():
            ap = d["ranking"]["average_precision"] if d["ranking"] else None
            L.append(f"| {name} | {kind} | {d['rows']:,} | {d['positives']} | {d['selected_true_positives']} | {_f(ap)} |")
    bt = r["development_backtest"]
    L += ["", "## Development backtest inside training", "",
          f"Fit steps {bt['fit_steps']} ({bt['fit_positives']} positives), evaluate steps {bt['evaluate_steps']} "
          f"({bt['evaluate_rows']:,} rows, {bt['evaluate_positives']} positives). C={bt['C']}.", "",
          "| method | AP | K=100 true pos. | K=100 recall |", "|---|---|---|---|"]
    for name, m in bt["methods"].items():
        a = m["capacity"]["100"]["all_segments"]
        L.append(f"| {name} | {_f(m['ranking']['average_precision'])} | {a['true_positives']} | {_f(a['recall'], True)} |")
    rt = r["runtime"]
    L += ["", "## Runtime", f"Total {rt['total_seconds']}s ({rt['sections_seconds']}); peak Python working set "
          f"{rt['peak_python_process_mib']} MiB.", ""]
    path.write_text("\n".join(L), encoding="utf-8")
