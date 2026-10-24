"""Phase 5 contracts: native CSRF, import transactions and draft composition.

All application imports happen after pinning the database and file storage to
disposable paths. These tests never read local credentials or learner data.
"""
from __future__ import annotations

import io
import json
import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import MultiDict
from scripts.preview_ui_phase5 import (
    GENERAL_SOURCE, PAPER_SOURCE, RESEARCH_SOURCE,
    isolate_environment, isolate_phase5, seed_data,
)

_storage = TemporaryDirectory(prefix='linhedu-phase5-tests-')
isolate_environment(_storage.name)
from app import app
from database import db
from models import BankQuestion, Exam, ImportSession, QuestionBank
isolate_phase5(app, _storage.name)


def csrf(response):
    html = response.get_data(as_text=True)
    match = re.search(r'name="csrf-token"[^>]*content="([^"]+)"', html) or re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return match.group(1)


@pytest.fixture
def workspace():
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
    isolate_phase5(app, _storage.name)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    with app.app_context():
        data = seed_data(db)
        yield SimpleNamespace(client=app.test_client(), data=data)
        db.session.remove()
        db.drop_all()


def login(workspace, role='teacher'):
    page = workspace.client.get('/login')
    result = workspace.client.post('/login', data={'csrf_token': csrf(page), 'username': 'qa_' + role, 'password': 'Academy123!'})
    assert result.status_code == 302
    from flask import g
    g.pop('_login_user', None)


def api(workspace, key='general', action='preview'):
    return f"/question-banks/import/{workspace.data['sessions'][key]}/{action}"


def json_post(workspace, url, payload):
    token = csrf(workspace.client.get('/question-banks/import'))
    return workspace.client.post(url, json=payload, headers={'X-CSRFToken': token})


def upload(workspace, source=GENERAL_SOURCE, **extra):
    token = csrf(workspace.client.get('/question-banks/import'))
    return workspace.client.post('/question-banks/import/upload', data={
        'csrf_token': token, 'file': (io.BytesIO(source.encode()), 'qa.tex'), **extra,
    })


@pytest.mark.parametrize('role', ['teacher', 'admin'])
def test_phase5_pages_and_mutation_destinations(workspace, role):
    login(workspace, role)
    page = workspace.client.get('/question-banks/import').get_data(as_text=True)
    assert ('Học liệu riêng của giáo viên khác' in page) == (role == 'admin')
    for path in ('/question-banks/import', '/assessments/from-bank'):
        assert workspace.client.get(path).status_code == 200
    if role == 'teacher':
        for key in ('paper', 'bank-paper'):
            assert workspace.client.get('/assessments/import/' + workspace.data['sessions'][key]).status_code == 200


def test_student_has_no_import_or_composer_access(workspace):
    login(workspace, 'student')
    assert workspace.client.get('/question-banks/import').status_code == 302
    assert workspace.client.get('/assessments/from-bank').status_code == 403
    assert workspace.client.get('/assessments/import/' + workspace.data['sessions']['paper']).status_code == 403


@pytest.mark.parametrize('profile', ['general', 'assessment', ''])
def test_public_tex_examples_download_in_isolated_root(workspace, profile):
    login(workspace)
    result = workspace.client.get('/question-banks/import/template/latex?profile=' + profile)
    assert result.status_code == 200 and b'\\begin{ex}' in result.data
    assert 'attachment' in result.headers['Content-Disposition']


def test_import_and_composer_mutations_require_csrf(workspace):
    login(workspace)
    assert workspace.client.post(api(workspace, action='confirm'), json={}).status_code == 400
    assert workspace.client.post('/question-banks/import/upload', data={'file': (io.BytesIO(GENERAL_SOURCE.encode()), 'qa.tex')}).status_code == 400
    assert workspace.client.post('/assessments/from-bank', data={}).status_code == 400


@pytest.mark.parametrize('filename', ['qa.docx', 'qa.pdf'])
def test_wrong_file_type_is_rejected_without_session(workspace, filename):
    login(workspace)
    before = ImportSession.query.count()
    result = workspace.client.post('/question-banks/import/upload', data={'csrf_token': csrf(workspace.client.get('/question-banks/import')), 'file': (io.BytesIO(b'bad'), filename)})
    assert result.status_code == 400 and ImportSession.query.count() == before


