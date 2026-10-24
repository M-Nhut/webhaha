"""Frozen class papers imported from unclassified TeX; no mastery inference."""
import copy
import json
import math
import re
from database import db
from models import Course, Exam, ExamQuestion, ExamAnswer, FormulaAsset, CurriculumNode
from services.latex_parser import normalize_question_latex
from services.question_policy import answer_issues
from services.practice_blueprint import auto_scoring_error

PURPOSE = 'standalone'


def authorized_course(course_id, actor):
    course = db.session.get(Course, course_id)
    if not course or actor.role not in ('teacher', 'admin') or (
            actor.role == 'teacher' and course.teacher_id != actor.id):
        raise PermissionError('Bạn không có quyền giao đề cho lớp này.')
    if not course.is_active:
        raise ValueError('Lớp đã ngừng hoạt động; hãy chọn lớp đang hoạt động.')
    return course


def editable_text(text, formulas):
    def source(match):
        asset = formulas.get(match.group(1), {})
        if asset.get('source_format') == 'LaTeXBlock':
            return match.group(0)  # Keep preamble and rendered figure identity.
        latex = asset.get('latex') or asset.get('source_text')
        return '$' + latex + '$' if latex else match.group(0)
    return re.sub(r'\[\[formula:([^\]]+)\]\]', source, text or '')


def reviewed_questions(questions, form):
    result = copy.deepcopy(questions)
    for i, question in enumerate(result):
        prefix = f'q{i}_'
        for field in ('question_text', 'context', 'explanation'):
            question[field] = form.get(prefix + field, question.get(field, '')).strip()
        points = float(form.get(prefix + 'weight', form.get(prefix + 'points', question.get('weight', question.get('points')) or 1)))
        if not math.isfinite(points) or points <= 0 or points > 100:
            raise ValueError(f'Câu {i+1}: điểm phải lớn hơn 0 và không quá 100.')
        question['weight'] = points
        question['report_category'] = form.get(prefix + 'report_category', question.get('report_category', '')).strip()[:200]
        question['report_chapter'] = form.get(prefix + 'report_chapter', question.get('report_chapter', '')).strip()[:200]
        question['report_code'] = form.get(prefix + 'report_code', question.get('report_code', '')).strip()
        question['report_confirmed'] = form.get(prefix + 'report_confirmed') == 'yes'
        question['difficulty_level'] = form.get(prefix + 'difficulty_level', question.get('difficulty_level', ''))
        if question['report_code'] and not CurriculumNode.query.filter_by(canonical_code=question['report_code'], is_active=True).first():
            raise ValueError(f'Câu {i+1}: nhãn kiến thức không còn hợp lệ.')
        if question['report_confirmed'] and question['report_code'] and not question['report_category']:
            question['report_category'] = CurriculumNode.query.filter_by(canonical_code=question['report_code']).one().category_name
        if question['report_confirmed'] and question['report_code']:
            node = CurriculumNode.query.filter_by(canonical_code=question['report_code']).one()
            question['report_chapter'] = f'Chương {node.chapter_code}: {node.chapter_name}'
        kind = question['question_type']
        items = question.get('statements' if kind == 'true_false' else 'options', [])
        if kind == 'short_answer':
            question['options'] = [{'text': form.get(prefix + 'answer', '').strip(), 'is_correct': True}]
            question.setdefault('learning_metadata', {}).setdefault('short_answer', {'mode': 'text', 'tolerance': '0'})
        else:
            for j, item in enumerate(items):
                item['text'] = form.get(prefix + f'option{j}', item.get('text', '')).strip()
                if kind == 'true_false':
                    value = form.get(prefix + f'truth{j}', '')
                    item['answer'] = (value == '1') if value in ('0', '1') else None
                else:
                    item['is_correct'] = form.get(prefix + 'correct') == str(j)
        normalize_question_latex(question)
        visible = ' '.join(str(question.get(field) or '') for field in ('question_text', 'context', 'explanation'))
        visible += ' '.join(str(item.get('text') or '') for item in question.get('options', []) + question.get('statements', []))
        question['formulas'] = {key: asset for key, asset in question.get('formulas', {}).items()
                                if '[[formula:' + key + ']]' in visible}
    return result


def review_errors(questions):
    errors = []
    if not questions:
        return ['File chưa có câu hỏi hợp lệ.']
    for i, question in enumerate(questions):
        issues, _ = answer_issues(question, require_answers=True)
        if not question.get('question_text', '').strip():
            issues.append('Thiếu nội dung câu hỏi.')
        if any(asset.get('conversion_status') in ('failed', 'pending')
               for asset in question.get('formulas', {}).values()):
            issues.append('Công thức hoặc hình vẽ chưa biên dịch được; sửa nguồn trước khi giao đề.')
        errors.extend(f'Câu {i+1}: {issue}' for issue in issues)
    return errors


