"""Focused mocked coverage for the Phase 1–2 teacher-key surface."""

import os
import unittest
from unittest.mock import patch

import requests
from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
import config

config.load_local_environment = lambda *args, **kwargs: None

from app import app
from database import db
from models import Course, TeacherAIKey, TeacherAIKeyGroup, User
from services.ai_gateway import (
    AIConfiguration,
    AIConfigurationError,
    AIGatewayError,
    GeminiAIGateway,
    TEACHER_GEMINI_MODEL,
    credential_fingerprint,
    encrypt_credential,
)


class _Reply:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self.headers = {}
        self.body = body if body is not None else {"choices": [{"message": {"content": '{"ok": true}'}}]}

    def json(self):
        return self.body


class _Session:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.replies:
            raise AssertionError("unexpected provider call")
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


class TeacherAISimplifiedReview(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AI_CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "FLASK_SECRET_KEY": "phase12-test-session-secret",
            "AI_LEGACY_ENV_FALLBACK_ENABLED": "1",
            "AI_ANALYSIS_API_URL": "https://legacy.invalid/api",
            "AI_ANALYSIS_API_KEY": "must-not-be-used",
        })
        self.env.start()
        self.settings = patch.dict(app.config, {"TESTING": True, "WTF_CSRF_ENABLED": False})
        self.settings.start()
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="phase12-teacher", fullname="Teacher", user_code="P12T", role="teacher")
        self.other = User(username="phase12-other", fullname="Other", user_code="P12O", role="teacher")
        db.session.add_all([self.teacher, self.other])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.settings.stop()
        self.env.stop()

    def browser(self, user=None):
        user = user or self.teacher
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return client

    def test_simple_save_creates_fixed_internal_group_and_probes_without_raw_key(self):
        provider = _Session([_Reply(), _Reply()])

        class ProbeGateway(GeminiAIGateway):
            def __init__(self, *args, **kwargs):
                super().__init__(http_session=provider, sleep_fn=lambda _: None)

        raw_keys = ["phase12-private-key-0001", "phase12-private-key-0002"]
        with patch("routes.ai_settings.GeminiAIGateway", ProbeGateway):
            response = self.browser().post(
                "/teacher/ai-settings/keys",
                data={"keys": "\n".join(raw_keys)},
                follow_redirects=True,
            )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertNotIn(raw_keys[0], page)
        self.assertNotIn("Tạo nhóm AI", page)
        self.assertNotIn("model_name", page)
        self.assertIn("Kiểm tra và lưu", page)
        group = TeacherAIKeyGroup.query.one()
        self.assertEqual(group.model_name, TEACHER_GEMINI_MODEL)
        self.assertTrue(group.is_default)
        keys = TeacherAIKey.query.order_by(TeacherAIKey.id).all()
        self.assertEqual([key.last_test_status for key in keys], ["ok", "ok"])
        self.assertEqual([call[1]["json"]["model"] for call in provider.calls], [TEACHER_GEMINI_MODEL] * 2)
        self.assertTrue(all(raw not in key.encrypted_key for raw in raw_keys for key in keys))

    def test_provider_categories_are_distinct_and_sanitized(self):
        config = AIConfiguration(
            source="teacher_group", provider="gemini-openai-compatible", endpoint="https://fake.invalid",
            model_name=TEACHER_GEMINI_MODEL, group_id=1, config_revision=1, owner_id=1,
        )
        cases = [
            (401, {}, "auth", "invalid_or_revoked"),
            (403, {"error": {"status": "PERMISSION_DENIED"}}, "permission", "permission_denied"),
            (429, {}, "quota", "quota_rate_limited"),
            (404, {"error": {"message": "model not found"}}, "model_not_found", "model_not_found"),
            (503, {}, "transient", "network_unavailable"),
        ]
        for status, body, kind, code in cases:
            with self.subTest(status=status):
                gateway = GeminiAIGateway(http_session=_Session([_Reply(status, body)]))
                with self.assertRaises(AIGatewayError) as raised:
                    gateway._post_json(config, "private-key-never-logged", {"model": TEACHER_GEMINI_MODEL})
                self.assertEqual(getattr(raised.exception, "kind", None), kind)
                self.assertEqual(gateway.public_error_code(raised.exception), code)
                self.assertNotIn("private-key-never-logged", str(raised.exception))

        gateway = GeminiAIGateway(http_session=_Session([requests.ConnectionError("Bearer private-key-never-logged")]))
        with self.assertRaises(AIGatewayError) as raised:
            gateway._post_json(config, "private-key-never-logged", {})
        self.assertEqual(getattr(raised.exception, "kind", None), "network")
        self.assertEqual(gateway.public_error_code(raised.exception), "network_unavailable")
        self.assertNotIn("private-key-never-logged", str(raised.exception))

    def test_unverified_key_is_never_eligible_and_shared_env_is_not_fallback(self):
        group = TeacherAIKeyGroup(
            owner_id=self.teacher.id, name="legacy-default", model_name="attacker-model", is_default=True,
        )
        db.session.add(group)
        db.session.flush()
        raw = "phase12-unverified-key"
        db.session.add(TeacherAIKey(
            group_id=group.id, encrypted_key=encrypt_credential(raw),
            key_fingerprint=credential_fingerprint(raw), key_hint=raw[-4:],
        ))
        course = Course(course_name="Phase 1–2", subject="Toán", teacher_id=self.teacher.id)
        db.session.add(course)
        db.session.commit()
        provider = _Session([])
        gateway = GeminiAIGateway(http_session=provider)
        resolved = gateway.resolve_course(course, allow_legacy=True)
        self.assertEqual(resolved.model_name, TEACHER_GEMINI_MODEL)
        with self.assertRaises(AIConfigurationError):
            gateway.complete(resolved, messages=[{"role": "user", "content": "synthetic"}])
        self.assertEqual(provider.calls, [])

    def test_existing_default_and_explicit_old_mapping_are_preserved(self):
        default = TeacherAIKeyGroup(owner_id=self.teacher.id, name="old-default", is_default=True)
        old = TeacherAIKeyGroup(owner_id=self.teacher.id, name="old-class", is_default=False)
        db.session.add_all([default, old])
        db.session.flush()
        mapped = Course(course_name="Mapped", subject="Toán", teacher_id=self.teacher.id, ai_key_group_id=old.id)
        db.session.add(mapped)
        db.session.commit()
        provider = _Session([_Reply()])

        class ProbeGateway(GeminiAIGateway):
            def __init__(self, *args, **kwargs):
                super().__init__(http_session=provider, sleep_fn=lambda _: None)

        with patch("routes.ai_settings.GeminiAIGateway", ProbeGateway):
            response = self.browser().post(
                "/teacher/ai-settings/keys", data={"keys": "phase12-existing-default-key"}, follow_redirects=True
            )
        self.assertEqual(response.status_code, 200)
        db.session.refresh(mapped)
        self.assertEqual(mapped.ai_key_group_id, old.id)
        self.assertEqual(TeacherAIKeyGroup.query.filter_by(id=default.id).count(), 1)
        self.assertEqual(TeacherAIKeyGroup.query.filter_by(id=old.id).count(), 1)
        self.assertIn("chưa được gộp", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
