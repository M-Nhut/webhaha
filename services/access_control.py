"""HTTP authorization decorators and question-bank authorization policy.

Authorization stays at the route boundary; query/business services should not
depend on Flask request globals.  The question-bank helpers below keep the
scope decision in one place, so a client cannot turn a read/use permission
into an edit or import permission by posting a different bank id.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from flask import abort, flash, redirect, url_for
from flask_login import current_user


ViewParameters = ParamSpec("ViewParameters")
ViewResult = TypeVar("ViewResult")


# ``QuestionBank.visibility`` is intentionally nullable while existing rows
# are waiting for the reviewed data backfill.  Do not infer a shared scope for
# a legacy row merely because its creator is currently an admin: the creator's
# role may have changed since the row was written.
BANK_VISIBILITY_PRIVATE = "private"
BANK_VISIBILITY_SHARED = "shared"
BANK_VISIBILITIES = frozenset({BANK_VISIBILITY_PRIVATE, BANK_VISIBILITY_SHARED})

# Question scope is deliberately a separate contract from bank visibility.
# A shared bank can contain private teacher supplements, so ``created_by`` is
# provenance only and must never be used as the private owner for new policy
# decisions.
QUESTION_SCOPE_PRIVATE = "private"
QUESTION_SCOPE_SHARED = "shared"
QUESTION_SCOPES = frozenset({QUESTION_SCOPE_PRIVATE, QUESTION_SCOPE_SHARED})
QUESTION_SCOPE_LEGACY_PRIVATE = "legacy_private"
QUESTION_SCOPE_LEGACY_SHARED = "legacy_shared"
QUESTION_SCOPE_UNKNOWN = "legacy_unknown"


def _bank_creator(bank):
    """Return the persisted creator, or ``None`` when ownership is unknown.

    Relationships are normally loaded through ``bank.creator``.  The small
    fallback query keeps the policy safe for lightweight test doubles and for
    callers that constructed an object without loading its relationship.  A
    missing user is deliberately not treated as an administrator.
    """
    creator = getattr(bank, "creator", None)
    if creator is not None:
        return creator
    creator_id = getattr(bank, "created_by", None)
    if not creator_id:
        return None
    try:
        # Import lazily to avoid the models -> access_control import cycle.
        from models import User
        from database import db
        return db.session.get(User, creator_id)
    except Exception:
        # Authorization must fail closed if the lookup cannot be completed.
        return None


def bank_visibility(bank):
    """Return the validated persisted visibility, or ``None`` for legacy.

    Only the two server-owned values are meaningful.  An arbitrary value is
    represented as ``"__invalid__"`` so it cannot accidentally enter the
    legacy compatibility path.
    """
    value = getattr(bank, "visibility", None)
    if value is None:
        return None
    # Stored scope is an enum contract.  Do not normalize arbitrary input
    # here: a malformed value must remain unavailable until an administrator
    # repairs it.
    return value if value in BANK_VISIBILITIES else "__invalid__"


def _bank_scope_state(bank):
    """Resolve a bank's scope without granting legacy admin rows shared use.

    ``legacy_private`` is the only compatibility state.  It applies to an
    existing NULL-scope row whose creator is a teacher, and only that teacher
    may use/edit it.  NULL rows created by an admin stay unavailable to
    teachers until the explicit migration/backfill establishes ``shared``.
    """
    creator = _bank_creator(bank)
    creator_role = getattr(creator, "role", None)
    visibility = bank_visibility(bank)
    if visibility == "__invalid__" or creator is None:
        return visibility, creator
    if visibility is None:
        if creator_role == "teacher":
            return "legacy_private", creator
        # A NULL admin-created row is intentionally not promoted to shared.
        return "legacy_unavailable", creator
    # Once persisted, the explicit scope is authoritative.  This keeps a
    # teacher-owned private bank private even if that account is later
    # promoted, and keeps an admin-created shared bank shared after an admin
    # account changes role.  New rows are still stamped with the creator's
    # allowed scope by ``set_new_bank_visibility``; only an absent creator is
    # considered unsafe here.
    if creator_role not in ("admin", "teacher"):
        # A row owned by a removed/unsupported role is not a valid teacher
        # bank, even if somebody manually populated its visibility column.
        return "__invalid__", creator
    return visibility, creator


def _is_admin(user):
    # Authentication is enforced by the route decorator.  Keeping this pure
    # role check also lets service-layer callers pass a persisted User without
    # depending on Flask-Login's LocalProxy properties.
    return bool(user and getattr(user, "role", None) == "admin")


def _is_teacher(user):
    return bool(user and getattr(user, "role", None) == "teacher")


def _is_owner(user, bank):
    return bool(user and getattr(user, "id", None) is not None and getattr(bank, "created_by", None) == user.id)


def class_teacher_actor(course):
    """Return the current teacher actor for a class-scoped bank decision.

    Class-bound consumers must authorize a bank against the teacher currently
    assigned to the class.  They must not pass the requesting student (which
    would always fail) or an administrator (which would broaden a private
    bank into a usable source).  A missing or role-changed teacher fails
    closed by returning ``None``.
    """
    teacher_id = getattr(course, "teacher_id", None)
    if not teacher_id:
        return None
    try:
        # Use a fresh identity from the current session rather than trusting a
        # stale relationship or a caller-supplied actor.
        from models import User
        from database import db
        teacher = db.session.get(User, teacher_id)
    except Exception:
        return None
    return teacher if (
        getattr(teacher, "role", None) == "teacher"
        and getattr(teacher, "is_active", True) is not False
    ) else None


def can_view_bank(user, bank):
    """Return whether ``user`` may read bank metadata/questions.

    Students never receive direct bank access.  Admins may inspect any bank
    row so an orphaned/invalid row can be repaired; non-admins require a
    known creator and a valid explicit/legacy scope.
    """
    if not bank or getattr(user, "role", None) == "student":
        return False
    if _is_admin(user):
        return True
    if not _is_teacher(user):
        return False
    scope, creator = _bank_scope_state(bank)
    if scope == BANK_VISIBILITY_SHARED and creator is not None:
        return True
    return (
        creator is not None
        and scope in (BANK_VISIBILITY_PRIVATE, "legacy_private")
        and _is_owner(user, bank)
    )


def can_use_bank(user, bank):
    """Return whether ``user`` may select bank content for a new activity.

    Use is distinct from editing/importing: teachers may use a valid shared
    admin bank, but cannot mutate it.  Inactive banks remain inspectable by
    admins/owners but are not selectable for new work.
    """
    if not getattr(bank, "is_active", True):
        return False
    return can_view_bank(user, bank)


def can_edit_bank(user, bank):
    """Return whether ``user`` may change bank metadata or questions."""
    if not bank or getattr(user, "role", None) == "student":
        return False
    if _is_admin(user):
        return True
    if not _is_teacher(user) or not _is_owner(user, bank):
        return False
    scope, creator = _bank_scope_state(bank)
    return creator is not None and scope in (BANK_VISIBILITY_PRIVATE, "legacy_private")


def can_add_question(user, bank):
    """Return whether ``user`` may add a *new* question to ``bank``.

    Adding content is deliberately narrower than viewing/using a bank, but
    it is not the same operation as editing the bank or editing an existing
    shared question.  A teacher may contribute a private supplement to an
    explicitly shared bank; the bank metadata and its shared rows remain
    read-only.  A teacher may also add to their own private (including
    compatible legacy) bank.  Administrators retain the existing audit/admin
    path for every bank.
    """
    if not bank or getattr(user, "role", None) == "student":
        return False
    if _is_admin(user):
        return True
    if not _is_teacher(user):
        return False

    scope, creator = _bank_scope_state(bank)
    if creator is None or scope in ("__invalid__", "legacy_unavailable"):
        return False
    if scope == BANK_VISIBILITY_SHARED:
        # Explicit shared scope is the only bank state that permits teacher
        # overlays.  Legacy NULL admin banks remain unavailable until reviewed
        # and classified by the administrator.
        return True
    return (
        scope in (BANK_VISIBILITY_PRIVATE, "legacy_private")
        and _is_owner(user, bank)
    )


def can_import_questions(user, bank):
    """Return whether ``user`` may import new questions into ``bank``.

    Import and manual authoring intentionally share the destination policy,
    while both remain separate from :func:`can_edit_bank`.  Keeping this
    named permission explicit prevents a UI ``can_edit`` flag from granting
    mutation of existing shared content.
    """
    return can_add_question(user, bank)


def can_import_into_bank(user, bank):
    """Backward-compatible alias for the Phase-2 import permission."""
    return can_import_questions(user, bank)


def can_delete_bank(user, bank):
    """Return whether ``user`` may delete ``bank``."""
    return can_edit_bank(user, bank)


def require_bank_add(bank, *, user=None):
    """Abort unless the actor may append a new question to ``bank``."""
    actor = current_user if user is None else user
    if not bank:
        abort(404)
    if not can_add_question(actor, bank):
        abort(403)
    return bank


def require_bank_view(bank, *, user=None):
    """Abort with 404/403 unless the actor may read this bank."""
    actor = current_user if user is None else user
    if not bank:
        abort(404)
    if not can_view_bank(actor, bank):
        abort(403)
    return bank


def require_bank_edit(bank, *, user=None):
    """Abort with 404/403 unless the actor may mutate this bank."""
    actor = current_user if user is None else user
    if not bank:
        abort(404)
    if not can_edit_bank(actor, bank):
        abort(403)
    return bank


def new_bank_visibility(user):
    """Return the only scope permitted for a newly created bank.

    The value is derived from the authenticated server actor; request fields
    are intentionally not accepted.  ``None`` means the caller cannot create
    a bank and is useful to service-layer callers that do not use Flask.
    """
    role = getattr(user, "role", None)
    if role == "admin":
        return BANK_VISIBILITY_SHARED
    if role == "teacher":
        return BANK_VISIBILITY_PRIVATE
    return None


def set_new_bank_visibility(bank, user):
    """Stamp server-owned scope on a newly constructed bank object."""
    visibility = new_bank_visibility(user)
    if visibility is None:
        raise ValueError("Chỉ quản trị viên hoặc giáo viên mới được tạo ngân hàng.")
    # Keep this setter tolerant while an older database is being upgraded: the
    # model field is present in the application code, while a separate
    # additive schema step handles existing installations.
    setattr(bank, "visibility", visibility)
    return bank


def _question_bank(question, bank=None):
    """Return a question's bank without treating a missing bank as public."""
    if bank is not None:
        # A caller-supplied bank is a route-boundary assertion, not an
        # override for the question's persisted foreign key.  Reject a
        # mismatched pair so a policy check cannot authorize a question from
        # another bank.
        question_bank_id = getattr(question, "bank_id", None)
        supplied_bank_id = getattr(bank, "id", None)
        if question_bank_id is not None and supplied_bank_id is not None and question_bank_id != supplied_bank_id:
            return None
        try:
            related_bank = getattr(question, "bank", None)
        except Exception:
            related_bank = None
        if (
            related_bank is not None
            and supplied_bank_id is not None
            and getattr(related_bank, "id", None) is not None
            and getattr(related_bank, "id", None) != supplied_bank_id
        ):
            return None
        return bank
    try:
        related = getattr(question, "bank", None)
    except Exception:
        related = None
    if related is not None:
        return related
    bank_id = getattr(question, "bank_id", None)
    if not bank_id:
        return None
    try:
        from models import QuestionBank
        from database import db
        return db.session.get(QuestionBank, bank_id)
    except Exception:
        return None


