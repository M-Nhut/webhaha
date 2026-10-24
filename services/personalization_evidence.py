"""Evidence and reporting primitives for learner personalization.

The module intentionally keeps one source of truth for learner evidence:
``SubmissionAnswer`` stores the learner's answer and ``ExamQuestion`` plus
``ExamAnswer`` store the frozen item/key.  LearningHistory and error profiles
only reference that evidence; they do not copy it into every aggregate row.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import defaultdict

from sqlalchemy import event
from sqlalchemy.orm import Session

from database import db
from models import (
    BankQuestion,
    BankQuestionOption,
    ErrorObservation,
    ExamQuestion,
    ExamSubmission,
    StudentErrorProfile,
    SubmissionAnswer,
    TeacherLearningReport,
)
from services.question_policy import TYPE_CODES, canonical_type


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _stable_source_identity(question: BankQuestion):
    """Return the canonical ID6 identity under the single T/D/S standard."""
    source = question.source_id
    if not source:
        return source
    try:
        from services.id6_service import parse_bank_question_id6
        parsed = parse_bank_question_id6(question)
    except (ImportError, TypeError, ValueError):
        parsed = None
    if not parsed:
        return source
    kind = canonical_type(question.question_type)
    code = TYPE_CODES.get(kind)
    if not code:
        return source
    prefix = parsed["id6_prefix"][:-len(parsed["type_code"])] + code
    return prefix + (
        f".{parsed['id6_sequence']}" if parsed["id6_sequence"] is not None else ""
    )



def bank_question_content_hash(question: BankQuestion):
    """Hash editable bank content without including its mutable database id."""
    return content_hash({
        "question_text": question.question_text,
        "context": question.context or "",
        "image_url": question.image_url or "",
        "question_type": canonical_question_type(question.question_type),
        "difficulty_level": question.difficulty_level,
        "points": float(question.points or 0),
        "explanation": question.explanation or "",
        "source_id": _stable_source_identity(question),
        "learning_metadata": json.loads(question.learning_metadata or "{}"),
        "curriculum_node_id": question.curriculum_node_id,
        "options": [
            {"text": option.option_text, "is_correct": bool(option.is_correct), "order": option.order_index}
            for option in sorted(question.options, key=lambda item: (item.order_index or 0, item.id or 0))
        ],
    })


def stamp_bank_question_content(question: BankQuestion):
    """Persist a new bank revision after bulk option writes or field edits."""
    new_hash = bank_question_content_hash(question)
    if question.content_hash != new_hash:
        question.content_revision = max(1, int(question.content_revision or 1)) + (0 if not question.content_hash else 1)
        question.content_hash = new_hash
        if question.curriculum_node:
            question.catalog_version = question.curriculum_node.catalog_version
    return question.content_hash


def canonical_question_type(value):
    value = str(value or "single").strip().lower()
    return {
        "truefalse": "true_false",
        "true-false": "true_false",
        "multiple_choice": "multi",
        "multiple": "multi",
        "essay": "short_answer",
        "tu_luan": "short_answer",
        "tự luận": "short_answer",
    }.get(value, value)


def question_snapshot(question: ExamQuestion):
    """Return the frozen question/key representation used in evidence hashes."""
    answers = [
        {"id": answer.id, "text": answer.answer_text, "is_correct": bool(answer.is_correct)}
        for answer in sorted(question.answers, key=lambda row: row.id)
    ]
    return {
        "question_id": question.id,
        "source_bank_question_id": question.bank_question_id,
        "source_id6": question.source_id6,
        "source_content_revision": question.source_content_revision,
        "question_text": question.question_text,
        "context": question.context or "",
        "question_type": canonical_question_type(question.question_type),
        "difficulty_level": question.difficulty_level,
        "curriculum_code": question.curriculum_code,
        "curriculum_catalog_version": question.curriculum_catalog_version,
        "topic": question.topic_snapshot,
        "points": float(question.points or 0),
        "answers": answers,
        "learning_metadata": json.loads(question.learning_metadata or "{}"),
    }


def refresh_question_snapshot(question: ExamQuestion, bank_question=None):
    """Freeze source metadata and hash after the question's answer key exists."""
    if bank_question is not None:
        question.learning_metadata = bank_question.learning_metadata
        question.source_id6 = bank_question.source_id
        question.source_content_revision = bank_question.content_revision or 1
        question.source_content_hash = bank_question.content_hash
        node = bank_question.curriculum_node
        question.curriculum_code = node.canonical_code if node else None
        question.curriculum_catalog_version = (
            bank_question.catalog_version or (node.catalog_version if node else None)
        )
        question.topic_snapshot = bank_question.topic or (
            (node.topic_name or node.category_name) if node else None
        )
    if not question.source_content_hash:
        question.source_content_hash = content_hash(question_snapshot(question))
    return question.source_content_hash


