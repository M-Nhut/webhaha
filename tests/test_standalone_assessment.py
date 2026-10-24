import io
from unittest.mock import patch
from werkzeug.datastructures import FileStorage, MultiDict
from tests.test_personalization_v2 import bank, app, db
from models import BankQuestion, Enrollment, Exam, ExamSubmission, ImportSession, LearningHistory
from services.import_service import ImportService
from services.standalone_assessment import save_paper

SOURCE = r'''\section*{Phần I. Trắc nghiệm}
\begin{ex}Giá trị $1+1$ là\choice{\True $2$}{$3$}{$4$}{$5$}\loigiai{$1+1=2$.}\end{ex}
\begin{ex}Xét các ý sau.\choiceTF{\True Một cộng một bằng hai.}{Một cộng một bằng ba.}{\True Hai là số chẵn.}{Hai là số lẻ.}\end{ex}
\begin{ex}Điền kết quả $2+3$.\shortans{5}\end{ex}'''


def login(user):
    from flask import g
    client = app.test_client()
    original_open = client.open
    def fresh_request(*args, **kwargs):
        g.pop('_login_user', None)
        return original_open(*args, **kwargs)
    client.open = fresh_request
    with client.session_transaction() as state:
        state['_user_id'] = str(user.id)
        state['_fresh'] = True
    return client


def uploaded(bank, source=SOURCE):
    return ImportService.create_and_process_session(bank.teacher.id,
        FileStorage(stream=io.BytesIO(source.encode()), filename='paper.tex'), 'paper.tex')


def form(bank, action='draft'):
    return MultiDict(dict(title='Đề kiểm tra thử', course_id=str(bank.course.id), duration_minutes='45',
                     action=action, reviewed='yes', q0_correct='0',
                     q1_truth0='1', q1_truth1='0', q1_truth2='1', q1_truth3='0', q2_answer='5'))


def test_unclassified_routes_to_paper_and_classified_stays_bank(bank):
    client = login(bank.teacher)
    response = client.post('/question-banks/import/upload', data={'file': (io.BytesIO(SOURCE.encode()), 'paper.tex')})
    data = response.get_json()
    assert response.status_code == 200, data
    assert data['redirect_url'].startswith('/assessments/import/')
    page = client.get(data['redirect_url'])
    assert page.status_code == 200
    assert 'Giao đề cho lớp' in page.get_data(as_text=True)
    classified = uploaded(bank, SOURCE.replace(r'\begin{ex}', r'\begin{ex}%[9C8Ni-1T]' + '\n', 1))
    assert (classified.get_scope() or {}).get('document_kind') != 'assessment'


def test_paper_draft_publish_submit_isolated_from_mastery(bank):
    initial_count = BankQuestion.query.count()
    session = uploaded(bank)
    client = login(bank.teacher)
    url = f'/assessments/import/{session.id}'
    draft = client.post(url, data=form(bank))
    assert draft.status_code == 302
    exam = Exam.query.filter_by(assessment_purpose='standalone').one()
    assert not exam.is_active and len(exam.questions) == 3
    student = login(bank.student)
    db.session.add(Enrollment(course_id=bank.course.id, student_id=bank.student.id, status='active'))
    db.session.commit()
    assert exam.title not in student.get('/assessments').get_data(as_text=True)
    published = client.post(url, data=form(bank, 'publish'))
    assert published.status_code == 302
    assert exam.is_active
    assert BankQuestion.query.count() == initial_count
    assert student.get(f'/practice/{exam.id}/take').status_code == 404
    assert student.get(f'/assessments/{exam.id}/take').status_code == 200
    q0, q1, q2 = exam.questions
    answers = {f'q_{q0.id}': str(q0.answers[0].id), f'q_{q2.id}_text': '5'}
    for answer in q1.answers:
        answers[f'q_{q1.id}_ans_{answer.id}'] = '1' if answer.is_correct else '0'
    with patch('routes.practice_runtime.AdaptiveEngine.update_performance') as mastery:
        submitted = student.post(f'/assessments/{exam.id}/take', data=answers)
        assert submitted.status_code == 302
        assert '/assessments/' in submitted.location
        mastery.assert_not_called()
    submission = ExamSubmission.query.filter_by(exam_id=exam.id).one()
    assert submission.total_score == 10
    assert LearningHistory.query.count() == 0
    student.post(f'/assessments/{exam.id}/take', data=answers)
    assert ExamSubmission.query.filter_by(exam_id=exam.id).count() == 1
    assert student.get(f'/assessments/{exam.id}/result').status_code == 200


