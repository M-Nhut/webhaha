"""Class-scoped question sources and immutable paper provenance.

The adaptive selector is deliberately a pure ranking/selection component.  A
class-bound route must first resolve its source through this module so the
teacher currently assigned to the class, rather than the requesting student
or an administrator, is the authority for private overlay questions.

New papers persist a small source manifest on :class:`models.Exam`.  It is a
snapshot of the source/audience decision and is never used to rewrite the
frozen question text or answer key.  Rows created before this manifest existed
remain readable through the explicit legacy compatibility path.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from database import db
from models import BankQuestion, Course, Exam, ExamQuestion, QuestionBank
from services.access_control import (
    BANK_VISIBILITY_PRIVATE,
    BANK_VISIBILITY_SHARED,
    can_use_bank,
    can_use_question_for_class,
    class_teacher_actor,
    resolve_question_source,
)
from services.personalization_evidence import content_hash, question_snapshot


# The first implementation of the manifest did not carry a hash of the
# complete frozen question/answer snapshot.  Keep the old version readable as
# an explicit compatibility format, but every newly written manifest uses the
# stronger contract below.
MANIFEST_VERSION = "phase4-source-manifest-v2"
LEGACY_MANIFEST_VERSIONS = frozenset({"phase4-source-manifest-v1"})


def _normalise_grade(value) -> str:
    """Normalise the two grade spellings used by legacy imports."""
    text = str(value or "").strip().casefold()
    if text.startswith("lớp "):
        # ``lớp `` is four code points.  The previous ``[5:]`` silently
        # turned the valid spelling ``Lớp 9`` into an empty grade.
        text = text[4:].strip()
    return text


def _is_supported_grade(bank: QuestionBank) -> bool:
    # The active product scope is Grade 9 / Chapter 8 / lesson i.  Accept the
    # historical ``Lớp 9`` spelling while keeping other grades out of the
    # class source resolver.
    return _normalise_grade(getattr(bank, "grade", None)) == "9"


def _parse_bank_ids(bank_ids: Iterable[int] | None):
    """Parse a bank-id collection without dropping malformed values.

    Request and persisted-session values are untrusted.  Silently skipping a
    bad value would turn ``[authorized_id, "oops"]`` into an apparently valid
    single-bank request.  The resolver therefore returns an explicit error for
    malformed or duplicate ids.  String integers remain accepted because a
    normal HTML form submits ids as strings and a few historical sessions
    stored them that way.
    """
    if bank_ids is None:
        return (), None
    if isinstance(bank_ids, (str, bytes)):
        return (), "bank_ids_invalid"
    try:
        raw_values = list(bank_ids)
    except TypeError:
        return (), "bank_ids_invalid"
    values = []
    for value in raw_values:
        if isinstance(value, bool):
            return (), "bank_ids_invalid"
        if isinstance(value, int):
            number = value
        elif isinstance(value, str) and value.strip().isdigit():
            number = int(value.strip())
        else:
            return (), "bank_ids_invalid"
        if number <= 0:
            return (), "bank_ids_invalid"
        if number in values:
            return (), "bank_ids_duplicate"
        values.append(number)
    return tuple(sorted(values)), None


def _requested_ids(bank_ids: Iterable[int] | None) -> tuple[int, ...]:
    """Return canonical ids for trusted internal callers.

    Public resolver functions use :func:`_parse_bank_ids` first and never use
    this helper to decide authorization.  Keeping this small compatibility
    helper avoids changing callers that only need canonical ordering.
    """
    values, error = _parse_bank_ids(bank_ids)
    return values if error is None else ()


def resolve_class_banks(course: Course, bank_ids: Iterable[int] | None, *, require_grade: bool = True):
    """Resolve all active banks usable by the class's current teacher.

    The returned ``valid`` flag is all-or-nothing: a caller that asks for two
    banks must not silently receive one authorized bank and accidentally drop
    the other.  The function is intentionally independent of Flask globals.
    """
    requested, parse_error = _parse_bank_ids(bank_ids)
    teacher = class_teacher_actor(course) if course else None
    if parse_error:
        return {"valid": False, "reason": parse_error, "teacher": teacher,
                "banks": [], "bank_ids": []}
    if not course or not getattr(course, "is_active", True):
        return {"valid": False, "reason": "class_unavailable", "teacher": teacher,
                "banks": [], "bank_ids": list(requested)}
    if not teacher or not requested:
        return {"valid": False, "reason": "teacher_or_bank_missing", "teacher": teacher,
                "banks": [], "bank_ids": list(requested)}

    banks = QuestionBank.query.filter(
        QuestionBank.id.in_(requested),
        QuestionBank.is_active.is_(True),
        QuestionBank.subject == course.subject,
    ).all()
    by_id = {bank.id: bank for bank in banks}
    authorised = []
    for bank_id in requested:
        bank = by_id.get(bank_id)
        if (
            bank
            and (not require_grade or _is_supported_grade(bank))
            and can_use_bank(teacher, bank)
        ):
            authorised.append(bank)
    valid = len(authorised) == len(requested)
    return {
        "valid": valid,
        "reason": None if valid else "bank_not_authorized",
        "teacher": teacher,
        "banks": authorised if valid else [],
        "bank_ids": list(requested),
    }


def resolve_class_questions(course: Course, bank_ids: Iterable[int] | None,
                            questions: Iterable[BankQuestion] | None = None,
                            *, require_grade: bool = True):
    """Return questions permitted by the resolved class source.

    When ``questions`` is supplied, only those objects are filtered.  This is
    useful for a selector that already loaded and readiness-filtered rows; it
    still rechecks each row against the current class teacher.
    """
    source = resolve_class_banks(course, bank_ids, require_grade=require_grade)
    if not source["valid"]:
        return {**source, "questions": []}
    allowed_bank_ids = set(source["bank_ids"])
    banks_by_id = {bank.id: bank for bank in source["banks"]}
    rows = list(questions) if questions is not None else BankQuestion.query.filter(
        BankQuestion.bank_id.in_(source["bank_ids"])
    ).all()
    allowed = [
        question for question in rows
        if getattr(question, "bank_id", None) in allowed_bank_ids
        # Passing the resolved bank is important: a malformed/detached object
        # must not authorize itself through a stale ``question.bank``
        # relationship whose id is different from its persisted bank_id.
        and can_use_question_for_class(
            course, question, bank=banks_by_id.get(getattr(question, "bank_id", None))
        )
    ]
    return {**source, "questions": allowed}


def _manifest_scope(question: BankQuestion):
    source = resolve_question_source(question)
    key = source.get("key")
    if key == "common":
        scope = "shared"
    elif key == "private":
        scope = "private"
    else:
        scope = "unknown"
    bank = getattr(question, "bank", None)
    visibility = getattr(bank, "visibility", None) if bank else None
    if visibility not in (BANK_VISIBILITY_SHARED, BANK_VISIBILITY_PRIVATE):
        # Legacy teacher-owned NULL banks are already resolved as private by
        # the central access policy.  Carry that effective decision into a
        # new paper's manifest without mutating the historical bank row.  An
        # ambiguous legacy admin bank resolves to ``unknown`` above and still
        # fails closed.
        if key == "private":
            visibility = BANK_VISIBILITY_PRIVATE
        elif key == "common":
            visibility = BANK_VISIBILITY_SHARED
        else:
            visibility = None
    return scope, source.get("owner_id"), visibility


def build_source_manifest(course: Course, pairs: Iterable[tuple[ExamQuestion, BankQuestion]],
                          bank_ids: Iterable[int] | None = None):
    """Build an immutable, audit-safe manifest for copied exam questions."""
    requested, parse_error = _parse_bank_ids(bank_ids)
    if parse_error:
        raise ValueError(f"Invalid source bank ids: {parse_error}")
    teacher = class_teacher_actor(course) if course else None
    if not course or not teacher or not getattr(course, "is_active", True):
        raise ValueError("An active class with a current teacher is required for a source manifest")
    pairs = list(pairs)
    if not pairs:
        raise ValueError("A source manifest requires at least one frozen question")
    items = []
    manifest_bank_ids = set(requested)
    bank_questions = []
    seen_exam_question_ids = set()
    seen_bank_question_ids = set()
    for index, pair in enumerate(pairs):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("Malformed source-manifest question pair")
        exam_question, bank_question = pair
        exam_question_id = getattr(exam_question, "id", None)
        bank_question_id = getattr(bank_question, "id", None)
        scope, owner_id, visibility = _manifest_scope(bank_question)
        bank_id = getattr(bank_question, "bank_id", None)
        if not isinstance(exam_question_id, int) or exam_question_id <= 0:
            raise ValueError("Manifest questions must be persisted before attachment")
        if not isinstance(bank_question_id, int) or bank_question_id <= 0:
            raise ValueError("Manifest bank questions must be persisted before attachment")
        if not isinstance(bank_id, int) or bank_id <= 0:
            raise ValueError("Manifest bank ids must be positive integers")
        if exam_question_id in seen_exam_question_ids or bank_question_id in seen_bank_question_ids:
            raise ValueError("A source manifest cannot contain duplicate question rows")
        seen_exam_question_ids.add(exam_question_id)
        seen_bank_question_ids.add(bank_question_id)
        bank_questions.append(bank_question)
        if requested and bank_id not in manifest_bank_ids:
            raise ValueError("A frozen question belongs to a bank outside the session source")
        manifest_bank_ids.add(bank_id)
        if scope not in ("shared", "private") or visibility not in (
            BANK_VISIBILITY_SHARED, BANK_VISIBILITY_PRIVATE
        ):
            raise ValueError("A frozen question has an unresolved source scope")
        if scope == "shared" and visibility != BANK_VISIBILITY_SHARED:
            raise ValueError("A shared question cannot come from a private bank")
        if scope == "private" and not isinstance(owner_id, int):
            raise ValueError("A private frozen question requires a teacher owner")
        if scope == "shared" and owner_id is not None:
            raise ValueError("A shared frozen question cannot carry a private owner")
        order_index = getattr(exam_question, "order_index", None)
        if not isinstance(order_index, int):
            order_index = index
        items.append({
            "order_index": order_index,
            "exam_question_id": exam_question_id,
            "bank_question_id": bank_question_id,
            "bank_id": bank_id,
            "scope": scope,
            "private_owner_id": owner_id,
            "bank_visibility": visibility,
            "source_id6": getattr(exam_question, "source_id6", None)
                or getattr(bank_question, "source_id", None),
            "source_content_revision": getattr(exam_question, "source_content_revision", None)
                or getattr(bank_question, "content_revision", None),
            "source_content_hash": getattr(exam_question, "source_content_hash", None)
                or getattr(bank_question, "content_hash", None),
            # This is deliberately independent from the source content hash:
            # it covers the copied text, options/answer key and frozen labels.
            "frozen_snapshot_hash": content_hash(question_snapshot(exam_question)),
        })
    source = resolve_class_banks(course, sorted(manifest_bank_ids), require_grade=True)
    if not source["valid"]:
        raise ValueError("The source manifest contains a bank unavailable to the current class teacher")
    resolved = resolve_class_questions(course, sorted(manifest_bank_ids), bank_questions)
    if len(resolved["questions"]) != len(bank_questions):
        raise ValueError("The source manifest contains a question unavailable to the current class teacher")
    return {
        "version": MANIFEST_VERSION,
        "course_id": getattr(course, "id", None),
        "teacher_id": getattr(teacher, "id", None),
        "bank_ids": sorted(manifest_bank_ids),
        "items": items,
    }


def attach_source_manifest(exam: Exam, course: Course,
                           pairs: Iterable[tuple[ExamQuestion, BankQuestion]],
                           bank_ids: Iterable[int] | None = None):
    """Persist a manifest after all copied question snapshots are complete."""
    manifest = build_source_manifest(course, pairs, bank_ids=bank_ids)
    exam.source_manifest = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    return manifest


def _stored_manifest(exam: Exam):
    """Return a stored manifest without hiding malformed JSON.

    The old ``Exam.get_source_manifest`` accessor intentionally returns ``{}``
    on parse errors, which is useful for ordinary display but unsafe for an
    authorization boundary.  This helper is retained for callers that only
    need the payload; validation uses :func:`_manifest_state` below to retain
    the absent/malformed distinction.
    """
    manifest, _present, malformed = _manifest_state(exam)
    return {} if malformed else manifest


def _manifest_state(exam):
    """Return ``(payload, present, malformed)`` for a source manifest.

    A non-empty ``source_manifest`` column is an assertion that the row uses
    manifest semantics.  Any parse/type failure therefore fails closed and
    cannot fall through to the legacy no-manifest branch.  The earlier
    ``adaptive_metadata.source_manifest`` location is an explicit bridge for
    the short-lived Phase-4 compatibility build, and is consulted only when
    the dedicated column is truly absent (NULL).
    """
    if not exam:
        return {}, False, True
    raw = getattr(exam, "source_manifest", None)
    if raw is not None:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}, True, True
        return (payload, True, not isinstance(payload, dict))

    metadata = exam.get_adaptive_metadata() if hasattr(exam, "get_adaptive_metadata") else {}
    if isinstance(metadata, dict) and "source_manifest" in metadata:
        value = metadata.get("source_manifest")
        return (value, True, not isinstance(value, dict))
    return {}, False, False


def _is_positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_nonnegative_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_manifest_shape(manifest):
    """Validate the schema-level invariants independent of database rows."""
    if not isinstance(manifest, dict):
        return False, "manifest_malformed"
    version = manifest.get("version")
    if not isinstance(version, str) or version not in ({MANIFEST_VERSION} | LEGACY_MANIFEST_VERSIONS):
        return False, "manifest_version"
    if not _is_positive_int(manifest.get("course_id")):
        return False, "manifest_course_id"
    if not _is_positive_int(manifest.get("teacher_id")):
        return False, "manifest_teacher_id"
    bank_ids = manifest.get("bank_ids")
    if not isinstance(bank_ids, list) or any(not _is_positive_int(value) for value in bank_ids):
        return False, "manifest_bank_ids"
    if bank_ids != sorted(set(bank_ids)):
        return False, "manifest_bank_ids"
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        return False, "manifest_items"
    required = {
        "order_index", "exam_question_id", "bank_question_id", "bank_id",
        "scope", "private_owner_id", "bank_visibility", "source_id6",
        "source_content_revision", "source_content_hash",
    }
    if version == MANIFEST_VERSION:
        required.add("frozen_snapshot_hash")
    seen_exam = set()
    seen_bank = set()
    seen_order = set()
    for item in items:
        if not isinstance(item, dict) or not required.issubset(item):
            return False, "manifest_item_shape"
        if not _is_nonnegative_int(item.get("order_index")):
            return False, "manifest_item_id"
        for key in ("exam_question_id", "bank_question_id", "bank_id"):
            if not _is_positive_int(item.get(key)):
                return False, "manifest_item_id"
        if item["exam_question_id"] in seen_exam or item["bank_question_id"] in seen_bank:
            return False, "manifest_item_duplicate"
        if item["order_index"] in seen_order:
            return False, "manifest_item_order"
        seen_exam.add(item["exam_question_id"])
        seen_bank.add(item["bank_question_id"])
        seen_order.add(item["order_index"])
        if item["bank_id"] not in bank_ids:
            return False, "manifest_item_bank"
        if item["scope"] not in ("shared", "private"):
            return False, "manifest_item_scope"
        if item["bank_visibility"] not in (BANK_VISIBILITY_SHARED, BANK_VISIBILITY_PRIVATE):
            return False, "manifest_item_visibility"
        if item["scope"] == "shared" and item["bank_visibility"] != BANK_VISIBILITY_SHARED:
            return False, "manifest_item_scope"
        owner = item["private_owner_id"]
        if item["scope"] == "private":
            if not _is_positive_int(owner):
                return False, "manifest_item_owner"
        elif owner is not None:
            return False, "manifest_item_owner"
        revision = item["source_content_revision"]
        if revision is not None and not _is_positive_int(revision):
            return False, "manifest_item_revision"
        for key in ("source_content_hash", "frozen_snapshot_hash"):
            if key in item and item[key] is not None and (
                not isinstance(item[key], str) or not item[key]
            ):
                return False, "manifest_item_hash"
    return True, None


def validate_exam_source(exam: Exam, *, require_live: bool = False):
    """Validate snapshot integrity and (optionally) current class authority.

    ``snapshot_valid`` concerns only immutable data copied into the paper.
    ``current_authorized`` re-resolves the live bank/question policy.  This
    distinction lets the result page retain historical evidence while the
    take/Continue paths fail closed when a private overlay is no longer usable.
    """
    if not exam:
        return {
            "valid": False,
            "legacy": False,
            "snapshot_valid": False,
            "current_authorized": False,
            "reason": "exam_missing",
            "manifest": {},
        }

    manifest, manifest_present, manifest_malformed = _manifest_state(exam)
    course = getattr(exam, "course", None)
    if course is None and getattr(exam, "course_id", None):
        course = db.session.get(Course, exam.course_id)
    questions = list(getattr(exam, "questions", None) or [])

    # Explicit compatibility for papers created before the dedicated manifest
    # column.  They remain readable, but live operations still re-check the
    # current class teacher against every persisted session bank available to
    # the old row.  A malformed/non-dict manifest never enters this branch.
    if not manifest_present:
        current_authorized = bool(course and getattr(course, "is_active", True))
        reason = None
        if require_live and current_authorized:
            legacy_bank_ids = []
            metadata = exam.get_adaptive_metadata()
            session_id = metadata.get("practice_session_id") if isinstance(metadata, dict) else None
            if session_id:
                from models import PracticeSession
                session = db.session.get(PracticeSession, session_id)
                if not session or session.course_id != exam.course_id:
                    current_authorized = False
                    reason = "legacy_session_missing"
                else:
                    raw_session_ids = None
                    try:
                        raw_session_ids = json.loads(session.bank_ids or "[]")
                    except (TypeError, ValueError, json.JSONDecodeError):
                        pass
                    legacy_bank_ids, parse_error = _parse_bank_ids(raw_session_ids)
                    if parse_error:
                        current_authorized = False
                        reason = parse_error
                    elif not legacy_bank_ids:
                        # Explicit compatibility for the earliest fixed-paper
                        # rows: their session was created before bank
                        # provenance and the frozen questions have no
                        # bank_question_id either.  There is no source claim
                        # to broaden, so retain the old class/enrollment
                        # runtime while rejecting partially linked rows.
                        if (
                            getattr(exam, "question_bank_id", None) is not None
                            or any(getattr(question, "bank_question_id", None) is not None for question in questions)
                        ):
                            current_authorized = False
                            reason = "legacy_session_source_missing"
            elif getattr(exam, "question_bank_id", None):
                legacy_bank_ids = (exam.question_bank_id,)

            if current_authorized and legacy_bank_ids:
                source = resolve_class_banks(course, legacy_bank_ids, require_grade=True)
                if not source["valid"]:
                    current_authorized = False
                    reason = source["reason"]
                else:
                    allowed = {bank.id: bank for bank in source["banks"]}
                    linked_questions = [
                        question for question in questions
                        if getattr(question, "bank_question_id", None) is not None
                    ]
                    for question in questions:
                        bank_id = getattr(question, "bank_question_id", None)
                        # Pre-manifest diagnostics often froze only the paper
                        # text/answers and have no bank-question foreign keys.
                        # Preserve that explicit legacy shape; a partially
                        # linked paper is ambiguous and fails closed.
                        if not linked_questions:
                            break
                        if bank_id is None:
                            current_authorized = False
                            reason = reason or "legacy_question_source_missing"
                            break
                        bank_question = db.session.get(BankQuestion, bank_id) if bank_id else None
                        if (
                            not bank_question
                            or bank_question.bank_id not in allowed
                            or not can_use_question_for_class(
                                course, bank_question, bank=allowed[bank_question.bank_id]
                            )
                        ):
                            current_authorized = False
                            reason = reason or "question_not_authorized"
                            break
        return {
            "valid": current_authorized if require_live else True,
            "legacy": True,
            "snapshot_valid": True,
            "current_authorized": current_authorized,
            "reason": reason,
            "manifest": {},
        }

    if manifest_malformed:
        return {
            "valid": False,
            "legacy": False,
            "snapshot_valid": False,
            "current_authorized": False,
            "reason": "manifest_malformed",
            "manifest": manifest if isinstance(manifest, dict) else {},
        }

    shape_valid, shape_reason = _validate_manifest_shape(manifest)
    snapshot_valid = bool(shape_valid and course)
    current_authorized = bool(course and getattr(course, "is_active", True))
    reason = shape_reason
    # Do not inspect malformed item dictionaries or bank-id values after the
    # schema check.  In particular, a hostile ``exam_question_id`` list/dict
    # must produce a clean fail-closed result rather than an unhashable-key
    # exception during mapping.
    if not shape_valid or not course:
        if not course:
            reason = reason or "course_missing"
        return {
            "valid": False,
            "legacy": False,
            "compatibility": "manifest_v1" if (
                isinstance(manifest, dict)
                and isinstance(manifest.get("version"), str)
                and manifest.get("version") in LEGACY_MANIFEST_VERSIONS
            ) else None,
            "snapshot_valid": False,
            "current_authorized": False,
            "reason": reason or "manifest_malformed",
            "manifest": manifest if isinstance(manifest, dict) else {},
        }
    items = manifest.get("items") if isinstance(manifest, dict) else []
    manifest_version = manifest.get("version") if isinstance(manifest, dict) else None

    if snapshot_valid and manifest.get("course_id") != getattr(course, "id", None):
        snapshot_valid = False
        current_authorized = False
        reason = reason or "manifest_course_mismatch"

    # The legacy v1 format is intentionally accepted only as a reduced
    # manifest contract.  New v2 rows always carry ``frozen_snapshot_hash``.
    # The compatibility distinction is returned to callers for audit/UI use.
    compatibility = "manifest_v1" if manifest_version in LEGACY_MANIFEST_VERSIONS else None

    # A fixed practice session is a second persisted source assertion.  It is
    # checked even when the manifest itself is structurally valid, so tampering
    # with either side cannot silently narrow/expand a multi-bank paper.
    session = None
    metadata = exam.get_adaptive_metadata()
    session_id = metadata.get("practice_session_id") if isinstance(metadata, dict) else None
    if session_id:
        from models import PracticeSession
        session = db.session.get(PracticeSession, session_id)
        if not session or session.course_id != getattr(exam, "course_id", None):
            current_authorized = False
            reason = reason or "session_source_mismatch"
        else:
            raw_session_ids = None
            try:
                raw_session_ids = json.loads(session.bank_ids or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
            session_bank_ids, parse_error = _parse_bank_ids(raw_session_ids)
            manifest_bank_ids, manifest_error = _parse_bank_ids(
                manifest.get("bank_ids") if isinstance(manifest, dict) else None
            )
            if (
                parse_error
                or manifest_error
                or tuple(session_bank_ids) != tuple(manifest_bank_ids)
            ):
                current_authorized = False
                reason = reason or "session_source_mismatch"
            if session.subject != getattr(course, "subject", None):
                current_authorized = False
                reason = reason or "session_scope_mismatch"
            if session.scope_code != "9C8-i":
                current_authorized = False
                reason = reason or "session_scope_mismatch"
            metadata_student_id = metadata.get("student_id") if isinstance(metadata, dict) else None
            if metadata_student_id is not None and session.student_id != metadata_student_id:
                current_authorized = False
                reason = reason or "session_scope_mismatch"

    questions_by_id = {getattr(question, "id", None): question for question in questions}
    if len(questions_by_id) != len(questions) or not all(_is_positive_int(key) for key in questions_by_id):
        snapshot_valid = False
        current_authorized = False
        reason = reason or "manifest_question_mapping"

    # Manifest order is part of the frozen paper contract.  Do not fall back
    # to index matching when an id is missing; that was an authorization gap in
    # the initial resolver implementation.
    seen_items = set()
    for index, item in enumerate(items if isinstance(items, list) else []):
        exam_question = questions_by_id.get(item.get("exam_question_id")) if isinstance(item, dict) else None
        if (
            not exam_question
            or item.get("exam_question_id") in seen_items
            or item.get("order_index") != (
                getattr(exam_question, "order_index", None)
                if isinstance(getattr(exam_question, "order_index", None), int)
                else index
            )
        ):
            snapshot_valid = False
            current_authorized = False
            reason = reason or "manifest_question_mapping"
            continue
        seen_items.add(item["exam_question_id"])
        expected = {
            "bank_question_id": getattr(exam_question, "bank_question_id", None),
            "source_id6": getattr(exam_question, "source_id6", None),
            "source_content_revision": getattr(exam_question, "source_content_revision", None),
            "source_content_hash": getattr(exam_question, "source_content_hash", None),
        }
        for key, value in expected.items():
            if item.get(key) != value:
                snapshot_valid = False
                reason = reason or "snapshot_mismatch"
        if manifest_version == MANIFEST_VERSION:
            try:
                frozen_hash = content_hash(question_snapshot(exam_question))
            except (TypeError, ValueError, json.JSONDecodeError):
                frozen_hash = None
            if not frozen_hash or item.get("frozen_snapshot_hash") != frozen_hash:
                snapshot_valid = False
                reason = reason or "snapshot_mismatch"

        bank_question_id = item.get("bank_question_id")
        bank_id = item.get("bank_id")
        bank_question = db.session.get(BankQuestion, bank_question_id) if bank_question_id else None
        bank = db.session.get(QuestionBank, bank_id) if bank_id else None
        if (
            not bank_question
            or not bank
            or bank_question.bank_id != bank_id
            or not getattr(bank, "is_active", False)
        ):
            current_authorized = False
            reason = reason or "question_not_authorized"
            continue

        # Compare both the frozen source identity and the current persisted
        # source.  A teacher owner change must not make an old private overlay
        # look like the same source merely because the row id survived.
        live_scope, live_owner, live_visibility = _manifest_scope(bank_question)
        if (
            live_scope != item.get("scope")
            or live_owner != item.get("private_owner_id")
            or live_visibility != item.get("bank_visibility")
        ):
            current_authorized = False
            reason = reason or (
                "private_owner_mismatch"
                if item.get("scope") == "private"
                else "source_scope_mismatch"
            )
        # ``source_content_*`` identifies the source revision copied into the
        # frozen paper; it is intentionally *not* compared with today's bank
        # content.  Editing a bank after publication must not rewrite or
        # invalidate the already frozen text/answer key.  Manifest-vs-
        # ExamQuestion checks above, plus ``frozen_snapshot_hash``, detect a
        # tampered paper snapshot while this live check remains permission-only.
        if not can_use_question_for_class(course, bank_question, bank=bank):
            current_authorized = False
            reason = reason or "question_not_authorized"

    if snapshot_valid and len(seen_items) != len(questions):
        snapshot_valid = False
        current_authorized = False
        reason = reason or "manifest_question_mapping"

    # Resolve the entire bank set, not merely the bank referenced by the
    # legacy ``Exam.question_bank_id`` pointer.  This is the all-or-nothing
    # class authority check for teacher papers that span multiple banks.
    manifest_bank_ids, manifest_error = _parse_bank_ids(
        manifest.get("bank_ids") if isinstance(manifest, dict) else None
    )
    if manifest_error or not manifest_bank_ids:
        current_authorized = False
        reason = reason or (manifest_error or "manifest_bank_ids")
    elif getattr(exam, "question_bank_id", None) != manifest_bank_ids[0]:
        current_authorized = False
        reason = reason or "primary_bank_mismatch"
    bank_source = resolve_class_banks(course, manifest_bank_ids, require_grade=True) if course else {
        "valid": False, "reason": "class_unavailable"
    }
    if not bank_source["valid"]:
        current_authorized = False
        reason = reason or bank_source["reason"]

    # A snapshot mismatch is never live-valid.  The result/history page can
    # still render frozen rows because it does not call this with require_live.
    valid = (snapshot_valid and current_authorized) if require_live else snapshot_valid
    return {
        "valid": valid,
        "legacy": False,
        "compatibility": compatibility,
        "snapshot_valid": snapshot_valid,
        "current_authorized": current_authorized,
        "reason": reason,
        "manifest": manifest,
    }
