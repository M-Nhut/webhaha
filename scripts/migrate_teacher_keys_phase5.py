"""Dry-run by default; migrate teacher-owned Gemini groups after review.

The command never loads the Flask app or a dotenv file.  It emits only
metadata/counts and a database fingerprint; key material is never printed.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import datetime as dt
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.teacher_keys_phase5 import (  # noqa: E402
    apply_plan,
    build_plan,
    connect_readonly,
    public_plan,
)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="One existing SQLite database file")
    parser.add_argument("--apply", action="store_true", help="Apply only after reviewing the dry-run fingerprint")
    parser.add_argument("--expect", help="Exact database_fingerprint returned by a reviewed dry-run")
    parser.add_argument(
        "--backup-dir", type=Path,
        help="Directory for before.sqlite3 and manifest.json (default: backups/teacher-keys-phase5-<UTC>)",
    )
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    database = args.database.expanduser()
    if database.is_symlink() or not database.is_file():
        parser.error("Database must be an existing regular file, not a symlink")

    with closing(connect_readonly(database)) as connection:
        plan = build_plan(connection)
    public = public_plan(plan)

    if not args.apply:
        print(json.dumps(public, ensure_ascii=False, indent=2))
        return 1 if public["blockers"] else 0
    if not args.expect:
        parser.error("--apply requires --expect from a reviewed dry-run")
    if args.expect != public["database_fingerprint"]:
        parser.error("--expect must match the fresh dry-run fingerprint")
    if public["blockers"]:
        parser.error("dry-run is blocked; no changes were made")
    if public["status"] == "no_changes":
        print(json.dumps({"status": "no_changes", "counts": public["counts"]}, ensure_ascii=False, indent=2))
        return 0

    if args.backup_dir:
        backup_dir = args.backup_dir.expanduser()
    else:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_dir = PROJECT_ROOT / "backups" / ("teacher-keys-phase5-" + stamp)
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_file = backup_dir / "before.sqlite3"
    result = apply_plan(database, backup_file, args.expect)
    manifest = backup_dir / "manifest.json"
    # ``public`` was created before the backup/apply and contains no private
    # internal planner state.  Never write the original plan object here.
    with manifest.open("x", encoding="utf-8") as handle:
        json.dump({"database": str(database.resolve()), "plan": public, "result": result}, handle, ensure_ascii=False, indent=2)
    manifest.chmod(0o600)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        # Exceptions from the migration are deliberately bounded and never
        # include row/ciphertext values.
        print("Migration stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)

