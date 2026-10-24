"""Read-only exam evidence. Never writes to adaptive learning history."""
import json
from types import SimpleNamespace
from services.personalization_evidence import answer_status, is_finalized


def assessment_rows(submissions):
    rows = []
    for submission in submissions:
        if submission.exam.assessment_purpose != 'standalone' or not is_finalized(submission):
            continue
        for answer in submission.answers:
            question = answer.question
            reporting = json.loads(question.learning_metadata or '{}').get('reporting', {})
            if not reporting.get('confirmed') or not question.curriculum_code:
                continue
            rows.append(SimpleNamespace(submission_id=submission.id, student_id=submission.student_id,
                exam_question_id=question.id, submission_answer_id=answer.id,
                curriculum_code=question.curriculum_code, answer_status=answer_status(answer),
                evidence_ref=f'submission:{submission.id}:answer:{answer.id}:revision:{submission.grading_revision or 0}',
                is_correct=answer.is_correct, grading_revision=submission.grading_revision,
                occurred_at=submission.submitted_at))
    return rows


