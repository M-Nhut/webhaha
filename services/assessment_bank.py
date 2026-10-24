"""Authorized bank selection produces a reviewable, frozen class-paper draft."""
import json
import random
import re
from database import db
from models import FormulaAsset, ImportSession
from services.bank_curriculum import bank_readiness_error, category_name
from services.source_resolver import resolve_class_questions


def formula_assets(questions):
    text = json.dumps(questions, ensure_ascii=False)
    assets = {}
    for key in set(re.findall(r'\[\[formula:([^\]]+)\]\]', text)):
        asset = db.session.get(FormulaAsset, key)
        if asset:
            assets[key] = dict(asset.to_api_dict(), content_hash=asset.content_hash)
    return assets


def question_pool(course, bank_ids):
    resolved = resolve_class_questions(course, bank_ids, require_grade=False)
    if not resolved['valid']:
        raise PermissionError('Ngân hàng không thuộc phạm vi sử dụng của lớp.')
    return [q for q in resolved['questions'] if q.question_type in ('single', 'true_false', 'truefalse', 'short_answer')
            and not bank_readiness_error(q)]


def create_bank_draft(actor, course, bank_ids, *, selected_ids=(), quantity=None, counts=None, budgets=None):
    from services.standalone_assessment import authorized_course
    authorized_course(course.id, actor)
    pool = question_pool(course, bank_ids)
    if counts is not None:
        from services.assessment_scoring import KINDS, kind_of
        requested = {kind: int(counts.get(kind, 0)) for kind in KINDS}
        if any(n < 0 for n in requested.values()) or not 1 <= sum(requested.values()) <= 100:
            raise ValueError('Tổng số câu phải từ 1 đến 100; số câu mỗi phần không âm.')
        selected = []
        for kind, count in requested.items():
            candidates = [q for q in pool if kind_of(q.question_type) == kind]
            if count > len(candidates):
                raise ValueError(f'{KINDS[kind]}: cần {count} câu, ngân hàng có {len(candidates)} câu đủ điều kiện. Giảm số câu hoặc bổ sung ngân hàng.')
            selected.extend(random.SystemRandom().sample(candidates, count))
    elif quantity is not None:
        if not 1 <= quantity <= 100 or quantity > len(pool):
            raise ValueError(f'Có {len(pool)} câu đủ điều kiện. Chọn từ 1 đến 100 câu và không vượt số câu hiện có.')
        selected = random.SystemRandom().sample(pool, quantity)
    else:
        ids = list(dict.fromkeys(int(value) for value in selected_ids))
        by_id = {q.id: q for q in pool}
        if not ids or len(ids) > 100:
            raise ValueError('Chọn từ 1 đến 100 câu để tạo đề.')
        if any(value not in by_id for value in ids):
            raise PermissionError('Một câu đã thay đổi quyền truy cập hoặc chưa đủ điều kiện.')
        selected = [by_id[value] for value in ids]
    questions = []
    for source in selected:
        payload = source.to_dict()
        payload['bank_question_id'] = source.id
        payload['options'] = [{'text': item.option_text, 'is_correct': item.is_correct} for item in source.options]
        payload['report_category'] = source.curriculum_node.category_name if source.curriculum_node else category_name(source)
        payload['report_code'] = source.curriculum_node.canonical_code if source.curriculum_node else ''
        payload['report_confirmed'] = True
        payload['formulas'] = formula_assets([payload])
        questions.append(payload)
    from services.assessment_scoring import allocate
    allocation = allocate(questions, budgets)
    session = ImportSession(user_id=actor.id, filename='Đề từ ngân hàng', file_type='tex',
                            status='preview', total_count=len(questions), expires_at=None,
                            scope_data=json.dumps({'document_kind': 'assessment', 'source': 'banks',
                                                   'section_points': allocation,
                                                   'bank_ids': [int(value) for value in bank_ids], 'course_id': course.id}))
    session.set_parsed_questions(questions)
    db.session.add(session)
    db.session.commit()
    return session
