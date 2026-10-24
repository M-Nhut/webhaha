"""Phase 8 integration contracts with CSRF, isolated storage and mocked AI."""
from __future__ import annotations

import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest
from flask import g, template_rendered, render_template
from scripts.preview_ui_phase8 import isolate_phase8_environment, isolate_phase5, seed_data, synthetic_providers

_storage = TemporaryDirectory(prefix='linhedu-phase8-tests-')
isolate_phase8_environment(_storage.name)
from app import app
from database import db
from models import (User, Course, Enrollment, DiagnosticAssignment, ClassAIAnalysisRun,
                    TeacherAIKey, LearningHistory, MasterySnapshot, Exam)


@pytest.fixture(scope='module')
def workspace():
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
    isolate_phase5(app, _storage.name)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    app.jinja_env.cache.clear()
    with synthetic_providers(), app.app_context():
        data = seed_data(db)
        yield SimpleNamespace(client=app.test_client(), data=data)
        db.session.remove()
        db.drop_all()


def csrf(response):
    html = response.get_data(as_text=True)
    match = re.search(r'name="csrf-token"[^>]*content="([^"]+)"', html) or re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    assert match
    return match.group(1)


def login(workspace, key='admin'):
    g.pop('_login_user', None)
    workspace.client.get('/logout')
    g.pop('_login_user', None)
    token = csrf(workspace.client.get('/login'))
    response = workspace.client.post('/login', data={'csrf_token': token, 'username': 'qa_'+key, 'password': 'Academy123!'})
    assert response.status_code == 302
    g.pop('_login_user', None)


def token(workspace):
    return csrf(workspace.client.get('/profile'))


def test_all_nine_screens_and_four_report_modes_are_read_only(workspace):
    data = workspace.data
    course, student = data['courses']['teacher'], data['users']['student']
    before = (ClassAIAnalysisRun.query.count(), Exam.query.count(), LearningHistory.query.count(), MasterySnapshot.query.count())
    for role, paths in [
        ('admin', ['/', '/courses', '/courses/new', f'/courses/{course}', f'/courses/{course}/edit', '/users/students', '/users/teachers', f'/users/{student}/edit']),
        ('teacher', ['/', '/courses', f'/courses/{course}', '/my-students', '/teacher/ai-settings']),
        ('student', ['/', '/courses', f'/courses/{course}']),
    ]:
        login(workspace, role)
        for path in paths:
            response = workspace.client.get(path, follow_redirects=path == '/my-students')
            assert response.status_code == 200, path
            html = response.get_data(as_text=True)
            assert 'style=' not in html and 'onchange=' not in html, path
    login(workspace, 'teacher')
    for scope in ('class', 'individual'):
        for view in ('', '&view=detail'):
            path = f'/ai-reports/{scope}?course_id={course}&student_id={student}{view}'
            assert workspace.client.get(path).status_code == 200
    assert before == (ClassAIAnalysisRun.query.count(), Exam.query.count(), LearningHistory.query.count(), MasterySnapshot.query.count())


def test_role_scope_and_csrf_boundaries(workspace):
    cid = workspace.data['courses']['teacher']
    for role in ('teacher', 'student'):
        login(workspace, role)
        fields = {'csrf_token': token(workspace)}
        for path in ('/courses/new', '/users/students', f'/users/{workspace.data["users"]["student"]}/edit'):
            response = workspace.client.get(path)
            assert response.status_code == 302 and response.headers['Location'].endswith('/')
        for path in ('/users', f'/courses/{cid}/delete', '/enrollments'):
            response = workspace.client.post(path, data=fields)
            assert response.status_code == 302 and response.headers['Location'].endswith('/')
    login(workspace, 'admin')
    assert workspace.client.get('/teacher/ai-settings').status_code == 403
    assert workspace.client.post(f'/courses/{cid}/lesson4-report/generate', json={}, headers={'X-CSRFToken': token(workspace)}).status_code == 403
    assert workspace.client.post('/users', data={'role': 'student'}).status_code == 400
    login(workspace, 'other')
    assert workspace.client.get(f'/api/ai-reports/{cid}').status_code == 403
    assert workspace.client.get(f'/courses/{cid}').status_code == 302
    login(workspace, 'other_student')
    assert workspace.client.get(f'/courses/{cid}').status_code == 302


