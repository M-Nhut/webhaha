"""Teacher-reviewed, unclassified class papers, separate from adaptive practice."""
from flask import abort, flash, redirect, render_template, request, url_for, jsonify, send_file, current_app
from flask_login import current_user, login_required
from database import db
from models import Course, Enrollment, Exam, ImportSession, QuestionBank, CurriculumNode
from services.standalone_assessment import PURPOSE, authorized_course, editable_text, review_errors, save_paper
from services.assessment_scoring import KINDS, kind_of, section_defaults


def _section_values(form, prefix, convert=str):
    """Preserve legacy forms that do not supply per-section controls."""
    if not any(f'{prefix}_{kind}' in form for kind in KINDS):
        return None
    try:
        return {kind: convert(form.get(f'{prefix}_{kind}', '0')) for kind in KINDS}
    except ValueError:
        raise ValueError('Số câu của từng hình thức phải là số nguyên.') from None


@login_required
def assessment_from_bank():
    if current_user.role not in ('teacher', 'admin'):
        abort(403)
    from services.assessment_bank import question_pool, create_bank_draft, formula_assets
    from services.source_resolver import resolve_class_banks
    courses = Course.query.filter_by(is_active=True)
    if current_user.role == 'teacher':
        courses = courses.filter_by(teacher_id=current_user.id)
    courses = courses.order_by(Course.course_name).all()
    params = request.form if request.method == 'POST' else request.args
    course_id = params.get('course_id', type=int)
    try:
        course = authorized_course(course_id, current_user) if course_id else None
    except (PermissionError, ValueError):
        abort(403)
    banks = [bank for bank in QuestionBank.query.filter_by(is_active=True).all()
             if course and resolve_class_banks(course, [bank.id], require_grade=False)['valid']]
    bank_ids = params.getlist('bank_ids', type=int)
    questions = []
    try:
        if course and bank_ids:
            questions = question_pool(course, bank_ids)
        if request.method == 'POST':
            if not course or not bank_ids:
                raise ValueError('Chọn lớp học và ít nhất một ngân hàng.')
            quantity = request.form.get('quantity', type=int)
            automatic = request.form.get('mode') == 'auto'
            counts = _section_values(request.form, 'count', convert=int) if automatic else None
            budgets = _section_values(request.form, 'budget')
            if request.form.get('mode') == 'auto' and quantity is None and counts is None:
                raise ValueError('Nhập số câu là số nguyên.')
            session = create_bank_draft(current_user, course, bank_ids,
                selected_ids=request.form.getlist('question_ids'),
                quantity=quantity if request.form.get('mode') == 'auto' else None, counts=counts, budgets=budgets)
            return redirect(url_for('assessment_import', session_id=session.id))
    except PermissionError:
        abort(403)
    except ValueError as exc:
        flash(str(exc), 'danger')
    from services.access_control import question_source_label
    return render_template('assessment_from_bank.html', courses=courses, course=course,
                           banks=banks, bank_ids=bank_ids, questions=questions,
                           kinds=KINDS, available={kind: sum(kind_of(q.question_type) == kind for q in questions) for kind in KINDS},
                           formulas=formula_assets([q.to_dict() for q in questions]),
                           question_sources={q.id: question_source_label(current_user, q, bank=q.bank) for q in questions})


@login_required
def assessment_list():
    query = Exam.query.filter_by(assessment_purpose=PURPOSE)
    if current_user.role == 'student':
        enrolled = db.session.query(Enrollment.course_id).filter_by(student_id=current_user.id, status='active')
        query = query.filter(Exam.course_id.in_(enrolled), Exam.is_active.is_(True))
    elif current_user.role == 'teacher':
        query = query.join(Course).filter(Course.teacher_id == current_user.id)
    elif current_user.role != 'admin':
        abort(403)
    return render_template('assessment_list.html', exams=query.order_by(Exam.created_at.desc()).all())


