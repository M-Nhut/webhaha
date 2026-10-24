"""Common-item diagnostic assignment helpers."""

from __future__ import annotations

import json
import datetime as dt
from collections import Counter

from database import db
from models import (
    Course, DiagnosticAssignment, Enrollment, Exam, ExamSubmission,
    LearningHistory, QuestionBank,
)
from services.personalization_evidence import content_hash, is_finalized, question_snapshot


SCOPE_CODE = "9C8-i"
DIAGNOSTIC_SELECTION_POLICY = "same_level_random_skill_transfer_v1"


def _exam_has_lesson_i_scope(exam, *, require_full_paper=False):
    """Validate the frozen Grade 9 / Chapter 8 / lesson-i boundary."""
    from services import practice_blueprint as blueprint

    questions = list(exam.questions) if exam else []
    if not questions or any(question.curriculum_code not in blueprint.SKILLS for question in questions):
        return False
    if not require_full_paper:
        return True
    type_counts = Counter(question.question_type for question in questions)
    if len(questions) != blueprint.TOTAL or type_counts != Counter(blueprint.TYPE_QUOTAS):
        return False
    diagnostic = exam.get_adaptive_metadata().get("diagnostic", {})
    if not isinstance(diagnostic, dict):
        return False
    if diagnostic.get("selection_policy") != DIAGNOSTIC_SELECTION_POLICY:
        # Historical papers still require all eight skills. A missing skill
        # is accepted only for new papers with matching frozen recovery data.
        return {question.curriculum_code for question in questions} == set(blueprint.SKILLS)
    return _transferred_coverage_matches(exam, diagnostic)


def _transferred_coverage_matches(exam, diagnostic):
    """Check recorded transfers against the frozen common paper, not live stock."""
    from services import aptga, practice_blueprint as blueprint

    recovery = diagnostic.get("recovery")
    if not isinstance(recovery, dict):
        return False
    actual = Counter(question.curriculum_code for question in exam.questions)
    levels = Counter(question.difficulty_level for question in exam.questions)
    expected_levels = aptga.apportion(blueprint.TOTAL, aptga.BASE)
    expected_skills = diagnostic.get("skill_targets")
    if not isinstance(expected_skills, dict) or set(expected_skills) != set(blueprint.SKILLS):
        return False
    if any(type(n) is not int or not 1 <= n <= 5 for n in expected_skills.values()):
        return False
    if sum(expected_skills.values()) != blueprint.TOTAL:
        return False
    if (
        levels != Counter(expected_levels)
        or diagnostic.get("level_targets") != expected_levels
        or recovery.get("effective_level_targets") != expected_levels
        or recovery.get("effective_skill_targets") != {s: actual[s] for s in blueprint.SKILLS}
        or recovery.get("unavailable_skills") != [s for s in blueprint.SKILLS if not actual[s]]
        or recovery.get("covered_skill_count") != len(actual)
        or recovery.get("coverage_policy") != "cover_available_skills"
        or recovery.get("replacement_policy") != "random_other_skill_same_level"
        or recovery.get("level_targets_preserved") is not True
        or max(actual.values()) > 5
    ):
        return False
    transfers = recovery.get("skill_transfers")
    if not isinstance(transfers, list):
        return False
    frozen = {q.bank_question_id: q for q in exam.questions}
    sources, targets, used = Counter(), Counter(), set()
    for transfer in transfers:
        if not isinstance(transfer, dict):
            return False
        source, target = transfer.get("source_skill"), transfer.get("target_skill")
        question_id = transfer.get("question_id")
        if type(question_id) is not int or question_id in used:
            return False
        question = frozen.get(question_id)
        if (
            source not in blueprint.SKILLS or target not in blueprint.SKILLS or source == target
            or transfer.get("count") != 1 or not question
            or question.curriculum_code != target
            or question.difficulty_level != transfer.get("level")
            or question.question_type != transfer.get("question_type")
        ):
            return False
        used.add(question_id)
        sources[source] += 1
        targets[target] += 1
    return (
        sources == Counter({s: max(0, expected_skills[s] - actual[s]) for s in blueprint.SKILLS})
        and targets == Counter({s: max(0, actual[s] - expected_skills[s]) for s in blueprint.SKILLS})
        and recovery.get("quota_changes") == len(transfers)
    )


def _assignment_matches_frozen_exam(assignment, exam):
    return bool(
        assignment
        and exam
        and assignment.exam_id == exam.id
        and assignment.common_item_hash == common_item_hash(exam)
    )


