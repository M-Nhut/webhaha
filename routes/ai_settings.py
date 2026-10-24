"""Teacher-owned Gemini credential administration routes.

These handlers intentionally do not use ``role_required('teacher')`` because
that helper also permits administrators.  Administrators may invoke only the
separate disable switch and never receive a credential-listing response.
"""

from __future__ import annotations

import datetime as dt

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from database import db
from models import AIProjectCooldown, TeacherAIKey, TeacherAIKeyGroup
from services.ai_gateway import (
    AIConfigurationError,
    AICooldownError,
    AIGatewayError,
    GeminiAIGateway,
    TEACHER_GEMINI_MODEL,
    credential_fingerprint,
    credential_security_ready,
    encrypt_credential,
    _project_scope,
    teacher_default_group,
)


# Phase 5 exposes one teacher-owned credential workspace.  Group names,
# models, project labels, default selection, per-course mapping, reordering and
# pause controls are retired; the migration retains only the rows needed for
# ownership/history while this surface manages encrypted keys and verification.
TEACHER_KEY_BATCH_LIMIT = 20
_INTERNAL_GROUP_NAME = "__teacher_internal_default__"


def _teacher_owner_required():
    if current_user.role != "teacher":
        abort(403)


def _teacher_default_group(owner_id: int, *, create: bool = False):
    """Resolve the teacher's one effective default group.

    Older databases may still contain archived rows.  The oldest default is
    selected deterministically; the Phase 5 migration is responsible for
    consolidating existing rows.  A new internal group is created only when a
    first save needs one and no default exists.
    """
    group = teacher_default_group(owner_id)
    if group is not None:
        return group
    if not create:
        return None

    # Reuse a previously-created internal row if an interrupted/older
    # deployment left it non-default.  It has no user-facing name/control.
    group = TeacherAIKeyGroup.query.filter_by(
        owner_id=owner_id, name=_INTERNAL_GROUP_NAME
    ).order_by(TeacherAIKeyGroup.id.asc()).first()
    if group is not None:
        group.is_default = True
        group.touch_configuration()
        return group

    group = TeacherAIKeyGroup(
        owner_id=owner_id,
        name=_INTERNAL_GROUP_NAME,
        model_name=TEACHER_GEMINI_MODEL,
        is_active=True,
        is_default=True,
    )
    db.session.add(group)
    db.session.flush()
    return group


def _owned_default_key(key_id: int):
    """Resolve only a key in the current teacher's simplified workspace."""
    _teacher_owner_required()
    group = _teacher_default_group(current_user.id)
    if group is None:
        abort(404)
    key = TeacherAIKey.query.filter_by(id=key_id, group_id=group.id).first() or abort(404)
    return group, key


def _parse_key_batch(raw_value: str):
    """Parse a bounded line-oriented batch without returning credential text."""
    keys = [line.strip() for line in (raw_value or "").splitlines() if line.strip()]
    if not keys or len(keys) > TEACHER_KEY_BATCH_LIMIT:
        raise ValueError("batch_size")
    # Do not impose provider-specific prefixes, but reject whitespace and
    # implausibly large values before encryption/network work.
    if any(len(value) < 16 or len(value) > 4096 or any(char.isspace() for char in value) for value in keys):
        raise ValueError("format")
    return keys


def _record_unverified_failure(gateway, key, error):
    """Store a safe status when a probe could not reach normal gateway code."""
    gateway._record_test_failure(key, error)


def _verification_flash_code(error):
    """Return a public verification category; never interpolate exceptions."""
    if isinstance(error, AICooldownError) and getattr(error, "verification_deferred", False):
        return "verification_deferred"
    return GeminiAIGateway.public_error_code(error)


def _security_ready_or_redirect():
    if credential_security_ready():
        return None
    flash("Máy chủ cần FLASK_SECRET_KEY và AI_CREDENTIAL_ENCRYPTION_KEY trước khi quản lý hoặc dùng khóa AI.", "warning")
    return redirect(url_for("teacher_ai_settings"))


