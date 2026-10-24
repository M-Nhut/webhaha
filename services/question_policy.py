"""One write policy for bank questions, imports and newly authored exams.

The import pipeline has three public answer formats.  Older files can still
contain the former essay labels; those labels are deliberately normalised to
``short_answer`` so an import never gets stuck on a format that the bank no
longer exposes.
"""

import re
import unicodedata

# ID6 type letters follow one single standard:
# T = single (Trắc nghiệm), D = true_false (Đúng/Sai THPT), S = short_answer (Trả lời ngắn).
# The internal question_type enum ('single', 'true_false', 'short_answer') remains independent.
TYPE_CODES = {"single": "T", "true_false": "D", "short_answer": "S"}
QUESTION_TYPE_BY_CODE = {"T": "single", "D": "true_false", "S": "short_answer"}
TYPE_LABELS = {"single": "Trắc nghiệm", "true_false": "Đúng/Sai THPT", "short_answer": "Trả lời ngắn"}
LEGACY_TYPE_LABELS = {
    "multiple_choice": "Nhiều đáp án (không còn hỗ trợ)",
    "multi": "Nhiều đáp án (không còn hỗ trợ)",
    "essay": "Tự luận → Trả lời ngắn",
    "tu_luan": "Tự luận → Trả lời ngắn",
}

_ESSAY_ALIASES = frozenset({
    "essay",
    "tu_luan",
    "tu luan",
    "tự luận",
    "bài tập tự luận",
    "bai tap tu luan",
    "tự luận mở",
    "tu luan mo",
    "tự luận cũ",
    "tu luan cu",
    "tu_luan_cu",
    "tự luận (dữ liệu cũ)",
    "tu luan (du lieu cu)",
    "long answer",
    "long_answer",
    "free response",
    "free_response",
})


def id6_type_code(question_type, **kwargs):
    """Return the ID6 letter for an internal type under the single contract."""
    kind = canonical_type(question_type)
    return TYPE_CODES.get(kind)


def id6_question_type(type_code, **kwargs):
    """Decode one ID6 type letter (T=single, D=true_false, S=short_answer)."""
    code = str(type_code or "").strip().upper()
    return QUESTION_TYPE_BY_CODE.get(code)



def _type_key(value):
    """Return a stable comparison key for Vietnamese/English type labels."""
    if value is None:
        return ""
    text = " ".join(str(value).strip().lower().split())
    text = re.sub(r"\s*([()/])\s*", r"\1", text)
    # Keep the accented form for exact aliases, then also compare a plain
    # ASCII form so ``tu_luan`` and ``tự luận`` follow the same path.
    plain = "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    return text, plain


def canonical_type(value):
    """Map all accepted aliases to one of the three public type codes.

    ``essay``/``tu_luan`` are intentionally mapped to short answer.  This is
    used by both new previews and old preview sessions loaded from the
    database, so users do not have to repair historical files manually.
    """
    text, plain = _type_key(value)
    if (
        text in _ESSAY_ALIASES
        or plain in _ESSAY_ALIASES
        or "essay" in text
        or "tự luận" in text
        or "tu luan" in plain
    ):
        return "short_answer"
    if text in {
        "truefalse", "true false", "true/false", "true_false",
        "đúng/sai", "đúng sai", "đúng/sai thpt", "dung/sai", "dung sai",
    } or plain in {
        "truefalse", "true false", "true/false", "true_false",
        "dung/sai", "dung sai", "dung/sai thpt",
    }:
        return "true_false"
    if text in {"single", "mc", "trắc nghiệm", "một đáp án", "một lựa chọn"} or plain in {
        "single", "mc", "trac nghiem", "mot dap an", "mot lua chon",
    }:
        return "single"
    if text in {"short_answer", "short answer", "trả lời ngắn", "điền đáp án"} or plain in {
        "short_answer", "short answer", "tra loi ngan", "dien dap an",
    }:
        return "short_answer"
    return value


def is_legacy_essay_type(value):
    """Whether ``value`` is an old essay label that will be migrated."""
    text, plain = _type_key(value)
    return text in _ESSAY_ALIASES or plain in _ESSAY_ALIASES


def require_supported_type(value, *, allow_legacy=False):
    """Validate a type at a write boundary.

    Import previews may explicitly opt into converting historical essay labels
    to the supported short-answer format.  Authoring and update APIs must not
    silently create a legacy type, so they use the strict default.
    """
    if not allow_legacy and is_legacy_essay_type(value):
        raise ValueError("Loại Tự luận cũ không còn được tạo mới; hãy chọn Trả lời ngắn.")
    value = canonical_type(value)
    if value not in TYPE_CODES:
        raise ValueError("Chỉ nhận Trắc nghiệm, Đúng/Sai THPT và Trả lời ngắn. Hãy chuyển câu sang hình thức hợp lệ hoặc loại khỏi lô nhập.")
    return value