def test_general_upload_review_and_source_download(workspace):
    login(workspace)
    result = upload(workspace, bank_id=workspace.data['banks']['general'])
    assert result.status_code == 200
    data = result.get_json()
    assert data['scope']['mode'] == 'general'
    assert {q['question_type'] for q in data['questions']} == {'single', 'true_false', 'short_answer'}
    assert all(q['status'] != 'error' and q['curriculum_node_id'] is None for q in data['questions'])
    downloaded = workspace.client.get('/question-banks/import/' + data['session_id'] + '/source')
    assert downloaded.status_code == 200 and downloaded.data == GENERAL_SOURCE.encode()


def test_upload_purpose_and_auto_detection_select_editor(workspace):
    login(workspace)
    for source, params in ((PAPER_SOURCE, {}), (GENERAL_SOURCE, {'document_purpose': 'assessment'})):
        result = upload(workspace, source, **params)
        assert result.status_code == 200 and result.get_json()['redirect_url'].startswith('/assessments/import/')
        assert workspace.client.get(result.get_json()['redirect_url']).status_code == 200


def test_resume_and_foreign_session_contract(workspace):
    login(workspace)
    data = workspace.client.get(api(workspace)).get_json()
    assert data['filename'] == 'general.tex' and data['bank_id'] == workspace.data['banks']['general']
    assert data['duplicate_report']['revision']
    foreign = workspace.client.get(api(workspace, 'foreign'))
    assert foreign.status_code == 404
    assert json_post(workspace, api(workspace, 'foreign', 'update'), {'index': 0, 'question': data['questions'][0]}).status_code == 404
    assert json_post(workspace, api(workspace, 'foreign', 'confirm'), {'bank_id': data['bank_id']}).status_code == 404
    assert workspace.client.get('/assessments/import/' + workspace.data['sessions']['foreign']).status_code == 403


def test_edit_and_remove_preview_rescan_preserving_other_rows(workspace):
    login(workspace)
    old = workspace.client.get(api(workspace)).get_json()
    row = old['questions'][0]
    row['question_text'] = 'Nội dung đã được giáo viên chỉnh sửa $x=2$.'
    edited = json_post(workspace, api(workspace, action='update'), {'index': 0, 'question': row})
    assert edited.status_code == 200 and edited.get_json()['questions'][0]['question_text']
    assert edited.get_json()['duplicate_report']['revision'] != old['duplicate_report']['revision']
    removed = json_post(workspace, api(workspace, action='remove'), {'index': 0})
    assert removed.status_code == 200 and removed.get_json()['stats']['total'] == 2
    assert removed.get_json()['questions'][0]['import_uid'] == old['questions'][1]['import_uid']


def test_destination_rescan_rejects_foreign_and_old_confirmation(workspace):
    login(workspace)
    old = workspace.client.get(api(workspace)).get_json()
    denied = json_post(workspace, api(workspace, action='destination'), {'bank_id': workspace.data['banks']['foreign']})
    assert denied.status_code == 400
    changed = json_post(workspace, api(workspace, action='destination'), {'bank_id': workspace.data['banks']['empty']})
    assert changed.status_code == 200 and changed.get_json()['bank_id'] == workspace.data['banks']['empty']
    stale = json_post(workspace, api(workspace, action='confirm'), {'bank_id': workspace.data['banks']['empty'], 'confirmation_token': old['duplicate_report']['revision']})
    assert stale.status_code == 400


@pytest.mark.parametrize('decision', ['incoming', 'duplicate', 'different', 'neither'])
def test_in_file_duplicate_decisions_are_revision_bound(workspace, decision):
    login(workspace)
    data = workspace.client.get(api(workspace, 'duplicates')).get_json()
    row = next(q for q in data['questions'] if q['duplicate']['matches'])
    match = row['duplicate']['matches'][0]
    result = json_post(workspace, api(workspace, 'duplicates', 'duplicate-decision'), {'import_uid': row['import_uid'], 'token': match['token'], 'decision': decision})
    assert result.status_code == 200 and result.get_json()['success']
    invalid = json_post(workspace, api(workspace, 'duplicates', 'duplicate-decision'), {'import_uid': row['import_uid'], 'token': 'stale-token', 'decision': decision})
    assert invalid.status_code == 400


