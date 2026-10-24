"""Focused Phase 5 report boundaries; no provider or production database."""

import datetime as dt
import os
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)
os.environ["FLASK_SECRET_KEY"] = "phase5-report-isolated-test-session"
os.environ["AI_CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
import config
config.load_local_environment = lambda *args, **kwargs: None

_storage = tempfile.TemporaryDirectory(prefix="phase5-report-tests-")
with patch.object(config, "upload_directories", return_value={
    "UPLOAD_FOLDER_AVATARS": f"{_storage.name}/avatars",
    "UPLOAD_FOLDER_COURSES": f"{_storage.name}/courses",
}):
    from app import app
from database import db
from models import Course, Enrollment, Exam, ExamQuestion, ExamSubmission, User
from services.ai_profile_analysis import AIProfileAnalyzer
from services.class_lesson4_report import ClassLesson4ReportService, build_class_lesson4_packet, validate_class_report
from services.diagnostic_report_contract import enrich_packet
from services.personalization_evidence import source_revision


class Phase5ReportTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="phase5-teacher", fullname="Teacher", user_code="T5", role="teacher")
        self.student = User(username="phase5-student", fullname="Student", user_code="S5", role="student")
        self.teacher.set_password("test-only")
        self.student.set_password("test-only")
        db.session.add_all([self.teacher, self.student])
        db.session.flush()
        self.course = Course(course_name="Phase 5", subject="Toán", teacher_id=self.teacher.id)
        db.session.add(self.course)
        db.session.flush()
        db.session.add(Enrollment(student_id=self.student.id, course_id=self.course.id, status="active"))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _diagnostic(self, revision=1):
        exam = Exam(course_id=self.course.id, created_by=self.teacher.id, title="Đầu vào", assessment_purpose="initial_diagnostic")
        db.session.add(exam)
        db.session.flush()
        kinds = (["single"] * 12) + (["true_false"] * 4) + (["short_answer"] * 6)
        for index, kind in enumerate(kinds):
            db.session.add(ExamQuestion(
                exam_id=exam.id, question_text=f"Câu {index + 1}", question_type=kind,
                curriculum_code="9C8-i-1", order_index=index,
            ))
        submission = ExamSubmission(
            exam_id=exam.id, student_id=self.student.id, submitted_at=dt.datetime.utcnow(),
            status="graded", is_graded=True, grading_revision=revision,
        )
        db.session.add(submission)
        db.session.commit()
        return submission

    def test_initial_diagnostic_is_a_latest_report_target(self):
        submission = self._diagnostic()
        packet = enrich_packet({"observed_error_evidence": []}, self.student.id, "Toán", course_id=self.course.id)
        self.assertEqual(packet["target_submission_id"], submission.id)
        self.assertEqual(packet["finalized_submission_snapshots"][0]["paper_kind"], "initial_diagnostic")
        class_packet = build_class_lesson4_packet(self.course)
        self.assertEqual(class_packet["coverage"]["event_count"], 0)
        self.assertEqual(class_packet["coverage"]["finalized_submission_count"], 1)

    def test_all_correct_finalized_submission_advances_report_revision(self):
        self._diagnostic(revision=1)
        first = source_revision(self.student.id, "Toán", course_id=self.course.id)
        self._diagnostic(revision=2)
        self.assertNotEqual(first, source_revision(self.student.id, "Toán", course_id=self.course.id))

    def test_class_risk_requires_matching_evidence_and_validation_fields(self):
        packet = {"roster": [{"student_ref": "anon"}], "students": [{"student_ref": "anon", "events": [{
            "event_ref": "e1", "outcome": "wrong", "curriculum_code": "9C8-i-1",
        }]}]}
        valid = {"schema_version": "class-lesson4-report-v1", "class_summary": {"next_risk_hypotheses": [{
            "skill": "9C8-i-1", "hypothesis": "Cần theo dõi.", "basis_evidence_refs": ["e1"],
            "affected_student_refs": ["anon"], "validation": "not_validated",
            "trigger_condition": "Gặp câu cùng kỹ năng.", "verification_question": "Em dựa vào điều kiện nào?",
            "suggested_remediation": "Đối chiếu lại câu tương tự.",
        }], "recommendations": []}, "students": []}
        self.assertEqual(validate_class_report(valid, packet)["class_summary"]["next_risk_hypotheses"][0]["skill"], "9C8-i-1")
        valid["class_summary"]["next_risk_hypotheses"][0]["skill"] = "9C8-i-2"
        self.assertEqual(validate_class_report(valid, packet)["class_summary"]["next_risk_hypotheses"], [])
        # Unknown references and false claims are dropped without changing
        # observed facts; valid hypotheses still survive beside invalid rows.
        valid["class_summary"]["next_risk_hypotheses"][0]["skill"] = "9C8-i-1"
        valid["class_summary"]["next_risk_hypotheses"][0]["basis_evidence_refs"] = ["foreign-evidence"]
        self.assertEqual(validate_class_report(valid, packet)["class_summary"]["next_risk_hypotheses"], [])
        self.assertEqual(packet["students"][0]["events"][0]["event_ref"], "e1")
        risk = valid["class_summary"]["next_risk_hypotheses"][0]
        risk["basis_evidence_refs"] = ["e1"]
        risk["validation"] = "validated"
        with self.assertRaisesRegex(ValueError, "thiếu điều kiện"):
            validate_class_report(valid, packet, require_teacher_support=True)
        risk["validation"] = "not_validated"
        risk.pop("verification_question")
        with self.assertRaisesRegex(ValueError, "thiếu điều kiện"):
            validate_class_report(valid, packet, require_teacher_support=True)

    def test_unknown_provider_exception_is_not_persistable_error_text(self):
        secret = RuntimeError("proxy echoed Authorization: Bearer private-key")
        self.assertNotIn("private-key", AIProfileAnalyzer._safe_error(secret))
        self.assertNotIn("private-key", ClassLesson4ReportService._safe_error(secret))


if __name__ == "__main__":
    unittest.main()
