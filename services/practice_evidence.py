"""Derived atomic learning evidence, separate from the non-linear exam score.

Frozen answers/metadata are the source of truth. Nothing is backfilled into old
grades; four statements share one parent-item evidence budget.
"""
from types import SimpleNamespace
from datetime import datetime

from services.personalization_evidence import answer_status, is_finalized
from services.practice_blueprint import SKILLS, LEVELS, metadata


def statement_results(answer):
    question = answer.question
    if question.question_type not in ("true_false", "truefalse"):
        return []
    payload = answer.get_answer_payload()
    if not isinstance(payload, dict):
        return []
    tags = metadata(question).get("statements", [])
    result = []
    for index, expected in enumerate(sorted(question.answers, key=lambda item: item.id)):
        tag = tags[index] if index < len(tags) and isinstance(tags[index], dict) else {}
        actual = payload.get(str(expected.id))
        answered = isinstance(actual, bool)
        result.append(dict(statement_id=expected.id, label="abcd"[index] if index < 4 else str(index + 1),
                           curriculum_code=tag.get("curriculum_code"), cognitive_level=tag.get("cognitive_level"),
                           actual=actual if answered else None, expected=bool(expected.is_correct),
                           status="answered" if answered else "unanswered",
                           correct=(actual == bool(expected.is_correct)) if answered else None))
    return result


def learning_rows(submissions):
    result = []
    exposures = {}
    for submission in sorted(submissions, key=lambda s: (s.submitted_at or datetime.min, s.id)):
        if not is_finalized(submission) or getattr(getattr(submission, 'exam', None), 'assessment_purpose', None) == 'standalone':
            continue
        for answer in submission.answers:
            if answer_status(answer) not in ("answered", "graded") or not answer.question:
                continue
            question = answer.question
            identity = question.source_content_hash or (
                ('bank', question.bank_question_id) if question.bank_question_id else ('exam', question.id))
            previous = exposures.setdefault(identity, set())
            repeat_weight = 1. / (1. + len(previous))
            previous.add(submission.id)
            base = dict(submission_id=submission.id, occurred_at=submission.submitted_at,
                        question_content_hash=question.source_content_hash,
                        bank_question_id=question.bank_question_id, exam_question_id=question.id)
            if question.question_type in ("true_false", "truefalse"):
                # No parent-label fallback: mixed statements cannot safely inherit it.
                for row in statement_results(answer):
                    if row["status"] == "answered" and row["curriculum_code"] in SKILLS and row["cognitive_level"] in LEVELS:
                        result.append(SimpleNamespace(**base, curriculum_code=row["curriculum_code"],
                            cognitive_level=row["cognitive_level"], normalized_score=float(row["correct"]),
                            evidence_weight=.25 * repeat_weight))
            elif question.curriculum_code in SKILLS and question.difficulty_level in LEVELS:
                result.append(SimpleNamespace(**base, curriculum_code=question.curriculum_code,
                    cognitive_level=question.difficulty_level,
                    normalized_score=max(0., min(1., (answer.points_earned or 0) / question.points)) if question.points else 0.,
                    evidence_weight=repeat_weight))
    return result


def practice_skill_matrix(rows):
    """Return all 8×4 cells, preserving ``unknown`` as no evidence.

    The selector keeps its sparse matrix for backwards-compatible audit
    payloads.  Student/teacher profiles need a complete grid so an untested
    cell is visibly different from a weak one.
    """
    from services import aptga

    observed = aptga.matrix(rows)
    empty = aptga.summarize([])
    return {
        f"{skill}||{level}": dict(observed.get(f"{skill}||{level}", empty))
        for skill in SKILLS for level in LEVELS
    }
