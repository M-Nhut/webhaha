"""ID6 identity and catalog selection, independent of document import parsers.

The active catalog is grade 9, Chapter 8, combined lesson ``i``.  Import
files provide the classification prefix (for example ``9C8Ni-1D``); only the
save boundary appends a suffix from the per-scope monotonic counter.
"""
import re

from sqlalchemy import case, event, inspect, select, text, update
from sqlalchemy.orm import Session

from database import db
from models import BankQuestion, CurriculumNode, ID6Counter
from services.curriculum_data import (
    CHAPTER8_CODE,
    CHAPTER8_GRADE,
    CHAPTER8_TOPIC_CODE,
    CHAPTER8_TOPIC_NAME,
    CHAPTER8_VERSION,
    RETAINED_CATEGORY_CODES,
    RETAINED_LESSON_CODE,
)
from services.question_policy import (
    TYPE_CODES,
    canonical_type,
    id6_question_type,
    id6_type_code,
    require_supported_type,
)

LEVEL_CODES = {"nhan_biet": "N", "thong_hieu": "H", "van_dung": "V", "van_dung_cao": "C"}
_ID_PREFIX_BODY = (
    r"(?P<grade>[6-9])C(?P<chapter>[1-9A-Z])(?P<level>[NHVC])"
    r"(?P<section>i)-(?P<category>[1-8])(?P<type>[TDS])"
)
_ID_BODY = _ID_PREFIX_BODY + r"(?:\.(?P<sequence>[1-9]\d*))?"
ID_PATTERN = re.compile(_ID_BODY, re.I)
ID_PREFIX_PATTERN = re.compile(_ID_PREFIX_BODY, re.I)
TAG_PATTERN = re.compile(r"%\[\s*(" + _ID_BODY + r")\s*\]", re.I)


def _normalize_grade(value):
    return re.sub(r"^Lớp\s*", "", str(value or "").strip(), flags=re.I).upper()


def _normalize_lesson(value):
    value = str(value or "").strip()
    return "i" if value.lower() == "i" else value.upper()


def is_chapter8_scope(grade, chapter):
    """Check for the active grade 9 / Chapter 8 scope."""
    return _normalize_grade(grade) == CHAPTER8_GRADE and str(chapter or "").strip().upper() == CHAPTER8_CODE

is_chapter6_scope = is_chapter8_scope


def is_retained_lesson_scope(grade, chapter, lesson=None, category=None):
    """Return whether curriculum metadata is in the retained combined lesson."""
    if not is_chapter8_scope(grade, chapter):
        return False
    if lesson is not None and _normalize_lesson(lesson) != RETAINED_LESSON_CODE:
        return False
    return category is None or str(category or "").strip() in RETAINED_CATEGORY_CODES


def parse_id6(value, **kwargs):
    """Parse an ID6 prefix or full ID under the single standard (T=single, D=true_false, S=short_answer)."""
    value = (value or "").strip()
    match = TAG_PATTERN.fullmatch(value) or ID_PATTERN.fullmatch(value)
    if not match:
        return None
    groups = match.groupdict()
    data = {
        "grade": groups["grade"].upper(),
        "chapter": groups["chapter"].upper(),
        "level": groups["level"].upper(),
        "section": _normalize_lesson(groups["section"]),
        "category": groups["category"],
        "type": groups["type"].upper(),
        "sequence": groups.get("sequence"),
    }
    if not is_retained_lesson_scope(data['grade'], data['chapter'], data['section'], data['category']):
        return None
    decoded_type = id6_question_type(data["type"])
    if not decoded_type:
        return None
    prefix = f"{data['grade']}C{data['chapter']}{data['level']}{data['section']}-{data['category']}{data['type']}"
    source_id = prefix + (f".{int(data['sequence'])}" if data["sequence"] is not None else "")
    return dict(
        source_id=source_id,
        id6_prefix=prefix,
        has_sequence=data["sequence"] is not None,
        grade=f"Lớp {data['grade']}",
        chapter=data['chapter'],
        section=data['section'],
        question_category=data['category'],
        difficulty_level={v: k for k, v in LEVEL_CODES.items()}[data['level']],
        question_type=decoded_type,
        type_code=data["type"],
        id6_sequence=int(data['sequence']) if data["sequence"] is not None else None,
    )


def parse_id6_for_record(source_id, **kwargs):
    """Decode a bank/preview source ID under the single standard."""
    source = str(source_id or "").strip()
    if not source:
        return None
    return parse_id6(source)