def answer_status(answer: SubmissionAnswer):
    """Normalize legacy rows without treating blank/waiting answers as wrong."""
    payload = answer.get_answer_payload()
    question = answer.question
    if not question:
        return "unanswered"
    q_type = canonical_question_type(question.question_type)
    if q_type == "true_false":
        values = payload if isinstance(payload, dict) else {}
        return "answered" if any(value is not None for value in values.values()) else "unanswered"
    if q_type == "short_answer":
        text = str(payload.get("text") or "").strip()
        has_file = bool(payload.get("file_url"))
        try:
            metadata = json.loads(question.learning_metadata or "{}")
        except (TypeError, ValueError):
            metadata = {}
        rule = metadata.get("short_answer") if isinstance(metadata, dict) else None
        # Historical manual/file submissions remain readable, but are not
        # eligible evidence and are never interpreted as a new wrong answer.
        if (text or has_file) and (has_file or not isinstance(rule, dict) or
                                   rule.get("mode") not in ("numeric", "text")):
            return "pending_review"
        return "answered" if text else "unanswered"
    if answer.answer_status == "legacy_unknown":
        return "legacy_unknown"
    if answer.answer_status in ("answered", "pending_review", "graded", "unanswered"):
        if answer.answer_status != "unanswered":
            return answer.answer_status
        # Old rows often have the default value while holding an actual answer.
    return "answered" if answer.get_selected_ids() else "unanswered"


def is_finalized(submission: ExamSubmission):
    """Only a submitted, fully graded attempt may change learning state.

    The narrow legacy exception is for old synthetic practice rows that have a
    timestamp but no status metadata; their answer status remains unknown and
    is marked as such by callers. New routes always write ``status=graded``.
    """
    if not submission or not submission.submitted_at:
        return False
    if submission.status in ("graded", "finalized") or bool(submission.is_graded):
        return True
    # A migration-safe compatibility path for historical practice fixtures that
    # predate the status column. It does not apply to explicit submitted/pending
    # rows and never turns an unanswered item into a misconception.
    if submission.status in (None, "draft") and submission.exam_type == "practice":
        return bool(submission.answers) and all(
            answer.answer_status in (None, "unanswered", "legacy_unknown") for answer in submission.answers
        )
    return False


def is_legacy_unknown_answer(submission: ExamSubmission, answer: SubmissionAnswer):
    """Recognize pre-provenance fixtures without weakening new pending rows."""
    return bool(
        submission and submission.status in (None, "draft")
        and submission.exam_type == "practice"
        and answer.answer_status in (None, "unanswered", "legacy_unknown")
        and answer.question
        and answer.selected_answer_ids in (None, "", "[]")
    )


def actual_answer(answer: SubmissionAnswer):
    question = answer.question
    q_type = canonical_question_type(question.question_type if question else "single")
    if q_type == "true_false":
        return answer.get_answer_payload()
    if q_type == "short_answer":
        payload = answer.get_answer_payload()
        if isinstance(payload, dict) and "text" in payload:
            from services.question_policy import resolve_formula_to_text
            return {"text": resolve_formula_to_text(payload["text"])}
        return payload
    return {"selected_answer_ids": answer.get_selected_ids()}


def expected_answer(question: ExamQuestion):
    q_type = canonical_question_type(question.question_type)
    if q_type == "true_false":
        return {str(item.id): bool(item.is_correct) for item in question.answers}
    if q_type == "short_answer":
        from services.question_policy import resolve_formula_to_text
        return {
            "accepted_text": [
                resolve_formula_to_text(item.answer_text.strip())
                for item in question.answers
                if item.answer_text and (item.is_correct or item.is_correct is None)
            ]
        }
    return {"correct_answer_ids": [item.id for item in question.answers if item.is_correct]}


def evidence_ref(submission_id, answer_id, grading_revision):
    return f"submission:{submission_id}:answer:{answer_id}:revision:{grading_revision}"


def _error_for_answer(answer):
    question = answer.question
    if not question or answer_status(answer) in ("unanswered", "pending_review", "legacy_unknown"):
        return None
    if bool(answer.is_correct):
        return None
    q_type = canonical_question_type(question.question_type)
    payload = actual_answer(answer)
    if q_type == "true_false":
        code, label = "statement_mismatch", "Mệnh đề đúng/sai không khớp đáp án"
        from services.practice_evidence import statement_results
        if not any(item["correct"] is False for item in statement_results(answer)):
            return None
    elif q_type == "short_answer":
        code, label = "short_answer_mismatch", "Câu trả lời ngắn không khớp đáp án chấm"
    elif q_type == "multi":
        code, label = "choice_set_mismatch", "Tập lựa chọn không khớp đáp án"
    else:
        code, label = "choice_mismatch", "Lựa chọn không khớp đáp án"
    return {
        "error_code": code,
        "error_label": label,
        "observed_claim": "Quan sát thấy câu trả lời không khớp đáp án của câu hỏi đã đóng băng; chưa đủ bằng chứng để kết luận nguyên nhân tâm lý hay kiến thức.",
        "actual_answer": payload,
        "expected_answer": expected_answer(question),
    }


