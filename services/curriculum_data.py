"""The single supported ID catalog: grade 9, Chapter 8, combined lesson ``i``.

The question bank still keeps the topic metadata because the adaptive engine
uses it, but the ID catalog deliberately has one bounded scope.  Keeping the
scope check here makes every importer, picker and seed path agree even when a
caller sends a legacy payload.
"""

import json
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data"
# The product scope is deliberately named after the corrected curriculum.  The
# CHAPTER6_* aliases below are kept for modules whose filenames are historical;
# their values are *not* the old Chapter 6 scope.
CHAPTER8_VERSION = "math9-c8-i-v1"
CHAPTER8_MIGRATION = "math9-chapter8-i-v1"
CHAPTER8_GRADE = "9"
CHAPTER8_CODE = "8"
RETAINED_LESSON_CODE = "i"
RETAINED_LESSON_NAME = "Bài 25 + 26 (kết hợp): Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố"
RETAINED_CATEGORY_CODES = frozenset(str(number) for number in range(1, 9))
RETAINED_CODE_PREFIX = f"{CHAPTER8_GRADE}C{CHAPTER8_CODE}-{RETAINED_LESSON_CODE}-"
CHAPTER8_TOPIC_CODE = "thong_ke_xac_suat"
CHAPTER8_TOPIC_NAME = "Thống kê và xác suất"
CHAPTER8_CHAPTER_NAME = "Một số yếu tố thống kê và xác suất"
LESSON_SIZES = {RETAINED_LESSON_CODE: len(RETAINED_CATEGORY_CODES)}

# Compatibility aliases for the phase-6 module names.  Keeping these aliases
# avoids a risky filename-wide rename while ensuring every active caller sees
# the corrected scope.
CHAPTER6_VERSION = CHAPTER8_VERSION
CHAPTER6_MIGRATION = CHAPTER8_MIGRATION
CHAPTER6_GRADE = CHAPTER8_GRADE
CHAPTER6_CODE = CHAPTER8_CODE
CHAPTER6_TOPIC_CODE = CHAPTER8_TOPIC_CODE
CHAPTER6_TOPIC_NAME = CHAPTER8_TOPIC_NAME


def canonical_code(row):
    lesson = str(row["lesson_code"]).strip()
    # ``i`` is a literal combined-lesson marker, not an upper-case Roman
    # numeral.  Preserve it in every catalog/ID scope representation.
    lesson = "i" if lesson.lower() == "i" else lesson.upper()
    return f"{str(row['grade']).strip()}C{str(row['chapter_code']).strip().upper()}-{lesson}-{str(row['category_code']).strip()}"


def is_retained_code(code):
    """Return whether ``code`` is one of the eight retained lesson-i IDs."""
    value = str(code or "").strip()
    prefix = RETAINED_CODE_PREFIX
    if value[:len(prefix)].upper() != prefix.upper():
        return False
    return value[len(prefix):] in RETAINED_CATEGORY_CODES


def _read(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def load_math9_catalog():
    rows = [row for row in _read("math9_curriculum.json")
            if str(row.get("grade")) == CHAPTER8_GRADE
            and str(row.get("chapter_code")) == CHAPTER8_CODE
            and row.get("lesson_code") == RETAINED_LESSON_CODE
            and str(row.get("category_code")) in RETAINED_CATEGORY_CODES]
    if any(str(row.get("grade")) != CHAPTER8_GRADE or str(row.get("chapter_code")) != CHAPTER8_CODE
           or row.get("lesson_code") != RETAINED_LESSON_CODE
           or str(row.get("category_code")) not in RETAINED_CATEGORY_CODES
           for row in rows):
        raise ValueError("Danh mục ID chỉ được chứa lớp 9, Chương 8, bài kết hợp i.")
    codes = [canonical_code(row) for row in rows]
    if len(codes) != len(set(codes)):
        raise ValueError("Danh mục chứa mã dạng bị trùng.")
    return rows


def load_chapter8_bundle():
    """Reject an inconsistent release before seeding or migrating any data."""
    rows = load_math9_catalog()
    rules = _read("math9_chapter8_rules.json")
    rules["topics"] = [dict(topic, lesson_codes=[RETAINED_LESSON_CODE])
                        for topic in rules.get("topics", [])]
    rules["categories"] = [rule for rule in rules.get("categories", [])
                            if is_retained_code(rule.get("canonical_code"))]
    expected = {f"9C8-{RETAINED_LESSON_CODE}-{category}"
                for category in RETAINED_CATEGORY_CODES}
    if {canonical_code(row) for row in rows} != expected or len(rows) != len(expected):
        raise ValueError("Bài kết hợp i phải có đúng 8 dạng ID 9C8-i-1 đến 9C8-i-8.")
    if any(row["catalog_version"] != CHAPTER8_VERSION for row in rows):
        raise ValueError("Phiên bản danh mục Chương 8 bài i không đồng nhất.")
    rule_rows = {rule["canonical_code"]: rule for rule in rules["categories"]}
    if set(rule_rows) != expected or len(rules["categories"]) != len(expected):
        raise ValueError("Thiếu hoặc trùng tiêu chí nhận diện dạng bài i.")
    topics = {topic["code"]: topic for topic in rules["topics"]}
    if (len(rules["topics"]) != 1 or set(topics) != {CHAPTER8_TOPIC_CODE}
            or topics[CHAPTER8_TOPIC_CODE]["lesson_codes"] != [RETAINED_LESSON_CODE]):
        raise ValueError("Bài i dùng một chủ đề chung: Thống kê và xác suất.")
    for row in rows:
        topic = topics.get(row["topic_code"])
        rule = rule_rows[canonical_code(row)]
        if (not topic or topic["name"] != row["topic_name"]
                or row["lesson_code"] not in topic["lesson_codes"]
                or rule["topic_code"] != row["topic_code"]
                or rule["name"] != row["category_name"]):
            raise ValueError("Chủ đề hoặc tên dạng bài i không khớp danh mục.")
        if not rule["required_intent"] or not rule["positive_signals"] or not rule["exclusions"]:
            raise ValueError("Dạng bài i thiếu yêu cầu nhận diện hoặc điều kiện loại trừ.")
    level_codes = {"nhan_biet": "N", "thong_hieu": "H", "van_dung": "V", "van_dung_cao": "C"}
    rubric = rules["difficulty_rubric"]
    if set(rubric) != set(level_codes) or any(
        rubric[level]["id_code"] != code or rubric[level]["rank"] != rank
        for rank, (level, code) in enumerate(level_codes.items(), 1)
    ):
        raise ValueError("Tiêu chí mức độ phải đúng thứ tự NB–TH–VD–VDC.")
    if rules["policies"]["default_difficulty"] is not None:
        raise ValueError("Không đặt mức độ mặc định cho bộ phân loại.")
    if rules["catalog_version"] != CHAPTER8_VERSION:
        raise ValueError("Danh mục nguồn và đích bài i không khớp phiên bản.")
    return {"rows": rows, "rules": rules}


# Historical import name retained for callers and migration reports.
load_chapter6_bundle = load_chapter8_bundle
