"""Phase 7 contracts against a disposable DB, real CSRF and synthetic sources."""
from __future__ import annotations

import datetime as dt
import json
import re
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest
from flask import g, template_rendered
from scripts.preview_ui_phase7 import isolate_environment, isolate_phase5, seed_data

_storage=TemporaryDirectory(prefix='linhedu-phase7-tests-')
isolate_environment(_storage.name)
from app import app
from database import db
from models import (BankQuestion, Course, DiagnosticAssignment, Enrollment, Exam, User,
                    ExamSubmission, LearningHistory, MasterySnapshot, PracticeSession)
from services.diagnostic_service import common_item_hash
from services import practice_blueprint as blueprint


@pytest.fixture
def workspace():
    assert app.config['SQLALCHEMY_DATABASE_URI']=='sqlite:///:memory:'
    isolate_phase5(app,_storage.name)
    app.config.update(TESTING=True,WTF_CSRF_ENABLED=True)
    app.jinja_env.cache.clear()
    with app.app_context():
        data=seed_data(db)
        yield SimpleNamespace(client=app.test_client(),data=data)
        db.session.remove();db.drop_all()


def csrf(response):
    html=response.get_data(as_text=True)
    match=re.search(r'name="csrf-token"[^>]*content="([^"]+)"',html) or re.search(r'name="csrf_token"[^>]*value="([^"]+)"',html)
    assert match
    return match.group(1)


def login(workspace,key='student'):
    g.pop('_login_user',None);workspace.client.get('/logout');g.pop('_login_user',None)
    token=csrf(workspace.client.get('/login'))
    response=workspace.client.post('/login',data={'csrf_token':token,'username':'qa_'+key,'password':'Academy123!'})
    assert response.status_code==302
    g.pop('_login_user',None)


@contextmanager
def contexts():
    result=[]
    def record(sender,template,context,**kwargs):result.append((template.name,context))
    template_rendered.connect(record,app)
    try:yield result
    finally:template_rendered.disconnect(record,app)


def get_context(workspace,path):
    with contexts() as captured:response=workspace.client.get(path)
    assert response.status_code==200
    return response,captured[-1][1]


def wizard_fields(workspace):
    return {'csrf_token':csrf(workspace.client.get('/diagnostics/new')),
            'question_bank_id':str(workspace.data['wizard']['bank_id']),
            'question_ids':[str(qid) for qid in workspace.data['wizard']['question_ids']]}


def reviewed_fields(workspace):
    fields=wizard_fields(workspace)
    review=workspace.client.post('/api/diagnostics/review',data=fields)
    assert review.status_code==200
    return {**fields,'review_digest':review.json['review_digest'],'confirmed':'yes',
            'course_id':str(workspace.data['courses']['teacher']),'title':'Đầu vào đã kiểm duyệt'}


def test_seven_screens_render_for_authorized_roles_without_creating_papers(workspace):
    before=(Exam.query.count(),DiagnosticAssignment.query.count(),LearningHistory.query.count(),MasterySnapshot.query.count())
    for role,paths in [
        ('admin',['/diagnostics','/diagnostics/new']),
        ('teacher',['/diagnostics','/teacher/practice',f"/teacher/practice/{workspace.data['users']['student']}?course_id={workspace.data['courses']['teacher']}",
                    f"/teacher/practice/drafts/{workspace.data['exams']['draft']}"]),
        ('student',['/practice','/practice/progress?subject=Toán'])]:
        login(workspace,role)
        for path in paths:assert workspace.client.get(path).status_code==200,path
    assert before==(Exam.query.count(),DiagnosticAssignment.query.count(),LearningHistory.query.count(),MasterySnapshot.query.count())


def test_diagnostic_authoring_stays_admin_only_and_requires_csrf(workspace):
    for role in ('teacher','student'):
        login(workspace,role)
        token=csrf(workspace.client.get('/profile'))
        assert workspace.client.get('/diagnostics/new').status_code==403
        assert workspace.client.post('/diagnostics/new',data={'csrf_token':token}).status_code==403
        assert workspace.client.get('/api/diagnostics/question-choices?question_bank_id='+str(workspace.data['wizard']['bank_id'])).status_code==403
        assert workspace.client.post('/api/diagnostics/review',data={'csrf_token':token}).status_code==403
    login(workspace,'admin')
    assert workspace.client.post('/api/diagnostics/review',data={}).status_code==400
    assert workspace.client.post('/diagnostics/new',data={}).status_code==400


