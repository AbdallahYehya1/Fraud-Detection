"""Day 1 data-quality audit (T04/T05) over the verified PaySim CSV and Parquet.

Every query here is descriptive. Label-based groupings (class, pure-positive
hours) are evaluator-only diagnostics; nothing in this module produces serving
features or filters.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
import pandas as pd

from . import config, splits
from .history import recipient_history
from .runtime import environment, peak_rss_mib

NUMERIC = ["amount", "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest"]
SOURCE_COLS = config.data_source()["csv"]["columns"]


def _partition_sql(col: str = "step") -> str:
    cases = " ".join(f"WHEN {col} BETWEEN {lo} AND {hi} THEN '{name}'"
                     for name, (lo, hi) in splits.partitions().items())
    return f"CASE {cases} END"


def _records(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _effective_decimals(col: str) -> str:
    """Decimal places after expanding Java-style scientific notation (e.g. 4.196370815E7 -> 2)."""
    return (f"CASE WHEN regexp_matches({col}, '[eE]') THEN greatest(0, "
            f"length(regexp_extract({col}, '\\.([0-9]*)[eE]', 1)) - "
            f"CAST(regexp_extract({col}, '[eE]([+-]?[0-9]+)', 1) AS INTEGER)) "
            f"WHEN strpos({col}, '.') > 0 THEN length({col}) - strpos({col}, '.') ELSE 0 END")


def _one(con: duckdb.DuckDBPyConnection, sql: str) -> dict:
    return _records(con, sql)[0]


class Timer:
    def __init__(self) -> None:
        self.sections: dict[str, float] = {}

    def run(self, name, fn, *args):
        t = time.perf_counter()
        out = fn(*args)
        self.sections[name] = round(time.perf_counter() - t, 2)
        print(f"  {name}: {self.sections[name]}s", flush=True)
        return out


def raw_text_checks(con, csv: Path) -> dict:
    """String-level checks on the original CSV: parse failures and decimal precision."""
    src = f"read_csv('{csv.as_posix()}', header=true, all_varchar=true)"
    parts = []
    for c in NUMERIC:
        parts.append(f"sum(CASE WHEN TRY_CAST({c} AS DOUBLE) IS NULL THEN 1 ELSE 0 END) AS {c}_unparseable")
        parts.append(f"sum(CASE WHEN regexp_matches(lower({c}), 'nan|inf') THEN 1 ELSE 0 END) AS {c}_nan_inf_text")
        parts.append(f"max({_effective_decimals(c)}) AS {c}_max_decimals")
        parts.append(f"sum(CASE WHEN regexp_matches({c}, '[eE]') THEN 1 ELSE 0 END) AS {c}_scientific_notation")
    parts += [
        "sum(CASE WHEN TRY_CAST(step AS INTEGER) IS NULL OR step LIKE '%.%' THEN 1 ELSE 0 END) AS step_not_integer",
        "sum(CASE WHEN isFraud NOT IN ('0','1') THEN 1 ELSE 0 END) AS isFraud_outside_01",
        "sum(CASE WHEN isFlaggedFraud NOT IN ('0','1') THEN 1 ELSE 0 END) AS isFlaggedFraud_outside_01",
        "sum(CASE WHEN nameOrig = '' OR nameDest = '' OR type = '' THEN 1 ELSE 0 END) AS empty_strings",
        "count(*) AS rows",
    ]
    return _one(con, f"SELECT {', '.join(parts)} FROM {src}")


def ingest_integrity(con, csv: Path, positions=(0, 1, 1_000_000, 3_181_310, 6_362_619)) -> dict:
    """Confirm source_row equals the original data-row position by re-reading CSV lines."""
    wanted = set(positions)
    raw: dict[int, list[str]] = {}
    with csv.open(encoding="utf-8") as fh:
        next(fh)
        for i, line in enumerate(fh):
            if i in wanted:
                raw[i] = line.rstrip("\n").split(",")
                if len(raw) == len(wanted):
                    break
    pos = ", ".join(str(p) for p in positions)
    rows = con.execute(f"""SELECT source_row, step, type, nameOrig, nameDest, isFraud FROM ev
                           WHERE source_row IN ({pos}) ORDER BY source_row""").fetchall()
    checks = []
    for source_row, step, typ, orig, dest, label in rows:
        line = raw[source_row]
        ok = [str(step), typ, orig, dest, str(label)] == [line[0], line[1], line[3], line[6], line[9]]
        checks.append({"source_row": source_row, "matches_csv_line": ok})
    return {"checked": checks, "passed": len(checks) == len(positions) and all(c["matches_csv_line"] for c in checks)}


def typed_checks(con) -> dict:
    parts = []
    for c in NUMERIC:
        parts += [f"sum(CASE WHEN isnan({c}) THEN 1 ELSE 0 END) AS {c}_nan",
                  f"sum(CASE WHEN isinf({c}) THEN 1 ELSE 0 END) AS {c}_inf",
                  f"sum(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) AS {c}_null",
                  f"sum(CASE WHEN {c} < 0 THEN 1 ELSE 0 END) AS {c}_negative",
                  f"sum(CASE WHEN {c} = 0 THEN 1 ELSE 0 END) AS {c}_zero"]
    types = ", ".join(f"'{t}'" for t in config.feature_contract()["transaction_types"])
    parts += [
        f"sum(CASE WHEN type NOT IN ({types}) THEN 1 ELSE 0 END) AS type_out_of_domain",
        "sum(CASE WHEN step < 1 OR step > 743 THEN 1 ELSE 0 END) AS step_out_of_range",
        "min(step) AS min_step", "max(step) AS max_step", "count(DISTINCT step) AS observed_steps",
        "sum(CASE WHEN NOT regexp_matches(nameOrig, '^[CM][0-9]+$') THEN 1 ELSE 0 END) AS nameOrig_bad_format",
        "sum(CASE WHEN NOT regexp_matches(nameDest, '^[CM][0-9]+$') THEN 1 ELSE 0 END) AS nameDest_bad_format",
        "sum(CASE WHEN nameOrig = nameDest THEN 1 ELSE 0 END) AS self_transfer_rows",
        "sum(isFraud) AS positives", "sum(isFlaggedFraud) AS policy_flagged",
        "sum(CASE WHEN isFlaggedFraud = 1 AND isFraud = 1 THEN 1 ELSE 0 END) AS flagged_and_positive",
        "sum(CASE WHEN isFlaggedFraud = 1 AND isFraud = 0 THEN 1 ELSE 0 END) AS flagged_and_negative",
        "max(source_row) AS max_source_row", "count(DISTINCT source_row) AS distinct_source_rows",
        "count(*) AS rows",
    ]
    out = _one(con, f"SELECT {', '.join(parts)} FROM ev")
    out["zero_amount_by_type_and_class"] = _records(con, """
        SELECT type, isFraud, count(*) AS rows FROM ev WHERE amount = 0
        GROUP BY ALL ORDER BY ALL""")
    out["name_prefix_by_role_and_type"] = _records(con, """
        SELECT type, left(nameOrig, 1) AS orig_prefix, left(nameDest, 1) AS dest_prefix,
               count(*) AS rows, sum(isFraud) AS positives
        FROM ev GROUP BY ALL ORDER BY ALL""")
    out["amount_quantiles_by_type"] = _records(con, """
        SELECT type, min(amount) AS min, quantile_cont(amount, 0.5) AS median,
               quantile_cont(amount, 0.99) AS p99, max(amount) AS max
        FROM ev GROUP BY ALL ORDER BY ALL""")
    return out


def duplicate_checks(con) -> dict:
    allcols = ", ".join(SOURCE_COLS)
    nolabel = ", ".join(c for c in SOURCE_COLS if c not in ("isFraud", "isFlaggedFraud"))
    exact = _one(con, f"""
        SELECT count(*) AS duplicate_groups, coalesce(sum(n), 0) AS rows_in_groups,
               coalesce(sum(n - 1), 0) AS surplus_rows, coalesce(max(n), 0) AS max_group_size
        FROM (SELECT count(*) AS n FROM ev GROUP BY {allcols} HAVING count(*) > 1)""")
    label_conflict = _one(con, f"""
        SELECT count(*) AS groups_with_conflicting_labels
        FROM (SELECT count(DISTINCT isFraud) AS k FROM ev GROUP BY {nolabel} HAVING k > 1)""")
    key = _one(con, """
        SELECT count(*) AS duplicate_groups, coalesce(sum(n), 0) AS rows_in_groups,
               coalesce(sum(pos), 0) AS positives_in_groups
        FROM (SELECT count(*) AS n, sum(isFraud) AS pos FROM ev
              GROUP BY step, type, amount, nameOrig, nameDest HAVING count(*) > 1)""")
    key_examples = _records(con, """
        SELECT step, type, amount, nameOrig, nameDest, count(*) AS n,
               list(source_row ORDER BY source_row) AS source_rows, sum(isFraud) AS positives
        FROM ev GROUP BY step, type, amount, nameOrig, nameDest HAVING count(*) > 1
        ORDER BY step, min(source_row) LIMIT 10""")
    # PaySim fraud is TRANSFER followed by CASH_OUT of the same amount by the same
    # synthetic actor; identical (step, amount) pairs are expected, not duplicates.
    transfer_cashout = _one(con, """
        WITH t AS (SELECT step, amount, nameDest FROM ev WHERE type = 'TRANSFER' AND isFraud = 1),
             c AS (SELECT step, amount, nameOrig FROM ev WHERE type = 'CASH_OUT' AND isFraud = 1)
        SELECT (SELECT count(*) FROM t) AS positive_transfers,
               (SELECT count(*) FROM c) AS positive_cash_outs,
               (SELECT count(*) FROM t JOIN c USING (step, amount)) AS same_step_same_amount_pairs,
               (SELECT count(*) FROM t JOIN c ON t.nameDest = c.nameOrig) AS transfer_dest_equals_cashout_orig""")
    return {"exact_all_columns": exact, "same_non_label_values_different_label": label_conflict,
            "same_step_type_amount_sender_recipient": key, "key_duplicate_examples": key_examples,
            "positive_transfer_cashout_pairing": transfer_cashout}


def partition_support(con) -> dict:
    p = _partition_sql()
    return {
        "by_partition": _records(con, f"""
            SELECT {p} AS partition, min(step) AS first_step, max(step) AS last_step,
                   count(DISTINCT step) AS observed_hours, count(*) AS rows,
                   sum(isFraud) AS positives, sum(isFraud) / count(*) AS prevalence,
                   sum(isFlaggedFraud) AS policy_flagged,
                   count(DISTINCT (step - 1) // 24) AS days_touched
            FROM ev GROUP BY 1 ORDER BY first_step"""),
        "by_partition_type": _records(con, f"""
            SELECT {p} AS partition, type, count(*) AS rows, sum(isFraud) AS positives,
                   sum(isFlaggedFraud) AS policy_flagged
            FROM ev GROUP BY ALL ORDER BY min(step), type"""),
        "partition_day_segments": _records(con, f"""
            SELECT {p} AS partition, (step - 1) // 24 AS day, min(step) AS first_step,
                   max(step) AS last_step, count(DISTINCT step) AS observed_hours,
                   count(*) AS rows, sum(isFraud) AS positives
            FROM ev GROUP BY ALL ORDER BY first_step"""),
    }


def recipient_history_coverage(con) -> dict:
    """Strictly earlier-step recurrence by partition x type x class."""
    p = _partition_sql("e.step")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE dest_hist AS
        WITH per AS (SELECT nameDest, step, count(*) AS n FROM ev GROUP BY 1, 2)
        SELECT nameDest, step, n,
               coalesce(sum(n) OVER (PARTITION BY nameDest ORDER BY step
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS prior_n,
               coalesce(sum(n) OVER (PARTITION BY nameDest ORDER BY step
                        RANGE BETWEEN 24 PRECEDING AND 1 PRECEDING), 0) AS prior_24h
        FROM per""")
    con.execute("""
        CREATE OR REPLACE TEMP TABLE orig_first AS
        SELECT nameOrig AS account, min(step) AS first_step FROM ev GROUP BY 1""")
    detail = _records(con, f"""
        SELECT {p} AS partition, e.type, e.isFraud AS label,
               count(*) AS rows,
               sum(CASE WHEN h.prior_n > 0 THEN 1 ELSE 0 END) AS with_prior,
               sum(CASE WHEN h.prior_n > 0 THEN 1 ELSE 0 END) / count(*) AS with_prior_fraction,
               sum(CASE WHEN h.prior_24h > 0 THEN 1 ELSE 0 END) / count(*) AS with_prior_24h_fraction,
               sum(CASE WHEN h.prior_n = 0 AND h.n > 1 THEN 1 ELSE 0 END) AS same_step_only_recurrence,
               sum(CASE WHEN h.prior_n = 1 THEN 1 ELSE 0 END) AS prior_1,
               sum(CASE WHEN h.prior_n BETWEEN 2 AND 4 THEN 1 ELSE 0 END) AS prior_2_4,
               sum(CASE WHEN h.prior_n BETWEEN 5 AND 9 THEN 1 ELSE 0 END) AS prior_5_9,
               sum(CASE WHEN h.prior_n >= 10 THEN 1 ELSE 0 END) AS prior_10_plus,
               sum(CASE WHEN o.first_step < e.step THEN 1 ELSE 0 END) AS dest_seen_earlier_as_sender
        FROM ev e JOIN dest_hist h USING (nameDest, step)
        LEFT JOIN orig_first o ON o.account = e.nameDest
        GROUP BY ALL ORDER BY min(e.step), e.type, label""")
    by_partition = _records(con, f"""
        SELECT {p} AS partition, e.isFraud AS label, count(*) AS rows,
               sum(CASE WHEN h.prior_n > 0 THEN 1 ELSE 0 END) / count(*) AS with_prior_fraction,
               sum(CASE WHEN h.prior_24h > 0 THEN 1 ELSE 0 END) / count(*) AS with_prior_24h_fraction
        FROM ev e JOIN dest_hist h USING (nameDest, step)
        GROUP BY ALL ORDER BY min(e.step), label""")
    overall = _one(con, """
        SELECT count(*) AS rows, sum(CASE WHEN h.prior_n > 0 THEN 1 ELSE 0 END) AS with_prior,
               sum(CASE WHEN h.prior_24h > 0 THEN 1 ELSE 0 END) AS with_prior_24h
        FROM ev e JOIN dest_hist h USING (nameDest, step)""")
    sender = _records(con, f"""
        WITH per AS (SELECT nameOrig, step, count(*) AS n FROM ev GROUP BY 1, 2),
             h AS (SELECT nameOrig, step,
                          coalesce(sum(n) OVER (PARTITION BY nameOrig ORDER BY step
                                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS prior_n
                   FROM per)
        SELECT {p} AS partition, count(*) AS rows,
               sum(CASE WHEN h.prior_n > 0 THEN 1 ELSE 0 END) AS with_prior,
               sum(CASE WHEN h.prior_n > 0 THEN 1 ELSE 0 END) / count(*) AS with_prior_fraction,
               sum(CASE WHEN h.prior_n > 0 AND e.isFraud = 1 THEN 1 ELSE 0 END) AS positives_with_prior
        FROM ev e JOIN h USING (nameOrig, step) GROUP BY 1 ORDER BY min(e.step)""")
    return {"definition": "same nameDest in recipient role at a strictly earlier step; "
                          "24h = steps s-24..s-1; same-step rows never count",
            "overall": overall, "by_partition_label": by_partition,
            "by_partition_type_label": detail, "sender_history_by_partition": sender}


