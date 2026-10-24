"""
Question Validator — Validates normalized questions before import.
Checks for errors, warnings, and potential duplicates.
"""

import re
from services.question_policy import answer_issues, canonical_type
from services.question_normalizer import (
    VALID_DIFFICULTIES,
    normalize_text, remove_diacritics
)


def _simplify_for_compare(text):
    """Simplify text for duplicate comparison: lowercase, no diacritics, no extra spaces."""
    if not text:
        return ""
    text = remove_diacritics(text.lower().strip())
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _similarity_ratio(a, b):
    """Simple character-level similarity ratio between two strings."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    a_set = set(a.split())
    b_set = set(b.split())
    if not a_set or not b_set:
        return 0.0
    intersection = a_set & b_set
    union = a_set | b_set
    return len(intersection) / len(union) if union else 0.0


def validate_question(question, existing_texts=None):
    """
    Validate a single normalized question.
    Adds errors and warnings in-place to the question dict.
    Updates 'status' to 'error' if critical issues found.
    """
    errors = []
    warnings = []
    q_type = canonical_type(question.get("question_type", "single"))
    # Validation is also used when reopening old import sessions.  Canonicalise
    # the type here so legacy essay rows are migrated even if they predate the
    # current normalizer.
    question["question_type"] = q_type
    options = question.get("options", [])
    statements = question.get("statements", [])

    # ──── ERROR checks ────

    # 1. Empty question text
    if not normalize_text(question.get("question_text", "")):
        errors.append("Câu hỏi không có nội dung")

    policy_errors, policy_warnings = answer_issues(question)
    errors.extend(policy_errors)
    warnings.extend(policy_warnings)
    errors.extend(question.get("scope_errors") or [])
    diff = question.get("difficulty_level", "")
    if diff and diff not in VALID_DIFFICULTIES:
        errors.append("Mức độ không hợp lệ; chọn NB, TH, VD hoặc VDC.")

    # ──── WARNING checks ────

    # 8. Duplicate check
    if existing_texts:
        simplified = _simplify_for_compare(question.get("question_text", ""))
        if simplified:
            for existing in existing_texts:
                ratio = _similarity_ratio(simplified, existing)
                if ratio > 0.85:
                    warnings.append("Có thể trùng với câu hỏi đã tồn tại trong ngân hàng")
                    break

    # Formula warnings
    formulas = question.get("formulas", {})
    from services.tex_table import display_asset
    formulas = {key: display_asset(value) for key, value in formulas.items()}
    question['formulas'] = formulas
    if any(f.get('needs_review') or f.get('conversion_status') in ('failed', 'pending')
           or not (f.get('mathml') or f.get('latex') or f.get('table') or f.get('preview_url') or f.get('svg_cache_key'))
           for f in formulas.values()):
        warnings.append("Có công thức phức tạp hoặc bị lỗi cấu trúc, cần giáo viên xem xét lại.")

    # 9. Points validation
    points = question.get("points", 1.0)
    if points <= 0:
        warnings.append(f"Điểm số ({points}) không hợp lệ, nên > 0")

    # 10. Low Confidence score warning
    conf = question.get("confidence_scores", {})
    if conf and isinstance(conf, dict):
        min_conf = min(conf.values()) if conf.values() else 1.0
        if min_conf < 0.6:
            warnings.append(f"Độ tin cậy trích xuất thấp ({int(min_conf*100)}%), cần giáo viên kiểm tra kỹ")

    # ──── Update status ────
    question["errors"] = errors
    question["warnings"] = warnings

    if errors:
        question["status"] = "error"
    elif warnings:
        question["status"] = "warning"
    else:
        question["status"] = "valid"

    return question


def validate_questions(questions, existing_bank_questions=None):
    """
    Validate a list of normalized questions.
    
    Args:
        questions: list of normalized question dicts
        existing_bank_questions: list of BankQuestion objects already in the bank
    
    Returns:
        dict with {
            'questions': validated list,
            'stats': {total, valid, warning, error}
        }
    """
    # Build set of existing question texts for duplicate detection
    existing_texts = set()
    if existing_bank_questions:
        for bq in existing_bank_questions:
            existing_texts.add(_simplify_for_compare(bq.question_text))

    # Also check within the import batch itself
    seen_texts = set()

    for q in questions:
        # Check for duplicates within the batch
        simplified = _simplify_for_compare(q.get("question_text", ""))
        if simplified and simplified in seen_texts:
            q.setdefault("warnings", []).append("Trùng lặp với câu hỏi khác trong cùng file import")
        elif simplified:
            seen_texts.add(simplified)

        validate_question(q, existing_texts)

    stats = {
        "total": len(questions),
        "valid": sum(1 for q in questions if q["status"] == "valid"),
        "warning": sum(1 for q in questions if q["status"] == "warning"),
        "error": sum(1 for q in questions if q["status"] == "error"),
    }

    return {"questions": questions, "stats": stats}
