"""Independent boundary checks for teacher credentials and failover policy."""
import os
import datetime as dt
import json
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)
os.environ["FLASK_SECRET_KEY"] = "gateway-review-isolated-test-session"
os.environ["AI_CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
import config
config.load_local_environment = lambda *args, **kwargs: None

_storage = tempfile.TemporaryDirectory(prefix="gateway-review-tests-")
with patch.object(config, "upload_directories", return_value={
    "UPLOAD_FOLDER_AVATARS": f"{_storage.name}/avatars",
    "UPLOAD_FOLDER_COURSES": f"{_storage.name}/courses",
}):
    from app import app
from database import db
from models import Course, TeacherAIKey, TeacherAIKeyGroup, User
from services.ai_gateway import (
    AIConfigurationError, AIGatewayError, GeminiAIGateway,
    credential_fingerprint, decrypt_credential, encrypt_credential,
)


class Reply:
    def __init__(self, status, body=None):
        self.status_code = status
        self.headers = {"Retry-After": "60"}
        self.body = body if body is not None else {"choices": [{"message": {"content": '{"ok":true}'}}]}

    def json(self):
        return self.body


class Client:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.replies:
            raise AssertionError("Unexpected external call")
        return self.replies.pop(0)


class AIGatewayIndependentReview(unittest.TestCase):
    def setUp(self):
        self.network = patch("requests.sessions.Session.request", side_effect=AssertionError("Real network is forbidden in isolated tests"))
        self.network.start()
        self.env = patch.dict(os.environ, {
            "AI_CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "FLASK_SECRET_KEY": "isolated-review-session-secret-not-for-production",
            "AI_GEMINI_MAX_PROJECT_ATTEMPTS": "2",
            "AI_LEGACY_ENV_FALLBACK_ENABLED": "1",
            "AI_ANALYSIS_API_URL": "https://legacy.example/api",
            "AI_ANALYSIS_API_KEY": "legacy-key-never-use-for-assigned-group",
        })
        self.env.start()
        self.app_settings = patch.dict(app.config, {"TESTING": True, "WTF_CSRF_ENABLED": False})
        self.app_settings.start()
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="key-review-owner", fullname="Owner", user_code="KR1", role="teacher")
        self.other = User(username="key-review-other", fullname="Other", user_code="KR2", role="teacher")
        self.teacher.set_password("test-only")
        self.other.set_password("test-only")
        db.session.add_all([self.teacher, self.other])
        db.session.flush()
        self.group = TeacherAIKeyGroup(owner_id=self.teacher.id, name="Review", is_default=True)
        db.session.add(self.group)
        db.session.flush()
        self.course = Course(course_name="Review class", subject="Toán", teacher_id=self.teacher.id,
                             ai_key_group_id=self.group.id)
        db.session.add(self.course)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.app_settings.stop()
        self.env.stop()
        self.network.stop()

    def browser(self, user):
        from flask import g
        g.pop("_login_user", None)
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return client

    def key(self, raw, project, order, *, verified=True):
        item = TeacherAIKey(group_id=self.group.id, encrypted_key=encrypt_credential(raw),
                            key_fingerprint=credential_fingerprint(raw), key_hint=raw[-4:],
                            project_ref=project, sort_order=order,
                            last_test_status="ok" if verified else None)
        db.session.add(item)
        db.session.commit()
        db.session.expire(self.group, ["keys"])
        return item

    def complete(self, client):
        gateway = GeminiAIGateway(http_session=client, sleep_fn=lambda _: None)
        return gateway.complete(gateway.resolve_course(self.course), messages=[{"role": "user", "content": "Synthetic test"}])

    def test_ciphertext_is_authenticated_and_missing_secret_fails_closed(self):
        token = encrypt_credential("test-secret-raw-value")
        self.assertNotIn("test-secret-raw-value", token)
        self.assertEqual(decrypt_credential(token), "test-secret-raw-value")
        with patch.dict(os.environ, {"AI_CREDENTIAL_ENCRYPTION_KEY": ""}):
            with self.assertRaises(AIConfigurationError):
                decrypt_credential(token)

    def test_revoked_key_can_use_second_key_in_same_project(self):
        self.key("review-key-one", "project-a", 0)
        self.key("review-key-two", "project-a", 1)
        client = Client([Reply(401), Reply(200)])
        self.assertEqual(self.complete(client), {"ok": True})
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[1][1]["headers"]["Authorization"], "Bearer review-key-two")

    def test_quota_skips_same_project_and_persists_across_gateway_instances(self):
        self.key("review-key-one", "project-a", 0)
        self.key("review-key-two", "project-a", 1)
        self.key("review-key-three", "project-b", 2)
        client = Client([Reply(429), Reply(200)])
        self.assertEqual(self.complete(client), {"ok": True})
        self.assertEqual(client.calls[1][1]["headers"]["Authorization"], "Bearer review-key-three")
        second = Client([Reply(200)])
        self.assertEqual(self.complete(second), {"ok": True})
        self.assertEqual(second.calls[0][1]["headers"]["Authorization"], "Bearer review-key-three")

    def test_cooled_projects_do_not_consume_actual_call_budget(self):
        for index, project in enumerate(("project-a", "project-b", "project-c")):
            self.key(f"review-key-{index}", project, index)
        gateway = GeminiAIGateway()
        gateway._mark_cooldown(self.teacher.id, "project-a")
        gateway._mark_cooldown(self.teacher.id, "project-b")
        db.session.commit()
        client = Client([Reply(200)])
        self.assertEqual(self.complete(client), {"ok": True})
        self.assertEqual(len(client.calls), 1)

    def test_paused_default_group_never_falls_through_to_shared_key(self):
        self.course.ai_key_group_id = None
        self.group.is_active = False
        db.session.commit()
        with self.assertRaises(AIConfigurationError):
            GeminiAIGateway().resolve_course(self.course, allow_legacy=True)

    def test_bad_request_is_not_rotated_and_provider_body_not_exposed(self):
        self.key("review-key-one", "project-a", 0)
        self.key("review-key-two", "project-b", 1)
        client = Client([Reply(400, {"error": {"message": "echo review-key-one private student data"}}), Reply(200)])
        with self.assertRaises(AIGatewayError) as raised:
            self.complete(client)
        self.assertEqual(len(client.calls), 1)
        self.assertNotIn("review-key-one", str(raised.exception))
        self.assertNotIn("private student data", str(raised.exception))

    def test_explicit_invalid_assignment_never_uses_shared_key(self):
        self.course.teacher_id = self.other.id
        db.session.commit()
        with self.assertRaises(AIConfigurationError):
            GeminiAIGateway().resolve_course(self.course, allow_legacy=True)

    def test_disabled_explicit_group_never_uses_shared_key(self):
        self.group.is_active = False
        db.session.commit()
        with self.assertRaises(AIConfigurationError):
            GeminiAIGateway().resolve_course(self.course, allow_legacy=True)

    def test_course_transfer_invalidates_previously_resolved_configuration(self):
        self.key("review-key-one", "project-a", 0)
        client = Client([Reply(200)])
        gateway = GeminiAIGateway(http_session=client)
        configuration = gateway.resolve_course(self.course)
        self.course.teacher_id = self.other.id
        db.session.commit()
        with self.assertRaises(AIConfigurationError):
            gateway.complete(configuration, messages=[{"role": "user", "content": "Synthetic"}])
        self.assertEqual(client.calls, [])

    def test_malformed_json_is_not_retried_with_another_key(self):
        self.key("review-key-one", "project-a", 0)
        self.key("review-key-two", "project-b", 1)
        client = Client([Reply(200, {"choices": [{"message": {"content": "invalid-json"}}]}), Reply(200)])
        with self.assertRaises(AIGatewayError):
            self.complete(client)
        self.assertEqual(len(client.calls), 1)

    def test_transfer_during_retry_wait_prevents_second_outbound_call(self):
        self.key("review-key-one", "project-a", 0)
        client = Client([Reply(503), Reply(200)])

        def transfer(_seconds):
            self.course.teacher_id = self.other.id
            db.session.commit()

        gateway = GeminiAIGateway(http_session=client, sleep_fn=transfer)
        with self.assertRaises(AIConfigurationError):
            gateway.complete(gateway.resolve_course(self.course), messages=[{"role": "user", "content": "Synthetic"}])
        self.assertEqual(len(client.calls), 1)

    def test_exact_key_test_never_rotates(self):
        key = self.key("review-key-one", "project-a", 0)
        self.key("review-key-two", "project-b", 1)
        client = Client([Reply(401), Reply(200)])
        gateway = GeminiAIGateway(http_session=client, sleep_fn=lambda _: None)
        with self.assertRaises(AIGatewayError):
            gateway.test_key(key)
        self.assertEqual(len(client.calls), 1)
        self.assertNotIn("student_id", str(client.calls[0][1]["json"]))

    def test_teacher_cannot_modify_or_test_another_teachers_key(self):
        key = self.key("review-long-private-key", "project-a", 0)
        client = self.browser(self.other)
        with patch("requests.Session.post", side_effect=AssertionError("Must not call provider")):
            for action in ("retry", "delete", "test"):
                response = client.post(f"/teacher/ai-settings/keys/{key.id}/{action}")
                self.assertIn(response.status_code, (403, 404))
        db.session.refresh(key)
        self.assertFalse(key.is_paused)
        self.assertIsNotNone(db.session.get(TeacherAIKey, key.id))

    def test_bulk_add_renders_only_mask_and_never_raw_key(self):
        raw = "review-private-credential-123456789"
        client = self.browser(self.teacher)
        provider = Client([Reply(200)])
        class ProbeGateway(GeminiAIGateway):
            def __init__(self, *args, **kwargs):
                super().__init__(http_session=provider, sleep_fn=lambda _: None)
        with patch("routes.ai_settings.GeminiAIGateway", ProbeGateway):
            response = client.post("/teacher/ai-settings/keys",
                                   data={"keys": raw + "\n" + raw}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(raw, response.get_data(as_text=True))
        stored = TeacherAIKey.query.filter_by(group_id=self.group.id).all()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].last_test_status, "ok")
        self.assertEqual(len(provider.calls), 1)
        self.assertNotIn(raw, stored[0].encrypted_key)
        self.assertEqual(decrypt_credential(stored[0].encrypted_key), raw)

    def test_credential_write_requires_csrf(self):
        client = self.browser(self.teacher)
        with patch.dict(app.config, {"WTF_CSRF_ENABLED": True}):
            response = client.post("/teacher/ai-settings/keys",
                                   data={"keys": "review-private-credential-123456789"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(TeacherAIKey.query.count(), 0)

    def test_admin_cannot_spend_teacher_key_or_list_teacher_credentials(self):
        admin = User(username="key-review-admin", fullname="Admin", user_code="KRA", role="admin")
        admin.set_password("test-only")
        db.session.add(admin)
        db.session.commit()
        client = self.browser(admin)
        with patch("requests.Session.post", side_effect=AssertionError("Must not call provider")):
            response = client.post(f"/courses/{self.course.id}/lesson4-report/generate")
            self.assertEqual(response.status_code, 403)
            self.assertEqual(client.get("/teacher/ai-settings").status_code, 403)

    def test_current_default_overrides_historical_course_group_without_assignment_route(self):
        historical = TeacherAIKeyGroup(owner_id=self.teacher.id, name="Historical class group", is_default=False)
        db.session.add(historical)
        db.session.flush()
        self.course.ai_key_group_id = historical.id
        db.session.commit()
        gateway = GeminiAIGateway()
        configuration = gateway.resolve_course(self.course)
        self.assertEqual(configuration.group_id, self.group.id)
        self.assertEqual(configuration.owner_id, self.teacher.id)
        client = self.browser(self.teacher)
        response = client.post(f"/courses/{self.course.id}/ai-settings", data={"ai_key_group_id": historical.id})
        self.assertEqual(response.status_code, 404)
        db.session.refresh(self.course)
        self.assertEqual(self.course.ai_key_group_id, historical.id)
        self.assertEqual(gateway.resolve_course(self.course).group_id, self.group.id)

    def test_owner_cannot_operate_keys_outside_current_default_group(self):
        historical = TeacherAIKeyGroup(owner_id=self.teacher.id, name="Historical private group", is_default=False)
        db.session.add(historical)
        db.session.flush()
        raw = "historical-private-key-never-return"
        key = TeacherAIKey(group_id=historical.id, encrypted_key=encrypt_credential(raw),
            key_fingerprint=credential_fingerprint(raw), key_hint=raw[-4:], last_test_status="ok")
        db.session.add(key)
        db.session.commit()
        owner = self.browser(self.teacher)
        for action in ("retry", "test", "delete"):
            with self.subTest(action=action):
                self.assertEqual(owner.post(f"/teacher/ai-settings/keys/{key.id}/{action}").status_code, 404)
        self.assertIsNotNone(db.session.get(TeacherAIKey, key.id))
        self.assertEqual(db.session.get(TeacherAIKey, key.id).last_test_status, "ok")

    def test_failed_class_requests_retry_and_configuration_revision_changes_identity(self):
        from services.class_lesson4_report import ClassLesson4ReportService
        provider = Client([])
        service = ClassLesson4ReportService(http_session=provider, sleep_fn=lambda _: None)
        first, cached, _ = service.generate(self.course, requested_by=self.teacher.id, allow_legacy=False, legacy_compatibility=False)
        self.assertFalse(cached)
        self.assertEqual(first.status, "failed")
        self.assertEqual(first.analysis_source, "ai_api")
        again, cached, _ = service.generate(self.course, requested_by=self.teacher.id, allow_legacy=False, legacy_compatibility=False)
        self.assertFalse(cached)
        self.assertEqual(again.status, "failed")
        self.assertNotEqual(again.id, first.id)
        self.assertEqual(again.input_hash, first.input_hash)
        self.group.touch_configuration()
        db.session.commit()
        revised, cached, _ = service.generate(self.course, requested_by=self.teacher.id, allow_legacy=False, legacy_compatibility=False)
        self.assertFalse(cached)
        self.assertNotEqual(revised.input_hash, first.input_hash)
        self.assertEqual(revised.ai_config_revision, self.group.config_revision)
        self.assertEqual(provider.calls, [])
        self.assertIsNone(revised.active_key)

    def test_unverified_default_key_cannot_send_report_traffic(self):
        self.key("review-unverified-private-key", "project-a", 0, verified=False)
        provider = Client([])
        with self.assertRaises(AIConfigurationError):
            self.complete(provider)
        self.assertEqual(provider.calls, [])

    def test_individual_report_sends_only_selected_course_evidence(self):
        from models import Enrollment, Exam, ExamAnswer, ExamQuestion, ExamSubmission, SubmissionAnswer
        from services.personalization_evidence import rebuild_error_observations
        from services.ai_profile_analysis import AIProfileAnalyzer

        self.key("review-long-private-key", "project-a", 0)
        student = User(username="review-shared-student", fullname="Shared", user_code="KRS", role="student")
        student.set_password("test-only")
        other_course = Course(course_name="Other class", subject="Toán", teacher_id=self.other.id)
        db.session.add_all([student, other_course])
        db.session.flush()
        for course, marker in ((self.course, "OWN_COURSE_EVIDENCE"), (other_course, "FOREIGN_COURSE_EVIDENCE")):
            db.session.add(Enrollment(student_id=student.id, course_id=course.id, status="active"))
            exam = Exam(title="Synthetic assessment", course_id=course.id, created_by=course.teacher_id,
                        assessment_purpose="initial_diagnostic")
            db.session.add(exam)
            db.session.flush()
            question = ExamQuestion(exam_id=exam.id, question_text=marker, question_type="single",
                                    curriculum_code="9C8-i-1", difficulty_level="thong_hieu", points=1)
            db.session.add(question)
            db.session.flush()
            # Personal report evidence accepts only a finalized complete
            # diagnostic/fixed-practice paper: 12 single + 4 TF + 6 short.
            for index, kind in enumerate(["single"] * 11 + ["true_false"] * 4 + ["short_answer"] * 6, start=1):
                db.session.add(ExamQuestion(exam_id=exam.id, question_text=f"Synthetic question {index + 1}",
                    question_type=kind, curriculum_code="9C8-i-1", order_index=index, points=1))
            correct = ExamAnswer(question_id=question.id, answer_text="A", is_correct=True)
            wrong = ExamAnswer(question_id=question.id, answer_text="B", is_correct=False)
            db.session.add_all([correct, wrong])
            db.session.flush()
            submission = ExamSubmission(exam_id=exam.id, student_id=student.id, submitted_at=dt.datetime.utcnow(),
                                        status="graded", is_graded=True, grading_revision=1)
            db.session.add(submission)
            db.session.flush()
            answer = SubmissionAnswer(submission_id=submission.id, question_id=question.id,
                                      selected_answer_ids=json.dumps([wrong.id]), is_correct=False,
                                      answer_status="answered", points_earned=0)
            db.session.add(answer)
            db.session.flush()
            rebuild_error_observations(submission)
        db.session.commit()
        result = {"schema_version": "lesson4-diagnostic-report-v1", "overview": "Chưa đủ bằng chứng.",
                  "error_analysis": [], "future_risks": [], "interventions": []}
        client = Client([Reply(200, {"choices": [{"message": {"content": json.dumps(result)}}]})])
        analyzer = AIProfileAnalyzer(http_session=client)
        run, _ = analyzer.analyze(student.id, requested_by=self.teacher.id, course=self.course, allow_legacy=False)
        self.assertEqual(run.status, "completed")
        sent = json.dumps(client.calls[0][1]["json"])
        self.assertIn("OWN_COURSE_EVIDENCE", sent)
        self.assertNotIn("FOREIGN_COURSE_EVIDENCE", sent)
        self.assertNotIn("FOREIGN_COURSE_EVIDENCE", run.request_data)