def diagnostic_assignment_is_eligible(assignment, exam):
    """Return whether an assigned common paper may start the unified flow."""
    return bool(
        exam
        and exam.assessment_purpose == "initial_diagnostic"
        and _assignment_matches_frozen_exam(assignment, exam)
        and _exam_has_lesson_i_scope(exam, require_full_paper=True)
    )


def common_diagnostic_selection(questions, *, rng=None):
    """Freeze one common paper; replace missing skills at the exact same level.

    Try the original skill quotas first, then randomly choose feasible other
    skills without changing type/level totals or duplicating content. No
    learner history is read and all students receive the same frozen result.
    """
    from services import aptga
    from services import practice_blueprint as blueprint
    from services.personalization_evidence import bank_question_content_hash
    from random import SystemRandom
    from services.practice_selector import skill_targets
    from services.practice_recovery import select_resilient

    # The common form uses the baseline directly.  ``allocate`` additionally
    # repairs practice floors/ceilings for adaptive sessions; that would turn
    # the requested 9/7/4/2 apportionment into a different common mix.
    level_targets = aptga.apportion(blueprint.TOTAL, aptga.BASE)
    knowledge_targets = skill_targets({})
    ranked = []
    for question in questions:
        node = question.curriculum_node
        skill = node.canonical_code if node else None
        ranked.append({
            "question": question,
            "skill": skill,
            "score": 0.,
            "components": {"teacher": max(0., min(1., float(question.adaptive_priority or 0) / 100))},
            "fingerprint": question.content_hash or bank_question_content_hash(question),
        })
    ranked.sort(key=lambda item: (-item["components"]["teacher"], item["question"].id))
    selected, shortages, status, recovery = select_resilient(
        ranked, level_targets, knowledge_targets, rng=rng if rng is not None else SystemRandom())
    warnings = []
    if selected and recovery["quota_changes"]:
        warnings.append(
            f"Đã tự động thay {recovery['quota_changes']} câu bằng dạng kiến thức khác cùng mức độ khó."
        )
    if selected and recovery["unavailable_skills"]:
        missing = ", ".join(s.rsplit("-", 1)[-1] for s in recovery["unavailable_skills"])
        warnings.append(
            f"Ngân hàng chưa có câu hợp lệ cho dạng {missing}; đề bao phủ {recovery['covered_skill_count']}/8 dạng."
        )
    return {
        "questions": [item["question"] for item in selected],
        "status": status,
        "shortages": shortages,
        "level_targets": level_targets,
        "skill_targets": knowledge_targets,
        "warnings": warnings,
        "selection_policy": DIAGNOSTIC_SELECTION_POLICY,
        "recovery": recovery,
    }


def common_item_hash(exam):
    """Hash the ordered frozen exam items, independent of student answers."""
    return content_hash({
        "exam_id": exam.id,
        "items": [question_snapshot(question) for question in exam.questions],
    })


def diagnostic_coverage(exam):
    """Summarize the frozen common form for teacher coverage review."""
    skills = Counter(question.curriculum_code or "unknown" for question in exam.questions)
    levels = Counter(question.difficulty_level or "unknown" for question in exam.questions)
    types = Counter(question.question_type or "unknown" for question in exam.questions)
    return {
        "item_count": len(exam.questions),
        "skill_counts": dict(sorted(skills.items())),
        "difficulty_counts": dict(sorted(levels.items())),
        "type_counts": dict(sorted(types.items())),
        "unknown_skill_count": skills.get("unknown", 0),
    }


def assign_diagnostic_cohort(exam, assigned_by=None):
    """Assign the same already-frozen item set to every active enrollee."""
    if not exam or exam.assessment_purpose != "initial_diagnostic" or not exam.course_id:
        return []
    item_hash = common_item_hash(exam)
    exam.diagnostic_coverage = json.dumps(diagnostic_coverage(exam), ensure_ascii=False, sort_keys=True)
    assigned = []
    enrollments = Enrollment.query.filter_by(course_id=exam.course_id, status="active").all()
    for enrollment in enrollments:
        row = DiagnosticAssignment.query.filter_by(
            exam_id=exam.id, student_id=enrollment.student_id
        ).first()
        if not row:
            row = DiagnosticAssignment(
                exam_id=exam.id, student_id=enrollment.student_id,
                assigned_by=assigned_by, common_item_hash=item_hash,
            )
            db.session.add(row)
        else:
            # Once assigned, the common form is immutable.  Silently replacing
            # this hash would make cohort results no longer comparable.
            if row.common_item_hash != item_hash:
                raise ValueError("Bài đánh giá đầu vào đã được giao; không thể thay đổi bộ câu hỏi chung.")
            if assigned_by:
                row.assigned_by = assigned_by
        assigned.append(row)
    db.session.flush()
    return assigned


