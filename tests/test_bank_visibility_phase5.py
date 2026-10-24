"""Focused, provider-free tests for the bank visibility Phase 5 migration."""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest

from services.bank_visibility_phase5 import (
    apply_plan,
    build_plan,
    connect_readonly,
    public_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_SCRIPT = PROJECT_ROOT / "scripts" / "migrate_bank_visibility_phase5.py"


class BankVisibilityPhase5Tests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "tutoring.sqlite3"
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE "user" (
                id INTEGER PRIMARY KEY,
                role TEXT
            );
            CREATE TABLE question_bank (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_by INTEGER,
                visibility TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE exam (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL
            );
            CREATE TABLE exam_question (
                id INTEGER PRIMARY KEY,
                exam_id INTEGER NOT NULL,
                question_text TEXT NOT NULL
            );
            CREATE TABLE exam_submission (
                id INTEGER PRIMARY KEY,
                exam_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                status TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            'INSERT INTO "user" (id, role) VALUES (?, ?)',
            [
                (1, "teacher"),
                (2, "admin"),
                (3, "student"),
                (4, "coordinator"),
            ],
        )
        connection.executemany(
            "INSERT INTO question_bank (id, name, created_by, visibility, is_active) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "Legacy teacher", 1, None, 1),
                (2, "Legacy admin", 2, None, 1),
                (3, "Explicit shared", 2, "shared", 1),
                (4, "Explicit private", 1, "private", 1),
                (5, "Orphan", 999, None, 1),
                (6, "Unsupported owner", 3, None, 1),
                (7, "Invalid scope", 1, "team", 1),
                (8, "Explicit orphan", 999, "shared", 1),
                (9, "Unsupported explicit", 4, "private", 1),
            ],
        )
        # These rows represent frozen historical artifacts.  They must remain
        # byte-for-byte unchanged by a bank-scope backfill.
        connection.execute("INSERT INTO exam (id, title) VALUES (10, 'Frozen paper')")
        connection.execute(
            "INSERT INTO exam_question (id, exam_id, question_text) VALUES (11, 10, 'Frozen question')"
        )
        connection.execute(
            "INSERT INTO exam_submission (id, exam_id, student_id, status) VALUES (12, 10, 50, 'graded')"
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _plan(self, shared_bank_ids=()):
        with closing(connect_readonly(self.database)) as connection:
            return build_plan(connection, shared_bank_ids)

    def _run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(MIGRATION_SCRIPT), "--database", str(self.database), *arguments],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def _cli_json(self, result):
        self.assertTrue(result.stdout, result.stderr)
        return json.loads(result.stdout)

    def test_dry_run_reports_each_legacy_boundary_without_mutating(self):
        before = self.database.read_bytes()
        plan = self._plan()
        after = self.database.read_bytes()

        self.assertEqual(before, after)
        self.assertEqual(plan["status"], "review_required")
        self.assertEqual(plan["review"]["admin_null_pending_bank_ids"], [2])
        self.assertEqual(plan["preserved"]["missing_owner_null_bank_ids"], [5])
        self.assertEqual(plan["preserved"]["unsupported_role_null_bank_ids"], [6])
        self.assertEqual(plan["preserved"]["invalid_visibility_bank_ids"], [7])
        self.assertEqual(plan["preserved"]["explicit_shared_bank_ids"], [3, 8])
        self.assertEqual(plan["preserved"]["explicit_private_bank_ids"], [4, 9])
        self.assertEqual(plan["counts"]["teacher_null_to_private"], 1)
        self.assertEqual(plan["counts"]["admin_null_pending_review"], 1)
        dumped = json.dumps(public_plan(plan), ensure_ascii=False)
        self.assertNotIn("Frozen question", dumped)
        self.assertNotIn("Legacy teacher", dumped)

    def test_apply_unambiguous_rows_leaves_admin_and_fail_closed_rows_untouched(self):
        plan = self._plan()
        backup = Path(self.tempdir.name) / "backup-unambiguous.sqlite3"
        result = apply_plan(self.database, backup, plan["database_fingerprint"])
        self.assertEqual(result["status"], "applied")
        self.assertTrue(backup.is_file())

        with closing(connect_readonly(self.database)) as connection:
            scopes = dict(
                connection.execute(
                    "SELECT id, visibility FROM question_bank ORDER BY id"
                ).fetchall()
            )
            self.assertEqual(scopes[1], "private")
            self.assertIsNone(scopes[2])
            self.assertEqual(scopes[3], "shared")
            self.assertEqual(scopes[4], "private")
            self.assertIsNone(scopes[5])
            self.assertIsNone(scopes[6])
            self.assertEqual(scopes[7], "team")
            self.assertEqual(scopes[8], "shared")
            self.assertEqual(scopes[9], "private")
            self.assertEqual(
                connection.execute("SELECT title FROM exam WHERE id=10").fetchone()[0],
                "Frozen paper",
            )
            self.assertEqual(
                connection.execute("SELECT question_text FROM exam_question WHERE id=11").fetchone()[0],
                "Frozen question",
            )
            self.assertEqual(
                connection.execute("SELECT status FROM exam_submission WHERE id=12").fetchone()[0],
                "graded",
            )
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
            )
            self.assertFalse(connection.execute("PRAGMA foreign_key_check").fetchone())

    def test_explicit_admin_mapping_is_scoped_and_idempotent(self):
        plan = self._plan([2])
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["review"]["admin_mapping_bank_ids"], [2])
        self.assertEqual(plan["review"]["admin_null_pending_bank_ids"], [])
        backup = Path(self.tempdir.name) / "backup-mapped.sqlite3"
        result = apply_plan(
            self.database,
            backup,
            plan["database_fingerprint"],
            [2],
        )
        self.assertEqual(result["status"], "applied")
        with closing(connect_readonly(self.database)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT visibility FROM question_bank WHERE id=2"
                ).fetchone()[0],
                "shared",
            )
            rerun = build_plan(connection, [2])
            self.assertEqual(rerun["status"], "no_changes")
            self.assertEqual(rerun["review"]["already_shared_mapping_bank_ids"], [2])
        second_backup = Path(self.tempdir.name) / "should-not-be-created.sqlite3"
        second = apply_plan(
            self.database,
            second_backup,
            rerun["database_fingerprint"],
            [2],
        )
        self.assertEqual(second["status"], "no_changes")
        self.assertFalse(second_backup.exists())

    def test_mapping_requires_existing_admin_null_bank_and_never_overrides_scope(self):
        for bank_id in (1, 4, 5, 7, 999):
            with self.subTest(bank_id=bank_id):
                plan = self._plan([bank_id])
                self.assertEqual(plan["status"], "blocked")
                self.assertTrue(plan["blockers"])

    def test_wrong_fingerprint_refuses_without_backup(self):
        plan = self._plan([2])
        backup = Path(self.tempdir.name) / "wrong-fingerprint.sqlite3"
        with self.assertRaises(ValueError):
            apply_plan(self.database, backup, "not-the-fingerprint", [2])
        self.assertFalse(backup.exists())
        self.assertEqual(self._plan([2])["database_fingerprint"], plan["database_fingerprint"])

    def test_failed_write_rolls_back_and_retains_verified_backup(self):
        plan = self._plan([2])
        connection = sqlite3.connect(self.database)
        connection.execute(
            """
            CREATE TRIGGER reject_phase5_update
            BEFORE UPDATE OF visibility ON question_bank
            WHEN NEW.id = 1
            BEGIN
                SELECT RAISE(ABORT, 'test migration rejection');
            END
            """
        )
        connection.commit()
        connection.close()
        # The trigger is part of the reviewed state, so refresh the plan.
        plan = self._plan([2])
        backup = Path(self.tempdir.name) / "backup-rollback.sqlite3"
        with self.assertRaises(sqlite3.DatabaseError):
            apply_plan(self.database, backup, plan["database_fingerprint"], [2])
        self.assertTrue(backup.is_file())
        with closing(connect_readonly(self.database)) as connection:
            self.assertIsNone(
                connection.execute(
                    "SELECT visibility FROM question_bank WHERE id=1"
                ).fetchone()[0]
            )
            self.assertIsNone(
                connection.execute(
                    "SELECT visibility FROM question_bank WHERE id=2"
                ).fetchone()[0]
            )
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
            )
        with closing(connect_readonly(backup)) as saved:
            self.assertEqual(
                saved.execute("PRAGMA integrity_check").fetchone()[0], "ok"
            )
            self.assertIsNone(
                saved.execute(
                    "SELECT visibility FROM question_bank WHERE id=1"
                ).fetchone()[0]
            )

    def test_cli_dry_run_is_read_only_and_pending_review_is_nonzero(self):
        before = self.database.read_bytes()
        result = self._run_cli()

        self.assertEqual(result.returncode, 1, result.stderr)
        report = self._cli_json(result)
        self.assertEqual(report["status"], "review_required")
        self.assertEqual(report["review"]["admin_null_pending_bank_ids"], [2])
        self.assertEqual(report["counts"]["teacher_null_to_private"], 1)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertFalse((Path(self.tempdir.name) / "backup").exists())

    def test_cli_apply_requires_expect_without_writing(self):
        before = self.database.read_bytes()
        backup_dir = Path(self.tempdir.name) / "would-be-backup"
        result = self._run_cli(
            "--shared-bank-id", "2",
            "--apply",
            "--backup-dir", str(backup_dir),
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("--apply requires --expect", result.stderr)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertFalse(backup_dir.exists())

    def test_cli_missing_or_invalid_database_path_never_creates_file(self):
        missing = Path(self.tempdir.name) / "missing.sqlite3"
        missing_result = subprocess.run(
            [sys.executable, str(MIGRATION_SCRIPT), "--database", str(missing)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(missing_result.returncode, 2)
        self.assertIn("existing regular file", missing_result.stderr)
        self.assertFalse(missing.exists())

        invalid = Path(self.tempdir.name) / "database-directory"
        invalid.mkdir()
        invalid_result = subprocess.run(
            [sys.executable, str(MIGRATION_SCRIPT), "--database", str(invalid)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(invalid_result.returncode, 2)
        self.assertIn("existing regular file", invalid_result.stderr)
        self.assertTrue(invalid.is_dir())

    def test_cli_explicit_mapping_applies_with_verified_backup_and_manifest(self):
        dry_run = self._run_cli("--shared-bank-id", "2")
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        plan = self._cli_json(dry_run)
        self.assertEqual(plan["status"], "ready")

        backup_dir = Path(self.tempdir.name) / "approved-backup"
        applied = self._run_cli(
            "--shared-bank-id", "2",
            "--apply",
            "--expect", plan["database_fingerprint"],
            "--backup-dir", str(backup_dir),
        )

        self.assertEqual(applied.returncode, 0, applied.stderr)
        result = self._cli_json(applied)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["after_status"], "no_changes")
        backup = backup_dir / "before.sqlite3"
        manifest = backup_dir / "manifest.json"
        self.assertTrue(backup.is_file())
        self.assertTrue(manifest.is_file())
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(manifest.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(backup_dir.stat().st_mode), 0o700)

        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest_data["plan"]["status"], "ready")
        self.assertEqual(manifest_data["result"]["status"], "applied")
        self.assertNotIn("Legacy teacher", json.dumps(manifest_data, ensure_ascii=False))
        with closing(connect_readonly(self.database)) as connection:
            scopes = dict(
                connection.execute(
                    "SELECT id, visibility FROM question_bank ORDER BY id"
                ).fetchall()
            )
            self.assertEqual(scopes[1], "private")
            self.assertEqual(scopes[2], "shared")

        with closing(connect_readonly(backup)) as saved:
            self.assertEqual(saved.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertIsNone(
                saved.execute(
                    "SELECT visibility FROM question_bank WHERE id=1"
                ).fetchone()[0]
            )
            self.assertIsNone(
                saved.execute(
                    "SELECT visibility FROM question_bank WHERE id=2"
                ).fetchone()[0]
            )

    def test_cli_replay_is_idempotent_and_scope_isolation_is_preserved(self):
        dry_run = self._run_cli("--shared-bank-id", "2")
        plan = self._cli_json(dry_run)
        approved_backup_dir = Path(self.tempdir.name) / "first-backup"
        applied = self._run_cli(
            "--shared-bank-id", "2",
            "--apply",
            "--expect", plan["database_fingerprint"],
            "--backup-dir", str(approved_backup_dir),
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)

        replay_dry_run = self._run_cli("--shared-bank-id", "2")
        self.assertEqual(replay_dry_run.returncode, 0, replay_dry_run.stderr)
        replay_plan = self._cli_json(replay_dry_run)
        self.assertEqual(replay_plan["status"], "no_changes")
        self.assertEqual(replay_plan["review"]["already_shared_mapping_bank_ids"], [2])

        second_backup_dir = Path(self.tempdir.name) / "replay-backup"
        replay_apply = self._run_cli(
            "--shared-bank-id", "2",
            "--apply",
            "--expect", replay_plan["database_fingerprint"],
            "--backup-dir", str(second_backup_dir),
        )
        self.assertEqual(replay_apply.returncode, 0, replay_apply.stderr)
        replay_result = self._cli_json(replay_apply)
        self.assertEqual(replay_result["status"], "no_changes")
        self.assertFalse(second_backup_dir.exists())

        with closing(connect_readonly(self.database)) as connection:
            scopes = dict(
                connection.execute(
                    "SELECT id, visibility FROM question_bank ORDER BY id"
                ).fetchall()
            )
            # Only the unambiguous teacher row and explicitly approved admin
            # row changed.  Existing scopes and fail-closed legacy rows remain.
            self.assertEqual(
                scopes,
                {
                    1: "private",
                    2: "shared",
                    3: "shared",
                    4: "private",
                    5: None,
                    6: None,
                    7: "team",
                    8: "shared",
                    9: "private",
                },
            )


if __name__ == "__main__":
    unittest.main()
