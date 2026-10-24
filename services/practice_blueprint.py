"""Versioned 22-item practice contract. No database access or implicit AI labels."""
from __future__ import annotations

import json
import re
from fractions import Fraction

from services.curriculum_data import (
    CHAPTER8_CODE,
    CHAPTER8_GRADE,
    RETAINED_LESSON_CODE,
)

VERSION = "practice-22-v1"
TOTAL = 22
# Both a common initial diagnostic and each newly generated fixed practice
# paper use this contract.  Historical papers keep their persisted duration.
DURATION_MINUTES = 40
SKILLS = tuple(f"{CHAPTER8_GRADE}C{CHAPTER8_CODE}-{RETAINED_LESSON_CODE}-{i}" for i in range(1, 9))
LEVELS = ("nhan_biet", "thong_hieu", "van_dung", "van_dung_cao")
TYPE_QUOTAS = {"single": 12, "true_false": 4, "short_answer": 6}
POINTS = {"single": .25, "true_false": 1., "short_answer": .5}
TYPE_LABELS = {"single": "Chọn đáp án", "true_false": "Đúng/Sai", "short_answer": "Trả lời ngắn"}
TF_POINTS = (0., .1, .25, .5, 1.)


def metadata(question):
    try:
        value = json.loads(getattr(question, "learning_metadata", None) or "{}")
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def numeric_value(text):
    """Bounded decimal/fraction parser; never executes input or guesses units."""
    value = str(text).strip().replace(",", ".")
    if len(value) > 80 or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:/[+-]?\d+(?:\.\d+)?)?", value):
        raise ValueError("Đáp án phải là số hoặc phân số, không kèm đơn vị.")
    try:
        parts = value.split("/")
        return Fraction(parts[0]) / Fraction(parts[1]) if len(parts) == 2 else Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Phân số không hợp lệ.") from exc


def validate_metadata(value):
    if not isinstance(value, dict):
        raise ValueError("Thông tin cá nhân hóa phải là một đối tượng.")
    result = {}
    if "statements" in value:
        items = value["statements"]
        if not isinstance(items, list) or len(items) != 4:
            raise ValueError("Cần nhãn kỹ năng cho đúng 4 ý Đúng/Sai.")
        result["statements"] = []
        for item in items:
            if not isinstance(item, dict) or item.get("curriculum_code") not in SKILLS or item.get("cognitive_level") not in LEVELS:
                raise ValueError("Mỗi ý phải có dạng kiến thức bài kết hợp 25 + 26 và mức nhận thức hợp lệ.")
            result["statements"].append({key: item[key] for key in ("curriculum_code", "cognitive_level")})
    if "short_answer" in value:
        rule = value["short_answer"]
        if not isinstance(rule, dict) or rule.get("mode") not in ("numeric", "text"):
            raise ValueError("Câu trả lời ngắn phải chọn cách chấm tự động: số hoặc văn bản.")
        tolerance = numeric_value(rule.get("tolerance", "0"))
        if tolerance < 0 or tolerance > 1:
            raise ValueError("Sai số tuyệt đối phải từ 0 đến 1.")
        result["short_answer"] = {"mode": rule["mode"], "tolerance": str(tolerance)}
    return result


def readiness_error(question):
    """Stricter than legacy readiness: new papers require reviewed evidence labels."""
    if getattr(question, "classification_status", None) != "teacher_confirmed":
        return "Phân loại chưa được giáo viên xác nhận"
    node = question.curriculum_node
    if not node or node.canonical_code not in SKILLS or not node.is_active:
        return "Chưa gắn dạng kiến thức bài kết hợp 25 + 26 hợp lệ"

    if question.difficulty_level not in LEVELS or question.question_type not in TYPE_QUOTAS:
        return "Loại câu hoặc mức nhận thức không hợp lệ"
    try:
        data = validate_metadata(metadata(question))
        if question.question_type == "true_false":
            if len(question.options) != 4:
                return "Đúng/Sai phải có đúng 4 ý"
            if len(data.get("statements", [])) != 4:
                return "Đúng/Sai chưa được giáo viên gắn nhãn cho 4 ý"
        if question.question_type == "short_answer":
            rule = data.get("short_answer")
            if not rule:
                return "Trả lời ngắn chưa có quy tắc chấm"
            if rule["mode"] == "numeric":
                for option in question.options:
                    if option.is_correct:
                        numeric_value(option.option_text)
    except ValueError as exc:
        return str(exc)
    auto_error = auto_scoring_error(question)
    if auto_error:
        return auto_error
    return None