def _question_creator(question):
    """Return the persisted question creator, or ``None`` on lookup failure."""
    try:
        creator = getattr(question, "creator", None)
    except Exception:
        creator = None
    if creator is not None:
        return creator
    creator_id = getattr(question, "created_by", None)
    if not creator_id:
        return None
    try:
        from models import User
        from database import db
        return db.session.get(User, creator_id)
    except Exception:
        return None


def _question_private_owner(question):
    """Resolve the separate private owner principal, failing closed."""
    try:
        owner = getattr(question, "private_owner", None)
    except Exception:
        owner = None
    if owner is not None:
        return owner
    owner_id = getattr(question, "private_owner_id", None)
    if not owner_id:
        return None
    try:
        from models import User
        from database import db
        return db.session.get(User, owner_id)
    except Exception:
        return None


def question_scope(question):
    """Return a validated persisted question scope, or ``None`` for legacy.

    Arbitrary non-NULL values are represented as ``"__invalid__"`` so they
    cannot accidentally enter the conservative legacy compatibility path.
    """
    value = getattr(question, "scope", None)
    if value is None:
        return None
    return value if isinstance(value, str) and value in QUESTION_SCOPES else "__invalid__"


def _question_scope_state(question, bank=None):
    """Resolve explicit/legacy question scope and its private principal.

    No historical rows are updated here.  A NULL question is promoted only
    when the existing bank ownership makes the result unambiguous:

    * private (including compatible legacy teacher-owned) banks stay private
      to the bank owner;
    * in an explicit shared bank, an old question created by that bank's
      administrator is safely shared, while a known teacher creator remains
      private to that teacher;
    * all other legacy combinations remain admin-only.
    """
    bank = _question_bank(question, bank)
    persisted_scope = question_scope(question)
    if persisted_scope == "__invalid__":
        return "__invalid__", None, bank

    if persisted_scope == QUESTION_SCOPE_SHARED:
        if getattr(question, "private_owner_id", None) is not None:
            # Shared rows must not carry a private principal.  Keep the
            # inconsistent row auditable by admins but unavailable to
            # teachers until it is repaired.
            return "__invalid__", _question_private_owner(question), bank
        # An explicit shared row has no private principal.  Bank compatibility
        # is checked separately so this cannot widen a private bank.
        return QUESTION_SCOPE_SHARED, None, bank

    if persisted_scope == QUESTION_SCOPE_PRIVATE:
        owner = _question_private_owner(question)
        if not owner or not _is_teacher(owner):
            # A private row with no valid teacher owner is not usable by a
            # teacher.  Administrators may still audit it through the caller.
            return "__invalid__", owner, bank
        return QUESTION_SCOPE_PRIVATE, owner, bank

    if bank is None:
        return QUESTION_SCOPE_UNKNOWN, None, None

    bank_state, bank_creator = _bank_scope_state(bank)
    if bank_state in ("__invalid__", "legacy_unavailable") or bank_creator is None:
        return QUESTION_SCOPE_UNKNOWN, None, bank

    bank_scope = bank_visibility(bank)
    # A non-NULL owner reference that cannot be resolved is not equivalent to
    # an absent legacy owner.  Falling back to created_by here could widen a
    # row after its private teacher account was removed.
    private_owner_id = getattr(question, "private_owner_id", None)
    q_owner = _question_private_owner(question)
    if private_owner_id is not None and q_owner is None:
        return QUESTION_SCOPE_UNKNOWN, None, bank
    if (
        private_owner_id is not None
        and q_owner is not None
        and getattr(q_owner, "id", None) != private_owner_id
    ):
        return QUESTION_SCOPE_UNKNOWN, None, bank
    q_creator = _question_creator(question)

    if bank_scope == BANK_VISIBILITY_PRIVATE or bank_state == "legacy_private":
        # A legacy private-bank question inherits the existing bank owner.
        # An already-populated, conflicting owner is evidence of corruption;
        # do not silently choose either principal.
        if q_owner is not None and getattr(q_owner, "id", None) != getattr(bank_creator, "id", None):
            return QUESTION_SCOPE_UNKNOWN, None, bank
        if _is_teacher(bank_creator):
            return QUESTION_SCOPE_LEGACY_PRIVATE, bank_creator, bank
        return QUESTION_SCOPE_UNKNOWN, None, bank

    if bank_scope == BANK_VISIBILITY_SHARED:
        # A teacher-created row in a shared bank is not made public by the
        # legacy fallback.  Keeping it private is the only safe interpretation
        # compatible with the future supplemental-question model.
        if q_owner is not None:
            if _is_teacher(q_owner):
                return QUESTION_SCOPE_LEGACY_PRIVATE, q_owner, bank
            return QUESTION_SCOPE_UNKNOWN, None, bank
        if _is_teacher(q_creator):
            return QUESTION_SCOPE_LEGACY_PRIVATE, q_creator, bank
        # Only the original administrator who owns the explicit shared bank
        # gives enough evidence that the old row was intended for the shared
        # catalog.  A different administrator is not promoted.
        if (
            _is_admin(bank_creator)
            and _is_admin(q_creator)
            and getattr(q_creator, "id", None) == getattr(bank_creator, "id", None)
        ):
            return QUESTION_SCOPE_LEGACY_SHARED, None, bank

    return QUESTION_SCOPE_UNKNOWN, None, bank


