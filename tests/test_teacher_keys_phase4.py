"""Focused mocked coverage for teacher-key Phase 4 runtime scheduling."""

from __future__ import annotations

import datetime as dt
import os
import unittest
from unittest.mock import patch
from email.utils import format_datetime

from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
import config

config.load_local_environment = lambda *args, **kwargs: None

from app import app
from database import db
from models import AIProjectCooldown, Course, TeacherAIKey, TeacherAIKeyGroup, User
from services.ai_gateway import (
    AICooldownError,
    AIGatewayError,
    GeminiAIGateway,
    credential_fingerprint,
    encrypt_credential,
    _project_scope,
)


class _Reply:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.body = body if body is not None else {
            "choices": [{"message": {"content": '{"ok": true}'}}]
        }

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


class TeacherKeysPhase4Tests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AI_CREDENTIAL_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "FLASK_SECRET_KEY": "phase4-test-session-secret",
            "AI_GEMINI_MAX_HTTP_ATTEMPTS": "4",
            "AI_GEMINI_TRANSIENT_RETRIES": "1",
            "AI_GEMINI_DEADLINE_SECONDS": "5",
            "AI_GEMINI_PROJECT_COOLDOWN_SECONDS": "60",
        })
        self.env.start()
        self.settings = patch.dict(app.config, {"TESTING": True, "WTF_CSRF_ENABLED": False})
        self.settings.start()
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="phase4-owner", fullname="Owner", user_code="P4O", role="teacher")
        db.session.add(self.teacher)
        db.session.flush()
        self.group = TeacherAIKeyGroup(
            owner_id=self.teacher.id, name="phase4-default", is_default=True,
        )
        db.session.add(self.group)
        db.session.flush()
        self.course = Course(
            course_name="Phase 4 class", subject="Toán", teacher_id=self.teacher.id,
        )
        db.session.add(self.course)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.settings.stop()
        self.env.stop()

    def key(self, raw, project="default", order=0):
        key = TeacherAIKey(
            group_id=self.group.id,
            encrypted_key=encrypt_credential(raw),
            key_fingerprint=credential_fingerprint(raw),
            key_hint=raw[-4:],
            project_ref=project,
            sort_order=order,
            last_test_status="ok",
            last_tested_at=dt.datetime.utcnow(),
        )
        db.session.add(key)
        db.session.commit()
        return key

    def complete(self, provider):
        gateway = GeminiAIGateway(http_session=provider, sleep_fn=lambda _: None)
        configuration = gateway.resolve_course(self.course)
        return gateway.complete(
            configuration,
            messages=[{"role": "user", "content": "synthetic phase4"}],
        )

    def test_round_robin_advances_without_revision_change(self):
        first = self.key("phase4-round-robin-key-a", order=0)
        second = self.key("phase4-round-robin-key-b", order=1)
        revision = self.group.config_revision

        one = _Session([_Reply()])
        self.assertEqual(self.complete(one), {"ok": True})
        self.assertEqual(one.calls[0][1]["headers"]["Authorization"], "Bearer phase4-round-robin-key-a")

        two = _Session([_Reply()])
        self.assertEqual(self.complete(two), {"ok": True})
        self.assertEqual(two.calls[0][1]["headers"]["Authorization"], "Bearer phase4-round-robin-key-b")
        db.session.refresh(self.group)
        self.assertEqual(self.group.config_revision, revision)
        self.assertEqual(TeacherAIKey.query.order_by(TeacherAIKey.sort_order).first().id, first.id)
        self.assertTrue(all(key.last_test_status == "ok" for key in (first, second)))

    def test_quota_wait_preserves_verified_state_and_honors_long_retry_after(self):
        first = self.key("phase4-quota-key-a", project="project-a", order=0)
        retry_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
        provider = _Session([_Reply(
            429,
            {"error": {"status": "RESOURCE_EXHAUSTED"}},
            {"Retry-After": format_datetime(retry_at, usegmt=True)},
        )])
        sleeps = []
        gateway = GeminiAIGateway(http_session=provider, sleep_fn=sleeps.append)
        with self.assertRaises(AICooldownError):
            gateway.complete(gateway.resolve_course(self.course), messages=[{"role": "user", "content": "synthetic"}])
        db.session.refresh(first)
        self.assertEqual(first.last_test_status, "ok")
        self.assertIsNotNone(first.last_tested_at)
        cooldown = AIProjectCooldown.query.filter_by(
            scope_key=_project_scope(self.teacher.id, "project-a")
        ).one()
        self.assertGreaterEqual(
            (cooldown.cooldown_until - dt.datetime.utcnow()).total_seconds(), 7190,
        )
        self.assertEqual(sleeps, [])

    def test_quota_does_not_cycle_same_project_but_uses_different_project(self):
        self.key("phase4-shared-key-a", project="same-project", order=0)
        self.key("phase4-shared-key-b", project="same-project", order=1)
        self.key("phase4-other-key", project="other-project", order=2)
        provider = _Session([
            _Reply(429, {"error": {"status": "RESOURCE_EXHAUSTED"}}, {"Retry-After": "300"}),
            _Reply(),
        ])
        self.assertEqual(self.complete(provider), {"ok": True})
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(provider.calls[0][1]["headers"]["Authorization"], "Bearer phase4-shared-key-a")
        self.assertEqual(provider.calls[1][1]["headers"]["Authorization"], "Bearer phase4-other-key")

    def test_invalid_key_is_paused_and_second_key_can_serve(self):
        first = self.key("phase4-invalid-key-a", order=0)
        second = self.key("phase4-invalid-key-b", order=1)
        provider = _Session([_Reply(401), _Reply()])
        self.assertEqual(self.complete(provider), {"ok": True})
        db.session.refresh(first)
        db.session.refresh(second)
        self.assertTrue(first.is_paused)
        self.assertEqual(first.last_test_status, "failed")
        self.assertFalse(second.is_paused)

        probe = _Session([_Reply()])
        GeminiAIGateway(http_session=probe, sleep_fn=lambda _: None).test_key(first, group=self.group)
        db.session.refresh(first)
        self.assertFalse(first.is_paused)
        self.assertEqual(first.last_test_status, "ok")

    def test_bad_request_and_model_error_do_not_burn_remaining_keys(self):
        first = self.key("phase4-bad-request-key-a", order=0)
        second = self.key("phase4-bad-request-key-b", order=1)
        provider = _Session([_Reply(400, {"error": {"message": "private student data"}}), _Reply()])
        with self.assertRaises(AIGatewayError):
            self.complete(provider)
        self.assertEqual(len(provider.calls), 1)
        db.session.refresh(second)
        self.assertEqual(second.last_test_status, "ok")

        # The queue was advanced by the first attempted request, so the next
        # request reaches the other verified key; the 404 itself still never
        # rotates within its own request.
        model_provider = _Session([_Reply(404, {"error": {"message": "model not found"}}), _Reply()])
        with self.assertRaises(AIGatewayError):
            self.complete(model_provider)
        self.assertEqual(len(model_provider.calls), 1)
        self.assertTrue(first.last_test_status == "ok" or second.last_test_status == "ok")

    def test_transient_retry_keeps_verified_key_eligible(self):
        first = self.key("phase4-transient-key-a", project="project-a", order=0)
        self.key("phase4-transient-key-b", project="project-b", order=1)
        provider = _Session([_Reply(503), _Reply(503), _Reply()])
        self.assertEqual(self.complete(provider), {"ok": True})
        self.assertEqual(len(provider.calls), 3)
        db.session.refresh(first)
        self.assertEqual(first.last_test_status, "ok")


if __name__ == "__main__":
    unittest.main()
