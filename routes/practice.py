"""Adaptive practice, teacher practice and analytics routes."""

from __future__ import annotations

import datetime as dt
import json
import math

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from adaptive_engine import AdaptiveEngine
from services import practice_blueprint as blueprint
from database import db
from models import (
    AIAnalysisRun, Course, Enrollment, ErrorObservation, Exam, ExamAnswer, ExamQuestion,
    ExamSubmission, MasterySnapshot, PracticeSession, QuestionBank, SubmissionAnswer, TeacherLearningReport, User
)
from services.access_control import can_use_bank, role_required
from services.personalization_evidence import (
    answer_status,
    is_finalized,
    report_payload,
    refresh_question_snapshot,
    source_revision,
    upsert_teacher_report,
)
from services.diagnostic_service import SCOPE_CODE, class_diagnostic_source, learner_profile_state
from services.practice_runtime import practice_decision_is_ready
from services.ai_gateway import AIConfigurationError, GeminiAIGateway
from services.source_resolver import (
    attach_source_manifest,
    resolve_class_banks,
    resolve_class_questions,
    validate_exam_source,
)


def _configuration_unavailable(gateway, course):
    """Read-only availability check; no provider call and no key exposure."""
    try:
        gateway.resolve_course(
            course, allow_legacy=GeminiAIGateway.legacy_enabled_for_unassigned_course(course)
        )
    except AIConfigurationError:
        return True
    return False


def _teacher_report_is_stale(report, course):
    """Read-only freshness check for a stored individual teacher report."""
    if not course or report.source_revision != source_revision(
        report.student_id, report.subject, course_id=course.id
    ):
        return True
    payload = report.get_payload()
    run_id = payload.get("ai_run_id")
    if not run_id:
        # Older artifacts did not carry an auditable AI-run/config identity.
        return True
    run = db.session.get(AIAnalysisRun, run_id)
    try:
        configuration = GeminiAIGateway().resolve_course(
            course, allow_legacy=GeminiAIGateway.legacy_enabled_for_unassigned_course(course)
        )
    except AIConfigurationError:
        return True
    return not run or run.course_id != course.id or (
        run.ai_credential_source, run.ai_key_group_id, run.ai_config_revision,
        run.provider, run.model_name,
    ) != (
        configuration.source, configuration.group_id, configuration.config_revision,
        configuration.provider, configuration.model_name,
    )


def _create_fixed_exam(*, selection, course, bank_ids, student_id, creator_id, title,
                       is_active, practice_session, metadata_extra=None):
    """Persist one frozen fixed paper inside the caller's transaction."""
    source = resolve_class_banks(course, bank_ids)
    if not source["valid"]:
        raise ValueError("The class source is no longer authorized")
    canonical_bank_ids = source["bank_ids"]
    selected_questions = list(selection.get("questions") or [])
    resolved_questions = resolve_class_questions(
        course, canonical_bank_ids, selected_questions
    )
    if (
        not resolved_questions["valid"]
        or len(resolved_questions["questions"]) != len(selected_questions)
        or {id(item) for item in resolved_questions["questions"]}
        != {id(item) for item in selected_questions}
    ):
        raise ValueError("The selected paper contains a question outside the class source")
    bank_ids = canonical_bank_ids
    recommendation = selection["recommendation"]
    metadata = {
        "student_id": student_id,
        "practice_session_id": practice_session.id,
        "explanation": selection["explanation"],
        "aptga": selection.get("aptga"),
        "score_weights": AdaptiveEngine.SCORE_WEIGHTS,
        "mastery_thresholds": AdaptiveEngine.MASTERY_THRESHOLDS,
        "cold_start_min_answers": AdaptiveEngine.COLD_START_MIN_ANSWERS,
        "actual_mix": selection["mix"],
        "ranked_questions": selection["ranked"],
    }
    metadata.update(metadata_extra or {})
    exam = Exam(
        title=title, course_id=course.id, created_by=creator_id,
        # Newly generated fixed papers share the 22-question, 40-minute
        # contract.  Existing rows are never rewritten.
        duration_minutes=blueprint.DURATION_MINUTES,
        exam_type="practice", question_bank_id=bank_ids[0],
        total_questions=selection["selected_count"],
        difficulty_config=json.dumps(recommendation["diff_config"]),
        question_type_config=json.dumps(recommendation["type_config"]),
        adaptive_metadata=json.dumps(metadata, ensure_ascii=False), is_active=is_active,
    )
    db.session.add(exam)
    db.session.flush()
    copied_pairs = []
    for index, bank_question in enumerate(selected_questions):
        question = ExamQuestion(
            exam_id=exam.id, bank_question_id=bank_question.id,
            question_text=bank_question.question_text, context=bank_question.context,
            image_url=bank_question.image_url, question_type=bank_question.question_type,
            difficulty_level=bank_question.difficulty_level,
            explanation=bank_question.explanation,
            points=blueprint.POINTS[bank_question.question_type], order_index=index,
        )
        db.session.add(question)
        db.session.flush()
        for option in bank_question.options:
            db.session.add(ExamAnswer(
                question_id=question.id, answer_text=option.option_text,
                is_correct=option.is_correct,
            ))
        db.session.flush()
        refresh_question_snapshot(question, bank_question)
        copied_pairs.append((question, bank_question))
    attach_source_manifest(exam, course, copied_pairs, bank_ids=bank_ids)
    practice_session.last_exam_id = exam.id
    practice_session.status = "active"
    practice_session.updated_at = dt.datetime.utcnow()
    return exam


def _student_course(student_id, course_id):
    """Resolve one explicitly selected active class enrollment."""
    if course_id is None:
        return None
    enrollment = Enrollment.query.filter_by(
        student_id=student_id, course_id=course_id, status="active"
    ).first()
    if not enrollment or not enrollment.course or not enrollment.course.is_active:
        return None
    return enrollment.course


def _teacher_session_banks(course, bank_ids):
    """Resolve all banks explicitly authorized by the selected class teacher."""
    result = resolve_class_banks(course, bank_ids)
    return result["banks"] if result["valid"] else []