def test_report_api_filters_scope_archive_and_null_are_preserved(workspace):
    login(workspace, 'teacher')
    cid, sid = workspace.data['courses']['teacher'], workspace.data['users']['student']
    response = workspace.client.get(f'/api/ai-reports/{cid}?analysis=1')
    assert response.status_code == 200
    assert 'no-store' in response.headers['Cache-Control']
    payload = response.json
    assert payload['status'] == 'completed'
    assert len(payload['evidence']) > 20
    assert payload['analysis']['causes'] and payload['analysis']['risks']
    assert payload['overview']['counts']['total'] > 100
    filtered = workspace.client.get(f'/api/ai-reports/{cid}?source=standalone&question_type=short_answer').json
    assert filtered['overview']['counts']['total'] < payload['overview']['counts']['total']
    person = workspace.client.get(f'/api/ai-reports/{cid}?student_id={sid}&analysis=1&include_archive=1').json
    assert person['personal_archive']['sections']['summary']
    assert person['overview']['counts']['total'] < payload['overview']['counts']['total']
    empty = workspace.client.get(f'/api/ai-reports/{cid}?student_id={workspace.data["users"]["cold"]}').json
    assert empty['overview']['counts']['correct_percent'] is None
    for query in ('skill=foreign', 'source=foreign', 'question_type=foreign'):
        assert workspace.client.get(f'/api/ai-reports/{cid}?{query}').status_code == 400
    assert workspace.client.get(f'/api/ai-reports/{cid}?student_id={workspace.data["users"]["other_student"]}').status_code == 404


def test_empty_directories_and_protected_admin_render(workspace):
    login(workspace, 'empty_teacher')
    for path in ('/', '/my-students', '/courses', '/ai-reports/class', '/teacher/ai-settings'):
        assert workspace.client.get(path, follow_redirects=path == '/my-students').status_code == 200
    login(workspace, 'admin')
    admin = db.session.get(User, workspace.data['users']['admin'])
    html = workspace.client.get(f'/users/{admin.id}/edit').get_data(as_text=True)
    assert 'data-people-form' not in html and 'reset-password' not in html
    before = (admin.username, admin.role, admin.password_hash)
    for path in (f'/users/{admin.id}/edit', f'/users/{admin.id}/delete', f'/users/{admin.id}/reset-password'):
        assert workspace.client.post(path, data={'csrf_token': token(workspace), 'role': 'student', 'password': 'forged'}).status_code == 302
    assert before == (admin.username, admin.role, admin.password_hash)
    captured = []
    def record(sender, template, context, **kwargs): captured.append(context)
    template_rendered.connect(record, app)
    try:
        workspace.client.get(f'/courses/{workspace.data["courses"]["empty"]}')
    finally:
        template_rendered.disconnect(record, app)
    context = dict(captured[-1]); context['available_students'] = []
    with app.test_request_context('/courses'):
        from flask_login import login_user
        login_user(admin)
        html = render_template('course_detail.html', **context)
    assert 'name="student_id"' not in html


def test_course_crud_transfer_and_legacy_ai_metadata_semantics(workspace):
    login(workspace, 'admin')
    fields = {'csrf_token': token(workspace), 'course_name': 'Lớp QA tạo thật trong RAM', 'subject': 'Toán', 'teacher_id': str(workspace.data['users']['teacher']), 'classroom': 'B.102', 'description': 'Nội dung QA', 'start_date': '2026-10-17', 'end_date': '2027-05-31', 'is_active': '1', 'ai_key_group_id': '999999'}
    assert workspace.client.post('/courses/new', data=fields).status_code == 302
    course = Course.query.filter_by(course_name=fields['course_name']).one()
    assert course.ai_key_group_id is None and course.classroom == 'B.102'
    group_id = TeacherAIKey.query.first().group_id
    course.ai_key_group_id = group_id; db.session.commit()
    assert workspace.client.post(f'/courses/{course.id}/edit', data=fields).status_code == 302
    assert course.ai_key_group_id == group_id
    fields.update(teacher_id=str(workspace.data['users']['other']), course_name='Đã đổi giáo viên')
    assert workspace.client.post(f'/courses/{course.id}/edit', data=fields).status_code == 302
    assert course.teacher_id == workspace.data['users']['other'] and course.ai_key_group_id is None
    assert workspace.client.post(f'/courses/{course.id}/delete', data={'csrf_token': token(workspace)}).status_code == 302
    assert db.session.get(Course, course.id) is None


