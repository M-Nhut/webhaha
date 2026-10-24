"""Current-contract regression tests, isolated database and mocked AI only."""
import datetime as dt
import re
from html import unescape
from urllib.parse import parse_qs, urlsplit
from types import SimpleNamespace
from unittest.mock import patch
from tests.test_personalization_v2 import app, db, bank
from models import Enrollment, Exam, ExamQuestion, ExamSubmission, SubmissionAnswer, ErrorObservation, ClassAIAnalysisRun
from services.class_lesson4_report import ClassLesson4ReportService, build_class_lesson4_packet


def client_for(bank):
    db.session.add(Enrollment(student_id=bank.student.id,course_id=bank.course.id,status='active'));db.session.commit()
    client=app.test_client()
    with client.session_transaction() as state:
        state['_user_id']=str(bank.teacher.id);state['_fresh']=True
    return client


def test_empty_roster_member_and_legacy_link(bank):
    client=client_for(bank)
    response=client.get('/teacher/practice')
    assert response.status_code==200
    assert 'Chưa làm bài' in response.get_data(as_text=True)
    assert client.get('/analytics/teacher').status_code==302
    assert client.get(f'/teacher/practice/{bank.student.id}?course_id=99999').status_code==403


def test_learning_profile_links_to_student_report_without_writing_profile(bank):
    client=client_for(bank)
    exam=Exam(title='Regression',course_id=bank.course.id,created_by=bank.teacher.id)
    db.session.add(exam);db.session.flush()
    q=ExamQuestion(exam_id=exam.id,question_text='Test',question_type='single',points=1)
    attempt=ExamSubmission(exam_id=exam.id,student_id=bank.student.id,exam_type='practice',status='graded',is_graded=True,submitted_at=dt.datetime.utcnow())
    db.session.add_all([q,attempt]);db.session.flush()
    answer=SubmissionAnswer(submission_id=attempt.id,question_id=q.id,answer_status='graded',points_earned=0)
    db.session.add(answer);db.session.flush()
    db.session.add(ErrorObservation(student_id=bank.student.id,submission_id=attempt.id,submission_answer_id=answer.id,exam_question_id=q.id,subject='Toán',error_code='wrong',error_label='Sai đáp án',observed_claim='Cần đối chiếu',evidence_ref='e1'))
    db.session.commit()
    with patch('adaptive_engine.AdaptiveEngine.recompute_mastery',side_effect=AssertionError('Read route must not write mastery')):
        response=client.get(f'/teacher/practice/{bank.student.id}?course_id={bank.course.id}')
    assert response.status_code==200
    html = response.get_data(as_text=True)
    for removed in ('Xem kết quả theo dạng kiến thức', 'Lỗi quan sát từ bài đã chấm', 'Báo cáo AI theo lớp'):
        assert removed not in html
    links = [unescape(href) for href, content in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
             if 'Xem báo cáo AI' in re.sub(r'<[^>]+>', '', content)]
    assert len(links) == 1
    target = urlsplit(links[0])
    assert target.path == '/ai-reports/individual'
    assert parse_qs(target.query) == {'course_id': [str(bank.course.id)], 'student_id': [str(bank.student.id)], 'view': ['detail']}
    assert client.get(links[0]).status_code == 200


def test_force_preserves_completed_artifact_and_new_roster_changes_hash(bank):
    service=ClassLesson4ReportService()
    config=SimpleNamespace(provider='test',model_name='test',source='legacy_env')
    result={'class_summary':{'ai_summary':'Tổng hợp kiểm thử','cause_hypotheses':[],
                            'next_risk_hypotheses':[],'recommendations':[]},'students':{}}
    with patch.object(service,'_resolve_configuration',return_value=(config,None)), patch.object(service,'_identity_for',return_value=None), patch.object(service,'_run_ai',return_value=result) as api:
        first,_,_=service.generate(bank.course,requested_by=bank.teacher.id)
        assert first.status=='completed'
        saved_response=first.response_data
        again,cached,_=service.generate(bank.course,requested_by=bank.teacher.id)
        assert cached and again.id==first.id and api.call_count==1
        forced,cached,_=service.generate(bank.course,requested_by=bank.teacher.id,force=True)
        assert not cached and forced.id!=first.id and api.call_count==2
        db.session.refresh(first)
        assert first.status=='completed' and first.response_data==saved_response
        db.session.add(Enrollment(student_id=bank.student.id,course_id=bank.course.id,status='active'));db.session.commit()
        new,_,_=service.generate(bank.course,requested_by=bank.teacher.id)
        assert new.id!=first.id and new.input_hash!=first.input_hash and api.call_count==3
