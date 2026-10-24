"""Dry-run by default; explicit local SQLite target and reviewed fingerprint."""
import argparse
from contextlib import closing
import datetime as dt
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from services.phase5_cleanup import apply_plan, build_plan, connect_readonly


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect", help="Fingerprint returned by dry-run")
    args = parser.parse_args()
    database = args.database.absolute()
    if database.is_symlink() or not database.is_file():
        parser.error("Database must be an existing regular file, not a symlink")
    uploads = PROJECT_ROOT / "static/uploads/submissions"
    with closing(connect_readonly(database)) as connection:
        plan = build_plan(connection, uploads)
    public = {key: value for key, value in plan.items() if key != "state"}
    if not args.apply:
        print(json.dumps(public, ensure_ascii=False, indent=2))
        return 1 if plan["blockers"] else 0
    if not args.expect:
        parser.error("--apply requires --expect from a reviewed dry-run")
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = PROJECT_ROOT / "backups" / ("phase5-" + timestamp)
    result = apply_plan(database, uploads, folder / "before.sqlite3", args.expect)
    if result["status"] == "applied":
        manifest = folder / "manifest.json"
        with manifest.open("x", encoding="utf-8") as handle:
            json.dump({"database": str(database), "plan": public, "result": result}, handle, indent=2)
        manifest.chmod(0o600)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print("Cleanup stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
