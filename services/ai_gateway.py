"""Tenant-scoped Gemini gateway and encrypted credential helpers.

This module is the only place that decrypts a teacher-provided key and the
only place that calls Gemini for report generation.  It intentionally has no
fallback from one teacher/group to another.  A legacy process environment key
is available only to direct compatibility callers or when a server explicitly
enables it for an unassigned legacy course.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import threading
import time
from dataclasses import dataclass
from collections import defaultdict
from email.utils import parsedate_to_datetime

import requests
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from database import db
from models import AIProjectCooldown, Course, TeacherAIKey, TeacherAIKeyGroup


GEMINI_OPENAI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
# Teacher-managed credentials use one server-selected model.  The model is
# deliberately a backend constant: the teacher form never accepts a model
# name, and a stale value in an older key-group row cannot change provider
# routing.  Legacy process-environment integrations keep their own model
# setting in ``legacy_configuration`` for backwards compatibility.
TEACHER_GEMINI_MODEL = (os.environ.get("TEACHER_GEMINI_MODEL", "").strip() or "gemini-3.5-flash-lite")


# ``TeacherAIKey`` predates Phase 4 and has no cursor/last-used column.  The
# existing ``sort_order`` is therefore used as a durable queue cursor: a
# claimed key is moved to the tail without touching the group's
# ``config_revision``.  The lock prevents two requests in one web worker from
# claiming the same head concurrently; a database row lock is also requested
# where the backend supports it.  Cross-worker fairness remains best effort
# until a future schema phase adds an explicit cursor/claim column.
_ROTATION_LOCKS = defaultdict(threading.RLock)


def _rotation_lock(group_id: int):
    return _ROTATION_LOCKS[int(group_id)]


class AIConfigurationError(RuntimeError):
    """A safe, user-actionable configuration problem."""


class AICooldownError(RuntimeError):
    """The configured Gemini project is in a persisted quota cooldown."""


class AIGatewayError(RuntimeError):
    """A sanitized provider failure; it never includes a response body/key."""


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _fernet() -> Fernet:
    """Return the dedicated credential cipher or fail closed.

    ``AI_CREDENTIAL_ENCRYPTION_KEY`` must be a valid Fernet key.  We do not
    derive a fallback from Flask/session/application secrets.
    """
    configured = os.environ.get("AI_CREDENTIAL_ENCRYPTION_KEY", "").strip()
    if not configured:
        raise AIConfigurationError("Chưa cấu hình AI_CREDENTIAL_ENCRYPTION_KEY trên máy chủ.")
    try:
        return Fernet(configured.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise AIConfigurationError("AI_CREDENTIAL_ENCRYPTION_KEY không hợp lệ.") from exc


def credential_security_ready() -> bool:
    """Whether browser credential administration may be enabled safely."""
    if not os.environ.get("FLASK_SECRET_KEY", "").strip():
        return False
    try:
        _fernet()
    except AIConfigurationError:
        return False
    return True


def encrypt_credential(raw_key: str) -> str:
    raw_key = (raw_key or "").strip()
    if not raw_key:
        raise ValueError("Khóa Gemini không được để trống.")
    return _fernet().encrypt(raw_key.encode("utf-8")).decode("ascii")


def decrypt_credential(ciphertext: str) -> str:
    try:
        return _fernet().decrypt((ciphertext or "").encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise AIConfigurationError("Không thể mở khóa Gemini đã lưu. Hãy liên hệ quản trị máy chủ.") from exc


def credential_fingerprint(raw_key: str) -> str:
    return hashlib.sha256((raw_key or "").strip().encode("utf-8")).hexdigest()


def teacher_default_group(owner_id: int | None):
    """Return the owning teacher's deterministic default key group.

    Phase 3 deliberately has one effective class credential pool.  The
    legacy ``Course.ai_key_group_id`` column is retained for history, but it
    is not consulted here.  Reading the default is intentionally side-effect
    free: callers may use this helper for availability/cache identity checks
    without creating rows or touching configuration revisions.

    Older databases can contain more than one default row.  Selecting the
    oldest row matches the teacher settings surface and keeps resolution
    stable until a later migration phase decides how to reconcile history.
    """
    if not owner_id:
        return None
    return TeacherAIKeyGroup.query.filter_by(
        owner_id=owner_id, is_default=True,
    ).order_by(TeacherAIKeyGroup.id.asc()).first()


def _project_scope(owner_id: int, project_ref: str) -> str:
    # The project label itself is not needed for routing/cooldown lookups.
    raw = f"gemini:{int(owner_id)}:{(project_ref or 'default').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _retry_after_seconds(response, default: int) -> int:
    """Return a safe, non-negative Retry-After delay in seconds.

    RFC 9110 permits either delta-seconds or an HTTP-date.  A provider's
    value is never silently shortened: in particular, the old 3600-second
    cap could make a key eligible while Gemini was still asking us to wait.
    The request path never sleeps for this value; it is persisted as a
    project cooldown and another known-different project may be tried.
    Invalid headers fall back to the already bounded server setting.
    """
    headers = getattr(response, "headers", None) if response is not None else None
    value = None
    if headers:
        try:
            value = headers.get("Retry-After")
        except AttributeError:
            value = None
        # Test doubles and non-requests adapters may use a plain, case-
        # sensitive mapping.  HTTP field names are case-insensitive.
        if value is None:
            try:
                for name, candidate in headers.items():
                    if str(name).lower() == "retry-after":
                        value = candidate
                        break
            except AttributeError:
                pass

    fallback = max(0, int(default or 0))
    if value is None:
        return fallback

    try:
        # Delta-seconds is an integer by specification.  Preserve zero: a
        # provider explicitly allowing an immediate retry should not be
        # changed into the previous arbitrary 15-second minimum.
        parsed = int(str(value).strip())
        if parsed >= 0:
            return parsed
    except (TypeError, ValueError):
        pass

    try:
        retry_at = parsedate_to_datetime(str(value).strip())
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=dt.timezone.utc)
        now = dt.datetime.now(dt.timezone.utc)
        # Ceil avoids shortening the provider's date by sub-second rounding.
        return max(0, int(math.ceil((retry_at - now).total_seconds())))
    except (TypeError, ValueError, OverflowError, IndexError):
        return fallback


def _response_content(body):
    content = body.get("output_text") if isinstance(body, dict) else None
    if content is None and isinstance(body, dict) and body.get("choices"):
        content = body["choices"][0].get("message", {}).get("content")
    if content is None and isinstance(body, dict):
        content = body.get("result", body)
    return json.loads(content) if isinstance(content, str) else content


def _response_markers(response) -> str:
    """Return a bounded, lower-case provider marker string.

    Provider response bodies are never included in an exception or persisted
    audit row.  Classification needs only a small marker subset, so cap the
    in-memory serialization as well in case a proxy returns a very large
    document.
    """
    try:
        body = response.json()
        return json.dumps(body, ensure_ascii=False)[:12000].lower()
    except (ValueError, TypeError, AttributeError):
        return ""


@dataclass
class AIConfiguration:
    """Resolved source identity used in cache keys and audit rows."""

    source: str  # teacher_group or legacy_env
    provider: str
    endpoint: str
    model_name: str
    group_id: int | None
    config_revision: int | None
    owner_id: int | None
    course_id: int | None = None
    group: object | None = None

    @property
    def cache_identity(self) -> tuple[str, int | None, int | None, str]:
        return (self.source, self.group_id, self.config_revision, self.model_name)


class GeminiAIGateway:
    """Bounded OpenAI-compatible Gemini client with project quota awareness."""

    def __init__(self, http_session=None, sleep_fn=None):
        self.session = http_session or requests.Session()
        self.sleep = sleep_fn or time.sleep
        self.timeout = _env_int("AI_GEMINI_TIMEOUT_SECONDS", _env_int("AI_ANALYSIS_TIMEOUT_SECONDS", 20, 3, 60), 3, 60)
        # The old MAX_PROJECT name is retained as a compatibility fallback.
        # This is a global outbound HTTP-call budget, not a count of cooled
        # projects (which consume no budget).
        self.max_http_attempts = _env_int(
            "AI_GEMINI_MAX_HTTP_ATTEMPTS",
            _env_int("AI_GEMINI_MAX_PROJECT_ATTEMPTS", 2, 1, 4), 1, 4,
        )
        self.cooldown_seconds = _env_int("AI_GEMINI_PROJECT_COOLDOWN_SECONDS", 60, 15, 3600)
        self.transient_retries = _env_int("AI_GEMINI_TRANSIENT_RETRIES", _env_int("AI_ANALYSIS_RETRIES", 1, 0, 2), 0, 2)
        self.deadline_seconds = _env_int("AI_GEMINI_DEADLINE_SECONDS", 45, 5, 120)

    @staticmethod
    def legacy_configured() -> bool:
        # Preserve the original compatibility path, which allowed a local
        # OpenAI-compatible endpoint with no bearer token.  Teacher web calls
        # still require explicit server opt-in for this legacy path.
        return bool(os.environ.get("AI_ANALYSIS_API_URL", "").strip())

    @staticmethod
    def legacy_enabled_for_unassigned_course(course) -> bool:
        # Teacher-triggered web requests are never allowed to fall through to
        # a shared process credential.  Direct compatibility services may
        # still call ``legacy_configuration`` explicitly; this method is the
        # route-level policy gate.
        return False

    @staticmethod
    def legacy_fallback_opted_in() -> bool:
        """Expose policy state only; never expose the legacy credential."""
        return _env_bool("AI_LEGACY_ENV_FALLBACK_ENABLED")

    @staticmethod
    def _endpoint() -> str:
        return os.environ.get("GEMINI_OPENAI_API_URL", GEMINI_OPENAI_ENDPOINT).strip() or GEMINI_OPENAI_ENDPOINT

    def resolve_course(self, course, *, allow_legacy: bool = False) -> AIConfiguration:
        """Resolve the owning teacher's single effective default group.

        ``allow_legacy`` remains in the signature for compatibility with
        older callers, but a teacher-owned course never falls through to a
        process environment credential.  The retained course group column is
        historical metadata only; a forged/stale value cannot override the
        teacher's current default pool.
        """
        if not course or not course.teacher_id:
            raise AIConfigurationError("Khóa học chưa được phân công giáo viên nên không thể dùng AI của giáo viên.")
        # Find an inactive default too, so stopping the default group is a
        # deliberate no-AI state rather than permission to use another
        # teacher's or the server's shared credentials.  The helper uses the
        # same deterministic oldest-default rule as teacher settings.
        group = teacher_default_group(course.teacher_id)
        if group is not None:
            if not group.is_active:
                raise AIConfigurationError("Nhóm AI của giáo viên đang tạm dừng.")
            if not credential_security_ready():
                raise AIConfigurationError("Máy chủ chưa sẵn sàng bảo vệ khóa AI của giáo viên.")
            return AIConfiguration(
                source="teacher_group", provider="gemini-openai-compatible",
                endpoint=self._endpoint(), model_name=TEACHER_GEMINI_MODEL,
                group_id=group.id, config_revision=int(group.config_revision or 1),
                owner_id=group.owner_id, course_id=course.id, group=group,
            )
        # ``allow_legacy`` cannot broaden a teacher course's credential scope.
        # Direct integrations can still call ``legacy_configuration``
        # explicitly when they intentionally operate outside a course.
        raise AIConfigurationError("Giáo viên chưa có nhóm AI mặc định cho khóa học này.")

    def legacy_configuration(self, *, course_id=None) -> AIConfiguration:
        if not self.legacy_configured():
            raise AIConfigurationError("Chưa cấu hình AI_ANALYSIS_API_URL và AI_ANALYSIS_API_KEY cho tích hợp cũ.")
        return AIConfiguration(
            source="legacy_env", provider=(os.environ.get("AI_ANALYSIS_PROVIDER", "openai-compatible").strip() or "openai-compatible")[:80],
            endpoint=os.environ.get("AI_ANALYSIS_API_URL", "").strip(),
            model_name=(os.environ.get("AI_ANALYSIS_MODEL", "").strip() or "configured-model")[:120],
            group_id=None, config_revision=None, owner_id=None, course_id=course_id,
        )

    def _cooldown(self, owner_id: int, project_ref: str):
        scope = _project_scope(owner_id, project_ref)
        row = AIProjectCooldown.query.filter_by(scope_key=scope).first()
        if row and row.cooldown_until > dt.datetime.utcnow():
            return row
        return None

    def _mark_cooldown(self, owner_id: int, project_ref: str, response=None):
        seconds = _retry_after_seconds(response, self.cooldown_seconds)
        scope = _project_scope(owner_id, project_ref)
        row = AIProjectCooldown.query.filter_by(scope_key=scope).first()
        now = dt.datetime.utcnow()
        try:
            until = now + dt.timedelta(seconds=seconds)
        except (OverflowError, ValueError):
            # A maliciously huge delta must not crash the request.  ``max``
            # is still later than any practical provider wait and, crucially,
            # does not make the key eligible earlier than requested.
            until = dt.datetime.max
        if row is None:
            # A quota response can be received concurrently by two report
            # requests.  Use a savepoint around INSERT so a unique-scope race
            # does not roll back the report transaction.
            try:
                with db.session.begin_nested():
                    row = AIProjectCooldown(scope_key=scope, provider="gemini", cooldown_until=until, reason_code="quota")
                    db.session.add(row)
                    db.session.flush()
            except IntegrityError:
                row = AIProjectCooldown.query.filter_by(scope_key=scope).first()
                if row is None:
                    raise
                row.cooldown_until = max(row.cooldown_until, until)
                row.reason_code = "quota"
        else:
            row.cooldown_until = max(row.cooldown_until, until)
            row.reason_code = "quota"
        return row

    def _claim_next_key(self, group, excluded_projects: set[str]):
        """Claim the next verified, non-paused key and move it to the tail.

        ``sort_order`` is the only cursor available in the Phase 1–3 schema.
        Claiming before the outbound call means a temporarily unhealthy key
        does not become the head of every subsequent request.  The group
        lock plus ``FOR UPDATE`` provide safe sequential behavior within a
        worker/database transaction; deployment-wide fairness remains
        best-effort until an explicit cursor column is introduced.

        Returns ``(key, project_ref, saw_cooldown)``.  A key whose project is
        cooling down is skipped without consuming the HTTP attempt budget.
        """
        saw_cooldown = False
        with _rotation_lock(group.id):
            # Re-query instead of using ``group.keys``: another request may
            # have moved the queue head since the configuration was resolved.
            query = TeacherAIKey.query.filter_by(
                group_id=group.id, is_paused=False, last_test_status="ok",
            ).order_by(
                TeacherAIKey.sort_order.asc(), TeacherAIKey.id.asc(),
            )
            try:
                query = query.with_for_update()
            except AttributeError:
                # Keep compatibility with lightweight query doubles used by
                # isolated tests.  Real SQLAlchemy queries support the lock.
                pass
            candidates = query.all()
            for candidate in candidates:
                project_ref = (candidate.project_ref or "default").strip() or "default"
                if project_ref in excluded_projects:
                    continue
                if self._cooldown(group.owner_id, project_ref):
                    saw_cooldown = True
                    continue

                current_max = db.session.query(func.max(TeacherAIKey.sort_order)).filter_by(
                    group_id=group.id,
                ).scalar()
                candidate.sort_order = int(current_max if current_max is not None else -1) + 1
                # Commit the cursor mutation independently of the eventual
                # provider result.  No group.touch_configuration() occurs:
                # rotation is runtime scheduling, not a new configuration.
                db.session.commit()
                return db.session.get(TeacherAIKey, candidate.id), project_ref, saw_cooldown
        return None, None, saw_cooldown

    @staticmethod
    def _status(response) -> int:
        try:
            return int(getattr(response, "status_code", 200))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _is_auth_body(response) -> bool:
        """Classify only known API-key markers without surfacing the body."""
        marker = _response_markers(response)
        return any(token in marker for token in (
            "api_key_invalid", "api key invalid", "unauthenticated",
            "invalid api key", "api key not valid", "api_key not valid",
            "invalid_api_key", "invalid api_key",
            "revoked api key",
        ))

    @staticmethod
    def _is_permission_body(response) -> bool:
        marker = _response_markers(response)
        return any(token in marker for token in (
            "permission_denied", "permission denied", "access denied",
            "forbidden", "insufficient permission", "not authorized",
        ))

    @staticmethod
    def _is_quota_body(response) -> bool:
        marker = _response_markers(response)
        return any(token in marker for token in (
            "resource_exhausted", "quota exceeded", "quota_exceeded",
            "rate limit", "rate_limit", "too many requests",
        ))

    @staticmethod
    def _is_model_not_found_body(response) -> bool:
        marker = _response_markers(response)
        return any(token in marker for token in (
            "model_not_found", "model not found", "unknown model",
            "models/" + TEACHER_GEMINI_MODEL + " is not found",
        ))

    @staticmethod
    def public_error_code(error) -> str:
        """Map a provider/configuration error to a safe persisted code.

        These values are stable UI categories rather than HTTP bodies/status
        text.  Keeping them in the existing ``last_error_code`` column avoids
        a schema migration for the simplified settings flow.
        """
        kind = getattr(error, "kind", None)
        if kind == "auth":
            return "invalid_or_revoked"
        if kind == "permission":
            return "permission_denied"
        if kind == "quota":
            return "quota_rate_limited"
        if kind in {"network", "transient"}:
            return "network_unavailable"
        if kind == "model_not_found":
            return "model_not_found"
        if kind == "malformed":
            return "malformed_response"
        if isinstance(error, AICooldownError):
            return "quota_rate_limited"
        if isinstance(error, AIConfigurationError):
            return "configuration_unavailable"
        return "provider_request_failed"

    def _record_test_failure(self, key, error, *, group=None, project_ref=None):
        """Persist only a bounded verification result, never provider data."""
        if isinstance(error, AICooldownError) or getattr(error, "kind", None) == "quota":
            # A skipped probe is not a failed probe.  Preserve a prior
            # successful verification (and its timestamp) so a temporary
            # project wait cannot permanently make the key ineligible.  A
            # never-verified key gets a safe UI marker but remains ineligible
            # because ``last_test_status`` stays unset.
            if key.last_test_status is None:
                key.last_error_code = "verification_deferred"
            if group is not None and project_ref:
                # ``test_key`` normally reaches this branch only after the
                # provider returned a quota response.  The row is already
                # persisted by the caller in that case; this is idempotent
                # and keeps the helper safe for direct callers.
                self._mark_cooldown(group.owner_id, project_ref, getattr(error, "response", None))
            db.session.commit()
            return
        # A persisted project cooldown means no provider request was made for
        # this key, so do not present the attempt as a fresh last-checked time.
        key.last_tested_at = dt.datetime.utcnow()
        key.last_test_status = "failed"
        key.last_error_code = self.public_error_code(error)[:80]
        # A credential explicitly rejected by Gemini is not worth attempting
        # in normal report rotation until the teacher retries it.  Other
        # failures remain visible as failed/unready without being discarded.
        if getattr(error, "kind", None) == "auth":
            key.is_paused = True
            if group is not None:
                group.touch_configuration()
        if getattr(error, "kind", None) == "quota" and group is not None:
            self._mark_cooldown(group.owner_id, project_ref or "default", getattr(error, "response", None))
        db.session.commit()

    def _post_json(self, config: AIConfiguration, api_key: str, payload: dict, *, timeout_seconds=None):
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            response = self.session.post(config.endpoint, headers=headers, json=payload, timeout=timeout_seconds or self.timeout)
        except requests.RequestException as exc:
            error = AIGatewayError("Không thể kết nối nhà cung cấp AI.")
            # Network failures are distinct from a provider 5xx. Both remain
            # bounded/retryable at the gateway layer.
            error.kind = "network"
            raise error from exc
        status = self._status(response)
        if status >= 400:
            # Deliberately do not include response text: some proxies echo
            # authentication headers or request metadata in error bodies.
            error = AIGatewayError(f"Nhà cung cấp AI trả về lỗi {status}.")
            error.status_code = status
            error.response = response
            if status == 429 or self._is_quota_body(response):
                error.kind = "quota"
            elif status == 404 or self._is_model_not_found_body(response):
                error.kind = "model_not_found"
            elif status == 401 or (status == 400 and self._is_auth_body(response)):
                error.kind = "auth"
            elif status == 403 or self._is_permission_body(response):
                error.kind = "permission"
            elif status >= 500:
                error.kind = "transient"
            else:
                error.kind = "request"
            raise error
        try:
            body = response.json()
            return _response_content(body)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            error = AIGatewayError("Nhà cung cấp AI không trả về JSON hợp lệ.")
            error.kind = "malformed"
            raise error from exc

    @staticmethod
    def _payload(messages, *, model_name: str, temperature: float, response_format):
        payload = {"model": model_name, "messages": messages, "temperature": temperature}
        if response_format:
            payload["response_format"] = response_format
        return payload

    def _current_group_for_call(self, config: AIConfiguration) -> TeacherAIKeyGroup:
        """Re-check the current owner/default before every provider attempt.

        A resolved configuration is only a snapshot.  Between retries a
        course can be transferred, its teacher's default can be replaced, or
        the group can be paused/deleted.  Re-resolving the current default
        here makes those changes fail closed instead of sending a stale
        teacher credential.
        """
        if config.source != "teacher_group" or not config.group_id:
            raise AIConfigurationError("Cấu hình AI của giáo viên không hợp lệ.")
        # Expire long-lived SQLAlchemy instances so a concurrent admin/teacher
        # update cannot leave an in-memory group/key usable after revocation.
        db.session.expire_all()
        group = db.session.get(TeacherAIKeyGroup, config.group_id)
        course = db.session.get(Course, config.course_id) if config.course_id else None
        if config.course_id and course is None:
            raise AIConfigurationError("Khóa học không còn tồn tại; không thể dùng cấu hình AI cũ.")
        if not group or not group.is_active or group.owner_id != config.owner_id:
            raise AIConfigurationError("Nhóm AI không còn khả dụng.")
        if int(group.config_revision or 1) != int(config.config_revision or 1):
            raise AIConfigurationError("Cấu hình AI đã thay đổi; hãy gửi lại yêu cầu.")
        if course and course.teacher_id != group.owner_id:
            raise AIConfigurationError("Giáo viên của khóa học đã thay đổi; không thể dùng cấu hình AI cũ.")

        # The course's legacy assignment is intentionally ignored.  The
        # current oldest default is the only effective class pool, and must
        # still be the exact group/revision resolved at request start.
        current_default = teacher_default_group(
            course.teacher_id if course else config.owner_id
        )
        if current_default is None:
            raise AIConfigurationError("Giáo viên chưa có nhóm AI mặc định cho khóa học này.")
        if current_default.id != group.id:
            raise AIConfigurationError("Nhóm AI mặc định của giáo viên đã thay đổi; hãy gửi lại yêu cầu.")
        if not current_default.is_active:
            raise AIConfigurationError("Nhóm AI của giáo viên đang tạm dừng.")
        return group

    def _call_with_transient_retries(self, config, api_key, payload, *, deadline, call_counter,
                                     before_attempt=None):
        last_error = None
        for retry in range(self.transient_retries + 1):
            remaining = deadline - time.monotonic()
            if remaining < 1 or call_counter[0] >= self.max_http_attempts:
                break
            if before_attempt is not None:
                # Re-check at every outbound retry, including after backoff.
                # This closes the transfer/revocation window while no request
                # is in flight.
                before_attempt()
            call_counter[0] += 1
            try:
                return self._post_json(config, api_key, payload, timeout_seconds=min(self.timeout, max(1, int(remaining))))
            except AIGatewayError as exc:
                last_error = exc
                if getattr(exc, "kind", None) not in {"transient", "network"} or retry >= self.transient_retries:
                    raise
                # Bounded retry on the same key/project; no key rotation occurs
                # while the transient request still has retry budget.
                if deadline - time.monotonic() < 1:
                    break
                self.sleep(min(.25 * (2 ** retry), max(0, deadline - time.monotonic())))
        raise last_error or AIGatewayError("Yêu cầu AI đã hết thời gian chờ.")

    def complete(self, config: AIConfiguration, *, messages, temperature: float = 0.1, response_format=None):
        """Return one JSON result with a project-scoped quota guard.

        Normal requests claim one round-robin key per project.  A 429 sets a
        durable project cooldown, and only a different project may be
        attempted afterwards.  This prevents same-project key rotation from
        bypassing Gemini's project-level limits while still allowing the
        verified pool to distribute ordinary requests fairly.
        """
        # ``AIConfiguration`` can be constructed by compatibility callers, so
        # enforce the teacher model at the last boundary too; a forged/stale
        # config object cannot override the server-selected model.
        model_name = TEACHER_GEMINI_MODEL if config.source == "teacher_group" else config.model_name
        if config.source == "teacher_group":
            config.model_name = TEACHER_GEMINI_MODEL
        payload = self._payload(messages, model_name=model_name, temperature=temperature, response_format=response_format)
        if config.source == "legacy_env":
            return self._call_with_transient_retries(
                config, os.environ.get("AI_ANALYSIS_API_KEY", "").strip(), payload,
                deadline=time.monotonic() + self.deadline_seconds, call_counter=[0],
            )
        group = self._current_group_for_call(config)
        # Only an explicit successful probe is eligible for report traffic.
        # Newly stored, failed, revoked, or never-checked credentials must
        # never become an implicit rotation candidate.  Keep this early check
        # separate from the claim loop so an all-unverified group reports a
        # configuration problem rather than a provider outage.
        if not TeacherAIKey.query.filter_by(
            group_id=group.id, is_paused=False, last_test_status="ok",
        ).first():
            raise AIConfigurationError("Nhóm AI chưa có khóa đã kiểm tra thành công và sẵn sàng.")

        exhausted_projects: set[str] = set()
        saw_cooldown = False
        last_error = None
        deadline = time.monotonic() + self.deadline_seconds
        call_counter = [0]
        while call_counter[0] < self.max_http_attempts and deadline - time.monotonic() >= 1:
            # The claim re-queries the current queue and atomically advances
            # its head before the request.  It also skips cooled projects
            # without consuming an outbound-call budget.
            group = self._current_group_for_call(config)
            key, project_ref, skipped_cooldown = self._claim_next_key(group, exhausted_projects)
            saw_cooldown = saw_cooldown or skipped_cooldown
            if key is None:
                break
            try:
                # Re-check every real outbound attempt, not only once per
                # HTTP request, so a transfer/revocation wins over a stale
                # configuration while a retry is sleeping.
                group = self._current_group_for_call(config)
                key = db.session.get(TeacherAIKey, key.id)
                if (
                    not key
                    or key.group_id != group.id
                    or key.is_paused
                    or key.last_test_status != "ok"
                ):
                    continue

                def still_allowed():
                    current_group = self._current_group_for_call(config)
                    current_key = db.session.get(TeacherAIKey, key.id)
                    if self._cooldown(current_group.owner_id, project_ref):
                        # Another request may have observed a quota response
                        # after this key was claimed but before this attempt.
                        # Re-check the shared project wait at the last safe
                        # boundary and never send into a newly cooled scope.
                        error = AICooldownError(
                            "Dự án Gemini đang trong thời gian chờ hạn mức; không gửi thêm yêu cầu."
                        )
                        error.runtime_wait = True
                        raise error
                    # Verification is an independent gate from runtime
                    # scheduling.  A concurrent retry/revocation must not
                    # send a key whose successful probe has since been
                    # removed, even if it is not marked paused yet.
                    if (
                        not current_key
                        or current_key.group_id != current_group.id
                        or current_key.is_paused
                        or current_key.last_test_status != "ok"
                    ):
                        raise AIConfigurationError("Khóa AI không còn khả dụng.")

                result = self._call_with_transient_retries(
                    config, decrypt_credential(key.encrypted_key), payload,
                    deadline=deadline, call_counter=call_counter, before_attempt=still_allowed,
                )
                # Runtime success does not rewrite verification metadata.  A
                # successful probe remains the source of truth for eligibility
                # and ``last_tested_at`` continues to mean last verification.
                return result
            except AICooldownError:
                # A concurrent project cooldown can be discovered after the
                # queue claim.  It consumed no new HTTP attempt; exclude this
                # project for the remainder of the request and try only a
                # known-different project.
                saw_cooldown = True
                exhausted_projects.add(project_ref)
                db.session.rollback()
            except AIGatewayError as exc:
                last_error = exc
                kind = getattr(exc, "kind", "")
                if kind == "quota":
                    # Gemini quotas are project-scoped.  Persist the provider
                    # wait and do not blindly cycle through more keys carrying
                    # this same (possibly only label-based) project scope.
                    self._mark_cooldown(group.owner_id, project_ref, getattr(exc, "response", None))
                    saw_cooldown = True
                    exhausted_projects.add(project_ref)
                    db.session.commit()
                elif kind == "auth":
                    # A revoked/invalid key is no longer verified and is
                    # paused until an explicit successful probe.  A second
                    # key may still be tried; this is not quota bypassing.
                    key.last_tested_at = dt.datetime.utcnow()
                    key.last_test_status = "failed"
                    key.last_error_code = self.public_error_code(exc)[:80]
                    key.is_paused = True
                    group.touch_configuration()
                    # This request can safely continue to a second credential
                    # after pausing the first. Carry the new revision so the
                    # next per-attempt revocation check distinguishes our own
                    # change from an external configuration replacement.
                    config.config_revision = group.config_revision
                    db.session.commit()
                elif kind == "permission" and self._is_permission_body(getattr(exc, "response", None)):
                    # An explicit per-key permission denial is actionable for
                    # that credential.  Pause it until a successful manual
                    # verification; unlike a generic model/config 403 this
                    # may safely move to another verified key.
                    key.last_tested_at = dt.datetime.utcnow()
                    key.last_test_status = "failed"
                    key.last_error_code = self.public_error_code(exc)[:80]
                    key.is_paused = True
                    group.touch_configuration()
                    config.config_revision = group.config_revision
                    db.session.commit()
                elif kind in {"transient", "network"}:
                    # A runtime transport failure is not a failed probe.  A
                    # previously verified key remains eligible on a later
                    # request; bounded retries and project exclusion protect
                    # this request from a hot loop without erasing proof of
                    # verification.  Keys in different projects can still be
                    # attempted within the request.
                    exhausted_projects.add(project_ref)
                    db.session.commit()
                else:
                    # Model/configuration/malformed/bad-request errors are
                    # request-wide and must not burn the remaining pool.
                    db.session.commit()
                    raise
            except AIConfigurationError:
                # Ownership/revision/decryption failures are security events,
                # not a reason to try another credential behind the caller's
                # back. Propagate the sanitized configuration error.
                raise
        if saw_cooldown and last_error is None:
            raise AICooldownError("Dự án Gemini đang trong thời gian chờ hạn mức; hãy thử lại sau.")
        if saw_cooldown:
            raise AICooldownError("Dự án Gemini đã chạm hạn mức; không thử thêm khóa cùng dự án.")
        raise AIGatewayError("Nhà cung cấp AI hiện không khả dụng.") from last_error

    def test_key(self, key, *, group=None, timeout_seconds=None, bypass_cooldown: bool = False):
        """Test exactly ``key`` with synthetic content and no key rotation."""
        group = group or key.group
        if not group or not group.is_active:
            raise AIConfigurationError("Nhóm AI đang tạm dừng.")
        if key.group_id != group.id:
            raise AIConfigurationError("Khóa không thuộc nhóm AI này.")
        project_ref = (key.project_ref or "default").strip() or "default"
        cooldown = self._cooldown(group.owner_id, project_ref)
        if cooldown and not bypass_cooldown:
            error = AICooldownError("Dự án Gemini đang trong thời gian chờ hạn mức; không gửi kiểm tra mới.")
            error.verification_deferred = True
            error.cooldown_until = cooldown.cooldown_until
            # No provider request occurred; do not overwrite the independent
            # verification state or invent a new test timestamp.  The route
            # can display this wait from the persisted project cooldown.
            raise error
        config = AIConfiguration(
            source="teacher_group", provider="gemini-openai-compatible", endpoint=self._endpoint(),
            model_name=TEACHER_GEMINI_MODEL, group_id=group.id,
            config_revision=int(group.config_revision or 1), owner_id=group.owner_id, group=group,
        )
        try:
            probe = self._payload(
                [{"role": "user", "content": "Return exactly one JSON object: {\"ok\": true}. No student data is included."}],
                model_name=config.model_name, temperature=0, response_format={"type": "json_object"},
            )
            probe["max_tokens"] = 1024
            result = self._post_json(config, decrypt_credential(key.encrypted_key), probe,
                                     timeout_seconds=timeout_seconds or self.timeout)
            # A 2xx transport response alone does not prove that the key can
            # be used by report traffic.  Require the tiny probe contract so
            # malformed/empty provider responses remain unready.
            if not isinstance(result, dict) or result.get("ok") is not True:
                error = AIGatewayError("Nhà cung cấp AI không trả về phản hồi kiểm tra hợp lệ.")
                error.kind = "malformed"
                raise error
            was_paused = bool(key.is_paused)
            key.last_tested_at = dt.datetime.utcnow()
            key.last_test_status = "ok"
            key.last_error_code = None
            key.is_paused = False
            # Clear project cooldown on successful probe so verified key can be used immediately
            scope = _project_scope(group.owner_id, project_ref)
            AIProjectCooldown.query.filter_by(scope_key=scope).delete()
            if was_paused:
                # Resuming a revoked key changes availability and therefore
                # must invalidate cached reports just like the pause did.
                group.touch_configuration()
            db.session.commit()
            return result
        except AIGatewayError as exc:
            self._record_test_failure(key, exc, group=group, project_ref=project_ref)
            raise