def rebuild_error_observations(submission: ExamSubmission):
    """Upsert current wrong-answer observations and supersede stale ones."""
    if not is_finalized(submission):
        return []
    subject = submission.exam.course.subject if submission.exam and submission.exam.course else ""
    active = []
    for answer in submission.answers:
        observation = _error_for_answer(answer)
        existing = ErrorObservation.query.filter_by(submission_answer_id=answer.id).all()
        if observation is None:
            for row in existing:
                row.status = "superseded"
                row.updated_at = dt.datetime.utcnow()
            continue
        ref = evidence_ref(submission.id, answer.id, submission.grading_revision or 0)
        row = next((item for item in existing if item.error_code == observation["error_code"]), None)
        if not row:
            row = ErrorObservation(
                student_id=submission.student_id,
                submission_id=submission.id,
                submission_answer_id=answer.id,
                exam_question_id=answer.question_id,
                bank_question_id=answer.question.bank_question_id,
                subject=subject,
                error_code=observation["error_code"],
                error_label=observation["error_label"],
                observed_claim=observation["observed_claim"],
                evidence_ref=ref,
            )
            db.session.add(row)
        row.curriculum_code = answer.question.curriculum_code
        row.topic = answer.question.topic_snapshot
        row.cognitive_level = answer.question.difficulty_level
        row.evidence_ref = ref
        row.confidence = 0.45
        row.status = "observed"
        row.updated_at = dt.datetime.utcnow()
        active.append(row)

    db.session.flush()
    # Recompute aggregates from active observations so regrading is idempotent.
    observations = ErrorObservation.query.filter_by(
        student_id=submission.student_id, subject=subject, status="observed"
    ).all()
    groups = defaultdict(list)
    for row in observations:
        groups[(row.curriculum_code, row.error_code)].append(row)
    profiles = StudentErrorProfile.query.filter_by(student_id=submission.student_id, subject=subject).all()
    by_key = {(row.curriculum_code, row.error_code): row for row in profiles}
    for key, rows in groups.items():
        profile = by_key.get(key)
        if not profile:
            profile = StudentErrorProfile(
                student_id=submission.student_id, subject=subject,
                curriculum_code=key[0], error_code=key[1],
            )
            db.session.add(profile)
        profile.evidence_count = len(rows)
        profile.confidence = round(min(0.9, 0.35 + len(rows) * 0.1), 4)
        profile.status = "observed"
        profile.first_observed_at = min(row.created_at for row in rows)
        profile.last_observed_at = max(row.created_at for row in rows)
        profile.updated_at = dt.datetime.utcnow()
    for key, profile in by_key.items():
        if key not in groups:
            profile.evidence_count = 0
            profile.status = "superseded"
            profile.updated_at = dt.datetime.utcnow()
    db.session.flush()
    return active


def evidence_packet(student_id, subject, course_id=None):
    from services.practice_evidence import statement_results
    """Build a teacher/AI packet with answer-level refs, excluding blanks/pending."""
    rows = ErrorObservation.query.filter_by(
        student_id=student_id, subject=subject, status="observed"
    ).order_by(ErrorObservation.created_at.desc(), ErrorObservation.id.desc()).all()
    packet = []
    for row in rows:
        answer = db.session.get(SubmissionAnswer, row.submission_answer_id)
        question = answer.question if answer else None
        submission = answer.submission if answer else None
        if not answer or not question or not submission or not is_finalized(submission):
            continue
        if course_id is not None and (not submission.exam or submission.exam.course_id != course_id):
            continue
        if answer_status(answer) in ("unanswered", "pending_review", "legacy_unknown"):
            continue
        packet.append({
            "observation_id": row.id,
            "evidence_ref": row.evidence_ref,
            "submission_id": row.submission_id,
            "answer_id": answer.id,
            "question_id": question.id,
            "question_content_hash": question.source_content_hash,
            "curriculum_code": row.curriculum_code,
            "topic": row.topic,
            "cognitive_level": row.cognitive_level,
            "error_code": row.error_code,
            "error_label": row.error_label,
            "claim": row.observed_claim,
            "actual_answer": actual_answer(answer),
            "statement_results": statement_results(answer),
            "expected_answer": expected_answer(question),
            "question_text": question.question_text,
            "grading_revision": submission.grading_revision,
        })
    return packet