def parse_bank_question_id6(question):
    """Parser for a persisted BankQuestion row."""
    return parse_id6_for_record(getattr(question, "source_id", None))


def make_id6_prefix(grade, chapter, section, category, difficulty, question_type, **kwargs):
    """Build a classification prefix without allocating or previewing a suffix."""
    grade = _normalize_grade(grade)
    section = _normalize_lesson(section)
    question_type = canonical_type(question_type)
    if not is_retained_lesson_scope(grade, chapter, section, category):
        raise ValueError("Thông tin ID câu hỏi không hợp lệ: chỉ hỗ trợ Chương 8, bài kết hợp i.")
    if difficulty not in LEVEL_CODES or question_type not in TYPE_CODES:
        raise ValueError("Hãy chọn mức độ NB/TH/VD/VDC và loại T/D/S hợp lệ.")
    prefix = f"{grade}C{str(chapter).strip().upper()}{LEVEL_CODES[difficulty]}{section}-{str(category).strip()}{TYPE_CODES[question_type]}"
    if not ID_PREFIX_PATTERN.fullmatch(prefix):
        raise ValueError("Thông tin ID câu hỏi không hợp lệ: chỉ hỗ trợ Chương 8, bài kết hợp i.")
    return prefix


def make_id6(grade, chapter, section, category, difficulty, question_type, sequence, **kwargs):
    if isinstance(sequence, bool):
        raise ValueError("Số thứ tự ID6 phải là số nguyên dương.")
    try:
        sequence = int(sequence)
    except (TypeError, ValueError):
        raise ValueError("Số thứ tự ID6 phải là số nguyên dương.") from None
    if sequence < 1:
        raise ValueError("Số thứ tự ID6 phải là số nguyên dương.")
    prefix = make_id6_prefix(grade, chapter, section, category, difficulty, question_type)
    code = f"{prefix}.{sequence}"
    if not ID_PATTERN.fullmatch(code):
        raise ValueError("Thông tin ID câu hỏi không hợp lệ: chỉ hỗ trợ Chương 8, bài kết hợp i.")
    return code



def select_curriculum(question, node_id):
    try:
        node = db.session.get(CurriculumNode, int(node_id))
    except (TypeError, ValueError):
        node = None
    if (not node or not node.is_active
            or not is_retained_lesson_scope(node.grade, node.chapter_code,
                                             node.lesson_code, node.category_code)):
        raise ValueError("Hãy chọn một dạng đang sử dụng trong Chương 8, bài kết hợp i.")
    question.curriculum_node = node
    question.curriculum_node_id = node.id
    question.grade = f"Lớp {node.grade}"
    question.chapter = node.chapter_code
    question.section = node.lesson_code
    question.question_category = node.category_code
    # Explicit teacher selection records the scope, but never fabricates a
    # source prefix.  A prefix can only come from file metadata.
    # Keep legacy source identity independent of reviewed learning labels.
    question.catalog_version = node.catalog_version or CHAPTER8_VERSION
    question.topic = node.topic_name or CHAPTER8_TOPIC_NAME
    return node


def _counter_high_water(session, scope):
    """Read the counter without mutating it (used by read-only previews)."""
    value = session.execute(select(ID6Counter.last_sequence).where(ID6Counter.scope == scope)).scalar()
    existing = session.execute(select(BankQuestion.id6_sequence).where(
        BankQuestion.id6_scope == scope, BankQuestion.id6_sequence.is_not(None)
    )).scalars().all()
    return max([value or 0, *(int(item) for item in existing if item is not None)], default=0)


def _upsert_counter(session, scope, minimum=0):
    """Create/touch a counter atomically while retaining its high-water mark."""
    connection = session.connection()
    if connection.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif connection.dialect.name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError("ID6 cần SQLite hoặc PostgreSQL.")
    table = ID6Counter.__table__
    statement = insert(table).values(scope=scope, last_sequence=0)
    last = connection.execute(statement.on_conflict_do_update(
        index_elements=[table.c.scope], set_={"last_sequence": table.c.last_sequence}
    ).returning(table.c.last_sequence)).scalar_one()
    # The counter row remains write-locked until the surrounding transaction
    # ends.  ``minimum`` is used only to preserve an imported full suffix that
    # is newer than the current counter; it never lowers the counter.
    if minimum > last:
        connection.execute(update(table).where(table.c.scope == scope).values(last_sequence=minimum))
        last = minimum
    return last