def test_incomplete_key_blocked_foreign_class_blocked_and_bank_confirm_blocked(bank):
    import pytest
    session = uploaded(bank)
    missing = form(bank, 'publish'); missing['q0_correct'] = ''
    with pytest.raises(ValueError):
        save_paper(session, bank.teacher, missing)
    db.session.rollback()
    foreign = form(bank); foreign['course_id'] = '99999'
    with pytest.raises(PermissionError):
        save_paper(session, bank.teacher, foreign)
    with pytest.raises(ValueError, match='Đề chưa phân dạng'):
        ImportService.confirm_import(session.id, bank.bank.id, bank.teacher.id)


def test_template_comments_and_section_levels(tmp_path):
    from services.latex_parser import parse_latex
    from services.latex_document import document_profile, knowledge_heading
    source = '% ' + r'\begin{ex}Example only\end{ex}' + '\n'
    source += r'\section*{Dạng 1. Phép cộng}\subsection*{II. Thông hiểu}' + '\n'
    source += SOURCE[SOURCE.index(r'\begin{ex}'):SOURCE.index(r'\begin{ex}Xét')]
    path = tmp_path / 'classified.tex'; path.write_text(source, encoding='utf-8')
    questions = parse_latex(path)
    assert len(questions) == 1
    assert questions[0]['difficulty_level'] == 'thong_hieu'
    assert document_profile(questions)['document_kind'] == 'bank'
    assert not knowledge_heading('I. Trắc nghiệm nhiều lựa chọn')
    assert not knowledge_heading('Đề số 1')
    path.write_text(source.replace('II. Thông hiểu', 'IV. Vận dụng cao'), encoding='utf-8')
    assert parse_latex(path)[0]['difficulty_level'] == 'van_dung_cao'


def test_edit_json_persists_all_fields_and_validation_keeps_draft(bank):
    session = uploaded(bank)
    client = login(bank.teacher)
    values = form(bank)
    values.update(dict(q0_question_text='Tính $2+2$.', q0_context='Dữ kiện mới',
                       q0_option0='$4$', q0_explanation='$2+2=4$.', q0_points='2'))
    url = f'/assessments/import/{session.id}'
    saved = client.post(url, data=values, headers={'Accept': 'application/json'})
    assert saved.status_code == 200, saved.get_json()
    exam = db.session.get(Exam, saved.get_json()['exam_id'])
    q = exam.questions[0]
    from services.question_policy import resolve_formula_to_text
    assert '2+2' in resolve_formula_to_text(q.question_text)
    assert q.context == 'Dữ kiện mới' and q.points == 5
    assert '4' in resolve_formula_to_text(q.answers[0].answer_text)
    assert '2+2=4' in resolve_formula_to_text(q.explanation)
    values['title'] = ''
    rejected = client.post(url, data=values, headers={'Accept': 'application/json'})
    assert rejected.status_code == 400 and not rejected.get_json()['success']
    assert exam.title == 'Đề kiểm tra thử'


def test_bank_selection_permissions_shortage_and_frozen_draft(bank):
    import pytest
    from services.assessment_bank import create_bank_draft
    question = bank.bank.questions[0]
    draft = create_bank_draft(bank.teacher, bank.course, [bank.bank.id], selected_ids=[question.id])
    assert draft.get_parsed_questions()[0]['bank_question_id'] == question.id
    values = form(bank); values['q0_report_confirmed'] = 'yes'
    exam = save_paper(draft, bank.teacher, values)
    assert exam.questions[0].curriculum_code == question.curriculum_node.canonical_code
    original = exam.questions[0].question_text
    question.question_text = 'Nội dung ngân hàng thay đổi'
    db.session.commit()
    assert exam.questions[0].question_text == original
    with pytest.raises(PermissionError):
        create_bank_draft(bank.teacher, bank.course, [bank.bank.id], selected_ids=[99999])
    with pytest.raises(ValueError):
        create_bank_draft(bank.teacher, bank.course, [bank.bank.id], quantity=101)
    auto = create_bank_draft(bank.teacher, bank.course, [bank.bank.id], quantity=12)
    assert len({q['bank_question_id'] for q in auto.get_parsed_questions()}) == 12