def _teacher_issued_practice(exam, student_id):
    """Identify a teacher-issued fixed paper without trusting a requester.

    New papers carry server-persisted provenance.  Legacy fixed papers may
    predate that marker, so their persisted creator is accepted only when it
    is a teacher and is not the target student.  Provenance must remain bound
    to the same course; bank authorization is checked separately against the
    current class teacher.
    """
    if not exam:
        return False
    metadata = exam.get_adaptive_metadata()
    provenance = metadata.get("practice_provenance") or {}
    if isinstance(provenance, dict) and provenance.get("kind") == "teacher_assigned":
        if provenance.get("course_id") != exam.course_id:
            return False
        origin_teacher = db.session.get(User, provenance.get("teacher_id")) if provenance.get("teacher_id") else None
        return getattr(origin_teacher, "role", None) == "teacher"
    creator = getattr(exam, "creator", None)
    if creator is None and getattr(exam, "created_by", None):
        creator = db.session.get(User, exam.created_by)
    return bool(
        getattr(creator, "role", None) == "teacher"
        and getattr(creator, "id", None) != student_id
    )


def _published_teacher_papers(student_id, course):
    """List valid targeted teacher papers without treating them as bank choices."""
    if not course or not course.teacher_id:
        return []
    exams = Exam.query.filter_by(
        course_id=course.id,
        exam_type="practice",
        is_active=True,
    ).order_by(Exam.created_at.desc(), Exam.id.desc()).all()
    items = []
    for exam in exams:
        metadata = exam.get_adaptive_metadata()
        session = db.session.get(PracticeSession, metadata.get("practice_session_id")) if metadata.get("practice_session_id") else None
        session_bank_ids = session.get_bank_ids() if session else []
        session_banks = _teacher_session_banks(course, session_bank_ids) if session else []
        source_validation = validate_exam_source(exam, require_live=True)
        manifest_bank_ids = (source_validation.get("manifest") or {}).get("bank_ids", [])
        if source_validation.get("legacy"):
            # Explicit compatibility for pre-manifest papers: the persisted
            # session is the only available source assertion.
            manifest_bank_ids = session_bank_ids
        if (
            not blueprint.is_fixed(exam)
            or not _teacher_issued_practice(exam, student_id)
            or metadata.get("student_id") != student_id
            or not session
            or session.student_id != student_id
            or session.course_id != course.id
            or session.scope_code != SCOPE_CODE
            or not session_banks
            or sorted(session_bank_ids) != sorted(manifest_bank_ids)
            or not exam.question_bank_id
            or exam.question_bank_id not in {bank.id for bank in session_banks}
            or not source_validation["valid"]
        ):
            continue
        submission = ExamSubmission.query.filter_by(
            exam_id=exam.id, student_id=student_id
        ).order_by(ExamSubmission.submitted_at.desc(), ExamSubmission.id.desc()).first()
        items.append({"exam": exam, "submission": submission})
    return items


def _resumable_practice_exam(student_id, course, bank):
    """Return the learner's latest still-open, unsubmitted class paper."""
    if not course or not bank:
        return None
    sessions = PracticeSession.query.filter_by(
        student_id=student_id,
        course_id=course.id,
        subject=course.subject,
        scope_code=SCOPE_CODE,
        status="active",
    ).order_by(PracticeSession.updated_at.desc(), PracticeSession.id.desc()).all()
    for session in sessions:
        if session.get_bank_ids() != [bank.id] or not session.last_exam_id:
            continue
        exam = db.session.get(Exam, session.last_exam_id)
        metadata = exam.get_adaptive_metadata() if exam else {}
        if (
            not exam
            or exam.exam_type != "practice"
            or not blueprint.is_fixed(exam)
            or exam.course_id != course.id
            or exam.question_bank_id != bank.id
            or exam.status_label != "open"
            or metadata.get("student_id") != student_id
            or metadata.get("practice_session_id") != session.id
            or not validate_exam_source(exam, require_live=True)["valid"]
        ):
            continue
        submitted = ExamSubmission.query.filter_by(
            exam_id=exam.id, student_id=student_id
        ).filter(ExamSubmission.submitted_at.isnot(None)).first()
        if not submitted:
            return exam
    return None


def _pending_practice_decision_exam(student_id, course, bank):
    """Keep a completed class session at its explicit continue/end choice."""
    if not course or not bank:
        return None
    sessions = PracticeSession.query.filter_by(
        student_id=student_id,
        course_id=course.id,
        subject=course.subject,
        scope_code=SCOPE_CODE,
        status="awaiting_decision",
    ).order_by(PracticeSession.updated_at.desc(), PracticeSession.id.desc()).all()
    for session in sessions:
        if not session.last_exam_id or not session.last_submission_id:
            continue
        exam = db.session.get(Exam, session.last_exam_id)
        submission = db.session.get(ExamSubmission, session.last_submission_id)
        metadata = exam.get_adaptive_metadata() if exam else {}
        if (
            exam
            and submission
            and blueprint.is_fixed(exam)
            and exam.course_id == course.id
            and metadata.get("student_id") == student_id
            and metadata.get("practice_session_id") == session.id
            and submission.exam_id == exam.id
            and submission.student_id == student_id
            and submission.is_graded
            and submission.status == "graded"
            and MasterySnapshot.query.filter_by(
                student_id=student_id,
                subject=session.subject,
                submission_id=submission.id,
            ).first()
        ):
            return exam
    return None


# ──────────────────────── ADAPTIVE PRACTICE & ANALYTICS ────────────────────────

@login_required
def practice_home():
    if current_user.role != "student":
        flash("Tính năng tự luyện dành cho học sinh.", "info")
        return redirect(url_for("index"))

    enrollments = Enrollment.query.filter_by(
        student_id=current_user.id, status="active"
    ).all()
    courses = sorted(
        {item.course.id: item.course for item in enrollments
         if item.course and item.course.is_active}.values(),
        key=lambda item: (item.course_name, item.id),
    )
    selected_id = request.args.get("course_id", type=int)
    if selected_id is not None and selected_id not in {course.id for course in courses}:
        abort(403)
    selected_course = next(
        (course for course in courses if course.id == selected_id),
        courses[0] if courses else None,
    )
    profile_state = None
    profile = None
    source_state = None
    resume_exam = None
    pending_decision_exam = None
    teacher_papers = []
    if selected_course:
        teacher_papers = _published_teacher_papers(current_user.id, selected_course)
        profile_state = learner_profile_state(
            current_user.id, selected_course.subject, course_id=selected_course.id
        )
        if profile_state["initialized"]:
            # Do not render a synthetic cold-start profile before a finalized
            # evidence source exists.
            profile = AdaptiveEngine.analyze_performance(
                current_user.id, selected_course.subject
            )
            source_state = class_diagnostic_source(current_user.id, selected_course)
            if source_state["status"] == "ready":
                pending_decision_exam = _pending_practice_decision_exam(
                    current_user.id, selected_course, source_state["bank"]
                )
                resume_exam = _resumable_practice_exam(
                    current_user.id, selected_course, source_state["bank"]
                )
    return render_template(
        "practice_home.html",
        courses=courses,
        selected_course=selected_course,
        profile=profile,
        profile_state=profile_state,
        source_state=source_state,
        resume_exam=resume_exam,
        pending_decision_exam=pending_decision_exam,
        teacher_papers=teacher_papers,
        blueprint=blueprint,
    )


