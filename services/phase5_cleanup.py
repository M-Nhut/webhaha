"""Bounded SQLite cleanup. No Flask imports, environment loading or seed.

Only the verified local data shape is supported. Nonempty traditional or
unknown papers require a separately reviewed row migration, never a guess.
"""
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

RETIRED_TABLES = ("attendance", "schedule")


def connect_readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def snapshot(connection):
    """Fingerprint all retained content without exposing credentials/data."""
    result = {}
    for name, sql in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"):
        rows = Counter(hashlib.sha256(repr(tuple(row)).encode()).hexdigest()
                       for row in connection.execute("SELECT * FROM " + quoted(name)))
        result[name] = {"schema": sql, "rows": sum(rows.values()),
                       "digest": hashlib.sha256(json.dumps(sorted(rows.items())).encode()).hexdigest()}
    return result


def fingerprint(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def build_plan(connection, uploads):
    state = snapshot(connection)
    targets = {name: state[name]["rows"] for name in RETIRED_TABLES if name in state}
    blockers = []
    required = {"schedule": {"id", "course_id", "teacher_id", "weekday"},
                "attendance": {"id", "student_id", "course_id", "status"}}
    for name in targets:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(" + quoted(name) + ")")}
        if not required[name] <= columns:
            blockers.append("Unexpected retired schema: " + name)
    for name in state:
        for edge in connection.execute("PRAGMA foreign_key_list(" + quoted(name) + ")"):
            if edge[2] in targets and name not in targets:
                blockers.append("Retained foreign key to retired table: " + name)
    if targets and connection.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
        blockers.append("Triggers/views require dependency review")
    if "exam" in state:
        columns = {row[1] for row in connection.execute('PRAGMA table_info("exam")')}
        if not {"exam_type", "assessment_purpose"} <= columns:
            blockers.append("Assessment schema needs explicit migration")
        elif connection.execute("SELECT 1 FROM exam WHERE COALESCE(exam_type,'')!='practice' AND COALESCE(assessment_purpose,'')!='initial_diagnostic' LIMIT 1").fetchone():
            blockers.append("Traditional/unknown papers need a reviewed row migration")
    if uploads.is_symlink() or (uploads.exists() and any(uploads.iterdir())):
        blockers.append("Submission directory requires file ownership/archive review")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        blockers.append("Pre-existing foreign key violations")
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        blockers.append("Database integrity failed")
    return {"targets": targets, "blockers": blockers, "fingerprint": fingerprint(state), "state": state}


def apply_plan(database, uploads, backup, expected):
    """Fresh backup, locked revalidation, exact drops and content comparison."""
    with closing(connect_readonly(database)) as source:
        plan = build_plan(source, uploads)
        if plan["blockers"] or plan["fingerprint"] != expected:
            raise ValueError("Blocked or changed data; run dry-run again")
        if not plan["targets"]:
            return {"status": "no_changes", "removed": {}}
        backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with backup.open("xb"):
            pass
        backup.chmod(0o600)
        with closing(sqlite3.connect(str(backup))) as destination:
            source.backup(destination)
        with closing(connect_readonly(backup)) as saved:
            if saved.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity failed")
            backup_state = snapshot(saved)
        if fingerprint(backup_state) != expected:
            raise ValueError("Data changed while backing up; nothing removed")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=rw", uri=True)) as live:
        live.execute("PRAGMA foreign_keys=ON")
        live.execute("BEGIN IMMEDIATE")
        try:
            current = build_plan(live, uploads)
            if current["blockers"] or current["fingerprint"] != expected:
                raise ValueError("Data changed before apply; nothing removed")
            for name in RETIRED_TABLES:
                if name in current["targets"]:
                    live.execute("DROP TABLE " + quoted(name))
            retained = {name: value for name, value in backup_state.items() if name not in current["targets"]}
            if snapshot(live) != retained or live.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Retained data or integrity changed; rolling back")
            if live.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Integrity failed; rolling back")
            live.commit()
        except Exception:
            live.rollback()
            raise
    return {"status": "applied", "removed": current["targets"], "backup": str(backup)}