def auto_scoring_error(question):
    """Return a blocking error when a frozen item cannot be auto-graded.

    This is intentionally separate from curriculum/classification readiness so
    historical papers can remain readable while new papers fail closed.
    """
    q_type = {"truefalse": "true_false"}.get(
        str(getattr(question, "question_type", "") or "").strip(),
        getattr(question, "question_type", ""),
    )
    answers = list(getattr(question, "answers", None) or getattr(question, "options", None) or [])
    if q_type not in TYPE_QUOTAS:
        return "Loại câu hỏi này không được chấm tự động."
    if not answers:
        return "Câu hỏi chưa có đáp án để chấm tự động."
    if q_type == "single" and sum(answer.is_correct is True for answer in answers) != 1:
        return "Trắc nghiệm phải có đúng một đáp án đúng."
    if q_type == "true_false" and any(answer.is_correct is None for answer in answers):
        return "Đúng/Sai phải có đáp án cho đủ các mệnh đề."
    if q_type != "short_answer":
        return None
    try:
        rule = metadata(question).get("short_answer", {})
        if not isinstance(rule, dict) or rule.get("mode") not in ("numeric", "text"):
            return "Trả lời ngắn chưa có quy tắc chấm tự động hợp lệ."
        tolerance = numeric_value(rule.get("tolerance", "0"))
        if tolerance < 0 or tolerance > 1:
            return "Sai số tuyệt đối phải từ 0 đến 1."
        accepted = [str(getattr(answer, "answer_text", None) or getattr(answer, "option_text", "")).strip()
                    for answer in answers
                    if answer.is_correct is True
                    and str(getattr(answer, "answer_text", None) or getattr(answer, "option_text", "")).strip()]
        if not accepted:
            return "Trả lời ngắn chưa có đáp án đúng hợp lệ."
        if rule["mode"] == "numeric":
            for value in accepted:
                numeric_value(value)
    except (TypeError, ValueError) as exc:
        return str(exc)
    return None


def grade_short(text, accepted, rule, has_file=False):
    """Return ``(correct, status)`` for an auto-graded short answer.

    Invalid learner input is a scored wrong answer. Invalid authoring data is
    a hard error and therefore cannot become a pending manual review.
    """
    text = text.strip()
    if has_file:
        raise ValueError("Tệp bài làm không được hỗ trợ; hãy nhập câu trả lời bằng văn bản.")
    mode = rule.get("mode") if isinstance(rule, dict) else None
    if mode not in ("numeric", "text"):
        raise ValueError("Câu trả lời ngắn chưa có quy tắc chấm tự động hợp lệ.")
    accepted = [str(key).strip() for key in accepted if str(key).strip()]
    if not accepted:
        raise ValueError("Câu trả lời ngắn chưa có đáp án đúng hợp lệ.")
    try:
        tolerance = numeric_value(rule.get("tolerance", "0"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Sai số tuyệt đối không hợp lệ.") from exc
    if tolerance < 0 or tolerance > 1:
        raise ValueError("Sai số tuyệt đối phải từ 0 đến 1.")
    expected = []
    if mode == "numeric":
        try:
            expected = [numeric_value(key) for key in accepted]
        except ValueError as exc:
            raise ValueError("Đáp án số lưu trong câu hỏi không hợp lệ.") from exc
    if not text:
        return False, "unanswered"
    if mode == "numeric":
        try:
            actual = numeric_value(text)
            return any(abs(actual - key) <= tolerance for key in expected), "answered"
        except ValueError:
            # The learner's malformed number is an answered, wrong response;
            # it must never trigger a teacher-review state.
            return False, "answered"
    if mode == "text":
        return text.casefold() in {key.strip().casefold() for key in accepted}, "answered"
    raise ValueError("Câu trả lời ngắn chưa có quy tắc chấm tự động hợp lệ.")


def is_fixed(exam):
    return exam.get_adaptive_metadata().get("aptga", {}).get("version") == VERSION
