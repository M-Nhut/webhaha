"""V2 acceptance tests: isolated database, no AI calls or real learner data."""
import datetime as dt
import json
import os
from collections import Counter
from types import SimpleNamespace

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ.pop('POSTGRES_URL', None)
import config
config.load_local_environment = lambda *args, **kwargs: None
from app import app
from database import db
from models import (BankQuestion, BankQuestionOption, Course, CurriculumNode,
                    Exam, ExamQuestion, ExamSubmission, QuestionBank, User)
from adaptive_engine import AdaptiveEngine
from services import aptga, practice_blueprint as bp
from services.practice_selector import skill_targets
from services.practice_recovery import select_resilient
from services.id6_service import select_curriculum
from services.id6_metadata import prepare_preview_edit, validate_teacher_confirmation
import pytest
from tempfile import TemporaryDirectory
from unittest.mock import patch


@pytest.fixture
def bank():
    with TemporaryDirectory(prefix='fnweb-test-import-') as upload_dir, patch('services.import_service.UPLOAD_TEMP_DIR', upload_dir), app.app_context():
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        db.drop_all()
        db.create_all()
        teacher = User(username='v2t', user_code='v2t', fullname='Giáo viên', role='teacher')
        student = User(username='v2s', user_code='v2s', fullname='Học sinh', role='student')
        db.session.add_all([teacher, student])
        db.session.flush()
        course = Course(course_name='Xác suất 9', subject='Toán', teacher_id=teacher.id)
        bank = QuestionBank(name='Nguồn kiểm thử', subject='Toán', grade='9', created_by=teacher.id)
        db.session.add_all([course, bank])
        db.session.flush()
        for i, skill in enumerate(bp.SKILLS, 1):
            node = CurriculumNode(grade='9', chapter_code='8', chapter_name='Xác suất',
                lesson_code='i', lesson_name='Không gian mẫu và xác suất', category_code=str(i),
                category_name=f'Dạng {i}', canonical_code=skill, is_active=True)
            db.session.add(node)
            db.session.flush()
            for level in bp.LEVELS:
                for kind in bp.TYPE_QUOTAS:
                    metadata = ({'statements':[{'curriculum_code':skill,'cognitive_level':level}]*4}
                        if kind=='true_false' else {'short_answer':{'mode':'numeric','tolerance':'0'}}
                        if kind=='short_answer' else {})
                    q = BankQuestion(bank_id=bank.id, created_by=teacher.id,
                        question_text=f'{skill} {level} {kind}', question_type=kind,
                        difficulty_level=level, curriculum_node_id=node.id, chapter='8', section='i',
                        grade='9', classification_status='teacher_confirmed', learning_metadata=json.dumps(metadata))
                    db.session.add(q)
                    db.session.flush()
                    for j in range(1 if kind=='short_answer' else 4):
                        db.session.add(BankQuestionOption(question_id=q.id, option_text='0.5' if kind=='short_answer' else str(j),
                            is_correct=j==0, order_index=j))
        db.session.commit()
        yield SimpleNamespace(bank=bank, teacher=teacher, student=student, course=course)
        db.session.remove()
        db.drop_all()


def choose(fixture):
    return AdaptiveEngine.select_questions(fixture.student.id, 'Toán', [fixture.bank.id], 22, {'blueprint':bp.VERSION})


def test_no_id_required_and_deterministic_full_paper(bank):
    result = choose(bank)
    assert result['selected_count'] == 22
    assert result['aptga']['actual_types'] == bp.TYPE_QUOTAS
    assert len(result['aptga']['actual_skills']) == 8
    assert all(q.source_id is None for q in result['questions'])
    assert [q.id for q in result['questions']] == [q.id for q in choose(bank)['questions']]


