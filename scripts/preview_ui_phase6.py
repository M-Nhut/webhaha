"""Synthetic Phase 6 preview; no real DB, credentials or uploads are loaded.

python3 scripts/preview_ui_phase6.py --port 8768
Accounts qa_teacher, qa_admin, qa_student; password Academy123!
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
from scripts.preview_ui_phase5 import isolate_environment, isolate_phase5, seed_data as seed_imports


def seed_data(db):
    from models import (User, Enrollment, Exam, ExamQuestion, ExamAnswer, ExamSubmission,
                        SubmissionAnswer, ImportSession, PracticeSession, MasterySnapshot, DiagnosticAssignment)
    from services.standalone_assessment import save_paper
    from services.diagnostic_service import common_item_hash
    from services import practice_blueprint as blueprint
    data = seed_imports(db)
    teacher = db.session.get(User, data['users']['teacher'])
    for key, role in (('empty_teacher', 'teacher'), ('other_student', 'student')):
        row = User(username='qa_' + key, fullname='Tài khoản minh họa ' + key, user_code='QA-' + key, role=role, is_active=True)
        row.set_password('Academy123!'); db.session.add(row); db.session.flush()
        data['users'][key] = row.id
    db.session.add(Enrollment(course_id=data['courses']['teacher'], student_id=data['users']['other_student'], status='active'))
    fields = dict(title='Kiểm tra · Phương trình và xác suất', course_id=str(data['courses']['teacher']), duration_minutes='45',
        action='publish', reviewed='yes', budget_single='4', budget_true_false='4', budget_short_answer='2',
        q0_correct='0', q1_truth0='1', q1_truth1='0', q1_truth2='1', q1_truth3='0', q2_answer='5')
    for i, level in enumerate(('nhan_biet', 'thong_hieu', 'van_dung_cao')):
        fields.update({f'q{i}_report_category': ('Phép toán cơ bản', 'Nhận định về số', 'Tính giá trị')[i],
            f'q{i}_report_chapter': 'Chủ đề: Số và phép tính', f'q{i}_report_confirmed': 'yes', f'q{i}_difficulty_level': level})
    published = save_paper(db.session.get(ImportSession, data['sessions']['paper']), teacher, fields)
    published.shuffle_questions = False; published.shuffle_answers = False
    published.questions[0].context = 'Đọc dữ kiện và trả lời độc lập từng câu.'
    published.questions[0].image_url = '/qa/media/graph.svg'
    short_metadata = json.loads(published.questions[2].learning_metadata or '{}')
    short_metadata['short_answer'] = {'mode': 'numeric', 'tolerance': '0'}
    published.questions[2].learning_metadata = json.dumps(short_metadata)
    draft = save_paper(db.session.get(ImportSession, data['sessions']['bank-paper']), teacher,
        {**fields, 'title': 'Bản nháp · Cần bổ sung nhãn kiến thức', 'action': 'draft',
         'q0_report_confirmed': '', 'q1_report_confirmed': '', 'q2_report_confirmed': ''})
    data['exams'] = {'published': published.id, 'draft': draft.id}
    prototypes = list(published.questions)

    def copy_paper(key, *, purpose='standalone', active=True, count=3, fixed=False, owner=None, course=None):
        paper = Exam(title={'graded': 'Kết quả · Đúng, một phần, bỏ trống và sai', 'history': 'Bài làm lịch sử chưa chấm',
            'empty': 'Đề chưa có bài nộp', 'foreign': 'Đề thuộc lớp khác', 'closed': 'Đề đã đóng',
            'fixed': 'Bài luyện cá nhân · 22 câu', 'decision': 'Bài luyện · Chờ lựa chọn tiếp theo',
            'source_invalid': 'Bài luyện · Nguồn đã thay đổi', 'diagnostic': 'Đánh giá đầu vào · 22 câu',
            'diagnostic_done': 'Đánh giá đầu vào · Đã hoàn tất', 'legacy': 'Bài tự luyện lịch sử · 3 câu',
            'multi_history': 'Đáp án nhiều lựa chọn · Bài lưu trữ'}.get(key, key),
            course_id=course or data['courses']['teacher'], created_by=owner or teacher.id, duration_minutes=40 if fixed else 45,
            is_active=active, shuffle_questions=False, shuffle_answers=False,
            assessment_purpose=purpose, exam_type='practice' if purpose == 'practice' else 'exam')
        db.session.add(paper); db.session.flush()
        kinds = ['single'] * 12 + ['true_false'] * 4 + ['short_answer'] * 6 if fixed else [q.question_type for q in prototypes] + (['single'] if count == 4 else [])
        for index, kind in enumerate(kinds):
            source = next(q for q in prototypes if q.question_type == kind)
            code = blueprint.SKILLS[index % len(blueprint.SKILLS)]
            metadata = json.loads(source.learning_metadata or '{}')
            if fixed:
                metadata = ({'statements': [{'curriculum_code': code, 'cognitive_level': 'nhan_biet'} for _ in range(4)]}
                    if kind == 'true_false' else {'short_answer': {'mode': 'numeric', 'tolerance': '0'}} if kind == 'short_answer' else {})
            question = ExamQuestion(exam_id=paper.id, question_text=(f'Câu minh họa {index + 1}. ' if fixed else '') + source.question_text,
                context=source.context if index == 0 else None, image_url=source.image_url if index == 0 else None,
                question_type=kind, points=blueprint.POINTS[kind] if fixed else (2 if count == 4 and kind == 'single' else source.points),
                order_index=index, difficulty_level=source.difficulty_level, explanation=source.explanation,
                curriculum_code=code if fixed else source.curriculum_code, topic_snapshot=source.topic_snapshot,
                learning_metadata=json.dumps(metadata))
            db.session.add(question); db.session.flush()
            for answer in source.answers:
                db.session.add(ExamAnswer(question_id=question.id, answer_text=answer.answer_text, is_correct=answer.is_correct))
        if fixed:
            paper.adaptive_metadata = json.dumps({'student_id': data['users']['student'], 'aptga': {
                'version': blueprint.VERSION, 'algorithm_version': 'synthetic-preview', 'fresh_count': 16, 'repeated_count': 6,
                'quota_changes': 0, 'desired_quotas': {'nhan_biet': 8, 'thong_hieu': 7, 'van_dung': 5, 'van_dung_cao': 2},
                'actual_quotas': {'nhan_biet': 8, 'thong_hieu': 7, 'van_dung': 5, 'van_dung_cao': 2}},
                'explanation': 'Dữ liệu minh họa bố cục; không phải kết quả chạy thuật toán chọn câu.'})
        data['exams'][key] = paper.id
        db.session.flush()
        return paper

    graded = copy_paper('graded', count=4)
    history = copy_paper('history')
    copy_paper('empty')
    copy_paper('foreign', owner=data['users']['other'], course=data['courses']['foreign'])
    copy_paper('closed', active=False)
    fixed = copy_paper('fixed', purpose='practice', count=22, fixed=True)
    decision = copy_paper('decision', purpose='practice', count=22, fixed=True)
    invalid = copy_paper('source_invalid', purpose='practice', count=22, fixed=True)
    invalid.source_manifest = 'invalid-synthetic-manifest'
    diagnostic = copy_paper('diagnostic', purpose='initial_diagnostic', count=22, fixed=True, owner=data['users']['admin'])
    done = copy_paper('diagnostic_done', purpose='initial_diagnostic', count=22, fixed=True, owner=data['users']['admin'])
    copy_paper('legacy', purpose='practice')
    multi = copy_paper('multi_history', purpose='practice')
    multi.questions[0].question_type = 'multi'
    multi.questions[0].answers[1].is_correct = True
    data['submissions'] = {}

    def result(key, paper, *, graded=True):
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        row = ExamSubmission(exam_id=paper.id, student_id=data['users']['student'], exam_type=paper.exam_type,
            started_at=now-dt.timedelta(seconds=125), submitted_at=now, finalized_at=now if graded else None,
            is_graded=graded, status='graded' if graded else 'draft', grading_revision=1 if graded else 0,
            max_score=paper.total_points, total_score=0, time_spent_seconds=125)
        db.session.add(row); db.session.flush(); correct = 0
        for index, question in enumerate(paper.questions):
            kind = question.question_type; selected=[]; text=None; earned=0; state='answered'; full=False
            if kind in ('true_false', 'truefalse'):
                actual = {str(a.id): a.is_correct if i < 2 else not a.is_correct for i,a in enumerate(question.answers)}
                text=json.dumps(actual);selected=[a.id for a in question.answers if actual[str(a.id)]]
                earned=question.points*(.25 if paper.assessment_purpose != 'standalone' else .5)
            elif kind=='short_answer': text=json.dumps({'text': ''});state='unanswered'
            else:
                selected=[question.answers[0 if index==0 else 1].id];full=index==0;earned=question.points if full else 0
            answer=SubmissionAnswer(submission_id=row.id, question_id=question.id, selected_answer_ids=json.dumps(selected),
                answer_text=text, is_correct=full if graded else False, points_earned=earned if graded else 0,
                answer_status=state, time_spent_seconds=20, grading_revision=1 if graded else 0)
            db.session.add(answer);row.total_score+=earned if graded else 0;correct+=int(full and graded)
        row.correct_count=correct;row.wrong_count=len(paper.questions)-correct
        data['submissions'][key]=row.id
        db.session.flush()
        return row

    result('graded', graded);result('history', history, graded=False);result('multi_history', multi)
    for key, paper in (('fixed', fixed), ('decision', decision), ('source_invalid', invalid)):
        session=PracticeSession(student_id=data['users']['student'], course_id=paper.course_id, subject='Toán',
            bank_ids=json.dumps([data['banks']['shared']]), status='active' if key=='fixed' else 'awaiting_decision', last_exam_id=paper.id)
        db.session.add(session);db.session.flush()
        meta=paper.get_adaptive_metadata();meta['practice_session_id']=session.id;paper.adaptive_metadata=json.dumps(meta)
        if key!='fixed':
            submission=result(key,paper);session.last_submission_id=submission.id
            db.session.add(MasterySnapshot(student_id=data['users']['student'], subject='Toán', submission_id=submission.id, profile_data='{}'))
    for key, paper in (('diagnostic', diagnostic), ('diagnostic_done', done)):
        db.session.add(DiagnosticAssignment(exam_id=paper.id, student_id=data['users']['student'], assigned_by=data['users']['admin'],
            common_item_hash=common_item_hash(paper), status='assigned' if key=='diagnostic' else 'completed'))
        if key=='diagnostic_done':result(key,paper)
    db.session.commit()
    data['questions_by_exam']={key:[{'id':q.id,'kind':q.question_type,'answers':[{'id':a.id,'correct':a.is_correct} for a in q.answers]} for q in db.session.get(Exam,eid).questions] for key,eid in data['exams'].items()}
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8768);args=parser.parse_args()
    with TemporaryDirectory(prefix='linhedu-phase6-preview-') as directory:
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
        def graph():return Response('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="220" viewBox="0 0 480 220"><rect width="480" height="220" fill="white"/><path d="M40 160H440M60 200V20" stroke="#596579" stroke-width="2"/><path d="M90 45Q230 300 370 45" fill="none" stroke="#1d4ed8" stroke-width="3"/><text x="435" y="180" font-family="Arial" font-size="15">x</text></svg>',mimetype='image/svg+xml')
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        print(f'Synthetic Phase 6 preview http://127.0.0.1:{args.port}/login',flush=True)
        app.run(host='127.0.0.1',port=args.port,debug=False,use_reloader=False,threaded=False)


if __name__=='__main__':main()