@login_required
def practice_generate():
    if current_user.role != "student":
        abort(403)

    course = _student_course(current_user.id, request.form.get("course_id", type=int))
    if not course:
        abort(403)
    home_url = url_for("practice_home", course_id=course.id)
    profile_state = learner_profile_state(
        current_user.id, course.subject, course_id=course.id
    )
    if not profile_state["initialized"]:
        if profile_state.get("exam"):
            flash("Hãy hoàn tất bài đánh giá đầu vào chung trước khi tạo đề cá nhân hóa.", "warning")
            return redirect(url_for("practice_take", exam_id=profile_state["exam"]))
        flash("Lớp này chưa có bài đánh giá đầu vào hợp lệ. Hãy liên hệ giáo viên phụ trách.", "warning")
        return redirect(home_url)
    source_state = class_diagnostic_source(current_user.id, course)
    if source_state["status"] != "ready":
        flash(source_state["message"], "warning")
        return redirect(home_url)
    bank = source_state["bank"]
    supplied_bank_ids = request.form.getlist("bank_ids")
    try:
        supplied = [int(value) for value in supplied_bank_ids]
        if len(supplied) != len(set(supplied)):
            abort(403)
        if supplied and set(supplied) != {bank.id}:
            abort(403)
    except (TypeError, ValueError):
        abort(400)
    pending_decision_exam = _pending_practice_decision_exam(
        current_user.id, course, bank
    )
    if pending_decision_exam:
        flash("Hãy chọn tiếp tục hoặc kết thúc phiên vừa hoàn tất trước khi tạo đề khác.", "info")
        return redirect(url_for("practice_result", exam_id=pending_decision_exam.id))
    resume_exam = _resumable_practice_exam(current_user.id, course, bank)
    if resume_exam:
        flash("Tiếp tục bài đang làm của lớp này.", "info")
        return redirect(url_for("practice_take", exam_id=resume_exam.id))

    bank_ids = [bank.id]
    title = f"Bài Tự Luyện: {bank.name}"

    selection = AdaptiveEngine.select_questions(
        current_user.id, course.subject, bank_ids, blueprint.TOTAL,
        constraints={"blueprint": blueprint.VERSION, "course_id": course.id},
    )
    if not selection["questions"]:
        flash(selection["explanation"], "warning")
        return redirect(home_url)
    source_questions = resolve_class_questions(course, [bank.id], selection["questions"])
    if (
        not source_questions["valid"]
        or len(source_questions["questions"]) != len(selection["questions"])
    ):
        flash("Bộ câu hỏi vừa chọn không còn thuộc nguồn được giáo viên hiện tại của lớp cho phép.", "warning")
        return redirect(home_url)
    recommendation = selection["recommendation"]
    title += f" ({recommendation['level'].upper()})"
    for old_session in PracticeSession.query.filter_by(
        student_id=current_user.id, course_id=course.id, subject=course.subject,
        scope_code=SCOPE_CODE,
    ).filter(PracticeSession.status.in_(("active", "awaiting_decision"))).all():
        old_session.status = "superseded"
        old_session.ended_at = dt.datetime.utcnow()
    practice_session = PracticeSession(
        student_id=current_user.id, course_id=course.id, subject=course.subject,
        scope_code=SCOPE_CODE, bank_ids=json.dumps(bank_ids), status="active",
    )
    db.session.add(practice_session)
    db.session.flush()
    exam = _create_fixed_exam(
        selection=selection, course=course, bank_ids=bank_ids,
        student_id=current_user.id, creator_id=current_user.id, title=title,
        is_active=True, practice_session=practice_session,
        metadata_extra={
            "review_mix": AdaptiveEngine.REVIEW_MIX,
            "cold_start": selection["profile"]["cold_start"],
            "answer_count": selection["profile"]["answer_count"],
        },
    )
    db.session.commit()
    flash(selection["explanation"], "info")
    return redirect(url_for("practice_take", exam_id=exam.id))


@login_required
def practice_progress():
    if current_user.role != "student":
        flash("Trang này dành cho học sinh.", "info")
        return redirect(url_for("index"))

    enrollments = Enrollment.query.filter_by(student_id=current_user.id, status="active").all()
    subjects = sorted({e.course.subject for e in enrollments if e.course and e.course.subject})
    if not subjects:
        subjects = ["Toán", "Tiếng Anh"]

    selected_subject = request.args.get("subject", subjects[0] if subjects else "Toán")
    profile = AdaptiveEngine.analyze_performance(current_user.id, selected_subject)

    # Submission history
    subs = (
        ExamSubmission.query
        .filter_by(student_id=current_user.id)
        .order_by(ExamSubmission.submitted_at.asc())
        .all()
    )
    history = [
        {
            "date": s.submitted_at.strftime("%d/%m/%Y %H:%M") if s.submitted_at else "",
            "score": s.score_on_ten if is_finalized(s) else None,
            "title": s.exam.title if s.exam else "Bài luyện",
            "type": s.exam_type,
            "purpose": s.exam.assessment_purpose,
            "is_graded": is_finalized(s),
            "exam_id": s.exam_id,
            "result_url": url_for("assessment_result" if s.exam.assessment_purpose == "standalone" else "practice_result", exam_id=s.exam_id),
        }
        for s in subs if s.exam and s.exam.course and s.exam.course.subject == selected_subject
    ]
    mastery_history = []
    snapshots = MasterySnapshot.query.filter_by(student_id=current_user.id, subject=selected_subject).order_by(MasterySnapshot.created_at.asc()).all()
    for snapshot in snapshots:
        try:
            data = json.loads(snapshot.profile_data or "{}")
        except (TypeError, ValueError):
            data = {}
        # A missing/invalid historical snapshot is a gap in the chart, not
        # evidence of the algorithm's default 50% prior.
        value = data.get("overall_mastery") if isinstance(data, dict) else None
        try:
            mastery = float(value) if value is not None and not isinstance(value, bool) else None
        except (TypeError, ValueError):
            mastery = None
        if mastery is not None and (not math.isfinite(mastery) or not 0 <= mastery <= 1):
            mastery = None
        mastery_history.append({
            "date": snapshot.created_at.strftime("%d/%m/%Y %H:%M"),
            "mastery": round(mastery * 100, 1) if mastery is not None else None,
            "snapshot_id": snapshot.id,
        })

    return render_template(
        "practice_progress.html",
        subjects=subjects,
        selected_subject=selected_subject,
        profile=profile,
        history=history,
        mastery_history=mastery_history,
    )


