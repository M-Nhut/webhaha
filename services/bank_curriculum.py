"""Bank-level curriculum policy; research practice keeps its own strict blueprint."""
import re
import json
import hashlib
from services.id6_service import catalog_options
from services.question_normalizer import remove_diacritics


def is_probability_bank(bank, questions=()):
    if not bank:
        return any(str(q.get('source_id', '')).startswith('9C8') for q in questions)
    grade = re.search(r'\d+', bank.grade or '')
    if grade and grade.group() != '9':
        return False
    topic = remove_diacritics(bank.topic or '').lower().strip()
    if topic:
        return 'xac suat' in topic or 'khong gian mau' in topic
    name = remove_diacritics(bank.name or '').lower()
    return ('xac suat' in name or any(q.curriculum_node_id for q in bank.questions) or any(
        (q.get('curriculum_node_id') or str(q.get('source_id', '')).startswith('9C8'))
        if isinstance(q, dict) else q.curriculum_node_id
        for q in questions))


def catalog_for_bank(bank, questions):
    if is_probability_bank(bank, questions):
        return catalog_options()
    categories = sorted({category_name(q) for q in questions})
    return [dict(id='category:' + name, category='', category_name=name) for name in categories]


def general_metadata(question):
    from services.practice_blueprint import numeric_value, validate_metadata
    raw = question.get('learning_metadata') or {}
    if not isinstance(raw, dict):
        raise ValueError('Thông tin chấm đáp án không hợp lệ.')
    result = {key: value for key, value in raw.items() if key == 'short_answer'}
    if question.get('question_type') == 'short_answer' and not result:
        options = question.get('options') or []
        answer = (options[0].get('text') or options[0].get('option_text') or '') if options else question.get('sample_answer', '')
        try:
            numeric_value(answer)
            mode = 'numeric'
        except (ValueError, TypeError):
            mode = 'text'
        result['short_answer'] = dict(mode=mode, tolerance='0')
    return validate_metadata(result)


def bank_readiness_error(question, *, research=False):
    from services.practice_blueprint import readiness_error, auto_scoring_error, LEVELS
    if research:
        return readiness_error(question)
    if question.classification_status != 'teacher_confirmed':
        return 'Nội dung chưa được giáo viên duyệt.'
    if question.difficulty_level not in LEVELS:
        return 'Chọn mức độ nhận thức hợp lệ.'
    return auto_scoring_error(question)


def prepare_general_questions(questions, bank=None):
    for question in questions:
        if question.get('saved_question_id'):
            continue
        question['curriculum_mode'] = 'general'
        question['curriculum_node_id'] = None
        question['scope_errors'] = []
        question['scope_defaults'] = {}
        question['classification'] = {'status': 'needs_review', 'reason': 'Nhãn từ tài liệu; giáo viên kiểm tra trước khi lưu.'}
        if bank:
            question['grade'] = bank.grade or question.get('grade', '')
            question['topic'] = bank.topic or question.get('topic', '')
        category = str(question.get('question_category') or '').strip()
        question['question_category'] = category[:100] or 'Chưa phân loại'
        question['learning_metadata'] = general_metadata(question)
    return questions


def category_name(question):
    labels = json.loads(question.classification_data or '{}')
    return labels.get('category_name') or question.question_category or 'Chưa phân loại'


def set_general_category(question, name):
    name = str(name or 'Chưa phân loại').strip()[:100] or 'Chưa phân loại'
    labels = json.loads(question.classification_data or '{}')
    labels.update(curriculum_mode='general', category_name=name)
    question.classification_data = json.dumps(labels, ensure_ascii=False)
    # Stable compact key fits the existing schema; display labels remain editable.
    question.question_category = 'g_' + hashlib.sha256(name.casefold().encode()).hexdigest()[:18]
    question.curriculum_node_id = None
