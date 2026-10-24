"""Deterministic, explainable review suggestion for Math 9 Chapter 8 lesson i.

It deliberately makes no network or model call.  The result is a suggestion
bound to a content fingerprint; unclear questions remain ``needs_review``.
"""
import hashlib
import json
import re
import unicodedata

from services.curriculum_data import CHAPTER8_VERSION

CLASSIFIER_VERSION = 'math9-c8-i-rules-v1'


def _plain(value):
    value = unicodedata.normalize('NFC', str(value or '')).lower()
    value = re.sub(r'<[^>]+>', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def _text(question):
    rows = question.get('statements') or question.get('options') or []
    return _plain(' '.join([question.get('question_text', ''), question.get('context', ''),
                            question.get('explanation', ''),
                            *[row.get('text') or row.get('option_text') or '' for row in rows]]))


def content_fingerprint(question):
    def row(value):
        return dict(text=value.get('text') or value.get('option_text') or '',
                    is_correct=value.get('is_correct'), answer=value.get('answer'))
    payload = dict(question_text=question.get('question_text'), context=question.get('context'),
                   image_url=question.get('image_url'), formulas=question.get('formulas'),
                   options=[row(value) for value in question.get('options') or []],
                   statements=[row(value) for value in question.get('statements') or []],
                   question_type=question.get('question_type'), explanation=question.get('explanation'))
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _has(text, *phrases):
    return [phrase for phrase in phrases if phrase in text]


def _category(text):
    """Return a retained combined-lesson code or no suggestion.

    The result is only a teacher-review suggestion.  It never becomes source
    ID metadata automatically.
    """
    probability = _has(text, 'không gian mẫu', 'xác suất', 'đồng xu', 'xúc sắc', 'xúc xắc',
                       'vòng quay', 'rút thẻ', 'rút một', 'chọn ngẫu nhiên', 'phép thử')
    if probability:
        if 'không gian mẫu' in text and 'xác suất' not in text:
            return '9C8-i-1', probability, .94
        if _has(text, 'số phần tử', 'bao nhiêu phần tử', 'có bao nhiêu kết quả') and 'xác suất' not in text:
            return '9C8-i-2', probability, .91
        games = [('đồng xu', 3), ('xúc sắc', 4), ('xúc xắc', 4), ('vòng quay', 5),
                 ('rút thẻ', 6), ('rút một', 6), ('viết số tự nhiên', 7), ('chọn ngẫu nhiên', 8)]
        hits = [number for phrase, number in games if phrase in text]
        if len(set(hits)) == 1 and ('xác suất' in text or probability):
            return f'9C8-i-{hits[0]}', probability, .92
        return None, probability, 0

    return None, [], 0


def _difficulty(text, category):
    """Difficulty uses required work, never length or numbers alone."""
    hard = _has(text, 'đồng thời', 'thỏa mãn tất cả', 'tìm tất cả', 'còn lại', 'biết rằng')
    if len(hard) >= 2:
        return 'van_dung_cao', hard, .84
    multi = _has(text, 'không gian mẫu', 'biến cố', 'ít nhất', 'nhiều hơn', 'điều kiện')
    if category and category.startswith('9C8-i-') and 'xác suất' in text and len(multi) >= 1:
        return 'van_dung', multi, .86
    direct = _has(text, 'không gian mẫu', 'số phần tử', 'có bao nhiêu kết quả')
    if direct:
        return 'nhan_biet', direct, .80
    return None, [], 0


def classify(question, scope=None):
    """Classify one preview row; returned data is safe to store in JSON."""
    text = _text(question)
    fingerprint = content_fingerprint(question)
    base = dict(version=CLASSIFIER_VERSION, catalog_version=CHAPTER8_VERSION,
                content_fingerprint=fingerprint, status='needs_review', primary_code=None,
                difficulty_level=None, statement_levels=[], rationale=[], confidence=0)
    grade = str(question.get('grade') or (scope or {}).get('grade') or '').replace('Lớp ', '')
    chapters = set((scope or {}).get('chapters') or [])
    section = str(question.get('section') or '').strip()
    lessons = set((scope or {}).get('lessons') or [])
    if (grade and grade != '9') or chapters and chapters != {'8'} or section and section.lower() != 'i' or lessons and not any(item == 'i' or item.endswith(':i') for item in lessons):
        base['rationale'] = ['Ngoài phạm vi Toán 9 Chương 8 bài kết hợp i; không tự phân loại.']
        return base
    if question.get('has_image') and not question.get('image_url'):
        base['rationale'] = ['Thiếu hình/bảng cần đọc để phân loại.']
        return base
    code, category_evidence, category_confidence = _category(text)
    if not code:
        base['rationale'] = ['Không xác định chắc chắn yêu cầu toán học hoặc dạng chính.']
        return base
    allowed = {f"9C{node['chapter']}-{node['section']}-{node['category']}" for node in (scope or {}).get('nodes', [])}
    if allowed and code not in allowed:
        base['rationale'] = ['Dạng gợi ý nằm ngoài phạm vi bài/chủ đề đã chọn.']
        return base
    level, level_evidence, level_confidence = _difficulty(text, code)
    if question.get('question_type') == 'true_false':
        # No fabricated per-statement levels: only attach a level where its
        # own wording has enough evidence.  The whole question uses the max.
        statement_levels = []
        for row in question.get('statements') or []:
            one_level, one_evidence, one_confidence = _difficulty(_plain(row.get('text')), code)
            statement_levels.append(dict(level=one_level, rationale=one_evidence, confidence=one_confidence))
        known = [row['level'] for row in statement_levels if row['level']]
        order = ('nhan_biet', 'thong_hieu', 'van_dung', 'van_dung_cao')
        if len(known) == 4:
            level = max(known, key=order.index)
            level_evidence = ['Mức toàn câu là mức cao nhất của bốn mệnh đề.']
        else:
            level = None
        base['statement_levels'] = statement_levels
    if not level:
        base.update(primary_code=code, confidence=category_confidence,
                    rationale=category_evidence + ['Chưa đủ căn cứ để gán mức độ.'])
        return base
    confidence = min(category_confidence, level_confidence)
    base.update(status='suggested' if confidence >= .80 else 'needs_review', primary_code=code,
                difficulty_level=level, rationale=category_evidence + level_evidence,
                confidence=round(confidence, 2))
    return base


def apply_preview_classification(questions, scope, nodes):
    """Attach suggestions without allocating ID6 or overriding teacher/ID labels."""
    node_by_code = {
        f"{node['grade']}C{node['chapter']}-{node['section']}-{node['category']}": node
        for node in nodes
    }
    for question in questions:
        old = question.get('classification') or {}
        result = classify(question, {**(scope or {}), 'nodes': nodes})
        if old.get('locked'):
            result = {**old, 'content_fingerprint': content_fingerprint(question), 'status': 'teacher_locked'}
        elif question.get('source_id'):
            from services.id6_service import parse_id6_for_record
            if parse_id6_for_record(
                question.get('source_id'),
                question_type=question.get('question_type'),
            ):
                result.update(status='source_labeled', rationale=['Giữ nhãn ID6 từ metadata file; không tự đổi phân loại.'])
        # Suggestions remain visible for teacher approval only.  Do not copy
        # their node/difficulty into question fields and do not synthesize IDs.
        question['classification'] = result
    return questions