@login_required
def assessment_import(session_id):
    if current_user.role not in ('teacher', 'admin'):
        abort(403)
    if request.method == 'POST':
        from services.import_transactions import lock_import_transaction
        lock_import_transaction()
    session = db.session.get(ImportSession, session_id) or abort(404)
    if session.user_id != current_user.id:
        abort(403)
    if (session.get_scope() or {}).get('document_kind') != 'assessment':
        abort(404)
    if request.method == 'POST':
        try:
            exam = save_paper(session, current_user, request.form)
            if request.accept_mimetypes.best == 'application/json':
                return jsonify(success=True, exam_id=exam.id, message='Đã giao đề cho lớp.' if exam.is_active else 'Đã lưu tất cả chỉnh sửa.',
                               matrix_url=url_for('assessment_matrix', exam_id=exam.id),
                               redirect_url=url_for('assessment_list') if exam.is_active else None)
            flash('Đã giao đề cho lớp.' if exam.is_active else 'Đã lưu bản nháp. Học sinh chưa nhìn thấy đề.', 'success')
            return redirect(url_for('assessment_list') if exam.is_active else url_for('assessment_import', session_id=session.id))
        except PermissionError:
            db.session.rollback()
            abort(403)
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            if request.accept_mimetypes.best == 'application/json':
                return jsonify(success=False, message=str(exc)), 400
            flash(str(exc), 'danger')
    query = Course.query.filter_by(is_active=True)
    if current_user.role == 'teacher':
        query = query.filter_by(teacher_id=current_user.id)
    exam = db.session.get(Exam, session.get_scope().get('exam_id')) if session.get_scope().get('exam_id') else None
    if exam:
        try:
            authorized_course(exam.course_id, current_user)
        except (PermissionError, ValueError):
            abort(403)
        if exam.is_active or exam.submissions:
            return redirect(url_for('assessment_result', exam_id=exam.id))
    questions = session.get_parsed_questions()
    counts, defaults = section_defaults(questions)
    return render_template('assessment_import.html', session=session, exam=exam, questions=questions,
                           kinds=KINDS, section_counts=counts, section_points=defaults,
                           courses=query.order_by(Course.course_name).all(), issues=review_errors(questions),
                           editable_text=editable_text, report_nodes=CurriculumNode.query.filter_by(is_active=True).order_by(CurriculumNode.canonical_code).all())


@login_required
def assessment_matrix(exam_id):
    if current_user.role not in ('teacher', 'admin'):
        abort(403)
    exam = db.session.get(Exam, exam_id) or abort(404)
    if exam.assessment_purpose != PURPOSE:
        abort(404)
    if current_user.role == 'teacher' and exam.course.teacher_id != current_user.id:
        abort(403)
    from services.assessment_matrix import build_matrix
    try:
        matrix = build_matrix(exam)
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('assessment_list'))
    if request.args.get('download') == 'xlsx':
        from services.matrix_xlsx import export_matrix
        response = send_file(export_matrix(matrix), as_attachment=True,
                             download_name=f'ma-tran-de-{exam.id}.xlsx',
                             mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        response = current_app.make_response(render_template('assessment_matrix.html', exam=exam, matrix=matrix))
    response.headers['Cache-Control'] = 'private, no-store'
    return response


def register_assessment_routes(app):
    app.add_url_rule('/assessments', view_func=assessment_list)
    app.add_url_rule('/assessments/<int:exam_id>/matrix', view_func=assessment_matrix)
    app.add_url_rule('/assessments/from-bank', view_func=assessment_from_bank, methods=['GET', 'POST'])
    app.add_url_rule('/assessments/import/<session_id>', view_func=assessment_import, methods=['GET', 'POST'])
    from routes.practice_runtime import practice_take, practice_result
    app.add_url_rule('/assessments/<int:exam_id>/take', endpoint='assessment_take', view_func=practice_take,
                     defaults={'standalone': True}, methods=['GET', 'POST'])
    app.add_url_rule('/assessments/<int:exam_id>/result', endpoint='assessment_result', view_func=practice_result,
                     defaults={'standalone': True})
