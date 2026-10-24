"""Initial diagnostic authoring and cohort assignment routes.

An administrator chooses a bank, manually selects its questions, and reviews
the full paper before creating and assigning it to the active cohort
through :func:`services.diagnostic_service.assign_diagnostic_cohort`.
"""

from __future__ import annotations

import json
from collections import Counter

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from database import db
from models import (
    BankQuestion,
    Course,
    DiagnosticAssignment,
    Enrollment,
    ErrorObservation,
    Exam,
    ExamAnswer,
    ExamQuestion,
    ExamSubmission,
    LearningHistory,
    MasterySnapshot,
    PracticeSession,
    QuestionBank,
    SubmissionAnswer,
)
from services.access_control import can_use_bank, can_use_question
from services.diagnostic_service import assign_diagnostic_cohort
from services.personalization_evidence import refresh_question_snapshot, bank_question_content_hash, content_hash
from services.question_policy import bank_question_ready, canonical_type
from services.source_resolver import (
    attach_source_manifest,
    resolve_class_banks,
)
from services import practice_blueprint as blueprint


def _accessible_banks():
    query = QuestionBank.query.filter_by(is_active=True)
    banks = query.order_by(QuestionBank.subject, QuestionBank.name).all()
    # A diagnostic is a class-bound use of a bank, not an edit/import
    # operation.  Resolve against at least one class's current teacher so an
    # administrator's audit access or a former teacher's private bank cannot
    # leak into the selector as a usable source.
    courses = _accessible_courses()
    banks = [
        bank for bank in banks
        if any(resolve_class_banks(course, [bank.id])["valid"] for course in courses)
    ]
    return banks


def _accessible_courses():
    query = Course.query
    if current_user.role == "teacher":
        query = query.filter_by(teacher_id=current_user.id)
    return query.order_by(Course.course_name).all()


def _diagnostic_question_ready(question: BankQuestion) -> bool:
    """Return whether a bank item may enter a frozen diagnostic.

    Diagnostics are deliberately narrower than general bank readiness: only
    teacher-confirmed, active Chapter 8 lesson-i items with an auto-safe
    short-answer rule
    may enter a common form.  This prevents a diagnostic from creating a
    pending manual-grading submission after the traditional grading route is
    removed.
    """
    if getattr(question, "adaptive_excluded", False):
        return False
    status = getattr(question, "classification_status", None)
    node = getattr(question, "curriculum_node", None)
    if status != "teacher_confirmed" or not node or not node.is_active:
        return False
    if node.canonical_code not in blueprint.SKILLS:
        return False
    if not bank_question_ready(question):
        return False
    if blueprint.readiness_error(question):
        return False
    rule = blueprint.metadata(question).get("short_answer", {})
    return canonical_type(question.question_type) != "short_answer" or rule.get("mode") in ("numeric", "text")


def _copy_bank_questions(exam, selected):
    """Copy one frozen common item set from the approved bank."""
    pairs = []
    for index, bank_question in enumerate(selected):
        question = ExamQuestion(
            exam_id=exam.id,
            bank_question_id=bank_question.id,
            question_text=bank_question.question_text,
            context=bank_question.context,
            image_url=bank_question.image_url,
            question_type=canonical_type(bank_question.question_type),
            difficulty_level=bank_question.difficulty_level,
            explanation=bank_question.explanation,
            # A common diagnostic has a fixed scoring contract, independent
            # of any legacy per-bank point value.
            points=blueprint.POINTS[canonical_type(bank_question.question_type)],
            order_index=index,
        )
        db.session.add(question)
        db.session.flush()
        for option in bank_question.options:
            db.session.add(ExamAnswer(
                question_id=question.id,
                answer_text=option.option_text,
                is_correct=option.is_correct,
            ))
        db.session.flush()
        refresh_question_snapshot(question, bank_question)
        pairs.append((question, bank_question))
    return pairs


@login_required
def diagnostic_list():
    """List only initial diagnostics; summative exams have no route here."""
    if current_user.role == "student":
        # Students have one class-aware entry for diagnostic and adaptive
        # work; keep the historical URL as a safe redirect.
        return redirect(url_for("practice_home"))
    elif current_user.role in ("admin", "teacher"):
        query = Exam.query.filter_by(assessment_purpose="initial_diagnostic")
        if current_user.role == "teacher":
            query = query.filter_by(created_by=current_user.id)
        exams = query.order_by(Exam.created_at.desc()).all()
        submissions = {}
    else:
        abort(403)
    return render_template("diagnostic_list.html", exams=exams, submissions_map=submissions)