def _student_practice_decision(submission_id):
    if current_user.role != "student":
        abort(403)
    submission = db.session.get(ExamSubmission, submission_id) or abort(404)
    exam = submission.exam
    metadata = exam.get_adaptive_metadata() if exam else {}
    session_id = metadata.get("practice_session_id")
    practice_session = db.session.get(PracticeSession, session_id) if session_id else None
    if (
        not exam or not practice_session or practice_session.student_id != current_user.id
        or submission.student_id != current_user.id or submission.exam_id != practice_session.last_exam_id
        or practice_session.course_id != exam.course_id
        or practice_session.scope_code != SCOPE_CODE
        or not blueprint.is_fixed(exam)
    ):
        abort(403)
    return submission, exam, practice_session


@login_required
def practice_continue(submission_id):
    submission, previous_exam, practice_session = _student_practice_decision(submission_id)
    if not practice_decision_is_ready(
        submission, previous_exam, practice_session, current_user.id
    ):
        flash("Bài làm chưa được lưu và cập nhật hồ sơ hoàn tất, hoặc lựa chọn này đã được xử lý.", "warning")
        return redirect(url_for("practice_result", exam_id=previous_exam.id))
    enrollment = Enrollment.query.filter_by(student_id=current_user.id,
        course_id=practice_session.course_id, status="active").first()
    if not enrollment or not enrollment.course or not enrollment.course.is_active:
        abort(403)
    bank_ids = practice_session.get_bank_ids()
    source_validation = validate_exam_source(previous_exam, require_live=True)
    manifest = source_validation.get("manifest") or {}
    if source_validation["valid"] and manifest.get("bank_ids"):
        if sorted(set(bank_ids)) != sorted(set(manifest.get("bank_ids") or [])):
            source_validation = {**source_validation, "valid": False, "reason": "session_source_mismatch"}
    if not source_validation["valid"]:
        flash("Nguồn câu hỏi của bài cũ không còn được giáo viên hiện tại của lớp cho phép; không thể sinh bài tiếp theo.", "warning")
        return redirect(url_for("practice_result", exam_id=previous_exam.id))
    previous_metadata = previous_exam.get_adaptive_metadata()
    teacher_origin = _teacher_issued_practice(previous_exam, current_user.id)
    if teacher_origin:
        # A teacher-issued paper may survive a class-teacher transfer only
        # when every bank captured by its session is still usable by the
        # current class teacher.  This keeps an authorized shared source alive
        # while rejecting a former teacher's private pool; it never rewrites
        # the frozen paper or its history.
        teacher_banks = _teacher_session_banks(enrollment.course, bank_ids)
        teacher_session = bool(
            teacher_banks
            and previous_exam.question_bank_id in {bank.id for bank in teacher_banks}
        )
        banks_authorized = teacher_session
        source_message = None
    else:
        teacher_session = False
        source_state = class_diagnostic_source(current_user.id, enrollment.course)
        source_bank = source_state.get("bank")
        banks_authorized = bool(
            source_state["status"] == "ready"
            and bank_ids == [source_bank.id]
            and previous_exam.question_bank_id == source_bank.id
        )
        source_message = source_state.get("message")
    if not banks_authorized:
        flash(
            source_message or "Nguồn câu hỏi của phiên không còn được giáo viên hiện tại của lớp cho phép; phiên đã được giữ để kiểm tra.",
            "warning",
        )
        return redirect(url_for("practice_result", exam_id=previous_exam.id))
    claimed = PracticeSession.query.filter_by(
        id=practice_session.id, student_id=current_user.id,
        status="awaiting_decision", last_submission_id=submission.id,
    ).update({
        PracticeSession.status: "generating",
        PracticeSession.updated_at: dt.datetime.utcnow(),
    }, synchronize_session=False)
    if claimed != 1:
        db.session.rollback()
        flash("Lựa chọn tiếp tục này đã được xử lý; không tạo thêm đề trùng.", "info")
        return redirect(url_for("practice_result", exam_id=previous_exam.id))
    db.session.expire(practice_session)
    teacher_constraints = previous_metadata.get("teacher_constraints") or {}
    constraints = {"blueprint": blueprint.VERSION}
    constraints.update({key: teacher_constraints.get(key, []) for key in ("chapters", "sections", "topics")})
    constraints["chapter"] = constraints.pop("chapters")
    constraints["section"] = constraints.pop("sections")
    constraints["topic"] = constraints.pop("topics")
    constraints["cognitive_levels"] = teacher_constraints.get("cognitive_levels", [])
    review_mix = previous_metadata.get("review_mix")
    if isinstance(review_mix, dict):
        constraints["review_mix"] = {
            key: (float(value) / 100 if float(value) > 1 else float(value))
            for key, value in review_mix.items()
        }
    constraints["course_id"] = enrollment.course.id
    selection = AdaptiveEngine.select_questions(
        current_user.id, practice_session.subject, bank_ids, blueprint.TOTAL,
        constraints=constraints,
    )
    if not selection["questions"]:
        db.session.rollback()
        flash(selection["explanation"], "warning")
        return redirect(url_for("practice_result", exam_id=previous_exam.id))
    source_questions = resolve_class_questions(
        enrollment.course, bank_ids, selection["questions"]
    )
    if (
        not source_questions["valid"]
        or len(source_questions["questions"]) != len(selection["questions"])
    ):
        db.session.rollback()
        flash("Bộ câu hỏi vừa chọn không còn thuộc nguồn được giáo viên hiện tại của lớp cho phép.", "warning")
        return redirect(url_for("practice_result", exam_id=previous_exam.id))
    title = f"Bài luyện tiếp theo · {practice_session.subject} · phiên {practice_session.id}"
    exam = _create_fixed_exam(
        selection=selection, course=enrollment.course, bank_ids=bank_ids,
        student_id=current_user.id, creator_id=current_user.id, title=title,
        is_active=True, practice_session=practice_session,
        metadata_extra={
            "review_mix": review_mix or AdaptiveEngine.REVIEW_MIX,
            "teacher_constraints": teacher_constraints,
            "continued_from_submission_id": submission.id,
            "practice_provenance": ({
                "kind": "teacher_assigned",
                "teacher_id": enrollment.course.teacher_id,
                "course_id": enrollment.course.id,
            } if teacher_session else {
                "kind": "class_diagnostic",
                "diagnostic_exam_id": source_state["exam"].id,
                "bank_id": source_bank.id,
                "course_id": enrollment.course.id,
            }),
        },
    )
    db.session.commit()
    flash("Hồ sơ mới nhất đã được dùng để tạo đề tiếp theo.", "success")
    return redirect(url_for("practice_take", exam_id=exam.id))


