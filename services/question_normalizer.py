"""
Question Normalizer — Converts parsed TeX data
into a unified schema for validation and preview.
"""

import re
import unicodedata
from services.question_policy import TYPE_CODES, canonical_type, is_legacy_essay_type


# ──────────────── DIFFICULTY MAPPING ────────────────

DIFFICULTY_MAP = {
    # Vietnamese
    "nhận biết": "nhan_biet",
    "nhan biet": "nhan_biet",
    "nhan_biet": "nhan_biet",
    "biết": "nhan_biet",
    "dễ": "nhan_biet",
    "easy": "nhan_biet",
    # Thông hiểu
    "hiểu": "thong_hieu",
    "hieu": "thong_hieu",
    "thông hiểu": "thong_hieu",
    "thong hieu": "thong_hieu",
    "thong_hieu": "thong_hieu",
    "nhận biết/hiểu": "thong_hieu",
    # Vận dụng
    "vận dụng": "van_dung",
    "van dung": "van_dung",
    "van_dung": "van_dung",
    "trung bình": "van_dung",
    "medium": "van_dung",
    # Vận dụng cao
    "vận dụng cao": "van_dung_cao",
    "van dung cao": "van_dung_cao",
    "van_dung_cao": "van_dung_cao",
    "nâng cao": "van_dung_cao",
    "khó": "van_dung_cao",
    "hard": "van_dung_cao",
    "difficult": "van_dung_cao",
}

VALID_DIFFICULTIES = {"nhan_biet", "thong_hieu", "van_dung", "van_dung_cao"}

DIFFICULTY_LABELS = {
    "nhan_biet": "Nhận biết",
    "thong_hieu": "Thông hiểu",
    "van_dung": "Vận dụng",
    "van_dung_cao": "Vận dụng cao",
}

# ──────────────── QUESTION TYPE MAPPING ────────────────

QUESTION_TYPE_MAP = {
    # Single Choice
    "single": "single",
    "trắc nghiệm": "single",
    "trac nghiem": "single",
    "một đáp án": "single",
    "một lựa chọn": "single",
    "multiple choice": "single",
    "mc": "single",
    # Multiple Choice (Many answers)
    "multiple_choice": "multiple_choice",
    "nhiều đáp án": "multiple_choice",
    "nhieu dap an": "multiple_choice",
    "trắc nghiệm nhiều đáp án": "multiple_choice",
    "chọn các đáp án đúng": "multiple_choice",
    # True/False (THPT Quốc Gia multi-statement)
    "true_false": "true_false",
    "truefalse": "true_false",
    "true/false": "true_false",
    "đúng/sai": "true_false",
    "dung/sai": "true_false",
    "đúng sai": "true_false",
    "đúng/sai thpt": "true_false",
    # Short answer
    "short_answer": "short_answer",
    "trả lời ngắn": "short_answer",
    "tra loi ngan": "short_answer",
    "tự luận ngắn": "short_answer",
    "điền đáp án": "short_answer",
    "short answer": "short_answer",
    "fill in": "short_answer",
    # Essay
    "essay": "essay",
    "tu_luan": "essay",
    "tự luận": "essay",
    "tu luan": "essay",
    "bài tập tự luận": "essay",
    "bai tap tu luan": "essay",
    "tự luận mở": "essay",
    "tu luan mo": "essay",
    "tự luận cũ": "essay",
    "tu luan cu": "essay",
    "tu_luan_cu": "essay",
    "tự luận (dữ liệu cũ)": "essay",
    "tu luan (du lieu cu)": "essay",
    "long answer": "essay",
    "long_answer": "essay",
    "free response": "essay",
    "free_response": "essay",
}

VALID_QUESTION_TYPES = frozenset(TYPE_CODES)


def normalize_text(text):
    """Strip and clean whitespace while preserving paragraph line breaks."""
    if not text:
        return ""
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in str(text).splitlines()]
    return "\n".join(l for l in lines if l)