def _bank_class_sources(bank, selected=()):
    """Find current classes that may use every selected bank question."""
    result = []
    for course in _accessible_courses():
        source = resolve_class_banks(course, [bank.id])
        if source["valid"] and all(can_use_question(source["teacher"], q, bank=bank) for q in selected):
            result.append((course, source["teacher"]))
    return result


def _wizard_bank(value):
    try:
        bank_id = int(value)
        if not 0 < bank_id <= 2_147_483_647:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Hãy chọn ngân hàng câu hỏi.") from None
    bank = db.session.get(QuestionBank, bank_id)
    if not bank or not can_use_bank(current_user, bank):
        raise ValueError("Ngân hàng không còn hoạt động hoặc không còn quyền sử dụng.")
    sources = _bank_class_sources(bank)
    if not sources:
        raise ValueError("Ngân hàng chưa có lớp đang hoạt động được phép sử dụng. Hãy chọn ngân hàng khác.")
    return bank, sources


def _wizard_selected(bank):
    """Read the exact ordered IDs, bounded to the existing 22-item contract."""
    values = request.form.getlist("question_ids")
    if len(values) != blueprint.TOTAL:
        raise ValueError(f"Hãy chọn đủ {blueprint.TOTAL} câu trước khi kiểm tra đề.")
    try:
        ids = [int(value) for value in values]
    except (TypeError, ValueError):
        raise ValueError("Danh sách câu hỏi đã chọn không hợp lệ.") from None
    if len(set(ids)) != len(ids) or any(not 0 < value <= 2_147_483_647 for value in ids):
        raise ValueError("Danh sách câu hỏi có mã không hợp lệ hoặc bị trùng.")
    from sqlalchemy.orm import joinedload, selectinload
    rows = BankQuestion.query.filter(BankQuestion.bank_id == bank.id, BankQuestion.id.in_(ids)).options(
        selectinload(BankQuestion.options), joinedload(BankQuestion.curriculum_node),
        joinedload(BankQuestion.creator), joinedload(BankQuestion.private_owner),
    ).all()
    by_id = {q.id: q for q in rows}
    if any(value not in by_id for value in ids):
        raise ValueError("Có câu đã bị xóa hoặc không thuộc ngân hàng đã chọn. Hãy kiểm tra lại bộ câu.")
    selected = [by_id[value] for value in ids]
    invalid = [q.id for q in selected if not _diagnostic_question_ready(q)]
    if invalid:
        raise ValueError("Câu chưa đủ điều kiện tạo đề đầu vào: " + ", ".join(f"#{value}" for value in invalid))
    types = Counter(canonical_type(q.question_type) for q in selected)
    if types != Counter(blueprint.TYPE_QUOTAS):
        raise ValueError("Cấu trúc hiện tại cần 12 câu trắc nghiệm, 4 câu Đúng/Sai và 6 câu trả lời ngắn.")
    skills = Counter(q.curriculum_node.canonical_code for q in selected)
    if set(skills) != set(blueprint.SKILLS):
        raise ValueError("Đề đầu vào cần bao phủ đủ 8 dạng kiến thức. Hãy bổ sung dạng còn thiếu trong bộ câu đã chọn.")
    levels = Counter(q.difficulty_level for q in selected)
    digest = content_hash({"bank_id": bank.id, "questions": [
        {"id": q.id, "content": bank_question_content_hash(q)} for q in selected
    ]})
    return selected, skills, levels, digest