def source_revision(student_id, subject, course_id=None):
    refs = [item["evidence_ref"] for item in evidence_packet(student_id, subject, course_id=course_id)]
    # Error refs alone cannot invalidate a teacher report after a new
    # all-correct finalized paper.  Include a small immutable identity for
    # every finalized in-scope 22-question diagnostic/fixed-practice attempt;
    # this remains evidence metadata, never a mastery or selection input.
    from services import practice_blueprint as blueprint

    finalized = []
    attempts = ExamSubmission.query.filter_by(student_id=student_id).order_by(
        ExamSubmission.submitted_at.desc(), ExamSubmission.id.desc()
    ).all()
    for submission in attempts:
        exam = submission.exam
        if not exam or not exam.course or exam.course.subject != subject:
            continue
        if course_id is not None and exam.course_id != course_id:
            continue
        questions = list(exam.questions)
        if len(questions) != 22 or not is_finalized(submission):
            continue
        if exam.assessment_purpose != "initial_diagnostic" and not blueprint.is_fixed(exam):
            continue
        if any(str(question.curriculum_code or "") not in blueprint.SKILLS for question in questions):
            continue
        if any(
            sum(canonical_question_type(question.question_type) == kind for question in questions) != count
            for kind, count in blueprint.TYPE_QUOTAS.items()
        ):
            continue
        finalized.append({
            "submission_id": submission.id,
            "grading_revision": int(submission.grading_revision or 0),
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        })
    return content_hash({
        "student_id": student_id,
        "subject": subject,
        "course_id": course_id,
        "evidence": refs,
        "finalized_22_submission_snapshots": finalized[:12],
    })


def upsert_teacher_report(student_id, subject, payload, generated_by=None, report_type="learning_profile", course_id=None,
                          source_revision_value=None):
    # Callers that perform a bounded external request pass the revision they
    # captured before the call.  Recomputing here after a concurrent
    # submission would incorrectly stamp an old AI snapshot as current.
    revision = source_revision_value or source_revision(student_id, subject, course_id=course_id)
    report = TeacherLearningReport.query.filter_by(
        student_id=student_id, subject=subject, report_type=report_type, source_revision=revision
    ).first()
    if not report:
        report = TeacherLearningReport(
            student_id=student_id, subject=subject, report_type=report_type,
            source_revision=revision, payload=canonical_json(payload), generated_by=generated_by,
        )
        db.session.add(report)
    else:
        report.payload = canonical_json(payload)
        report.updated_at = dt.datetime.utcnow()
    db.session.flush()
    return report


def report_payload(student_id, subject, profile, course_id=None):
    errors = evidence_packet(student_id, subject, course_id=course_id)
    by_skill = defaultdict(int)
    for row in errors:
        by_skill[row.get("curriculum_code") or row.get("topic") or "unknown"] += 1
    return {
        "schema_version": "teacher-learning-report-v1",
        "student_id": student_id,
        "course_id": course_id,
        "subject": subject,
        "observed_errors": errors,
        "observed_error_counts": dict(by_skill),
        "future_error_risks": [
            {
                "skill": skill,
                "basis_observation_count": count,
                "confidence": round(min(0.75, 0.25 + count * 0.1), 4),
                "validation": "not_validated",
                "label": "rủi ro cần theo dõi, chưa phải dự đoán đã được kiểm chứng",
            }
            for skill, count in sorted(by_skill.items(), key=lambda item: (-item[1], item[0]))
        ],
        "mastery": profile,
        "limitations": [
            "Chỉ câu đã trả lời và đã chấm mới được dùng làm bằng chứng.",
            "Một câu sai là quan sát lỗi trên câu đó, không tự động chứng minh một misconception ổn định.",
            "future_error_risks chưa được xác thực theo dữ liệu dọc và không được dùng như nhãn chắc chắn.",
        ],
    }


@event.listens_for(Session, "before_flush")
def _stamp_bank_question_content(session, flush_context, instances):
    """Advance bank revision only when editable content actually changes."""
    for question in list(session.new) + list(session.dirty):
        if not isinstance(question, BankQuestion) or question in session.deleted:
            continue
        # Do not recurse on the bookkeeping fields themselves.  The computed
        # hash includes answer options and curriculum identity, so an edit to
        # either changes the frozen-source revision for future exams.
        stamp_bank_question_content(question)
    for option in list(session.new) + list(session.dirty) + list(session.deleted):
        if isinstance(option, BankQuestionOption) and option.question:
            stamp_bank_question_content(option.question)
