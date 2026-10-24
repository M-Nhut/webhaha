"""Adversarial source/manifest contracts for Phase 4.

These tests intentionally stay on an in-memory SQLite database and exercise
only the resolver boundary.  They do not call providers or require a
production schema.
"""

from __future__ import annotations

import json
import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)

import config  # noqa: E402

config.load_local_environment = lambda *args, **kwargs: None

from app import app  # noqa: E402
from database import db  # noqa: E402
from models import (  # noqa: E402
    BankQuestion,
    Course,
    Exam,
    ExamQuestion,
    PracticeSession,
    QuestionBank,
    User,
)
from services.access_control import (  # noqa: E402
    BANK_VISIBILITY_PRIVATE,
    BANK_VISIBILITY_SHARED,
    QUESTION_SCOPE_PRIVATE,
    QUESTION_SCOPE_SHARED,
)
from services.source_resolver import (  # noqa: E402
    attach_source_manifest,
    resolve_class_banks,
    resolve_class_questions,
    validate_exam_source,
)


class SourceResolverPhase4Tests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()

        self.admin = User(username="p4-src-admin", user_code="P4SA", fullname="Admin", role="admin")
        self.former = User(username="p4-src-former", user_code="P4SF", fullname="Former", role="teacher")
        self.teacher = User(username="p4-src-teacher", user_code="P4ST", fullname="Current", role="teacher")
        db.session.add_all((self.admin, self.former, self.teacher))
        db.session.flush()

        self.course = Course(course_name="Lớp nguồn", subject="Toán", teacher_id=self.teacher.id)
        self.shared = QuestionBank(
            name="Shared", subject="Toán", grade="Lớp 9",
            created_by=self.admin.id, visibility=BANK_VISIBILITY_SHARED,
        )
        self.former_private = QuestionBank(
            name="Former private", subject="Toán", grade="9",
            created_by=self.former.id, visibility=BANK_VISIBILITY_PRIVATE,
        )
        self.teacher_private = QuestionBank(
            name="Current private", subject="Toán", grade="9",
            created_by=self.teacher.id, visibility=BANK_VISIBILITY_PRIVATE,
        )
        db.session.add_all((self.course, self.shared, self.former_private, self.teacher_private))
        db.session.flush()
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _question(self, bank, *, scope=QUESTION_SCOPE_SHARED, owner=None, label="q"):
        question = BankQuestion(
            bank_id=bank.id,
            question_text=label,
            question_type="single",
            difficulty_level="nhan_biet",
            created_by=self.admin.id if scope == QUESTION_SCOPE_SHARED else (owner or self.teacher).id,
            scope=scope,
            private_owner_id=owner.id if owner else None,
            source_id=f"src-{label}",
            content_revision=1,
            content_hash=f"hash-{label}",
        )
        db.session.add(question)
        db.session.flush()
        return question

    def _exam(self, questions, *, course=None, bank_ids=None, session=None):
        course = course or self.course
        bank_ids = list(bank_ids or sorted({question.bank_id for question in questions}))
        metadata = {"student_id": 9001}
        if session:
            metadata["practice_session_id"] = session.id
        exam = Exam(
            title="Frozen paper", course_id=course.id, created_by=self.teacher.id,
            question_bank_id=bank_ids[0], exam_type="practice", is_active=True,
            adaptive_metadata=json.dumps(metadata),
        )
        db.session.add(exam)
        db.session.flush()
        pairs = []
        for index, bank_question in enumerate(questions):
            copied = ExamQuestion(
                exam_id=exam.id, bank_question_id=bank_question.id,
                question_text=bank_question.question_text, question_type="single",
                points=1, order_index=index,
                source_id6=bank_question.source_id,
                source_content_revision=bank_question.content_revision,
                source_content_hash=bank_question.content_hash,
            )
            db.session.add(copied)
            db.session.flush()
            pairs.append((copied, bank_question))
        attach_source_manifest(exam, course, pairs, bank_ids=bank_ids)
        db.session.flush()
        return exam

    def test_grade_alias_and_invalid_ids_are_not_skipped(self):
        self.assertTrue(resolve_class_banks(self.course, [self.shared.id])["valid"])
        malformed = resolve_class_banks(self.course, [self.shared.id, "not-an-id"])
        self.assertFalse(malformed["valid"])
        self.assertEqual(malformed["reason"], "bank_ids_invalid")
        self.assertFalse(resolve_class_banks(self.course, [self.shared.id, 0])["valid"])
        self.assertEqual(
            resolve_class_banks(self.course, [self.shared.id, self.shared.id])["reason"],
            "bank_ids_duplicate",
        )

    def test_question_resolver_keeps_current_teacher_overlay_only(self):
        common = self._question(self.shared, label="common")
        current_overlay = self._question(
            self.shared, scope=QUESTION_SCOPE_PRIVATE, owner=self.teacher, label="current"
        )
        former_overlay = self._question(
            self.shared, scope=QUESTION_SCOPE_PRIVATE, owner=self.former, label="former"
        )
        db.session.commit()
        resolved = resolve_class_questions(
            self.course, [self.shared.id], [common, current_overlay, former_overlay]
        )
        self.assertEqual({question.id for question in resolved["questions"]}, {common.id, current_overlay.id})

    def test_malformed_manifest_never_falls_back_to_legacy(self):
        exam = Exam(
            title="Malformed", course_id=self.course.id, created_by=self.teacher.id,
            question_bank_id=self.shared.id, exam_type="practice", is_active=True,
            source_manifest="{not json",
        )
        db.session.add(exam)
        db.session.flush()
        state = validate_exam_source(exam, require_live=True)
        self.assertFalse(state["valid"])
        self.assertFalse(state["legacy"])
        self.assertEqual(state["reason"], "manifest_malformed")

        exam.source_manifest = json.dumps({"version": [], "items": [{"exam_question_id": []}]})
        nested = validate_exam_source(exam, require_live=True)
        self.assertFalse(nested["valid"])
        self.assertFalse(nested["legacy"])

    def test_frozen_snapshot_tamper_fails_live(self):
        question = self._question(self.shared, label="original")
        exam = self._exam([question], bank_ids=[self.shared.id])
        self.assertTrue(validate_exam_source(exam, require_live=True)["valid"])
        exam.questions[0].question_text = "tampered frozen text"
        tampered = validate_exam_source(exam, require_live=True)
        self.assertFalse(tampered["valid"])
        self.assertFalse(tampered["snapshot_valid"])
        self.assertEqual(tampered["reason"], "snapshot_mismatch")

    def test_live_bank_edit_does_not_rewrite_frozen_paper(self):
        question = self._question(self.shared, label="original")
        exam = self._exam([question], bank_ids=[self.shared.id])
        question.question_text = "new bank text"
        question.content_revision = 2
        question.content_hash = "new-bank-hash"
        db.session.flush()
        self.assertTrue(validate_exam_source(exam, require_live=True)["valid"])

    def test_frozen_private_owner_and_live_owner_are_both_checked(self):
        former_course = Course(course_name="Lớp cũ", subject="Toán", teacher_id=self.former.id)
        db.session.add(former_course)
        db.session.flush()
        question = self._question(
            self.shared, scope=QUESTION_SCOPE_PRIVATE, owner=self.former, label="former-overlay"
        )
        exam = self._exam([question], course=former_course, bank_ids=[self.shared.id])
        former_course.teacher_id = self.teacher.id
        db.session.flush()
        blocked = validate_exam_source(exam, require_live=True)
        self.assertFalse(blocked["valid"])
        self.assertTrue(blocked["snapshot_valid"])

        # Even if somebody rewrites the live owner to the new teacher, the
        # paper's frozen private owner remains a distinct provenance assertion.
        question.private_owner_id = self.teacher.id
        db.session.flush()
        owner_mismatch = validate_exam_source(exam, require_live=True)
        self.assertFalse(owner_mismatch["valid"])
        self.assertIn(owner_mismatch["reason"], {"private_owner_mismatch", "question_not_authorized"})

    def test_multi_bank_session_mapping_is_exact(self):
        common = self._question(self.shared, label="common")
        private = self._question(
            self.teacher_private, scope=QUESTION_SCOPE_PRIVATE, owner=self.teacher, label="private"
        )
        session = PracticeSession(
            student_id=9001, course_id=self.course.id, subject=self.course.subject,
            scope_code="9C8-i", bank_ids=json.dumps([self.shared.id, self.teacher_private.id]),
            status="active",
        )
        db.session.add(session)
        db.session.flush()
        exam = self._exam(
            [common, private], bank_ids=[self.shared.id, self.teacher_private.id], session=session
        )
        self.assertTrue(validate_exam_source(exam, require_live=True)["valid"])
        session.bank_ids = json.dumps([self.shared.id])
        db.session.flush()
        mismatch = validate_exam_source(exam, require_live=True)
        self.assertFalse(mismatch["valid"])
        self.assertEqual(mismatch["reason"], "session_source_mismatch")


if __name__ == "__main__":
    unittest.main()