def _reserve_sequence(session, scope):
    """Allocate the next suffix atomically; deleted numbers are never reused."""
    last = _upsert_counter(session, scope)
    existing = session.execute(select(BankQuestion.id6_sequence).where(
        BankQuestion.id6_scope == scope, BankQuestion.id6_sequence.is_not(None)
    )).scalars().all()
    pending = [q.id6_sequence for q in session.new if isinstance(q, BankQuestion)
               and q.id6_scope == scope and q.id6_sequence is not None]
    sequence = max([last, *(int(value) for value in existing), *(int(value) for value in pending)], default=0) + 1
    _upsert_counter(session, scope, sequence)
    return sequence


def preview_sequence(node):
    if (not node or not is_retained_lesson_scope(node.grade, node.chapter_code,
                                                  node.lesson_code, node.category_code)):
        raise ValueError("Chỉ có thể xem số thứ tự cho Chương 8, bài kết hợp i.")
    scope = node.canonical_code
    # This function is deliberately read-only: no counter row or lock is
    # created while a browser is merely asking what the next suffix would be.
    return _counter_high_water(db.session, scope) + 1


def synchronize_identity(session, question):
    import json
    labels = json.loads(question.classification_data or '{}')
    if question.classification_status == 'teacher_confirmed' and labels.get('curriculum_mode') == 'general':
        return
    if question.classification_status == 'teacher_confirmed' and question.curriculum_node_id:
        # Source tags are optional provenance. Explicit reviewed labels win.
        return
    is_new = question in session.new
    parsed = parse_id6_for_record(question.source_id)
    if is_new:
        require_supported_type(question.question_type or (parsed['question_type'] if parsed else 'single'))
    elif canonical_type(question.question_type) not in TYPE_CODES:
        return

    if not parsed:
        raw_source = str(question.source_id or "").strip()
        source_was_changed = is_new or inspect(question).attrs.source_id.history.has_changes()
        if raw_source and (ID_PATTERN.fullmatch(raw_source) or TAG_PATTERN.fullmatch(raw_source)) and source_was_changed:
            raise ValueError(
                "Tiền tố ID6 không hợp lệ theo chuẩn duy nhất 9C8{mức độ}i-{dạng}[TDS]."
            )
        return

    scope = CurriculumNode.make_canonical_code(
        parsed['grade'].split()[-1], parsed['chapter'], parsed['section'],
        parsed['question_category']
    )
    if not is_retained_lesson_scope(parsed['grade'], parsed['chapter'], parsed['section'], parsed['question_category']):
        return

    # Reviewed curriculum labels are authoritative. Old source IDs remain
    # provenance only; editing a reviewed label must not rewrite source metadata.
    if not is_new and not inspect(question).attrs.source_id.history.has_changes():
        return

    state = inspect(question)
    source_changed = is_new or state.attrs.source_id.history.has_changes()
    _ensure_source_consistency(session, question, parsed, scope, strict=source_changed)
    if not is_new and not source_changed:
        if parsed['id6_sequence'] is not None and not question.id6_scope:
            question.id6_scope = scope
            question.id6_sequence = parsed['id6_sequence']
            _set_identity_fields(session, question, parsed, scope, update_type=False)
            _upsert_counter(session, scope, parsed['id6_sequence'])
        return

    old_scope = question.id6_scope
    old_sequence = question.id6_sequence

    _set_identity_fields(session, question, parsed, scope, update_type=is_new)
    if not is_new and old_scope == scope and old_sequence:
        sequence = old_sequence
    else:
        sequence = _reserve_sequence(session, scope)

    question.id6_scope = scope
    question.id6_sequence = sequence
    question.source_id = f"{parsed['id6_prefix']}.{sequence}"
    question.catalog_version = CHAPTER8_VERSION


def _set_identity_fields(session, question, parsed, scope, *, update_type=True):
    """Copy parsed source metadata and resolve its existing catalog node."""
    question.grade = parsed['grade']
    question.chapter = parsed['chapter']
    question.section = parsed['section']
    question.question_category = parsed['question_category']
    question.difficulty_level = parsed['difficulty_level']
    if update_type or not getattr(question, "question_type", None):
        question.question_type = canonical_type(parsed['question_type'])
    question.id6_scope = scope
    question.catalog_version = CHAPTER8_VERSION
    expected_node_id = session.execute(
        select(CurriculumNode.id).where(CurriculumNode.canonical_code == scope)
    ).scalar()
    if not question.curriculum_node_id and expected_node_id:
        question.curriculum_node_id = expected_node_id