def history_crosscheck(con, max_step: int = 48) -> dict:
    """Compare DuckDB window counts with the pandas reference on early steps."""
    sample = con.execute(f"""
        SELECT source_row, step, nameDest, amount FROM ev WHERE step <= {max_step}
        ORDER BY source_row""").df()
    ref = recipient_history(sample)
    # recompute DuckDB counts restricted to the same subset (history inside subset only)
    db = con.execute(f"""
        WITH s AS (SELECT source_row, step, nameDest FROM ev WHERE step <= {max_step}),
             per AS (SELECT nameDest, step, count(*) AS n FROM s GROUP BY 1, 2),
             h AS (SELECT nameDest, step,
                          coalesce(sum(n) OVER (PARTITION BY nameDest ORDER BY step
                                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS prior_n,
                          coalesce(sum(n) OVER (PARTITION BY nameDest ORDER BY step
                                   RANGE BETWEEN 24 PRECEDING AND 1 PRECEDING), 0) AS prior_24h
                   FROM per)
        SELECT s.source_row, h.prior_n, h.prior_24h FROM s JOIN h USING (nameDest, step)
        ORDER BY s.source_row""").df()
    merged = sample[["source_row"]].join(ref).merge(db, on="source_row")
    mism_all = int((merged["dest_prior_count"] != merged["prior_n"]).sum())
    mism_24 = int((merged["dest_prior_count_24h"] != merged["prior_24h"]).sum())
    return {"steps": f"1-{max_step}", "rows": len(merged), "mismatch_prior_count": mism_all,
            "mismatch_prior_24h": mism_24, "passed": mism_all == 0 and mism_24 == 0}