@login_required
def practice_end(submission_id):
    submission, exam, practice_session = _student_practice_decision(submission_id)
    if not practice_decision_is_ready(
        submission, exam, practice_session, current_user.id
    ):
        flash("Bài làm chưa được lưu và cập nhật hồ sơ hoàn tất, hoặc lựa chọn này đã được xử lý.", "warning")
        return redirect(url_for("practice_result", exam_id=exam.id))
    ended_at = dt.datetime.utcnow()
    changed = PracticeSession.query.filter_by(
        id=practice_session.id, student_id=current_user.id,
        status="awaiting_decision", last_submission_id=submission_id,
        last_exam_id=exam.id,
    ).update({
        PracticeSession.status: "ended",
        PracticeSession.ended_at: ended_at,
        PracticeSession.updated_at: ended_at,
    }, synchronize_session=False)
    if changed == 1:
        db.session.commit()
        flash("Đã lưu và kết thúc phiên luyện tập.", "success")
    else:
        db.session.rollback()
        flash("Lựa chọn của phiên này đã được xử lý trước đó.", "info")
    return redirect(url_for("practice_progress", subject=practice_session.subject))


@login_required
@role_required("teacher")
def teacher_practice_list():
    course_query = Course.query
    if current_user.role == 'teacher':
        course_query = course_query.filter_by(teacher_id=current_user.id)
    courses = course_query.order_by(Course.course_name).all()
    course_by_id = {course.id: course for course in courses}
    selected_id = request.args.get('course_id', type=int)
    if selected_id and selected_id not in course_by_id:
        abort(403)
    selected_course = course_by_id.get(selected_id)
    if current_user.role == 'admin' and not selected_course and courses:
        selected_course = courses[0]
    scope_ids = [selected_course.id] if selected_course else list(course_by_id)
    roster_by_student = {}
    if scope_ids:
        roster = Enrollment.query.filter(Enrollment.course_id.in_(scope_ids), Enrollment.status == 'active').all()
        for enrollment in roster:
            student = enrollment.student
            if not student or student.role != 'student':
                continue
            info = roster_by_student.setdefault(student.id, dict(student=student, courses={}))
            info['courses'][enrollment.course_id] = course_by_id[enrollment.course_id]
    attempts_by_student = {student_id: [] for student_id in roster_by_student}
    if roster_by_student:
        attempts = ExamSubmission.query.join(Exam).filter(
            ExamSubmission.student_id.in_(roster_by_student), Exam.course_id.in_(scope_ids),
            db.or_(ExamSubmission.exam_type == 'practice', Exam.assessment_purpose.in_(['initial_diagnostic', 'standalone'])),
        ).all()
        for attempt in attempts:
            if attempt.exam.course_id in roster_by_student[attempt.student_id]['courses']:
                attempts_by_student[attempt.student_id].append(attempt)
    students = []
    for student_id, info in roster_by_student.items():
        attempts = attempts_by_student[student_id]
        finished = [item for item in attempts if is_finalized(item)]
        practice = [item for item in finished if item.exam.assessment_purpose not in ('initial_diagnostic', 'standalone')]
        assessments = [item for item in finished if item.exam.assessment_purpose == 'standalone']
        scores = [item.percentage / 10 for item in finished if item.exam.assessment_purpose != 'standalone']
        dates = [item.submitted_at or item.started_at for item in attempts if item.submitted_at or item.started_at]
        students.append(dict(student=info['student'], courses=sorted(info['courses'].values(), key=lambda course: course.course_name.casefold()),
                             total_practice=len(practice), total_assessments=len(assessments), completed=len(finished),
                             latest_activity=max(dates) if dates else None,
                             average=round(sum(scores)/len(scores),1) if scores else None))
    students.sort(key=lambda row: row['student'].fullname.casefold())
    return render_template('teacher_practice_list.html', students=students, courses=courses, selected_course=selected_course)



