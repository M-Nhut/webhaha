"""Dashboard and classroom-access queries.

These queries deliberately cover enrollment and learning activity only.  The
retired classroom-operations data is not part of dashboard aggregation.
"""

from __future__ import annotations

from typing import Any

from flask_login import current_user
from sqlalchemy import or_

from models import Course, Enrollment, Exam, ExamSubmission, User


def get_accessible_student_ids() -> list[int]:
    """Return student IDs visible to the current account."""
    if current_user.role == "admin":
        return [user.id for user in User.query.filter_by(role="student").all()]
    return [current_user.id] if current_user.role == "student" else []


def students_for_teacher(teacher_id: int) -> list[User]:
    """Return active enrolled students in courses assigned to a teacher."""
    return User.query.join(Enrollment, Enrollment.student_id == User.id).join(
        Course, Course.id == Enrollment.course_id
    ).filter(
        Course.teacher_id == teacher_id,
        Enrollment.status == "active",
        User.role == "student",
    ).distinct().order_by(User.fullname).all()


def teacher_dashboard_data(teacher: User) -> dict[str, Any]:
    """Summarize the teacher's retained course and roster data."""
    courses = Course.query.filter_by(teacher_id=teacher.id).order_by(Course.course_name).all()
    return {
        "assigned_classes": len(courses),
        "student_count": len(students_for_teacher(teacher.id)),
    }


def student_dashboard_data(student: User) -> dict[str, Any]:
    """Summarize the student's enrolled courses and retained learning activity."""
    course_ids = [
        item.course_id
        for item in Enrollment.query.filter_by(student_id=student.id, status="active").all()
    ]
    courses = Course.query.filter(Course.id.in_(course_ids)).all() if course_ids else []
    retained = or_(Exam.exam_type == "practice", Exam.assessment_purpose == "initial_diagnostic")
    exams_taken = ExamSubmission.query.join(Exam).filter(
        ExamSubmission.student_id == student.id,
        ExamSubmission.is_graded.is_(True),
        retained,
    ).count()
    return {
        "courses": courses,
        "course_count": len(courses),
        "exams_taken": exams_taken,
    }