def assign_existing_diagnostics_for_enrollment(enrollment, assigned_by=None):
    """Give a late enrollee each currently eligible frozen class diagnostic.

    This is called by the enrollment write path.  It does not alter papers or
    existing assignments; it merely applies the same frozen hash contract used
    for the original cohort.
    """
    if not enrollment or enrollment.status != "active":
        return []
    now = dt.datetime.now()
    exams = Exam.query.filter(
        Exam.course_id == enrollment.course_id,
        Exam.assessment_purpose == "initial_diagnostic",
        Exam.is_active.is_(True),
    ).order_by(Exam.created_at.desc(), Exam.id.desc()).all()
    assigned = []
    for exam in exams:
        if (exam.start_time and exam.start_time > now) or (exam.end_time and exam.end_time < now):
            continue
        item_hash = common_item_hash(exam)
        row = DiagnosticAssignment.query.filter_by(
            exam_id=exam.id, student_id=enrollment.student_id
        ).first()
        if not row:
            row = DiagnosticAssignment(
                exam_id=exam.id,
                student_id=enrollment.student_id,
                assigned_by=assigned_by,
                common_item_hash=item_hash,
            )
            db.session.add(row)
        elif row.common_item_hash != item_hash:
            raise ValueError("Bài đánh giá đầu vào đã giao không còn khớp bộ câu hỏi đã đóng băng.")
        assigned.append(row)
    db.session.flush()
    return assigned


def complete_diagnostic_assignment(submission):
    """Mark initialization complete after the diagnostic is fully graded.

    Completion is independent of how many cells gained evidence: an entirely
    blank but finalized diagnostic still initializes an honest unknown profile
    and must not send the learner through an endless diagnostic loop.
    """
    exam = submission.exam if submission else None
    if not exam or exam.assessment_purpose != "initial_diagnostic" or not is_finalized(submission):
        return None
    row = DiagnosticAssignment.query.filter_by(
        exam_id=exam.id, student_id=submission.student_id
    ).first()
    if not row:
        return None
    if row.common_item_hash != common_item_hash(exam):
        raise ValueError("Bộ câu hỏi đầu vào đã thay đổi sau khi giao; không thể xác nhận hồ sơ so sánh.")
    row.status = "completed"
    row.completed_at = submission.finalized_at or submission.submitted_at
    db.session.flush()
    return row


def learner_profile_state(student_id, subject, course_id=None):
    """Return initialized/required state without equating unknown cells to weak.

    Valid legacy evidence and persisted snapshots are accepted so an upgraded
    installation never forces established learners through a needless new test.
    """
    scope_codes = {f"9C8-i-{index}" for index in range(1, 9)}
    history = LearningHistory.query.filter(
        LearningHistory.student_id == student_id,
        LearningHistory.subject == subject,
        LearningHistory.answer_status.in_(("answered", "graded")),
        LearningHistory.curriculum_code.in_(scope_codes),
    ).all()
    submission_ids = {row.submission_id for row in history}
    submissions = {
        row.id: row for row in ExamSubmission.query.filter(
            ExamSubmission.id.in_(submission_ids)
        ).all()
    } if submission_ids else {}
    has_history = any(is_finalized(submissions.get(row.submission_id)) for row in history)
    if has_history:
        return {"initialized": True, "status": "initialized", "source": "existing_evidence", "exam": None}

    assignments_query = DiagnosticAssignment.query.join(
        Exam, Exam.id == DiagnosticAssignment.exam_id
    ).join(Course, Course.id == Exam.course_id).filter(
        DiagnosticAssignment.student_id == student_id,
        Course.subject == subject,
        Exam.assessment_purpose == "initial_diagnostic",
    )
    # Evidence may initialize the shared subject/scope profile, but a pending
    # entry paper must always belong to the class the learner selected.
    if course_id is not None:
        assignments_query = assignments_query.filter(Exam.course_id == course_id)
    assignments = assignments_query.order_by(
        DiagnosticAssignment.assigned_at.desc(), DiagnosticAssignment.id.desc()
    ).all()
    assignments = [assignment for assignment in assignments if (
        (exam := db.session.get(Exam, assignment.exam_id))
        and _assignment_matches_frozen_exam(assignment, exam)
        and _exam_has_lesson_i_scope(exam)
    )]
    for assignment in assignments:
        submission = ExamSubmission.query.filter_by(
            exam_id=assignment.exam_id, student_id=student_id
        ).order_by(ExamSubmission.submitted_at.desc(), ExamSubmission.id.desc()).first()
        # A status flag alone is not learner evidence. Initialization needs a
        # finalized submission, including an honestly blank diagnostic.
        if submission and is_finalized(submission):
            return {"initialized": True, "status": "initialized", "source": "initial_diagnostic", "exam": assignment.exam_id}
    pending = next((row for row in assignments if (
        row.status == "assigned"
        and (exam := db.session.get(Exam, row.exam_id))
        and exam.status_label == "open"
        and _exam_has_lesson_i_scope(exam, require_full_paper=True)
    )), None)
    return {
        "initialized": False,
        "status": "diagnostic_required" if pending else "diagnostic_unavailable",
        "source": None,
        "exam": pending.exam_id if pending else None,
    }