def test_import_receipt_replay_and_reimport_do_not_duplicate_rows(workspace):
    login(workspace)
    before = BankQuestion.query.count()
    data = workspace.client.get(api(workspace)).get_json()
    payload = {'bank_id': data['bank_id'], 'confirmation_token': data['duplicate_report']['revision']}
    first = json_post(workspace, api(workspace, action='confirm'), payload).get_json()
    assert first['success'] and first['imported_count'] == 3 and first['completed']
    assert BankQuestion.query.count() == before + 3
    replay = json_post(workspace, api(workspace, action='confirm'), payload).get_json()
    assert replay['replayed'] and BankQuestion.query.count() == before + 3
    second = workspace.client.get(api(workspace, 'duplicates')).get_json()
    assert second['duplicate_report']['duplicate'] == 6


def test_incomplete_answer_partial_receipt_keeps_pending_row(workspace):
    login(workspace)
    data = workspace.client.get(api(workspace, 'incomplete')).get_json()
    result = json_post(workspace, api(workspace, 'incomplete', 'confirm'), {'bank_id': data['bank_id'], 'confirmation_token': data['duplicate_report']['revision']}).get_json()
    assert result['success'] and result['imported_count'] == 2 and not result['completed']
    preview = workspace.client.get(api(workspace, 'incomplete')).get_json()
    assert sum(bool(q.get('saved_question_id')) for q in preview['questions']) == 2
    assert any(q['status'] == 'error' and q.get('confirmation_errors') for q in preview['questions'])
    assert json_post(workspace, api(workspace, 'incomplete', 'destination'), {'bank_id': workspace.data['banks']['empty']}).status_code == 400


def test_shared_destination_creates_only_teacher_owned_overlay(workspace):
    login(workspace)
    data = upload(workspace, RESEARCH_SOURCE, bank_id=workspace.data['banks']['shared']).get_json()
    result = json_post(workspace, '/question-banks/import/' + data['session_id'] + '/confirm', {'bank_id': data['bank_id'], 'confirmation_token': data['duplicate_report']['revision']}).get_json()
    assert result['success'] and result['imported_count'] == 1
    created = BankQuestion.query.filter_by(bank_id=data['bank_id'], question_text=data['questions'][0]['question_text']).one()
    assert created.scope == 'private' and created.private_owner_id == workspace.data['users']['teacher']


def test_new_bank_scope_is_derived_from_actor(workspace):
    login(workspace)
    response = json_post(workspace, api(workspace, action='destination'), {'bank_id': None}).get_json()
    result = json_post(workspace, api(workspace, action='confirm'), {'new_bank_name': 'Ngân hàng nhập mới', 'subject': 'Toán', 'grade': '10', 'visibility': 'shared', 'confirmation_token': response['duplicate_report']['revision']}).get_json()
    assert result['success']
    bank = QuestionBank.query.filter_by(name='Ngân hàng nhập mới').one()
    assert bank.visibility == 'private' and bank.created_by == workspace.data['users']['teacher']


@pytest.mark.parametrize('mode', ['manual', 'auto'])
def test_bank_selection_creates_reviewable_draft_with_exact_scoring(workspace, mode):
    login(workspace)
    token = csrf(workspace.client.get('/assessments/from-bank'))
    fields = MultiDict({'csrf_token': token, 'course_id': str(workspace.data['courses']['teacher']), 'mode': mode,
        'count_single': '1', 'count_true_false': '1', 'count_short_answer': '1',
        'budget_single': '4', 'budget_true_false': '4', 'budget_short_answer': '2'})
    fields.setlist('bank_ids', [str(workspace.data['banks']['general'])])
    fields.setlist('question_ids', [str(workspace.data['questions'][name]) for name in ('general-single', 'general-tf', 'general-short')])
    result = workspace.client.post('/assessments/from-bank', data=fields)
    assert result.status_code == 302 and result.location.startswith('/assessments/import/')
    sid = result.location.rsplit('/', 1)[-1]
    row = db.session.get(ImportSession, sid)
    assert len(row.get_parsed_questions()) == 3 and row.get_scope()['section_points'] == {'single': 4, 'true_false': 4, 'short_answer': 2}
    assert Exam.query.count() == 0


