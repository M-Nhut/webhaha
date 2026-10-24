"""Phase 6 route, grading and permission contracts with isolated DB/storage."""
from __future__ import annotations

import io
import json
import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

import pytest
from scripts.preview_ui_phase6 import isolate_environment, isolate_phase5, seed_data

_storage=TemporaryDirectory(prefix='linhedu-phase6-tests-')
isolate_environment(_storage.name)
from app import app
from database import db
from models import Exam, ExamSubmission, SubmissionAnswer, MasterySnapshot, LearningHistory
isolate_phase5(app,_storage.name)


def token(response):
    html=response.get_data(as_text=True)
    match=re.search(r'name="csrf-token"[^>]*content="([^"]+)"',html) or re.search(r'name="csrf_token"[^>]*value="([^"]+)"',html)
    return match.group(1)


@pytest.fixture
def workspace():
    assert app.config['SQLALCHEMY_DATABASE_URI']=='sqlite:///:memory:'
    isolate_phase5(app,_storage.name)
    app.config.update(TESTING=True,WTF_CSRF_ENABLED=True)
    with app.app_context():
        data=seed_data(db)
        yield SimpleNamespace(client=app.test_client(),data=data)
        db.session.remove();db.drop_all()


def login(workspace,role='student'):
    from flask import g
    workspace.client.get('/logout');g.pop('_login_user',None)
    page=workspace.client.get('/login')
    response=workspace.client.post('/login',data={'csrf_token':token(page),'username':'qa_'+role,'password':'Academy123!'})
    assert response.status_code==302
    g.pop('_login_user',None)


def url(workspace,key='published',action='take'):
    return f"/{'assessments' if key in ('published','graded','history','empty','foreign','closed','draft') else 'practice'}/{workspace.data['exams'][key]}/{action}"


@pytest.mark.parametrize('key',['published','fixed','diagnostic','legacy'])
def test_take_all_contexts_keep_fields_and_never_render_answer_key(workspace,key):
    login(workspace)
    response=workspace.client.get(url(workspace,key))
    assert response.status_code==200
    html=response.get_data(as_text=True)
    assert 'id="exam-form"' in html and 'name="csrf_token"' in html
    assert 'name="time_spent_seconds"' in html and 'is_correct' not in html and 'data-correct' not in html
    assert not re.search(r'<input\b[^>]*\bchecked(?:\s|>)',html)
    for q in workspace.data['questions_by_exam'][key]:
        name=f"q_{q['id']}_text" if q['kind']=='short_answer' else f"q_{q['id']}_ans_" if q['kind']=='true_false' else f"q_{q['id']}"
        assert name in html
    count=22 if key in ('fixed','diagnostic') else 3
    assert len(workspace.data['questions_by_exam'][key])==count


@pytest.mark.parametrize('role',['teacher','admin'])
def test_teacher_admin_cannot_take_student_paper(workspace,role):
    login(workspace,role)
    assert workspace.client.get(url(workspace)).status_code==403
    assert workspace.client.get(url(workspace,'fixed')).status_code==403


def test_reading_take_does_not_create_draft_or_restore_answers(workspace):
    login(workspace)
    before=(ExamSubmission.query.count(),SubmissionAnswer.query.count())
    for _ in range(2):assert workspace.client.get(url(workspace)).status_code==200
    assert before==(ExamSubmission.query.count(),SubmissionAnswer.query.count())


def test_numeric_hint_is_available_for_standalone_as_well_as_fixed(workspace):
    login(workspace)
    for key in ('published','fixed','diagnostic'):
        html=workspace.client.get(url(workspace,key)).get_data(as_text=True)
        assert 'phân số' in html


@pytest.mark.parametrize('key',['graded','history','decision','source_invalid','diagnostic_done','multi_history'])
def test_student_results_show_own_frozen_evidence(workspace,key):
    login(workspace)
    response=workspace.client.get(url(workspace,key,'result'))
    assert response.status_code==200
    assert db.session.get(Exam,workspace.data['exams'][key]).title in response.get_data(as_text=True)


def test_ungraded_history_is_distinct_from_zero_or_incorrect(workspace):
    login(workspace)
    response=workspace.client.get(url(workspace,'history','result'))
    html=response.get_data(as_text=True)
    assert 'Chưa chấm' in html and 'lịch sử' in html


def test_decision_buttons_follow_server_source_readiness(workspace):
    login(workspace)
    ready=workspace.client.get(url(workspace,'decision','result')).get_data(as_text=True)
    invalid=workspace.client.get(url(workspace,'source_invalid','result')).get_data(as_text=True)
    sid=workspace.data['submissions']['decision'];blocked=workspace.data['submissions']['source_invalid']
    assert f'/practice/submissions/{sid}/continue' in ready and f'/practice/submissions/{sid}/end' in ready
    assert f'/practice/submissions/{blocked}/continue' not in invalid and f'/practice/submissions/{blocked}/end' in invalid


def test_student_cannot_see_another_submission_or_matrix(workspace):
    login(workspace,'other_student')
    response=workspace.client.get(url(workspace,'graded','result')+'?submission_id='+str(workspace.data['submissions']['graded']))
    assert response.status_code==302
    assert workspace.client.get(url(workspace,'fixed')).status_code==403
    assert workspace.client.get(url(workspace,'published','matrix')).status_code==403
    login(workspace)
    assert workspace.client.get(url(workspace,'foreign')).status_code==403
    assert workspace.client.get(url(workspace,'source_invalid')).status_code==403


def test_missing_standalone_result_returns_to_assessments(workspace):
    login(workspace)
    response=workspace.client.get(url(workspace,'published','result'))
    assert response.status_code==302 and response.location.endswith('/assessments')