def pure_positive_hours(con) -> dict:
    p = _partition_sql()
    con.execute("""
        CREATE OR REPLACE TEMP TABLE hours AS
        SELECT step, count(*) AS rows, sum(isFraud) AS positives FROM ev GROUP BY step""")
    by_partition = _records(con, f"""
        SELECT {p} AS partition, count(*) AS observed_hours,
               sum(CASE WHEN positives = rows THEN 1 ELSE 0 END) AS pure_positive_hours,
               sum(CASE WHEN positives = rows THEN positives ELSE 0 END) AS positives_in_pure_hours,
               sum(CASE WHEN positives > 0 AND positives < rows THEN 1 ELSE 0 END) AS mixed_hours,
               sum(CASE WHEN positives > 0 AND positives < rows THEN positives ELSE 0 END) AS positives_in_mixed_hours,
               sum(CASE WHEN positives > 0 AND positives < rows THEN rows ELSE 0 END) AS rows_in_mixed_hours,
               sum(CASE WHEN positives = 0 THEN 1 ELSE 0 END) AS zero_positive_hours,
               sum(CASE WHEN positives = 0 THEN rows ELSE 0 END) AS rows_in_zero_positive_hours,
               sum(positives) AS positives
        FROM hours GROUP BY 1 ORDER BY min(step)""")
    pure_size = _records(con, f"""
        SELECT {p} AS partition, min(rows) AS min_rows, median(rows) AS median_rows, max(rows) AS max_rows
        FROM hours WHERE positives = rows GROUP BY 1 ORDER BY min(step)""")
    hour_of_day = _records(con, """
        SELECT (step - 1) % 24 AS hour_of_day, count(*) AS observed_hours,
               sum(CASE WHEN positives = rows THEN 1 ELSE 0 END) AS pure_positive_hours,
               sum(rows) AS rows, sum(positives) AS positives
        FROM hours GROUP BY 1 ORDER BY 1""")
    by_day = _records(con, """
        SELECT (step - 1) // 24 AS day, count(*) AS observed_hours,
               sum(CASE WHEN positives = rows THEN 1 ELSE 0 END) AS pure_positive_hours,
               sum(rows) AS rows, sum(positives) AS positives
        FROM hours GROUP BY 1 ORDER BY 1""")
    return {"by_partition": by_partition, "pure_hour_row_counts": pure_size,
            "by_hour_of_day": hour_of_day, "by_day": by_day,
            "scope": "evaluator-only diagnostic; never a feature, serving filter or assistant input"}


