"""Focused Phase-2 contracts for teacher-owned shared-bank overlays."""

from __future__ import annotations

import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)

import config  # noqa: E402

config.load_local_environment = lambda *args, **kwargs: None

from app import app  # noqa: E402
from database import db  # noqa: E402
from models import BankQuestion, BankQuestionOption, ImportSession, QuestionBank, User  # noqa: E402
from services.access_control import (  # noqa: E402
    BANK_VISIBILITY_PRIVATE,
    BANK_VISIBILITY_SHARED,
    QUESTION_SCOPE_PRIVATE,
    QUESTION_SCOPE_SHARED,
    can_add_question,
    can_delete_bank,
    can_edit_bank,
    can_import_questions,
    new_question_scope,
    set_new_question_scope,
)
from services.import_duplicates import scan_duplicates  # noqa: E402
from services.import_scope import save_scope  # noqa: E402
from services.import_service import ImportService  # noqa: E402


SCOPE = {
    "grade": "9",
    "chapters": ["8"],
    "lessons": ["8:i"],
    "topics": ["thong_ke_xac_suat"],
}


def question(text="Một đồng xu có xác suất ra mặt ngửa bằng bao nhiêu?"):
    return {
        "index": 1,
        "question_text": text,
        "question_type": "single",
        "source_id": "9C8Ni-1T.1",
        "grade": "Lớp 9",
        "chapter": "8",
        "section": "i",
        "question_category": "1",
        "options": [
            {"text": "1/2", "is_correct": True},
            {"text": "1/3", "is_correct": False},
            {"text": "1/4", "is_correct": False},
            {"text": "1", "is_correct": False},
        ],
        "statements": [],
        "difficulty_level": "nhan_biet",
        "points": 1,
        "formulas": {},
    }


