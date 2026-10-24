"""Read ID6 annotations around an existing import preview without parsing question content.

The adapter enriches metadata after document extraction and uses the shared
preview validation/edit contract. It does not rewrite mathematical content.
"""
import re
from pathlib import Path

from database import db
from models import BankQuestion, CurriculumNode
from services.id6_service import (
    TAG_PATTERN,
    ID_PATTERN,
    LEVEL_CODES,
    TYPE_CODES,
    is_retained_lesson_scope,
    parse_id6,
    parse_id6_for_record,
)
from services.question_policy import (
    canonical_type,
)
from services.question_validator import validate_questions


def _source_annotations(session, count):
    path = Path(session.file_path or '')
    if not path.is_file():
        return []
    text = ''
    if session.file_type in ('tex', 'latex'):
        text = path.read_text(encoding='utf-8')
        from services.latex_parser import _strip_latex_comments
        cleaned_text = _strip_latex_comments(text)
        blocks = re.findall(r'\\begin\{(bt|ex|question|bai)\}(.*?)\\end\{\1\}', cleaned_text, re.S | re.I)
        if len(blocks) == count:
            return [_metadata_from_block(body) for _, body in blocks]
    else:
        return []
    # Use question boundaries so a partially tagged file cannot shift annotations.
    blocks = re.split(r'(?:^|\n)\s*(?:Câu|Bài|Question)\s+\d+\s*[.:)]', text, flags=re.I)[1:]
    if len(blocks) == count:
        return [_metadata_from_block(body) for body in blocks]
    return []


def _metadata_from_block(text, **kwargs):
    """Parse one block and preserve an explicit multi-prefix conflict."""
    values = []
    for match in TAG_PATTERN.finditer(text or ''):
        metadata = parse_id6(match.group())
        if metadata:
            values.append(metadata)
    distinct = {item['source_id'] for item in values}
    if len(distinct) > 1:
        return {"id6_metadata_conflict": "Một câu có nhiều tiền tố ID6 khác nhau; cần giữ lại đúng một tiền tố trong file nguồn."}
    return values[0] if values else None


def _apply_metadata(question, metadata):
    incoming_type = canonical_type(metadata.get('question_type'))
    current_type = question.get('question_type')
    if current_type and canonical_type(current_type) != incoming_type:
        question['id6_metadata_conflict'] = (
            f"Tiền tố ID6 chỉ rõ loại {incoming_type} nhưng parser nhận {canonical_type(current_type)}."
        )
        question['source_id'] = metadata.get('source_id', question.get('source_id', ''))
        question['id6_prefix'] = metadata.get('id6_prefix', '')
        return False
    question.update({key: value for key, value in metadata.items() if key != 'id6_sequence'})
    question['question_type'] = incoming_type
    scope = CurriculumNode.make_canonical_code(metadata['grade'].split()[-1], metadata['chapter'], metadata['section'], metadata['question_category'])
    node = CurriculumNode.query.filter_by(canonical_code=scope, is_active=True).first()
    question['curriculum_node_id'] = node.id if node else None
    if question['question_type'] == 'true_false' and not question.get('statements') and question.get('options'):
        question['statements'] = [dict(id=chr(97+i), text=re.sub(r'^[a-d][).:]\s*', '', option.get('text', ''), flags=re.I), answer=option.get('is_correct'))
                                  for i, option in enumerate(question['options'])]
        question['options'] = []


def _clear_unsupported_id(question, source_id):
    """Report a legacy label without rewriting the imported source string."""
    if not source_id:
        return False
    match = TAG_PATTERN.fullmatch(source_id.strip()) or ID_PATTERN.fullmatch(source_id.strip())
    if not match:
        return False
    groups = match.groupdict() if hasattr(match, 'groupdict') else None
    if groups:
        grade, chapter = groups.get('grade'), groups.get('chapter')
        lesson, category = groups.get('section'), groups.get('category')
    else:
        grade, chapter = match.group(1), match.group(2)
        lesson, category = match.group(4), match.group(5)
    if is_retained_lesson_scope(grade, chapter, lesson, category):
        return False
    question.setdefault('warnings', []).append(
        'Mã ID nguồn không thuộc Chương 8 bài kết hợp i; giữ nguyên để đối chiếu và yêu cầu nhập lại file đúng phạm vi.'
    )
    return False


