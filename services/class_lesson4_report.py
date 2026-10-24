"""Class-level AI reporting for the retained Math 9 Chapter 8 combined lessons 25 and 26.

The service deliberately has one fixed scope.  It builds a privacy-minimized
packet from finalized, in-class answer facts, keeps observed outcomes separate
from unvalidated next-attempt hypotheses, and stores every generated snapshot
for audit/review.  The deterministic path is useful both when the configured
provider is unavailable and when a teacher needs a report with no external
call.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time
from collections import defaultdict
from copy import deepcopy

import requests
from sqlalchemy.exc import IntegrityError

from database import db
from models import (
    ClassAIAnalysisRun,
    Enrollment,
    Exam,
    ExamQuestion,
    ExamSubmission,
    LearningHistory,
    SubmissionAnswer,
)
from services.ai_gateway import (
    AICooldownError,
    AIConfigurationError,
    AIGatewayError,
    GeminiAIGateway,
    TEACHER_GEMINI_MODEL,
    teacher_default_group,
)
from services.curriculum_data import (
    CHAPTER6_CODE,
    CHAPTER6_GRADE,
    RETAINED_LESSON_CODE,
    RETAINED_LESSON_NAME,
    is_retained_code,
)
from services.personalization_evidence import (
    actual_answer,
    answer_status,
    expected_answer,
    is_finalized,
)


SCOPE_CODE = f"{CHAPTER6_GRADE}C{CHAPTER6_CODE}-{RETAINED_LESSON_CODE}"
SUBJECT_DEFAULT = "Toán"
PROMPT_VERSION = "class-c8-i-v8-teacher-support"
SCHEMA_VERSION = "class-lesson4-report-v1"
INPUT_SCHEMA_VERSION = "class-lesson4-input-v1"
LESSON4_SCOPE = {
    "grade": CHAPTER6_GRADE,
    "chapter_code": CHAPTER6_CODE,
    "lesson_code": RETAINED_LESSON_CODE,
    "lesson_name": RETAINED_LESSON_NAME,
    "scope_code": SCOPE_CODE,
}

_ANSWER_STATUSES = {"answered", "graded"}
MAX_FINALIZED_SNAPSHOTS_PER_STUDENT = 24
_ERROR_CODES = {
    "true_false": ("statement_mismatch", "Mệnh đề đúng/sai không khớp đáp án"),
    "short_answer": ("short_answer_mismatch", "Câu trả lời ngắn không khớp đáp án chấm"),
    "multi": ("choice_set_mismatch", "Tập lựa chọn không khớp đáp án"),
    "single": ("choice_mismatch", "Lựa chọn không khớp đáp án"),
}
SKILL_NAMES = {
    "9C8-i-1": "Dạng 1: Viết tập hợp không gian mẫu",
    "9C8-i-2": "Dạng 2: Xác định số phần tử không gian mẫu",
    "9C8-i-3": "Dạng 3: Xác suất trò chơi Tung đồng xu",
    "9C8-i-4": "Dạng 4: Xác suất trò chơi Gieo xúc xắc",
    "9C8-i-5": "Dạng 5: Xác suất trò chơi Vòng quay số",
    "9C8-i-6": "Dạng 6: Xác suất trò chơi Rút thẻ từ trong hộp",
    "9C8-i-7": "Dạng 7: Xác suất phép thử viết số tự nhiên",
    "9C8-i-8": "Dạng 8: Xác suất trò chơi chọn đối tượng",
}



def _env_int(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _iso(value):
    return value.isoformat() if value else None


def _scope_code(value):
    value = str(value or "").strip()
    # Catalog keys keep the combined-lesson marker lowercase.
    return f"{SCOPE_CODE}-{value.rsplit('-', 1)[-1]}" if is_retained_code(value) else None


def _stable_student_ref(course_id, student_id):
    salt = os.environ.get("AI_ANALYSIS_PSEUDONYM_SALT", "educenter-chapter6")
    # The token is stable for the student across repeated class reports while
    # still exposing no database id, name, code, or contact information.
    return hashlib.sha256(f"{salt}:student:{student_id}".encode("utf-8")).hexdigest()[:16]


def _answer_for_history(row, submission):
    if row.submission_answer_id:
        answer = db.session.get(SubmissionAnswer, row.submission_answer_id)
        if answer:
            return answer
    return next((answer for answer in submission.answers if answer.question_id == row.exam_question_id), None)


def _question_for_history(row):
    return db.session.get(ExamQuestion, row.exam_question_id)


def _event_error(question):
    qtype = str(question.question_type or "single").strip().lower()
    qtype = {"truefalse": "true_false", "true-false": "true_false", "multiple_choice": "multi"}.get(qtype, qtype)
    return _ERROR_CODES.get(qtype, _ERROR_CODES["single"])


def _actual_answer_text(answer, question):
    """Make the frozen answer evidence readable without losing raw IDs."""
    payload = actual_answer(answer)
    qtype = str(question.question_type or "single").strip().lower()
    if qtype in ("short_answer", "essay", "tu_luan"):
        from services.question_policy import resolve_formula_to_text
        return resolve_formula_to_text(payload)
    by_id = {str(item.id): item.answer_text for item in question.answers}
    if qtype in ("true_false", "truefalse", "true-false"):
        return {by_id.get(str(key), str(key)): value for key, value in payload.items()}
    selected = payload.get("selected_answer_ids", [])
    return [by_id.get(str(item), str(item)) for item in selected]


def _expected_answer_text(question):
    qtype = str(question.question_type or "single").strip().lower()
    if qtype in ("short_answer", "essay", "tu_luan"):
        from services.question_policy import resolve_formula_to_text
        answers = [
            resolve_formula_to_text(item.answer_text)
            for item in question.answers
            if item.answer_text and (item.is_correct or item.is_correct is None)
        ]
        answers = [s for s in answers if s]
        return " / ".join(answers) if answers else ""
    if qtype in ("true_false", "truefalse", "true-false"):
        return {item.answer_text: bool(item.is_correct) for item in question.answers}
    return [item.answer_text for item in question.answers if item.is_correct]


def _finalized_events(course, roster, source_cutoff=None):
    """Return answer-level facts strictly belonging to this course and scope."""
    student_ids = [item["student_id"] for item in roster]
    if not student_ids:
        return {item["student_ref"]: [] for item in roster}

    submissions = ExamSubmission.query.join(Exam, Exam.id == ExamSubmission.exam_id).filter(
        Exam.course_id == course.id,
        ExamSubmission.student_id.in_(student_ids),
        ExamSubmission.submitted_at.isnot(None),
    ).all()
    finalized = {
        submission.id: submission
        for submission in submissions
        if is_finalized(submission)
    }
    if not finalized:
        return {item["student_ref"]: [] for item in roster}

    rows = LearningHistory.query.filter(
        LearningHistory.submission_id.in_(list(finalized)),
        LearningHistory.student_id.in_(student_ids),
        LearningHistory.subject == course.subject,
    ).order_by(LearningHistory.occurred_at.asc(), LearningHistory.id.asc()).all()
    from services.assessment_evidence import assessment_rows
    rows.extend(assessment_rows(finalized.values()))
    rows.sort(key=lambda row: (row.occurred_at or dt.datetime.min, row.submission_id, row.exam_question_id or 0))
    by_ref = {item["student_ref"]: [] for item in roster}
    refs_by_student = {item["student_id"]: item["student_ref"] for item in roster}
    seen_refs = set()
    for row in rows:
        submission = finalized.get(row.submission_id)
        student_ref = refs_by_student.get(row.student_id)
        if not submission or not student_ref or submission.student_id != row.student_id:
            continue
        if source_cutoff and submission.submitted_at and submission.submitted_at > source_cutoff:
            continue
        if source_cutoff and row.occurred_at and row.occurred_at > source_cutoff:
            continue
        code = _scope_code(row.curriculum_code)
        question = _question_for_history(row)
        if not code and question:
            code = _scope_code(question.curriculum_code)
        if not code or not question:
            # Unknown curriculum metadata is intentionally excluded from a
            # fixed Lesson 4 report rather than guessed into this scope.
            continue
        answer = _answer_for_history(row, submission)
        if not answer:
            continue
        current_status = row.answer_status or answer_status(answer)
        if current_status not in _ANSWER_STATUSES:
            continue
        ref = row.evidence_ref or (
            f"submission:{submission.id}:answer:{answer.id}:revision:{submission.grading_revision or row.grading_revision or 0}"
        )
        if ref in seen_refs:
            continue
        seen_refs.add(ref)
        is_correct = bool(row.is_correct)
        from services.practice_evidence import statement_results
        statements = statement_results(answer)
        statement_texts = {option.id: option.answer_text for option in question.answers}
        statements = [dict(s, text=statement_texts.get(s["statement_id"], "")) for s in statements]
        statement_count = len(statements)
        answered_statement_count = sum(s["status"] == "answered" for s in statements)
        coverage_status = "not_applicable"
        outcome = "correct" if is_correct else "wrong"
        event_type = "observed_progress" if is_correct else "observed_error"
        if statements:
            answered_statements = [s for s in statements if s["status"] == "answered"]
            coverage_status = "complete" if answered_statement_count == statement_count else (
                "partial" if answered_statement_count else "none"
            )
            if not answered_statements:
                continue
            if coverage_status != "complete":
                # A partially answered parent is evidence of partial coverage,
                # not a full observed-progress/error event.  In particular,
                # three correct statements must not imply mastery of the
                # fourth or of the parent skill.
                is_correct = None
                outcome = "partial"
                event_type = "observed_partial"
            else:
                is_correct = all(s["correct"] for s in answered_statements)
                outcome = "correct" if is_correct else "wrong"
                event_type = "observed_progress" if is_correct else "observed_error"
        error_code, error_label = _event_error(question)
        actual_payload = actual_answer(answer)
        by_ref[student_ref].append({
            "event_ref": ref,
            "evidence_ref": ref,
            "event_type": event_type,
            "outcome": outcome,
            "student_ref": student_ref,
            "submission_id": submission.id,
            "assessment_source": submission.exam.assessment_purpose or submission.exam_type,
            "question_id": question.id,
            "answer_id": answer.id,
            "question_ref": f"exam_question:{question.id}",
            "answer_ref": f"submission_answer:{answer.id}",
            "curriculum_code": code,
            "topic": question.topic_snapshot or code,
            "cognitive_level": question.difficulty_level,
            "error_code": error_code if outcome == "wrong" else None,
            "error_label": error_label if outcome == "wrong" else None,
            "question_text": (question.question_text or "")[:1200],
            "question_context": question.context or "",
            "image_url": question.image_url or "",
            "actual_answer": actual_payload,
            "statement_results": statements,
            "question_type": question.question_type,
            "actual_answer_text": _actual_answer_text(answer, question),
            "expected_answer": expected_answer(question),
            "expected_answer_text": _expected_answer_text(question),
            "grading_revision": int(submission.grading_revision or row.grading_revision or 0),
            "occurred_at": _iso(row.occurred_at or submission.submitted_at),
            "question_content_hash": question.source_content_hash,
            "statement_count": statement_count,
            "answered_statement_count": answered_statement_count,
            "coverage_status": coverage_status,
            "complete_response": coverage_status in ("not_applicable", "complete"),
        })
    return by_ref


def _finalized_submission_snapshots(course, roster, source_cutoff=None):
    """Identity-only finalized scope snapshots, including all-blank papers.

    Answer events intentionally exclude blanks.  These rows make the input
    fingerprint advance nevertheless when a newly finalized in-scope paper
    has no answered item, without sending answer content or learner identity
    to an external provider.
    """
    student_ids = [item["student_id"] for item in roster]
    output = {item["student_ref"]: [] for item in roster}
    if not student_ids:
        return output
    ref_by_student = {item["student_id"]: item["student_ref"] for item in roster}
    submissions = ExamSubmission.query.join(Exam, Exam.id == ExamSubmission.exam_id).filter(
        Exam.course_id == course.id,
        ExamSubmission.student_id.in_(student_ids),
        ExamSubmission.submitted_at.isnot(None),
    ).order_by(ExamSubmission.submitted_at.desc(), ExamSubmission.id.desc()).all()
    for submission in submissions:
        if not is_finalized(submission):
            continue
        if source_cutoff and submission.submitted_at and submission.submitted_at > source_cutoff:
            continue
        # Require at least one frozen item in the retained scope.  We do not
        # infer scope from an exam title or from a mutable bank row.
        if not any(_scope_code(question.curriculum_code) for question in submission.exam.questions):
            continue
        student_ref = ref_by_student.get(submission.student_id)
        if not student_ref or len(output[student_ref]) >= MAX_FINALIZED_SNAPSHOTS_PER_STUDENT:
            continue
        output[student_ref].append({
            "submission_id": submission.id,
            "grading_revision": int(submission.grading_revision or 0),
            "submitted_at": _iso(submission.submitted_at),
            "status": submission.status,
        })
    return output


def build_class_lesson4_packet(course, *, source_cutoff=None):
    """Build the canonical, anonymized request packet for one owned course."""
    source_cutoff = source_cutoff or dt.datetime.utcnow()
    enrollments = Enrollment.query.filter_by(course_id=course.id, status="active").order_by(
        Enrollment.student_id.asc(), Enrollment.id.asc()
    ).all()
    roster = []
    for enrollment in enrollments:
        student = enrollment.student
        if not student or student.role != "student":
            continue
        roster.append({
            "student_id": student.id,
            "student_ref": _stable_student_ref(course.id, student.id),
            "enrollment_id": enrollment.id,
            "enrolled_at": _iso(enrollment.enrolled_at),
        })
    events_by_ref = _finalized_events(course, roster, source_cutoff=source_cutoff)
    snapshots_by_ref = _finalized_submission_snapshots(course, roster, source_cutoff=source_cutoff)
    students = []
    total_events = 0
    total_snapshots = 0
    for item in roster:
        events = events_by_ref.get(item["student_ref"], [])
        snapshots = snapshots_by_ref.get(item["student_ref"], [])
        total_events += len(events)
        total_snapshots += len(snapshots)
        students.append({
            "student_ref": item["student_ref"],
            "events": events,
            "finalized_submission_snapshots": snapshots,
        })
    return {
        "schema_version": INPUT_SCHEMA_VERSION,
        "scope": {**LESSON4_SCOPE, "subject": course.subject, "course_ref": f"course:{course.id}"},
        "roster": [{"student_ref": item["student_ref"]} for item in roster],
        "students": students,
        "coverage": {
            "policy": "strict_in_class_course_only",
            "history_scope": "finalized_answer_facts_only",
            "roster_count": len(roster),
            "students_with_data": sum(bool(item["events"]) for item in students),
            "students_without_data": sum(not item["events"] for item in students),
            "event_count": total_events,
            "finalized_submission_count": total_snapshots,
            "finalized_snapshot_limit_per_student": MAX_FINALIZED_SNAPSHOTS_PER_STUDENT,
            "source_cutoff": _iso(source_cutoff),
        },
    }


def packet_fingerprint(packet, *, provider=None, model_name=None, prompt_version=PROMPT_VERSION,
                       credential_source=None, config_revision=None, key_group_id=None,
                       owner_id=None):
    """Fingerprint evidence plus the provider/model/prompt contract.

    Including the execution contract prevents a report generated by an older
    prompt/model from being reused after configuration changes, even when the
    roster and answers are unchanged.
    """
    canonical = deepcopy(packet)
    coverage = canonical.get("coverage", {})
    coverage.pop("source_cutoff", None)
    canonical["coverage"] = coverage
    provider = provider or os.environ.get("AI_ANALYSIS_PROVIDER", "openai-compatible").strip() or "openai-compatible"
    model_name = model_name or os.environ.get("AI_ANALYSIS_MODEL", "").strip() or "configured-model"
    return _hash({
        "packet": canonical,
        "provider": provider[:80],
        "model_name": model_name[:120],
        "prompt_version": prompt_version,
        "credential_source": credential_source,
        "config_revision": config_revision,
        "key_group_id": key_group_id,
        # Unavailable teacher configurations have no group id.  Include the
        # current owner so a reassigned course cannot reuse the former
        # teacher's fallback snapshot.
        "owner_id": owner_id,
    })


def _events_by_ref(packet):
    output = {}
    owner = {}
    for student in packet.get("students", []):
        token = student.get("student_ref")
        for event in student.get("events", []):
            ref = str(event.get("event_ref") or event.get("evidence_ref") or "")
            if ref:
                output[ref] = event
                owner[ref] = token
    return output, owner


def _external_error_event_copy(event):
    """Return the minimum evidence-grounded error copy safe for external AI."""
    statements = list(event.get("statement_results") or [])
    wrong_statements = [
        {
            "label": row.get("label"),
            "curriculum_code": row.get("curriculum_code"),
            "cognitive_level": row.get("cognitive_level"),
            "actual": row.get("actual"),
            "status": "answered",
            "correct": False,
        }
        for row in statements
        if row.get("status") == "answered" and row.get("correct") is False
    ]
    is_parent_error = event.get("event_type") == "observed_error" and event.get("outcome") == "wrong"
    if not is_parent_error and not wrong_statements:
        return None
    skill = next((row.get("curriculum_code") for row in wrong_statements if row.get("curriculum_code")), None)
    cognitive = next((row.get("cognitive_level") for row in wrong_statements if row.get("cognitive_level")), None)
    copied = {
        "event_ref": event.get("event_ref"),
        "evidence_ref": event.get("evidence_ref") or event.get("event_ref"),
        "event_type": "observed_error",
        "outcome": "wrong",
        "student_ref": event.get("student_ref"),
        "assessment_source": event.get("assessment_source"),
        "curriculum_code": skill or event.get("curriculum_code"),
        "cognitive_level": cognitive or event.get("cognitive_level"),
        "error_code": "statement_mismatch" if statements else event.get("error_code"),
        "error_label": "Mệnh đề đã trả lời không khớp đáp án" if statements else event.get("error_label"),
        "question_ref": event.get("question_ref"),
        "answer_ref": event.get("answer_ref"),
        "question_text": event.get("question_text"),
        "question_context": event.get("question_context"),
        "occurred_at": event.get("occurred_at"),
        "grading_revision": event.get("grading_revision"),
        "coverage_status": event.get("coverage_status"),
        "complete_response": event.get("complete_response"),
    }
    if wrong_statements:
        copied["wrong_statement_results"] = wrong_statements
        copied["statement_comparison"] = deepcopy(statements)
    else:
        copied["actual_answer_text"] = deepcopy(event.get("actual_answer_text"))
        copied["expected_answer_text"] = deepcopy(event.get("expected_answer_text"))
    return copied


def _evidence_strength(count):
    return "limited" if count <= 1 else "repeated"


def _deterministic_risk(skill, refs, student_refs, label=None):
    return {
        "skill": skill,
        "hypothesis": (
            f"Có thể tiếp tục gặp lỗi ở {label or skill} khi gặp câu tương tự; "
            "đây là giả thuyết cần theo dõi, không phải kết luận nguyên nhân."
        ),
        "basis_evidence_refs": list(refs),
        "affected_student_refs": list(student_refs),
        "evidence_strength": _evidence_strength(len(refs)),
        "validation": "not_validated",
        "trigger_condition": f"Khi gặp lại câu cùng kỹ năng {label or skill} với cách biểu đạt tương tự.",
        "verification_question": "Em đã đối chiếu lựa chọn của mình với điều kiện nào trong đề?",
        "suggested_remediation": "Cho luyện lại câu tương tự, yêu cầu giải thích bước chọn đáp án và xem lại từng bằng chứng sai.",
    }


def deterministic_class_report(packet, *, reason=None, include_risk_hypotheses=False):
    """Build observed facts; outage fallback deliberately has no hypotheses."""
    events, owners = _events_by_ref(packet)
    grouped = defaultdict(list)
    for ref, event in events.items():
        if event.get("outcome") == "wrong":
            grouped[(event.get("curriculum_code") or "unknown", event.get("error_code") or "observed_error")].append(ref)

    observed_errors = []
    for (skill, error_code), refs in sorted(grouped.items()):
        student_refs = sorted({owners[ref] for ref in refs})
        labels = [events[ref].get("error_label") for ref in refs if events[ref].get("error_label")]
        observed_errors.append({
            "skill": skill,
            "error_code": error_code,
            "error_label": labels[0] if labels else "Câu trả lời sai đã chấm",
            "claim": "Quan sát câu trả lời sai đã chấm; chưa đủ bằng chứng để kết luận nguyên nhân hay misconception ổn định.",
            "evidence_refs": refs,
            "affected_student_refs": student_refs,
            "observation_count": len(refs),
            "evidence_strength": _evidence_strength(len(refs)),
        })

    recovery = []
    for student in packet.get("students", []):
        prior_wrong = {}
        for event in student.get("events", []):
            skill = event.get("curriculum_code") or "unknown"
            if event.get("outcome") == "wrong":
                prior_wrong[skill] = event.get("event_ref")
            elif event.get("outcome") == "correct" and prior_wrong.get(skill):
                recovery.append({
                    "skill": skill,
                    "student_ref": student.get("student_ref"),
                    "evidence_refs": [prior_wrong[skill], event.get("event_ref")],
                    "claim": "Có câu trả lời đúng sau một quan sát sai trước đó ở cùng kỹ năng; đây là dấu hiệu tiến bộ cần tiếp tục kiểm tra.",
                })

    fallback_risks = []
    if include_risk_hypotheses:
        for (skill, _error_code), refs in sorted(grouped.items()):
            students = sorted({owners[ref] for ref in refs})
            label = next((events[ref].get("topic") for ref in refs if events[ref].get("topic")), None)
            fallback_risks.append(_deterministic_risk(skill, refs, students, label))

    student_rows = []
    for student in packet.get("students", []):
        token = student.get("student_ref")
        rows = student.get("events", [])
        wrong = [event for event in rows if event.get("outcome") == "wrong"]
        correct = [event for event in rows if event.get("outcome") == "correct"]
        by_skill = defaultdict(list)
        for event in wrong:
            by_skill[(event.get("curriculum_code") or "unknown", event.get("error_code") or "observed_error")].append(event.get("event_ref"))
        risks = [
            _deterministic_risk(skill, refs, [token], next((events[ref].get("topic") for ref in refs if events[ref].get("topic")), None))
            for (skill, _code), refs in sorted(by_skill.items())
        ] if include_risk_hypotheses else []
        student_rows.append({
            "student_ref": token,
            "data_status": "no_data" if not rows else "has_data",
            "observed_events": rows,
            "observed_errors": wrong,
            "observed_progress": correct,
            "next_risk_hypotheses": risks,
            "recommendations": [risk["suggested_remediation"] for risk in risks],
            "note": (
                "Chưa có câu trả lời đã chấm trong phạm vi lớp và Bài 25 + 26."
                if not rows else
                ("Các rủi ro tương lai chỉ là giả thuyết chưa kiểm chứng; không phải xác suất hay nhãn năng lực."
                 if include_risk_hypotheses else
                 "Chỉ hiển thị dữ liệu quan sát; chưa có giả thuyết AI về rủi ro tiếp theo.")
            ),
        })

    if observed_errors:
        recommendations = [{
            "skill": item["skill"],
            "text": "Ôn lại kỹ năng này bằng câu tương tự và đối chiếu đáp án thực tế trong các ref đã nêu.",
            "basis_evidence_refs": item["evidence_refs"],
        } for item in observed_errors]
        diagnosis = "Báo cáo ghi nhận các lỗi trên câu đã chấm và các dấu hiệu tiến bộ trong Bài 25 + 26; chưa kết luận misconception ổn định."
    else:
        recommendations = [{
            "skill": None,
            "text": "Chưa có lỗi sai đã chấm trong phạm vi dữ liệu lớp; tiếp tục thu thập câu trả lời Bài 25 + 26 để có bằng chứng.",
            "basis_evidence_refs": [],
        }]
        diagnosis = "Chưa có đủ bằng chứng câu sai đã chấm trong phạm vi lớp và Bài 25 + 26 để xác định điểm yếu."
    if reason:
        diagnosis = f"{diagnosis} Nguồn: {reason}."

    return {
        "schema_version": SCHEMA_VERSION,
        "scope": LESSON4_SCOPE,
        "class_summary": {
            "diagnosis": diagnosis,
            "observed_errors": observed_errors,
            "observed_progress_recovery": recovery,
            "next_risk_hypotheses": fallback_risks,
            "recommendations": recommendations,
        },
        "students": student_rows,
        "coverage": packet.get("coverage", {}),
        "limitations": [
            "Chỉ dùng câu trả lời đã nộp và đã chấm của đúng lớp này; câu bỏ trống/chưa chấm bị loại.",
            "Observed errors là sự kiện trên câu cụ thể, không tự động là misconception.",
            "Next-risk hypotheses là giả thuyết validation=not_validated, không phải xác suất đã hiệu chuẩn.",
        ],
    }


def _validate_refs(refs, known_refs, owner=None, *, required=True):
    if not isinstance(refs, list) or (required and not refs):
        raise ValueError("Danh sách bằng chứng không hợp lệ.")
    clean = []
    for ref in refs[:20]:
        ref = str(ref)
        if ref not in known_refs:
            raise ValueError("AI dẫn chiếu evidence_ref ngoài packet.")
        if ref not in clean:
            clean.append(ref)
    if owner and any(known_refs[ref] != owner for ref in clean):
        raise ValueError("AI dẫn chiếu bằng chứng của học sinh khác.")
    return clean


def validate_class_report(data, packet, *, require_teacher_support=False):
    """Validate only claims that can be traced to this request packet."""
    if not isinstance(data, dict):
        raise ValueError("AI phải trả về một JSON object.")
    if data.get("schema_version") not in (SCHEMA_VERSION, "class-lesson4-ai-v1"):
        raise ValueError("Sai schema báo cáo lớp Bài 25 + 26.")
    known_events, owners = _events_by_ref(packet)
    known_students = {row.get("student_ref") for row in packet.get("roster", [])}
    known_skills = {event.get("curriculum_code") for event in known_events.values() if event.get("curriculum_code")}
    known_skills.update(statement.get("curriculum_code") for event in known_events.values()
                        for statement in event.get("statement_results", []) if statement.get("curriculum_code"))
    summary = data.get("class_summary") or {}
    if not isinstance(summary, dict):
        raise ValueError("class_summary phải là object.")

    # Some providers return observed sections even though the server owns the
    # canonical observed-event rendering.  Validate them when present so a
    # fabricated ref cannot be smuggled through an otherwise valid response.
    for row in (summary.get("observed_errors") or [])[:80]:
        if not isinstance(row, dict):
            raise ValueError("Observed error không hợp lệ.")
        skill = str(row.get("skill") or row.get("curriculum_code") or "")
        if skill not in known_skills:
            raise ValueError("Observed error dẫn chiếu kỹ năng ngoài packet.")
        refs = _validate_refs(row.get("evidence_refs") or row.get("basis_evidence_refs"), owners)
        if any(known_events[ref].get("outcome") != "wrong" for ref in refs):
            raise ValueError("Observed error phải trỏ tới câu trả lời sai.")
        affected = row.get("affected_student_refs", [])
        if not isinstance(affected, list) or any(str(token) not in known_students for token in affected):
            raise ValueError("Observed error có học sinh ngoài roster.")
        if any(owners[ref] not in affected for ref in refs):
            raise ValueError("Observed error có affected_student_refs không khớp bằng chứng.")
    for row in (summary.get("observed_progress_recovery") or [])[:80]:
        if not isinstance(row, dict):
            raise ValueError("Observed recovery không hợp lệ.")
        token = str(row.get("student_ref") or "")
        if token not in known_students:
            raise ValueError("Observed recovery có học sinh ngoài roster.")
        refs = _validate_refs(row.get("evidence_refs"), owners, token)
        if any(known_events[ref].get("outcome") != "correct" for ref in refs[-1:]):
            raise ValueError("Observed recovery phải có câu trả lời đúng.")

    def error_matches_skill(event, skill):
        return (event.get("outcome") == "wrong" and event.get("curriculum_code") == skill) or any(
            statement.get("status") == "answered" and statement.get("correct") is False
            and (statement.get("curriculum_code") or event.get("curriculum_code")) == skill
            for statement in event.get("statement_results", []))

    def clean_risk(row, owner=None):
        if not isinstance(row, dict):
            return None
        skill = str(row.get("skill") or "").strip()
        if not skill or skill not in known_skills:
            return None
        try:
            raw_refs = row.get("basis_evidence_refs") or row.get("evidence_refs") or []
            refs = _validate_refs(raw_refs, owners, owner)
        except ValueError:
            return None
        matching_refs = [ref for ref in refs if error_matches_skill(known_events[ref], skill)]
        if not matching_refs:
            return None
        affected = row.get("affected_student_refs", [owner] if owner else [])
        if not isinstance(affected, list) or any(str(token) not in known_students for token in affected):
            affected = list({owners[ref] for ref in matching_refs})
        else:
            for ref in matching_refs:
                if owners[ref] not in affected:
                    affected.append(owners[ref])
        if owner and any(str(token) != owner for token in affected):
            return None
        def required_text(key, limit, fallback=""):
            val = str(row.get(key) or fallback).strip()
            return val[:limit] if val else fallback
        hypo = required_text("hypothesis", 800)
        if not hypo:
            return None
        if require_teacher_support and (row.get("validation") != "not_validated" or any(
                not isinstance(row.get(key), str) or not row[key].strip()
                for key in ("trigger_condition", "verification_question", "suggested_remediation"))):
            raise ValueError("Nguy cơ sai lần tiếp theo thiếu điều kiện, câu hỏi kiểm chứng hoặc hướng hỗ trợ.")
        return {
            "skill": skill,
            "hypothesis": hypo,
            "basis_evidence_refs": matching_refs,
            "affected_student_refs": sorted({owners[ref] for ref in matching_refs}),
            "evidence_strength": _evidence_strength(len({known_events[ref].get("question_content_hash") or known_events[ref].get("question_ref") or ref for ref in matching_refs})),
            "validation": "not_validated",
            "trigger_condition": required_text("trigger_condition", 600, "Cần củng cố kiến thức dạng bài này"),
            "verification_question": required_text("verification_question", 600, "Kiểm tra lại dạng bài tương tự"),
            "suggested_remediation": required_text("suggested_remediation", 500, "Hướng dẫn luyện tập lại"),
        }

    def prioritize(rows):
        unique = {(row['skill'], tuple(sorted(row['basis_evidence_refs'])), row['hypothesis']): row for row in rows}
        return sorted(unique.values(), key=lambda row: (
            -len({known_events[ref].get('question_content_hash') or known_events[ref].get('question_ref') or ref for ref in row['basis_evidence_refs']}),
            row['skill'], row['hypothesis']))[:3]

    def clean_summary(rows, owner=None):
        if not isinstance(rows, list):
            raise ValueError("Tóm tắt AI phải là danh sách.")
        output = []
        for row in rows[:6]:
            if not isinstance(row, dict) or not isinstance(row.get("text"), str):
                raise ValueError("Dòng tóm tắt AI không hợp lệ.")
            refs = _validate_refs(row.get("basis_evidence_refs", []), owners, owner, required=False)
            text = row["text"].strip()[:800]
            if text and text not in {item["text"] for item in output}:
                output.append({"text": text, "basis_evidence_refs": refs})
        return output

    def clean_causes(rows, owner=None):
        if not isinstance(rows, list):
            raise ValueError("Giả thuyết nguyên nhân phải là danh sách.")
        output = []
        for row in rows[:30]:
            if not isinstance(row, dict):
                raise ValueError("Giả thuyết nguyên nhân không hợp lệ.")
            refs = _validate_refs(row.get("basis_evidence_refs", []), owners, owner)
            skill = str(row.get("skill") or "")
            if skill not in known_skills or any(not error_matches_skill(known_events[ref], skill) for ref in refs):
                raise ValueError("Nguyên nhân phải dẫn đúng bằng chứng sai của dạng bài.")
            if row.get("validation") != "not_validated":
                raise ValueError("Nguyên nhân phải là giả thuyết chưa kiểm chứng.")
            hypothesis = str(row.get("hypothesis") or "").strip()[:800]
            question = str(row.get("verification_question") or "").strip()[:600]
            if not hypothesis or not question:
                raise ValueError("Nguyên nhân thiếu nội dung hoặc câu hỏi kiểm chứng.")
            output.append({"skill": skill, "hypothesis": hypothesis, "verification_question": question,
                           "validation": "not_validated", "basis_evidence_refs": refs})
        unique = {(row["skill"], row["hypothesis"], tuple(sorted(row["basis_evidence_refs"]))): row for row in output}
        return list(unique.values())[:(3 if owner else 8)]

    teaching_fields = {"learning_goal": 600, "teaching_strategy": 1200, "teacher_question": 600,
                       "practice_suggestion": 800, "success_criteria": 600}

    def clean_recommendation(row, owner=None):
        if not isinstance(row, dict):
            raise ValueError("Khuyến nghị không hợp lệ.")
        refs = _validate_refs(row.get("basis_evidence_refs", []), owners, owner, required=False)
        skill = row.get("skill")
        if skill is not None and str(skill) not in known_skills:
            raise ValueError("Khuyến nghị dẫn chiếu kỹ năng ngoài packet.")
        if skill is not None and any(not (known_events[ref].get("curriculum_code") == str(skill)
                or any(statement.get("curriculum_code") == str(skill)
                       for statement in known_events[ref].get("statement_results", []))) for ref in refs):
            raise ValueError("Khuyến nghị dẫn chiếu bằng chứng khác dạng kiến thức.")
        clean = {
            "skill": str(skill) if skill is not None else None,
            "text": str(row.get("text") or row.get("recommendation") or "").strip()[:600],
            "basis_evidence_refs": refs,
        }
        for key, limit in teaching_fields.items():
            value = row.get(key, "")
            if not isinstance(value, str):
                raise ValueError("Các nội dung hướng dạy phải là chuỗi văn bản.")
            clean[key] = value.strip()[:limit]
        if require_teacher_support and (not clean["text"] or any(not clean[key] for key in teaching_fields)):
            raise ValueError("Khuyến nghị thiếu mục tiêu, hướng dạy, câu hỏi, bài luyện hoặc tiêu chí kiểm tra tiến bộ.")
        return clean

    risks = [r for row in (summary.get("next_risk_hypotheses") or [])[:80] if (r := clean_risk(row)) is not None]
    recommendations = [clean_recommendation(row) for row in (summary.get("recommendations") or [])[:80]]

    student_rows = {}
    raw_students = data.get("students", [])
    if not isinstance(raw_students, list):
        raise ValueError("students phải là danh sách.")
    for row in raw_students[:500]:
        if not isinstance(row, dict):
            raise ValueError("Mục học sinh không hợp lệ.")
        token = str(row.get("student_ref") or "")
        if token not in known_students or token in student_rows:
            raise ValueError("AI trả về student_ref ngoài roster hoặc trùng.")
        for event in (row.get("observed_events") or [])[:200]:
            if not isinstance(event, dict):
                raise ValueError("Observed event cá nhân không hợp lệ.")
            refs = _validate_refs([event.get("event_ref") or event.get("evidence_ref")], owners, token)
            if not refs:
                raise ValueError("Observed event thiếu evidence_ref.")
        personal_risks = [risk for item in (row.get("next_risk_hypotheses") or [])[:30] if (risk := clean_risk(item, token)) is not None]
        student_recommendations = []
        for item in (row.get("recommendations") or [])[:30]:
            if isinstance(item, str) and not require_teacher_support:
                student_recommendations.append(item[:500])
            elif isinstance(item, dict):
                student_recommendations.append(clean_recommendation(item, token))
            else:
                raise ValueError("Khuyến nghị cá nhân không hợp lệ.")
        student_rows[token] = {
            "student_ref": token,
            "ai_summary": clean_summary(row.get("ai_summary", []), token),
            "cause_hypotheses": clean_causes(row.get("cause_hypotheses", []), token),
            "next_risk_hypotheses": prioritize(personal_risks),
            "recommendations": student_recommendations,
        }
    result = {
        "class_summary": {
            "ai_summary": clean_summary(summary.get("ai_summary", [])),
            "cause_hypotheses": clean_causes(summary.get("cause_hypotheses", [])),
            "next_risk_hypotheses": prioritize(risks),
            "recommendations": recommendations,
        },
        "students": student_rows,
    }
    if require_teacher_support:
        def require_sections(section, error_refs):
            if not section or not section.get("ai_summary") or not section.get("recommendations"):
                raise ValueError("AI chưa trả đủ tóm tắt và khuyến nghị hướng dạy cho giáo viên.")
            if error_refs:
                if not section.get("cause_hypotheses") or not section.get("next_risk_hypotheses"):
                    raise ValueError("AI chưa trả đủ giả thuyết nguyên nhân và nguy cơ sai ở lần tiếp theo.")
                if not any(set(row.get("basis_evidence_refs", [])).intersection(error_refs)
                           for row in section["recommendations"]):
                    raise ValueError("Khuyến nghị hướng dạy chưa gắn với bằng chứng lỗi quan sát.")
        error_refs = {ref for ref, event in known_events.items() if _external_error_event_copy(event)}
        if packet.get("coverage", {}).get("event_count"):
            require_sections(result["class_summary"], error_refs)
        counts = {row.get("student_ref"): sum(row.get(key, 0) for key in ("correct", "wrong", "partial"))
                  for row in packet.get("observed_statistics", {}).get("students", [])}
        for person in packet.get("students", []):
            token = person.get("student_ref")
            if person.get("events") or counts.get(token):
                require_sections(student_rows.get(token), {ref for ref in error_refs if owners[ref] == token})
    return result


from services.diagnostic_report_contract import SYSTEM_PROMPT as DIAGNOSTIC_SYSTEM_PROMPT

SYSTEM_PROMPT = DIAGNOSTIC_SYSTEM_PROMPT + """\nĐây là báo cáo toàn lớp: giữ class_summary và students theo schema. Dẫn đúng evidence_ref của từng học sinh, không ghép bằng chứng người khác. Trong next_risk_hypotheses.hypothesis, viết ngắn gọn 1–2 câu, chỉ rõ có nguy cơ sai tiếp theo ở điểm nào để giáo viên nắm bắt. Chỉ tối đa 3 nguy cơ mỗi học sinh. Không suy ra tỉ lệ đúng toàn lớp từ hồ sơ chỉ gồm lỗi; không dùng ngôn ngữ xác suất/calibration. Tuân thủ schema báo cáo lớp và hướng dạy bên dưới."""

SYSTEM_PROMPT += """\nBáo cáo phục vụ GIÁO VIÊN chọn cách dạy và hỗ trợ. Bắt buộc trả đủ các phần sau cho lớp và từng học sinh có dữ liệu:
1. ai_summary: 3–5 dòng ngắn cho lớp, 1–3 dòng cho mỗi học sinh. Dùng observed_statistics cho số liệu; đếm lượt trả lời câu, không phải ý Đúng/Sai. partial nghĩa chưa trả lời đủ ý; không kết luận nắm vững từ số câu đúng.
2. cause_hypotheses: khi có bằng chứng lỗi, nêu ít nhất một nguyên nhân CÓ THỂ CÓ, có skill, hypothesis, basis_evidence_refs, verification_question, validation=not_validated. Câu hỏi phải giúp giáo viên xác minh cách học sinh suy nghĩ/làm bài. Với ít bằng chứng, nêu rõ cần kiểm chứng; không kết luận nguyên nhân là sự thật.
3. next_risk_hypotheses: khi có lỗi, nêu ít nhất một nguy cơ CÓ THỂ SAI ở lần làm tiếp theo, tối đa ba. Chỉ rõ học sinh có thể sai bước nào, khi gặp dạng/điều kiện nào, câu hỏi kiểm chứng và hướng hỗ trợ. Dẫn đúng bằng chứng lỗi, validation=not_validated. Không viết lại nguyên nhân vào phần nguy cơ; không tự cho tỷ lệ dự đoán.
4. recommendations: trả object có text, skill, basis_evidence_refs, learning_goal, teaching_strategy, teacher_question, practice_suggestion, success_criteria. Nêu mục tiêu cần củng cố, các bước hướng dẫn cụ thể cho giáo viên, câu hỏi gợi mở trực tiếp dùng được trên lớp, dạng bài luyện và tiêu chí quan sát học sinh tiến bộ. Báo cáo lớp có thể gợi ý chia nhóm theo lỗi; báo cáo cá nhân điều chỉnh cho lỗi của học sinh đó. Khi có lỗi, ít nhất một khuyến nghị phải dẫn bằng chứng lỗi. Không chỉ viết 'ôn lại kiến thức' hoặc 'luyện thêm'. Ưu tiên tối đa ba khuyến nghị mỗi học sinh, năm cho lớp.
Học sinh có số liệu nhưng chưa ghi nhận lỗi: để cause_hypotheses và next_risk_hypotheses trống, có tóm tắt và hướng dạy kiểm tra thêm thay vì bịa điểm yếu. Học sinh không có dữ liệu: để mọi nhận định trống. Không nêu tên hoặc đưa thêm dữ liệu ngoài packet."""


def _user_prompt(packet):
    summary_schema = [{"text": "tóm tắt dựa vào observed_statistics và bằng chứng", "basis_evidence_refs": []}]
    cause_schema = [{"skill": "exact curriculum_code", "hypothesis": "nguyên nhân có thể có",
                     "basis_evidence_refs": ["exact event_ref"], "verification_question": "câu hỏi kiểm chứng",
                     "validation": "not_validated"}]
    recommendation_schema = [{
        "skill": "exact curriculum_code or null", "text": "ưu tiên hỗ trợ giáo viên",
        "basis_evidence_refs": ["exact error event_ref when errors exist"],
        "learning_goal": "mục tiêu kiến thức/cách làm cần củng cố",
        "teaching_strategy": "các bước giáo viên hướng dẫn, minh họa và cho học sinh tự giải thích",
        "teacher_question": "câu hỏi gợi mở cụ thể giáo viên có thể dùng ngay",
        "practice_suggestion": "dạng bài luyện và cách thay đổi điều kiện để kiểm tra",
        "success_criteria": "tiêu chí quan sát/kiểm tra ngắn để biết học sinh tiến bộ",
    }]
    schema = {
        "schema_version": SCHEMA_VERSION,
        "class_summary": {
            "ai_summary": summary_schema,
            "cause_hypotheses": cause_schema,
            "next_risk_hypotheses": [{
                "skill": "exact curriculum_code",
                "hypothesis": "hypothesis, not a fact",
                "basis_evidence_refs": ["exact event_ref from packet"],
                "affected_student_refs": ["exact student_ref"],
                "evidence_strength": "limited|repeated",
                "validation": "not_validated",
                "trigger_condition": "specific triggering scenario",
                "verification_question": "teacher question that could validate the hypothesis",
                "suggested_remediation": "string",
            }],
            "recommendations": recommendation_schema,
        },
        "students": [{
            "student_ref": "exact student_ref",
            "ai_summary": summary_schema,
            "cause_hypotheses": cause_schema,
            "next_risk_hypotheses": "same schema as above; only this student's refs",
            "recommendations": recommendation_schema,
        }],
    }
    return (
        "Không nêu tên, mã học sinh, số điện thoại hoặc dữ liệu ngoài packet. "
        "Không tự thêm học sinh/kỹ năng/ref.\nSCHEMA:\n"
        + _canonical_json(schema)
        + "\nPACKET:\n"
        + _canonical_json(packet)
    )


class ClassLesson4ReportService:
    """Generate/cache one fixed-scope report with durable idempotency."""

    def __init__(self, http_session=None, sleep_fn=None):
        self.session = http_session or requests.Session()
        self.sleep = sleep_fn or time.sleep
        self.url = os.environ.get("AI_ANALYSIS_API_URL", "").strip()
        self.api_key = os.environ.get("AI_ANALYSIS_API_KEY", "").strip()
        self.model = (os.environ.get("AI_ANALYSIS_MODEL", "").strip() or "configured-model")[:120]
        self.provider = (os.environ.get("AI_ANALYSIS_PROVIDER", "openai-compatible").strip() or "openai-compatible")[:80]
        self.timeout = _env_int("AI_ANALYSIS_TIMEOUT_SECONDS", 20, 3, 60)
        self.retries = _env_int("AI_ANALYSIS_RETRIES", 2, 0, 3)
        self.batch_size = _env_int("CLASS_REPORT_AI_BATCH_SIZE", 40, 1, 100)
        self.max_events_per_student = _env_int("CLASS_REPORT_AI_MAX_EVENTS_PER_STUDENT", 100, 1, 500)
        self.processing_timeout = _env_int("CLASS_REPORT_PROCESSING_TIMEOUT_SECONDS", 300, 30, 3600)
        self.fallback_retry_seconds = _env_int("CLASS_REPORT_FALLBACK_RETRY_SECONDS", 60, 15, 3600)
        self.gateway = GeminiAIGateway(http_session=self.session, sleep_fn=self.sleep)

    @property
    def configured(self):
        return bool(self.url)

    def input_hash(self, packet, configuration=None, identity=None):
        provider = configuration.provider if configuration else (identity or {}).get("provider", self.provider)
        model_name = configuration.model_name if configuration else (identity or {}).get("model_name", self.model)
        return packet_fingerprint(
            packet,
            provider=provider,
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
            credential_source=(identity or {}).get("source"),
            config_revision=(identity or {}).get("config_revision"),
            key_group_id=(identity or {}).get("group_id"),
            owner_id=(identity or {}).get("owner_id"),
        )

    def _batch_packets(self, packet):
        students = packet.get("students", [])
        batches = [students[index:index + self.batch_size] for index in range(0, len(students), self.batch_size)] or [[]]
        output = []
        total_events = int(packet.get("coverage", {}).get("event_count", 0))
        for index, batch in enumerate(batches):
            included = []
            omitted = 0
            for student in batch:
                # The external model receives a deep-copy of observed errors,
                # never mastery, correct-answer progress, unanswered statements,
                # quotas or selection state. Wrong answered statements in a
                # partial question are copied as errors. The complete packet remains local
                # for deterministic reporting and evidence validation.
                events = [copied for copied in (
                    _external_error_event_copy(event) for event in student.get("events", [])
                ) if copied]
                keep = events[-self.max_events_per_student:]
                omitted += max(0, len(events) - len(keep))
                included.append({"student_ref": student.get("student_ref"), "events": keep})
            batch_packet = {
                "schema_version": INPUT_SCHEMA_VERSION,
                "scope": packet.get("scope", {}),
                "roster": [{"student_ref": student.get("student_ref")} for student in batch],
                "students": included,
                "coverage": {
                    **packet.get("coverage", {}),
                    "batch_index": index + 1,
                    "batch_count": len(batches),
                    "students_in_batch": len(batch),
                    "events_included": sum(len(student["events"]) for student in included),
                    "events_omitted_for_ai_batch": omitted,
                    "events_total_course": total_events,
                    "external_payload": "error_profile_copy_with_observed_counts",
                },
                "observed_statistics": {
                    "unit": "lượt trả lời câu hỏi",
                    "class_totals": {outcome: sum(event.get("outcome") == outcome
                                                  for student in students for event in student.get("events", []))
                                     for outcome in ("correct", "wrong", "partial")},
                    "students": [{"student_ref": student.get("student_ref"),
                                  **{outcome: sum(event.get("outcome") == outcome for event in student.get("events", []))
                                     for outcome in ("correct", "wrong", "partial")}}
                                 for student in batch],
                },
            }
            output.append(batch_packet)
        return output

    def _omitted_event_count(self, packet):
        return sum(
            max(0, len([event for event in student.get("events", [])
                        if _external_error_event_copy(event)]) - self.max_events_per_student)
            for student in packet.get("students", [])
        )

    def _call_api(self, packet, configuration=None):
        configuration = configuration or self.gateway.legacy_configuration()
        return self.gateway.complete(
            configuration,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(packet)},
            ],
            temperature=0, response_format={"type": "json_object"},
        )

    def _run_ai(self, packet, configuration=None):
        if configuration is None:
            configuration = self.gateway.legacy_configuration()
        batches = self._batch_packets(packet)
        if not packet.get("coverage", {}).get("event_count"):
            raise RuntimeError("Chưa có câu trả lời Bài 25 + 26 đã chấm để gửi AI.")
        aggregate = {"schema_version": SCHEMA_VERSION, "class_summary": {"ai_summary": [], "cause_hypotheses": [], "next_risk_hypotheses": [], "recommendations": []}, "students": []}
        for batch in batches:
            raw = self._call_api(batch, configuration)
            clean = validate_class_report(raw, batch, require_teacher_support=True)
            aggregate["class_summary"]["ai_summary"].extend(clean["class_summary"]["ai_summary"])
            aggregate["class_summary"]["cause_hypotheses"].extend(clean["class_summary"]["cause_hypotheses"])
            aggregate["class_summary"]["next_risk_hypotheses"].extend(clean["class_summary"]["next_risk_hypotheses"])
            aggregate["class_summary"]["recommendations"].extend(clean["class_summary"]["recommendations"])
            aggregate["students"].extend(clean["students"].values())
        # Validate the merged response against the complete packet before it is
        # ever persisted or displayed.
        return validate_class_report(aggregate, packet, require_teacher_support=True)

    def _new_run(self, course, packet, input_hash, requested_by, now, configuration=None, identity=None):
        provider = configuration.provider if configuration else (identity or {}).get("provider", self.provider)
        model_name = configuration.model_name if configuration else (identity or {}).get("model_name", self.model)
        run = ClassAIAnalysisRun(
            course_id=course.id,
            ai_key_group_id=(identity or {}).get("group_id"),
            ai_config_revision=(identity or {}).get("config_revision"),
            ai_credential_source=(identity or {}).get("source"),
            requested_by=requested_by,
            scope_code=SCOPE_CODE,
            input_hash=input_hash,
            provider=provider,
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
            status="processing",
            analysis_source="pending",
            request_data=_canonical_json({
                "schema_version": "class-lesson4-error-profile-copy-v1",
                "scope": packet.get("scope", {}),
                "roster": packet.get("roster", []),
                "students": [{
                    "student_ref": student.get("student_ref"),
                    "events": [copied for copied in (
                        _external_error_event_copy(event) for event in student.get("events", [])
                    ) if copied],
                } for student in packet.get("students", [])],
                "coverage": packet.get("coverage", {}),
                "limitations": ["External AI input is an error-profile copy only; it has no mastery, quotas or selection state."],
            }),
            response_data="{}",
            source_cutoff=dt.datetime.fromisoformat(packet["coverage"]["source_cutoff"]),
            roster_count=int(packet.get("coverage", {}).get("roster_count", 0)),
            event_count=int(packet.get("coverage", {}).get("event_count", 0)),
            active_key=f"{course.id}:{SCOPE_CODE}:{input_hash}",
            created_at=now,
        )
        db.session.add(run)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return ClassAIAnalysisRun.query.filter_by(active_key=f"{course.id}:{SCOPE_CODE}:{input_hash}").first(), True
        return run, False

    def _active_run(self, course, input_hash):
        active = ClassAIAnalysisRun.query.filter_by(
            active_key=f"{course.id}:{SCOPE_CODE}:{input_hash}"
        ).first()
        if not active:
            return None
        created = active.created_at or dt.datetime.utcnow()
        if (dt.datetime.utcnow() - created).total_seconds() <= self.processing_timeout:
            return active
        # A worker/request may have been killed after persisting "processing".
        # Release the durable lock so the next bounded request can recover.
        active.status = "failed"
        active.analysis_source = "observed_data_fallback"
        active.error_message = "Yêu cầu trước đã hết thời gian xử lý; có thể thử lại."
        active.active_key = None
        active.completed_at = dt.datetime.utcnow()
        db.session.commit()
        return None

    @staticmethod
    def _safe_error(exc):
        # Gateway exceptions already redact response bodies.  Validation and
        # configuration messages are local, bounded diagnostics; arbitrary
        # exceptions may carry a proxy body, headers, or credentials and are
        # collapsed to a stable public audit message.
        if isinstance(exc, (ValueError, AIConfigurationError, AICooldownError, AIGatewayError)):
            return str(exc or "AI không khả dụng.").replace("\n", " ")[:500]
        return "AI không khả dụng hoặc phản hồi không hợp lệ."

    def _resolve_configuration(self, course, *, allow_legacy):
        """Resolve only the assigned teacher's current default pool."""
        try:
            return self.gateway.resolve_course(course, allow_legacy=allow_legacy), None
        except AIConfigurationError as error:
            # A course with no teacher default remains unavailable.  Legacy
            # process credentials are available only to callers that
            # explicitly construct ``legacy_configuration`` outside this
            # course/report path.
            return None, error

    @staticmethod
    def _unavailable_identity(course):
        """Build a stable unavailable identity from the current owner.

        A legacy ``course.ai_key_group`` relationship may point at a former
        teacher or an old class override, so it is deliberately ignored.  If
        a default exists but is paused, its id/revision still distinguish the
        snapshot from later configuration changes.  When no default exists,
        a negative owner marker in the existing revision column lets
        ``get_latest`` distinguish two owners without a schema migration;
        the owner id is also included in the input hash.
        """
        owner_id = getattr(course, "teacher_id", None)
        group = teacher_default_group(owner_id)
        config_revision = getattr(group, "config_revision", None) if group else None
        if config_revision is None:
            # ``ai_config_revision`` is nullable and historically used 0 for
            # unavailable rows.  A negative owner marker is only used for new
            # Phase 3 unavailable snapshots, preserving old rows while making
            # reassignment cache-safe without adding a column.
            config_revision = -int(owner_id) if owner_id else 0
        return {
            "source": "unavailable",
            "group_id": getattr(group, "id", None),
            "config_revision": config_revision,
            "owner_id": owner_id,
            "provider": "gemini-openai-compatible",
            # Keep unavailable/fallback cache identity aligned with the
            # gateway's immutable teacher model; old group rows retain their
            # historical model_name for audit only.
            "model_name": TEACHER_GEMINI_MODEL if group else "not-configured",
        }

    @staticmethod
    def _identity_for(configuration, course, *, legacy_compatibility):
        if configuration is None:
            return ClassLesson4ReportService._unavailable_identity(course)
        if configuration.source == "legacy_env" and legacy_compatibility:
            # Existing direct integrations retain their original cache/hash.
            return None
        return {
            "source": configuration.source,
            "group_id": configuration.group_id,
            "config_revision": configuration.config_revision,
            "owner_id": configuration.owner_id,
            "provider": configuration.provider,
            "model_name": configuration.model_name,
        }

    def get_latest(self, course, *, allow_legacy=False, legacy_compatibility=False):
        configuration, _ = self._resolve_configuration(course, allow_legacy=allow_legacy)
        identity = self._identity_for(configuration, course, legacy_compatibility=legacy_compatibility)
        query = ClassAIAnalysisRun.query.filter_by(course_id=course.id, scope_code=SCOPE_CODE)
        if identity is not None:
            query = query.filter(
                ClassAIAnalysisRun.ai_key_group_id == identity["group_id"],
                ClassAIAnalysisRun.ai_config_revision == identity["config_revision"],
                ClassAIAnalysisRun.ai_credential_source == identity["source"],
                ClassAIAnalysisRun.provider == identity["provider"],
                ClassAIAnalysisRun.model_name == identity["model_name"],
            )
        return query.order_by(ClassAIAnalysisRun.created_at.desc(), ClassAIAnalysisRun.id.desc()).first()

    def generate(self, course, *, requested_by=None, force=False, allow_legacy=True, legacy_compatibility=True):
        source_cutoff = dt.datetime.utcnow()
        packet = build_class_lesson4_packet(course, source_cutoff=source_cutoff)
        configuration, configuration_error = self._resolve_configuration(course, allow_legacy=allow_legacy)
        # Teacher requests include source/group/revision in their hash, which
        # invalidates completed and fallback reports after credential/model/
        # pause changes. Direct legacy compatibility keeps its former hash.
        identity = self._identity_for(configuration, course, legacy_compatibility=legacy_compatibility)
        input_hash = self.input_hash(packet, configuration, identity)
        latest = ClassAIAnalysisRun.query.filter_by(
            course_id=course.id, scope_code=SCOPE_CODE, input_hash=input_hash, status="completed"
        )
        if identity is not None:
            latest = latest.filter(
                ClassAIAnalysisRun.ai_key_group_id == identity["group_id"],
                ClassAIAnalysisRun.ai_config_revision == identity["config_revision"],
                ClassAIAnalysisRun.ai_credential_source == identity["source"],
                ClassAIAnalysisRun.provider == identity["provider"],
                ClassAIAnalysisRun.model_name == identity["model_name"],
            )
        latest = latest.order_by(
            ClassAIAnalysisRun.created_at.desc(), ClassAIAnalysisRun.id.desc()
        ).first()
        if latest and not force:
            return latest, True, packet
        active = self._active_run(course, input_hash)
        if active:
            return active, True, packet
        run, coalesced = self._new_run(course, packet, input_hash, requested_by, source_cutoff, configuration, identity)
        if coalesced:
            return run, True, packet
        omitted_for_ai = self._omitted_event_count(packet)

        if configuration_error:
            run.status = "failed"
            run.analysis_source = "ai_api"
            run.error_message = self._safe_error(configuration_error)
            run.completed_at = dt.datetime.utcnow()
            run.active_key = None
            db.session.commit()
            return run, False, packet

        if not configuration:
            run.status = "failed"
            run.analysis_source = "ai_api"
            run.error_message = "Chưa cấu hình API AI cho giáo viên phụ trách lớp này. Vui lòng thêm khóa AI trong Cài đặt AI."
            run.completed_at = dt.datetime.utcnow()
            run.active_key = None
            db.session.commit()
            return run, False, packet

        try:
            ai_result = self._run_ai(packet, configuration)
            # Server-owned observed events and coverage are always retained;
            # only validated hypotheses/recommendations come from the model.
            result = deterministic_class_report(packet)
            result["class_summary"]["ai_summary"] = ai_result["class_summary"]["ai_summary"]
            result["class_summary"]["cause_hypotheses"] = ai_result["class_summary"]["cause_hypotheses"]
            result["class_summary"]["next_risk_hypotheses"] = ai_result["class_summary"]["next_risk_hypotheses"]
            result["class_summary"]["recommendations"] = ai_result["class_summary"]["recommendations"] or result["class_summary"]["recommendations"]
            ai_by_student = ai_result["students"]
            for student in result["students"]:
                ai_student = ai_by_student.get(student["student_ref"])
                if ai_student is not None:
                    student["ai_summary"] = ai_student["ai_summary"]
                    student["cause_hypotheses"] = ai_student["cause_hypotheses"]
                    student["next_risk_hypotheses"] = ai_student["next_risk_hypotheses"]
                    student["recommendations"] = ai_student["recommendations"] or student["recommendations"]
            status, source, error = "completed", "ai_api", None
        except Exception as exc:
            error = self._safe_error(exc)
            status, source = "failed", "ai_api"
            result = {"error": error, "class_summary": None, "students": []}

        result["coverage"] = {
            **packet.get("coverage", {}),
            "ai_batch_size": self.batch_size,
            "ai_max_events_per_student": self.max_events_per_student,
            "events_omitted_for_ai": omitted_for_ai,
        }
        result["analysis_source"] = source
        result["provider_status"] = status
        result["model_name"] = (
            configuration.model_name if configuration
            else (identity or {}).get("model_name", self.model)
        )
        result["prompt_version"] = PROMPT_VERSION
        run.status = status
        run.analysis_source = source
        run.response_data = _canonical_json(result)
        run.omitted_event_count = omitted_for_ai
        run.error_message = error
        run.completed_at = dt.datetime.utcnow()
        run.retry_after = None
        run.active_key = None
        db.session.commit()
        return run, False, packet

    def present(self, run, course, packet=None, *, allow_legacy=None, legacy_compatibility=None):
        """Return a teacher-facing copy with token-to-roster mapping.

        Names and user codes are added only after the stored/API packet has
        been validated; they never enter the external request.
        """
        if packet is None:
            packet = build_class_lesson4_packet(course)
        # HTTP readers pass their exact policy flags.  Keep direct service
        # callers backward compatible unless they explicitly request this
        # freshness assertion.
        if allow_legacy is not None and legacy_compatibility is not None:
            configuration, _ = self._resolve_configuration(course, allow_legacy=allow_legacy)
            identity = self._identity_for(
                configuration, course, legacy_compatibility=legacy_compatibility
            )
            if run.input_hash != self.input_hash(packet, configuration, identity):
                return {
                    "id": run.id,
                    "status": "stale",
                    "stale": True,
                    "review_status": run.review_status or "unreviewed",
                    "report": None,
                    "coverage": packet.get("coverage", {}),
                }
        data = deepcopy(run.get_response_data())
        ref_to_student = {
            _stable_student_ref(course.id, enrollment.student_id): enrollment.student
            for enrollment in Enrollment.query.filter_by(course_id=course.id, status="active").all()
            if enrollment.student and enrollment.student.role == "student"
        }
        exam_q_ids = set()
        for student in data.get("students", []):
            for ev in student.get("observed_events", []):
                qid = ev.get("question_id")
                if qid:
                    exam_q_ids.add(qid)
        q_pos_map = {}
        if exam_q_ids:
            from models import ExamQuestion
            for q in ExamQuestion.query.filter(ExamQuestion.id.in_(list(exam_q_ids))).all():
                if getattr(q, "order_index", None) is not None:
                    q_pos_map[q.id] = q.order_index + 1

        for student in data.get("students", []):
            token = student.get("student_ref")
            person = ref_to_student.get(token)
            if person:
                student["student_id"] = person.id
                student["display_name"] = person.fullname
                student["user_code"] = person.user_code
            else:
                student["display_name"] = "Học sinh không còn trong roster"
            for ev in student.get("observed_events", []):
                ev["skill_name"] = SKILL_NAMES.get(ev.get("curriculum_code"), ev.get("curriculum_code", ""))
                if ev.get("question_id") in q_pos_map:
                    ev["question_position"] = q_pos_map[ev["question_id"]]
            for ev in student.get("observed_errors", []):
                ev["skill_name"] = SKILL_NAMES.get(ev.get("curriculum_code"), ev.get("curriculum_code", ""))
                if ev.get("question_id") in q_pos_map:
                    ev["question_position"] = q_pos_map[ev["question_id"]]
            for ev in student.get("observed_progress", []):
                ev["skill_name"] = SKILL_NAMES.get(ev.get("curriculum_code"), ev.get("curriculum_code", ""))
                if ev.get("question_id") in q_pos_map:
                    ev["question_position"] = q_pos_map[ev["question_id"]]
            for item in student.get("next_risk_hypotheses", []):
                item["skill_name"] = SKILL_NAMES.get(item.get("skill"), item.get("skill", ""))
            for item in student.get("recommendations", []):
                if isinstance(item, dict):
                    item["skill_name"] = SKILL_NAMES.get(item.get("skill"), item.get("skill", ""))
        token_to_name = {
            token: person.fullname
            for token, person in ref_to_student.items()
        }
        summary = data.get("class_summary") or {}
        for item in summary.get("observed_errors", []):
            item["skill_name"] = SKILL_NAMES.get(item.get("skill"), item.get("skill", ""))
        for item in summary.get("observed_progress_recovery", []):
            item["skill_name"] = SKILL_NAMES.get(item.get("skill"), item.get("skill", ""))
        for item in summary.get("next_risk_hypotheses", []):
            item["skill_name"] = SKILL_NAMES.get(item.get("skill"), item.get("skill", ""))
        for item in summary.get("recommendations", []):
            item["skill_name"] = SKILL_NAMES.get(item.get("skill"), item.get("skill", ""))
        for section in (summary.get("observed_errors", []), summary.get("next_risk_hypotheses", [])):
            for item in section:
                item["affected_students"] = [
                    {"student_ref": token, "display_name": token_to_name.get(token, "Học sinh không còn trong roster")}
                    for token in item.get("affected_student_refs", [])
                ]
        presented = {
            "id": run.id,
            "status": run.status,
            "analysis_source": run.analysis_source,
            "provider": run.provider,
            "model_name": run.model_name,
            "prompt_version": run.prompt_version,
            "input_hash": run.input_hash,
            "source_cutoff": _iso(run.source_cutoff),
            "generated_at": _iso(run.completed_at or run.created_at),
            "review_status": run.review_status or "unreviewed",
            "reviewed_at": _iso(run.reviewed_at),
            "review_note": run.review_note,
            "error_message": run.error_message,
            "cached": False,
            "report": data,
            "coverage": {
                "roster_count": run.roster_count,
                "event_count": run.event_count,
                "omitted_event_count": run.omitted_event_count,
                **(data.get("coverage") or packet.get("coverage", {})),
            },
            "skill_names": SKILL_NAMES,
        }
        # Keep the metadata envelope while exposing the core report keys at
        # the same level for simple API clients and template integrations.
        for key in ("schema_version", "scope", "class_summary", "students", "limitations"):
            if key in data:
                presented[key] = data[key]
        return presented


__all__ = [
    "ClassLesson4ReportService",
    "LESSON4_SCOPE",
    "PROMPT_VERSION",
    "SCOPE_CODE",
    "build_class_lesson4_packet",
    "deterministic_class_report",
    "packet_fingerprint",
    "validate_class_report",
]


def present_observed_report(course, packet):
    """Read-only facts remain available independently of the AI provider."""
    data = deterministic_class_report(packet)
    roster = {_stable_student_ref(course.id, e.student_id): e.student
              for e in Enrollment.query.filter_by(course_id=course.id, status='active').all()
              if e.student and e.student.role == 'student'}
    for row in data['students']:
        person = roster.get(row['student_ref'])
        if person:
            row.update(student_id=person.id, display_name=person.fullname)
    data['skill_names'] = SKILL_NAMES
    return data
