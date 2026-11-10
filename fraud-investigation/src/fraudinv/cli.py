"""Command line entry point: ``python -m fraudinv <command>``."""
from __future__ import annotations

import argparse
import json
import sys

from . import config


def cmd_verify(args) -> int:
    from .source import SourceMismatch, extract_csv, verify_file

    src = config.data_source()
    p = config.paths()
    try:
        print(json.dumps(verify_file(p.raw_archive, src["archive"]["bytes"], src["archive"]["sha256"])))
        if not p.raw_csv.exists():
            if not args.extract:
                print(f"CSV missing at {p.raw_csv}; rerun with --extract", file=sys.stderr)
                return 2
            extract_csv(p.raw_archive, src["archive"]["original_csv_name"], p.raw_csv)
        print(json.dumps(verify_file(p.raw_csv, src["csv"]["bytes"], src["csv"]["sha256"])))
    except SourceMismatch as exc:
        print(f"SOURCE MISMATCH: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_ingest(args) -> int:
    from .ingest import csv_to_parquet

    src = config.data_source()
    p = config.paths()
    if p.events_parquet.exists() and not args.force:
        print(f"exists: {p.events_parquet} (use --force to rebuild)")
        return 0
    print(json.dumps(csv_to_parquet(p.raw_csv, p.events_parquet, src["csv"]["columns"], src["csv"]["rows"])))
    return 0


def cmd_audit(args) -> int:
    from . import audit, audit_report

    out = config.REPORTS_DIR / "day1"
    result = audit.run(out, memory_limit=args.memory_limit, threads=args.threads, verify=not args.skip_verify)
    audit_report.write_markdown(result, out / "data_quality_audit.md")
    print(f"wrote {out / 'data_quality_audit.json'} and .md; total {result['runtime']['total_seconds']}s")
    return 0


def cmd_evaluate_dev(args) -> int:
    from . import dev_report, dev_report_md

    out = config.REPORTS_DIR / "day2"
    result = dev_report.run(out)
    dev_report_md.write_markdown(result, out / "validation_report.md")
    print(f"wrote {out / 'validation_report.json'} and .md; total {result['runtime']['total_seconds']}s")
    return 0


def cmd_features(args) -> int:
    from . import features

    print(json.dumps(features.build()))
    return 0


def cmd_select(args) -> int:
    from . import model_select

    result = model_select.run(config.REPORTS_DIR / "day3")
    print(json.dumps(result["decision"], indent=2))
    return 0


def cmd_freeze(args) -> int:
    from . import freeze

    record = freeze.freeze()
    print(json.dumps({k: record[k] for k in ("model_version", "candidate_id", "validation_ap_reproduced")}, indent=2))
    return 0


def cmd_final_test(args) -> int:
    from . import day3_report_md, freeze

    result = freeze.final_test(rerun_reason=args.rerun_reason)
    day3_report_md.write_markdown(config.REPORTS_DIR / "day3" / "day3_report.md")
    print(json.dumps(result["population"]), result["runtime"])
    return 0


def cmd_db_env(args) -> int:
    from . import db

    print("created .env" if db.write_env() else ".env exists; left unchanged")
    return 0


def cmd_db_migrate(args) -> int:
    from . import db

    print(json.dumps({"applied": db.migrate()}))
    return 0


def cmd_replay_create(args) -> int:
    from . import db, replay

    with db.connect("app", autocommit=True) as conn:
        print(json.dumps(replay.create_run(conn, args.run_id, args.first_step, args.last_step, args.capacity)))
    return 0


def cmd_replay_run(args) -> int:
    from . import db, replay

    with db.connect("app", autocommit=True) as conn:
        print(json.dumps(replay.run_replay(conn, args.run_id, max_steps=args.max_steps), default=str))
    return 0


def cmd_day4_check(args) -> int:
    from . import day4_check

    result = day4_check.run()
    print(json.dumps({"passed": result["passed"], "runtime": result["runtime"]}))
    return 0 if result["passed"] else 1


def cmd_analyst_add(args) -> int:
    from . import cases, db

    with db.connect("admin", autocommit=True) as conn:
        token = cases.add_analyst(conn, args.analyst_id, args.name)
    path = config.APP_ROOT / ".tools" / f"analyst-{args.analyst_id}.token"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    print(f"analyst {args.analyst_id} ready; bearer token written to {path} (git-ignored; shown once there)")
    return 0


def cmd_evidence_backfill(args) -> int:
    from . import db, replay

    with db.connect("app", autocommit=True) as conn:
        segs = conn.execute("SELECT partition_name, simulation_day FROM app.day_finalization WHERE run_id = %s "
                            "ORDER BY 2", (args.run_id,)).fetchall()
        for part, day in segs:
            n = replay.backfill_evidence(conn, replay.Source.default(), args.run_id, part, day)
            print(json.dumps({"segment": [part, day], "source_rows_considered": n}))
    return 0


def cmd_evaluate_run(args) -> int:
    from . import evaluate_run

    r = evaluate_run.evaluate(args.run_id)
    print(json.dumps({"total": r["total"], "offline_segment_crosscheck": r["offline_segment_crosscheck"]}))
    return 0


def cmd_assistant_ask(args) -> int:
    from . import assistant

    res = assistant.investigate(args.case_id, args.question)
    print(f"[{res['mode']}] {res.get('seconds')}s, {res.get('tool_calls')} tool call(s)\n\n{res['answer']}")
    removed = (res.get("guard") or {}).get("removed") or []
    if removed:
        print(f"\n(guard removed {len(removed)} unsupported sentence(s))")
    return 0


def cmd_assistant_eval(args) -> int:
    from . import assistant_eval

    if args.freeze:
        dev_path, _ = assistant_eval._paths(args.version, "dev")
        dev = json.loads(dev_path.read_text(encoding="utf-8"))
        if dev["identity"] != assistant_eval.current_identity(args.version):
            print("dev report was produced by a different configuration; rerun --split dev first")
            return 1
        print(json.dumps(assistant_eval.freeze(dev, args.version), indent=2))
        return 0
    r = assistant_eval.run(args.split, rerun_reason=args.rerun_reason, version=args.version)
    print(json.dumps(r["summary"], indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fraudinv")
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("verify", help="verify archive/CSV checksums")
    v.add_argument("--extract", action="store_true", help="extract the CSV if missing")
    v.set_defaults(func=cmd_verify)
    i = sub.add_parser("ingest", help="build typed Parquet with source_row")
    i.add_argument("--force", action="store_true")
    i.set_defaults(func=cmd_ingest)
    a = sub.add_parser("audit", help="run the Day 1 data-quality audit")
    a.add_argument("--memory-limit", default="2GB")
    a.add_argument("--threads", type=int, default=4)
    a.add_argument("--skip-verify", action="store_true")
    a.set_defaults(func=cmd_audit)
    e = sub.add_parser("evaluate-dev", help="Day 2 baselines on validation only")
    e.set_defaults(func=cmd_evaluate_dev)
    sub.add_parser("features", help="build the label-free history feature table").set_defaults(func=cmd_features)
    sub.add_parser("select", help="Day 3 selection on validation").set_defaults(func=cmd_select)
    sub.add_parser("freeze", help="refit, verify and freeze the champion").set_defaults(func=cmd_freeze)
    ft = sub.add_parser("final-test", help="one-time test evaluation of the frozen selection")
    ft.add_argument("--rerun-reason", default=None, help="required if a final report already exists")
    ft.set_defaults(func=cmd_final_test)
    sub.add_parser("db-env", help="create .env with random local DB passwords").set_defaults(func=cmd_db_env)
    sub.add_parser("db-migrate", help="apply sql/*.sql, roles and grants").set_defaults(func=cmd_db_migrate)
    rc = sub.add_parser("replay-create", help="create a replay run with full prior warm-up")
    rc.add_argument("--run-id", required=True)
    rc.add_argument("--first-step", type=int, required=True)
    rc.add_argument("--last-step", type=int, required=True)
    rc.add_argument("--capacity", type=int, default=100)
    rc.set_defaults(func=cmd_replay_create)
    rr = sub.add_parser("replay-run", help="replay (or resume) a run from its committed cursor")
    rr.add_argument("--run-id", required=True)
    rr.add_argument("--max-steps", type=int, default=None)
    rr.set_defaults(func=cmd_replay_run)
    sub.add_parser("day4-check", help="real-data interruption/consistency check").set_defaults(func=cmd_day4_check)
    aa = sub.add_parser("analyst-add", help="create a demo analyst and write a bearer token file")
    aa.add_argument("analyst_id")
    aa.add_argument("--name", required=True)
    aa.set_defaults(func=cmd_analyst_add)
    eb = sub.add_parser("evidence-backfill", help="itemize earlier records for a run's cases (idempotent)")
    eb.add_argument("--run-id", required=True)
    eb.set_defaults(func=cmd_evidence_backfill)
    er = sub.add_parser("evaluate-run", help="evaluator-only aggregate metrics for a run's queue")
    er.add_argument("--run-id", required=True)
    er.set_defaults(func=cmd_evaluate_run)
    ask = sub.add_parser("assistant-ask", help="ask the bounded local assistant about one case")
    ask.add_argument("case_id")
    ask.add_argument("question")
    ask.set_defaults(func=cmd_assistant_ask)
    ae = sub.add_parser("assistant-eval", help="run dev/holdout assistant evaluation, or --freeze after dev")
    ae.add_argument("--split", choices=["dev", "holdout"], default="dev")
    ae.add_argument("--freeze", action="store_true")
    ae.add_argument("--rerun-reason", default=None)
    ae.add_argument("--version", choices=["v1", "v2"], default="v2")
    ae.set_defaults(func=cmd_assistant_eval)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
