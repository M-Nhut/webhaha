"""Disposable Phase 8 preview. All identities, reports and credentials are synthetic.

python3 scripts/preview_ui_phase8.py --port 8770
qa_admin / qa_teacher / qa_student; password Academy123!
Provider calls are mocked; any other requests HTTP call fails closed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.preview_ui_phase7 import seed_data as seed_learning
from scripts.preview_ui_phase5 import isolate_environment, isolate_phase5


def isolate_phase8_environment(directory):
    isolate_environment(directory)
    from cryptography.fernet import Fernet
    os.environ['AI_CREDENTIAL_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
    os.environ['AI_LEGACY_ENV_FALLBACK_ENABLED'] = '0'
    os.environ['AI_ANALYSIS_API_URL'] = ''


def synthetic_analysis(self, packet, configuration=None):
    """Fixture annotations cite only actual evidence from the disposable packet."""
    def sections(events):
        wrong = [e for e in events if e.get('outcome') in ('wrong', 'partial')]
        if not wrong:
            return {k: [] for k in ('ai_summary', 'cause_hypotheses', 'next_risk_hypotheses', 'recommendations')}
        item = wrong[0]
        refs = [item.get('evidence_ref') or item['event_ref']]
        skill = item.get('curriculum_code')
        return {
            'ai_summary': [{'text': 'Dữ liệu minh họa ghi nhận câu trả lời cần đối chiếu lại điều kiện của biến cố.', 'basis_evidence_refs': refs}],
            'cause_hypotheses': [{'skill': skill, 'hypothesis': 'Học sinh có thể bỏ sót điều kiện khi xác định kết quả thuận lợi.', 'basis_evidence_refs': refs, 'validation': 'not_validated', 'verification_question': 'Em đã chọn kết quả thuận lợi theo điều kiện nào?'}],
            'next_risk_hypotheses': [{'skill': skill, 'hypothesis': 'Có thể lặp lại lỗi khi gặp bài cùng cách diễn đạt.', 'basis_evidence_refs': refs, 'affected_student_refs': [item.get('student_ref')], 'validation': 'not_validated', 'trigger_condition': 'Khi gặp câu tương tự.', 'verification_question': 'Em có thể liệt kê các kết quả thuận lợi?', 'suggested_remediation': 'Cho giải thích bằng sơ đồ và đối chiếu đáp án.'}],
            'recommendations': [{'skill': skill, 'text': 'Cho học sinh giải thích cách đếm trước khi tính xác suất.', 'basis_evidence_refs': refs, 'learning_goal': 'Xác định đúng kết quả thuận lợi.', 'teaching_strategy': 'Dùng ví dụ trực quan và câu hỏi gợi mở.', 'guiding_question': 'Điều kiện nào trong đề loại bỏ một kết quả?', 'suggested_practice': 'Hai câu tương tự có đổi điều kiện.', 'success_criteria': 'Giải thích đúng cả kết quả thuận lợi và không gian mẫu.'}],
        }
    students = {s['student_ref']: sections(s.get('events', [])) for s in packet.get('students', [])}
    events = [e for s in packet.get('students', []) for e in s.get('events', [])]
    return {'class_summary': sections(events), 'students': students}


@contextmanager
def synthetic_providers():
    with ExitStack() as stack:
        stack.enter_context(patch('services.ai_gateway.GeminiAIGateway._post_json', return_value={'ok': True}))
        stack.enter_context(patch('services.class_lesson4_report.ClassLesson4ReportService._run_ai', synthetic_analysis))
        stack.enter_context(patch('requests.sessions.Session.request', side_effect=RuntimeError('Outbound HTTP disabled in synthetic Phase 8 preview.')))
        yield


def seed_data(db):
    from models import (User, Course, Enrollment, TeacherAIKeyGroup, TeacherAIKey,
                        AIProjectCooldown, AIAnalysisRun)
    from services.ai_gateway import encrypt_credential, credential_fingerprint, _project_scope
    from services.class_lesson4_report import ClassLesson4ReportService

    data = seed_learning(db)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    teacher = db.session.get(User, data['users']['teacher'])
    teacher.position = 'Giáo viên Toán · Khối 9'
    teacher.phone = '0900000000'
    main = db.session.get(Course, data['courses']['teacher'])
    main.classroom = 'A.203'
    main.start_date, main.end_date = dt.date(2026, 9, 1), dt.date(2027, 5, 31)
    main.description = 'Củng cố kiến thức xác suất, đối chiếu bài làm và hỗ trợ từng học sinh theo dữ liệu đã chấm.'
    for key, fullname, role, active in (
        ('other_student', 'Nguyễn Hoàng Minh Anh · Tài khoản chưa có hoạt động', 'student', True),
        ('inactive_student', 'Trần Nguyễn Lê Hoàng Phương Anh · Hồ sơ tạm ngừng', 'student', False),
        ('ai_paused', 'Giáo viên có cấu hình AI đang tạm dừng', 'teacher', True),
    ):
        user = User(username='qa_'+key, user_code='QA-'+key, fullname=fullname, role=role, is_active=active)
        user.set_password('Academy123!'); db.session.add(user); db.session.flush()
        data['users'][key] = user.id
    for key, title, owner, active in (
        ('unassigned', 'Toán 9 · Lớp chờ phân công giáo viên', None, True),
        ('inactive', 'Toán 9 · Lớp đã kết thúc và lưu lại để đối chiếu kết quả học tập', teacher.id, False),
        ('long', 'Chuyên đề xác suất và thống kê dành cho học sinh lớp 9 · Nhóm bổ trợ buổi chiều', teacher.id, True),
    ):
        course = Course(course_name=title, subject='Toán', teacher_id=owner, is_active=active)
        db.session.add(course); db.session.flush(); data['courses'][key] = course.id
    db.session.add(Enrollment(student_id=data['users']['other_student'], course_id=main.id, status='inactive'))
    group = TeacherAIKeyGroup(owner_id=teacher.id, name='__teacher_internal_default__', is_default=True, is_active=True)
    db.session.add(group); db.session.flush()
    statuses = ['ok', 'deferred', 'invalid_or_revoked', 'permission_denied', 'quota_rate_limited',
                'network_unavailable', 'server_overloaded', 'model_not_found', 'malformed_response',
                'configuration_unavailable', 'provider_request_failed', 'ok']
    data['ai_keys'] = {}
    for index, status in enumerate(statuses):
        raw = f'phase8-synthetic-credential-{index:04d}-never-a-provider-key'
        key = TeacherAIKey(group_id=group.id, encrypted_key=encrypt_credential(raw),
            key_fingerprint=credential_fingerprint(raw), key_hint=f'QA{index:04d}',
            project_ref='qa-wait' if index == 11 else 'default', label=f'Khóa minh họa {index+1}',
            sort_order=index, is_paused=status == 'invalid_or_revoked',
            last_test_status=status if status in ('ok','deferred') else 'failed',
            last_error_code=None if status == 'ok' else 'verification_deferred' if status == 'deferred' else status,
            last_tested_at=None if status == 'deferred' else now - dt.timedelta(hours=index))
        db.session.add(key); db.session.flush(); data['ai_keys'][str(index)] = key.id
    db.session.add(AIProjectCooldown(scope_key=_project_scope(teacher.id, 'qa-wait'),
        cooldown_until=now + dt.timedelta(hours=2), reason_code='quota_rate_limited'))
    db.session.add(TeacherAIKeyGroup(owner_id=teacher.id, name='Nhóm cũ chỉ còn thông tin lịch sử', is_default=False))
    db.session.add(TeacherAIKeyGroup(owner_id=data['users']['ai_paused'], name='__teacher_internal_default__', is_default=True, is_active=False))
    db.session.commit()
    run, _, packet = ClassLesson4ReportService().generate(main, requested_by=teacher.id, allow_legacy=False, legacy_compatibility=False)
    assert run.status == 'completed', run.error_message
    data['reports'] = {'completed': run.id, 'event_count': packet['coverage']['event_count']}
    db.session.add(AIAnalysisRun(student_id=data['users']['student'], course_id=main.id,
        subject='Toán', chapter_code='8', input_hash='synthetic-personal-archive', provider='synthetic',
        model_name='synthetic-preview', prompt_version='synthetic', status='completed',
        schema_version='lesson4-diagnostic-report-v1', request_data='{}', response_data=json.dumps({
            'overall_diagnosis': 'Bản lưu minh họa: cần đối chiếu cách xác định kết quả thuận lợi.',
            'errors': [{'hypothesis': 'Có thể bỏ sót điều kiện của biến cố.', 'statement_label': 'Giả thuyết cần xác minh', 'evidence': []}],
            'interventions': ['Yêu cầu học sinh liệt kê kết quả trước khi áp dụng công thức.']}, ensure_ascii=False)))
    db.session.commit()
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8770)
    args = parser.parse_args()
    with TemporaryDirectory(prefix='linhedu-phase8-preview-') as directory:
        isolate_phase8_environment(directory)
        from app import app
        from database import db
        from flask import jsonify, Response
        from whitenoise import WhiteNoise
        isolate_phase5(app, directory)
        assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
        app.config.update(TESTING=False, WTF_CSRF_ENABLED=True, TEMPLATES_AUTO_RELOAD=True)
        app.jinja_env.auto_reload = True
        app.wsgi_app = WhiteNoise(app.wsgi_app, root=str(ROOT/'static'), prefix='static/', autorefresh=True, max_age=0)
        with synthetic_providers():
            with app.app_context(): data = seed_data(db)
            @app.get('/qa/fixture')
            def fixture(): return jsonify(data)
            @app.get('/qa/media/graph.svg')
            def graph():
                return Response('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="220"><rect width="480" height="220" fill="white"/><path d="M40 160H440M60 200V20" stroke="#596579"/><path d="M90 45Q230 300 370 45" fill="none" stroke="#1d4ed8" stroke-width="3"/></svg>', mimetype='image/svg+xml')
            logging.getLogger('werkzeug').setLevel(logging.ERROR)
            print(f'Synthetic Phase 8 preview http://127.0.0.1:{args.port}/login', flush=True)
            app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False, threaded=False)


if __name__ == '__main__': main()
