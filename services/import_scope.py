"""Persist and validate the curriculum scope of one imported file."""

import datetime as dt
import hashlib
import json

from database import db
from models import ImportSession
from services.id6_service import catalog_options

UNASSIGNED_TOPIC = "__unassigned__"


def editable_session(session_id, user_id=None):
    session = db.session.get(ImportSession, session_id)
    if not session or (user_id is not None and session.user_id != user_id):
        raise ValueError("Không tìm thấy phiên import.")
    if session.file_type not in ("tex", "latex"):
        raise ValueError("Định dạng phiên nhập đã ngừng hỗ trợ. Hãy tải file TeX mới.")
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    if session.status != "preview" or (session.expires_at and session.expires_at <= now):
        raise ValueError("Phiên import đã đóng hoặc hết hạn. Hãy tải lại file.")
    return session


def _string_list(payload, key):
    items = payload.get(key)
    if not isinstance(items, list) or not items or not all(isinstance(v, str) and v for v in items):
        raise ValueError("Hãy chọn đủ lớp, chương, bài và chủ đề cho file.")
    return sorted(set(items))


def normalize_scope(payload):
    if not isinstance(payload, dict):
        raise ValueError("Phạm vi file không hợp lệ.")
    grade = str(payload.get("grade", ""))
    chapters, lessons, topics = (_string_list(payload, key) for key in ("chapters", "lessons", "topics"))
    nodes = [n for n in catalog_options() if n["grade"] == grade]
    if not nodes or not set(chapters).issubset({n["chapter"] for n in nodes}):
        raise ValueError("Chương không thuộc lớp đã chọn hoặc danh mục đã ngừng sử dụng.")
    nodes = [n for n in nodes if n["chapter"] in chapters]
    if not set(lessons).issubset({f"{n['chapter']}:{n['section']}" for n in nodes}):
        raise ValueError("Bài không thuộc các chương đã chọn.")
    if {key.split(":")[0] for key in lessons} != set(chapters):
        raise ValueError("Mỗi chương được chọn cần có ít nhất một bài.")
    nodes = [n for n in nodes if f"{n['chapter']}:{n['section']}" in lessons]
    if not set(topics).issubset({n.get("topic_code") or UNASSIGNED_TOPIC for n in nodes}):
        raise ValueError("Chủ đề không thuộc các bài đã chọn.")
    nodes = [n for n in nodes if (n.get("topic_code") or UNASSIGNED_TOPIC) in topics]
    if {f"{n['chapter']}:{n['section']}" for n in nodes} != set(lessons):
        raise ValueError("Hãy chọn chủ đề phù hợp cho tất cả các bài đã chọn.")
    signature = hashlib.sha256(json.dumps(sorted(nodes, key=lambda n: n["id"]), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    normalized = dict(grade=grade, chapters=chapters, lessons=lessons, topics=topics, catalog_signature=signature)
    return normalized, nodes


def apply_scope(questions, scope, nodes):
    """Apply unambiguous defaults only; multi-lesson files are never flattened."""
    for question in questions:
        if question.get("saved_question_id"):
            continue
        for field, old_value in (question.get("scope_defaults") or {}).items():
            if question.get(field) == old_value:
                question[field] = ""
        question["scope_defaults"] = {}
        question["scope_errors"] = []
        candidates = list(nodes)
        for field, key in (("grade", "grade"), ("chapter", "chapter"), ("section", "section"),
                           ("question_category", "category")):
            value = str(question.get(field) or "").removeprefix("Lớp ")
            if value:
                candidates = [n for n in candidates if n[key] == value]
        if question.get("curriculum_node_id"):
            candidates = [n for n in candidates if str(n["id"]) == str(question["curriculum_node_id"])]
        if not candidates:
            question["scope_errors"] = ["Câu có lớp/chương/bài/dạng ngoài phạm vi file. Hãy sửa câu hoặc thay đổi phạm vi."]
            continue
        for field, key in (("grade", "grade"), ("chapter", "chapter"), ("section", "section"), ("topic", "topic_name")):
            choices = {n.get(key) for n in candidates}
            if not question.get(field) and len(choices) == 1:
                value = next(iter(choices))
                if value:
                    value = f"Lớp {value}" if field == "grade" else value
                    question[field] = value
                    question["scope_defaults"][field] = value
    return questions


def default_inferred_scope():
    """Build the canonical curriculum scope from the active Chapter 8 catalog."""
    nodes = [n for n in catalog_options() if n["grade"] == "9" and n["chapter"] == "8" and n["section"] == "i"]
    if not nodes:
        nodes = catalog_options()
    if not nodes:
        return dict(grade="9", chapters=["8"], lessons=["8:i"], topics=["thong_ke_xac_suat"], catalog_signature=""), []
    grade = nodes[0]["grade"]
    chapters = sorted(set(n["chapter"] for n in nodes))
    lessons = sorted(set(f"{n['chapter']}:{n['section']}" for n in nodes))
    topics = sorted(set(n.get("topic_code") or UNASSIGNED_TOPIC for n in nodes))
    signature = hashlib.sha256(json.dumps(sorted(nodes, key=lambda n: n["id"]), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    normalized = dict(
        grade=grade,
        chapters=chapters,
        lessons=lessons,
        topics=topics,
        catalog_signature=signature,
    )
    return normalized, nodes


def validate_session_scope(session, *, required=True):
    from services.bank_curriculum import is_probability_bank
    questions = session.get_parsed_questions()
    if not is_probability_bank(session.bank, questions):
        grades = sorted({str(q.get('grade') or '').strip() for q in questions} - {''})
        scope = dict(mode='general', grade=session.bank.grade if session.bank else (grades[0] if len(grades) == 1 else ''),
                     topic=session.bank.topic if session.bank else '', catalog_signature='general-v1')
        session.scope_data = json.dumps(scope, ensure_ascii=False)
        return scope, []
    scope = session.get_scope()
    if not scope:
        normalized, nodes = default_inferred_scope()
        session.scope_data = json.dumps(normalized, ensure_ascii=False)
        return normalized, nodes
    try:
        normalized, nodes = normalize_scope(scope)
    except Exception:
        normalized, nodes = default_inferred_scope()
        session.scope_data = json.dumps(normalized, ensure_ascii=False)
        return normalized, nodes
    if scope.get("catalog_signature") != normalized["catalog_signature"]:
        normalized, nodes = default_inferred_scope()
        session.scope_data = json.dumps(normalized, ensure_ascii=False)
        return normalized, nodes
    return normalized, nodes


def refresh_preview(session, scope=None, nodes=None):
    from services.question_validator import validate_questions
    if scope is None:
        scope, nodes = validate_session_scope(session, required=False)
    questions = session.get_parsed_questions()
    general = scope.get("mode") == "general"
    if general:
        from services.bank_curriculum import prepare_general_questions
        prepare_general_questions(questions, session.bank)
    elif scope:
        for question in questions:
            question.pop("curriculum_mode", None)
        apply_scope(questions, scope, nodes)
        # A suggestion carries its own content fingerprint and never allocates
        # an ID6 number.  It is recalculated after every scope/content change.
        from services.question_classification_service import apply_preview_classification
        apply_preview_classification(questions, scope, nodes)
    from services.latex_parser import normalize_question_latex
    for question in questions:
        if not question.get('saved_question_id'):
            normalize_question_latex(question)
    result = validate_questions(questions)
    from services.id6_metadata import (
        annotate_id6_conflicts,
        materialize_review_metadata,
        validate_id6_readiness,
    )
    annotate_id6_conflicts(result["questions"])
    # Reviewed curriculum labels are required; a source ID is optional.
    if nodes:
        validate_id6_readiness(result["questions"], nodes)
    # Populate only safe, source-derived review defaults so teachers can see
    # and edit the same metadata that confirmation will persist.  This does
    # not grant approval or change any existing bank row.
    if not general:
        materialize_review_metadata(result["questions"])
    # Confirmation can add stricter answer/scoring errors than the editable
    # draft validator. Preserve those visibly until the teacher edits the row,
    # at which point ``update_preview_question`` clears and recalculates them.
    for question in result["questions"]:
        pending = question.get("confirmation_errors") or []
        if pending and not question.get("saved_question_id"):
            errors = question.setdefault("errors", [])
            errors.extend(error for error in pending if error not in errors)
            question["status"] = "error"
    for status in ("valid", "warning", "error"):
        result["stats"][status] = sum(q["status"] == status for q in result["questions"])
    from services.import_duplicates import scan_duplicates
    session.duplicate_report = json.dumps(scan_duplicates(session, result['questions']), ensure_ascii=False)
    session.set_parsed_questions(result["questions"])
    for key in ("total", "valid", "warning", "error"):
        setattr(session, key + "_count", result["stats"][key])
    return session


def save_scope(session, payload):
    scope, nodes = normalize_scope(payload)
    session.scope_data = json.dumps(scope, ensure_ascii=False)
    refresh_preview(session, scope, nodes)
    db.session.commit()
    return scope