def resolve_question_source(question, *, bank=None):
    """Return the conservative, display-safe source for a bank question.

    The persisted ``scope`` is not sufficient for legacy rows: a NULL row can
    safely resolve to a teacher-private contribution, a shared contribution,
    or remain unresolved.  Callers that build tabs/facets should use this
    resolver instead of looking at ``created_by`` or ``scope`` directly.  The
    owner id is returned only as an internal policy decision; serializers must
    not expose it to ordinary teachers.

    ``key`` is one of ``common``, ``private`` or ``unknown``.  Unknown rows
    stay in the administrator's all/audit view and are excluded from teacher
    common/private buckets, so a legacy ambiguity can never widen visibility.
    """
    resolved_scope, private_owner, resolved_bank = _question_scope_state(question, bank)
    # ``can_view_question(admin, ...)`` deliberately permits an audit read of
    # malformed or mismatched rows.  That audit exception must not make such
    # a row look like a legitimate common/private tab contribution.  Recheck
    # the resolved scope against the containing bank for display bucketing;
    # incompatible rows remain visible only in the administrator's all view.
    bank_state = None
    bank_creator = None
    persisted_bank_scope = None
    if resolved_bank is not None:
        bank_state, bank_creator = _bank_scope_state(resolved_bank)
        persisted_bank_scope = bank_visibility(resolved_bank)
    if resolved_scope in (QUESTION_SCOPE_SHARED, QUESTION_SCOPE_LEGACY_SHARED):
        if (
            bank_state != BANK_VISIBILITY_SHARED
            or bank_creator is None
            or persisted_bank_scope != BANK_VISIBILITY_SHARED
        ):
            resolved_scope = QUESTION_SCOPE_UNKNOWN
        else:
            return {
                "key": "common",
                "resolved_scope": resolved_scope,
                "owner_id": None,
                "bank": resolved_bank,
            }
    if resolved_scope in (QUESTION_SCOPE_PRIVATE, QUESTION_SCOPE_LEGACY_PRIVATE):
        owner_id = getattr(private_owner, "id", None)
        private_bank_owner_id = getattr(bank_creator, "id", None)
        private_bank = bank_state in (BANK_VISIBILITY_PRIVATE, "legacy_private")
        shared_bank = bank_state == BANK_VISIBILITY_SHARED
        if shared_bank or (private_bank and owner_id == private_bank_owner_id):
            return {
                "key": "private",
                "resolved_scope": resolved_scope,
                "owner_id": owner_id,
                "bank": resolved_bank,
            }
        resolved_scope = QUESTION_SCOPE_UNKNOWN
    return {
        "key": "unknown",
        "resolved_scope": resolved_scope,
        "owner_id": None,
        "bank": resolved_bank,
    }


