"""Student practice runtime: taking, submitting and viewing a paper.

Initial diagnostic authoring lives in :mod:`routes.diagnostics`; no teacher
grading route is used by this runtime.
Runtime handlers here accept explicit practice papers and the legacy
``initial_diagnostic`` purpose, including diagnostics whose ``exam_type`` is
still the historical ``exam`` value.
"""

from __future__ import annotations

import datetime as dt
import json
import random

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from adaptive_engine import AdaptiveEngine
from database import db
from models import (
    DiagnosticAssignment,
    Exam,
    ExamSubmission,
    PracticeSession,
    SubmissionAnswer,
)
from services import practice_blueprint as blueprint
from services.diagnostic_service import SCOPE_CODE, complete_diagnostic_assignment
from services.personalization_evidence import canonical_json, content_hash, is_finalized
from services.practice_runtime import (
    is_practice_runtime_exam,
    practice_decision_is_ready,
    student_can_access_exam,
    teacher_can_access_submission,
)
from services.question_policy import canonical_type


def _get_practice_exam(exam_id, standalone=False):
    exam = db.session.get(Exam, exam_id) or abort(404)
    if standalone:
        if exam.assessment_purpose != 'standalone':
            abort(404)
        return exam
    if not is_practice_runtime_exam(exam):
        # The practice route must never become a second way to take a
        # traditional exam.
        abort(404)
    return exam


def _practice_result_url(exam_id):
    return url_for('assessment_result' if request.endpoint == 'assessment_take' else 'practice_result', exam_id=exam_id)


def _practice_auto_scoring_error(exam):
    """Return the first reason a new paper cannot be auto-scored."""
    for question in exam.questions:
        error = blueprint.auto_scoring_error(question)
        if error:
            return error
    return None


def _claim_grading_slot(exam, student_id, fixed_practice, now):
    """Claim a new runtime submission without committing a partial grade.

    New fixed papers have a persisted session, so a conditional state update
    gives concurrent POSTs one winner.  Initial diagnostics use their unique
    assignment row for the equivalent ``assigned -> grading`` claim.  Both
    claims are in the same transaction as answers, evidence and mastery; an
    exception rolls the transient state back for a clean retry.

    Some pre-Phase-3 practice rows have no session.  They remain readable and
    gradeable using their historical behavior, but cannot gain a new durable
    concurrency guard without changing their stored contract.
    """
    if fixed_practice:
        session_id = exam.get_adaptive_metadata().get("practice_session_id")
        practice_session = db.session.get(PracticeSession, session_id) if session_id else None
        if not practice_session:
            # Truly historical fixed rows predate persistent sessions and keep
            # their old behavior.  A paper that names a now-missing session is
            # inconsistent new data and must not silently bypass its claim.
            return None, None, session_id is None
        claimed = PracticeSession.query.filter_by(
            id=practice_session.id,
            student_id=student_id,
            course_id=exam.course_id,
            scope_code=SCOPE_CODE,
            status="active",
            last_exam_id=exam.id,
        ).update({
            PracticeSession.status: "submitting",
            PracticeSession.updated_at: now,
        }, synchronize_session=False)
        if claimed != 1:
            return None, None, False
        db.session.expire(practice_session)
        return practice_session.id, None, True

    if exam.assessment_purpose != "initial_diagnostic":
        # Historical non-fixed practice is retained for reading/grading but
        # has no Phase-4 session or diagnostic-assignment contract to claim.
        return None, None, True

    assignment = DiagnosticAssignment.query.filter_by(
        exam_id=exam.id, student_id=student_id
    ).first()
    if not assignment:
        return None, None, False
    claimed = DiagnosticAssignment.query.filter_by(
        id=assignment.id, status="assigned"
    ).update({DiagnosticAssignment.status: "grading"}, synchronize_session=False)
    if claimed != 1:
        return None, None, False
    db.session.expire(assignment)
    return None, assignment.id, True