def test_exhausted_recent_bank_recovers_without_duplicate_content(bank):
    exam = Exam(title='Lượt trước', course_id=bank.course.id, created_by=bank.teacher.id)
    db.session.add(exam)
    db.session.flush()
    for q in bank.bank.questions:
        db.session.add(ExamQuestion(exam_id=exam.id, bank_question_id=q.id, question_text=q.question_text,
            question_type=q.question_type, points=1, source_content_hash=q.content_hash))
    db.session.add(ExamSubmission(exam_id=exam.id, student_id=bank.student.id,
        submitted_at=dt.datetime.utcnow(), status='submitted'))
    db.session.commit()
    result = choose(bank)
    assert result['selected_count'] == 22
    assert result['aptga']['repeated_count'] == 22
    assert result['aptga']['immediate_repeat_count'] == 22
    assert result['aptga']['recovery_stage'] == 'immediate_review'
    assert len({q.id for q in result['questions']}) == 22
    assert result['aptga']['actual_types'] == bp.TYPE_QUOTAS


def test_unreviewed_and_invalid_answers_never_recovered(bank):
    for q in bank.bank.questions:
        if q.question_type == 'true_false':
            q.classification_status = 'suggested'
    db.session.commit()
    result = choose(bank)
    assert result['selected_count'] == 0
    assert result['aptga']['rejected']


def test_teacher_can_reclassify_legacy_id_without_rewriting_source(bank):
    q = bank.bank.questions[0]
    q.source_id = '9C8Ni-1T.999'
    db.session.commit()
    node = CurriculumNode.query.filter_by(canonical_code=bp.SKILLS[1]).one()
    select_curriculum(q, node.id)
    q.difficulty_level = 'thong_hieu'
    db.session.commit()
    assert q.source_id == '9C8Ni-1T.999'
    assert q.curriculum_node_id == node.id
    assert bp.readiness_error(q) is None


def test_import_confirmation_without_id_has_reviewed_metadata(bank):
    node = CurriculumNode.query.first()
    q = dict(question_text='Tính xác suất', question_type='short_answer', difficulty_level='nhan_biet',
             curriculum_node_id=node.id, options=[dict(text='0.5', is_correct=True)])
    prepare_preview_edit(q)
    validate_teacher_confirmation([q])
    assert not q.get('errors')
    assert q['learning_metadata']['short_answer']['mode'] == 'numeric'
    assert not q.get('source_id')


def test_import_saves_reviewed_question_without_source_code(bank):
    from models import ImportSession
    from services.import_scope import refresh_preview
    from services.import_service import ImportService
    node = CurriculumNode.query.first()
    q = dict(question_text='Một hộp chứa 3 thẻ đỏ và 7 thẻ xanh. Xác suất chọn thẻ đỏ?',
        question_type='short_answer', difficulty_level='nhan_biet',curriculum_node_id=node.id,
        options=[dict(text='0.3', is_correct=True)], explanation='Có 3 trong 10 thẻ là thẻ đỏ.', points=1)
    prepare_preview_edit(q)
    session = ImportSession(user_id=bank.teacher.id, bank_id=bank.bank.id,
        filename='no-code.tex', file_type='tex', status='preview')
    session.set_parsed_questions([q])
    db.session.add(session)
    db.session.flush()
    refresh_preview(session)
    db.session.commit()
    ImportService.confirm_import(session.id, bank.bank.id, bank.teacher.id)
    saved = BankQuestion.query.filter_by(question_text=q['question_text']).one()
    assert saved.source_id is None
    assert saved.classification_status == 'teacher_confirmed'
    assert bp.readiness_error(saved) is None


def test_bounded_repair_and_missing_type(bank):
    base = choose(bank)
    ranked = [dict(question=q, skill=q.curriculum_node.canonical_code, score=0,
                   fingerprint=str(q.id)) for q in base['questions']]
    levels = base['aptga']['desired_quotas']
    actual = Counter(x['skill'] for x in ranked)
    desired = dict(actual)
    donor = next(s for s in bp.SKILLS if desired[s]>1)
    receiver = next(s for s in bp.SKILLS if s!=donor and desired[s]<5)
    desired[donor]-=1
    desired[receiver]+=1
    selected, _, status, audit = select_resilient(ranked, levels, desired)
    assert status == 'ready'
    assert len(selected) == 22
    assert audit['recovery_stage'] == 'same_level_skill_transfer'
    assert audit['quota_changes'] == 1
    invalid = [x for x in ranked if x['question'].question_type != 'true_false']
    assert not select_resilient(invalid, levels, desired)[0]


