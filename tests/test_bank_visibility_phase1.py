"""Focused Phase 1 contracts for question-bank visibility and ownership."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)

# Prevent local dotenv overrides from redirecting destructive fixture setup
# away from the isolated in-memory database, including standalone test runs.
import config
config.load_local_environment = lambda *args, **kwargs: None

from app import app
from database import db
from models import QuestionBank, User
from services.access_control import (
    BANK_VISIBILITY_PRIVATE,
    BANK_VISIBILITY_SHARED,
    can_delete_bank,
    can_edit_bank,
    can_import_into_bank,
    can_use_bank,
    can_view_bank,
)


class BankVisibilityPolicyTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        self.assertEqual(str(db.engine.url), "sqlite:///:memory:")
        db.drop_all()
        db.create_all()
        self.admin = User(username="bank-admin", user_code="BVA", fullname="Admin", role="admin")
        self.owner = User(username="bank-owner", user_code="BVT", fullname="Owner", role="teacher")
        self.other = User(username="bank-other", user_code="BVO", fullname="Other", role="teacher")
        self.student = User(username="bank-student", user_code="BVS", fullname="Student", role="student")
        db.session.add_all([self.admin, self.owner, self.other, self.student])
        db.session.flush()
        self.shared = QuestionBank(
            name="Shared", subject="Toán", created_by=self.admin.id,
            visibility=BANK_VISIBILITY_SHARED,
        )
        self.private = QuestionBank(
            name="Private", subject="Toán", created_by=self.owner.id,
            visibility=BANK_VISIBILITY_PRIVATE,
        )
        self.legacy_private = QuestionBank(
            name="Legacy private", subject="Toán", created_by=self.owner.id,
        )
        self.legacy_admin = QuestionBank(
            name="Legacy admin", subject="Toán", created_by=self.admin.id,
        )
        db.session.add_all([self.shared, self.private, self.legacy_private, self.legacy_admin])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_shared_separates_read_use_from_mutation(self):
        self.assertTrue(can_view_bank(self.other, self.shared))
        self.assertTrue(can_use_bank(self.other, self.shared))
        self.assertFalse(can_edit_bank(self.other, self.shared))
        # Overlay Phase 2 permits appending private questions, not bank edits.
        self.assertTrue(can_import_into_bank(self.other, self.shared))
        self.assertFalse(can_delete_bank(self.other, self.shared))
        self.assertTrue(can_edit_bank(self.admin, self.shared))

    def test_private_and_legacy_teacher_rows_remain_owner_only(self):
        for bank in (self.private, self.legacy_private):
            self.assertTrue(can_view_bank(self.owner, bank))
            self.assertTrue(can_use_bank(self.owner, bank))
            self.assertTrue(can_edit_bank(self.owner, bank))
            self.assertTrue(can_import_into_bank(self.owner, bank))
            self.assertTrue(can_delete_bank(self.owner, bank))
            self.assertFalse(can_view_bank(self.other, bank))
            self.assertFalse(can_use_bank(self.other, bank))

    def test_legacy_admin_rows_and_unknown_creator_fail_closed_to_teachers(self):
        self.assertFalse(can_view_bank(self.other, self.legacy_admin))
        self.assertFalse(can_use_bank(self.other, self.legacy_admin))
        self.assertTrue(can_view_bank(self.admin, self.legacy_admin))

        unknown = QuestionBank(
            name="Unknown creator", subject="Toán", created_by=999999,
            visibility=BANK_VISIBILITY_SHARED,
        )
        db.session.add(unknown)
        db.session.commit()
        self.assertFalse(can_view_bank(self.other, unknown))
        self.assertFalse(can_use_bank(self.other, unknown))
        self.assertTrue(can_edit_bank(self.admin, unknown))
        self.assertFalse(can_view_bank(self.student, self.shared))

    def test_new_bank_visibility_is_server_owned_for_create_route(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.admin.id)
            session["_fresh"] = True
        response = client.post(
            "/question-banks/new",
            data={"name": "Admin bank", "subject": "Toán", "visibility": "private"},
        )
        self.assertEqual(response.status_code, 302)
        admin_bank = QuestionBank.query.filter_by(name="Admin bank").one()
        self.assertEqual(admin_bank.visibility, BANK_VISIBILITY_SHARED)

        with client.session_transaction() as session:
            session["_user_id"] = str(self.owner.id)
            session["_fresh"] = True
        # Flask-Login may retain the previous LocalProxy in the request
        # context; ensure the second request resolves the teacher account.
        from flask import g
        g.pop("_login_user", None)
        client.post(
            "/question-banks/new",
            data={"name": "Teacher bank", "subject": "Toán", "visibility": "shared"},
        )
        teacher_bank = QuestionBank.query.filter_by(name="Teacher bank").one()
        self.assertEqual(teacher_bank.visibility, BANK_VISIBILITY_PRIVATE)

    def test_shared_bank_direct_read_is_allowed_but_edit_route_is_not(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.other.id)
            session["_fresh"] = True
        self.assertEqual(client.get(f"/question-banks/{self.shared.id}").status_code, 200)
        self.assertEqual(client.get(f"/question-banks/{self.shared.id}/edit").status_code, 403)
        self.assertEqual(
            client.post(
                f"/question-banks/{self.shared.id}/questions/add",
                data={"question_text": "Không được sửa"},
            ).status_code,
            302,  # Authoring is allowed; this incomplete payload is rejected.
        )


class BankVisibilitySchemaMigrationTests(unittest.TestCase):
    def test_additive_migration_preserves_null_rows_and_is_repeatable(self):
        from scripts.migrate_bank_visibility_phase1 import migrate

        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "bank.db"
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    "CREATE TABLE question_bank (id INTEGER PRIMARY KEY, created_by INTEGER NOT NULL)"
                )
                connection.execute("INSERT INTO question_bank (id, created_by) VALUES (1, 7)")
                connection.commit()
            self.assertTrue(migrate(database_path))
            self.assertFalse(migrate(database_path))
            with sqlite3.connect(database_path) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(question_bank)")}
                value = connection.execute("SELECT visibility FROM question_bank WHERE id = 1").fetchone()[0]
                self.assertIn("visibility", columns)
                self.assertIsNone(value)


if __name__ == "__main__":
    unittest.main()