def question_source_label(user, question, *, bank=None):
    """Return an actor-safe source label for a question detail payload.

    Administrators have an audit read path, so their label must describe the
    owning teacher rather than saying ``only you``.  A teacher sees that label
    only for an already-authorized private row owned by that teacher.
    """
    source = resolve_question_source(question, bank=bank)
    if source["key"] == "common":
        return "Dùng chung"
    if source["key"] == "private":
        if _is_teacher(user) and source["owner_id"] == getattr(user, "id", None):
            return "Riêng tư — chỉ bạn"
        return "Riêng tư — giáo viên sở hữu"
    return "Dữ liệu cũ — phạm vi chưa xác định"


def _question_bank_allows(user, resolved_scope, private_owner, bank):
    """Check that a resolved question scope fits the containing bank."""
    if bank is None or not _is_teacher(user):
        return False
    if not can_view_bank(user, bank):
        return False

    bank_scope, bank_creator = _bank_scope_state(bank)
    persisted_bank_scope = bank_visibility(bank)
    if bank_scope in ("__invalid__", "legacy_unavailable") or bank_creator is None:
        return False

    if resolved_scope in (QUESTION_SCOPE_SHARED, QUESTION_SCOPE_LEGACY_SHARED):
        # Shared question content is visible only through an explicit shared
        # bank; a private/legacy bank must never be widened by a row value.
        return persisted_bank_scope == BANK_VISIBILITY_SHARED

    if resolved_scope in (QUESTION_SCOPE_PRIVATE, QUESTION_SCOPE_LEGACY_PRIVATE):
        if not private_owner or not _is_teacher(private_owner):
            return False
        if persisted_bank_scope == BANK_VISIBILITY_SHARED:
            # This is the future overlay shape: only its teacher owner sees it.
            return getattr(private_owner, "id", None) == getattr(user, "id", None)
        if bank_scope in (BANK_VISIBILITY_PRIVATE, "legacy_private"):
            # Existing private banks remain private to their bank owner even
            # when a question's provenance creator differs.
            return (
                getattr(private_owner, "id", None) == getattr(user, "id", None)
                and getattr(private_owner, "id", None) == getattr(bank_creator, "id", None)
            )
    return False


