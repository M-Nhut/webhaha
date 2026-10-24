"""Focused Phase-4 contracts for class-scoped question-bank selection."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)

import config  # noqa: E402
config.load_local_environment = lambda *args, **kwargs: None

from app import app  # noqa: E402
from database import db  # noqa: E402
from models import (  # noqa: E402
    Course,
    DiagnosticAssignment,
    Enrollment,
    Exam,
    ExamQuestion,
    PracticeSession,
    QuestionBank,
    User,
)
from services import practice_blueprint as blueprint  # noqa: E402
from services.access_control import (  # noqa: E402
    BANK_VISIBILITY_PRIVATE,
    BANK_VISIBILITY_SHARED,
)
from services.diagnostic_service import class_diagnostic_source, common_item_hash  # noqa: E402
from routes.practice import _published_teacher_papers, _teacher_session_banks  # noqa: E402


class BankSelectionPhase4Tests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        self.admin = User(username="p4-bank-admin", user_code="P4BA", fullname="Admin", role="admin")
        self.former = User(username="p4-bank-former", user_code="P4BF", fullname="Former", role="teacher")
        self.teacher = User(username="p4-bank-teacher", user_code="P4BT", fullname="Current", role="teacher")
        self.other = User(username="p4-bank-other", user_code="P4BO", fullname="Other", role="teacher")
        self.student = User(username="p4-bank-student", user_code="P4BS", fullname="Student", role="student")
        db.session.add_all((self.admin, self.former, self.teacher, self.other, self.student))
        db.session.flush()
        self.course = Course(course_name="Lớp chuyển giao", subject="Toán", teacher_id=self.teacher.id)
        self.shared = QuestionBank(
            name="Bank dùng chung", subject="Toán", grade="9",
            created_by=self.admin.id, visibility=BANK_VISIBILITY_SHARED,
        )
        self.teacher_private = QuestionBank(
            name="Bank riêng hiện tại", subject="Toán", grade="9",
            created_by=self.teacher.id, visibility=BANK_VISIBILITY_PRIVATE,
        )
        self.former_private = QuestionBank(
            name="Bank riêng giáo viên cũ", subject="Toán", grade="9",
            created_by=self.former.id, visibility=BANK_VISIBILITY_PRIVATE,
        )
        self.other_private = QuestionBank(
            name="Bank riêng giáo viên khác", subject="Toán", grade="9",
            created_by=self.other.id, visibility=BANK_VISIBILITY_PRIVATE,
        )
        db.session.add_all((self.course, self.shared, self.teacher_private, self.former_private, self.other_private))
        db.session.flush()
        db.session.add(Enrollment(student_id=self.student.id, course_id=self.course.id, status="active"))
        db.session.commit()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def login(self, user):
        from flask import g
        g.pop("_login_user", None)
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

    def _make_diagnostic(self, course, bank, created_by=None):
        exam = Exam(
            title=f"Diagnostic {course.course_name}", course_id=course.id,
            created_by=created_by or self.former.id, question_bank_id=bank.id,
            exam_type="exam", assessment_purpose="initial_diagnostic",
            total_questions=blueprint.TOTAL, duration_minutes=blueprint.DURATION_MINUTES,
            is_active=True,
        )
        db.session.add(exam)
        db.session.flush()
        kinds = (["single"] * 12) + (["true_false"] * 4) + (["short_answer"] * 6)
        for index, kind in enumerate(kinds):
            db.session.add(ExamQuestion(
                exam_id=exam.id, question_text=f"Item {index}", question_type=kind,
                points=blueprint.POINTS[kind], order_index=index,
                curriculum_code=blueprint.SKILLS[index % len(blueprint.SKILLS)],
                difficulty_level="nhan_biet",
            ))
        db.session.flush()
        assignment = DiagnosticAssignment(
            exam_id=exam.id, student_id=self.student.id,
            common_item_hash=common_item_hash(exam), status="assigned",
        )
        db.session.add(assignment)
        db.session.commit()
        return exam, assignment

    def _teacher_paper(self, bank):
        session = PracticeSession(
            student_id=self.student.id, course_id=self.course.id,
            subject=self.course.subject, scope_code="9C8-i",
            bank_ids=json.dumps([bank.id]), status="active",
        )
        db.session.add(session)
        db.session.flush()
        exam = Exam(
            title=f"Teacher paper {bank.name}", course_id=self.course.id,
            created_by=self.former.id, question_bank_id=bank.id,
            exam_type="practice", is_active=True,
            adaptive_metadata=json.dumps({
                "aptga": {"version": blueprint.VERSION},
                "student_id": self.student.id,
                "practice_session_id": session.id,
                "practice_provenance": {
                    "kind": "teacher_assigned", "teacher_id": self.former.id,
                    "course_id": self.course.id,
                },
            }),
        )
        db.session.add(exam)
        db.session.flush()
        session.last_exam_id = exam.id
        db.session.commit()
        return exam, session

    def test_teacher_diagnostic_candidates_include_shared_but_not_foreign_private(self):
        self.login(self.teacher)
        body = self.client.get("/diagnostics/new").get_data(as_text=True)
        self.assertIn(self.shared.name, body)
        self.assertIn(self.teacher_private.name, body)
        self.assertNotIn(self.former_private.name, body)
        self.assertNotIn(self.other_private.name, body)

    def test_diagnostic_request_cannot_forge_former_private_bank(self):
        self.login(self.teacher)
        response = self.client.post("/diagnostics/new", data={
            "course_id": self.course.id,
            "question_bank_id": self.former_private.id,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Exam.query.filter_by(assessment_purpose="initial_diagnostic").count(), 0)

    def test_diagnostic_post_rechecks_shared_bank_with_current_teacher_actor(self):
        self.login(self.teacher)
        empty_selection = {
            "questions": [], "status": "insufficient_candidates", "shortages": [],
            "level_targets": {}, "skill_targets": {}, "warnings": [],
        }
        with patch("routes.diagnostics.common_diagnostic_selection", return_value=empty_selection) as selector:
            response = self.client.post("/diagnostics/new", data={
                "course_id": self.course.id,
                "question_bank_id": self.shared.id,
            })
        self.assertEqual(response.status_code, 302)
        selector.assert_called_once()

    def test_class_source_shared_survives_transfer_but_former_private_source_does_not(self):
        shared_course = Course(course_name="Lớp shared", subject="Toán", teacher_id=self.former.id)
        private_course = Course(course_name="Lớp private", subject="Toán", teacher_id=self.former.id)
        db.session.add_all((shared_course, private_course))
        db.session.flush()
        db.session.add_all((
            Enrollment(student_id=self.student.id, course_id=shared_course.id, status="active"),
            Enrollment(student_id=self.student.id, course_id=private_course.id, status="active"),
        ))
        shared_exam, _ = self._make_diagnostic(shared_course, self.shared)
        private_exam, _ = self._make_diagnostic(private_course, self.former_private)
        shared_course.teacher_id = self.teacher.id
        private_course.teacher_id = self.teacher.id
        db.session.commit()

        shared_state = class_diagnostic_source(self.student.id, shared_course)
        private_state = class_diagnostic_source(self.student.id, private_course)
        self.assertEqual(shared_state["status"], "ready")
        self.assertEqual(shared_state["bank"].id, self.shared.id)
        self.assertEqual(private_state["status"], "bank_unavailable")
        self.assertIsNone(private_state["bank"])
        # The frozen diagnostic rows remain untouched by the authorization
        # recheck.
        self.assertEqual(db.session.get(Exam, shared_exam.id).question_bank_id, self.shared.id)
        self.assertEqual(db.session.get(Exam, private_exam.id).question_bank_id, self.former_private.id)

    def test_teacher_session_banks_use_current_teacher_policy(self):
        self.assertEqual(
            {bank.id for bank in _teacher_session_banks(self.course, [self.shared.id, self.teacher_private.id])},
            {self.shared.id, self.teacher_private.id},
        )
        self.assertEqual(_teacher_session_banks(self.course, [self.former_private.id]), [])
        self.assertEqual(_teacher_session_banks(self.course, [self.other_private.id]), [])

    def test_former_teacher_paper_shared_source_remains_visible_but_private_is_hidden(self):
        shared_exam, _ = self._teacher_paper(self.shared)
        private_exam, _ = self._teacher_paper(self.former_private)
        db.session.commit()
        papers = _published_teacher_papers(self.student.id, self.course)
        self.assertIn(shared_exam.id, {item["exam"].id for item in papers})
        self.assertNotIn(private_exam.id, {item["exam"].id for item in papers})


if __name__ == "__main__":
    unittest.main()
