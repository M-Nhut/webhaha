"""Dedicated class and individual AI reports, with class-bound authorization."""

from hashlib import sha256
from pathlib import Path

from flask import abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from database import db
from models import AIAnalysisRun, Course, Enrollment, User
from routes.academic import _class_report_course, class_report_data
from services.ai_report_overview import build_overview, personal_archive_sections, report_sections
from services.class_lesson4_report import SKILL_NAMES, build_class_lesson4_packet, present_observed_report


def _report_asset_versions():
    """Use new URLs after an asset edit, including formerly incomplete downloads."""
    static_root = Path(current_app.static_folder)
    return {
        key: sha256((static_root / filename).read_bytes()).hexdigest()[:12]
        for key, filename in (("css", "css/ai-reports.css"), ("js", "js/modules/ai_reports.js"))
    }


def _student(course, student_id):
    if student_id is None:
        return None
    enrollment = Enrollment.query.filter_by(course_id=course.id, student_id=student_id, status="active").first()
    person = db.session.get(User, student_id)
    if not enrollment or not person or person.role != "student":
        abort(404)
    return person


@login_required
def ai_reports():
    if current_user.role not in {"teacher", "admin"}:
        abort(403)
    if request.endpoint == "ai_reports":
        endpoint = "ai_reports_individual" if request.args.get("student_id") else "ai_reports_class"
        args = {key: request.args[key] for key in
                ("course_id", "student_id", "view", "refresh", "skill", "source", "question_type") if key in request.args}
        return redirect(url_for(endpoint, **args))
    individual = request.endpoint == "ai_reports_individual"
    query = Course.query
    if current_user.role == "teacher":
        query = query.filter_by(teacher_id=current_user.id)
    courses = query.order_by(Course.course_name, Course.id).all()
    course_id = request.args.get("course_id", type=int)
    course = _class_report_course(course_id) if course_id is not None else (courses[0] if courses else None)
    people = sorted([e.student for e in Enrollment.query.filter_by(course_id=course.id, status="active").all()
                     if e.student and e.student.role == "student"], key=lambda p: (p.fullname, p.id)) if course else []
    student_id = request.args.get("student_id", type=int) if individual else None
    if individual and student_id is None and people:
        student_id = people[0].id
    student = _student(course, student_id) if course else None
    detail = request.args.get("view") == "detail"
    initial_data = _report_payload(course, student_id, include_analysis=False, filtered=not detail) if course and (not individual or student) else None
    return render_template("ai_reports.html", courses=courses, course=course, students=people,
                           student=student, detail=detail, skill_names=SKILL_NAMES, individual=individual,
                           report_endpoint=request.endpoint, initial_data=initial_data,
                           asset_versions=_report_asset_versions())


@login_required
def ai_report_data(course_id):
    course = _class_report_course(course_id)
    student_id = request.args.get("student_id", type=int)
    _student(course, student_id)
    response = jsonify(_report_payload(course, student_id, include_analysis=request.args.get("analysis") == "1"))
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _report_payload(course, student_id, *, include_analysis=False, filtered=True):
    """Overview reads only server facts; AI configuration/output is read on detail."""
    skill = request.args.get("skill", "").strip() if filtered else ""
    source = request.args.get("source", "").strip() if filtered else ""
    qtype = request.args.get("question_type", "").strip() if filtered else ""
    if skill and skill not in SKILL_NAMES:
        abort(400)
    if source and source not in {"standalone", "initial_diagnostic", "practice"}:
        abort(400)
    if qtype and qtype not in {"single", "true_false", "short_answer", "multiple_choice", "multi"}:
        abort(400)
    if include_analysis:
        data = class_report_data(course)
    else:
        packet = build_class_lesson4_packet(course)
        data = {"observed": present_observed_report(course, packet), "coverage": packet.get("coverage", {}),
                "status": "observed", "report": None}
    observed = data["observed"]
    overview = build_overview(observed, student_id=student_id, skill=skill, source=source, question_type=qtype)
    envelope = data.get("report") or {}
    core = envelope.get("report")
    sections = report_sections(core, student_id=student_id)
    evidence = build_overview(observed, student_id=student_id)["events"]
    student_ref = next((row["student_ref"] for row in overview["students"] if row["student_id"] == student_id), None)
    progress = [row for row in observed.get("class_summary", {}).get("observed_progress_recovery", [])
                if student_id is None or row.get("student_ref") == student_ref]
    allowed_refs = {event.get("event_ref") for event in evidence}
    if sections:
        for key in ("summary", "causes", "risks", "recommendations"):
            sections[key] = [row for row in sections[key] if isinstance(row, dict)
                             and set(row.get("basis_evidence_refs", [])).issubset(allowed_refs)]
    archive = None
    if include_analysis and student_id is not None and request.args.get("include_archive") == "1":
        run = AIAnalysisRun.query.filter_by(course_id=course.id, student_id=student_id,
                                           subject=course.subject, status="completed").order_by(
                                               AIAnalysisRun.created_at.desc(), AIAnalysisRun.id.desc()).first()
        if run:
            adapted = personal_archive_sections(run.get_response_data())
            if adapted:
                archive = {"id": run.id, "generated_at": run.created_at.isoformat() if run.created_at else None,
                           "sections": adapted}
    return {
        "status": data["status"], "error": data.get("error"), "overview": overview,
        "analysis": sections, "evidence": evidence, "coverage": data["coverage"], "progress": progress,
        "metadata": {key: envelope.get(key) for key in
                     ("id", "generated_at", "review_status", "review_note", "model_name", "prompt_version", "analysis_source")},
        "scope_label": "Toán 9 · Bài 25 + 26 · Lớp " + course.course_name, "personal_archive": archive,
    }


def register_ai_report_routes(app):
    app.add_url_rule("/ai-reports", endpoint="ai_reports", view_func=ai_reports)
    app.add_url_rule("/ai-reports/class", endpoint="ai_reports_class", view_func=ai_reports)
    app.add_url_rule("/ai-reports/individual", endpoint="ai_reports_individual", view_func=ai_reports)
    app.add_url_rule("/api/ai-reports/<int:course_id>", endpoint="ai_report_data", view_func=ai_report_data)