def test_diagnostic_choices_are_paginated_and_answers_lazy(workspace):
    login(workspace,'admin');bank=workspace.data['wizard']['bank_id'];records=[]
    for page in range(1,5):
        response=workspace.client.get(f'/api/diagnostics/question-choices?question_bank_id={bank}&page={page}')
        assert response.status_code==200 and response.headers['Cache-Control']=='private, no-store'
        assert len(response.json['questions'])<=25
        records.extend(response.json['questions'])
    assert len(records)==97 and len({q['id'] for q in records})==97
    blocked=next(q for q in records if q['id']==workspace.data['wizard']['blocked_question_id'])
    assert not blocked['selectable'] and blocked['blocked_reason']
    for q in records:assert 'options' not in q and 'explanation' not in q
    detail=workspace.client.get(next(q['detail_url'] for q in records if q['selectable']))
    assert detail.status_code==200 and detail.json['question']['options']


def test_review_is_read_only_and_confirm_freezes_exact_paper_for_active_cohort(workspace):
    login(workspace,'admin');before=(Exam.query.count(),DiagnosticAssignment.query.count())
    fields=reviewed_fields(workspace)
    assert before==(Exam.query.count(),DiagnosticAssignment.query.count())
    response=workspace.client.post('/diagnostics/new',data={**fields,'duration_minutes':'5','total_questions':'1','shuffle_answers':'1'})
    assert response.status_code==200 and response.json['success']
    paper=db.session.get(Exam,response.json['exam_id'])
    assert [q.bank_question_id for q in paper.questions]==workspace.data['wizard']['question_ids']
    assert paper.question_count==22 and paper.duration_minutes==40 and paper.total_points==10
    assert not paper.shuffle_questions and not paper.shuffle_answers and paper.created_by==workspace.data['users']['admin']
    assert {q.curriculum_code for q in paper.questions}==set(blueprint.SKILLS)
    cohort=DiagnosticAssignment.query.filter_by(exam_id=paper.id).all()
    assert len(cohort)==Enrollment.query.filter_by(course_id=paper.course_id,status='active').count()
    assert {a.common_item_hash for a in cohort}=={common_item_hash(paper)}


def test_publish_rejects_stale_digest_unconfirmed_or_incompatible_class(workspace):
    login(workspace,'admin');fields=reviewed_fields(workspace);before=Exam.query.count()
    for changes in ({'review_digest':'stale'},{'confirmed':''},{'course_id':str(workspace.data['courses']['foreign'])}):
        response=workspace.client.post('/diagnostics/new',data={**fields,**changes})
        assert response.status_code==400 and not response.json['success']
    question=db.session.get(BankQuestion,workspace.data['wizard']['question_ids'][0])
    question.question_text+=' Nội dung đã thay đổi.';db.session.commit()
    assert workspace.client.post('/diagnostics/new',data=fields).status_code==400
    assert Exam.query.count()==before


def test_review_rejects_duplicates_blocked_and_missing_skills(workspace):
    login(workspace,'admin');fields=wizard_fields(workspace);ids=fields['question_ids']
    for invalid in (ids[:21],ids[:21]+[ids[0]],ids[:21]+[str(workspace.data['wizard']['blocked_question_id'])]):
        response=workspace.client.post('/api/diagnostics/review',data={**fields,'question_ids':invalid})
        assert response.status_code==400 and not response.json['success']


def test_home_next_step_is_server_state_not_a_second_generate_button(workspace):
    for role,state in [('cold','diagnostic'),('no_diagnostic','diagnostic'),('start','generate'),('resume','resume'),('pending','decision'),('blocked','source-unavailable')]:
        login(workspace,role);response=workspace.client.get('/practice');html=response.get_data(as_text=True)
        assert response.status_code==200 and f'data-practice-next="{state}"' in html
        if state!='generate':assert 'action="/practice/generate"' not in html
    login(workspace,'no_course');html=workspace.client.get('/practice').get_data(as_text=True)
    assert 'Chưa có lớp học' in html and 'action="/practice/generate"' not in html