@login_required
@role_required("teacher")
def teacher_practice_detail(student_id):
    student = db.session.get(User, student_id) or abort(404)
    if student.role != "student":
        abort(404)
    enrollments = Enrollment.query.filter_by(student_id=student.id, status="active").all()
    available_courses = [item.course for item in enrollments if item.course and (
        current_user.role == "admin" or item.course.teacher_id == current_user.id
    )]
    if current_user.role == "teacher" and not available_courses:
        abort(403)
    requested_course = request.args.get('course_id', type=int)
    course_choices = list(available_courses)
    if requested_course and requested_course not in {course.id for course in available_courses}:
        abort(403)
    if requested_course:
        available_courses = [course for course in available_courses if course.id == requested_course]
    course_ids = {course.id for course in available_courses}
    submissions = [item for item in ExamSubmission.query.filter_by(student_id=student.id)
                   .order_by(ExamSubmission.started_at.desc()).all() if item.exam
                   and item.exam.course_id in course_ids
                   and (item.exam_type == "practice" or item.exam.assessment_purpose in ("initial_diagnostic", "standalone"))]
    
    subjects = sorted({item.exam.course.subject for item in submissions if item.exam and item.exam.course})
    subjects = sorted(set(subjects) | {course.subject for course in available_courses})
    from services.teacher_learning import summarize_learning
    profiles = {subject: summarize_learning(submissions, subject) for subject in subjects}
    bank_query = QuestionBank.query.filter(QuestionBank.is_active.is_(True), QuestionBank.subject.in_(subjects))
    candidate_banks = bank_query.order_by(QuestionBank.subject, QuestionBank.name).all()
    # Bank selectors are class-bound.  Resolve candidates against each
    # selected course's current teacher, including for an administrator; a
    # broad admin audit permission must not turn a former teacher's private
    # bank into a usable source for another class.
    available_banks = [
        bank for bank in candidate_banks
        if any(resolve_class_banks(course, [bank.id])["valid"] for course in available_courses)
    ]
    bank_course_counts = {}
    for bank in available_banks:
        for course in available_courses:
            resolved = resolve_class_questions(course, [bank.id], bank.questions)
            bank_course_counts.setdefault(bank.id, {})[course.id] = len(resolved["questions"])
    ai_analyses = {}
    learning_reports = {}
    error_observations = {}
    for subject in subjects:
        subject_course_ids = [course.id for course in available_courses if course.subject == subject]
        run = AIAnalysisRun.query.filter(
            AIAnalysisRun.student_id == student.id, AIAnalysisRun.subject == subject,
            AIAnalysisRun.chapter_code == "8", AIAnalysisRun.course_id.in_(subject_course_ids),
            AIAnalysisRun.status == "completed",
        ).order_by(AIAnalysisRun.created_at.desc(), AIAnalysisRun.id.desc()).first() if subject_course_ids else None
        if run:
            ai_analyses[subject] = {
                "run": run, "result": run.get_response_data(), "request": run.get_request_data(),
                "course": next((course for course in available_courses if course.id == run.course_id), None),
            }
        report_types = [f"learning_profile_course_{course_id}" for course_id in subject_course_ids]
        report = TeacherLearningReport.query.filter(
            TeacherLearningReport.student_id == student.id,
            TeacherLearningReport.subject == subject,
            TeacherLearningReport.report_type.in_(report_types),
        ).order_by(TeacherLearningReport.generated_at.desc(), TeacherLearningReport.id.desc()).first() if report_types else None
        if report:
            report_course_id = report.get_payload().get("course_id")
            report_course = next((course for course in available_courses if course.id == report_course_id), None)
            learning_reports[subject] = {
                "report": report,
                "course": report_course,
                # A new all-correct finalised diagnostic/practice attempt has
                # no wrong-answer ref, but still invalidates an old report.
                "stale": _teacher_report_is_stale(report, report_course),
            }
        raw_observations = ErrorObservation.query.join(
            SubmissionAnswer, ErrorObservation.submission_answer_id == SubmissionAnswer.id
        ).join(ExamQuestion, SubmissionAnswer.question_id == ExamQuestion.id).join(
            Exam, ExamQuestion.exam_id == Exam.id
        ).filter(
            ErrorObservation.student_id == student.id, ErrorObservation.subject == subject,
            ErrorObservation.status == "observed", Exam.course_id.in_(subject_course_ids),
        ).order_by(ErrorObservation.created_at.desc(), ErrorObservation.id.desc()).limit(20).all() if subject_course_ids else []
        # Do not surface stale observations from historical manual/file-only
        # answers, even when an older row was marked observed before phase 3.
        error_observations[subject] = [
            row for row in raw_observations
            if row.answer and answer_status(row.answer) in ("answered", "graded")
        ]
    availability_gateway = GeminiAIGateway()
    ai_api_configured = any(
        not _configuration_unavailable(availability_gateway, course) for course in available_courses
    )
    return render_template(
        "teacher_practice_detail.html", student=student, submissions=submissions, profiles=profiles, course_choices=course_choices, selected_course_id=requested_course,
        visible_bank_counts={
            bank.id: max(bank_course_counts.get(bank.id, {}).values(), default=0)
            for bank in available_banks
        },
        bank_course_counts=bank_course_counts,
        available_courses=available_courses, available_banks=available_banks, ai_analyses=ai_analyses,
        learning_reports=learning_reports, error_observations=error_observations,
        ai_api_configured=ai_api_configured,
    )


@login_required
@role_required("teacher")
def teacher_run_ai_analysis(student_id):
    # This paid action must be initiated by the actual assigned teacher, not
    # merely an administrator admitted by the legacy role decorator.
    if current_user.role != "teacher":
        abort(403)
    student = db.session.get(User, student_id) or abort(404)
    if student.role != "student":
        abort(404)
    subject = request.form.get("subject", "Toán").strip()
    course = db.session.get(Course, request.form.get("course_id", type=int)) or abort(404)
    enrollment = Enrollment.query.filter_by(student_id=student.id, course_id=course.id, status="active").first()
    if not enrollment or course.subject != subject or course.teacher_id != current_user.id:
        abort(403)
    evidence_revision = source_revision(student.id, subject, course_id=course.id)
    from services.ai_profile_analysis import AIProfileAnalyzer
    analyzer = AIProfileAnalyzer()
    run, cached = analyzer.analyze(
        student.id, subject=subject, requested_by=current_user.id, course=course,
        allow_legacy=GeminiAIGateway.legacy_enabled_for_unassigned_course(course),
        force=request.form.get("force") == "1",
    )
    if cached:
        flash("Đang hiển thị phân tích AI đã lưu vì dữ liệu học tập chưa thay đổi.", "info")
    elif run.status == "completed":
        flash("AI đã phân tích xong năng lực Chương 8, bài kết hợp 25 + 26.", "success")
    else:
        flash(f"Không thể phân tích bằng AI: {run.error_message or 'Lỗi kết nối AI API'}. Hệ thống chỉ gọi AI API trực tiếp (không dùng phương án dự phòng).", "danger")
        return redirect(url_for("teacher_practice_detail", student_id=student.id))
    profile = AdaptiveEngine.analyze_performance(student.id, subject)
    report = report_payload(student.id, subject, profile, course_id=course.id)
    report["ai_analysis"] = run.get_response_data()
    report["ai_run_id"] = run.id
    report["ai_run_status"] = run.status
    report["analysis_source"] = "ai_api"
    upsert_teacher_report(
        student.id, subject, report, generated_by=current_user.id,
        report_type=f"learning_profile_course_{course.id}", course_id=course.id,
        source_revision_value=evidence_revision,
    )
    db.session.commit()
    return redirect(url_for("teacher_practice_detail", student_id=student.id))


