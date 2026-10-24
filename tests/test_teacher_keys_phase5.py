"""Focused, provider-free coverage for the teacher-key Phase 5 migration."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.teacher_keys_phase5 import (
    FIXED_MODEL,
    apply_plan,
    build_plan,
    connect_readonly,
    public_plan,
)


class TeacherKeysPhase5Tests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "keys.sqlite3"
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE "user" (id INTEGER PRIMARY KEY);
            CREATE TABLE teacher_ai_key_group (
                id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL,
                name TEXT NOT NULL, model_name TEXT NOT NULL,
                is_active INTEGER NOT NULL, is_default INTEGER NOT NULL,
                config_revision INTEGER NOT NULL, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE teacher_ai_key (
                id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL,
                encrypted_key TEXT NOT NULL, key_fingerprint TEXT NOT NULL,
                key_hint TEXT NOT NULL, project_ref TEXT NOT NULL, label TEXT,
                sort_order INTEGER NOT NULL, is_paused INTEGER NOT NULL,
                last_tested_at TEXT, last_test_status TEXT, last_error_code TEXT,
                created_at TEXT, updated_at TEXT,
                UNIQUE(group_id, key_fingerprint),
                FOREIGN KEY(group_id) REFERENCES teacher_ai_key_group(id)
            );
            CREATE TABLE course (
                id INTEGER PRIMARY KEY, teacher_id INTEGER, ai_key_group_id INTEGER
            );
            CREATE TABLE class_ai_analysis_run (
                id INTEGER PRIMARY KEY, course_id INTEGER,
                ai_key_group_id INTEGER, model_name TEXT
            );
            """
        )
        connection.executemany('INSERT INTO "user" (id) VALUES (?)', [(1,), (2,)])
        connection.executemany(
            "INSERT INTO teacher_ai_key_group VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (1, 1, "oldest", "old-model", 1, 1, 2, "2026-01-01", "2026-01-01"),
                (2, 1, "legacy-referenced", "legacy-model", 1, 0, 1, "2026-01-02", "2026-01-02"),
                (3, 1, "legacy-unreferenced", "legacy-model", 0, 0, 1, "2026-01-03", "2026-01-03"),
                (4, 2, "other-owner", "old-model", 1, 1, 1, "2026-01-01", "2026-01-01"),
            ],
        )
        connection.executemany(
            "INSERT INTO teacher_ai_key VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (1, 1, "CIPHERTEXT-A", "fp-shared", "1111", "project-a", None, 0, 0, "2026-01-01", "ok", None, "2026-01-01", "2026-01-01"),
                (2, 2, "CIPHERTEXT-B", "fp-shared", "1111", "project-b", None, 1, 1, "2026-01-02", "failed", "invalid_or_revoked", "2026-01-02", "2026-01-02"),
                (3, 3, "CIPHERTEXT-C", "fp-unique", "3333", "project-c", None, 0, 0, "2026-01-03", "ok", None, "2026-01-03", "2026-01-03"),
                (4, 4, "CIPHERTEXT-D", "fp-shared", "4444", "project-d", None, 0, 0, "2026-01-01", "ok", None, "2026-01-01", "2026-01-01"),
            ],
        )
        connection.execute("INSERT INTO course VALUES (1,1,2)")
        connection.execute("INSERT INTO class_ai_analysis_run VALUES (9,1,2,'legacy-model')")
        connection.commit()
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _plan(self):
        with connect_readonly(self.database) as connection:
            return build_plan(connection)

    def test_dry_run_is_non_mutating_and_hides_key_material(self):
        before = self.database.read_bytes()
        plan = self._plan()
        after = self.database.read_bytes()
        self.assertEqual(before, after)
        self.assertEqual(plan["owners"][0]["canonical_group_id"], 1)
        self.assertEqual(plan["counts"]["groups_to_archive"], 1)
        self.assertEqual(plan["counts"]["groups_to_delete"], 1)
        self.assertEqual(plan["counts"]["keys_to_delete"], 1)
        self.assertEqual(plan["counts"]["keys_to_move"], 1)
        dumped = json.dumps(public_plan(plan), ensure_ascii=False)
        self.assertNotIn("CIPHERTEXT", dumped)
        self.assertNotIn("fp-shared", dumped)

    def test_apply_merges_same_owner_only_and_preserves_referenced_archive(self):
        plan = self._plan()
        backup = Path(self.tempdir.name) / "before.sqlite3"
        result = apply_plan(self.database, backup, plan["database_fingerprint"])
        self.assertEqual(result["status"], "applied")
        with connect_readonly(self.database) as connection:
            groups = {row[0]: row for row in connection.execute(
                "SELECT id,owner_id,model_name,is_active,is_default FROM teacher_ai_key_group"
            )}
            self.assertEqual(groups[1][2], FIXED_MODEL)
            self.assertEqual(tuple(groups[2][2:]), ("legacy-model", 0, 0))
            self.assertNotIn(3, groups)
            keys = [tuple(row) for row in connection.execute(
                "SELECT group_id,key_fingerprint,is_paused,last_test_status FROM teacher_ai_key ORDER BY id"
            )]
            self.assertEqual(keys, [(1, "fp-shared", 1, "failed"), (1, "fp-unique", 1, "ok"), (4, "fp-shared", 0, "ok")])
            self.assertIsNone(connection.execute("SELECT ai_key_group_id FROM course WHERE id=1").fetchone()[0])
            self.assertEqual(connection.execute("SELECT ai_key_group_id FROM class_ai_analysis_run WHERE id=9").fetchone()[0], 2)
            self.assertEqual(build_plan(connection)["status"], "no_changes")
        with connect_readonly(backup) as saved:
            self.assertEqual(saved.execute("SELECT model_name FROM teacher_ai_key_group WHERE id=1").fetchone()[0], "old-model")
            self.assertEqual(saved.execute("SELECT ai_key_group_id FROM course WHERE id=1").fetchone()[0], 2)

    def test_wrong_fingerprint_refuses_without_creating_backup(self):
        plan = self._plan()
        backup = Path(self.tempdir.name) / "should-not-exist.sqlite3"
        with self.assertRaises(ValueError):
            apply_plan(self.database, backup, "wrong-fingerprint")
        self.assertFalse(backup.exists())
        self.assertEqual(self._plan()["database_fingerprint"], plan["database_fingerprint"])

    def test_empty_fingerprint_is_a_review_blocker(self):
        connection = sqlite3.connect(self.database)
        connection.execute("UPDATE teacher_ai_key SET key_fingerprint='' WHERE id=1")
        connection.commit()
        connection.close()
        plan = self._plan()
        self.assertTrue(any("empty fingerprint" in item for item in plan["blockers"]))
        self.assertEqual(plan["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