def can_view_question(user, question, *, bank=None):
    """Return whether an actor may read one bank question.

    Administrators can inspect malformed/orphaned rows for repair.  Teachers
    and students cannot use that audit exception; malformed scopes, unknown
    owners, mismatched bank scopes, and unresolved legacy rows fail closed.
    """
    if question is None:
        return False
    resolved_bank = _question_bank(question, bank)
    if bank is not None and resolved_bank is None:
        return False
    if _is_admin(user):
        return True
    if not _is_teacher(user):
        return False
    resolved_scope, private_owner, resolved_bank = _question_scope_state(question, resolved_bank)
    return _question_bank_allows(user, resolved_scope, private_owner, resolved_bank)


def can_use_question(user, question, *, bank=None):
    """Return whether an actor may select one question for a new activity."""
    if question is None:
        return False
    resolved_bank = _question_bank(question, bank)
    if resolved_bank is None or not getattr(resolved_bank, "is_active", True):
        return False
    if _is_admin(user):
        return True
    return can_view_question(user, question, bank=resolved_bank)


def can_include_question_in_duplicate_scan(user, question, *, bank=None):
    """Return whether a bank row may participate in import duplicate review.

    Duplicate review is not an audit read.  In particular, an administrator
    may inspect private rows through the audit path, but importing common
    content must never compare against (or disclose) a private supplement.
    Teachers compare against shared rows and their own private rows only.
    The helper deliberately resolves the persisted question scope before
    applying the actor rule, including conservative legacy resolution.
    """
    if question is None:
        return False
    resolved_bank = _question_bank(question, bank)
    if resolved_bank is None:
        return False
    persisted_bank_scope = bank_visibility(resolved_bank)

    # A NULL-scope administrator bank is intentionally not teacher-readable,
    # but administrators still need duplicate protection for its compatible
    # historical rows.  Only the bank administrator's own rows without a
    # private principal qualify; ambiguous rows stay out of the report.
    if _is_admin(user) and persisted_bank_scope is None:
        bank_creator = _bank_creator(resolved_bank)
        if (
            bank_creator is not None
            and _is_admin(bank_creator)
            and getattr(question, "private_owner_id", None) is None
            and getattr(question, "created_by", None) == getattr(bank_creator, "id", None)
            and question_scope(question) in (None, QUESTION_SCOPE_SHARED)
        ):
            return True
        # A NULL bank owned by a teacher is the conservative legacy-private
        # shape.  Let it fall through so an administrator importing into that
        # existing private destination can still detect duplicates against
        # the bank owner's rows.  Other NULL banks remain ambiguous and do
        # not enter a duplicate report.
        if bank_creator is None or not _is_teacher(bank_creator):
            return False
    resolved_scope, private_owner, resolved_bank = _question_scope_state(question, resolved_bank)
    if resolved_scope in (QUESTION_SCOPE_SHARED, QUESTION_SCOPE_LEGACY_SHARED):
        # Shared candidates are valid only in an explicit shared destination.
        return (
            persisted_bank_scope == BANK_VISIBILITY_SHARED
            and (_is_admin(user) or can_view_question(user, question, bank=resolved_bank))
        )
    if resolved_scope in (QUESTION_SCOPE_PRIVATE, QUESTION_SCOPE_LEGACY_PRIVATE):
        if _is_admin(user) and (
            persisted_bank_scope == BANK_VISIBILITY_PRIVATE
            or (
                persisted_bank_scope is None
                and _is_teacher(_bank_creator(resolved_bank))
            )
        ):
            bank_creator = _bank_creator(resolved_bank)
            return bool(
                bank_creator is not None
                and _is_teacher(bank_creator)
                and private_owner is not None
                and getattr(private_owner, "id", None) == getattr(bank_creator, "id", None)
            )
        # A private candidate is comparable only to its owner.  This also
        # prevents an administrator's broad audit permission from exposing a
        # private row while the administrator adds common content.
        return bool(
            _is_teacher(user)
            and private_owner is not None
            and getattr(private_owner, "id", None) == getattr(user, "id", None)
            and can_view_question(user, question, bank=resolved_bank)
        )
    return False