@login_required
def teacher_ai_settings():
    _teacher_owner_required()
    # Phase 5 leaves one effective group per teacher.  Historical group rows
    # may remain archived for report references, but they are never exposed as
    # selectable runtime configuration.
    default_group = _teacher_default_group(current_user.id)
    # Runtime quota waits are deliberately displayed separately from probe
    # verification.  A verified key must remain ``last_test_status == 'ok'``
    # while its project is cooling down; otherwise a temporary 429 would make
    # it permanently disappear from the rotation pool.
    runtime_cooldowns = {}
    if default_group is not None:
        for key in default_group.keys:
            scope = _project_scope(current_user.id, key.project_ref or "default")
            cooldown = AIProjectCooldown.query.filter_by(scope_key=scope).first()
            if cooldown and cooldown.cooldown_until > dt.datetime.utcnow():
                runtime_cooldowns[key.id] = cooldown.cooldown_until
    other_groups_count = TeacherAIKeyGroup.query.filter(
        TeacherAIKeyGroup.owner_id == current_user.id,
        TeacherAIKeyGroup.is_default.is_(False),
    ).count()
    return render_template(
        "teacher_ai_settings.html", group=default_group,
        credential_security_ready=credential_security_ready(),
        runtime_cooldowns=runtime_cooldowns,
        other_groups_count=other_groups_count,
    )


_VERIFICATION_LABELS = {
    "verification_deferred": "chưa gửi kiểm tra vì đang chờ hạn mức",
    "invalid_or_revoked": "khóa không hợp lệ hoặc đã bị thu hồi",
    "permission_denied": "khóa không có quyền dùng model",
    "quota_rate_limited": "đã chạm hạn mức hoặc bị giới hạn tốc độ",
    "network_unavailable": "không thể kết nối mạng tới nhà cung cấp",
    "server_overloaded": "máy chủ AI quá tải tạm thời (vui lòng thử lại sau ít phút)",
    "model_not_found": "model không tồn tại hoặc không được hỗ trợ",
    "malformed_response": "phản hồi nhà cung cấp không hợp lệ",
    "configuration_unavailable": "máy chủ chưa sẵn sàng bảo vệ khóa",
    "provider_request_failed": "nhà cung cấp từ chối yêu cầu",
}


def _verification_label(code):
    return _VERIFICATION_LABELS.get(code, _VERIFICATION_LABELS["provider_request_failed"])


def _verify_saved_keys(group, keys):
    """Verify each distinct saved key with one small synthetic request.

    The old gateway retry/rotation policy remains available to report calls;
    this administrative probe is intentionally one request per key and uses a
    short timeout so a 20-key form cannot hold a worker indefinitely.
    """
    gateway = GeminiAIGateway()
    gateway.timeout = min(gateway.timeout, 10)
    gateway.transient_retries = 0
    counts = {}
    for key in keys:
        try:
            gateway.test_key(key, group=group, timeout_seconds=gateway.timeout)
            code = "ok"
        except (AICooldownError, AIGatewayError, AIConfigurationError) as error:
            code = _verification_flash_code(error)
            # Decryption/configuration failures occur before ``test_key`` can
            # persist a status; persist only the safe category in that case.
            if isinstance(error, AICooldownError) and key.last_test_status == "deferred":
                code = "verification_deferred"
            elif key.last_test_status != "failed" or key.last_error_code != code:
                db.session.rollback()
                _record_unverified_failure(gateway, key, error)
        except Exception:
            # Adapters and test doubles can throw arbitrary exceptions.  Never
            # surface their text (it may contain an Authorization header).
            safe = AIGatewayError("Không thể kiểm tra khóa này.")
            safe.kind = "network"
            code = _verification_flash_code(safe)
            db.session.rollback()
            _record_unverified_failure(gateway, key, safe)
        counts[code] = counts.get(code, 0) + 1
    return counts