@login_required
def practice_take(exam_id, standalone=False):
    """Render/submit a practice or initial-diagnostic paper."""
    if current_user.role != "student":
        abort(403)
    if standalone and request.method == 'POST':
        # Serialize one-attempt checks with publication/edit transactions.
        from services.import_transactions import lock_import_transaction
        lock_import_transaction()
    exam = _get_practice_exam(exam_id, standalone)
    take_endpoint = 'assessment_take' if standalone else 'practice_take'
    home_endpoint = 'assessment_list' if standalone else 'practice_home'
    if not student_can_access_exam(exam, current_user.id, require_live_source=True):
        abort(403)

    if exam.status_label != "open":
        flash("Bài kiểm tra chưa mở hoặc đã đóng.", "warning")
        return redirect(url_for(home_endpoint))

    # Student submissions are text/choice only.  Reject multipart file
    # payloads before creating a submission; no upload path is ever persisted.
    if request.method == "POST":
        if any(
            getattr(file_obj, "filename", "").strip()
            for key in request.files
            for file_obj in request.files.getlist(key)
        ):
            flash("Tệp bài làm không được hỗ trợ; hãy nhập câu trả lời bằng văn bản.", "danger")
            return redirect(url_for(take_endpoint, exam_id=exam.id))

    fixed_practice = blueprint.is_fixed(exam)
    if exam.exam_type == "exam":
        # Diagnostics historically use the ``exam`` type.  Keep their
        # one-submission guard while routing them through this module.
        existing = ExamSubmission.query.filter_by(
            exam_id=exam.id, student_id=current_user.id
        ).first()
        if existing and is_finalized(existing):
            flash("Bạn đã làm bài kiểm tra này rồi.", "info")
            return redirect(_practice_result_url(exam.id))
    if fixed_practice:
        existing_practice = ExamSubmission.query.filter_by(
            exam_id=exam.id, student_id=current_user.id
        ).filter(ExamSubmission.submitted_at.isnot(None)).order_by(
            ExamSubmission.submitted_at.desc(), ExamSubmission.id.desc()
        ).first()
        if existing_practice:
            flash(
                "Bài luyện này đã được nộp; hãy chọn Tiếp tục để nhận đề mới từ hồ sơ đã cập nhật.",
                "info",
            )
            return redirect(_practice_result_url(exam.id))
    scoring_error = _practice_auto_scoring_error(exam)
    if scoring_error:
        flash(f"Bài này chưa sẵn sàng để chấm tự động: {scoring_error}", "warning")
        return redirect(url_for("diagnostic_list" if exam.assessment_purpose == "initial_diagnostic" else "practice_home"))

    # A fixed practice paper uses its published order.  Diagnostic papers and
    # traditional exam-shaped legacy rows keep the historical shuffle rules.
    questions = list(exam.questions)
    if fixed_practice:
        questions.sort(key=lambda q: (
            list(blueprint.TYPE_QUOTAS).index(q.question_type),
            q.order_index or 0,
            q.id,
        ))
    if exam.shuffle_questions and not fixed_practice:
        random.shuffle(questions)

    if exam.shuffle_answers:
        for question in questions:
            question._shuffled_answers = list(question.answers)
            # Fixed true/false statements are published in their source order;
            # single-choice options may still be shuffled as before.
            if not fixed_practice or question.question_type == "single":
                random.shuffle(question._shuffled_answers)
    else:
        for question in questions:
            question._shuffled_answers = list(question.answers)
    for question in questions:
        if canonical_type(question.question_type) == "short_answer":
            question._practice_short_rule = blueprint.metadata(question).get("short_answer", {})

    if request.method == "POST":
        submitted_at = dt.datetime.utcnow()
        try:
            client_elapsed = max(0, int(request.form.get("time_spent_seconds", 0)))
        except (TypeError, ValueError):
            client_elapsed = 0
        client_elapsed = min(
            client_elapsed,
            max(60, int(exam.duration_minutes or 30) * 60 + 300),
        )
        try:
            session_id, _assignment_id, claimed = _claim_grading_slot(
                exam, current_user.id, fixed_practice, submitted_at
            )
            if not claimed:
                db.session.rollback()
                existing = ExamSubmission.query.filter_by(
                    exam_id=exam.id, student_id=current_user.id
                ).filter(ExamSubmission.submitted_at.isnot(None)).first()
                if existing and is_finalized(existing):
                    flash("Bài làm này đã được ghi nhận; hệ thống không tạo thêm lượt nộp.", "info")
                    return redirect(_practice_result_url(exam.id))
                flash("Bài làm đang được lưu ở một yêu cầu khác. Hãy chờ rồi mở lại kết quả.", "info")
                return redirect(url_for(take_endpoint, exam_id=exam.id))

            # A diagnostic has a single submission.  If an old interrupted
            # draft exists, rebuild its answers from this POST rather than
            # leaving stale selections mixed with the finalized attempt.
            submission = ExamSubmission.query.filter_by(
                exam_id=exam.id, student_id=current_user.id
            ).filter(ExamSubmission.submitted_at.is_(None)).order_by(
                ExamSubmission.id.desc()
            ).first()
            if submission:
                SubmissionAnswer.query.filter_by(submission_id=submission.id).delete()
                db.session.expire(submission, ["answers"])
            else:
                submission = ExamSubmission(
                    exam_id=exam.id,
                    student_id=current_user.id,
                    # Keep pre-Phase-4 runtime rows' persisted type; only a
                    # diagnostic is necessarily an ``exam`` row.
                    exam_type=exam.exam_type,
                )
                db.session.add(submission)
                db.session.flush()
            submission.started_at = submitted_at - dt.timedelta(seconds=client_elapsed)

            total_score = 0
            max_score = 0

            def question_time(question_id):
                try:
                    value = max(0, int(request.form.get(f"time_q_{question_id}", 0)))
                except (TypeError, ValueError):
                    value = 0
                return min(
                    value,
                    client_elapsed or value,
                    max(60, int(exam.duration_minutes or 30) * 60),
                )

            for question in exam.questions:
                max_score += question.points
                q_type = canonical_type(question.question_type)

                if q_type in ("truefalse", "true_false"):
                    answers = question.answers
                    correct_statements = 0
                    selected_dict = {}
                    for answer in answers:
                        choice = request.form.get(f"q_{question.id}_ans_{answer.id}")
                        if choice == "1":
                            selected_dict[str(answer.id)] = True
                            correct_statements += int(bool(answer.is_correct))
                        elif choice == "0":
                            selected_dict[str(answer.id)] = False
                            correct_statements += int(not bool(answer.is_correct))
                        else:
                            selected_dict[str(answer.id)] = None
                    total_statements = len(answers)
                    if fixed_practice:
                        multiplier = blueprint.TF_POINTS[min(correct_statements, 4)] if total_statements else 0
                        points_earned = round(question.points * multiplier, 2)
                    elif standalone:
                        points_earned = round(question.points * correct_statements / total_statements, 4) if total_statements else 0
                    elif correct_statements == total_statements:
                        points_earned = question.points
                    elif correct_statements == 3:
                        points_earned = .5
                    elif correct_statements == 2:
                        points_earned = .25
                    elif correct_statements == 1:
                        points_earned = .1
                    else:
                        points_earned = 0
                    is_correct = bool(total_statements and correct_statements == total_statements)
                    total_score += points_earned
                    answer_state = "answered" if any(value is not None for value in selected_dict.values()) else "unanswered"
                    actual = selected_dict
                    answer = SubmissionAnswer(
                        submission_id=submission.id, question_id=question.id,
                        selected_answer_ids=json.dumps([item.id for item in answers if actual.get(str(item.id)) is True]),
                        answer_text=json.dumps(actual), is_correct=is_correct,
                        points_earned=points_earned, time_spent_seconds=question_time(question.id),
                        answer_status=answer_state, answer_snapshot=canonical_json({"actual": actual}),
                    )
                elif q_type == "short_answer":
                    text_ans = request.form.get(f"q_{question.id}_text", "").strip()
                    rule = blueprint.metadata(question).get("short_answer", {})
                    correct_answers = [item.answer_text.strip() for item in question.answers if item.answer_text and item.is_correct]
                    is_correct, answer_state = blueprint.grade_short(text_ans, correct_answers, rule)
                    points_earned = question.points if is_correct else 0
                    total_score += points_earned
                    actual = {"text": text_ans}
                    answer = SubmissionAnswer(
                        submission_id=submission.id, question_id=question.id,
                        selected_answer_ids="[]", answer_text=json.dumps(actual), is_correct=is_correct,
                        points_earned=points_earned, time_spent_seconds=question_time(question.id),
                        answer_status=answer_state, answer_snapshot=canonical_json({"actual": actual}),
                    )
                else:
                    values = request.form.getlist(f"q_{question.id}") if q_type == "multi" else [request.form.get(f"q_{question.id}")]
                    selected_ids = [int(value) for value in values if value]
                    correct_ids = {item.id for item in question.answers if item.is_correct}
                    is_correct = bool(selected_ids) and set(selected_ids) == correct_ids
                    points_earned = question.points if is_correct else 0
                    total_score += points_earned
                    actual = {"selected_answer_ids": selected_ids}
                    answer = SubmissionAnswer(
                        submission_id=submission.id, question_id=question.id,
                        selected_answer_ids=json.dumps(selected_ids), is_correct=is_correct,
                        points_earned=points_earned, time_spent_seconds=question_time(question.id),
                        answer_status="answered" if selected_ids else "unanswered",
                        answer_snapshot=canonical_json({"actual": actual}),
                    )
                answer.evidence_hash = content_hash({"question": question.source_content_hash, "actual": actual})
                db.session.add(answer)

            db.session.flush()
            db.session.expire(submission, ["answers"])
            graded_answers = list(submission.answers)
            revision = max(1, int(submission.grading_revision or 0) + 1)
            submission.total_score = total_score
            submission.max_score = max_score
            submission.is_graded = True
            submission.status = "graded"
            submission.grading_revision = revision
            submission.finalized_at = submitted_at
            submission.submitted_at = submitted_at
            submission.time_spent_seconds = client_elapsed
            submission.correct_count = sum(1 for answer in graded_answers if answer.is_correct)
            submission.wrong_count = max(0, len(exam.questions) - submission.correct_count)
            for answer in graded_answers:
                answer.grading_revision = revision

            if not standalone:
                AdaptiveEngine.update_performance(current_user.id, submission, commit=False)
                complete_diagnostic_assignment(submission)
            if session_id:
                transitioned = PracticeSession.query.filter_by(
                    id=session_id, student_id=current_user.id,
                    status="submitting", last_exam_id=exam.id,
                ).update({
                    PracticeSession.last_submission_id: submission.id,
                    PracticeSession.status: "awaiting_decision",
                    PracticeSession.updated_at: submitted_at,
                }, synchronize_session=False)
                if transitioned != 1:
                    raise RuntimeError("Phiên làm bài không còn gắn với đề hiện tại.")
            # Score, answers, profile facts, error observations, diagnostic
            # completion and the session decision state commit together.
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Không thể lưu đồng thời bài làm và hồ sơ năng lực"
            )
            flash(
                "Chưa thể lưu trọn vẹn bài làm và hồ sơ năng lực. Vui lòng nộp lại; hệ thống chưa ghi nhận bản dở dang.",
                "danger",
            )
            return redirect(url_for(take_endpoint, exam_id=exam.id))

        flash(f"Đã nộp bài! Điểm: {submission.score_on_ten}/10", "success")
        return redirect(_practice_result_url(exam.id))

    return render_template("exam_take.html", exam=exam, questions=questions)