def can_edit_question(user, question, *, bank=None):
    """Return whether an actor may mutate one question or its answers."""
    if question is None:
        return False
    resolved_bank = _question_bank(question, bank)
    if bank is not None and resolved_bank is None:
        return False
    if _is_admin(user):
        return True
    if not _is_teacher(user):
        return False
    resolved_scope, private_owner, resolved_bank = _question_scope_state(question, resolved_bank)
    return (
        resolved_scope in (QUESTION_SCOPE_PRIVATE, QUESTION_SCOPE_LEGACY_PRIVATE)
        and private_owner is not None
        and getattr(private_owner, "id", None) == getattr(user, "id", None)
        and _question_bank_allows(user, resolved_scope, private_owner, resolved_bank)
    )


def can_delete_question(user, question, *, bank=None):
    """Return whether an actor may delete one question."""
    return can_edit_question(user, question, bank=bank)


def can_use_question_for_class(course, question, *, bank=None):
    """Authorize class runtime use with the course's current teacher.

    Callers must pass the course, not a student or an administrator.  This
    helper is intentionally separate from the general actor policy so a class
    consumer cannot broaden a private supplement by using an audit principal.
    """
    actor = class_teacher_actor(course)
    return bool(actor and can_use_question(actor, question, bank=bank))


def require_question_view(question, *, bank=None, user=None):
    """Abort unless the actor may read this question."""
    actor = current_user if user is None else user
    if not question:
        abort(404)
    if not can_view_question(actor, question, bank=bank):
        abort(403)
    return question


