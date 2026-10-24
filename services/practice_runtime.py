"""Shared classification and access checks for practice runtime routes.

This module deliberately has no Flask route registration.  The exam authoring
and grading handlers may use these predicates without importing the practice
route module (and therefore without creating a route import cycle).
"""

from __future__ import annotations

from database import db
from models import DiagnosticAssignment, Enrollment, ExamSubmission, MasterySnapshot, PracticeSession
from services.practice_blueprint import is_fixed
from services.personalization_evidence import is_finalized
from services.diagnostic_service import SCOPE_CODE


def is_practice_runtime_exam(exam) -> bool:
    """Return whether *exam* belongs to the student practice runtime.

    Initial diagnostics historically use the regular ``exam`` type, so the
    assessment purpose is intentionally part of this predicate as well as
    the explicit ``practice`` type.
    """
    return bool(
        exam
        and (
            getattr(exam, "exam_type", None) == "practice"
            or getattr(exam, "assessment_purpose", None) == "initial_diagnostic"
        )
    )


def student_can_access_exam(exam, student_id: int, *, require_live_source: bool = False) -> bool:
    """Check the existing student ownership/enrollment contract.

    Fixed papers are private to the student recorded in their frozen
    metadata.  Diagnostics remain class-wide, but still require an active
    enrollment in the exam's course.
    """
    if not exam or not getattr(exam, "course_id", None):
        return False
    if is_fixed(exam) and exam.get_adaptive_metadata().get("student_id") != student_id:
        return False
    enrolled = db.session.query(Enrollment.id).filter_by(
        student_id=student_id, course_id=exam.course_id, status="active"
    ).first() is not None
    if not enrolled:
        return False
    if require_live_source:
        # Result/history views deliberately keep frozen evidence readable, but
        # opening an active paper for a new attempt must use the same current
        # class-teacher policy as the generator.  Legacy papers without a
        # manifest are accepted by ``validate_exam_source`` for compatibility.
        from services.source_resolver import validate_exam_source
        if not validate_exam_source(exam, require_live=True)["valid"]:
            return False
    if getattr(exam, "assessment_purpose", None) == "initial_diagnostic":
        from services.diagnostic_service import diagnostic_assignment_is_eligible

        assignment = DiagnosticAssignment.query.filter_by(
            exam_id=exam.id, student_id=student_id
        ).first()
        if diagnostic_assignment_is_eligible(assignment, exam):
            return True
        # Preserve read access to the learner's own finalized historical
        # result. It cannot authorize a new attempt because the runtime's
        # one-submission guard immediately redirects back to that result.
        historical = ExamSubmission.query.filter_by(
            exam_id=exam.id, student_id=student_id
        ).order_by(ExamSubmission.submitted_at.desc(), ExamSubmission.id.desc()).first()
        return is_finalized(historical)
    return True


def teacher_can_access_submission(exam, submission, user) -> bool:
    """Allow a teacher to view/grade only submissions in their scope.

    Student-created fixed practice papers are the one deliberate exception to
    ``exam.created_by`` ownership: the course teacher can access the paper
    while its target student remains actively enrolled in that course.
    """
    if not exam or not submission or not user:
        return False
    if getattr(user, "role", None) == "admin" or exam.created_by == user.id:
        return True
    if (
        getattr(user, "role", None) != "teacher"
        or getattr(exam, "exam_type", None) != "practice"
        or not is_fixed(exam)
        or not getattr(exam, "course", None)
    ):
        return False
    metadata = exam.get_adaptive_metadata()
    if exam.course.teacher_id != user.id:
        return False
    if metadata.get("student_id") != submission.student_id:
        return False
    return db.session.query(Enrollment.id).filter_by(
        course_id=exam.course_id,
        student_id=submission.student_id,
        status="active",
    ).first() is not None


def practice_decision_is_ready(submission, exam, practice_session, student_id: int) -> bool:
    """Return whether the persisted learning loop may expose a decision.

    A score alone is deliberately insufficient.  The same finalized
    submission must have produced its mastery snapshot while the learner is
    still actively enrolled in the class owning this fixed paper.  Keeping
    this predicate outside HTTP routes prevents a result page from advertising
    Continue/End that its POST endpoints cannot safely honor.
    """
    if not (
        submission
        and exam
        and practice_session
        and is_fixed(exam)
        and practice_session.student_id == student_id
        and submission.student_id == student_id
        and submission.exam_id == exam.id
        and practice_session.course_id == exam.course_id
        and bool(getattr(getattr(exam, "course", None), "is_active", False))
        and practice_session.scope_code == SCOPE_CODE
        and practice_session.status == "awaiting_decision"
        and practice_session.last_exam_id == exam.id
        and practice_session.last_submission_id == submission.id
        and submission.status == "graded"
        and bool(submission.is_graded)
        and is_finalized(submission)
    ):
        return False
    if not db.session.query(Enrollment.id).filter_by(
        student_id=student_id, course_id=practice_session.course_id, status="active"
    ).first():
        return False
    return db.session.query(MasterySnapshot.id).filter_by(
        student_id=student_id,
        subject=practice_session.subject,
        submission_id=submission.id,
    ).first() is not None