@login_required
@role_required("teacher")
def teacher_generate_adaptive_practice(student_id):
    student = db.session.get(User, student_id) or abort(404)
    course = db.session.get(Course, request.form.get("course_id", type=int)) or abort(404)
    enrollment = Enrollment.query.filter_by(student_id=student.id, course_id=course.id, status="active").first()
    if not enrollment or (current_user.role == "teacher" and course.teacher_id != current_user.id):
        abort(403)
    profile_state = learner_profile_state(student.id, course.subject, course_id=course.id)
    if not profile_state["initialized"]:
        flash("Học sinh cần hoàn tất bài đánh giá đầu vào bài kết hợp 25 + 26 trước khi nhận đề cá nhân hóa.", "warning")
        return redirect(url_for("teacher_practice_detail", student_id=student.id))
    try:
        raw_bank_ids = request.form.getlist("bank_ids")
        parsed_bank_ids = [int(value) for value in raw_bank_ids]
        if (
            not parsed_bank_ids
            or len(parsed_bank_ids) != len(set(parsed_bank_ids))
            or any(value <= 0 for value in parsed_bank_ids)
        ):
            raise ValueError
        bank_ids = set(parsed_bank_ids)
        total = blueprint.TOTAL
        review_mix = {
            "weak": max(0, int(request.form.get("mix_weak", 60))),
            "middle": max(0, int(request.form.get("mix_middle", 25))),
            "strong": max(0, int(request.form.get("mix_strong", 15))),
        }
    except (TypeError, ValueError):
        flash("Cấu hình bài luyện không hợp lệ.", "danger")
        return redirect(url_for("teacher_practice_detail", student_id=student.id))
    if sum(review_mix.values()) != 100:
        flash("Tỷ lệ vùng yếu, trung bình và duy trì phải bằng 100%.", "warning")
        return redirect(url_for("teacher_practice_detail", student_id=student.id))
    # Re-resolve every requested bank against the teacher currently assigned
    # to this class.  In particular, an administrator request must not use
    # ``can_use_bank(admin, bank)`` to bypass a former/current teacher's
    # private scope.
    banks = _teacher_session_banks(course, bank_ids)
    if not banks or len(banks) != len(bank_ids):
        flash("Hãy chọn ngân hàng thuộc đúng môn học và được giáo viên hiện tại của lớp cho phép sử dụng.", "warning")
        return redirect(url_for("teacher_practice_detail", student_id=student.id))

    def csv_values(name):
        return [value.strip() for value in request.form.get(name, "").split(",") if value.strip()]

    levels = [value for value in request.form.getlist("cognitive_levels") if value in ("nhan_biet", "thong_hieu", "van_dung", "van_dung_cao")]
    selection = AdaptiveEngine.select_questions(student.id, course.subject, list(bank_ids), total, constraints={
        "blueprint": blueprint.VERSION,
        "course_id": course.id,
        "chapter": csv_values("chapters"), "section": csv_values("sections"), "topic": csv_values("topics"),
        "cognitive_levels": levels, "review_mix": {key: value / 100 for key, value in review_mix.items()},
    })
    if not selection["questions"]:
        flash(selection["explanation"], "warning")
        return redirect(url_for("teacher_practice_detail", student_id=student.id))
    source_questions = resolve_class_questions(course, sorted(bank_ids), selection["questions"])
    if (
        not source_questions["valid"]
        or len(source_questions["questions"]) != len(selection["questions"])
    ):
        flash("Bộ câu hỏi vừa chọn không còn thuộc nguồn được giáo viên hiện tại của lớp cho phép.", "warning")
        return redirect(url_for("teacher_practice_detail", student_id=student.id))
    for old_session in PracticeSession.query.filter_by(
        student_id=student.id, course_id=course.id, subject=course.subject
    ).filter(PracticeSession.status.in_(("active", "awaiting_decision"))).all():
        old_session.status = "superseded"
        old_session.ended_at = dt.datetime.utcnow()
    practice_session = PracticeSession(
        student_id=student.id, course_id=course.id, subject=course.subject,
        bank_ids=json.dumps(sorted(bank_ids)), status="active",
    )
    db.session.add(practice_session)
    db.session.flush()
    exam = _create_fixed_exam(
        selection=selection, course=course, bank_ids=sorted(bank_ids),
        student_id=student.id, creator_id=current_user.id,
        title=f"Bài luyện cá nhân hóa - {student.fullname} - {course.subject}",
        is_active=False, practice_session=practice_session,
        metadata_extra={
            "review_mix": review_mix,
            "practice_provenance": {
                "kind": "teacher_assigned",
                "teacher_id": course.teacher_id,
                "course_id": course.id,
            },
            "teacher_constraints": {
                "chapters": csv_values("chapters"), "sections": csv_values("sections"),
                "topics": csv_values("topics"), "cognitive_levels": levels,
            },
        },
    )
    db.session.commit()
    flash(f"Đã tạo bản nháp {len(selection['questions'])} câu. {selection['explanation']}", "success")
    return redirect(url_for("teacher_practice_draft", exam_id=exam.id))


@login_required
@role_required("teacher")
def teacher_practice_draft(exam_id):
    """Review and publish a generated 22-item practice paper.

    This deliberately owns only fixed practice drafts.  Traditional exam
    editing is not a fallback path for publishing adaptive practice.
    """
    exam = db.session.get(Exam, exam_id) or abort(404)
    if not blueprint.is_fixed(exam) or exam.exam_type != "practice":
        abort(404)
    if current_user.role == "teacher" and exam.created_by != current_user.id:
        abort(403)
    if request.method == "POST":
        # The question snapshot is frozen at generation; only the draft's
        # release state remains mutable.  Re-resolve every source before
        # allowing publication so a former class teacher cannot release a
        # paper containing a private overlay that the current class teacher
        # may no longer use.  Legacy drafts without a manifest remain
        # compatible and are checked by the historical route contract.
        source_state = validate_exam_source(exam, require_live=True)
        publish_requested = request.form.get("is_active") in ("1", "on", "true", "yes")
        if (
            publish_requested
            and current_user.role == "teacher"
            and (not exam.course or exam.course.teacher_id != current_user.id)
        ):
            # A former teacher may close their old draft, but cannot publish
            # it after class authority has transferred.
            abort(403)
        if publish_requested and not source_state["valid"]:
            flash("Nguồn câu hỏi của bản nháp không còn được giáo viên hiện tại của lớp cho phép; không thể phát hành.", "warning")
            return redirect(url_for("teacher_practice_draft", exam_id=exam.id))
        if ExamSubmission.query.filter_by(exam_id=exam.id).first():
            flash("Đề đã có bài làm; không được sửa bản chụp đã sử dụng.", "warning")
        else:
            try:
                duration = int(request.form.get("duration_minutes", exam.duration_minutes))
                title = request.form.get("title", exam.title).strip()
                if not title or not 5 <= duration <= 180:
                    raise ValueError
                exam.title = title
                exam.duration_minutes = duration
                exam.is_active = publish_requested
                db.session.commit()
                flash("Đã lưu trạng thái phát hành; giữ nguyên 22 câu và hồ sơ lựa chọn.", "success")
            except (TypeError, ValueError):
                db.session.rollback()
                flash("Tiêu đề không được trống; thời gian từ 5 đến 180 phút.", "warning")
        return redirect(url_for("teacher_practice_draft", exam_id=exam.id))
    source_state = validate_exam_source(exam, require_live=True)
    return render_template(
        "practice_draft.html", exam=exam,
        draft_locked=ExamSubmission.query.filter_by(exam_id=exam.id).first() is not None,
        draft_source_valid=source_state["valid"],
        draft_source_message=("Nguồn câu hỏi không còn được giáo viên hiện tại của lớp cho phép. Có thể lưu bản nháp hoặc đóng đề; cần kiểm tra nguồn trước khi phát hành." if not source_state["valid"] else ""),
        draft_can_publish=current_user.role == "admin" or bool(exam.course and exam.course.teacher_id == current_user.id),
    )


