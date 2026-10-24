"""Focused isolated tests for the fixed class Lesson 4 report."""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)
os.environ["FLASK_SECRET_KEY"] = "class-report-isolated-test-session"
os.environ["AI_CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["AI_LEGACY_ENV_FALLBACK_ENABLED"] = "0"

import config
config.load_local_environment = lambda *args, **kwargs: None

_storage = tempfile.TemporaryDirectory(prefix="class-report-tests-")
with patch.object(config, "upload_directories", return_value={
    "UPLOAD_FOLDER_AVATARS": f"{_storage.name}/avatars",
    "UPLOAD_FOLDER_COURSES": f"{_storage.name}/courses",
}):
    from app import app
from database import db
from models import (
    ClassAIAnalysisRun,
    Course,
    Enrollment,
    Exam,
    ExamAnswer,
    ExamQuestion,
    ExamSubmission,
    LearningHistory,
    SubmissionAnswer,
    TeacherAIKey,
    TeacherAIKeyGroup,
    User,
)
from services.ai_gateway import credential_fingerprint, encrypt_credential
from services.class_lesson4_report import (
    ClassLesson4ReportService,
    PROMPT_VERSION,
    SCOPE_CODE,
    build_class_lesson4_packet,
    deterministic_class_report,
    present_observed_report,
    validate_class_report,
)


def _teacher_support_response(packet):
    """Return a valid mocked provider response using only its actual packet."""
    def section(students):
        events = [event for student in students for event in student.get("events", [])]
        refs = [event["event_ref"] for event in events]
        errors = [event for event in events if event.get("outcome") == "wrong"]
        skill = errors[0]["curriculum_code"] if errors else None
        error_refs = [event["event_ref"] for event in errors if event["curriculum_code"] == skill]
        owners = [row["student_ref"] for row in students if any(event["event_ref"] in error_refs for event in row.get("events", []))]
        return {
            "ai_summary": [{"text": "Đối chiếu số liệu bài làm và bằng chứng đã chấm.", "basis_evidence_refs": refs}],
            "cause_hypotheses": [{"skill": skill, "hypothesis": "Có thể chưa kiểm tra đủ điều kiện.",
                "basis_evidence_refs": error_refs, "verification_question": "Em đã kiểm tra điều kiện nào?",
                "validation": "not_validated"}] if errors else [],
            "next_risk_hypotheses": [{"skill": skill, "hypothesis": "Có thể bỏ sót điều kiện ở câu tương tự.",
                "basis_evidence_refs": error_refs, "affected_student_refs": owners,
                "validation": "not_validated", "trigger_condition": "Khi điều kiện bài toán thay đổi.",
                "verification_question": "Điều kiện mới ảnh hưởng thế nào?", "suggested_remediation": "Đối chiếu hai ví dụ."}] if errors else [],
            "recommendations": [{"skill": skill, "text": "Hướng dẫn đối chiếu điều kiện trước khi giải.",
                "basis_evidence_refs": error_refs, "learning_goal": "Nhận biết đủ điều kiện.",
                "teaching_strategy": "Giáo viên minh họa hai trường hợp và yêu cầu giải thích.",
                "teacher_question": "Vì sao trường hợp này thỏa mãn?", "practice_suggestion": "Giải câu cùng dạng với điều kiện mới.",
                "success_criteria": "Giải thích được điều kiện và tự kiểm tra kết quả."}],
        }
    counts = {row["student_ref"]: sum(row.get(key, 0) for key in ("correct", "wrong", "partial"))
              for row in packet.get("observed_statistics", {}).get("students", [])}
    students = []
    for student in packet["students"]:
        has_data = bool(student.get("events") or counts.get(student["student_ref"]))
        row = section([student]) if has_data else {key: [] for key in ("ai_summary", "cause_hypotheses", "next_risk_hypotheses", "recommendations")}
        students.append({"student_ref": student["student_ref"], **row})
    return {"schema_version": "class-lesson4-report-v1", "class_summary": section(packet["students"]), "students": students}


class _Response:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class _Session:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(kwargs)
        body = self.body
        if callable(body):
            packet = json.loads(kwargs["json"]["messages"][-1]["content"].split("\nPACKET:\n", 1)[1])
            body = {"choices": [{"message": {"content": json.dumps(body(packet))}}]}
        return _Response(body)


class ClassLesson4ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def setUp(self):
        self.network = patch("requests.sessions.Session.request", side_effect=AssertionError("Real network is forbidden in isolated tests"))
        self.network.start()
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="class-teacher", fullname="Class Teacher", user_code="CT", role="teacher")
        self.other_teacher = User(username="class-other", fullname="Other Teacher", user_code="OT", role="teacher")
        self.student = User(username="class-student", fullname="Student A", user_code="SA", role="student")
        self.no_data = User(username="class-no-data", fullname="Student B", user_code="SB", role="student")
        self.other_student = User(username="class-other-student", fullname="Other Course", user_code="SO", role="student")
        for user in (self.teacher, self.other_teacher, self.student, self.no_data, self.other_student):
            user.set_password("password")
        db.session.add_all([self.teacher, self.other_teacher, self.student, self.no_data, self.other_student])
        db.session.flush()
        self.course = Course(course_name="Lớp Bài 4", subject="Toán", teacher_id=self.teacher.id)
        self.other_course = Course(course_name="Lớp khác", subject="Toán", teacher_id=self.other_teacher.id)
        db.session.add_all([self.course, self.other_course])
        db.session.flush()
        db.session.add_all([
            Enrollment(student_id=self.student.id, course_id=self.course.id, status="active"),
            Enrollment(student_id=self.no_data.id, course_id=self.course.id, status="active"),
            Enrollment(student_id=self.other_student.id, course_id=self.other_course.id, status="active"),
        ])
        self.group = TeacherAIKeyGroup(owner_id=self.teacher.id, name="verified-test-default", is_default=True)
        db.session.add(self.group)
        db.session.flush()
        raw_key = "synthetic-class-report-key-never-real"
        db.session.add(TeacherAIKey(group_id=self.group.id, encrypted_key=encrypt_credential(raw_key),
            key_fingerprint=credential_fingerprint(raw_key), key_hint=raw_key[-4:], last_test_status="ok"))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.network.stop()

    def _attempt(self, *, course, student, code="9C8-i-1", correct=False, revision=1, stamp=None):
        exam = Exam(title="Bài 4", course_id=course.id, created_by=course.teacher_id)
        db.session.add(exam)
        db.session.flush()
        question = ExamQuestion(
            exam_id=exam.id, question_text="Xác suất của biến cố", question_type="single",
            difficulty_level="thong_hieu", curriculum_code=code, topic_snapshot="Không gian mẫu",
            points=1,
        )
        db.session.add(question)
        db.session.flush()
        right = ExamAnswer(question_id=question.id, answer_text="A", is_correct=True)
        wrong = ExamAnswer(question_id=question.id, answer_text="B", is_correct=False)
        db.session.add_all([right, wrong])
        db.session.flush()
        selected = [right.id] if correct else [wrong.id]
        submission = ExamSubmission(
            exam_id=exam.id, student_id=student.id, submitted_at=stamp or dt.datetime.utcnow(),
            is_graded=True, status="graded", grading_revision=revision,
        )
        db.session.add(submission)
        db.session.flush()
        answer = SubmissionAnswer(
            submission_id=submission.id, question_id=question.id,
            selected_answer_ids=json.dumps(selected), is_correct=correct,
            answer_status="graded", grading_revision=revision,
        )
        db.session.add(answer)
        db.session.flush()
        history = LearningHistory(
            student_id=student.id, submission_id=submission.id, exam_question_id=question.id,
            subject=course.subject, curriculum_code=code, topic="Không gian mẫu",
            difficulty_band="thong_hieu", cognitive_level="thong_hieu", is_correct=correct,
            normalized_score=1 if correct else 0, points_earned=1 if correct else 0,
            max_points=1, weight=1, occurred_at=stamp or dt.datetime.utcnow(),
            submission_answer_id=answer.id, answer_status="graded", grading_revision=revision,
            evidence_ref=f"submission:{submission.id}:answer:{answer.id}:revision:{revision}",
        )
        db.session.add(history)
        db.session.commit()
        return history

    def _service(self):
        return ClassLesson4ReportService(http_session=_Session(_teacher_support_response), sleep_fn=lambda _: None)

    def _login(self, user):
        from flask import g
        g.pop("_login_user", None)
        client = app.test_client()
        response = client.post("/login", data={"username": user.username, "password": "password", "submit": "Đăng nhập"})
        self.assertEqual(response.status_code, 302)
        return client

    def test_packet_is_strictly_in_class_and_keeps_no_data_roster(self):
        wrong = self._attempt(course=self.course, student=self.student, correct=False)
        self._attempt(course=self.other_course, student=self.other_student, correct=True)
        packet = build_class_lesson4_packet(self.course)
        self.assertEqual(packet["coverage"]["roster_count"], 2)
        self.assertEqual(packet["coverage"]["students_with_data"], 1)
        self.assertEqual(packet["coverage"]["event_count"], 1)
        self.assertEqual({event["event_ref"] for row in packet["students"] for event in row["events"]}, {wrong.evidence_ref})
        self.assertNotIn(self.student.fullname, json.dumps(packet, ensure_ascii=False))
        self.assertNotIn(self.student.user_code, json.dumps(packet, ensure_ascii=False))

    def test_unconfigured_generation_fails_but_observed_facts_remain_available(self):
        self._attempt(course=self.course, student=self.student, correct=False)
        self.group.is_default = False
        db.session.commit()
        provider = _Session(_teacher_support_response)
        service = ClassLesson4ReportService(http_session=provider, sleep_fn=lambda _: None)
        run, cached, packet = service.generate(self.course, requested_by=self.teacher.id)
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.analysis_source, "ai_api")
        self.assertFalse(cached)
        self.assertEqual(provider.calls, [])
        self.assertEqual(run.get_response_data(), {})
        observed = present_observed_report(self.course, packet)
        self.assertEqual(len(observed["class_summary"]["observed_errors"]), 1)
        self.assertTrue(any(row["data_status"] == "no_data" for row in observed["students"]))
        self.assertEqual(observed["class_summary"]["next_risk_hypotheses"], [])

    def test_invalid_api_reference_is_rejected_without_persisting_claims(self):
        self._attempt(course=self.course, student=self.student, correct=False)
        def foreign_cause(packet):
            response = _teacher_support_response(packet)
            response["class_summary"]["cause_hypotheses"][0]["basis_evidence_refs"] = ["foreign-evidence-never-persist"]
            return response
        fake = _Session(foreign_cause)
        service = ClassLesson4ReportService(http_session=fake, sleep_fn=lambda _: None)
        run, _, _ = service.generate(self.course, requested_by=self.teacher.id)
        self.assertEqual(run.status, "failed")
        self.assertIn("evidence_ref", run.error_message)
        self.assertNotIn("foreign-evidence-never-persist", run.response_data)
        self.assertIsNone(run.get_response_data()["class_summary"])
        sent = json.dumps(fake.calls[0]["json"], ensure_ascii=False)
        self.assertNotIn(self.student.fullname, sent)
        outbound_packet = json.loads(fake.calls[0]["json"]["messages"][-1]["content"].split("\nPACKET:\n", 1)[1])
        self.assertNotIn(json.dumps(self.student.user_code), json.dumps(outbound_packet))

    def test_valid_api_response_is_persisted_and_token_mapped_for_teacher(self):
        self._attempt(course=self.course, student=self.student, correct=False)
        packet = build_class_lesson4_packet(self.course)
        token = next(row["student_ref"] for row in packet["students"] if row["events"])
        service = self._service()
        run, _, _ = service.generate(self.course, requested_by=self.teacher.id)
        presented = service.present(run, self.course)
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.analysis_source, "ai_api")
        self.assertEqual(run.scope_code, "9C8-i")
        self.assertEqual(run.ai_key_group_id, self.group.id)
        self.assertEqual(run.ai_credential_source, "teacher_group")
        mapped = next(row for row in presented["students"] if row["student_ref"] == token)
        self.assertEqual(mapped["display_name"], self.student.fullname)
        self.assertEqual(presented["class_summary"]["next_risk_hypotheses"][0]["validation"], "not_validated")
        self.assertNotIn(self.student.fullname, run.request_data)
        self.assertNotIn(self.student.user_code, run.request_data)

    def test_invalid_optional_risk_never_reaches_persisted_report(self):
        self._attempt(course=self.course, student=self.student, correct=False)
        marker = "unsupported-risk-never-persist"
        def mixed_risks(packet):
            response = _teacher_support_response(packet)
            invalid = {**response["class_summary"]["next_risk_hypotheses"][0],
                       "hypothesis": marker, "basis_evidence_refs": ["outside-packet-evidence"]}
            response["class_summary"]["next_risk_hypotheses"].append(invalid)
            response["students"][0]["next_risk_hypotheses"].append(invalid)
            return response
        service = ClassLesson4ReportService(http_session=_Session(mixed_risks), sleep_fn=lambda _: None)
        run, _, _ = service.generate(self.course, requested_by=self.teacher.id)
        self.assertEqual(run.status, "completed")
        self.assertEqual(len(run.get_response_data()["class_summary"]["next_risk_hypotheses"]), 1)
        self.assertNotIn(marker, run.response_data)
        self.assertNotIn("outside-packet-evidence", run.response_data)

    def test_cache_invalidation_includes_correct_attempt_and_roster(self):
        self._attempt(course=self.course, student=self.student, correct=False)
        service = self._service()
        first, cached, _ = service.generate(self.course, requested_by=self.teacher.id)
        self.assertFalse(cached)
        second, cached, _ = service.generate(self.course, requested_by=self.teacher.id)
        self.assertTrue(cached)
        self.assertEqual(first.id, second.id)
        self._attempt(course=self.course, student=self.student, correct=True, revision=2)
        third, cached, _ = service.generate(self.course, requested_by=self.teacher.id)
        self.assertFalse(cached)
        self.assertNotEqual(first.input_hash, third.input_hash)
        student_row = next(row for row in third.get_response_data()["students"] if row["observed_events"])
        self.assertEqual(len(student_row["observed_progress"]), 1)
        self.assertEqual(len(student_row["observed_errors"]), 1)
        db.session.add(Enrollment(student_id=self.other_student.id, course_id=self.course.id, status="active"))
        db.session.commit()
        fourth, cached, _ = service.generate(self.course, requested_by=self.teacher.id)
        self.assertFalse(cached)
        self.assertNotEqual(third.input_hash, fourth.input_hash)

    def test_regrade_revision_and_outcome_invalidate_snapshot(self):
        history = self._attempt(course=self.course, student=self.student, correct=False, revision=1)
        service = self._service()
        first, _, _ = service.generate(self.course, requested_by=self.teacher.id)
        history.is_correct = True
        history.normalized_score = 1
        history.grading_revision = 2
        history.evidence_ref = history.evidence_ref.replace("revision:1", "revision:2")
        answer = db.session.get(SubmissionAnswer, history.submission_answer_id)
        answer.is_correct = True
        answer.grading_revision = 2
        db.session.commit()
        second, cached, _ = service.generate(self.course, requested_by=self.teacher.id)
        self.assertFalse(cached)
        self.assertNotEqual(first.input_hash, second.input_hash)

    def test_api_filters_foreign_student_risk_without_persisting_its_refs(self):
        self._attempt(course=self.course, student=self.student, correct=False)
        self._attempt(course=self.course, student=self.no_data, correct=False)
        packet = build_class_lesson4_packet(self.course)
        first, second = packet["students"]
        response = _teacher_support_response(packet)
        first_risk = response["students"][0]["next_risk_hypotheses"][0]
        first_risk["basis_evidence_refs"] = [second["events"][0]["event_ref"]]
        clean = validate_class_report(response, packet)
        personal = clean["students"][first["student_ref"]]
        self.assertEqual(personal["next_risk_hypotheses"], [])
        self.assertTrue(clean["class_summary"]["next_risk_hypotheses"])
        self.assertNotIn(second["events"][0]["event_ref"], json.dumps(personal))
        # Causes/observed facts have a stricter contract than optional risks.
        response["students"][0]["cause_hypotheses"][0]["basis_evidence_refs"] = [second["events"][0]["event_ref"]]
        with self.assertRaises(ValueError):
            validate_class_report(response, packet)

    def test_processing_row_coalesces_duplicate_generation(self):
        self._attempt(course=self.course, student=self.student, correct=False)
        service = ClassLesson4ReportService()
        packet = build_class_lesson4_packet(self.course)
        now = dt.datetime.utcnow()
        configuration, _ = service._resolve_configuration(self.course, allow_legacy=False)
        identity = service._identity_for(configuration, self.course, legacy_compatibility=False)
        input_hash = service.input_hash(packet, configuration, identity)
        active = ClassAIAnalysisRun(
            course_id=self.course.id, requested_by=self.teacher.id, scope_code=SCOPE_CODE,
            input_hash=input_hash, provider=configuration.provider,
            model_name=configuration.model_name, prompt_version=PROMPT_VERSION,
            ai_key_group_id=configuration.group_id, ai_config_revision=configuration.config_revision,
            ai_credential_source=configuration.source,
            status="processing", analysis_source="pending", request_data=json.dumps(packet),
            response_data="{}", source_cutoff=now, roster_count=2, event_count=1,
            active_key=f"{self.course.id}:{SCOPE_CODE}:{input_hash}", created_at=now,
        )
        db.session.add(active)
        db.session.commit()
        run, cached, _ = service.generate(self.course, requested_by=self.teacher.id)
        self.assertTrue(cached)
        self.assertEqual(run.id, active.id)
        self.assertEqual(ClassAIAnalysisRun.query.count(), 1)

    def test_large_packet_is_batched_and_reports_omitted_ai_events(self):
        self._attempt(course=self.course, student=self.student, correct=False)
        self._attempt(course=self.course, student=self.student, correct=True, revision=2)
        packet = build_class_lesson4_packet(self.course)
        with patch.dict(os.environ, {"CLASS_REPORT_AI_BATCH_SIZE": "1", "CLASS_REPORT_AI_MAX_EVENTS_PER_STUDENT": "1"}, clear=False):
            service = ClassLesson4ReportService()
            batches = service._batch_packets(packet)
            self.assertEqual(len(batches), 2)
            self.assertEqual({row["student_ref"] for batch in batches for row in batch["students"]}, {row["student_ref"] for row in packet["students"]})
            self.assertEqual(sum(batch["coverage"]["events_omitted_for_ai_batch"] for batch in batches), 0)
            sent_events = [event for batch in batches for student in batch["students"] for event in student["events"]]
            self.assertTrue(all(event["event_type"] == "observed_error" for event in sent_events))
            serialized = json.dumps(batches, ensure_ascii=False)
            self.assertIn("expected_answer_text", serialized)
            self.assertNotIn('"mastery"', serialized)

    def test_external_error_copy_keeps_only_answered_wrong_tf_statements(self):
        packet = {
            "scope": {"scope_code": "9C8-i"},
            "roster": [{"student_ref": "student-token"}],
            "coverage": {"roster_count": 1, "event_count": 2},
            "students": [{"student_ref": "student-token", "events": [
                {
                    "event_ref": "partial-wrong", "evidence_ref": "partial-wrong",
                    "event_type": "observed_partial", "outcome": "partial",
                    "student_ref": "student-token", "curriculum_code": "9C8-i-1",
                    "coverage_status": "partial", "statement_results": [
                        {"label": "a", "curriculum_code": "9C8-i-2", "cognitive_level": "thong_hieu", "actual": False, "expected": True, "status": "answered", "correct": False},
                        {"label": "b", "curriculum_code": "9C8-i-3", "cognitive_level": "thong_hieu", "actual": None, "expected": False, "status": "unanswered", "correct": None},
                    ],
                },
                {
                    "event_ref": "partial-no-error", "evidence_ref": "partial-no-error",
                    "event_type": "observed_partial", "outcome": "partial",
                    "student_ref": "student-token", "curriculum_code": "9C8-i-1",
                    "coverage_status": "partial", "statement_results": [
                        {"label": "a", "curriculum_code": "9C8-i-2", "cognitive_level": "thong_hieu", "actual": True, "expected": True, "status": "answered", "correct": True},
                        {"label": "b", "curriculum_code": "9C8-i-3", "cognitive_level": "thong_hieu", "actual": None, "expected": False, "status": "unanswered", "correct": None},
                    ],
                },
            ]}],
        }
        batches = ClassLesson4ReportService()._batch_packets(packet)
        events = batches[0]["students"][0]["events"]
        self.assertEqual([event["event_ref"] for event in events], ["partial-wrong"])
        self.assertEqual(events[0]["curriculum_code"], "9C8-i-2")
        self.assertEqual(len(events[0]["wrong_statement_results"]), 1)
        self.assertNotIn("expected", events[0]["wrong_statement_results"][0])

    def test_partial_true_false_event_is_not_reported_as_full_progress(self):
        packet = {
            "coverage": {"roster_count": 1, "event_count": 1},
            "students": [{"student_ref": "student-token", "events": [{
                "event_ref": "partial-ref", "outcome": "partial",
                "event_type": "observed_partial", "curriculum_code": "9C8-i-1",
                "coverage_status": "partial", "complete_response": False,
                "answered_statement_count": 3, "statement_count": 4,
            }]}],
        }
        report = deterministic_class_report(packet)
        row = report["students"][0]
        self.assertEqual(row["observed_progress"], [])
        self.assertEqual(row["observed_errors"], [])
        self.assertEqual(row["observed_events"][0]["coverage_status"], "partial")

    def test_routes_enforce_owner_and_return_report(self):
        self._attempt(course=self.course, student=self.student, correct=False)
        owner = self._login(self.teacher)
        provider = _Session(_teacher_support_response)
        with patch("requests.Session.post", side_effect=provider.post):
            response = owner.post(f"/courses/{self.course.id}/lesson4-report/generate", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["report"]["report"]["scope"]["scope_code"], "9C8-i")
        self.assertEqual(response.get_json()["status"], "completed")
        page = owner.get(f"/courses/{self.course.id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("lesson4-ai-report", page.get_data(as_text=True))
        self.assertIn("/ai-reports/class", page.get_data(as_text=True))
        run = ClassAIAnalysisRun.query.filter_by(course_id=self.course.id).order_by(ClassAIAnalysisRun.id.desc()).first()
        review = owner.post(
            f"/courses/{self.course.id}/lesson4-report/{run.id}/review",
            json={"status": "confirmed", "review_note": "Đã đối chiếu bằng chứng."},
        )
        self.assertEqual(review.status_code, 200)
        db.session.refresh(run)
        self.assertEqual(run.review_status, "confirmed")
        # A subsequent finalized answer makes the old report unconfirmable.
        self._attempt(course=self.course, student=self.student, correct=True, revision=2)
        stale = owner.post(f"/courses/{self.course.id}/lesson4-report/{run.id}/review", json={"status": "confirmed"})
        self.assertEqual(stale.status_code, 409)
        other = self._login(self.other_teacher)
        self.assertEqual(other.get(f"/courses/{self.course.id}/lesson4-report").status_code, 403)
        self.assertEqual(other.post(f"/courses/{self.course.id}/lesson4-report/generate", json={}).status_code, 403)
        self.assertEqual(other.post(
            f"/courses/{self.course.id}/lesson4-report/{run.id}/review", json={"status": "confirmed"}
        ).status_code, 403)


if __name__ == "__main__":
    unittest.main()
