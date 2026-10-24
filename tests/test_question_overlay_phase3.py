"""Bounded Phase-3 contracts for bank detail scope tabs and source metadata."""

from __future__ import annotations

import os
import json
import re
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)

import config  # noqa: E402

config.load_local_environment = lambda *args, **kwargs: None

from app import app  # noqa: E402
from database import db  # noqa: E402
from models import BankQuestion, BankQuestionOption, QuestionBank, User  # noqa: E402
from services.access_control import (  # noqa: E402
    BANK_VISIBILITY_PRIVATE,
    BANK_VISIBILITY_SHARED,
    QUESTION_SCOPE_PRIVATE,
    QUESTION_SCOPE_SHARED,
)


class QuestionOverlayPhase3Tests(unittest.TestCase):
    @staticmethod
    def rendered_questions(body):
        # Inspect the actual client payload instead of relying on translated
        # labels surviving Jinja's safe Unicode JSON escaping.
        return json.loads(re.search(r'questions:\s*(\[.*?\]),\s*csrfToken:', body, re.S).group(1))

    @staticmethod
    def rendered_scope_counts(body):
        return {scope: int(value) for scope, value in re.findall(r'scope=(all|common|mine)[^"]*"[^>]*>[^<]*<span>(\d+)</span>', body)}

    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        self.admin = User(username="overlay3-admin", user_code="O3A", fullname="Admin", role="admin")
        self.teacher = User(username="overlay3-teacher", user_code="O3T", fullname="Teacher", role="teacher")
        self.other = User(username="overlay3-other", user_code="O3O", fullname="Other", role="teacher")
        db.session.add_all([self.admin, self.teacher, self.other])
        db.session.flush()
        self.shared = QuestionBank(
            name="Overlay 3 shared", subject="Toán", created_by=self.admin.id,
            visibility=BANK_VISIBILITY_SHARED,
        )
        self.private = QuestionBank(
            name="Overlay 3 private", subject="Toán", created_by=self.teacher.id,
            visibility=BANK_VISIBILITY_PRIVATE,
        )
        db.session.add_all([self.shared, self.private])
        db.session.flush()
        self.common = self.add_question(
            self.shared, self.admin, "Common source text", scope=QUESTION_SCOPE_SHARED,
            grade="8", difficulty="nhan_biet",
        )
        self.mine = self.add_question(
            self.shared, self.admin, "Teacher private source text", scope=QUESTION_SCOPE_PRIVATE,
            owner=self.teacher, grade="9", difficulty="van_dung",
        )
        self.foreign = self.add_question(
            self.shared, self.admin, "Foreign private secret", scope=QUESTION_SCOPE_PRIVATE,
            owner=self.other, grade="7", difficulty="van_dung_cao",
        )
        # A NULL row created by a teacher in an explicit shared bank resolves
        # to that teacher's private contribution, without changing storage.
        self.legacy_mine = self.add_question(
            self.shared, self.teacher, "Legacy teacher contribution", scope=None,
            grade="9", difficulty="thong_hieu",
        )
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

    def add_question(self, bank, creator, text, *, scope, owner=None, grade="8", difficulty="nhan_biet", qtype="single"):
        row = BankQuestion(
            bank_id=bank.id,
            created_by=creator.id,
            question_text=text,
            question_type=qtype,
            difficulty_level=difficulty,
            grade=grade,
            scope=scope,
            private_owner_id=owner.id if owner else None,
        )
        db.session.add(row)
        db.session.flush()
        for index, value in enumerate(("A", "B", "C", "D")):
            db.session.add(BankQuestionOption(
                question_id=row.id,
                option_text=value,
                is_correct=index == 0,
                order_index=index,
            ))
        return row

    def test_teacher_tabs_are_authorized_and_legacy_private_is_mine(self):
        self.login(self.teacher)
        body = self.client.get(f"/question-banks/{self.shared.id}?scope=all").get_data(as_text=True)
        self.assertIn(self.common.question_text, body)
        self.assertIn(self.mine.question_text, body)
        self.assertIn(self.legacy_mine.question_text, body)
        self.assertNotIn(self.foreign.question_text, body)
        self.assertIn("Câu riêng của tôi", body)
        labels = {row['source_label'] for row in self.rendered_questions(body)}
        self.assertIn("Dùng chung", labels)
        self.assertIn("Riêng tư — chỉ bạn", labels)
        # Authorized tab totals are 3 all, 1 common, and 2 private; the
        # foreign private row cannot affect any teacher-visible count.
        self.assertEqual(self.rendered_scope_counts(body), {'all': 3, 'common': 1, 'mine': 2})

        mine_body = self.client.get(f"/question-banks/{self.shared.id}?scope=mine").get_data(as_text=True)
        self.assertNotIn(self.common.question_text, mine_body)
        self.assertNotIn(self.foreign.question_text, mine_body)
        self.assertIn(self.mine.question_text, mine_body)
        self.assertIn(self.legacy_mine.question_text, mine_body)

    def test_scope_stats_and_grade_facets_stay_stable_while_result_filter_changes(self):
        self.login(self.teacher)
        response = self.client.get(
            f"/question-banks/{self.shared.id}?scope=all&q=Common&type=single&grade=8"
        )
        body = response.get_data(as_text=True)
        self.assertIn(self.common.question_text, body)
        self.assertNotIn(self.mine.question_text, body)
        self.assertNotIn(self.foreign.question_text, body)
        # Stats/facets describe the all-authorized tab before filters: grade 8,
        # 9 and the private row's van_dung remain represented in the facets.
        self.assertRegex(body, r'<dt>Nhận biết</dt><dd>1</dd>')
        self.assertRegex(body, r'<dt>Thông hiểu</dt><dd>1</dd>')
        self.assertRegex(body, r'<dt>Vận dụng</dt><dd>1</dd>')
        self.assertIn("1 câu phù hợp bộ lọc", body)
        self.assertIn('value="9"', body)

    def test_admin_audit_has_all_rows_and_never_uses_only_you_label(self):
        self.login(self.admin)
        body = self.client.get(f"/question-banks/{self.shared.id}?scope=all").get_data(as_text=True)
        for text in (self.common.question_text, self.mine.question_text, self.foreign.question_text, self.legacy_mine.question_text):
            self.assertIn(text, body)
        labels = {row['source_label'] for row in self.rendered_questions(body)}
        self.assertNotIn("Riêng tư — chỉ bạn", labels)
        self.assertIn("Riêng tư — giáo viên sở hữu", labels)
        self.assertIn("Đóng góp riêng (kiểm toán)", body)
        self.assertEqual(self.rendered_scope_counts(body)['all'], 4)

        private_body = self.client.get(f"/question-banks/{self.shared.id}?scope=mine").get_data(as_text=True)
        self.assertNotIn(self.common.question_text, private_body)
        self.assertIn(self.mine.question_text, private_body)
        self.assertIn(self.foreign.question_text, private_body)

    def test_invalid_scope_and_filter_never_widen_authorized_dataset(self):
        self.login(self.teacher)
        invalid_scope = self.client.get(f"/question-banks/{self.shared.id}?scope=not-a-scope")
        invalid_body = invalid_scope.get_data(as_text=True)
        self.assertIn(self.common.question_text, invalid_body)
        self.assertIn(self.mine.question_text, invalid_body)
        self.assertNotIn(self.foreign.question_text, invalid_body)

        invalid_type = self.client.get(f"/question-banks/{self.shared.id}?scope=mine&type=not-a-type")
        invalid_type_body = invalid_type.get_data(as_text=True)
        self.assertNotIn(self.mine.question_text, invalid_type_body)
        self.assertNotIn(self.foreign.question_text, invalid_type_body)
        self.assertIn("0 câu phù hợp bộ lọc", invalid_type_body)

    def test_mutation_json_keeps_actor_source_and_edit_permissions(self):
        self.login(self.teacher)
        payload = self.mine.to_dict()
        payload["question_text"] = "Teacher private source updated"
        response = self.client.post(f"/questions/{self.mine.id}/update", json=payload)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        updated = response.get_json()["question"]
        self.assertTrue(updated["can_edit"])
        self.assertTrue(updated["can_delete"])
        self.assertEqual(updated["source"], "private")
        self.assertEqual(updated["source_label"], "Riêng tư — chỉ bạn")
        self.assertEqual(
            self.client.post(f"/questions/{self.common.id}/update", json=self.common.to_dict()).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