def test_duplicate_hashes_cannot_fill_22_slots(bank):
    base = choose(bank)
    ranked = [dict(question=q, skill=q.curriculum_node.canonical_code, score=0,
                   fingerprint='same-content') for q in base['questions']]
    assert not select_resilient(ranked, base['aptga']['desired_quotas'], base['aptga']['skill_targets'])[0]


def test_repeat_evidence_discount():
    from services.practice_evidence import learning_rows
    question = SimpleNamespace(id=1, source_content_hash='same', bank_question_id=1,
        question_type='single', curriculum_code=bp.SKILLS[0], difficulty_level=bp.LEVELS[0], points=1)
    # Stub only finalization/answer parsing; exercise real history weighting.
    from unittest.mock import patch
    submissions = [SimpleNamespace(id=i, submitted_at=dt.datetime(2026,9,i),
        answers=[SimpleNamespace(question=question, points_earned=1)]) for i in (1,2,3)]
    with patch('services.practice_evidence.is_finalized', return_value=True), patch('services.practice_evidence.answer_status', return_value='answered'):
        rows = learning_rows(submissions[::-1])
    assert [r.evidence_weight for r in rows] == [1, .5, 1/3]
    assert aptga.summarize(rows)['distinct_count'] == 1
    assert not aptga.summarize(rows)['sufficient']


def test_frozen_paper_take_submit_result_and_audit(bank):
    from models import Enrollment, PracticeSession, MasterySnapshot
    from routes.practice import _create_fixed_exam
    db.session.add(Enrollment(student_id=bank.student.id, course_id=bank.course.id, status='active'))
    session = PracticeSession(student_id=bank.student.id, course_id=bank.course.id,
        subject='Toán', scope_code='9C8-i', status='active', bank_ids=json.dumps([bank.bank.id]))
    db.session.add(session)
    db.session.flush()
    exam = _create_fixed_exam(selection=choose(bank), course=bank.course, bank_ids=[bank.bank.id],
        student_id=bank.student.id, creator_id=bank.student.id, title='Bài luyện V2',
        is_active=True, practice_session=session)
    db.session.commit()
    client = app.test_client()
    with client.session_transaction() as login:
        login['_user_id'] = str(bank.student.id)
        login['_fresh'] = True
    assert client.get('/practice').status_code == 200
    response = client.get(f'/practice/{exam.id}/take')
    assert response.status_code == 200
    payload = {}
    for q in exam.questions:
        if q.question_type == 'single':
            payload[f'q_{q.id}'] = str(next(a.id for a in q.answers if a.is_correct))
        elif q.question_type == 'short_answer':
            payload[f'q_{q.id}_text'] = '1/2'
        else:
            for answer in q.answers:
                payload[f'q_{q.id}_ans_{answer.id}'] = str(int(answer.is_correct))
    assert client.post(f'/practice/{exam.id}/take', data=payload).status_code == 302
    result = client.get(f'/practice/{exam.id}/result')
    assert result.status_code == 200
    assert 'Vì sao bạn nhận bài luyện này?' in result.get_data(as_text=True)
    assert MasterySnapshot.query.filter_by(student_id=bank.student.id).count() == 1
    snapshot = MasterySnapshot.query.filter_by(student_id=bank.student.id).one()
    persisted = json.loads(snapshot.profile_data)
    assert persisted['practice_evidence_policy'] == 'atomic_repeat_discount_v2'
    assert len(persisted['practice_skill_mastery']) == 32
    submission = ExamSubmission.query.filter_by(exam_id=exam.id).one()
    assert submission.total_score == 10
    assert len(choose(bank)['questions']) == 22