def enrich_preview(session, *, commit=True):
    if session.status != 'preview':
        return
    questions = session.get_parsed_questions()
    from services.bank_curriculum import is_probability_bank
    if not is_probability_bank(session.bank, questions):
        return
    if not questions:
        return
    annotations = []
    # Only reopen the source when metadata is absent; teacher edits take precedence.
    if any(not parse_id6_for_record(q.get('source_id')) for q in questions):
        try:
            annotations = _source_annotations(session, len(questions))
        except (OSError, ValueError):
            annotations = []
    changed = False
    for index, question in enumerate(questions):
        if question.get('saved_question_id') or question.get('teacher_labels_selected'):
            # Already saved questions have an authoritative source_id.
            continue
        metadata = parse_id6_for_record(question.get('source_id'))
        if not metadata and _clear_unsupported_id(question, question.get('source_id')):
            changed = True
        if not metadata:
            match = TAG_PATTERN.search(question.get('question_text', ''))
            if not match and annotations:
                annotation = annotations[index]
                if isinstance(annotation, dict):
                    metadata = annotation
                else:
                    match = annotation
            if not metadata and match:
                metadata = parse_id6(match.group())
            if not metadata and match and _clear_unsupported_id(question, match.group()):
                changed = True
        if metadata and metadata.get('id6_metadata_conflict'):
            question['id6_metadata_conflict'] = metadata['id6_metadata_conflict']
            changed = True
        elif metadata:
            _apply_metadata(question, metadata)
            changed = True
    if changed:
        validate_questions(questions)
        annotate_id6_conflicts(questions)
        session.set_parsed_questions(questions)
        session.total_count = len(questions)
        session.valid_count = sum(q['status'] == 'valid' for q in questions)
        session.warning_count = sum(q['status'] == 'warning' for q in questions)
        session.error_count = sum(q['status'] == 'error' for q in questions)
        if commit:
            db.session.commit()


def annotate_id6_conflicts(questions):
    seen = set()
    for question in questions:
        metadata = parse_id6_for_record(question.get('source_id'))
        if not metadata:
            continue
        scope = CurriculumNode.make_canonical_code(metadata['grade'].split()[-1], metadata['chapter'], metadata['section'], metadata['question_category'])
        key = (scope, metadata['id6_sequence'])
        if metadata['id6_sequence'] is None:
            # Prefixes intentionally have no suffix until save; repeated
            # prefixes are valid and receive distinct atomic numbers later.
            continue
        if key in seen or BankQuestion.query.filter_by(id6_scope=scope, id6_sequence=key[1]).first():
            question.setdefault('warnings', []).append('Số thứ tự ID6 nguồn đã tồn tại; hệ thống sẽ cấp số mới khi lưu và giữ nguyên tiền tố phân loại.')
            if question.get('status') == 'valid':
                question['status'] = 'warning'
        seen.add(key)


def validate_id6_readiness(questions, nodes=None):
    """Compatibility entry point: explicit teacher labels replace mandatory ID6."""
    allowed = {n.get('id') for n in (nodes or [])}
    for question in questions:
        if question.get('saved_question_id'):
            continue
        node_id = question.get('curriculum_node_id')
        try:
            node = db.session.get(CurriculumNode, int(node_id)) if node_id else None
        except (TypeError, ValueError):
            node = None
        if (not node or not node.is_active
                or not is_retained_lesson_scope(node.grade, node.chapter_code, node.lesson_code, node.category_code)
                or (allowed and node.id not in allowed)):
            question.setdefault('errors', []).append('Hãy chọn dạng kiến thức trong phạm vi nhập trước khi xác nhận.')
            question['status'] = 'error'
    return questions