@login_required
def diagnostic_question_choices():
    """Step 2: one page of prompts, with answer data loaded on demand."""
    if current_user.role != "admin":
        abort(403)
    try:
        bank, sources = _wizard_bank(request.args.get("question_bank_id"))
        from services.bank_detail_page import (
            metadata_for_bank, hydrate_readiness, question_page, preview_payload, catalog_for_metadata,
        )
        rows = [q for q in metadata_for_bank(bank) if any(
            can_use_question(teacher, q, bank=bank) for _, teacher in sources)]
        hydrate_readiness(rows)
        catalog = catalog_for_metadata(rows, research=True)
        filters = request.args.to_dict()
        filters["per_page"] = 25
        if filters.get("node_id") and filters["node_id"] not in {str(node["id"]) for node in catalog}:
            raise ValueError("Dạng kiến thức đã chọn không hợp lệ.")
        records, pagination = question_page(bank, rows, filters, catalog, research=True)
        questions = preview_payload(records, rows, bank, current_user, research=True)
        by_id = {q.id: q for q in rows}
        nodes = {str(node["id"]): node for node in catalog}
        for item in questions:
            question = by_id[item["id"]]
            node = nodes.get(str(item["curriculum_node_id"]), {})
            blocked_reason = ""
            if not _diagnostic_question_ready(question):
                if question.adaptive_excluded:
                    blocked_reason = "Câu đang được tạm loại khỏi bộ câu sử dụng."
                elif question.classification_status != "teacher_confirmed":
                    blocked_reason = "Phân loại của câu chưa được giáo viên xác nhận."
                else:
                    blocked_reason = blueprint.readiness_error(question) or "Câu chưa có đủ nội dung và đáp án hợp lệ."
            item.update(
                blocked_reason=blocked_reason,
                skill=node.get("canonical_code", "") or (question.curriculum_node.canonical_code if question.curriculum_node else ""),
                skill_label=node.get("category_name", "Chưa phân loại"),
                selectable=_diagnostic_question_ready(question),
                detail_url=url_for("question_bank_question_detail_json", bank_id=bank.id, question_id=item["id"]),
            )
        response = jsonify(success=True, questions=questions, pagination=pagination, skills=catalog)
        response.headers["Cache-Control"] = "private, no-store"
        return response
    except ValueError as exc:
        return jsonify(success=False, message=str(exc)), 400


@login_required
def review_diagnostic():
    """Step 3 is read-only: no exam/assignment is saved before confirmation."""
    if current_user.role != "admin":
        abort(403)
    try:
        bank, _ = _wizard_bank(request.form.get("question_bank_id"))
        selected, skills, levels, digest = _wizard_selected(bank)
        sources = _bank_class_sources(bank, selected)
        if not sources:
            raise ValueError("Bộ câu đã chọn chưa có lớp nào được phép sử dụng toàn bộ. Hãy kiểm tra các câu riêng tư.")
        questions = [{
            "id": q.id, "question_text": q.question_text, "context": q.context or "",
            "image_url": q.image_url or "", "question_type": canonical_type(q.question_type),
            "difficulty_level": q.difficulty_level, "skill": q.curriculum_node.canonical_code,
            "skill_label": q.curriculum_node.category_name,
            "points": blueprint.POINTS[canonical_type(q.question_type)], "explanation": q.explanation or "",
            "options": [{"text": answer.option_text, "correct": answer.is_correct} for answer in q.options],
        } for q in selected]
        from services.assessment_bank import formula_assets
        response = jsonify(success=True, questions=questions, formulas=formula_assets(questions),
                           bank={"id": bank.id, "name": bank.name},
                           courses=[{"id": course.id, "name": course.course_name} for course, _ in sources],
                           skill_counts=dict(skills), level_counts=dict(levels), review_digest=digest)
        response.headers["Cache-Control"] = "private, no-store"
        return response
    except ValueError as exc:
        return jsonify(success=False, message=str(exc)), 400