class QuestionOverlayPhase2Tests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        from services.curriculum_service import seed_math9_catalog

        seed_math9_catalog()
        self.admin = User(
            username="overlay-admin", user_code="OA", fullname="Admin", role="admin"
        )
        self.teacher = User(
            username="overlay-teacher", user_code="OT", fullname="Teacher", role="teacher"
        )
        self.other = User(
            username="overlay-other", user_code="OO", fullname="Other", role="teacher"
        )
        db.session.add_all([self.admin, self.teacher, self.other])
        db.session.flush()
        self.shared = QuestionBank(
            name="Shared", subject="Toán", created_by=self.admin.id,
            visibility=BANK_VISIBILITY_SHARED,
        )
        self.private = QuestionBank(
            name="Teacher private", subject="Toán", created_by=self.teacher.id,
            visibility=BANK_VISIBILITY_PRIVATE,
        )
        db.session.add_all([self.shared, self.private])
        db.session.commit()
        self.client = app.test_client()
        self.login(self.teacher)

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

    def add_row(self, bank, creator, *, scope, owner=None, text="Một đồng xu có xác suất ra mặt ngửa bằng bao nhiêu?"):
        row = BankQuestion(
            bank_id=bank.id,
            created_by=creator.id,
            question_text=text,
            question_type="single",
            scope=scope,
            private_owner_id=owner.id if owner else None,
        )
        db.session.add(row)
        db.session.flush()
        for index, value in enumerate(("1/2", "1/3", "1/4", "1")):
            db.session.add(BankQuestionOption(
                question_id=row.id,
                option_text=value,
                is_correct=index == 0,
                order_index=index,
            ))
        db.session.flush()
        return row

    def preview(self, user, bank, row=None):
        session = ImportSession(
            user_id=user.id,
            bank_id=bank.id,
            filename="overlay.tex",
            file_type="tex",
            status="preview",
        )
        session.set_parsed_questions([row or question()])
        db.session.add(session)
        db.session.commit()
        # Match the upload/preview boundary: source tags are materialized into
        # explicit curriculum metadata before scope validation and review.
        from services.id6_metadata import enrich_preview
        enrich_preview(session, commit=False)
        save_scope(session, SCOPE)
        return session

    def test_shared_bank_add_is_separate_from_bank_edit_and_stamps_private_owner(self):
        self.assertFalse(can_edit_bank(self.teacher, self.shared))
        self.assertTrue(can_add_question(self.teacher, self.shared))
        self.assertTrue(can_import_questions(self.teacher, self.shared))
        self.assertFalse(can_delete_bank(self.teacher, self.shared))

        row = BankQuestion(
            bank_id=self.shared.id,
            created_by=self.teacher.id,
            question_text="Teacher overlay",
            question_type="single",
        )
        self.assertEqual(new_question_scope(self.teacher, self.shared), QUESTION_SCOPE_PRIVATE)
        set_new_question_scope(row, self.teacher, self.shared)
        self.assertEqual((row.scope, row.private_owner_id), (QUESTION_SCOPE_PRIVATE, self.teacher.id))

        admin_row = BankQuestion(
            bank_id=self.shared.id,
            created_by=self.admin.id,
            question_text="Administrator common",
            question_type="single",
            scope=QUESTION_SCOPE_PRIVATE,
            private_owner_id=self.other.id,
        )
        set_new_question_scope(admin_row, self.admin, self.shared)
        self.assertEqual((admin_row.scope, admin_row.private_owner_id), (QUESTION_SCOPE_SHARED, None))

    def test_teacher_manual_add_shared_creates_private_overlay_without_enabling_shared_edit(self):
        from models import CurriculumNode

        node = CurriculumNode.query.filter_by(chapter_code="8", category_code="1").first()
        response = self.client.post(
            f"/question-banks/{self.shared.id}/questions/add",
            data={
                "question_text": "Câu riêng của giáo viên",
                "question_type": "single",
                "difficulty_level": "nhan_biet",
                "curriculum_node_id": str(node.id),
                "option_text": ["A", "B", "C", "D"],
                "correct_option": "0",
                "reviewed": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        row = BankQuestion.query.one()
        self.assertEqual((row.scope, row.private_owner_id), (QUESTION_SCOPE_PRIVATE, self.teacher.id))
        self.assertFalse(can_edit_bank(self.teacher, self.shared))

        body = self.client.get(f"/question-banks/{self.shared.id}").get_data(as_text=True)
        self.assertIn(f'href="/question-banks/import?bank_id={self.shared.id}"', body)
        self.assertIn("Thêm câu riêng", body)
        payload = self.client.get(f"/api/question-banks/{self.shared.id}/questions/{row.id}").get_json()
        self.assertEqual(payload['question']['source_label'], "Riêng tư — chỉ bạn")
        self.assertIn("canEdit: false", body)

        self.login(self.other)
        other_body = self.client.get(f"/question-banks/{self.shared.id}").get_data(as_text=True)
        self.assertNotIn("Câu riêng của giáo viên", other_body)

    def test_duplicate_scan_is_actor_scoped_and_admin_common_does_not_match_private_overlay(self):
        shared_row = self.add_row(self.shared, self.admin, scope=QUESTION_SCOPE_SHARED, text="Shared content")
        own_row = self.add_row(self.shared, self.admin, scope=QUESTION_SCOPE_PRIVATE, owner=self.teacher, text="Teacher-only content")
        foreign_row = self.add_row(self.shared, self.admin, scope=QUESTION_SCOPE_PRIVATE, owner=self.other, text="Foreign-only content")
        db.session.commit()

        teacher_session = self.preview(self.teacher, self.shared, question("Teacher-only content"))
        teacher_report = scan_duplicates(teacher_session, teacher_session.get_parsed_questions(), actor=self.teacher, bank=self.shared)
        self.assertEqual(teacher_report["duplicate"], 1)
        matches = teacher_session.get_parsed_questions()[0]["duplicate"]["matches"]
        self.assertEqual([match["bank_question_id"] for match in matches], [own_row.id])
        self.assertNotIn(foreign_row.id, [match["bank_question_id"] for match in matches])

        admin_session = self.preview(self.admin, self.shared, question("Foreign-only content"))
        admin_report = scan_duplicates(admin_session, admin_session.get_parsed_questions(), actor=self.admin, bank=self.shared)
        self.assertEqual(admin_report["duplicate"], 0)
        self.assertEqual(admin_session.get_parsed_questions()[0]["duplicate"]["matches"], [])

        # The administrator still gets duplicate protection in an existing
        # private teacher bank, but that row is never treated as common.
        private_row = self.add_row(self.private, self.admin, scope=QUESTION_SCOPE_PRIVATE, owner=self.teacher, text="Private content")
        db.session.commit()
        private_session = self.preview(self.admin, self.private, question("Private content"))
        private_report = scan_duplicates(private_session, private_session.get_parsed_questions(), actor=self.admin, bank=self.private)
        self.assertEqual(private_report["duplicate"], 1)
        self.assertEqual(private_session.get_parsed_questions()[0]["duplicate"]["matches"][0]["bank_question_id"], private_row.id)

        legacy_private = QuestionBank(
            name="Legacy teacher private", subject="Toán", created_by=self.teacher.id,
            visibility=None,
        )
        db.session.add(legacy_private)
        db.session.flush()
        legacy_row = self.add_row(
            legacy_private, self.admin, scope=None, text="Legacy private content"
        )
        db.session.commit()
        legacy_session = self.preview(self.admin, legacy_private, question("Legacy private content"))
        legacy_report = scan_duplicates(
            legacy_session,
            legacy_session.get_parsed_questions(),
            actor=self.admin,
            bank=legacy_private,
        )
        self.assertEqual(legacy_report["duplicate"], 1)
        self.assertEqual(
            legacy_session.get_parsed_questions()[0]["duplicate"]["matches"][0]["bank_question_id"],
            legacy_row.id,
        )

    def test_import_stamps_teacher_overlay_and_admin_private_destination_owner(self):
        teacher_session = self.preview(self.teacher, self.shared, question("Teacher import"))
        teacher_token = teacher_session.get_duplicate_report()["revision"]
        teacher_receipt = ImportService.confirm_import(
            teacher_session.id,
            self.shared.id,
            self.teacher.id,
            confirmation_token=teacher_token,
        )
        self.assertEqual(teacher_receipt["imported_count"], 1)
        overlay = BankQuestion.query.filter_by(question_text="Teacher import").one()
        self.assertEqual((overlay.scope, overlay.private_owner_id), (QUESTION_SCOPE_PRIVATE, self.teacher.id))

        admin_session = self.preview(self.admin, self.private, question("Admin import into private"))
        admin_token = admin_session.get_duplicate_report()["revision"]
        admin_receipt = ImportService.confirm_import(
            admin_session.id,
            self.private.id,
            self.admin.id,
            confirmation_token=admin_token,
        )
        self.assertEqual(admin_receipt["imported_count"], 1)
        private_import = BankQuestion.query.filter_by(question_text="Admin import into private").one()
        self.assertEqual((private_import.scope, private_import.private_owner_id), (QUESTION_SCOPE_PRIVATE, self.teacher.id))

    def test_confirmation_audience_change_rejects_old_and_omitted_tokens(self):
        session = self.preview(self.teacher, self.shared, question("Audience changed"))
        old_token = session.get_duplicate_report()["revision"]

        # The actor is reloaded at confirmation time.  Promotion must not
        # silently turn the reviewed teacher-private overlay into shared data.
        self.teacher.role = "admin"
        db.session.commit()
        message = "Quyền hoặc phạm vi ngân hàng đã thay đổi"
        with self.assertRaisesRegex(ValueError, message):
            ImportService.confirm_import(
                session.id,
                self.shared.id,
                self.teacher.id,
                confirmation_token=old_token,
            )
        db.session.rollback()
        with self.assertRaisesRegex(ValueError, message):
            ImportService.confirm_import(session.id, self.shared.id, self.teacher.id)
        db.session.rollback()
        self.assertEqual(BankQuestion.query.count(), 0)

    def test_confirmed_receipt_and_preview_do_not_replay_private_matches(self):
        private_row = self.add_row(
            self.private,
            self.admin,
            scope=QUESTION_SCOPE_PRIVATE,
            owner=self.teacher,
            text="Historical private match",
        )
        db.session.commit()
        session = self.preview(self.admin, self.private, question("Historical private match"))
        token = session.get_duplicate_report()["revision"]
        receipt = ImportService.confirm_import(
            session.id,
            self.private.id,
            self.admin.id,
            confirmation_token=token,
        )
        self.assertEqual(receipt["rows"][0]["matches"][0]["bank_question_id"], private_row.id)

        # Ownership can change after the receipt was generated.  Cached
        # historical match payloads must not survive either service replay or
        # the confirmed preview response.
        private_row.private_owner_id = self.other.id
        db.session.commit()
        replay = ImportService.confirm_import(
            session.id,
            self.private.id,
            self.admin.id,
            confirmation_token=token,
        )
        self.assertEqual(replay["rows"][0]["matches"], [])

        self.login(self.admin)
        payload = self.client.get(f"/question-banks/import/{session.id}/preview")
        self.assertEqual(payload.status_code, 200, payload.json)
        self.assertEqual(payload.json["result"]["rows"][0]["matches"], [])


if __name__ == "__main__":
    unittest.main()