def _ensure_source_consistency(session, question, parsed, scope, *, strict=False):
    """Reject a source/metadata mismatch instead of silently changing labels."""
    expected = {
        "grade": parsed["grade"],
        "chapter": parsed["chapter"],
        "section": parsed["section"],
        "question_category": parsed["question_category"],
        "difficulty_level": parsed["difficulty_level"],
        "question_type": canonical_type(parsed["question_type"]),
    }
    for field, wanted in expected.items():
        current = getattr(question, field, None)
        if current in (None, ""):
            continue
        if field == "grade":
            current = _normalize_grade(current)
            wanted = _normalize_grade(wanted)
        elif field == "section":
            current = _normalize_lesson(current)
            wanted = _normalize_lesson(wanted)
        elif field == "question_type":
            current = canonical_type(current)
        else:
            current = str(current).strip().upper() if field in ("chapter", "question_category") else str(current).strip()
        if current != wanted:
            # A default is absent on newly constructed SQLAlchemy objects; a
            # populated value here is an explicit parser/teacher choice.
            raise ValueError("Tiền tố ID6 và metadata câu hỏi đang xung đột; không tự đổi phân loại.")
    if question.id6_scope and question.id6_scope != scope:
        raise ValueError("Tiền tố ID6 không khớp phạm vi đã lưu; không tự đổi phân loại.")
    if question.id6_sequence is not None and parsed["id6_sequence"] is not None:
        if int(question.id6_sequence) != int(parsed["id6_sequence"]):
            raise ValueError("Số thứ tự ID6 và metadata đã lưu đang xung đột.")
    if question.curriculum_node_id:
        node = session.get(CurriculumNode, question.curriculum_node_id)
        if node and node.canonical_code != scope:
            raise ValueError("Tiền tố ID6 không khớp dạng bài đã lưu; không tự đổi phân loại.")


@event.listens_for(Session, 'before_flush')
def _sync_id6_before_flush(session, flush_context, instances):
    deleted_questions = [q for q in session.deleted if isinstance(q, BankQuestion)]
    if deleted_questions:
        connection = session.connection()
        # Preserve the previous cascade when an upgraded database still has the
        # historical mapping table. It must not prevent deleting its question.
        if inspect(connection).has_table('question_skill'):
            connection.execute(text('DELETE FROM question_skill WHERE question_id = :question_id'),
                               [{'question_id': q.id} for q in deleted_questions])
    for question in list(session.new) + list(session.dirty):
        if isinstance(question, BankQuestion) and question not in session.deleted:
            synchronize_identity(session, question)


def catalog_options():
    return [dict(id=n.id, grade=n.grade, chapter=n.chapter_code, chapter_name=n.chapter_name,
                 section=n.lesson_code, lesson_name=n.lesson_name, category=n.category_code,
                 category_name=n.category_name, topic_code=n.topic_code or CHAPTER8_TOPIC_CODE,
                 topic_name=n.topic_name or CHAPTER8_TOPIC_NAME)
            for n in CurriculumNode.query.filter_by(
            is_active=True, grade=CHAPTER8_GRADE, chapter_code=CHAPTER8_CODE,
            lesson_code=RETAINED_LESSON_CODE
            ).all()]


def migrate_id6_metadata():
    """Backfill metadata only where a target full source ID already exists.

    This startup-safe adapter deliberately does not infer IDs from
    ``question_skill``, content, category names, or old source strings.  The
    explicit Chapter 8 migration owns any reviewed legacy mapping.
    """
    for question in BankQuestion.query.filter(BankQuestion.id6_scope.is_(None)).order_by(BankQuestion.id).all():
        parsed = parse_bank_question_id6(question)
        if not parsed or parsed['id6_sequence'] is None:
            continue
        scope = CurriculumNode.make_canonical_code(
            parsed['grade'].split()[-1], parsed['chapter'], parsed['section'],
            parsed['question_category']
        )
        # Existing persisted ``question_type`` is the compatibility anchor;
        # startup metadata repair must never flip D/T semantics or rewrite a
        # reviewed answer structure.
        _set_identity_fields(db.session, question, parsed, scope, update_type=False)
        question.id6_scope = scope
        question.id6_sequence = parsed['id6_sequence']
        _upsert_counter(db.session, scope, parsed['id6_sequence'])
    db.session.commit()
