"""Explicit local migration for the audited, pre-submission chapter correction.

No application imports or environment loading. Dry-run first; an apply requires
the exact fingerprint and creates a private SQLite backup before any writes.
Historical submitted papers need a separate migration; this script refuses them.
"""
import argparse
from contextlib import closing
import datetime as dt
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.phase5_cleanup import connect_readonly, fingerprint, snapshot

SOURCE = re.compile(r"^9C6([NHVC])4-([1-8])([DTS])\.([1-9]\d*)$")
SCOPES = {f"9C6-4-{i}": f"9C8-i-{i}" for i in range(1, 9)}
CHANGED_TABLES = {"bank_question", "curriculum_node", "id6_counter", "import_session"}


def mapped(value):
    """Translate identity fields in metadata; never rewrite question content."""
    if isinstance(value, dict):
        return {SCOPES.get(key, key): mapped(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mapped(item) for item in value]
    if isinstance(value, str):
        if value in SCOPES:
            return SCOPES[value]
        match = SOURCE.fullmatch(value)
        if match:
            level, category, kind, sequence = match.groups()
            return f"9C8{level}i-{category}{kind}.{sequence}"
    return value


def json_metadata(value):
    if not value:
        return value
    return json.dumps(mapped(json.loads(value)), ensure_ascii=False)


def plan(connection):
    connection.row_factory = sqlite3.Row
    state = snapshot(connection)
    old_nodes = list(connection.execute("SELECT * FROM curriculum_node WHERE grade='9' AND chapter_code='6' AND lesson_code='4'"))
    old_questions = list(connection.execute("SELECT * FROM bank_question WHERE chapter='6' AND section='4'"))
    blocked = []
    if old_nodes or old_questions:
        if len(old_nodes) != 8 or {row["canonical_code"] for row in old_nodes} != set(SCOPES):
            blocked.append("Expected exactly eight original catalog nodes")
        if connection.execute("SELECT 1 FROM curriculum_node WHERE chapter_code='8' AND lesson_code='i' LIMIT 1").fetchone():
            blocked.append("Target catalog already exists; merge requires review")
        for table in ("exam", "exam_submission", "learning_history", "student_mastery", "error_observation", "question_skill"):
            if table in state and state[table]["rows"]:
                blocked.append("Historical/linked data requires review: " + table)
        for row in old_questions:
            if row["id6_scope"]:
                match = SOURCE.fullmatch(row["source_id"] or "")
                if row["id6_scope"] not in SCOPES or not match or int(match[4]) != row["id6_sequence"]:
                    blocked.append("Inconsistent existing question identity: " + str(row["id"]))
            elif row["source_id"]:
                blocked.append("Unclassified source ID requires review: " + str(row["id"]))
            for field in ("classification_data", "learning_metadata"):
                if row[field]:
                    try:
                        json.loads(row[field])
                    except ValueError:
                        blocked.append("Invalid historical metadata: " + str(row["id"]))
        if connection.execute("SELECT 1 FROM id6_counter WHERE scope LIKE '9C8-i-%' LIMIT 1").fetchone():
            blocked.append("Target counters already exist")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        blocked.append("Foreign key violations")
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        blocked.append("Integrity failure")
    return {"fingerprint": fingerprint(state), "catalog_nodes": len(old_nodes),
            "questions": len(old_questions), "source_ids": sum(bool(q["id6_scope"]) for q in old_questions),
            "blockers": blocked}, state, old_nodes, old_questions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect")
    args = parser.parse_args()
    database = args.database.absolute()
    if database.is_symlink() or not database.is_file():
        parser.error("Use an existing local database file, not a symlink")
    with closing(connect_readonly(database)) as connection:
        report, before, nodes, questions = plan(connection)
    if not args.apply:
        print(json.dumps(report, indent=2))
        return bool(report["blockers"])
    if not args.expect or report["blockers"] or report["fingerprint"] != args.expect:
        raise ValueError("Blocked or changed data; review dry-run before apply")
    if not nodes and not questions:
        print(json.dumps({"status": "no_changes"}))
        return 0
    catalog = json.loads((ROOT / "services/data/math9_curriculum.json").read_text())
    targets = {str(row["category_code"]): row for row in catalog
               if row.get("grade") == "9" and row.get("chapter_code") == "8" and row.get("lesson_code") == "i"}
    if set(targets) != {str(i) for i in range(1, 9)}:
        raise ValueError("Updated chapter8 i catalog must be deployed before migration")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = ROOT / "backups" / ("chapter8-i-" + stamp)
    folder.mkdir(mode=0o700)
    backup = folder / "before.sqlite3"
    with backup.open("xb"):
        pass
    backup.chmod(0o600)
    with closing(connect_readonly(database)) as source, closing(sqlite3.connect(backup)) as destination:
        source.backup(destination)
    with closing(connect_readonly(backup)) as saved:
        if fingerprint(snapshot(saved)) != args.expect or saved.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup validation failed or data changed")
    with closing(sqlite3.connect(database.as_uri() + "?mode=rw", uri=True)) as live:
        live.execute("PRAGMA foreign_keys=ON")
        live.execute("BEGIN IMMEDIATE")
        try:
            current, state, nodes, questions = plan(live)
            if current["fingerprint"] != args.expect or current["blockers"]:
                raise ValueError("Database changed before migration")
            fields = ("grade", "chapter_code", "chapter_name", "lesson_code", "lesson_name", "category_code",
                      "category_name", "is_advanced", "catalog_version", "topic_code", "topic_name")
            for node in nodes:
                target = targets[node["category_code"]]
                live.execute("UPDATE curriculum_node SET " + ",".join(name + "=?" for name in fields) +
                             ",canonical_code=? WHERE id=?",
                             [target.get(name, node[name]) for name in fields] + [SCOPES[node["canonical_code"]], node["id"]])
            for question in questions:
                source_id = mapped(question["source_id"])
                original = question["original_source_id"] or question["source_id"]
                live.execute("UPDATE bank_question SET chapter='8',section='i',source_id=?,original_source_id=?,"
                             "id6_scope=?,classification_data=?,learning_metadata=? WHERE id=?",
                             (source_id, original, SCOPES.get(question["id6_scope"], question["id6_scope"]),
                              json_metadata(question["classification_data"]), json_metadata(question["learning_metadata"]), question["id"]))
            for old, new in SCOPES.items():
                live.execute("UPDATE id6_counter SET scope=? WHERE scope=?", (new, old))
            # Preserve original file and parsed payload for audit. A preview
            # from the old scope must not be confirmed under new ID semantics.
            cancelled = live.execute("UPDATE import_session SET status='cancelled' WHERE status='preview'").rowcount
            after = snapshot(live)
            if set(after) != set(before) or any(after[t] != before[t] for t in before if t not in CHANGED_TABLES):
                raise ValueError("Unexpected changes outside identity metadata")
            if any(after[t]["rows"] != before[t]["rows"] for t in CHANGED_TABLES):
                raise ValueError("Migration unexpectedly changed row counts")
            if live.execute("PRAGMA foreign_key_check").fetchone() or live.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Database integrity failed")
            live.commit()
        except Exception:
            live.rollback()
            raise
    receipt = {**report, "status": "applied", "cancelled_old_previews": cancelled,
               "backup": str(backup), "protected_tables_unchanged": len(before) - len(CHANGED_TABLES)}
    with (folder / "manifest.json").open("x") as handle:
        json.dump(receipt, handle, indent=2)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, sqlite3.Error) as error:
        print("Migration stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