def class_diagnostic_source(student_id, course):
    """Resolve the sole bank authorized for practice in one selected class.

    The binding comes from the class diagnostic, never from a client bank id.
    The newest assigned diagnostic fails closed instead of falling back to an
    older assessment or another teacher's bank.
    """
    from services.curriculum_data import CHAPTER8_GRADE

    if not course:
        return {"status": "assessment_missing", "exam": None, "bank": None,
                "message": "Không tìm thấy lớp học đã chọn."}
    enrollment = Enrollment.query.filter_by(
        student_id=student_id, course_id=course.id, status="active"
    ).first()
    if not enrollment or not course.is_active:
        return {"status": "class_unavailable", "exam": None, "bank": None,
                "message": "Bạn không còn ghi danh trong lớp đang hoạt động này."}
    assignment = DiagnosticAssignment.query.join(
        Exam, Exam.id == DiagnosticAssignment.exam_id
    ).filter(
        DiagnosticAssignment.student_id == student_id,
        Exam.course_id == course.id,
        Exam.assessment_purpose == "initial_diagnostic",
    ).order_by(DiagnosticAssignment.assigned_at.desc(), DiagnosticAssignment.id.desc()).first()
    if not assignment:
        return {"status": "assessment_missing", "exam": None, "bank": None,
                "message": "Lớp này chưa giao đánh giá đầu vào cho bạn. Hãy liên hệ giáo viên phụ trách."}
    exam = db.session.get(Exam, assignment.exam_id)
    if not _assignment_matches_frozen_exam(assignment, exam) or not _exam_has_lesson_i_scope(
        exam, require_full_paper=True
    ):
        return {"status": "assessment_invalid", "exam": exam, "bank": None,
                "message": "Đánh giá đầu vào của lớp chưa đúng phạm vi 8 dạng bài kết hợp 25 + 26. Giáo viên cần kiểm tra lại."}
    # A malformed/new manifest is not silently downgraded to the legacy
    # diagnostic path.  Historical no-manifest rows are handled explicitly by
    # ``validate_exam_source`` and remain compatible when their live source is
    # still authorized.
    from services.source_resolver import validate_exam_source
    source_validation = validate_exam_source(exam, require_live=True)
    if not source_validation["valid"]:
        source_reason = source_validation.get("reason")
        status = (
            "bank_unavailable"
            if source_reason in {
                "bank_not_authorized", "question_not_authorized",
                "private_owner_mismatch", "source_scope_mismatch",
                "class_unavailable", "teacher_or_bank_missing",
            }
            else "assessment_invalid"
        )
        return {"status": status, "exam": exam, "bank": None,
                "message": "Đánh giá đầu vào không còn có nguồn câu hỏi hợp lệ; giáo viên cần kiểm tra lại manifest và ngân hàng lớp."}
    bank = db.session.get(QuestionBank, exam.question_bank_id) if exam.question_bank_id else None
    grade = str(getattr(bank, "grade", "") or "").strip()
    from services.source_resolver import resolve_class_banks
    source = resolve_class_banks(course, [bank.id] if bank else [])
    if (
        not bank
        or not bank.is_active
        or bank.subject != course.subject
        or grade not in (CHAPTER8_GRADE, f"Lớp {CHAPTER8_GRADE}")
        or not source["valid"]
    ):
        return {"status": "bank_unavailable", "exam": exam, "bank": None,
                "message": "Ngân hàng nguồn của lớp không còn hợp lệ. Giáo viên hiện tại cần chọn ngân hàng lớp 9 được phép sử dụng (dùng chung hoặc riêng của mình)."}
    return {"status": "ready", "exam": exam, "bank": bank, "message": None}
