"""Dry-run by default; safely backfill historical question-bank visibility.

The script requires one explicit existing SQLite database path.  It never
loads the Flask app or an environment file.  Use ``--shared-bank-id`` one or
more times only after an administrator has reviewed that exact legacy bank.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sqlite3
import sys
from contextlib import closing


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.bank_visibility_phase5 import (  # noqa: E402
    apply_plan,
    build_plan,
    connect_readonly,
    public_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="One existing regular SQLite database file.",
    )
    parser.add_argument(
        "--shared-bank-id",
        dest="shared_bank_ids",
        action="append",
        type=int,
        default=[],
        help="Explicitly map one reviewed admin-owned NULL bank to shared; repeat as needed.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the reviewed plan after validating --expect.",
    )
    parser.add_argument(
        "--expect",
        help="Exact database_fingerprint returned by the matching dry-run.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Directory for before.sqlite3 and manifest.json (default: backups/bank-visibility-phase5-<UTC>).",
    )
    return parser


def _database_path(parser: argparse.ArgumentParser, value: Path) -> Path:
    candidate = value.expanduser()
    if candidate.is_symlink() or not candidate.is_file():
        parser.error("Database must be an existing regular file, not a symlink")
    return candidate.resolve()


def main(argv=None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    database = _database_path(parser, args.database)
    try:
        with closing(connect_readonly(database)) as connection:
            plan = build_plan(connection, args.shared_bank_ids)
    except (OSError, ValueError, sqlite3.DatabaseError) as error:
        parser.error(str(error))

    public = public_plan(plan)
    if not args.apply:
        print(json.dumps(public, ensure_ascii=False, indent=2))
        # A pending admin mapping is intentionally a review stop, even though
        # unambiguous teacher updates may still be listed in the same report.
        return 1 if public["status"] in {"blocked", "review_required"} else 0

    if not args.expect:
        parser.error("--apply requires --expect from a reviewed dry-run")
    if str(args.expect) != str(public["database_fingerprint"]):
        parser.error("--expect must match the fresh dry-run fingerprint")

    if args.backup_dir:
        backup_dir = args.backup_dir.expanduser()
    else:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_dir = PROJECT_ROOT / "backups" / ("bank-visibility-phase5-" + stamp)
    backup_file = backup_dir / "before.sqlite3"

    try:
        result = apply_plan(
            database,
            backup_file,
            args.expect,
            args.shared_bank_ids,
        )
    except (OSError, ValueError, sqlite3.DatabaseError) as error:
        print("Migration stopped: " + str(error), file=sys.stderr)
        return 1

    if result["status"] == "applied":
        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        manifest = backup_dir / "manifest.json"
        with manifest.open("x", encoding="utf-8") as handle:
            json.dump(
                {
                    "database": str(database),
                    "plan": public,
                    "result": result,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        manifest.chmod(0o600)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("after_status", result["status"]) in {"blocked", "review_required"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
