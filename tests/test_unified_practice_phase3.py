"""Four focused DB contracts for the unified Phase-3 learner entry."""
import datetime as dt
import json
import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)
import config
config.load_local_environment = lambda *args, **kwargs: None

from app import app
from database import db
from models import (
    Course, DiagnosticAssignment, Enrollment, Exam, ExamAnswer, ExamQuestion,
    ExamSubmission, PracticeSession, QuestionBank, User,
)
from services import practice_blueprint as blueprint
from services.diagnostic_service import common_item_hash


class UnifiedPracticePhase3Tests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="p3_teacher", user_code="P3T", fullname="GV", role="teacher")
        self.other_teacher = User(username="p3_other_teacher", user_code="P3OT", fullname="GV khác", role="teacher")
        self.student = User(username="p3_student", user_code="P3S", fullname="HS", role="student")
        self.other_student = User(username="p3_other_student", user_code="P3OS", fullname="HS khác", role="student")
        db.session.add_all((self.teacher, self.other_teacher, self.student, self.other_student))
        db.session.flush()
        self.course = Course(course_name="Lớp 9A", subject="Toán", teacher_id=self.teacher.id)
        self.bank = QuestionBank(name="Nguồn lớp 9A", subject="Toán", grade="9", created_by=self.teacher.id)
        self.foreign_bank = QuestionBank(name="NGÂN HÀNG KHÔNG ĐƯỢC LỘ", subject="Toán", grade="9", created_by=self.other_teacher.id)
        db.session.add_all((self.course, self.bank, self.foreign_bank))
        db.session.flush()
        db.session.add_all((
            Enrollment(student_id=self.student.id, course_id=self.course.id, status="active"),
            Enrollment(student_id=self.other_student.id, course_id=self.course.id, status="active"),
        ))
        self.diagnostic = self._make_diagnostic()
        db.session.add(DiagnosticAssignment(
            exam_id=self.diagnostic.id,
            student_id=self.student.id,
            assigned_by=self.teacher.id,
            common_item_hash=common_item_hash(self.diagnostic),
        ))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _client(self, user):
        from flask import g
        g.pop("_login_user", None)
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return client

    def _make_diagnostic(self):
        exam = Exam(
            title="Đầu vào lớp 9A", course_id=self.course.id,
            created_by=self.teacher.id, question_bank_id=self.bank.id,
            exam_type="exam", assessment_purpose="initial_diagnostic",
            total_questions=blueprint.TOTAL, duration_minutes=blueprint.DURATION_MINUTES,
            is_active=True,
        )
        db.session.add(exam)
        db.session.flush()
        kinds = (["single"] * 12) + (["true_false"] * 4) + (["short_answer"] * 6)
        for index, kind in enumerate(kinds):
            metadata = {"short_answer": {"mode": "numeric", "tolerance": "0"}} if kind == "short_answer" else {}
            question = ExamQuestion(
                exam_id=exam.id, question_text=f"Câu {index + 1}",
                question_type=kind, points=blueprint.POINTS[kind], order_index=index,
                curriculum_code=blueprint.SKILLS[index % len(blueprint.SKILLS)],
                learning_metadata=json.dumps(metadata),
            )
            db.session.add(question)
            db.session.flush()
            answer_count = 4 if kind in ("single", "true_false") else 1
            for answer_index in range(answer_count):
                db.session.add(ExamAnswer(
                    question_id=question.id,
                    answer_text="1" if kind == "short_answer" else str(answer_index),
                    is_correct=(answer_index == 0),
                ))
        db.session.flush()
        return exam

    def _finalize_diagnostic(self):
        submission = ExamSubmission(
            exam_id=self.diagnostic.id, student_id=self.student.id,
            exam_type="exam", submitted_at=dt.datetime.utcnow(),
            finalized_at=dt.datetime.utcnow(), status="graded", is_graded=True,
        )
        db.session.add(submission)
        assignment = DiagnosticAssignment.query.filter_by(
            exam_id=self.diagnostic.id, student_id=self.student.id
        ).one()
        assignment.status = "completed"
        assignment.completed_at = submission.finalized_at
        db.session.commit()

    def test_student_has_one_pending_entry_and_no_cross_teacher_bank_listing(self):
        client = self._client(self.student)
        page = client.get(f"/practice?course_id={self.course.id}")
        self.assertEqual(page.status_code, 200)
        body = page.get_data(as_text=True)
        self.assertIn(f'href="/practice/{self.diagnostic.id}/take"', body)
        self.assertNotIn(self.foreign_bank.name, body)
        redirect_response = client.get("/diagnostics", follow_redirects=False)
        self.assertEqual(redirect_response.status_code, 302)
        self.assertTrue(redirect_response.headers["Location"].endswith("/practice"))

    def test_diagnostic_take_requires_its_student_assignment(self):
        self.assertEqual(
            self._client(self.student).get(f"/practice/{self.diagnostic.id}/take").status_code,
            200,
        )
        self.assertEqual(
            self._client(self.other_student).get(f"/practice/{self.diagnostic.id}/take").status_code,
            403,
        )

    def test_generate_uses_only_selected_class_diagnostic_bank(self):
        self._finalize_diagnostic()
        client = self._client(self.student)
        empty = {"questions": [], "explanation": "Thiếu câu phù hợp"}
        with patch("routes.practice.AdaptiveEngine.select_questions", return_value=empty) as select:
            response = client.post("/practice/generate", data={"course_id": self.course.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(select.call_args.args[2], [self.bank.id])
        with patch("routes.practice.AdaptiveEngine.select_questions") as select:
            forbidden = client.post("/practice/generate", data={
                "course_id": self.course.id, "bank_ids": [self.foreign_bank.id],
            })
        self.assertEqual(forbidden.status_code, 403)
        select.assert_not_called()

    def test_generate_resumes_own_unsubmitted_class_paper(self):
        self._finalize_diagnostic()
        session = PracticeSession(
            student_id=self.student.id, course_id=self.course.id,
            subject=self.course.subject, scope_code="9C8-i",
            bank_ids=json.dumps([self.bank.id]), status="active",
        )
        db.session.add(session)
        db.session.flush()
        exam = Exam(
            title="Đề đang làm", course_id=self.course.id,
            created_by=self.teacher.id, question_bank_id=self.bank.id,
            exam_type="practice", is_active=True,
            adaptive_metadata=json.dumps({
                "student_id": self.student.id,
                "practice_session_id": session.id,
                "aptga": {"version": blueprint.VERSION},
            }),
        )
        db.session.add(exam)
        db.session.flush()
        session.last_exam_id = exam.id
        db.session.commit()
        home = self._client(self.student).get(f"/practice?course_id={self.course.id}")
        self.assertIn("Bài giáo viên giao", home.get_data(as_text=True))
        before = Exam.query.filter_by(exam_type="practice").count()
        with patch("routes.practice.AdaptiveEngine.select_questions") as select:
            response = self._client(self.student).post(
                "/practice/generate", data={"course_id": self.course.id},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/practice/{exam.id}/take", response.headers["Location"])
        self.assertEqual(Exam.query.filter_by(exam_type="practice").count(), before)
        select.assert_not_called()


if __name__ == "__main__":
    unittest.main()