def test_enrollment_reactivation_is_idempotent_and_assigns_existing_diagnostic(workspace):
    login(workspace, 'admin')
    cid, sid = workspace.data['courses']['teacher'], workspace.data['users']['other_student']
    enrollment = Enrollment.query.filter_by(course_id=cid, student_id=sid).one()
    assert enrollment.status == 'inactive'
    before = Enrollment.query.count()
    for _ in range(2):
        assert workspace.client.post('/enrollments', data={'csrf_token': token(workspace), 'course_id': str(cid), 'student_id': str(sid)}).status_code == 302
    assert enrollment.status == 'active' and Enrollment.query.count() == before
    assert DiagnosticAssignment.query.filter_by(student_id=sid, exam_id=workspace.data['exams']['diagnostic']).count() == 1


def test_user_create_edit_reset_delete_and_forged_role(workspace):
    login(workspace, 'admin')
    fields = {'csrf_token': token(workspace), 'role': 'admin', 'username': 'qa_created', 'user_code': 'QA-created', 'fullname': 'Người dùng QA'}
    count = User.query.count()
    assert workspace.client.post('/users', data=fields).status_code == 302
    assert User.query.count() == count
    fields['role'] = 'student'
    assert workspace.client.post('/users', data=fields).status_code == 302
    user = User.query.filter_by(username='qa_created').one()
    assert user.check_password('123456') and user.is_active
    fields.update(role='teacher', position='Giáo viên QA', phone='0900111222', is_active='1')
    assert workspace.client.post(f'/users/{user.id}/edit', data=fields).status_code == 302
    assert user.role == 'teacher' and user.position == 'Giáo viên QA'
    assert workspace.client.post(f'/users/{user.id}/reset-password', data={'csrf_token': token(workspace), 'password': 'Changed123!'}).status_code == 302
    assert user.check_password('Changed123!')
    uid = user.id
    assert workspace.client.post(f'/users/{uid}/delete', data={'csrf_token': token(workspace)}).status_code == 302
    assert db.session.get(User, uid) is None


def test_review_and_generation_change_annotations_without_changing_learning(workspace):
    login(workspace, 'teacher')
    cid = workspace.data['courses']['teacher']
    before = (LearningHistory.query.count(), MasterySnapshot.query.count())
    response = workspace.client.post(f'/courses/{cid}/lesson4-report/generate', json={'force': True}, headers={'X-CSRFToken': token(workspace)})
    assert response.status_code == 200
    run = ClassAIAnalysisRun.query.filter_by(course_id=cid).order_by(ClassAIAnalysisRun.id.desc()).first()
    assert run.status == 'completed'
    login(workspace, 'admin')
    response = workspace.client.post(f'/courses/{cid}/lesson4-report/{run.id}/review', json={'status': 'confirmed', 'review_note': 'Đã đối chiếu dữ liệu minh họa'}, headers={'X-CSRFToken': token(workspace)})
    assert response.status_code == 200 and run.review_status == 'confirmed'
    assert before == (LearningHistory.query.count(), MasterySnapshot.query.count())


def test_key_save_retry_delete_are_scoped_masked_and_use_only_mock_provider(workspace):
    login(workspace, 'teacher')
    raw = 'phase8-only-synthetic-new-credential'
    response = workspace.client.post('/teacher/ai-settings/keys', data={'csrf_token': token(workspace), 'keys': raw}, follow_redirects=True)
    assert response.status_code == 200 and raw not in response.get_data(as_text=True)
    key = TeacherAIKey.query.order_by(TeacherAIKey.id.desc()).first()
    assert key.last_test_status == 'ok' and raw not in key.encrypted_key
    login(workspace, 'other')
    assert workspace.client.post(f'/teacher/ai-settings/keys/{key.id}/retry', data={'csrf_token': token(workspace)}).status_code == 404
    login(workspace, 'teacher')
    assert workspace.client.post(f'/teacher/ai-settings/keys/{key.id}/retry', data={'csrf_token': token(workspace)}).status_code == 302
    kid = key.id
    assert workspace.client.post(f'/teacher/ai-settings/keys/{kid}/delete', data={'csrf_token': token(workspace)}).status_code == 302
    assert db.session.get(TeacherAIKey, kid) is None
