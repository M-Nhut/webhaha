"""Focused Phase-4 learning-loop contracts (SQLite, no production data)."""
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
    Course, DiagnosticAssignment, Enrollment, ErrorObservation, Exam,
    ExamAnswer, ExamQuestion, ExamSubmission, MasterySnapshot,
    PracticeSession, SubmissionAnswer, User,
)
from services import practice_blueprint as blueprint
from services.diagnostic_service import common_item_hash


class LearningLoopPhase4Tests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="p4_teacher", user_code="P4T", fullname="GV", role="teacher")
        self.student = User(username="p4_student", user_code="P4S", fullname="HS", role="student")
        db.session.add_all((self.teacher, self.student))
        db.session.flush()
        self.course = Course(course_name="Lớp 9 Phase 4", subject="Toán", teacher_id=self.teacher.id)
        db.session.add(self.course)
        db.session.flush()
        db.session.add(Enrollment(student_id=self.student.id, course_id=self.course.id, status="active"))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def client(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.student.id)
            session["_fresh"] = True
        return client

    def fixed_exam(self, kinds=("single",)):
        session = PracticeSession(
            student_id=self.student.id, course_id=self.course.id,
            subject="Toán", scope_code="9C8-i", status="active", bank_ids="[]",
        )
        db.session.add(session)
        db.session.flush()
        exam = Exam(
            title="Bài Phase 4", course_id=self.course.id, created_by=self.student.id,
            exam_type="practice", is_active=True, duration_minutes=40,
            adaptive_metadata=json.dumps({
                "aptga": {"version": blueprint.VERSION}, "student_id": self.student.id,
                "practice_session_id": session.id,
            }),
        )
        db.session.add(exam)
        db.session.flush()
        session.last_exam_id = exam.id
        for index, kind in enumerate(kinds):
            metadata = ({"statements": [
                {"curriculum_code": blueprint.SKILLS[0], "cognitive_level": "nhan_biet"}
                for _ in range(4)
            ]} if kind == "true_false" else {})
            question = ExamQuestion(
                exam_id=exam.id, question_text=f"Câu {index}", question_type=kind,
                points=1, order_index=index, curriculum_code=blueprint.SKILLS[0],
                difficulty_level="nhan_biet", learning_metadata=json.dumps(metadata),
            )
            db.session.add(question)
            db.session.flush()
            for answer_index in range(4 if kind == "true_false" else 2):
                db.session.add(ExamAnswer(
                    question_id=question.id, answer_text=str(answer_index),
                    is_correct=(answer_index == 0),
                ))
        db.session.commit()
        return exam, session

    def diagnostic_exam(self):
        exam = Exam(
            title="Đầu vào Phase 4", course_id=self.course.id, created_by=self.teacher.id,
            exam_type="exam", assessment_purpose="initial_diagnostic", is_active=True,
            duration_minutes=40,
        )
        db.session.add(exam)
        db.session.flush()
        kinds = ("single",) * 12 + ("true_false",) * 4 + ("short_answer",) * 6
        for index, kind in enumerate(kinds):
            metadata = ({"statements": [
                {"curriculum_code": blueprint.SKILLS[index % 8], "cognitive_level": "nhan_biet"}
                for _ in range(4)
            ]} if kind == "true_false" else {"short_answer": {"mode": "numeric", "tolerance": "0"}} if kind == "short_answer" else {})
            question = ExamQuestion(
                exam_id=exam.id, question_text=f"Đầu vào {index}", question_type=kind,
                points=blueprint.POINTS[kind], order_index=index,
                curriculum_code=blueprint.SKILLS[index % 8], difficulty_level="nhan_biet",
                learning_metadata=json.dumps(metadata),
            )
            db.session.add(question)
            db.session.flush()
            for answer_index in range(4 if kind in ("single", "true_false") else 1):
                db.session.add(ExamAnswer(
                    question_id=question.id, answer_text="1" if kind == "short_answer" else str(answer_index),
                    is_correct=(answer_index == 0),
                ))
        db.session.flush()
        assignment = DiagnosticAssignment(
            exam_id=exam.id, student_id=self.student.id,
            common_item_hash=common_item_hash(exam), status="assigned",
        )
        db.session.add(assignment)
        db.session.commit()
        return exam, assignment

    def test_fixed_double_post_finalizes_once_and_updates_evidence(self):
        exam, session = self.fixed_exam()
        client = self.client()
        answer = exam.questions[0].answers[1]  # observed wrong answer
        self.assertEqual(client.post(f"/practice/{exam.id}/take", data={f"q_{exam.questions[0].id}": answer.id}).status_code, 302)
        self.assertEqual(client.post(f"/practice/{exam.id}/take", data={f"q_{exam.questions[0].id}": answer.id}).status_code, 302)
        submission = ExamSubmission.query.filter_by(exam_id=exam.id).one()
        self.assertTrue(submission.is_graded)
        self.assertEqual(ExamSubmission.query.filter_by(exam_id=exam.id).count(), 1)
        self.assertIsNotNone(MasterySnapshot.query.filter_by(submission_id=submission.id).first())
        self.assertEqual(ErrorObservation.query.filter_by(submission_id=submission.id, status="observed").count(), 1)
        db.session.refresh(session)
        self.assertEqual(session.status, "awaiting_decision")

    def test_evidence_failure_rolls_back_submission_and_transient_claim(self):
        exam, session = self.fixed_exam()
        with patch("routes.practice_runtime.AdaptiveEngine.update_performance", side_effect=RuntimeError("boom")):
            response = self.client().post(f"/practice/{exam.id}/take", data={})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ExamSubmission.query.filter_by(exam_id=exam.id).count(), 0)
        db.session.refresh(session)
        self.assertEqual(session.status, "active")

    def test_tf_partial_is_scored_and_blank_is_not_error_evidence(self):
        partial_exam, _session = self.fixed_exam(("true_false",))
        question = partial_exam.questions[0]
        payload = {
            f"q_{question.id}_ans_{answer.id}": "1" if answer.is_correct else "0"
            for answer in question.answers[:3]
        }
        # Make the fourth answered statement wrong: expected false, chosen true.
        payload[f"q_{question.id}_ans_{question.answers[3].id}"] = "1"
        self.client().post(f"/practice/{partial_exam.id}/take", data=payload)
        partial = ExamSubmission.query.filter_by(exam_id=partial_exam.id).one()
        tf_answer = partial.answers[0]
        self.assertEqual(tf_answer.points_earned, .5)
        self.assertEqual(ErrorObservation.query.filter_by(submission_id=partial.id, status="observed").count(), 1)

        blank_exam, _session = self.fixed_exam(("true_false",))
        self.client().post(f"/practice/{blank_exam.id}/take", data={})
        blank = ExamSubmission.query.filter_by(exam_id=blank_exam.id).one()
        self.assertEqual(blank.answers[0].answer_status, "unanswered")
        self.assertEqual(ErrorObservation.query.filter_by(submission_id=blank.id, status="observed").count(), 0)

    def test_diagnostic_rebuilds_draft_and_decisions_require_snapshot(self):
        exam, assignment = self.diagnostic_exam()
        draft = ExamSubmission(exam_id=exam.id, student_id=self.student.id, exam_type="exam")
        db.session.add(draft)
        db.session.flush()
        db.session.add(SubmissionAnswer(submission_id=draft.id, question_id=exam.questions[0].id,
                                        selected_answer_ids="[999]", answer_status="answered"))
        db.session.commit()
        response = self.client().post(f"/practice/{exam.id}/take", data={})
        self.assertEqual(response.status_code, 302)
        db.session.refresh(assignment)
        self.assertEqual(assignment.status, "completed")
        self.assertEqual(ExamSubmission.query.filter_by(exam_id=exam.id).count(), 1)
        self.assertEqual(SubmissionAnswer.query.filter_by(submission_id=draft.id).count(), blueprint.TOTAL)
        self.assertEqual(SubmissionAnswer.query.filter_by(submission_id=draft.id, selected_answer_ids="[999]").count(), 0)

        fixed, session = self.fixed_exam()
        self.client().post(f"/practice/{fixed.id}/take", data={})
        submission = ExamSubmission.query.filter_by(exam_id=fixed.id).one()
        snapshot = MasterySnapshot.query.filter_by(submission_id=submission.id).one()
        db.session.delete(snapshot)
        db.session.commit()
        self.assertNotIn("Tiếp tục luyện", self.client().get(f"/practice/{fixed.id}/result").get_data(as_text=True))
        self.client().post(f"/practice/submissions/{submission.id}/end")
        db.session.refresh(session)
        self.assertEqual(session.status, "awaiting_decision")


if __name__ == "__main__":
    unittest.main()
