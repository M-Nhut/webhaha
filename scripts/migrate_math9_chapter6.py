#!/usr/bin/env python3
"""Inspect, apply, or restore chapter 6 without importing app.py."""

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from services.curriculum_migration import (
    CatalogMigrationBlocked, apply_chapter6_migration, inspect_chapter6_migration,
    rollback_chapter6_migration,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    database = parser.add_mutually_exclusive_group(required=True)
    database.add_argument("--database", type=Path, help="Existing SQLite database file")
    database.add_argument("--database-url-env", help="Environment variable containing the database URL")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true", help="Read-only inventory (default)")
    action.add_argument("--apply", action="store_true")
    action.add_argument("--rollback", action="store_true")
    parser.add_argument("--expected-fingerprint", help="Reject apply if the reviewed dry-run plan changed")
    parser.add_argument("--report", type=Path, help="Save full UTF-8 JSON report")
    args = parser.parse_args()
    if args.report and args.database and args.report.resolve() == args.database.resolve():
        parser.error("Report must not overwrite the database.")
    if args.database:
        if not args.database.is_file():
            parser.error("SQLite database does not exist; this tool never creates the target database.")
        url = URL.create("sqlite", database=str(args.database.resolve()))
    else:
        url = os.environ.get(args.database_url_env)
        if not url:
            parser.error("Database URL environment variable is empty.")
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
    engine = create_engine(url)
    code = 0
    try:
        if args.apply:
            report = apply_chapter6_migration(engine, args.expected_fingerprint)
        elif args.rollback:
            report = rollback_chapter6_migration(engine)
        else:
            report = inspect_chapter6_migration(engine)
            code = 2 if report["blockers"] else 0
    except CatalogMigrationBlocked as exc:
        report, code = exc.report, 2
    finally:
        engine.dispose()
    output = json.dumps(report, ensure_ascii=False, indent=2, default=lambda value: value.isoformat())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
        print(json.dumps({"status": report["status"], "counts": report.get("counts"),
                          "blockers": [{"kind": b["kind"], "count": b["count"]} for b in report.get("blockers", [])],
                          "report": str(args.report.resolve())}, ensure_ascii=False))
    else:
        print(output)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