def review_metadata_for_question(question):
    """Use explicit reviewed labels, with legacy file tags as optional defaults.

    Statement defaults inherit the parent labels for teacher review; they are
    never inferred as separate skills from the question wording.
    """
    parsed = parse_id6_for_record(question.get("source_id"))
    node_id = question.get("curriculum_node_id")
    if node_id:
        try:
            node = db.session.get(CurriculumNode, int(node_id))
        except (TypeError, ValueError):
            node = None
        if node and node.is_active:
            parsed = dict(grade=node.grade, chapter=node.chapter_code, section=node.lesson_code,
                          question_category=node.category_code, question_type=question.get("question_type"),
                          difficulty_level=question.get("difficulty_level"))
    if not parsed:
        return None, "Hãy chọn dạng kiến thức trước khi xác nhận."


    raw = question.get("learning_metadata")
    if raw in (None, ""):
        metadata = {}
    elif isinstance(raw, dict):
        metadata = dict(raw)
    else:
        return None, "Metadata sẵn sàng phải là một đối tượng hợp lệ."

    question_type = canonical_type(question.get("question_type") or parsed["question_type"])
    scope = CurriculumNode.make_canonical_code(
        parsed["grade"].split()[-1], parsed["chapter"], parsed["section"],
        parsed["question_category"],
    )
    if question_type == "short_answer" and "short_answer" not in metadata:
        options = question.get("options") or []
        ans_text = ""
        if options and isinstance(options[0], dict):
            ans_text = options[0].get("text") or options[0].get("option_text") or ""
        elif question.get("sample_answer"):
            ans_text = str(question.get("sample_answer"))
        ans_text = str(ans_text).strip()

        is_numeric = False
        try:
            float(ans_text.replace(',', '.'))
            is_numeric = True
        except ValueError:
            if re.match(r'^[+-]?\d+\s*/\s*\d+$', ans_text):
                is_numeric = True
            elif re.match(r'^[+-]?\\(?:dfrac|frac)\{\d+\}\{\d+\}$', ans_text):
                is_numeric = True

        mode = "numeric" if is_numeric else "text"
        metadata["short_answer"] = {"mode": mode, "tolerance": "0"}
    elif question_type == "true_false" and "statements" not in metadata:
        metadata["statements"] = [
            {"curriculum_code": scope, "cognitive_level": parsed["difficulty_level"]}
            for _ in range(4)
        ]

    try:
        from services.practice_blueprint import validate_metadata
        return validate_metadata(metadata), None
    except ValueError as exc:
        return None, str(exc)


def materialize_review_metadata(questions):
    """Expose safe inherited review metadata in preview without approving it."""
    changed = False
    for question in questions:
        if question.get("saved_question_id"):
            continue
        metadata, error = review_metadata_for_question(question)
        if error:
            errors = question.setdefault("errors", [])
            if error not in errors:
                errors.append(error)
                changed = True
            question["status"] = "error"
            continue
        if metadata is None or question.get("learning_metadata") == metadata:
            continue
        question["learning_metadata"] = metadata
        changed = True
    return changed


def validate_teacher_confirmation(questions):
    """Fail closed for rows that cannot become teacher-confirmed at save time.

    This runs at the import boundary, after the usual preview validation.  It
    marks only unsaved rows as errors so an otherwise valid batch can still be
    partially imported.  Old bank questions are deliberately untouched.
    """
    from services.question_policy import require_valid_answers

    for question in questions:
        if question.get("saved_question_id"):
            continue
        errors = []
        try:
            require_valid_answers(question)
        except ValueError as exc:
            errors.append(str(exc))

        validate_id6_readiness([question])
        errors.extend(question.get("errors", []))

        metadata, metadata_error = review_metadata_for_question(question)
        if metadata_error:
            errors.append(metadata_error)
        elif metadata is not None:
            question["learning_metadata"] = metadata

        if errors:
            existing = question.setdefault("errors", [])
            existing.extend(error for error in errors if error not in existing)
            question["confirmation_errors"] = list(errors)
            question["status"] = "error"
        else:
            question.pop("confirmation_errors", None)
    return questions


def prepare_preview_edit(question):
    """Validate a preview edit without generating or rewriting an ID prefix."""
    if question.get('curriculum_mode') == 'general':
        question['curriculum_node_id'] = None
        return
    node_id = question.get('curriculum_node_id')
    if node_id:
        try:
            node = db.session.get(CurriculumNode, int(node_id))
        except (TypeError, ValueError):
            node = None
        if (not node or not node.is_active
                or not is_retained_lesson_scope(node.grade, node.chapter_code,
                                                 node.lesson_code, node.category_code)):
            raise ValueError('Dạng bài không hợp lệ hoặc đã ngừng sử dụng.')
        question.update({
                'grade': f'Lớp {node.grade}', 'chapter': node.chapter_code,
                'section': node.lesson_code, 'question_category': node.category_code,
                'topic': node.topic_name or '', 'curriculum_node_id': node.id,
            })
        question['teacher_labels_selected'] = True
