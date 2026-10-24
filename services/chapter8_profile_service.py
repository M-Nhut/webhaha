"""Build privacy-minimized, deterministic Chapter 8 learner profiles for AI analysis."""

import hashlib
import os
import statistics
from collections import defaultdict

from models import BankQuestion, CurriculumNode, ExamSubmission, LearningHistory


CHAPTER_CODE = "8"
TOPIC_NAME = "Thống kê và xác suất"
COGNITIVE_LEVELS = {"nhan_biet", "thong_hieu", "van_dung", "van_dung_cao"}
LESSON_TYPE_LIMITS = {"i": 8}


def _clean_code(value):
    value = str(value or "").strip()
    if value.lower() == "i":
        return "i"
    digits = "".join(char for char in value if char.isdigit())
    return str(int(digits)) if digits else value


def _taxonomy(bank_question):
    node = bank_question.curriculum_node if bank_question else None
    chapter = _clean_code(bank_question.chapter if bank_question else None)
    chapter = chapter or _clean_code(node.chapter_code if node else None)
    if chapter != CHAPTER_CODE:
        return None
    lesson = _clean_code((bank_question.section if bank_question else None) or (node.lesson_code if node else None))
    exercise_type = _clean_code((bank_question.question_category if bank_question else None) or (node.category_code if node else None))
    if lesson not in LESSON_TYPE_LIMITS or not exercise_type.isdigit():
        return None
    if not 1 <= int(exercise_type) <= LESSON_TYPE_LIMITS[lesson]:
        return None
    return {
        "lesson": lesson,
        "exercise_type": exercise_type,
        "exercise_name": (node.category_name if node else None) or f"Dạng {exercise_type}",
        "lesson_name": (node.lesson_name if node else None) or f"Bài {lesson}",
    }


def _trend(values):
    if len(values) < 4:
        return "insufficient_data"
    midpoint = len(values) // 2
    older = sum(values[:midpoint]) / midpoint
    recent = sum(values[midpoint:]) / (len(values) - midpoint)
    if recent - older >= .10:
        return "improving"
    if older - recent >= .10:
        return "declining"
    return "stable"


def _pseudonym(student_id):
    salt = os.environ.get("AI_ANALYSIS_PSEUDONYM_SALT", "educenter-chapter6")
    return hashlib.sha256(f"{salt}:{student_id}".encode("utf-8")).hexdigest()[:16]


def _catalog():
    nodes = CurriculumNode.query.filter_by(chapter_code=CHAPTER_CODE, is_active=True).order_by(
        CurriculumNode.lesson_code, CurriculumNode.category_code
    ).all()
    rows, seen = [], set()
    for node in nodes:
        lesson, exercise_type = _clean_code(node.lesson_code), _clean_code(node.category_code)
        key = (lesson, exercise_type)
        if lesson not in LESSON_TYPE_LIMITS or key in seen:
            continue
        if not exercise_type.isdigit() or int(exercise_type) > LESSON_TYPE_LIMITS[lesson]:
            continue
        seen.add(key)
        rows.append({
            "lesson": lesson, "lesson_name": node.lesson_name,
            "exercise_type": exercise_type, "exercise_name": node.category_name,
        })
    return rows


def build_chapter8_profile(student_id, subject="Toán", submission_limit=5, answer_limit=50, course_id=None):
    """Return a stable JSON-ready profile using only the latest Chapter 8 attempts."""
    from services.personalization_evidence import is_finalized
    submissions = [
        submission for submission in ExamSubmission.query.filter_by(student_id=student_id)
        .order_by(ExamSubmission.submitted_at.desc(), ExamSubmission.id.desc()).all()
        if submission.submitted_at and submission.exam and submission.exam.course
        and submission.exam.course.subject == subject and is_finalized(submission)
        and (course_id is None or submission.exam.course_id == course_id)
    ][:max(1, int(submission_limit))]
    submission_ids = [submission.id for submission in submissions]
    history = []
    if submission_ids:
        history = LearningHistory.query.filter(LearningHistory.submission_id.in_(submission_ids)).order_by(
            LearningHistory.occurred_at.desc(), LearningHistory.id.desc()
        ).limit(max(1, int(answer_limit))).all()
        history = [row for row in history if row.answer_status not in ("unanswered", "pending_review")]
    bank_ids = {row.bank_question_id for row in history if row.bank_question_id}
    bank_map = {question.id: question for question in BankQuestion.query.filter(BankQuestion.id.in_(bank_ids)).all()} if bank_ids else {}

    groups = defaultdict(list)
    valid_rows = []
    for row in reversed(history):
        taxonomy = _taxonomy(bank_map.get(row.bank_question_id))
        if not taxonomy or row.cognitive_level not in COGNITIVE_LEVELS:
            continue
        item = {
            **taxonomy, "cognitive_level": row.cognitive_level,
            "normalized_score": max(0., min(1., float(row.normalized_score or 0))),
            "is_correct": bool(row.is_correct), "weight": max(.0001, float(row.weight or 0)),
            "time_spent_seconds": max(0, int(row.time_spent_seconds or 0)),
            "occurred_at": row.occurred_at,
        }
        groups[(taxonomy["lesson"], taxonomy["exercise_type"], row.cognitive_level)].append(item)
        valid_rows.append(item)

    skill_results = []
    for (lesson, exercise_type, cognitive), items in sorted(groups.items()):
        total_weight = sum(item["weight"] for item in items)
        mastery = sum(item["weight"] * item["normalized_score"] for item in items) / total_weight
        times = [item["time_spent_seconds"] for item in items if item["time_spent_seconds"] > 0]
        skill_results.append({
            "lesson": lesson, "lesson_name": items[0]["lesson_name"],
            "exercise_type": exercise_type, "exercise_name": items[0]["exercise_name"],
            "cognitive_level": cognitive, "attempts": len(items),
            "correct_count": sum(item["is_correct"] for item in items),
            "accuracy": round(sum(item["is_correct"] for item in items) / len(items), 4),
            "normalized_score": round(sum(item["normalized_score"] for item in items) / len(items), 4),
            "mastery": round(mastery, 4),
            "median_time_seconds": round(statistics.median(times), 1) if times else 0,
            "recent_trend": _trend([item["normalized_score"] for item in items]),
        })

    total_weight = sum(item["weight"] for item in valid_rows)
    overall = sum(item["weight"] * item["normalized_score"] for item in valid_rows) / total_weight if total_weight else .5
    return {
        "schema_version": "chapter6-profile-v1",
        "student_ref": _pseudonym(student_id),
        "subject": subject,
        "chapter": CHAPTER_CODE,
        "topic": TOPIC_NAME,
        "recent_window": {
            "submission_count": len(submissions), "answer_count": len(valid_rows),
            "submission_limit": int(submission_limit), "answer_limit": int(answer_limit),
        },
        "overall_mastery": round(overall, 4),
        "skill_results": skill_results,
        "available_taxonomy": _catalog(),
    }


build_chapter6_profile = build_chapter8_profile
