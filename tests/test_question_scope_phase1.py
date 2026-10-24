"""Focused Phase-1 contracts for question-level scope and IDOR guards."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)

import config
config.load_local_environment = lambda *args, **kwargs: None

from app import app
from database import db
from models import BankQuestion, Course, QuestionBank, User
from services.access_control import (
    BANK_VISIBILITY_PRIVATE,
    BANK_VISIBILITY_SHARED,
    QUESTION_SCOPE_PRIVATE,
    QUESTION_SCOPE_SHARED,
    can_delete_question,
    can_edit_question,
    can_use_question_for_class,
    can_use_question,
    can_view_question,
)


class QuestionScopePolicyTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        self.assertEqual(str(db.engine.url), "sqlite:///:memory:")
        db.drop_all()
        db.create_all()
        self.admin = User(username="qscope-admin", user_code="QSA", fullname="Admin", role="admin")
        self.owner = User(username="qscope-owner", user_code="QSO", fullname="Owner", role="teacher")
        self.other = User(username="qscope-other", user_code="QST", fullname="Other", role="teacher")
        self.student = User(username="qscope-student", user_code="QSS", fullname="Student", role="student")
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
        self.legacy_shared = QuestionBank(
            name="Legacy shared", subject="Toán", created_by=self.admin.id,
            visibility=None,
        )
        db.session.add_all([self.shared, self.private, self.legacy_shared])
        db.session.flush()
        self.shared_q = self._question(self.shared, self.admin, scope=QUESTION_SCOPE_SHARED)
        self.overlay_q = self._question(
            self.shared, self.admin, scope=QUESTION_SCOPE_PRIVATE, private_owner=self.owner,
        )
        self.private_q = self._question(
            self.private, self.admin, scope=QUESTION_SCOPE_PRIVATE, private_owner=self.owner,
        )
        self.foreign_q = self._question(
            self.shared, self.admin, scope=QUESTION_SCOPE_PRIVATE, private_owner=self.other,
        )
        self.legacy_shared_q = self._question(self.shared, self.admin)
        self.legacy_teacher_q = self._question(self.shared, self.owner)
        self.legacy_private_q = self._question(self.private, self.admin)
        db.session.commit()

    def _question(self, bank, creator, *, scope=None, private_owner=None):
        row = BankQuestion(
            bank_id=bank.id,
            question_text=(
                f"Question {bank.name} {creator.username} "
                f"{private_owner.username if private_owner else '-'} {scope}"
            ),
            question_type="single",
            created_by=creator.id,
            scope=scope,
            private_owner_id=private_owner.id if private_owner else None,
        )
        db.session.add(row)
        db.session.flush()
        return row

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_shared_private_and_class_use_matrix(self):
        self.assertTrue(can_view_question(self.other, self.shared_q))
        self.assertTrue(can_use_question(self.other, self.shared_q))
        self.assertFalse(can_edit_question(self.other, self.shared_q))
        self.assertFalse(can_delete_question(self.other, self.shared_q))

        for row in (self.overlay_q,):
            self.assertTrue(can_view_question(self.owner, row))
            self.assertTrue(can_use_question(self.owner, row))
            self.assertTrue(can_edit_question(self.owner, row))
            self.assertTrue(can_delete_question(self.owner, row))
            self.assertFalse(can_view_question(self.other, row))
            self.assertFalse(can_use_question(self.other, row))
            self.assertFalse(can_edit_question(self.other, row))

        self.assertTrue(can_view_question(self.owner, self.private_q))
        self.assertFalse(can_view_question(self.other, self.private_q))
        self.assertTrue(can_view_question(self.admin, self.foreign_q))
        self.assertTrue(can_edit_question(self.admin, self.foreign_q))
        self.assertFalse(can_view_question(self.student, self.shared_q))
        self.assertFalse(can_use_question(self.admin, None, bank=self.shared))

        owner_course = Course(course_name="Owner class", subject="Toán", teacher_id=self.owner.id)
        other_course = Course(course_name="Other class", subject="Toán", teacher_id=self.other.id)
        student_course = Course(course_name="Student class", subject="Toán", teacher_id=self.student.id)
        self.assertTrue(can_use_question_for_class(owner_course, self.overlay_q))
        self.assertFalse(can_use_question_for_class(other_course, self.overlay_q))
        self.assertFalse(can_use_question_for_class(student_course, self.overlay_q))

    def test_legacy_resolution_never_widens_and_mismatches_fail_closed(self):
        # The old admin-owned row in an explicit shared bank is compatible with
        # shared access; a teacher-created legacy row remains private to them.
        self.assertTrue(can_view_question(self.other, self.legacy_shared_q))
        self.assertTrue(can_view_question(self.owner, self.legacy_teacher_q))
        self.assertFalse(can_view_question(self.other, self.legacy_teacher_q))
        self.assertTrue(can_view_question(self.owner, self.legacy_private_q))
        self.assertFalse(can_view_question(self.other, self.legacy_private_q))

        # A private owner from another teacher cannot be authorized by passing
        # a different bank object to the policy helper.
        self.assertFalse(can_view_question(self.owner, self.foreign_q, bank=self.private))
        self.assertFalse(can_edit_question(self.owner, self.foreign_q, bank=self.private))

        malformed = self._question(self.shared, self.admin, scope="not-a-scope")
        missing_owner = self._question(self.shared, self.admin, scope=QUESTION_SCOPE_PRIVATE)
        unresolved_owner = self._question(self.shared, self.admin, scope=None)
        unresolved_owner.private_owner_id = 999999
        db.session.commit()
        self.assertFalse(can_view_question(self.owner, malformed))
        self.assertFalse(can_view_question(self.owner, missing_owner))
        self.assertFalse(can_view_question(self.owner, unresolved_owner))
        self.assertTrue(can_view_question(self.admin, malformed))

    def test_detail_filters_foreign_private_question(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.owner.id)
            session["_fresh"] = True
        response = client.get(f"/question-banks/{self.shared.id}")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn(self.overlay_q.question_text, body)
        self.assertNotIn(self.foreign_q.question_text, body)

        with client.session_transaction() as session:
            session["_user_id"] = str(self.other.id)
            session["_fresh"] = True
        from flask import g
        g.pop("_login_user", None)
        response = client.get(f"/question-banks/{self.shared.id}")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertNotIn(self.overlay_q.question_text, body)
        self.assertIn(self.foreign_q.question_text, body)

    def test_direct_question_mutations_reject_foreign_private_row(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.owner.id)
            session["_fresh"] = True
        self.assertEqual(
            client.post(f"/questions/{self.foreign_q.id}/update", json={}).status_code,
            403,
        )
        self.assertEqual(
            client.post(f"/questions/{self.foreign_q.id}/toggle-answer", json={}).status_code,
            403,
        )
        self.assertEqual(
            client.post(f"/questions/{self.foreign_q.id}/delete").status_code,
            403,
        )
        self.assertEqual(
            client.post(
                f"/question-banks/{self.shared.id}/questions/{self.foreign_q.id}/adaptive",
                data={"adaptive_priority": "10"},
            ).status_code,
            403,
        )


class QuestionScopeSchemaMigrationTests(unittest.TestCase):
    def test_additive_migration_preserves_null_rows_and_is_repeatable(self):
        from scripts.migrate_question_scope_phase1 import migrate

        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "bank.db"
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    "CREATE TABLE bank_question (id INTEGER PRIMARY KEY, bank_id INTEGER NOT NULL, created_by INTEGER NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO bank_question (id, bank_id, created_by) VALUES (1, 4, 7)"
                )
                connection.commit()
            self.assertTrue(migrate(database_path))
            self.assertFalse(migrate(database_path))
            with sqlite3.connect(database_path) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(bank_question)")}
                scope, owner = connection.execute(
                    "SELECT scope, private_owner_id FROM bank_question WHERE id = 1"
                ).fetchone()
            self.assertIn("scope", columns)
            self.assertIn("private_owner_id", columns)
            self.assertIsNone(scope)
            self.assertIsNone(owner)


if __name__ == "__main__":
    unittest.main()
