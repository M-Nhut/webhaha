"""Focused Phase 3 contracts for visible/read-only question-bank pages."""

from __future__ import annotations

import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)
import config  # noqa: E402
config.load_local_environment = lambda project_root=config.PROJECT_ROOT: None

from app import app  # noqa: E402
from database import db  # noqa: E402
from models import BankQuestion, QuestionBank, User  # noqa: E402
from services.access_control import BANK_VISIBILITY_PRIVATE, BANK_VISIBILITY_SHARED  # noqa: E402


class BankListPhase3Tests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        self.admin = User(username="list-admin", user_code="L3A", fullname="Admin", role="admin")
        self.teacher = User(username="list-teacher", user_code="L3T", fullname="Teacher", role="teacher")
        self.other = User(username="list-other", user_code="L3O", fullname="Other", role="teacher")
        self.student = User(username="list-student", user_code="L3S", fullname="Student", role="student")
        db.session.add_all([self.admin, self.teacher, self.other, self.student])
        db.session.flush()
        self.shared = QuestionBank(name="Shared admin", subject="Toán", created_by=self.admin.id,
                                   visibility=BANK_VISIBILITY_SHARED)
        self.private = QuestionBank(name="My private", subject="Toán", created_by=self.teacher.id,
                                    visibility=BANK_VISIBILITY_PRIVATE)
        self.legacy = QuestionBank(name="My legacy", subject="Toán", created_by=self.teacher.id)
        self.other_private = QuestionBank(name="Other private", subject="Toán", created_by=self.other.id,
                                          visibility=BANK_VISIBILITY_PRIVATE)
        self.legacy_admin = QuestionBank(name="Legacy admin", subject="Toán", created_by=self.admin.id)
        db.session.add_all([self.shared, self.private, self.legacy, self.other_private, self.legacy_admin])
        db.session.flush()
        self.shared_question = BankQuestion(
            bank_id=self.shared.id, created_by=self.admin.id,
            question_text="Shared question", question_type="single",
        )
        db.session.add(self.shared_question)
        db.session.commit()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def login(self, user):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        from flask import g
        g.pop("_login_user", None)

    def test_teacher_list_separates_shared_and_owned_legacy_banks(self):
        self.login(self.teacher)
        body = self.client.get("/question-banks").get_data(as_text=True)
        self.assertIn("Ngân hàng dùng chung", body)
        self.assertIn("Ngân hàng của tôi", body)
        for name in (self.shared.name, self.private.name, self.legacy.name):
            self.assertIn(name, body)
        for name in (self.other_private.name, self.legacy_admin.name):
            self.assertNotIn(name, body)

    def test_shared_detail_is_read_only_in_the_rendered_page_and_js_config(self):
        self.login(self.teacher)
        response = self.client.get(f"/question-banks/{self.shared.id}")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        for marker in ("Import thêm câu", "Phân loại ID6"):
            self.assertNotIn(marker, body)
        self.assertIn("canEdit: false", body)
        self.assertIn("canAdd: true", body)
        self.assertIn(f'href="/question-banks/import?bank_id={self.shared.id}"', body)
        self.assertIn("data-add-question-open", body)
        self.assertIn("canEditQuestion(q)", body)
        self.assertIn("Shared question", body)

    def test_shared_bank_mutation_urls_and_json_apis_are_forbidden(self):
        self.login(self.teacher)
        self.assertEqual(self.client.get(f"/question-banks/{self.shared.id}/edit").status_code, 403)
        self.assertEqual(self.client.post(f"/question-banks/{self.shared.id}/delete").status_code, 403)
        self.assertEqual(self.client.post(f"/question-banks/{self.shared.id}/questions/add", data={"question_text": "x"}).status_code, 302)
        self.assertEqual(BankQuestion.query.count(), 1)  # Invalid append saved nothing.
        self.assertEqual(self.client.post(f"/question-banks/{self.shared.id}/questions/{self.shared_question.id}/adaptive").status_code, 403)
        self.assertEqual(self.client.post(f"/questions/{self.shared_question.id}/update", json={}).status_code, 403)
        self.assertEqual(self.client.post(f"/questions/{self.shared_question.id}/toggle-answer", json={}).status_code, 403)

    def test_student_cannot_open_bank_or_question_mutation_endpoints(self):
        self.login(self.student)
        self.assertEqual(self.client.get(f"/question-banks/{self.shared.id}").status_code, 302)
        self.assertEqual(self.client.post(f"/questions/{self.shared_question.id}/toggle-answer", json={}).status_code, 302)


if __name__ == "__main__":
    unittest.main()