def test_progress_keeps_ungraded_and_missing_values_distinct_from_zero(workspace):
    login(workspace)
    response,context=get_context(workspace,'/practice/progress?subject=Toán')
    pending=next(h for h in context['history'] if h['exam_id']==workspace.data['exams']['ungraded'])
    standalone=next(h for h in context['history'] if h['exam_id']==workspace.data['exams']['standalone'])
    assert pending['score'] is None and not pending['is_graded'] and pending['result_url'].startswith('/assessments/')
    assert standalone['score']==10 and standalone['purpose']=='standalone'
    stored=db.session.get(ExamSubmission,workspace.data['submissions']['standalone'])
    stored.max_score=0;db.session.commit()
    missing_page,missing=get_context(workspace,'/practice/progress?subject=Toán')
    assert 'Chưa có thang điểm' in missing_page.get_data(as_text=True)
    assert next(h for h in missing['history'] if h['exam_id']==stored.exam_id)['score'] is None
    assert any(h['mastery'] is None for h in context['mastery_history'])
    assert 'Chưa chấm' in response.get_data(as_text=True)
    assert all(h['result_url'] for h in context['history'])
    snapshot=MasterySnapshot.query.filter_by(student_id=workspace.data['users']['student'],submission_id=None).one()
    for invalid in ('{}','[]','{"overall_mastery":"bad"}','{"overall_mastery":true}','{"overall_mastery":1.5}','{"overall_mastery":"NaN"}'):
        snapshot.profile_data=invalid;db.session.commit()
        _,context=get_context(workspace,'/practice/progress?subject=Toán')
        assert next(h for h in context['mastery_history'] if h['snapshot_id']==snapshot.id)['mastery'] is None
    snapshot.profile_data='{"overall_mastery":0}';db.session.commit()
    _,context=get_context(workspace,'/practice/progress?subject=Toán')
    assert next(h for h in context['mastery_history'] if h['snapshot_id']==snapshot.id)['mastery']==0
    login(workspace,'teacher')
    html=workspace.client.get(f"/teacher/practice/{workspace.data['users']['student']}?course_id={workspace.data['courses']['teacher']}").get_data(as_text=True)
    assert 'Chưa có thang điểm' in html and 'None/10' not in html


def test_empty_progress_is_neutral_and_assets_are_local(workspace):
    login(workspace,'cold');html=workspace.client.get('/practice/progress?subject=Toán').get_data(as_text=True)
    assert 'Chưa có bằng chứng' in html and 'Chưa đủ dữ liệu' in html
    assert 'Chưa có dữ liệu' in html and 'cdn.jsdelivr' not in html and 'vendor/chartjs/chart.umd.js' in html
    assert '<canvas id="scoreChart"' not in html


def test_teacher_scope_and_nullable_average_are_preserved(workspace):
    login(workspace,'teacher');_,context=get_context(workspace,'/teacher/practice?course_id='+str(workspace.data['courses']['teacher']))
    empty=next(row for row in context['students'] if row['student'].id==workspace.data['users']['cold'])
    main=next(row for row in context['students'] if row['student'].id==workspace.data['users']['student'])
    assert empty['average'] is None and empty['completed']==0
    assert main['total_assessments']==1 and main['total_practice']>=3
    foreign=workspace.data['courses']['foreign']
    assert workspace.client.get('/teacher/practice?course_id='+str(foreign)).status_code==403
    assert workspace.client.get(f"/teacher/practice/{workspace.data['users']['student']}?course_id={foreign}").status_code==403
    assert workspace.client.get('/analytics/teacher').status_code==302