def test_phase1_inventory_is_additive_and_does_not_change_selection(bank):
    before = choose(bank)
    inventory = before['aptga']['source_inventory']
    assert inventory['mode'] == 'observe_only'
    assert len(inventory['cells']) == 96
    assert inventory['candidate_rows'] == 96
    assert not inventory['empty_cells']
    # Disable only the added audit calculation, retaining the original solver.
    with patch('services.practice_source_inventory.build_source_inventory', return_value={}):
        without_audit = choose(bank)
    assert [q.id for q in before['questions']] == [q.id for q in without_audit['questions']]
    assert before['ranked'] == without_audit['ranked']
    assert {k: v for k, v in before['aptga'].items() if k != 'source_inventory'} == {
        k: v for k, v in without_audit['aptga'].items() if k != 'source_inventory'}
    assert before['explanation'] == without_audit['explanation']


def test_phase1_inventory_uses_filtered_approved_pool(bank):
    bad = bank.bank.questions[0]
    kind = bad.question_type
    bad.classification_status = 'suggested'
    db.session.commit()
    result = choose(bank)
    inventory = result['aptga']['source_inventory']
    assert inventory['candidate_rows'] == 95
    assert result['aptga']['rejected']['Phân loại chưa được giáo viên xác nhận'] == 1
    empty = dict(skill=bad.curriculum_node.canonical_code, level=bad.difficulty_level,
                 question_type=kind)
    assert empty in inventory['empty_cells']


def test_phase2_transfers_are_frozen_and_visible_on_the_real_take_page(bank):
    from models import Enrollment, PracticeSession
    from routes.practice import _create_fixed_exam
    # Remove a whole skill from the approved pool; enough other levels/types remain.
    for q in bank.bank.questions:
        if q.curriculum_node.canonical_code == bp.SKILLS[0]:
            q.adaptive_excluded = True
    db.session.commit()
    selection = choose(bank)
    audit = selection['aptga']
    assert selection['selected_count'] == 22
    assert audit['actual_quotas'] == audit['desired_quotas']
    assert audit['unavailable_skills'] == [bp.SKILLS[0]]
    assert audit['skill_transfers'] and audit['covered_skill_count'] == 7
    assert all(q.curriculum_node.canonical_code != bp.SKILLS[0] for q in selection['questions'])
    db.session.add(Enrollment(student_id=bank.student.id, course_id=bank.course.id, status='active'))
    session = PracticeSession(student_id=bank.student.id, course_id=bank.course.id,
        subject='Toán', scope_code='9C8-i', status='active', bank_ids=json.dumps([bank.bank.id]))
    db.session.add(session)
    db.session.flush()
    exam = _create_fixed_exam(selection=selection, course=bank.course, bank_ids=[bank.bank.id],
        student_id=bank.student.id, creator_id=bank.student.id, title='Chuyển dạng giữ mức',
        is_active=True, practice_session=session)
    db.session.commit()
    assert exam.get_adaptive_metadata()['aptga']['skill_transfers'] == audit['skill_transfers']
    for frozen in exam.questions:
        assert frozen.curriculum_code == frozen.bank_question.curriculum_node.canonical_code
    client = app.test_client()
    with client.session_transaction() as web_session:
        web_session['_user_id'] = str(bank.student.id)
        web_session['_fresh'] = True
    response = client.get(f'/practice/{exam.id}/take')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Chuyển dạng và giữ mức nhận thức' in html
    assert '7/8 dạng' in html
    assert 'Chuyển 1 vị trí từ dạng 1 sang dạng' in html


def test_phase2_real_pool_missing_high_level_returns_no_shortened_paper(bank):
    for q in bank.bank.questions:
        if q.difficulty_level == bp.LEVELS[-1]:
            q.adaptive_excluded = True
    db.session.commit()
    result = choose(bank)
    assert not result['questions']
    assert result['aptga']['status'] == 'insufficient_candidates'
    assert any(s['key'] == bp.LEVELS[-1] for s in result['aptga']['shortages'])
    assert result['aptga']['effective_level_targets'] == result['aptga']['desired_quotas']
    assert not result['aptga']['skill_transfers']