def run(out_dir: Path, memory_limit: str = "2GB", threads: int = 4, verify: bool = True) -> dict:
    from .ingest import csv_to_parquet
    from .source import verify_file

    started = time.perf_counter()
    timer = Timer()
    src = config.data_source()
    p = config.paths()
    result: dict = {"audit": "day1-data-quality", "contract_versions": {
        "split": config.split_protocol()["protocol_version"],
        "features": config.feature_contract()["contract_version"]},
        "environment": environment()}
    if verify:
        result["source_verification"] = {
            "archive": timer.run("verify_archive", verify_file, p.raw_archive,
                                 src["archive"]["bytes"], src["archive"]["sha256"]),
            "csv": timer.run("verify_csv", verify_file, p.raw_csv,
                             src["csv"]["bytes"], src["csv"]["sha256"]),
        }
    if not p.events_parquet.exists():
        result["ingest"] = timer.run("csv_to_parquet", csv_to_parquet, p.raw_csv, p.events_parquet,
                                     src["csv"]["columns"], src["csv"]["rows"])
    tmp = p.data_dir / "duckdb_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{memory_limit}'; SET threads={threads}; "
                f"SET temp_directory='{tmp.as_posix()}'; SET preserve_insertion_order=false")
    con.execute(f"CREATE VIEW ev AS SELECT * FROM read_parquet('{p.events_parquet.as_posix()}')")
    result["ingest_integrity"] = timer.run("ingest_integrity", ingest_integrity, con, p.raw_csv)
    result["raw_text_checks"] = timer.run("raw_text_checks", raw_text_checks, con, p.raw_csv)
    result["typed_checks"] = timer.run("typed_checks", typed_checks, con)
    result["duplicates"] = timer.run("duplicates", duplicate_checks, con)
    result["partition_support"] = timer.run("partition_support", partition_support, con)
    result["recipient_history"] = timer.run("recipient_history", recipient_history_coverage, con)
    result["history_crosscheck"] = timer.run("history_crosscheck", history_crosscheck, con)
    result["pure_positive_hours"] = timer.run("pure_positive_hours", pure_positive_hours, con)
    con.close()
    result["runtime"] = {"sections_seconds": timer.sections,
                         "total_seconds": round(time.perf_counter() - started, 2),
                         "peak_python_process_mib": peak_rss_mib(),
                         "duckdb_memory_limit": memory_limit, "duckdb_threads": threads}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data_quality_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