def remove_diacritics(text):
    """Remove Vietnamese diacritics for comparison."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def normalize_difficulty(raw):
    """Map raw difficulty string to internal enum."""
    if not raw:
        return None
    cleaned = normalize_text(raw).lower()
    cleaned_no_diacritics = remove_diacritics(cleaned)
    if cleaned in DIFFICULTY_MAP:
        return DIFFICULTY_MAP[cleaned]
    if cleaned_no_diacritics in DIFFICULTY_MAP:
        return DIFFICULTY_MAP[cleaned_no_diacritics]
    for key, value in DIFFICULTY_MAP.items():
        if key in cleaned or key in cleaned_no_diacritics:
            return value
    return None


def normalize_question_type(raw):
    """Map raw question type string to internal enum."""
    if not raw:
        return None
    canonical = canonical_type(raw)
    if canonical in TYPE_CODES:
        return canonical
    cleaned = normalize_text(raw).lower()
    cleaned_no_diacritics = remove_diacritics(cleaned)
    if cleaned in QUESTION_TYPE_MAP:
        return canonical_type(QUESTION_TYPE_MAP[cleaned])
    if cleaned_no_diacritics in QUESTION_TYPE_MAP:
        return canonical_type(QUESTION_TYPE_MAP[cleaned_no_diacritics])
    for key, value in QUESTION_TYPE_MAP.items():
        if key in cleaned or key in cleaned_no_diacritics:
            return canonical_type(value)
    return None


def infer_question_type(options, statements=None, raw_question_text=""):
    """Infer question type from options/statements/text content."""
    if statements and len(statements) > 0:
        return "true_false"
    if not options or len(options) == 0:
        # The former essay format is intentionally imported as short answer.
        # A missing answer key remains a normal short-answer review warning;
        # it must not turn into an unsupported-type error.
        return "short_answer"
    
    correct_count = sum(1 for o in options if o.get("is_correct"))
    if correct_count > 1:
        return "multiple_choice"
        
    if len(options) == 2:
        texts = {normalize_text(o.get("text", "")).lower() for o in options}
        tf_pairs = [{"đúng", "sai"}, {"true", "false"}, {"yes", "no"}, {"đ", "s"}]
        for pair in tf_pairs:
            if texts == pair:
                return "true_false"
    return "single"


def has_math_content(text):
    """Detect if text contains mathematical formulas or special symbols."""
    if not text:
        return False
    math_patterns = [
        r'\$.*?\$',           # LaTeX inline
        r'\\frac\{',          # LaTeX fraction
        r'\\sqrt\{',          # LaTeX sqrt
        r'\\sum',             # LaTeX sum
        r'\\int',             # LaTeX integral
        r'[∑∫∏√∂∇≤≥≠±∞]',    # Unicode math symbols
        r'\^{?\d+}?',         # Superscript pattern
        r'_{?\d+}?',          # Subscript pattern
    ]
    for pattern in math_patterns:
        if re.search(pattern, text):
            return True
    return False


def normalize_question(raw_question, index=0):
    """
    Normalize a raw parsed question into the unified schema.
    """
    q = {
        "index": index + 1,
        "source_position": index + 1,
        "source_label": raw_question.get('source_label') or (f"Trang {raw_question['page']} — Câu {raw_question['_header_number']} (mục {index+1})" if raw_question.get('_header_number') else f"Mục {index+1} trong file"),
        "question_text": normalize_text(raw_question.get("question_text", "")),
        "context": normalize_text(raw_question.get("context", "")),
        "image_url": raw_question.get("image_url", ""),
        "confidence_scores": raw_question.get("confidence_scores", {"question": 0.95, "type": 0.9, "image": 0.9, "answer": 0.9}),
        "question_type": None,
        "difficulty_level": None,
        "points": float(raw_question.get("points", 1.0)),
        "explanation": normalize_text(raw_question.get("explanation", "")),
        "options": [],
        "statements": [],
        "status": "valid",
        "errors": [],
        "warnings": [],
        "has_image": bool(raw_question.get("has_image", False) or raw_question.get("image_url")),
        "image_paths": raw_question.get("image_paths", []),
        "source_line": raw_question.get("source_line", 0),
        "formulas": raw_question.get("formulas", {}),
        "source_id": normalize_text(raw_question.get("source_id", "")),
        "grade": normalize_text(raw_question.get("grade", "")),
        "chapter": normalize_text(raw_question.get("chapter", "")),
        "section": normalize_text(raw_question.get("section", "")),
        "question_category": normalize_text(raw_question.get("question_category", "")),
        "sample_answer": normalize_text(raw_question.get("sample_answer", "")),
        "raw_correct": normalize_text(raw_question.get("raw_correct", "")),
    }

    # Normalize difficulty
    raw_diff = raw_question.get("difficulty_level", "")
    normalized_diff = normalize_difficulty(raw_diff)
    if normalized_diff:
        q["difficulty_level"] = normalized_diff
    elif raw_diff:
        q["difficulty_level"] = "nhan_biet"
        q["warnings"].append(
            f'Mức độ "{raw_diff}" không hợp lệ, đã đặt mặc định: Nhận biết.'
        )
    else:
        q["difficulty_level"] = "nhan_biet"

    # Normalize options
    raw_options = raw_question.get("options", [])
    for i, opt in enumerate(raw_options):
        text = normalize_text(opt.get("text", ""))
        is_corr = bool(opt.get("is_correct", False))
        
        # Check if text starts with single quote or asterisk marker: 'A., 'B., ’C., *D.
        if text and text[0] in ("'", "’", "’", "*"):
            is_corr = True
            text = text[1:].strip()
            # Clean leading option letter if left over e.g. A. ...
            m_letter = re.match(r"^[A-E][.:)]?\s*(.*)", text)
            if m_letter:
                text = m_letter.group(1).strip()

        if text:
            q["options"].append({
                "text": text,
                "is_correct": is_corr,
                "order_index": opt.get("order_index", i),
            })

    # Normalize True/False statements
    raw_statements = raw_question.get("statements", [])
    for i, stmt in enumerate(raw_statements):
        st_text = normalize_text(stmt.get("text", ""))
        if st_text:
            q["statements"].append({
                "id": stmt.get("id", chr(97 + i)),  # 'a', 'b', 'c', 'd'
                "text": st_text,
                "answer": stmt.get("answer", None)  # True, False, or None
            })

    # Normalize question type
    raw_type = raw_question.get("question_type", "")
    normalized_type = normalize_question_type(raw_type)
    if normalized_type:
        q["question_type"] = normalized_type
    else:
        q["question_type"] = infer_question_type(q["options"], q["statements"], q["question_text"])

    # Keep a small, non-error audit hint in the preview so teachers can see
    # why an old essay row became short answer.  It is deliberately not put in
    # ``warnings``: the conversion is automatic and needs no manual repair.
    if is_legacy_essay_type(raw_type):
        q["type_conversion"] = {
            "from": str(raw_type),
            "to": "short_answer",
            "label": "Tự luận cũ đã chuyển thành Trả lời ngắn",
        }

    if q["question_type"] == "short_answer" and q["options"]:
        if not q["sample_answer"]:
            q["sample_answer"] = q["options"][0]["text"]
        if not q["raw_correct"]:
            q["raw_correct"] = q["options"][0]["text"]

    inline_image_text = "\n".join([
        q["context"],
        q["question_text"],
        q["explanation"],
        *[option["text"] for option in q["options"]],
        *[statement["text"] for statement in q["statements"]],
    ])
    inline_image_paths = re.findall(
        r"\[\[image:(/static/uploads/questions/[A-Za-z0-9._-]+)\]\]",
        inline_image_text,
    )
    q["image_paths"] = list(dict.fromkeys(q["image_paths"] + inline_image_paths))
    q["has_image"] = bool(q["has_image"] or inline_image_paths)

    # Construct content blocks
    content_blocks = []
    if q["context"]:
        content_blocks.append({"type": "text", "value": q["context"]})
    if q["image_url"]:
        content_blocks.append({"type": "image", "url": q["image_url"]})
    if q["question_text"]:
        content_blocks.append({"type": "text", "value": q["question_text"]})
    q["content_blocks"] = content_blocks

    # Check for math content
    all_text = (q["context"] or "") + " " + q["question_text"] + " " + " ".join(o["text"] for o in q["options"])
    if has_math_content(all_text):
        q["warnings"].append("Có công thức toán, cần kiểm tra hiển thị KaTeX")

    return q


def normalize_questions(raw_questions):
    """Normalize a list of raw questions."""
    return [normalize_question(q, i) for i, q in enumerate(raw_questions)]
