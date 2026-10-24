"""Fresh authorization checks for the stateful question-bank import flow.

Import previews can remain open for hours, while a user's role, a bank's
scope, or its ownership record may change.  Every state-changing step loads
those rows again before trusting the destination captured by the session.
"""

from __future__ import annotations

from database import db
from models import ImportSession, QuestionBank, User
from services.access_control import can_import_questions
from services.import_scope import editable_session


class ImportSessionNotFound(ValueError):
    """The session is absent or belongs to a different user."""


def fresh_import_actor(user_id):
    """Return the current persisted import actor, failing after role changes."""
    actor = db.session.get(User, user_id, populate_existing=True)
    if not actor or actor.role not in ("teacher", "admin"):
        raise ValueError("Không có quyền thực hiện phiên import.")
    return actor


def fresh_import_bank(bank_id, actor):
    """Reload a destination and its creator before applying the central policy."""
    bank = db.session.get(QuestionBank, bank_id, populate_existing=True)
    if not bank:
        raise ValueError("Ngân hàng đích không còn tồn tại.")

    # ``can_import_questions`` validates explicit/legacy scope using the
    # persisted creator.  Refresh that principal too so a creator role change
    # cannot be hidden by SQLAlchemy's identity map during a long-lived test,
    # CLI operation, or reused application context.  This permission is
    # intentionally distinct from ``can_edit_bank``: teachers may contribute
    # a private overlay to a shared bank while the bank remains read-only.
    if bank.created_by:
        db.session.get(User, bank.created_by, populate_existing=True)
        db.session.expire(bank, ["creator"])
    if not can_import_questions(actor, bank):
        raise ValueError("Không có quyền nhập vào ngân hàng đích.")
    return bank


def import_session_context(
    session_id,
    user_id,
    *,
    require_open=True,
    revalidate_target=True,
):
    """Reload and authorize the actor, session, and persisted destination."""
    actor = fresh_import_actor(user_id)
    session = db.session.get(ImportSession, session_id, populate_existing=True)
    if not session or session.user_id != user_id:
        raise ImportSessionNotFound("Không tìm thấy phiên import.")
    if require_open:
        editable_session(session_id, user_id)
    bank = None
    if revalidate_target and session.bank_id is not None:
        bank = fresh_import_bank(session.bank_id, actor)
    return actor, session, bank
