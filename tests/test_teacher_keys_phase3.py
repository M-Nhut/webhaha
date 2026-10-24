"""Focused mocked coverage for teacher-key Phase 3 default resolution."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
import config

config.load_local_environment = lambda *args, **kwargs: None

from app import app
from database import db
from models import Course, TeacherAIKey, TeacherAIKeyGroup, User
from services.ai_gateway import (
    AIConfigurationError,
    GeminiAIGateway,
    TEACHER_GEMINI_MODEL,
    credential_fingerprint,
    encrypt_credential,
)
from services.class_lesson4_report import ClassLesson4ReportService
from services.ai_profile_analysis import AIProfileAnalyzer


class _Reply:
    def __init__(self, status=200):
        self.status_code = status
        self.headers = {}
        self.body = {"choices": [{"message": {"content": '{"ok": true}'}}]}

    def json(self):
        return self.body


class _Session:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        reply = self.replies.pop(0)
        return reply


class TeacherKeysPhase3Tests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AI_CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "FLASK_SECRET_KEY": "phase3-test-session-secret",
            "AI_ANALYSIS_API_URL": "https://legacy.invalid/api",
            "AI_ANALYSIS_API_KEY": "legacy-must-not-be-used",
            "AI_LEGACY_ENV_FALLBACK_ENABLED": "1",
        })
        self.env.start()
        self.app_settings = patch.dict(app.config, {"TESTING": True, "WTF_CSRF_ENABLED": False})
        self.app_settings.start()
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="phase3-owner", fullname="Owner", user_code="P3O", role="teacher", is_active=True)
        self.other = User(username="phase3-other", fullname="Other", user_code="P3T", role="teacher", is_active=True)
        self.admin = User(username="phase3-admin", fullname="Admin", user_code="P3A", role="admin", is_active=True)
        db.session.add_all([self.teacher, self.other, self.admin])
        db.session.flush()
        self.default = TeacherAIKeyGroup(
            owner_id=self.teacher.id, name="oldest-default", model_name="stale-model", is_default=True,
        )
        self.newer_default = TeacherAIKeyGroup(
            owner_id=self.teacher.id, name="newer-default", model_name="other-stale-model", is_default=True,
        )
        self.other_default = TeacherAIKeyGroup(
            owner_id=self.other.id, name="other-default", is_default=True,
        )
        db.session.add_all([self.default, self.newer_default, self.other_default])
        db.session.flush()
        # Keep the first group deterministic and active for normal tests.
        self.newer_default.is_default = False
        self.course = Course(
            course_name="Phase 3 class", subject="Toán", teacher_id=self.teacher.id,
            # This retained value is deliberately not an effective override.
            ai_key_group_id=self.other_default.id,
        )
        db.session.add(self.course)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.app_settings.stop()
        self.env.stop()

    def browser(self, user):
        from flask import g
        g.pop("_login_user", None)
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return client

    def verified_key(self, group, raw, order=0):
        key = TeacherAIKey(
            group_id=group.id, encrypted_key=encrypt_credential(raw),
            key_fingerprint=credential_fingerprint(raw), key_hint=raw[-4:],
            last_test_status="ok", sort_order=order,
        )
        db.session.add(key)
        db.session.commit()
        return key

    def test_resolver_uses_oldest_owner_default_and_ignores_legacy_mapping(self):
        self.newer_default.is_default = True
        db.session.commit()
        configuration = GeminiAIGateway().resolve_course(self.course, allow_legacy=True)
        self.assertEqual(configuration.group_id, self.default.id)
        self.assertEqual(configuration.model_name, TEACHER_GEMINI_MODEL)
        self.assertNotEqual(configuration.group_id, self.course.ai_key_group_id)

    def test_new_course_and_retired_assignment_route_cannot_set_legacy_override(self):
        client = self.browser(self.admin)
        response = client.post("/courses/new", data={
            "course_name": "Forged mapping", "subject": "Toán", "teacher_id": self.teacher.id,
            "ai_key_group_id": self.other_default.id, "is_active": "1",
        })
        self.assertEqual(response.status_code, 302)
        created = Course.query.filter_by(course_name="Forged mapping").one()
        self.assertIsNone(created.ai_key_group_id)
        self.assertEqual(GeminiAIGateway().resolve_course(created).group_id, self.default.id)

        teacher_client = self.browser(self.teacher)
        response = teacher_client.post(
            f"/courses/{self.course.id}/ai-settings",
            data={"ai_key_group_id": self.other_default.id},
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.course)
        self.assertEqual(self.course.ai_key_group_id, self.other_default.id)
        self.assertEqual(GeminiAIGateway().resolve_course(self.course).group_id, self.default.id)

    def test_default_change_during_retry_stops_stale_credential(self):
        self.verified_key(self.default, "phase3-old-owner-key")
        self.verified_key(self.newer_default, "phase3-new-owner-key")
        provider = _Session([_Reply(503), _Reply(200)])

        def switch_default(_seconds):
            self.default.is_default = False
            self.newer_default.is_default = True
            db.session.commit()

        gateway = GeminiAIGateway(http_session=provider, sleep_fn=switch_default)
        configuration = gateway.resolve_course(self.course)
        with self.assertRaises(AIConfigurationError):
            gateway.complete(configuration, messages=[{"role": "user", "content": "synthetic"}])
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0][1]["headers"]["Authorization"], "Bearer phase3-old-owner-key")

    def test_unavailable_report_identity_changes_after_reassignment(self):
        # No owner defaults: the old explicit mapping must not make this
        # report appear to have an available/current group.
        self.default.is_default = False
        self.other_default.is_default = False
        self.course.ai_key_group_id = self.default.id
        db.session.commit()
        service = ClassLesson4ReportService(http_session=_Session([]))
        first, cached, _ = service.generate(
            self.course, requested_by=self.teacher.id, allow_legacy=True, legacy_compatibility=True,
        )
        self.assertFalse(cached)
        self.assertEqual(first.ai_credential_source, "unavailable")
        self.assertIsNone(first.ai_key_group_id)
        self.assertEqual(first.ai_config_revision, -self.teacher.id)
        profile_identity = AIProfileAnalyzer._unavailable_course_identity(self.course)
        self.assertIsNone(profile_identity["group_id"])
        self.assertEqual(profile_identity["revision"], -self.teacher.id)

        self.course.teacher_id = self.other.id
        db.session.commit()
        second, cached, _ = service.generate(
            self.course, requested_by=self.other.id, allow_legacy=True, legacy_compatibility=True,
        )
        self.assertFalse(cached)
        self.assertNotEqual(first.id, second.id)
        self.assertNotEqual(first.input_hash, second.input_hash)
        latest = service.get_latest(self.course, allow_legacy=True, legacy_compatibility=False)
        self.assertEqual(latest.id, second.id)


if __name__ == "__main__":
    unittest.main()