def test_typed_bank_selection_and_ten_point_save(bank):
    from services.assessment_bank import create_bank_draft
    from collections import Counter
    import pytest
    counts = {'single': 12, 'true_false': 4, 'short_answer': 6}
    budgets = {'single': 3, 'true_false': 4, 'short_answer': 3}
    draft = create_bank_draft(bank.teacher, bank.course, [bank.bank.id], counts=counts, budgets=budgets)
    items = draft.get_parsed_questions()
    assert Counter(q['question_type'] for q in items) == counts
    assert len({q['bank_question_id'] for q in items}) == 22
    assert sum(q['points'] for q in items) == 10
    before = ImportSession.query.count()
    with pytest.raises(ValueError, match='ngân hàng có'):
        create_bank_draft(bank.teacher, bank.course, [bank.bank.id], counts={'single': 99}, budgets={'single': 10})
    assert ImportSession.query.count() == before
    session = uploaded(bank)
    values = form(bank)
    values.update({f'budget_{kind}': str(value) for kind, value in budgets.items()})
    exam = save_paper(session, bank.teacher, values)
    assert [q.points for q in exam.questions] == [3, 4, 3]
    values['budget_single'] = '4'
    response = login(bank.teacher).post(f'/assessments/import/{session.id}', data=values, headers={'Accept': 'application/json'})
    assert response.status_code == 400
    assert [q.points for q in exam.questions] == [3, 4, 3]
    client = login(bank.teacher)
    assert client.get(f'/assessments/from-bank?course_id={bank.course.id}&bank_ids={bank.bank.id}').status_code == 200
    assert client.get('/assessments/from-bank?course_id=99999').status_code == 403
    posted = client.post(f'/assessments/from-bank?course_id={bank.course.id}&bank_ids={bank.bank.id}',
                         data={'course_id': str(bank.course.id), 'bank_ids': str(bank.bank.id), 'mode': 'auto', 'quantity': '3'})
    assert posted.status_code == 302 and '/assessments/import/' in posted.location


def test_exam_evidence_in_report_but_no_adaptive_change(bank):
    from tests.test_personalization_v2 import choose
    from services.class_lesson4_report import build_class_lesson4_packet, packet_fingerprint
    from services.practice_evidence import learning_rows
    from adaptive_engine import AdaptiveEngine
    before = [q.id for q in choose(bank)['questions']]
    db.session.add(Enrollment(course_id=bank.course.id, student_id=bank.student.id, status='active'))
    db.session.commit()
    session = uploaded(bank)
    values = form(bank, 'publish')
    values['q0_report_confirmed'] = 'yes'
    values['q0_report_code'] = '9C8-i-1'
    values['q0_difficulty_level'] = 'nhan_biet'
    exam = save_paper(session, bank.teacher, values)
    student = login(bank.student)
    q = exam.questions[0]
    response = student.post(f'/assessments/{exam.id}/take', data={f'q_{q.id}': str(q.answers[1].id)})
    assert response.status_code == 302
    submission = ExamSubmission.query.filter_by(exam_id=exam.id).one()
    packet = build_class_lesson4_packet(bank.course)
    events = packet['students'][0]['events']
    assert len(events) == 1 and events[0]['assessment_source'] == 'standalone'
    assert events[0]['outcome'] == 'wrong' and events[0]['curriculum_code'] == '9C8-i-1'
    assert packet_fingerprint(packet) == packet_fingerprint(build_class_lesson4_packet(bank.course))
    assert learning_rows([submission]) == []
    assert AdaptiveEngine.record_submission(bank.student.id, submission) == []
    assert LearningHistory.query.count() == 0
    assert [q.id for q in choose(bank)['questions']] == before
    teacher = login(bank.teacher)
    page = teacher.get(f'/teacher/practice/{bank.student.id}?course_id={bank.course.id}')
    assert page.status_code == 200
    assert 'Kết quả đề kiểm tra' not in page.get_data(as_text=True)


def test_explicit_assessment_accepts_classified_file(bank):
    source = SOURCE.replace(r'\begin{ex}', r'\begin{ex}%[9C8Ni-1T]' + '\n', 1)
    response = login(bank.teacher).post('/question-banks/import/upload', data={
        'file': (io.BytesIO(source.encode()), 'classified.tex'), 'document_purpose': 'assessment'})
    assert response.status_code == 200
    assert response.get_json()['redirect_url'].startswith('/assessments/import/')