def test_merged_student_roster_deduplicates_and_preserves_class_scope(workspace):
    login(workspace, 'teacher')
    sid = workspace.data['users']['student']
    cid = workspace.data['courses']['teacher']
    english = workspace.data['courses']['english']
    student = db.session.get(User, sid)
    student.phone = '0900123456'
    student.position = 'Lớp 9A'
    foreign_only = User(username='merge_foreign_only', user_code='MERGE-FOREIGN',
                        fullname='Học sinh của giáo viên khác', role='student')
    db.session.add(foreign_only)
    db.session.flush()
    db.session.add(Enrollment(student_id=foreign_only.id, course_id=workspace.data['courses']['foreign'], status='active'))
    inactive_membership = Course(course_name='Lớp không ghi danh', subject='Toán', teacher_id=workspace.data['users']['teacher'])
    db.session.add(inactive_membership)
    db.session.flush()
    for course_id, score in ((english, 10), (workspace.data['courses']['foreign'], 1), (inactive_membership.id, 1)):
        exam = Exam(title='Merge scope check', course_id=course_id, created_by=workspace.data['users']['teacher'],
                    exam_type='practice', assessment_purpose='adaptive_practice')
        db.session.add(exam)
        db.session.flush()
        db.session.add(ExamSubmission(exam_id=exam.id, student_id=sid, exam_type='practice', status='graded',
                                     is_graded=True, total_score=score, max_score=10,
                                     submitted_at=dt.datetime.utcnow()))
    db.session.commit()
    _, scoped = get_context(workspace, f'/teacher/practice?course_id={cid}')
    main = next(row for row in scoped['students'] if row['student'].id == sid)
    assert len([row for row in scoped['students'] if row['student'].id == sid]) == 1
    response, combined = get_context(workspace, '/teacher/practice')
    assert combined['selected_course'] is None
    assert foreign_only.id not in {row['student'].id for row in combined['students']}
    merged = next(row for row in combined['students'] if row['student'].id == sid)
    assert {course.id for course in merged['courses']} == {cid, english}
    assert merged['total_practice'] == main['total_practice'] + 1
    assert merged['completed'] == main['completed'] + 1
    html = response.get_data(as_text=True)
    assert '0900123456' in html and 'Lớp 9A' in html and student.user_code in html
    nav = html.split('<aside class="sidebar"', 1)[1].split('</aside>', 1)[0]
    assert nav.count('aria-label="Học sinh của tôi"') == 1
    assert 'aria-label="Theo dõi học tập"' not in nav
    legacy = workspace.client.get(f'/my-students?course_id={cid}')
    assert legacy.status_code == 302
    assert legacy.headers['Location'].endswith(f'/teacher/practice?course_id={cid}')
    assert workspace.client.get('/my-students?course_id='+str(workspace.data['courses']['foreign']), follow_redirects=True).status_code == 403


def draft_url(workspace,key='draft'):
    return f"/teacher/practice/drafts/{workspace.data['exams'][key]}"


def test_draft_context_reports_lock_source_and_current_class_authority(workspace):
    login(workspace,'teacher')
    for key,locked,valid in [('draft',False,True),('draft_locked',True,True),('draft_invalid',False,False)]:
        response,context=get_context(workspace,draft_url(workspace,key))
        assert context['draft_locked']==locked and context['draft_source_valid']==valid and context['draft_can_publish']
        assert len(context['exam'].questions)==22
        if locked:assert 'disabled' in response.get_data(as_text=True)


def test_native_release_updates_only_release_fields_and_rejects_locked_or_invalid_source(workspace):
    login(workspace,'teacher');paper=db.session.get(Exam,workspace.data['exams']['draft'])
    frozen=common_item_hash(paper);manifest=paper.source_manifest
    fields={'csrf_token':csrf(workspace.client.get(draft_url(workspace))),'title':'Bài luyện đã duyệt','duration_minutes':'50','is_active':'on'}
    response=workspace.client.post(draft_url(workspace),data=fields)
    assert response.status_code==302
    db.session.refresh(paper)
    assert paper.title=='Bài luyện đã duyệt' and paper.duration_minutes==50 and paper.is_active
    assert common_item_hash(paper)==frozen and paper.source_manifest==manifest and paper.question_count==22
    for key in ('draft_locked','draft_invalid'):
        blocked=db.session.get(Exam,workspace.data['exams'][key]);before=(blocked.title,blocked.duration_minutes,blocked.is_active)
        fields['csrf_token']=csrf(workspace.client.get(draft_url(workspace,key)))
        assert workspace.client.post(draft_url(workspace,key),data=fields).status_code==302
        db.session.refresh(blocked);assert before==(blocked.title,blocked.duration_minutes,blocked.is_active)