def _student_can_view_practice_result(exam):
    if current_user.role != "student" or not student_can_access_exam(exam, current_user.id):
        abort(403)


@login_required
def practice_result(exam_id, standalone=False):
    """Show a student's practice result or the teacher/admin result list."""
    exam = _get_practice_exam(exam_id, standalone)
    if standalone and current_user.role == 'teacher' and exam.course.teacher_id != current_user.id:
        abort(403)
    submission_id = request.args.get("submission_id", type=int)

    if current_user.role == "student":
        _student_can_view_practice_result(exam)
        query = ExamSubmission.query.filter_by(
            exam_id=exam.id, student_id=current_user.id
        )
        if submission_id:
            submission = query.filter_by(id=submission_id).first()
        else:
            submission = query.order_by(ExamSubmission.started_at.desc()).first()
        if not submission:
            flash("Bạn chưa nộp đề kiểm tra này." if standalone else "Bạn chưa làm bài tự luyện này.", "warning")
            return redirect(url_for("assessment_list" if standalone else "practice_home"))
        session_id = exam.get_adaptive_metadata().get("practice_session_id")
        practice_session = db.session.get(PracticeSession, session_id) if session_id else None
        can_decide = practice_decision_is_ready(
            submission, exam, practice_session, current_user.id
        )
        from services.source_resolver import validate_exam_source
        can_continue = bool(
            can_decide and validate_exam_source(exam, require_live=True)["valid"]
        )
        return render_template(
            "exam_result.html",
            exam=exam,
            submission=submission,
            single_view=True,
            practice_session=practice_session,
            can_decide=can_decide,
            can_continue=can_continue,
            diagnostic_complete=bool(
                exam.assessment_purpose == "initial_diagnostic"
                and is_finalized(submission)
            ),
        )

    if current_user.role in ("admin", "teacher"):
        if submission_id:
            submission = db.session.get(ExamSubmission, submission_id) or abort(404)
            if submission.exam_id != exam.id:
                abort(404)
            if current_user.role == "teacher" and not teacher_can_access_submission(exam, submission, current_user):
                abort(403)
            return render_template(
                "exam_result.html",
                exam=exam,
                submission=submission,
                single_view=True,
                can_decide=False,
                can_continue=False,
                diagnostic_complete=False,
            )

        if current_user.role == "admin":
            submissions = ExamSubmission.query.filter_by(exam_id=exam.id).order_by(
                ExamSubmission.total_score.desc()
            ).all()
        else:
            submissions = ExamSubmission.query.filter_by(exam_id=exam.id).order_by(
                ExamSubmission.total_score.desc()
            ).all()
            submissions = [
                submission for submission in submissions
                if teacher_can_access_submission(exam, submission, current_user)
            ]
        return render_template(
            "exam_result.html", exam=exam, submissions=submissions, single_view=False
        )
    else:
        abort(403)


def register_practice_runtime_routes(app) -> None:
    """Register dedicated practice runtime routes."""
    app.add_url_rule(
        "/practice/<int:exam_id>/take",
        endpoint="practice_take",
        view_func=practice_take,
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        "/practice/<int:exam_id>/result",
        endpoint="practice_result",
        view_func=practice_result,
        methods=["GET"],
    )