@login_required
def create_diagnostic():
    """Create the reviewed manual paper only on the final admin confirmation."""
    if current_user.role != "admin":
        abort(403)
    if request.method == "GET":
        return render_template("diagnostic_form.html", banks=_accessible_banks(), blueprint=blueprint)
    try:
        bank, _ = _wizard_bank(request.form.get("question_bank_id"))
        selected, skills, levels, digest = _wizard_selected(bank)
        if request.form.get("review_digest") != digest:
            raise ValueError("Nội dung câu hỏi đã thay đổi sau khi xem lại. Hãy trở về bước chọn câu và kiểm tra đề lần nữa.")
        course_id = request.form.get("course_id", type=int)
        course = next((course for course, _ in _bank_class_sources(bank, selected) if course.id == course_id), None)
        if not course:
            raise ValueError("Hãy chọn lớp đang hoạt động được phép sử dụng bộ câu này.")
        if request.form.get("confirmed") != "yes":
            raise ValueError("Hãy xác nhận đã kiểm tra nội dung và đáp án trước khi tạo đề.")
        title = request.form.get("title", "").strip() or f"Đánh giá đầu vào · {course.course_name}"
        if len(title) > 200:
            raise ValueError("Tên đề tối đa 200 ký tự.")
        metadata = {"diagnostic": {
            "version": blueprint.VERSION, "personalization": "disabled_common_paper", "bank_id": bank.id,
            "selection_policy": "manual", "recovery": {},
            "level_targets": {level: levels[level] for level in blueprint.LEVELS},
            "skill_targets": {skill: skills[skill] for skill in blueprint.SKILLS},
            "type_targets": blueprint.TYPE_QUOTAS,
            "scoring": {"points": blueprint.POINTS, "true_false": list(blueprint.TF_POINTS)},
        }}
        exam = Exam(title=title, course_id=course.id, created_by=current_user.id,
                    duration_minutes=blueprint.DURATION_MINUTES, is_active=True,
                    shuffle_questions=False, shuffle_answers=False, question_bank_id=bank.id,
                    exam_type="exam", exam_category="Đánh giá đầu vào", total_questions=blueprint.TOTAL,
                    difficulty_config=json.dumps(metadata["diagnostic"]["level_targets"], ensure_ascii=False),
                    question_type_config=json.dumps(blueprint.TYPE_QUOTAS, ensure_ascii=False),
                    adaptive_metadata=json.dumps(metadata, ensure_ascii=False), assessment_purpose="initial_diagnostic")
        db.session.add(exam)
        db.session.flush()
        pairs = _copy_bank_questions(exam, selected)
        attach_source_manifest(exam, course, pairs, bank_ids=[bank.id])
        assign_diagnostic_cohort(exam, assigned_by=current_user.id)
        db.session.commit()
        flash("Đã tạo và giao đề đánh giá đầu vào từ các câu bạn đã chọn.", "success")
        return jsonify(success=True, redirect_url=url_for("diagnostic_list"), exam_id=exam.id)
    except ValueError as exc:
        db.session.rollback()
        return jsonify(success=False, message=str(exc)), 400
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Unable to save manual initial diagnostic")
        return jsonify(success=False, message="Không thể lưu đề lúc này. Thông tin đã chọn được giữ; hãy thử lại."), 500


@login_required
def delete_diagnostic(exam_id: int):
    """Delete an initial diagnostic exam and clean up all associated records safely."""
    if current_user.role not in ("admin", "teacher"):
        abort(403)

    exam = db.session.get(Exam, exam_id) or abort(404)
    if exam.assessment_purpose != "initial_diagnostic":
        abort(400)

    if current_user.role == "teacher" and (
        exam.created_by != current_user.id and exam.course.teacher_id != current_user.id
    ):
        abort(403)

    try:
        sub_ids = [s.id for s in exam.submissions]

        if sub_ids:
            # Clean up student learning observations, evidence facts, and snapshots
            ErrorObservation.query.filter(ErrorObservation.submission_id.in_(sub_ids)).delete(synchronize_session=False)
            LearningHistory.query.filter(LearningHistory.submission_id.in_(sub_ids)).delete(synchronize_session=False)
            MasterySnapshot.query.filter(MasterySnapshot.submission_id.in_(sub_ids)).delete(synchronize_session=False)
            PracticeSession.query.filter(PracticeSession.last_submission_id.in_(sub_ids)).update(
                {'last_submission_id': None}, synchronize_session=False
            )

        PracticeSession.query.filter_by(last_exam_id=exam.id).update(
            {'last_exam_id': None}, synchronize_session=False
        )
        DiagnosticAssignment.query.filter_by(exam_id=exam.id).delete(synchronize_session=False)

        # SQLAlchemy cascade="all, delete-orphan" on Exam.questions and Exam.submissions
        # deletes ExamSubmission, SubmissionAnswer, ExamQuestion, and ExamAnswer cleanly.
        db.session.delete(exam)
        db.session.commit()
        flash("Đã xóa bài đánh giá đầu vào thành công.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Lỗi khi xóa bài đánh giá đầu vào: {str(e)}", "danger")

    return redirect(url_for("diagnostic_list"))


def register_diagnostic_routes(app) -> None:
    app.add_url_rule("/api/diagnostics/question-choices", endpoint="diagnostic_question_choices", view_func=diagnostic_question_choices)
    app.add_url_rule("/api/diagnostics/review", endpoint="review_diagnostic", view_func=review_diagnostic, methods=["POST"])
    app.add_url_rule("/diagnostics", endpoint="diagnostic_list", view_func=diagnostic_list)
    app.add_url_rule(
        "/diagnostics/new", endpoint="create_diagnostic", view_func=create_diagnostic,
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        "/diagnostics/<int:exam_id>/delete",
        endpoint="delete_diagnostic",
        view_func=delete_diagnostic,
        methods=["POST"],
    )