def require_question_edit(question, *, bank=None, user=None):
    """Abort unless the actor may mutate this question."""
    actor = current_user if user is None else user
    if not question:
        abort(404)
    if not can_edit_question(actor, question, bank=bank):
        abort(403)
    return question


def require_question_delete(question, *, bank=None, user=None):
    """Abort unless the actor may delete this question."""
    actor = current_user if user is None else user
    if not question:
        abort(404)
    if not can_delete_question(actor, question, bank=bank):
        abort(403)
    return question


def new_question_scope(user, bank):
    """Return the server-owned scope for a newly persisted question.

    A teacher contribution to a shared bank is a private overlay owned by the
    authenticated teacher.  Administrator contributions to a shared bank are
    shared.  Existing private-bank behavior is unchanged: even an
    administrator importing there creates a private row owned by the bank's
    teacher, never a shared row.  The caller's payload is intentionally not
    consulted for either value.
    """
    bank_scope, bank_creator = _bank_scope_state(bank)
    persisted_bank_scope = bank_visibility(bank)
    if bank_creator is None or bank_scope == "__invalid__":
        raise ValueError("Không thể xác định quyền sở hữu ngân hàng.")
    if persisted_bank_scope == BANK_VISIBILITY_SHARED:
        if _is_admin(user):
            return QUESTION_SCOPE_SHARED
        if _is_teacher(user) and can_add_question(user, bank):
            return QUESTION_SCOPE_PRIVATE
        raise ValueError("Không có quyền thêm câu riêng vào ngân hàng dùng chung.")
    if bank_scope in (BANK_VISIBILITY_PRIVATE, "legacy_private") and _is_teacher(bank_creator):
        if _is_admin(user) or getattr(user, "id", None) == getattr(bank_creator, "id", None):
            return QUESTION_SCOPE_PRIVATE
    if _is_admin(user) and _is_admin(bank_creator):
        # Keep newly added administrator content explicit even while the bank
        # itself remains a legacy NULL row awaiting reviewed backfill.
        return QUESTION_SCOPE_SHARED
    raise ValueError("Không có quyền tạo câu hỏi trong ngân hàng này.")