def _save_key_batch(raw_value: str):
    """Encrypt, persist, and probe a simple teacher key batch."""
    raw_keys = _parse_key_batch(raw_value)
    group = _teacher_default_group(current_user.id, create=True)
    if group is None or not group.is_active:
        db.session.rollback()
        raise AIConfigurationError("Nhóm AI của giáo viên đang tạm dừng.")

    existing = {
        key.key_fingerprint: key for key in group.keys
    }
    next_order = max((key.sort_order for key in group.keys), default=-1) + 1
    keys_to_check = []
    added = 0
    seen = set()
    for raw_key in raw_keys:
        fingerprint = credential_fingerprint(raw_key)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        key = existing.get(fingerprint)
        if key is None:
            key = TeacherAIKey(
                group_id=group.id,
                encrypted_key=encrypt_credential(raw_key),
                key_fingerprint=fingerprint,
                key_hint=raw_key[-4:],
                # Phase 1–2 intentionally has no project/name controls.  All
                # such keys share the existing safe default cooldown scope.
                project_ref="default",
                label=None,
                sort_order=next_order + added,
                last_test_status=None,
                last_error_code=None,
            )
            db.session.add(key)
            existing[fingerprint] = key
            added += 1
        keys_to_check.append(key)

    if added:
        group.touch_configuration()
    db.session.flush()
    db.session.commit()
    counts = _verify_saved_keys(group, keys_to_check)
    return group, added, len(keys_to_check), counts


@login_required
def teacher_ai_save_keys():
    """Save and verify up to 20 teacher-owned keys in one simple form."""
    _teacher_owner_required()
    blocked = _security_ready_or_redirect()
    if blocked:
        return blocked
    try:
        group, added, checked, counts = _save_key_batch(request.form.get("keys") or "")
    except ValueError as error:
        db.session.rollback()
        if str(error) == "batch_size":
            flash(f"Nhập từ 1 đến {TEACHER_KEY_BATCH_LIMIT} khóa, mỗi khóa một dòng.", "warning")
        else:
            flash("Một hoặc nhiều khóa không đúng định dạng độ dài/khoảng trắng.", "warning")
        return redirect(url_for("teacher_ai_settings"))
    except AIConfigurationError as error:
        db.session.rollback()
        if str(error) == "Nhóm AI của giáo viên đang tạm dừng.":
            flash(str(error), "warning")
        else:
            flash("Không thể lưu khóa vì máy chủ chưa sẵn sàng bảo vệ thông tin này.", "warning")
        return redirect(url_for("teacher_ai_settings"))
    except AIGatewayError:
        db.session.rollback()
        flash("Không thể lưu khóa vì máy chủ chưa sẵn sàng bảo vệ thông tin này.", "warning")
        return redirect(url_for("teacher_ai_settings"))

    ready = counts.get("ok", 0)
    failures = checked - ready
    if failures:
        details = ", ".join(
            f"{count} {_verification_label(code)}"
            for code, count in counts.items() if code != "ok"
        )
        flash(
            f"Đã mã hóa và lưu {added} khóa mới; kiểm tra {ready}/{checked} khóa sẵn sàng. {details.capitalize()}. "
            "Khóa lỗi/chưa xác minh không được dùng cho báo cáo.",
            "warning",
        )
    else:
        flash(f"Đã kiểm tra và lưu {checked} khóa; tất cả đã sẵn sàng dùng cho báo cáo.", "success")
    return redirect(url_for("teacher_ai_settings"))