@login_required
@role_required("teacher")
def teacher_analytics():
    selected = request.args.get('student_id', type=int)
    if selected:
        return redirect(url_for('teacher_practice_detail', student_id=selected))
    return redirect(url_for('teacher_practice_list'))



def _teacher_student_courses(student_id):
    """Return courses through which the current teacher may view a student."""
    query = Enrollment.query.join(Course).filter(
        Enrollment.student_id == student_id, Enrollment.status == "active"
    )
    if current_user.role == "teacher":
        query = query.filter(Course.teacher_id == current_user.id)
    return [row.course for row in query.all() if row.course]


@login_required
@role_required("teacher")
def teacher_review_error(student_id, observation_id):
    observation = db.session.get(ErrorObservation, observation_id) or abort(404)
    if observation.student_id != student_id or not _teacher_student_courses(student_id):
        abort(403)
    answer = db.session.get(SubmissionAnswer, observation.submission_answer_id)
    report_course = answer.question.exam.course if answer and answer.question and answer.question.exam else None
    if not report_course or (current_user.role == "teacher" and report_course.teacher_id != current_user.id):
        abort(403)
    if request.method == "POST":
        status = request.form.get("status", "reviewed").strip()
        if status not in ("observed", "reviewed", "dismissed"):
            abort(400)
        observation.status = status
        observation.teacher_note = request.form.get("teacher_note", "").strip()[:2000] or None
        observation.reviewed_by = current_user.id
        observation.reviewed_at = dt.datetime.utcnow()
        db.session.commit()
        flash("Đã cập nhật nhận định lỗi quan sát.", "success")
    return redirect(url_for("teacher_practice_detail", student_id=student_id))


@login_required
@role_required("teacher")
def teacher_review_report(student_id, report_id):
    report = db.session.get(TeacherLearningReport, report_id) or abort(404)
    if report.student_id != student_id or not _teacher_student_courses(student_id):
        abort(403)
    prefix = "learning_profile_course_"
    if not (report.report_type or "").startswith(prefix):
        # Legacy subject-only artifacts remain in the database but are not
        # surfaced/reviewed in a teacher's per-course AI workspace.
        abort(403)
    try:
        report_course_id = int(report.report_type[len(prefix):])
    except (TypeError, ValueError):
        abort(403)
    report_course = db.session.get(Course, report_course_id)
    enrollment = Enrollment.query.filter_by(
        student_id=student_id, course_id=report_course_id, status="active"
    ).first()
    if not report_course or not enrollment or (current_user.role == "teacher" and report_course.teacher_id != current_user.id):
        abort(403)
    if report.source_revision != source_revision(student_id, report.subject, course_id=report_course_id):
        flash("Báo cáo đã cũ vì có bằng chứng bài làm mới; hãy tạo lại trước khi duyệt.", "warning")
        return redirect(url_for("teacher_practice_detail", student_id=student_id))
    report_payload_data = report.get_payload()
    run_id = report_payload_data.get("ai_run_id")
    if run_id:
        run = db.session.get(AIAnalysisRun, run_id)
        gateway = GeminiAIGateway()
        try:
            configuration = gateway.resolve_course(
                report_course, allow_legacy=GeminiAIGateway.legacy_enabled_for_unassigned_course(report_course)
            )
        except AIConfigurationError:
            configuration = None
        current_identity = (
            configuration.source, configuration.group_id, configuration.config_revision,
            configuration.provider, configuration.model_name,
        ) if configuration else None
        run_identity = (run.ai_credential_source, run.ai_key_group_id, run.ai_config_revision,
                        run.provider, run.model_name) if run else None
        if not run or run.course_id != report_course_id or current_identity != run_identity:
            flash("Báo cáo AI đã cũ vì cấu hình khóa học thay đổi; hãy tạo lại trước khi duyệt.", "warning")
            return redirect(url_for("teacher_practice_detail", student_id=student_id))
    if request.method == "POST":
        payload = report_payload_data
        # A deterministic provider-outage fallback can be annotated, but is
        # never marked as a reviewed/verified AI conclusion.
        report.status = "reviewed" if payload.get("ai_run_status") == "completed" else "reviewed_observed"
        report.reviewed_by = current_user.id
        report.review_note = request.form.get("review_note", "").strip()[:2000] or None
        correction = request.form.get("correction_text", "").strip()
        report.correction_payload = json.dumps({"text": correction}, ensure_ascii=False) if correction else None
        report.reviewed_at = dt.datetime.utcnow()
        db.session.commit()
        flash("Đã lưu trạng thái duyệt báo cáo.", "success")
    return redirect(url_for("teacher_practice_detail", student_id=student_id))




def register_practice_routes(app) -> None:
    """Register practice and analytics handlers with legacy endpoint names."""
    app.add_url_rule("/practice", endpoint="practice_home", view_func=practice_home)
    app.add_url_rule("/practice/generate", endpoint="practice_generate", view_func=practice_generate, methods=["POST"])
    app.add_url_rule("/practice/progress", endpoint="practice_progress", view_func=practice_progress)
    app.add_url_rule("/practice/submissions/<int:submission_id>/continue", endpoint="practice_continue", view_func=practice_continue, methods=["POST"])
    app.add_url_rule("/practice/submissions/<int:submission_id>/end", endpoint="practice_end", view_func=practice_end, methods=["POST"])
    app.add_url_rule("/teacher/practice", endpoint="teacher_practice_list", view_func=teacher_practice_list)
    app.add_url_rule("/teacher/practice/<int:student_id>", endpoint="teacher_practice_detail", view_func=teacher_practice_detail)
    app.add_url_rule("/teacher/practice/<int:student_id>/ai-analysis", endpoint="teacher_run_ai_analysis", view_func=teacher_run_ai_analysis, methods=["POST"])
    app.add_url_rule("/teacher/practice/<int:student_id>/errors/<int:observation_id>/review", endpoint="teacher_review_error", view_func=teacher_review_error, methods=["POST"])
    app.add_url_rule("/teacher/practice/<int:student_id>/reports/<int:report_id>/review", endpoint="teacher_review_report", view_func=teacher_review_report, methods=["POST"])
    app.add_url_rule("/teacher/practice/<int:student_id>/generate", endpoint="teacher_generate_adaptive_practice", view_func=teacher_generate_adaptive_practice, methods=["POST"])
    app.add_url_rule("/teacher/practice/drafts/<int:exam_id>", endpoint="teacher_practice_draft", view_func=teacher_practice_draft, methods=["GET", "POST"])
    app.add_url_rule("/analytics/teacher", endpoint="teacher_analytics", view_func=teacher_analytics)