def set_new_question_scope(question, user, bank=None):
    """Stamp scope/owner on a new question without trusting request fields."""
    resolved_bank = _question_bank(question, bank)
    scope = new_question_scope(user, resolved_bank)
    setattr(question, "scope", scope)
    if scope == QUESTION_SCOPE_PRIVATE:
        # Teacher overlays are owned by the authenticated contributor even
        # though the containing shared bank is owned by an administrator.
        # Imports into an existing private bank retain the bank owner's
        # principal, including when an administrator performs the import.
        if _is_teacher(user) and bank_visibility(resolved_bank) == BANK_VISIBILITY_SHARED:
            owner = user
        else:
            owner = _bank_creator(resolved_bank)
        if not owner or not _is_teacher(owner):
            raise ValueError("Không thể xác định giáo viên sở hữu câu hỏi riêng.")
        setattr(question, "private_owner_id", owner.id)
    else:
        setattr(question, "private_owner_id", None)
    return question


# Descriptive aliases keep service callers readable and make the bank/question
# distinction explicit without duplicating policy implementations.
can_view_bank_question = can_view_question
can_use_bank_question = can_use_question
can_edit_bank_question = can_edit_question
can_delete_bank_question = can_delete_question
require_bank_question_view = require_question_view
require_bank_question_edit = require_question_edit
require_bank_question_delete = require_question_delete


def role_required(*allowed_roles: str) -> Callable[[Callable[ViewParameters, ViewResult]], Callable[ViewParameters, ViewResult]]:
    """Allow admins and explicitly listed roles to use a Flask view."""

    def decorator(view: Callable[ViewParameters, ViewResult]) -> Callable[ViewParameters, ViewResult]:
        @wraps(view)
        def wrapped(*args: ViewParameters.args, **kwargs: ViewParameters.kwargs) -> ViewResult:
            if not current_user.is_authenticated:
                return redirect(url_for("login"))
            if current_user.role == "admin" or current_user.role in allowed_roles:
                return view(*args, **kwargs)
            flash("Bạn không có quyền truy cập trang này.", "danger")
            return redirect(url_for("index"))

        return wrapped

    return decorator