def paper_form(workspace, **changes):
    fields = {'csrf_token': csrf(workspace.client.get('/question-banks/import')),
        'title': 'Đề kiểm tra thử', 'course_id': str(workspace.data['courses']['teacher']), 'duration_minutes': '45',
        'action': 'draft', 'reviewed': 'yes', 'budget_single': '4', 'budget_true_false': '4', 'budget_short_answer': '2',
        'q0_correct': '0', 'q1_truth0': '1', 'q1_truth1': '0', 'q1_truth2': '1', 'q1_truth3': '0', 'q2_answer': '5'}
    return {**fields, **changes}


def test_editor_json_failure_does_not_write_then_draft_publish_lock(workspace):
    login(workspace)
    url = '/assessments/import/' + workspace.data['sessions']['paper']
    bad = workspace.client.post(url, data=paper_form(workspace, budget_single='7'), headers={'Accept': 'application/json'})
    assert bad.status_code == 400 and not bad.get_json()['success'] and Exam.query.count() == 0
    draft = workspace.client.post(url, data=paper_form(workspace), headers={'Accept': 'application/json'})
    assert draft.status_code == 200 and draft.get_json()['matrix_url']
    exam = db.session.get(Exam, draft.get_json()['exam_id'])
    assert not exam.is_active and len(exam.questions) == 3 and sum(q.points for q in exam.questions) == 10
    reviewed = workspace.client.post(url, data=paper_form(workspace, action='publish', reviewed=''), headers={'Accept': 'application/json'})
    assert reviewed.status_code == 400 and not exam.is_active
    published = workspace.client.post(url, data=paper_form(workspace, action='publish'), headers={'Accept': 'application/json'})
    assert published.status_code == 200 and published.get_json()['redirect_url'] == '/assessments' and exam.is_active
    assert workspace.client.get(url).status_code == 302
    blocked = workspace.client.post(url, data=paper_form(workspace), headers={'Accept': 'application/json'})
    assert blocked.status_code == 400


def test_foreign_course_and_bank_sources_remain_unavailable(workspace):
    login(workspace)
    course = workspace.data['courses']['teacher']
    assert workspace.client.get(f"/assessments/from-bank?course_id={course}&bank_ids={workspace.data['banks']['foreign']}").status_code == 403
    result = workspace.client.post('/assessments/import/' + workspace.data['sessions']['paper'], data=paper_form(workspace, course_id=str(workspace.data['courses']['foreign'])), headers={'Accept': 'application/json'})
    assert result.status_code == 403 and Exam.query.count() == 0


def test_cancel_closes_session_and_prevents_confirmation(workspace):
    login(workspace)
    assert json_post(workspace, api(workspace, action='cancel'), {}).get_json()['success']
    assert json_post(workspace, api(workspace, action='confirm'), {'bank_id': workspace.data['banks']['general']}).status_code == 404


def test_original_question_link_resolves_page_without_disclosing_private_rows(workspace):
    login(workspace)
    bank_id = workspace.data['banks']['shared']
    target = db.session.get(BankQuestion, workspace.data['questions']['common-7'])
    page = workspace.client.get(f'/question-banks/{bank_id}?question_id={target.id}')
    assert page.status_code == 200
    assert json.dumps(target.question_text, ensure_ascii=True)[1:-1] in page.get_data(as_text=True)
    hidden = workspace.data['questions']['foreign-overlay']
    protected = workspace.client.get(f'/question-banks/{bank_id}?question_id={hidden}')
    hidden_text = db.session.get(BankQuestion, hidden).question_text
    assert protected.status_code == 200
    assert json.dumps(hidden_text, ensure_ascii=True)[1:-1] not in protected.get_data(as_text=True)