def test_closed_and_already_submitted_go_to_expected_destination(workspace):
    login(workspace)
    assert workspace.client.get(url(workspace,'closed')).location.endswith('/assessments')
    response=workspace.client.get(url(workspace,'graded'))
    assert response.status_code==302 and response.location.endswith('/result')


@pytest.mark.parametrize('role',['teacher','admin'])
def test_management_list_matrix_and_submission_detail(workspace,role):
    login(workspace,role)
    client=workspace.client
    assert client.get('/assessments').status_code==200
    for key in ('graded','history','empty'):
        assert client.get(url(workspace,key,'result')).status_code==200
    response=client.get(url(workspace,'graded','result')+'?submission_id='+str(workspace.data['submissions']['graded']))
    assert response.status_code==200
    assert client.get(url(workspace,'empty','result')+'?submission_id='+str(workspace.data['submissions']['graded'])).status_code==404
    if role=='teacher':assert client.get(url(workspace,'foreign','result')).status_code==403


def test_matrix_export_stays_ten_points_and_no_store(workspace):
    login(workspace,'teacher')
    from services.assessment_matrix import build_matrix
    for key in ('published','draft','graded'):
        paper=db.session.get(Exam,workspace.data['exams'][key]);before=[q.points for q in paper.questions]
        response=workspace.client.get(url(workspace,key,'matrix'))
        assert response.status_code==200 and response.headers['Cache-Control']=='private, no-store'
        matrix=build_matrix(paper)
        assert sum(matrix['section_points'])==10 and before==[q.points for q in paper.questions]
        raw=workspace.client.get(url(workspace,key,'matrix')+'?download=xlsx')
        assert raw.status_code==200 and raw.headers['Cache-Control']=='private, no-store'
        with ZipFile(io.BytesIO(raw.data)) as archive:
            assert archive.testzip() is None
            assert b'landscape' in archive.read('xl/worksheets/sheet1.xml')


def answer_form(workspace,mode='all'):
    fields={'csrf_token':token(workspace.client.get(url(workspace))), 'time_spent_seconds':'90'}
    for q in workspace.data['questions_by_exam']['published']:
        fields[f"time_q_{q['id']}"]='30'
        if mode=='blank':continue
        if q['kind']=='single':fields[f"q_{q['id']}"]=str(next(a['id'] for a in q['answers'] if a['correct']))
        elif q['kind']=='true_false':
            for i,a in enumerate(q['answers']):
                if mode!='partial' or i<2:fields[f"q_{q['id']}_ans_{a['id']}"]='1' if a['correct'] else '0'
        else:fields[f"q_{q['id']}_text"]='5.0'
    return fields


@pytest.mark.parametrize('mode,score',[('all',10),('partial',8),('blank',0)])
def test_standalone_native_post_grades_once_without_updating_mastery(workspace,mode,score):
    login(workspace)
    before=(MasterySnapshot.query.count(),LearningHistory.query.count())
    fields=answer_form(workspace,mode)
    with patch('routes.practice_runtime.AdaptiveEngine.update_performance') as adaptive:
        result=workspace.client.post(url(workspace),data=fields)
        adaptive.assert_not_called()
    assert result.status_code==302 and result.location.endswith('/result')
    row=ExamSubmission.query.filter_by(exam_id=workspace.data['exams']['published']).one()
    assert row.total_score==score and row.max_score==10 and row.time_spent_seconds==90
    assert row.is_graded and row.status=='graded' and row.finalized_at
    assert [a.time_spent_seconds for a in row.answers]==[30,30,30]
    assert before==(MasterySnapshot.query.count(),LearningHistory.query.count())
    repeat=workspace.client.post(url(workspace),data=fields)
    assert repeat.status_code==302 and ExamSubmission.query.filter_by(exam_id=row.exam_id).count()==1
    assert workspace.client.get(result.location).status_code==200


def test_post_requires_csrf_and_rejects_file_answers(workspace):
    login(workspace)
    assert workspace.client.post(url(workspace),data={}).status_code==400
    fields=answer_form(workspace);fields['file']=(io.BytesIO(b'not a supported submission'),'answer.txt')
    assert workspace.client.post(url(workspace),data=fields).status_code==302
    assert ExamSubmission.query.filter_by(exam_id=workspace.data['exams']['published']).count()==0


def test_failed_grading_transaction_rolls_back_every_answer(workspace):
    login(workspace)
    before=SubmissionAnswer.query.count()
    with patch('routes.practice_runtime.db.session.commit',side_effect=RuntimeError('Synthetic failure')):
        response=workspace.client.post(url(workspace),data=answer_form(workspace))
    assert response.status_code==302 and response.location.endswith('/take')
    assert ExamSubmission.query.filter_by(exam_id=workspace.data['exams']['published']).count()==0
    assert SubmissionAnswer.query.count()==before


@pytest.mark.parametrize('key',['fixed','diagnostic'])
def test_fixed_and_diagnostic_keep_existing_grading_contract(workspace,key):
    login(workspace)
    fields={'csrf_token':token(workspace.client.get(url(workspace,key))),'time_spent_seconds':'100'}
    for q in workspace.data['questions_by_exam'][key]:
        if q['kind']=='single':fields[f"q_{q['id']}"]=str(next(a['id'] for a in q['answers'] if a['correct']))
        elif q['kind']=='true_false':
            fields.update({f"q_{q['id']}_ans_{a['id']}":'1' if a['correct'] else '0' for a in q['answers']})
        else:fields[f"q_{q['id']}_text"]='5'
    result=workspace.client.post(url(workspace,key),data=fields)
    assert result.status_code==302 and result.location.endswith('/result')
    row=ExamSubmission.query.filter_by(exam_id=workspace.data['exams'][key]).one()
    assert row.total_score==10 and row.max_score==10 and len(row.answers)==22
