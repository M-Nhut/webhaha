"""Dashboard, course, user and enrollment routes."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from database import db
from models import (
    User, Course, Enrollment,
    Exam, ExamSubmission,
    ClassAIAnalysisRun,
)
from services.access_control import role_required
from services.class_codes import ensure_join_code, normalize_join_code
from services.dashboard import (
    get_accessible_student_ids,
    student_dashboard_data,
    teacher_dashboard_data,
)
from helpers import parse_date, resolve_student_id
from services.class_lesson4_report import ClassLesson4ReportService, SCOPE_CODE, build_class_lesson4_packet
from services.ai_gateway import GeminiAIGateway, teacher_default_group

# ──────────────────────── DASHBOARD ────────────────────────

@login_required
def index():
    today = dt.date.today()
    defaults = {
        "dashboard_scope": "center", "student": None, "teacher_data": None,
        "student_data": None, "exams_data": [], "activities": [],
        "total_students": 0, "total_teachers": 0,
    }

    if current_user.role == "teacher":
        teacher_data = teacher_dashboard_data(current_user)
        teacher_exams = Exam.query.filter_by(
            created_by=current_user.id, assessment_purpose="initial_diagnostic"
        ).order_by(Exam.created_at.desc()).all()
        exams_data = [{
            "exam": exam,
            "total_submissions": ExamSubmission.query.filter_by(exam_id=exam.id).count(),
        } for exam in teacher_exams]
        activities = []
        exam_ids = [exam.id for exam in teacher_exams]
        if exam_ids:
            for submission in ExamSubmission.query.filter(ExamSubmission.exam_id.in_(exam_ids)).order_by(
                ExamSubmission.submitted_at.desc()).limit(10).all():
                activities.append({
                    "type": "diagnostic_submission",
                    "title": f"Nộp đánh giá đầu vào: {submission.exam.title}",
                    "desc": f"Học sinh {submission.student.fullname} đã nộp bài.",
                    "time": submission.submitted_at or submission.started_at,
                    "icon": "file-check",
                })
        return render_template("index.html", **{
            **defaults,
            "dashboard_scope": "teacher",
            "teacher_data": teacher_data,
            "exams_data": exams_data,
            "activities": activities,
        })

    if current_user.role == "student":
        student = current_user
        student_data = student_dashboard_data(student)
        course_ids = [e.course_id for e in Enrollment.query.filter_by(student_id=student.id, status="active").all()]
        student_exams = Exam.query.filter(Exam.course_id.in_(course_ids), Exam.is_active == True,
            or_(Exam.exam_type == "practice", Exam.assessment_purpose == "initial_diagnostic")).order_by(
            Exam.created_at.desc()).all() if course_ids else []
        exams_data = []
        for exam in student_exams:
            submission = ExamSubmission.query.filter_by(exam_id=exam.id, student_id=student.id).first()
            exams_data.append({
                "exam": exam,
                "status": "not_started" if not submission else ("graded" if submission.is_graded else "submitted"),
                "score_str": f"{submission.total_score}/{submission.max_score}" if submission else "",
                "submission_id": submission.id if submission else None,
            })
        activities = []
        for submission in ExamSubmission.query.join(Exam).filter(
            ExamSubmission.student_id == student.id,
            or_(Exam.exam_type == "practice", Exam.assessment_purpose == "initial_diagnostic"),
        ).order_by(ExamSubmission.submitted_at.desc()).limit(10).all():
            activities.append({
                "type": "practice_activity",
                "title": f"Hoàn tất {'đánh giá đầu vào' if submission.exam.assessment_purpose == 'initial_diagnostic' else 'bài tự luyện'}: {submission.exam.title}",
                "desc": f"Điểm số: {submission.total_score}/{submission.max_score}" if submission.is_graded else "Chưa hoàn tất",
                "time": submission.submitted_at or submission.started_at,
                "icon": "file-question",
            })
        return render_template("index.html", **{
            **defaults,
            "dashboard_scope": "student",
            "student_data": student_data,
            "student": student,
            "exams_data": exams_data,
            "activities": activities,
        })

    center_exams = Exam.query.filter(
        or_(Exam.exam_type == "practice", Exam.assessment_purpose == "initial_diagnostic")
    ).order_by(Exam.created_at.desc()).limit(8).all()
    exams_data = [{"exam": exam, "total_submissions": ExamSubmission.query.filter_by(exam_id=exam.id).count()}
                  for exam in center_exams]
    activities = [{
        "type": "practice_activity",
        "title": f"Đánh giá học tập: {submission.student.fullname}",
        "desc": f"Môn {submission.exam.course.course_name} - " + ("Chưa hoàn tất" if not submission.is_graded else f"{submission.total_score}/{submission.max_score}"),
        "time": submission.submitted_at or submission.started_at,
        "icon": "file-question",
    } for submission in ExamSubmission.query.join(Exam).filter(
        or_(Exam.exam_type == "practice", Exam.assessment_purpose == "initial_diagnostic")
    ).order_by(ExamSubmission.submitted_at.desc()).limit(15).all()]
    return render_template("index.html", **{
        **defaults,
        "total_students": User.query.filter_by(role="student").count(),
        "total_teachers": User.query.filter_by(role="teacher").count(),
        "exams_data": exams_data,
        "activities": activities,
    })


@login_required
def courses():
    query = Course.query
    if current_user.role == "teacher":
        query = query.filter_by(teacher_id=current_user.id)
    elif current_user.role == "student":
        student_ids = get_accessible_student_ids()
        course_ids = [enrollment.course_id for enrollment in Enrollment.query.filter(Enrollment.student_id.in_(student_ids)).all()]
        query = query.filter(Course.id.in_(course_ids)) if course_ids else query.filter(db.text("0=1"))
    return render_template("courses.html", courses=query.order_by(Course.course_name).all())


@login_required
@role_required("admin")
def add_course():
    teachers = User.query.filter_by(role="teacher").order_by(User.fullname).all()
    if request.method == "POST":
        teacher_id = request.form.get("teacher_id", type=int)
        course = Course(
            course_name=request.form["course_name"],
            subject=request.form["subject"],
            teacher_id=teacher_id,
            # Class AI always resolves the assigned teacher's default group at
            # request time.  The legacy column is intentionally left empty for
            # newly-created courses so a forged form field cannot establish a
            # hidden per-class override.
            ai_key_group_id=None,
            classroom=request.form.get("classroom"),
            description=request.form.get("description"),
            start_date=parse_date(request.form.get("start_date")),
            end_date=parse_date(request.form.get("end_date")),
            is_active=bool(request.form.get("is_active")),
        )
        db.session.add(course)
        db.session.commit()
        flash("Đã tạo khóa học.", "success")
        return redirect(url_for("courses"))
    return render_template("course_form.html", course=None, teachers=teachers)


@login_required
@role_required("admin")
def edit_course(course_id):
    course = db.session.get(Course, course_id) or abort(404)
    teachers = User.query.filter_by(role="teacher").order_by(User.fullname).all()
    if request.method == "POST":
        teacher_id = request.form.get("teacher_id", type=int)
        teacher_changed = course.teacher_id != teacher_id
        course.course_name = request.form["course_name"]
        course.subject = request.form["subject"]
        course.teacher_id = teacher_id
        # Never carry a former teacher's credential group into a transfer.
        if teacher_changed:
            # A teacher transfer must not carry the former owner's group.
            course.ai_key_group_id = None
        # For an unchanged teacher, preserve any legacy value exactly as
        # stored.  It is historical metadata only and cannot override the
        # teacher-default resolver used by AI requests.
        course.classroom = request.form.get("classroom")
        course.description = request.form.get("description")
        course.start_date = parse_date(request.form.get("start_date"))
        course.end_date = parse_date(request.form.get("end_date"))
        course.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Đã cập nhật khóa học.", "success")
        return redirect(url_for("courses"))
    return render_template("course_form.html", course=course, teachers=teachers)


@login_required
@role_required("admin")
def delete_course(course_id):
    db.session.delete(db.session.get(Course, course_id) or abort(404))
    db.session.commit()
    flash("Đã xóa khóa học.", "success")
    return redirect(url_for("courses"))


@login_required
def course_detail(course_id):
    course = db.session.get(Course, course_id) or abort(404)
    # Check authorization if teacher or student
    if current_user.role == "teacher" and course.teacher_id != current_user.id:
        flash("Bạn không dạy khóa học này.", "danger")
        return redirect(url_for("courses"))
    elif current_user.role == "student":
        student_ids = get_accessible_student_ids()
        is_enrolled = Enrollment.query.filter(Enrollment.student_id.in_(student_ids), Enrollment.course_id == course.id, Enrollment.status == "active").first()
        if not is_enrolled:
            flash("Bạn không có quyền truy cập khóa học này.", "danger")
            return redirect(url_for("courses"))

    # A legacy class gains its shareable code the first time its teacher
    # or an admin opens it; students never see a blank code.
    if current_user.role in ("teacher", "admin") and (
        current_user.role == "admin" or course.teacher_id == current_user.id
    ):
        ensure_join_code(course)
    # Active enrollments
    active_enrollments = Enrollment.query.filter_by(course_id=course.id, status="active").all()
    # List of all active students for select dropdown (excluding already enrolled)
    enrolled_student_ids = [e.student_id for e in active_enrollments]
    all_active_students = User.query.filter_by(role="student", is_active=True).order_by(User.fullname).all()
    available_students = [s for s in all_active_students if s.id not in enrolled_student_ids]
    
    # Display the same effective pool that gateway/report identity checks use;
    # a retained legacy course mapping is never surfaced as current config.
    default_group = teacher_default_group(course.teacher_id)
    effective_ai_group = default_group if default_group and default_group.is_active else None
    lesson4_report = ClassLesson4ReportService().get_latest(
        course,
        allow_legacy=GeminiAIGateway.legacy_enabled_for_unassigned_course(course),
        legacy_compatibility=False,
    )
    return render_template(
        "course_detail.html", 
        course=course, 
        enrollments=active_enrollments, 
        available_students=available_students,
        effective_ai_group=effective_ai_group,
        lesson4_report=lesson4_report,
    )


def _class_report_course(course_id):
    """Resolve a course and enforce teacher ownership at every report route."""
    course = db.session.get(Course, course_id) or abort(404)
    if current_user.role not in {"admin", "teacher"}:
        abort(403)
    if current_user.role == "teacher" and course.teacher_id != current_user.id:
        abort(403)
    return course


@login_required
def course_lesson4_report(course_id):
    """Return the latest fixed Lesson 4 report and current data coverage."""
    course = _class_report_course(course_id)
    return jsonify(class_report_data(course))


def class_report_data(course):
    """Shared read path for the existing API and the dedicated report workspace."""
    packet = build_class_lesson4_packet(course)
    service = ClassLesson4ReportService()
    legacy_allowed = GeminiAIGateway.legacy_enabled_for_unassigned_course(course)
    configuration, _ = service._resolve_configuration(course, allow_legacy=legacy_allowed)
    identity = service._identity_for(configuration, course, legacy_compatibility=False)
    input_hash = service.input_hash(packet, configuration, identity)
    run = service.get_latest(course, allow_legacy=legacy_allowed, legacy_compatibility=False)
    current = bool(run and run.input_hash == input_hash and run.status == "completed")
    if run and run.status == "processing":
        age = (dt.datetime.utcnow() - (run.created_at or dt.datetime.utcnow())).total_seconds()
        status = "processing" if age <= service.processing_timeout else "stale"
    elif current:
        status = run.status
    elif run and run.status == "failed":
        status = "failed"
    elif run:
        status = "stale"
    else:
        status = "missing"
    data = service.present(
        run, course, packet, allow_legacy=legacy_allowed, legacy_compatibility=False
    ) if current else None
    from services.class_lesson4_report import present_observed_report
    return {
        "observed": present_observed_report(course, packet),
        "scope": SCOPE_CODE,
        "status": status,
        "error": run.error_message if run and run.status == "failed" else None,
        "stale": not current,
        "report": data,
        "coverage": packet.get("coverage", {}),
    }


@login_required
def generate_course_lesson4_report(course_id):
    """Generate or reuse a persisted class report for the fixed Lesson 4."""
    course = _class_report_course(course_id)
    # Administrators may view an existing auditable report or disable a group,
    # but cannot spend a teacher-owned Gemini credential.
    if current_user.role != "teacher" or course.teacher_id != current_user.id:
        abort(403)
    payload = request.get_json(silent=True) or request.form
    force = str(payload.get("force", "0")).lower() in {"1", "true", "yes", "on"}
    service = ClassLesson4ReportService()
    run, cached, packet = service.generate(
        course, requested_by=current_user.id, force=force,
        allow_legacy=GeminiAIGateway.legacy_enabled_for_unassigned_course(course),
        legacy_compatibility=False,
    )
    if not run:
        abort(503)
    if run.status == "failed":
        return jsonify({
            "scope": SCOPE_CODE,
            "status": "failed",
            "error": run.error_message or "Không thể gọi AI API. Vui lòng kiểm tra cấu hình khóa AI của giáo viên.",
            "report": None,
            "coverage": packet.get("coverage", {}),
        }), 400
    # A learner may finalize another paper while the bounded provider call is
    # in flight.  Never label that older snapshot current merely because this
    # request created it; the next click can generate from the newer evidence.
    current_packet = build_class_lesson4_packet(course)
    configuration, _ = service._resolve_configuration(
        course, allow_legacy=GeminiAIGateway.legacy_enabled_for_unassigned_course(course)
    )
    identity = service._identity_for(configuration, course, legacy_compatibility=False)
    if run.input_hash != service.input_hash(current_packet, configuration, identity):
        return jsonify({
            "scope": SCOPE_CODE,
            "status": "stale",
            "stale": True,
            "report": None,
            "coverage": current_packet.get("coverage", {}),
        })
    data = service.present(
        run, course, current_packet,
        allow_legacy=GeminiAIGateway.legacy_enabled_for_unassigned_course(course),
        legacy_compatibility=False,
    )
    data["cached"] = bool(cached)
    data["stale"] = False
    return jsonify({"scope": SCOPE_CODE, "status": run.status, "report": data, "coverage": packet.get("coverage", {})}), (
        202 if run.status == "processing" else 200
    )


@login_required
def review_course_lesson4_report(course_id, report_id):
    """Record a review only for the current completed AI snapshot."""
    course = _class_report_course(course_id)
    run = db.session.get(ClassAIAnalysisRun, report_id) or abort(404)
    if run.course_id != course.id or run.scope_code != SCOPE_CODE:
        abort(404)
    status = str((request.get_json(silent=True) or request.form).get("status", "confirmed")).strip()
    if status not in {"confirmed", "rejected", "unreviewed"}:
        abort(400)
    payload = request.get_json(silent=True) or request.form
    service = ClassLesson4ReportService()
    packet = build_class_lesson4_packet(course)
    legacy_allowed = GeminiAIGateway.legacy_enabled_for_unassigned_course(course)
    configuration, _ = service._resolve_configuration(course, allow_legacy=legacy_allowed)
    identity = service._identity_for(configuration, course, legacy_compatibility=False)
    current_hash = service.input_hash(packet, configuration, identity)
    if run.input_hash != current_hash:
        return jsonify({"error": "Báo cáo đã cũ vì dữ liệu bài làm hoặc cấu hình AI đã thay đổi."}), 409
    if status == "confirmed" and run.status != "completed":
        return jsonify({"error": "Chỉ có thể xác nhận báo cáo đã phân tích hoàn tất bằng AI."}), 409
    run.review_status = status
    run.reviewed_by = current_user.id if status != "unreviewed" else None
    run.review_note = str(payload.get("review_note") or "").strip()[:2000] or None
    run.reviewed_at = dt.datetime.utcnow() if status != "unreviewed" else None
    db.session.commit()
    return jsonify({
        "id": run.id, "review_status": run.review_status,
        "reviewed_at": run.reviewed_at.isoformat() if run.reviewed_at else None,
    })


@login_required
def my_students():
    if current_user.role != "teacher":
        flash("Trang này chỉ dành cho giáo viên.", "danger")
        return redirect(url_for("index"))
    return redirect(url_for("teacher_practice_list", course_id=request.args.get("course_id", type=int)))


@login_required
@role_required("admin")
def manage_users(role_name):
    if role_name not in ("students", "teachers"):
        abort(404)
    role_map = {"students": ["student"], "teachers": ["teacher"]}
    users = User.query.filter(User.role.in_(role_map[role_name])).order_by(User.fullname).all()
    students = User.query.filter_by(role="student").order_by(User.fullname).all()
    return render_template("manage_users.html", users=users, role_name=role_name, students=students)


def _user_form_values():
    """Normalize only profile fields; passwords keep their existing semantics."""
    return {name: (request.form.get(name) or "").strip()
            for name in ("username", "fullname", "user_code", "phone", "position")}


def _user_form_errors(values, *, exclude_user_id=None):
    errors = []
    fields = {
        "username": ("Tên đăng nhập", 80, True),
        "fullname": ("Họ và tên", 100, True),
        "user_code": ("Mã người dùng", 20, True),
        "phone": ("Số điện thoại", 20, False),
        "position": ("Lớp / Vị trí", 100, False),
    }
    for name, (label, maximum, required) in fields.items():
        if required and not values[name]:
            errors.append(f"{label} không được để trống.")
        elif len(values[name]) > maximum:
            errors.append(f"{label} không được dài quá {maximum} ký tự.")
    for name, label in (("username", "Tên đăng nhập"), ("user_code", "Mã người dùng")):
        if not values[name]:
            continue
        query = User.query.filter(getattr(User, name) == values[name])
        if exclude_user_id is not None:
            query = query.filter(User.id != exclude_user_id)
        if query.first() is not None:
            errors.append(f"{label} đã được sử dụng.")
    return errors


@login_required
@role_required("admin")
def add_user():
    role = request.form.get("role", "student")
    if role not in {"student", "teacher"}:
        flash("Chỉ có thể tạo tài khoản học sinh hoặc giáo viên.", "danger")
        return redirect(request.referrer or url_for("index"))
    destination = request.referrer or url_for("manage_users", role_name="teachers" if role == "teacher" else "students")
    values = _user_form_values()
    errors = _user_form_errors(values)
    if errors:
        flash("Không thể thêm người dùng. " + " ".join(errors), "danger")
        return redirect(destination)
    user = User(**values, role=role, is_active=True)
    user.set_password(request.form.get("password") or "123456")
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Không thể lưu tài khoản. Tên đăng nhập hoặc mã người dùng có thể đã được sử dụng; vui lòng kiểm tra và thử lại.", "danger")
        return redirect(destination)
    flash("Đã thêm người dùng.", "success")
    return redirect(destination)


@login_required
@role_required("admin")
def edit_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    students = User.query.filter_by(role="student").order_by(User.fullname).all()
    if request.method == "POST":
        new_role = request.form.get("role", user.role)
        if user.role == "admin" or new_role not in {"student", "teacher"}:
            flash("Tài khoản admin không được đổi vai trò tại màn hình này.", "danger")
            return redirect(url_for("manage_users", role_name="teachers" if user.role == "teacher" else "students"))
        values = _user_form_values()
        submitted_user = SimpleNamespace(id=user.id, **values, role=new_role,
                                         is_active=bool(request.form.get("is_active")))
        errors = _user_form_errors(values, exclude_user_id=user.id)
        if errors:
            flash("Không thể cập nhật người dùng. " + " ".join(errors), "danger")
            return render_template("edit_user.html", user=submitted_user, students=students)
        for name, value in values.items():
            setattr(user, name, value)
        user.role = new_role
        user.is_active = submitted_user.is_active
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Không thể lưu tài khoản. Tên đăng nhập hoặc mã người dùng có thể đã được sử dụng; vui lòng kiểm tra và thử lại.", "danger")
            return render_template("edit_user.html", user=submitted_user, students=students)
        flash("Đã cập nhật người dùng.", "success")
        return redirect(url_for("manage_users", role_name="teachers" if user.role == "teacher" else "students"))
    return render_template("edit_user.html", user=user, students=students)


@login_required
@role_required("admin")
def delete_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == current_user.id or user.role == "admin":
        flash("Không thể xóa tài khoản này.", "danger")
        return redirect(request.referrer or url_for("index"))
    db.session.delete(user)
    db.session.commit()
    flash("Đã xóa người dùng.", "success")
    return redirect(request.referrer or url_for("index"))


@login_required
@role_required("admin")
def reset_password(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.role == "admin":
        flash("Không thể reset mật khẩu admin tại màn hình này.", "danger")
        return redirect(request.referrer or url_for("index"))
    user.set_password(request.form.get("password") or "123456")
    db.session.commit()
    flash("Đã reset mật khẩu.", "success")
    return redirect(request.referrer or url_for("index"))


@login_required
@role_required("admin")
def add_enrollment():
    student_id_raw = request.form["student_id"]
    course_id = int(request.form["course_id"])
    
    student_id = resolve_student_id(student_id_raw)
    if not student_id:
        flash(f"Không tìm thấy học sinh với mã hoặc tên đăng nhập '{student_id_raw}'.", "danger")
        return redirect(request.referrer or url_for("courses"))
        
    existing = Enrollment.query.filter_by(student_id=student_id, course_id=course_id).first()
    if existing:
        if existing.status == "active":
            flash("Học sinh này đã ghi danh vào khóa học rồi.", "warning")
        else:
            existing.status = "active"
            from services.diagnostic_service import assign_existing_diagnostics_for_enrollment
            assign_existing_diagnostics_for_enrollment(existing, assigned_by=current_user.id)
            db.session.commit()
            flash("Đã kích hoạt lại ghi danh cho học sinh này.", "success")
        return redirect(request.referrer or url_for("courses"))
        
    enrollment = Enrollment(student_id=student_id, course_id=course_id, status="active")
    db.session.add(enrollment)
    db.session.flush()
    from services.diagnostic_service import assign_existing_diagnostics_for_enrollment
    assign_existing_diagnostics_for_enrollment(enrollment, assigned_by=current_user.id)
    db.session.commit()
    flash("Đã ghi danh học sinh thành công.", "success")
    return redirect(request.referrer or url_for("courses"))



@login_required
@role_required("teacher")
def teacher_add_course():
    """Let a teacher create only their own class.

    The admin course form is reused, but the submitted teacher is ignored:
    a forged teacher_id can never assign a class to another teacher.
    """
    if request.method == "POST":
        course = Course(
            course_name=request.form["course_name"],
            subject=request.form["subject"],
            teacher_id=current_user.id,
            ai_key_group_id=None,
            classroom=request.form.get("classroom"),
            description=request.form.get("description"),
            start_date=parse_date(request.form.get("start_date")),
            end_date=parse_date(request.form.get("end_date")),
            is_active=bool(request.form.get("is_active")),
        )
        db.session.add(course)
        db.session.flush()
        ensure_join_code(course)
        flash("Đã tạo lớp học. Gửi mã lớp hoặc link lớp cho học sinh tham gia.", "success")
        return redirect(url_for("course_detail", course_id=course.id))
    return render_template("course_form.html", course=None, teachers=[current_user])


@login_required
def join_by_code():
    """Enter a class code, then continue to the confirm-join page."""
    if current_user.role != "student":
        flash("Chỉ học sinh mới tham gia lớp bằng mã lớp.", "danger")
        return redirect(url_for("courses"))
    if request.method == "POST":
        code = normalize_join_code(request.form.get("code"))
        if code:
            return redirect(url_for("join_class", code=code))
        flash("Vui lòng nhập mã lớp.", "danger")
    return render_template("join_class.html", course=None, already_enrolled=False)


@login_required
def join_class(code):
    """Join a class from its link (/join/<code>) or from a typed code."""
    if current_user.role != "student":
        flash("Chỉ học sinh mới tham gia lớp bằng mã lớp.", "danger")
        return redirect(url_for("courses"))
    normalized = normalize_join_code(code)
    course = Course.query.filter_by(join_code=normalized).first()
    if not course or not course.is_active:
        flash("Mã lớp không tồn tại hoặc lớp đã tạm ngưng.", "danger")
        return redirect(url_for("onboarding"))
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
    if enrollment and enrollment.status == "active":
        return render_template("join_class.html", course=course, already_enrolled=True)
    if request.method == "POST":
        if enrollment:
            enrollment.status = "active"
        else:
            enrollment = Enrollment(student_id=current_user.id, course_id=course.id, status="active")
            db.session.add(enrollment)
        db.session.commit()
        try:
            from services.diagnostic_service import assign_existing_diagnostics_for_enrollment

            assign_existing_diagnostics_for_enrollment(enrollment, assigned_by=course.teacher_id)
        except Exception:
            # Diagnostics are a bonus on join; a failure there must not undo
            # an enrollment the student has just confirmed.
            pass
        flash(f"Bạn đã tham gia lớp {course.course_name}.", "success")
        return redirect(url_for("course_detail", course_id=course.id))
    return render_template("join_class.html", course=course, already_enrolled=False)


def register_academic_routes(app) -> None:
    """Register handlers while preserving the legacy route contract."""
    app.add_url_rule("/", endpoint="index", view_func=index)
    app.add_url_rule("/courses", endpoint="courses", view_func=courses)
    app.add_url_rule("/courses/new", endpoint="add_course", view_func=add_course, methods=["GET", "POST"])
    app.add_url_rule("/courses/teacher-new", endpoint="teacher_add_course", view_func=teacher_add_course, methods=["GET", "POST"])
    app.add_url_rule("/join", endpoint="join_by_code", view_func=join_by_code, methods=["GET", "POST"])
    app.add_url_rule("/join/<code>", endpoint="join_class", view_func=join_class, methods=["GET", "POST"])
    app.add_url_rule("/courses/<int:course_id>/edit", endpoint="edit_course", view_func=edit_course, methods=["GET", "POST"])
    app.add_url_rule("/courses/<int:course_id>/delete", endpoint="delete_course", view_func=delete_course, methods=["POST"])
    app.add_url_rule("/courses/<int:course_id>", endpoint="course_detail", view_func=course_detail)
    app.add_url_rule("/courses/<int:course_id>/lesson4-report", endpoint="course_lesson4_report", view_func=course_lesson4_report)
    app.add_url_rule("/courses/<int:course_id>/lesson4-report/generate", endpoint="generate_course_lesson4_report", view_func=generate_course_lesson4_report, methods=["POST"])
    app.add_url_rule("/courses/<int:course_id>/lesson4-report/<int:report_id>/review", endpoint="review_course_lesson4_report", view_func=review_course_lesson4_report, methods=["POST"])
    app.add_url_rule("/my-students", endpoint="my_students", view_func=my_students)
    app.add_url_rule("/users/<role_name>", endpoint="manage_users", view_func=manage_users)
    app.add_url_rule("/users", endpoint="add_user", view_func=add_user, methods=["POST"])
    app.add_url_rule("/users/<int:user_id>/edit", endpoint="edit_user", view_func=edit_user, methods=["GET", "POST"])
    app.add_url_rule("/users/<int:user_id>/delete", endpoint="delete_user", view_func=delete_user, methods=["POST"])
    app.add_url_rule("/users/<int:user_id>/reset-password", endpoint="reset_password", view_func=reset_password, methods=["POST"])
    app.add_url_rule("/enrollments", endpoint="add_enrollment", view_func=add_enrollment, methods=["POST"])