def test_generate_resumes_or_returns_to_decision_without_duplicate_papers(workspace):
    for role,key,action in [('resume','resume','take'),('pending','pending','result')]:
        login(workspace,role);before=Exam.query.count()
        response=workspace.client.post('/practice/generate',data={'csrf_token':csrf(workspace.client.get('/practice')),'course_id':str(workspace.data['courses']['teacher'])})
        assert response.status_code==302 and response.location.endswith(f"/{workspace.data['exams'][key]}/{action}")
        assert Exam.query.count()==before


def test_generate_student_and_teacher_create_real_fixed_papers_without_expanding_sources(workspace):
    login(workspace,'start');before=Exam.query.count()
    fields={'csrf_token':csrf(workspace.client.get('/practice')),'course_id':str(workspace.data['courses']['teacher'])}
    response=workspace.client.post('/practice/generate',data=fields)
    assert response.status_code==302 and response.location.endswith('/take')
    assert Exam.query.count()==before+1
    paper=db.session.get(Exam,int(response.location.split('/')[-2]))
    assert paper.question_count==22 and paper.duration_minutes==40 and paper.total_points==10
    assert paper.question_bank_id==workspace.data['wizard']['bank_id']
    login(workspace,'teacher')
    path=f"/teacher/practice/{workspace.data['users']['start']}/generate"
    fields={'csrf_token':csrf(workspace.client.get('/teacher/practice')),'course_id':str(workspace.data['courses']['teacher']),
            'bank_ids':[str(workspace.data['wizard']['bank_id'])],'mix_weak':'60','mix_middle':'25','mix_strong':'15',
            'cognitive_levels':list(blueprint.LEVELS)}
    response=workspace.client.post(path,data=fields)
    assert response.status_code==302 and '/draft' in response.location
    generated=db.session.get(Exam,int(response.location.rsplit('/',1)[-1]))
    assert generated.question_count==22 and not generated.is_active
    assert generated.created_by==workspace.data['users']['teacher']


def test_continue_uses_current_source_and_rejects_replayed_old_decision(workspace):
    login(workspace,'pending');sid=workspace.data['submissions']['pending']
    result=f"/practice/{workspace.data['exams']['pending']}/result"
    fields={'csrf_token':csrf(workspace.client.get(result))}
    response=workspace.client.post(f'/practice/submissions/{sid}/continue',data=fields)
    assert response.status_code==302 and response.location.endswith('/take')
    before=Exam.query.count()
    assert workspace.client.post(f'/practice/submissions/{sid}/continue',data=fields).status_code==403
    assert Exam.query.count()==before
    new_exam=db.session.get(Exam,int(response.location.split('/')[-2]))
    assert new_exam.question_count==22 and new_exam.question_bank_id==workspace.data['wizard']['bank_id']
    session=db.session.get(PracticeSession,new_exam.get_adaptive_metadata()['practice_session_id'])
    assert session.status=='active'


def test_end_decision_preserves_result_and_does_not_create_another_paper(workspace):
    login(workspace,'pending');sid=workspace.data['submissions']['pending']
    exam=db.session.get(Exam,workspace.data['exams']['pending'])
    session=db.session.get(PracticeSession,exam.get_adaptive_metadata()['practice_session_id'])
    fields={'csrf_token':csrf(workspace.client.get(f'/practice/{exam.id}/result'))}
    before=Exam.query.count()
    response=workspace.client.post(f'/practice/submissions/{sid}/end',data=fields)
    assert response.status_code==302 and '/practice/progress' in response.location
    db.session.refresh(session);assert session.status=='ended' and session.ended_at
    assert workspace.client.post(f'/practice/submissions/{sid}/end',data=fields).status_code==302
    assert Exam.query.count()==before
    assert workspace.client.get(f'/practice/{exam.id}/result').status_code==200