@login_required
def teacher_ai_retry_key(key_id: int):
    """Retry one key in the current teacher's internal default group."""
    group, key = _owned_default_key(key_id)
    blocked = _security_ready_or_redirect()
    if blocked:
        return blocked
    gateway = GeminiAIGateway()
    gateway.timeout = max(gateway.timeout, 25)
    gateway.transient_retries = 0
    try:
        gateway.test_key(key, group=group, timeout_seconds=gateway.timeout, bypass_cooldown=True)
    except (AICooldownError, AIGatewayError, AIConfigurationError) as error:
        code = _verification_flash_code(error)
        if key.last_test_status != "failed" or key.last_error_code != code:
            db.session.rollback()
            _record_unverified_failure(gateway, key, error)
        flash(f"Kiểm tra lại thất bại: {_verification_label(code)}.", "warning")
    except Exception:
        safe = AIGatewayError("Không thể kiểm tra khóa này.")
        safe.kind = "network"
        db.session.rollback()
        _record_unverified_failure(gateway, key, safe)
        flash(f"Kiểm tra lại thất bại: {_verification_label('network_unavailable')}.", "warning")
    else:
        flash("Khóa đã được kiểm tra lại và sẵn sàng.", "success")
    return redirect(url_for("teacher_ai_settings"))


@login_required
def teacher_ai_delete_default_key(key_id: int):
    """Delete one key from the current teacher's internal group only."""
    group, key = _owned_default_key(key_id)
    blocked = _security_ready_or_redirect()
    if blocked:
        return blocked
    db.session.delete(key)
    group.touch_configuration()
    db.session.commit()
    flash("Đã xóa khóa mã hóa. Báo cáo và lịch sử cũ vẫn được giữ nguyên.", "success")
    return redirect(url_for("teacher_ai_settings"))


@login_required
def teacher_ai_test_key(key_id: int):
    """Run the preserved synthetic verification for one owned key."""
    group, key = _owned_default_key(key_id)
    blocked = _security_ready_or_redirect()
    if blocked:
        return blocked
    try:
        GeminiAIGateway().test_key(key, group=group, bypass_cooldown=True)
    except AICooldownError as exc:
        flash(f"Không thể kiểm tra khóa này: {_verification_label(_verification_flash_code(exc))}.", "warning")
    except (AIConfigurationError, AIGatewayError) as exc:
        flash(f"Không thể kiểm tra khóa này: {_verification_label(_verification_flash_code(exc))}.", "warning")
    else:
        flash("Khóa đã phản hồi với lệnh kiểm tra không chứa dữ liệu học sinh.", "success")
    return redirect(url_for("teacher_ai_settings"))


@login_required
def admin_disable_teacher_ai_group(group_id: int):
    if current_user.role != "admin":
        abort(403)
    # This narrow endpoint is deliberately non-enumerating and does not
    # render/serialize the group or keys for administrators.
    group = db.session.get(TeacherAIKeyGroup, group_id) or abort(404)
    if group.is_active:
        group.is_active = False
        group.touch_configuration()
        db.session.commit()
        flash("Đã tạm dừng nhóm AI của giáo viên.", "success")
    return redirect(url_for("courses"))


def register_ai_settings_routes(app) -> None:
    app.add_url_rule("/teacher/ai-settings", endpoint="teacher_ai_settings", view_func=teacher_ai_settings)
    app.add_url_rule("/teacher/ai-settings/keys", endpoint="teacher_ai_save_keys", view_func=teacher_ai_save_keys, methods=["POST"])
    app.add_url_rule("/teacher/ai-settings/keys/<int:key_id>/test", endpoint="teacher_ai_test_key", view_func=teacher_ai_test_key, methods=["GET", "POST"])
    app.add_url_rule("/teacher/ai-settings/keys/<int:key_id>/retry", endpoint="teacher_ai_retry_key", view_func=teacher_ai_retry_key, methods=["GET", "POST"])
    app.add_url_rule("/teacher/ai-settings/keys/<int:key_id>/delete", endpoint="teacher_ai_delete_default_key", view_func=teacher_ai_delete_default_key, methods=["POST"])
    app.add_url_rule("/admin/ai-groups/<int:group_id>/disable", endpoint="admin_disable_teacher_ai_group", view_func=admin_disable_teacher_ai_group, methods=["POST"])