def _persist_assets(question):
    remap = {}
    for key, data in question.get('formulas', {}).items():
        asset = FormulaAsset.query.filter_by(content_hash=data['content_hash']).first()
        if not asset:
            fields = ('content_hash', 'latex', 'mathml', 'source_text', 'source_preamble', 'source_format',
                      'parse_confidence', 'conversion_status', 'render_method', 'render_error', 'svg_cache_key')
            asset = FormulaAsset(**{field: data.get(field) for field in fields},
                                 verification_status=data.get('verification_status', 'verified'))
            db.session.add(asset)
            db.session.flush()
        remap[key] = str(asset.id)
    def resolve(text):
        for old, new in remap.items():
            text = (text or '').replace('[[formula:' + old + ']]', '[[formula:' + new + ']]')
        return text or ''
    return resolve


def save_paper(session, actor, form):
    """Caller serializes the transaction; drafts may be revised until publication."""
    course = authorized_course(int(form.get('course_id', 0)), actor)
    title = form.get('title', '').strip()
    duration = int(form.get('duration_minutes', 45))
    if not title or len(title) > 200 or not 1 <= duration <= 240:
        raise ValueError('Nhập tên đề (tối đa 200 ký tự) và thời gian từ 1 đến 240 phút.')
    questions = reviewed_questions(session.get_parsed_questions(), form)
    from services.assessment_scoring import allocate, KINDS
    budgets = {kind: form.get('budget_' + kind, '0') for kind in KINDS} if any('budget_' + kind in form for kind in KINDS) else None
    allocation = allocate(questions, budgets)
    publish = form.get('action') == 'publish'
    issues = review_errors(questions)
    if publish and (issues or form.get('reviewed') != 'yes'):
        raise ValueError('\n'.join(issues) or 'Hãy xác nhận đã đối chiếu nội dung và đáp án trước khi giao đề.')
    scope = session.get_scope()
    sources = {}
    if scope.get('source') == 'banks':
        from services.assessment_bank import question_pool
        sources = {q.id: q for q in question_pool(course, scope.get('bank_ids', []))}
        if any(q.get('bank_question_id') not in sources for q in questions):
            raise PermissionError('Nguồn câu hỏi đã thay đổi quyền sử dụng hoặc trạng thái duyệt.')
    exam = db.session.get(Exam, scope.get('exam_id')) if scope.get('exam_id') else None
    if exam:
        authorized_course(exam.course_id, actor)
        if exam.assessment_purpose != PURPOSE or exam.created_by != actor.id:
            raise PermissionError('Không có quyền sửa đề.')
        if exam.is_active or exam.submissions:
            raise ValueError('Đề đã giao hoặc có bài làm; không thể thay đổi nội dung.')
        exam.questions.clear()
        db.session.flush()
    else:
        exam = Exam(created_by=actor.id, course_id=course.id, title=title,
                    exam_type='exam', assessment_purpose=PURPOSE, is_active=False)
        db.session.add(exam)
        db.session.flush()
    exam.title, exam.course_id, exam.duration_minutes = title, course.id, duration
    exam.shuffle_questions = exam.shuffle_answers = False
    exam.total_questions = len(questions)
    exam.adaptive_metadata = json.dumps({'import_session_id': session.id, 'source_filename': session.filename,
                                         'scoring': 'ten_point_tf_proportional_v1', 'section_points': allocation,
                                         'mastery_update': False}, ensure_ascii=False)
    for i, payload in enumerate(questions):
        resolve = _persist_assets(payload)
        kind = payload['question_type']
        confirmed = bool(payload.get('report_confirmed'))
        metadata = copy.deepcopy(payload.get('learning_metadata') or {})
        metadata['reporting'] = {'confirmed': confirmed, 'category': payload.get('report_category', ''),
                                 'chapter': payload.get('report_chapter', '') if confirmed else '',
                                 'source': scope.get('source', 'latex')}
        if not confirmed:
            metadata.pop('statements', None)
        question = ExamQuestion(exam=exam, order_index=i, question_type=kind,
            question_text=resolve(payload.get('question_text')), context=resolve(payload.get('context')),
            explanation=resolve(payload.get('explanation')), points=payload['points'],
            image_url=payload.get('image_url'), bank_question_id=payload.get('bank_question_id'),
            curriculum_code=payload.get('report_code') if confirmed else None,
            topic_snapshot=payload.get('report_category') if confirmed else None,
            difficulty_level=payload.get('difficulty_level') if confirmed else None,
            learning_metadata=json.dumps(metadata, ensure_ascii=False))
        db.session.add(question)
        items = payload.get('statements' if kind == 'true_false' else 'options', [])
        for item in items:
            question.answers.append(ExamAnswer(answer_text=resolve(item.get('text')), is_correct=(item.get('answer') if kind == 'true_false' else bool(item.get('is_correct')))))
    db.session.flush()
    from services.personalization_evidence import refresh_question_snapshot
    for question in exam.questions:
        refresh_question_snapshot(question)
    if publish:
        errors = [auto_scoring_error(question) for question in exam.questions]
        if any(errors):
            raise ValueError(next(error for error in errors if error))
    exam.is_active = publish
    scope['exam_id'] = exam.id
    session.scope_data = json.dumps(scope, ensure_ascii=False)
    session.set_parsed_questions(questions)
    session.status = 'confirmed' if publish else 'preview'
    db.session.commit()
    return exam