def answer_issues(question, require_answers=False):
    """Return structural errors and incomplete-answer warnings, without mutation."""
    errors, warnings = [], []
    kind = canonical_type(question.get("question_type"))
    try:
        require_supported_type(kind)
    except ValueError as exc:
        return [str(exc)], []
    options = question.get("options") or []
    statements = question.get("statements") or []
    if not isinstance(options, list) or not isinstance(statements, list):
        return ["Danh sách đáp án không hợp lệ."], []
    if not all(isinstance(item, dict) for item in options + statements):
        return ["Dữ liệu từng đáp án không hợp lệ."], []
    def content(item):
        return str(item.get("text") or item.get("option_text") or "").strip()
    if kind == "single":
        if len(options) != 4 or any(not content(item) for item in options):
            errors.append("Trắc nghiệm cần đủ 4 phương án A, B, C, D.")
        correct = sum(item.get("is_correct") is True for item in options)
        if correct > 1:
            errors.append("Trắc nghiệm chỉ có một đáp án đúng.")
        elif correct == 0:
            warnings.append("Chưa chọn đáp án đúng; câu chỉ có thể lưu nháp.")
        if any(item.get("is_correct") is not None and not isinstance(item.get("is_correct"), bool) for item in options):
            errors.append("Đáp án đúng phải là giá trị đúng/sai hợp lệ.")
    elif kind == "true_false":
        if len(statements) != 4 or any(not content(item) for item in statements):
            errors.append("Đúng/Sai THPT cần đủ 4 mệnh đề a, b, c, d.")
        if any(item.get("answer") is None for item in statements):
            warnings.append("Chưa chọn Đúng/Sai cho đủ 4 ý; câu chỉ có thể lưu nháp.")
        if any(item.get("answer") is not None and not isinstance(item.get("answer"), bool) for item in statements):
            errors.append("Đáp án mỗi mệnh đề phải là Đúng hoặc Sai.")
    elif not options or any(not content(item) for item in options) or not any(item.get("is_correct") is True for item in options):
        warnings.append("Trả lời ngắn cần đáp án mẫu; câu chỉ có thể lưu nháp.")
    if require_answers:
        errors.extend(warnings)
        warnings = []
    return errors, warnings


def require_valid_answers(question):
    errors, _ = answer_issues(question, require_answers=True)
    if errors:
        raise ValueError(" ".join(errors))


def bank_question_ready(question):
    if not question.question_text.strip():
        return False
    errors, _ = answer_issues(question.to_dict(), require_answers=True)
    return not errors


def clean_latex_math_to_text(s):
    """Normalize simple LaTeX math (fractions, spaces, delimiters) to plain text."""
    if not s:
        return ""
    text = str(s).strip()
    text = text.strip("$").strip()
    text = re.sub(r"\\\(|\\\)|\\\[|\\\]", "", text)
    # Convert \dfrac{a}{b} or \frac{a}{b} to a/b
    text = re.sub(r"\\(?:d?frac)\{([^{}]+)\}\{([^{}]+)\}", r"\1/\2", text)
    # Convert LaTeX spaces
    text = re.sub(r"\\(?:\s|,|;|:|!)", " ", text)
    # Strip text commands
    text = re.sub(r"\\(?:text|mathrm|textbf|mathbf)\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def resolve_formula_to_text(s):
    """Resolve any [[formula:<uuid>]] placeholders using FormulaAsset, then normalize to text."""
    if not s:
        return ""
    if isinstance(s, dict):
        s = s.get("text") or s.get("accepted_text") or ""
        if isinstance(s, list):
            s = " / ".join(str(item) for item in s)
    elif isinstance(s, (list, tuple, set)):
        s = " / ".join(str(item) for item in s)
    text = str(s)
    if "[[formula:" in text:
        from extensions import db
        from models import FormulaAsset
        def replacer(match):
            fid = match.group(1)
            try:
                fa = db.session.get(FormulaAsset, fid)
                if fa and fa.latex:
                    return clean_latex_math_to_text(fa.latex)
                if fa and fa.source_text:
                    return clean_latex_math_to_text(fa.source_text)
            except Exception:
                pass
            return ""
        text = re.sub(r"\[\[formula:([0-9a-fA-F-]+)\]\]", replacer, text)
    return clean_latex_math_to_text(text)

