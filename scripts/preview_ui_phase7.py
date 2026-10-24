"""Synthetic Phase 7 learning preview; SQLite memory and temporary files only.

python3 scripts/preview_ui_phase7.py --port 8769
qa_admin / qa_teacher / qa_student; password Academy123!
Additional learner states are listed at /qa/fixture. No real accounts are read.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.preview_ui_phase5 import isolate_environment, isolate_phase5
from scripts.preview_ui_phase4 import seed_data as seed_banks


def seed_data(db):
    from adaptive_engine import AdaptiveEngine
    from models import (User, Course, Enrollment, QuestionBank, BankQuestion,
                        BankQuestionOption, CurriculumNode, Exam, ExamSubmission,
                        SubmissionAnswer, PracticeSession, DiagnosticAssignment,
                        MasterySnapshot)
    from routes.diagnostics import _copy_bank_questions
    from services import practice_blueprint as blueprint
    from services.diagnostic_service import common_item_hash
    from services.source_resolver import attach_source_manifest

    data = seed_banks(db)
    data.update(courses={}, exams={}, submissions={}, state_accounts={})
    teacher = db.session.get(User, data['users']['teacher'])
    admin = db.session.get(User, data['users']['admin'])
    other = db.session.get(User, data['users']['other'])
    course = Course.query.filter_by(teacher_id=teacher.id).one()
    data['courses']['teacher'] = course.id
    for key, label, subject, owner in [
        ('no_diagnostic', 'Toán 9 · Lớp chưa có đầu vào', 'Toán', teacher),
        ('blocked', 'Toán 9 · Lớp cần kiểm tra nguồn', 'Toán', teacher),
        ('english', 'Tiếng Anh · Lớp 9A', 'Tiếng Anh', teacher),
        ('foreign', 'Toán 9 · Lớp giáo viên khác', 'Toán', other),
        ('empty', 'Toán 9 · Lớp chưa có học sinh', 'Toán', teacher),
    ]:
        row = Course(course_name=label, subject=subject, teacher_id=owner.id, is_active=True)
        db.session.add(row); db.session.flush(); data['courses'][key] = row.id

    for key, name in [('cold','Học sinh mới'), ('no_course','Chưa có lớp'),
                      ('no_diagnostic','Chưa có đầu vào'), ('start','Sẵn sàng luyện tập'),
                      ('resume','Đang làm bài'), ('pending','Chờ lựa chọn tiếp theo'),
                      ('blocked','Nguồn chưa sẵn sàng'), ('one_point','Một bài đã chấm'),
                      ('declining','Cần củng cố thêm'), ('stable','Kết quả ổn định'),
                      ('empty_teacher','Giáo viên chưa có lớp')]:
        row = User(username='qa_'+key, user_code='QA-'+key, fullname=name,
                   role='teacher' if key=='empty_teacher' else 'student', is_active=True)
        row.set_password('Academy123!'); db.session.add(row); db.session.flush()
        data['users'][key] = row.id
        if key not in ('empty_teacher', 'no_course'):
            target = data['courses'].get(key, course.id) if key in ('no_diagnostic','blocked') else course.id
            db.session.add(Enrollment(student_id=row.id, course_id=target, status='active'))
        if row.role=='student': data['state_accounts'][key] = row.username
    for key in ('english','foreign'):
        db.session.add(Enrollment(student_id=data['users']['student'], course_id=data['courses'][key], status='active'))

    # A genuine eligible source pool for the manual wizard and selector. The
    # synthetic papers below are UI fixtures, not algorithm-evaluation results.
    bank = QuestionBank(name='Toán 9 · Bộ câu đầu vào và luyện tập', subject='Toán',
                        grade='9', created_by=teacher.id, visibility='private', is_active=True)
    db.session.add(bank); db.session.flush(); data['banks']['diagnostic'] = bank.id
    nodes = [db.session.get(CurriculumNode, nid) for nid in data['nodes']]
    by_type_skill = {}
    for skill_index, node in enumerate(nodes):
        for level in blueprint.LEVELS:
            for kind in blueprint.TYPE_QUOTAS:
                meta = ({'statements':[{'curriculum_code':node.canonical_code, 'cognitive_level':level} for _ in range(4)]}
                        if kind=='true_false' else {'short_answer':{'mode':'numeric','tolerance':'0'}} if kind=='short_answer' else {})
                question = BankQuestion(bank_id=bank.id, created_by=teacher.id, private_owner_id=teacher.id,
                    scope='private', subject='Toán', grade='9', chapter='8', section='i',
                    topic=node.category_name, question_category=node.category_name,
                    question_text=rf'{node.category_name}. Gieo một xúc xắc cân đối. Tính $P(A)$ khi $A$ có ba kết quả thuận lợi.',
                    context='Đọc dữ kiện chung và trả lời độc lập từng câu.' if skill_index==0 else None,
                    image_url='/qa/media/graph.svg' if skill_index==0 and kind=='single' else None,
                    question_type=kind, difficulty_level=level, curriculum_node_id=node.id,
                    classification_status='teacher_confirmed', learning_metadata=json.dumps(meta),
                    explanation=r'Có ba kết quả thuận lợi trong sáu kết quả: $P(A)=\frac{3}{6}=\frac{1}{2}$.')
                db.session.add(question); db.session.flush()
                answers = [('0.5',True)] if kind=='short_answer' else [
                    (r'$P(A)=1/2$',True),(r'$P(A)=1/3$',False),
                    (r'$P(A^c)=1/2$',kind=='true_false'),(r'$P(A)=1$',False)]
                for order,(text,correct) in enumerate(answers):
                    db.session.add(BankQuestionOption(question_id=question.id,option_text=text,is_correct=correct,order_index=order))
                by_type_skill.setdefault((kind,skill_index),[]).append(question)
    selected=[]
    for kind,count in blueprint.TYPE_QUOTAS.items():
        for index in range(count):selected.append(by_type_skill[kind,index%8][index//8])
    blocked = BankQuestion(bank_id=bank.id, created_by=teacher.id, private_owner_id=teacher.id,
        scope='private', subject='Toán', grade='9', question_text='Câu chưa được xác nhận phân loại.',
        question_type='single', curriculum_node_id=nodes[0].id, classification_status='needs_review')
    db.session.add(blocked); db.session.flush()
    data['wizard']={'bank_id':bank.id,'question_ids':[q.id for q in selected],
                    'blocked_question_id':blocked.id,'choices_count':97}
    now=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    def paper(key, *, learner=None, purpose='practice', active=True, target=None, owner=None):
        target=target or course; owner=owner or teacher
        metadata={'student_id':learner.id if learner else None,
            'explanation':'Bộ câu minh họa bố cục, dữ liệu và trạng thái. Không phải kết quả đánh giá thuật toán chọn câu.',
            'aptga':{'version':blueprint.VERSION,'algorithm_version':'synthetic-preview',
                'fresh_count':16,'repeated_count':6,'quota_changes':0,
                'desired_quotas':{'nhan_biet':18,'thong_hieu':4,'van_dung':0,'van_dung_cao':0},
                'actual_quotas':{'nhan_biet':18,'thong_hieu':4,'van_dung':0,'van_dung_cao':0}}}
        if purpose=='initial_diagnostic':metadata={'diagnostic':{'version':blueprint.VERSION,'selection_policy':'manual'}}
        row=Exam(title={'diagnostic':'Đánh giá đầu vào · Toán 9A','diagnostic_teacher':'Đầu vào lịch sử · Giáo viên tạo',
            'diagnostic_closed':'Đầu vào đã đóng','draft':'Bài luyện · Chờ duyệt và phát hành',
            'draft_locked':'Bài luyện · Đã có bài nộp','draft_invalid':'Bài luyện · Nguồn cần kiểm tra',
            'assigned':'Bài giáo viên giao · Xác suất','resume':'Bài luyện đang làm',
            'pending':'Bài luyện vừa hoàn tất','standalone':'Kiểm tra độc lập · Kết quả đối chiếu',
            'ungraded':'Bài lưu trữ · Chưa chấm'}.get(key,key),
            course_id=target.id, created_by=owner.id, question_bank_id=bank.id,
            exam_type='exam' if purpose in ('initial_diagnostic','standalone') else 'practice',
            assessment_purpose=purpose, is_active=active, duration_minutes=40,
            total_questions=22, shuffle_questions=False,shuffle_answers=False,
            adaptive_metadata=json.dumps(metadata,ensure_ascii=False))
        db.session.add(row);db.session.flush()
        pairs=_copy_bank_questions(row,selected);attach_source_manifest(row,target,pairs,bank_ids=[bank.id])
        if purpose=='practice':
            session=PracticeSession(student_id=learner.id,course_id=target.id,subject=target.subject,
                bank_ids=json.dumps([bank.id]),status='active' if active else 'draft',last_exam_id=row.id)
            db.session.add(session);db.session.flush()
            meta=row.get_adaptive_metadata();meta['practice_session_id']=session.id
            meta['practice_provenance']={'kind':'teacher_assigned' if owner.role=='teacher' else 'class_diagnostic',
                'teacher_id':target.teacher_id,'course_id':target.id}
            row.adaptive_metadata=json.dumps(meta,ensure_ascii=False)
        data['exams'][key]=row.id;return row

    diagnostic=paper('diagnostic',purpose='initial_diagnostic',owner=admin)
    paper('diagnostic_teacher',purpose='initial_diagnostic',active=False)
    paper('diagnostic_closed',purpose='initial_diagnostic',active=False,owner=admin)
    learner_keys=['student','cold','start','resume','pending','one_point','declining','stable']
    for key in learner_keys:
        db.session.add(DiagnosticAssignment(exam_id=diagnostic.id,student_id=data['users'][key],assigned_by=admin.id,
            common_item_hash=common_item_hash(diagnostic),status='assigned'))

    def finalize(key, exam, learner, correct_count=12, days_ago=0, graded=True):
        stamp=now-dt.timedelta(days=days_ago)
        sub=ExamSubmission(exam_id=exam.id,student_id=learner.id,exam_type=exam.exam_type,
            started_at=stamp-dt.timedelta(minutes=25),submitted_at=stamp,finalized_at=stamp if graded else None,
            status='graded' if graded else 'submitted',is_graded=graded,grading_revision=1 if graded else 0,
            total_score=0,max_score=10,time_spent_seconds=1500)
        db.session.add(sub);db.session.flush()
        for index,q in enumerate(exam.questions):
            correct=index<correct_count;kind=q.question_type
            if kind=='short_answer':text=json.dumps({'text':'0.5' if correct else '0'});ids=[]
            elif kind=='true_false':
                actual={str(a.id):a.is_correct if correct else not a.is_correct for a in q.answers}
                text=json.dumps(actual);ids=[a.id for a in q.answers if actual[str(a.id)]]
            else:text=None;ids=[next(a.id for a in q.answers if a.is_correct==correct)]
            earned=q.points if correct and graded else 0
            db.session.add(SubmissionAnswer(submission_id=sub.id,question_id=q.id,selected_answer_ids=json.dumps(ids),
                answer_text=text,answer_status='answered' if graded else 'pending_review',points_earned=earned,
                is_correct=correct and graded,time_spent_seconds=60,grading_revision=sub.grading_revision))
            sub.total_score+=earned
        sub.correct_count=min(correct_count,len(exam.questions)) if graded else 0
        sub.wrong_count=len(exam.questions)-sub.correct_count
        db.session.flush()
        if graded and exam.assessment_purpose!='standalone':
            AdaptiveEngine.update_performance(learner.id,sub,commit=False)
            snap=MasterySnapshot.query.filter_by(submission_id=sub.id).one();snap.created_at=stamp
        if exam.exam_type=='practice':
            session=db.session.get(PracticeSession,exam.get_adaptive_metadata().get('practice_session_id'))
            session.status='ended';session.last_submission_id=sub.id;session.ended_at=stamp
        data['submissions'][key]=sub.id;return sub

    for key in learner_keys:
        if key=='cold':continue
        learner=db.session.get(User,data['users'][key])
        finalize(key+'_diagnostic',diagnostic,learner,correct_count=4 if key=='student' else 22 if key=='declining' else 12,days_ago=8)
        assignment=DiagnosticAssignment.query.filter_by(exam_id=diagnostic.id,student_id=learner.id).one()
        assignment.status='completed';assignment.completed_at=now-dt.timedelta(days=8)
        counts=[8,16,22] if key=='student' else [22,16,4] if key=='declining' else [12,12,12] if key=='stable' else []
        for index,count in enumerate(counts):
            exam=paper(key+'_history_'+str(index),learner=learner,owner=learner)
            finalize(key+'_history_'+str(index),exam,learner,count,days_ago=6-index)

    for key in ('resume','pending'):
        learner=db.session.get(User,data['users'][key]);exam=paper(key,learner=learner,owner=learner)
        if key=='pending':
            sub=finalize('pending',exam,learner,18)
            session=db.session.get(PracticeSession,exam.get_adaptive_metadata()['practice_session_id'])
            session.status='awaiting_decision';session.ended_at=None
    student=db.session.get(User,data['users']['student'])
    paper('assigned',learner=student)
    draft=paper('draft',learner=student,active=False)
    locked=paper('draft_locked',learner=student)
    finalize('draft_locked',locked,student,16,days_ago=1)
    invalid=paper('draft_invalid',learner=student,active=False);invalid.source_manifest='{"version":"invalid-preview"}'
    standalone=paper('standalone',learner=student,purpose='standalone');finalize('standalone',standalone,student,22)
    ungraded=paper('ungraded',learner=student,purpose='standalone');finalize('ungraded',ungraded,student,0,graded=False)
    # Corrupt snapshots are explicit chart gaps, never synthetic 50% points.
    db.session.add(MasterySnapshot(student_id=student.id,subject='Toán',profile_data='{}',created_at=now))
    blocked_user=db.session.get(User,data['users']['blocked'])
    blocked_course=db.session.get(Course,data['courses']['blocked'])
    blocked_exam=paper('diagnostic_blocked',purpose='initial_diagnostic',target=blocked_course,owner=admin)
    db.session.add(DiagnosticAssignment(exam_id=blocked_exam.id,student_id=blocked_user.id,assigned_by=admin.id,
        common_item_hash=common_item_hash(blocked_exam),status='completed'))
    finalize('blocked',blocked_exam,blocked_user,12)
    blocked_exam.source_manifest='{"version":"invalid-preview"}'
    db.session.commit()
    data['questions_by_exam']={key:[{'id':q.id,'kind':q.question_type,'answers':[{'id':a.id,'correct':a.is_correct} for a in q.answers]} for q in db.session.get(Exam,eid).questions] for key,eid in data['exams'].items()}
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8769);args=parser.parse_args()
    with TemporaryDirectory(prefix='linhedu-phase7-preview-') as directory:
        isolate_environment(directory)
        from app import app
        from database import db
        from flask import jsonify, Response
        from whitenoise import WhiteNoise
        isolate_phase5(app,directory)
        assert app.config['SQLALCHEMY_DATABASE_URI']=='sqlite:///:memory:'
        app.config.update(TESTING=False,WTF_CSRF_ENABLED=True,TEMPLATES_AUTO_RELOAD=True)
        app.jinja_env.auto_reload=True
        app.wsgi_app=WhiteNoise(app.wsgi_app,root=str(ROOT/'static'),prefix='static/',autorefresh=True,max_age=0)
        with app.app_context():data=seed_data(db)
        @app.get('/qa/fixture')
        def fixture():return jsonify(data)
        @app.get('/qa/media/graph.svg')
        def graph():return Response('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="220" viewBox="0 0 480 220"><rect width="480" height="220" fill="white"/><path d="M40 160H440M60 200V20" stroke="#596579" stroke-width="2"/><path d="M90 45Q230 300 370 45" fill="none" stroke="#1d4ed8" stroke-width="3"/></svg>',mimetype='image/svg+xml')
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        print(f'Synthetic Phase 7 preview http://127.0.0.1:{args.port}/login',flush=True)
        app.run(host='127.0.0.1',port=args.port,debug=False,use_reloader=False,threaded=False)


if __name__=='__main__':main()
