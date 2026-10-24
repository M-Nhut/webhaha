"""Curriculum catalog helpers.

Catalog data supports manual editing and the independent ID6 metadata adapter.
Document parsers and the import service do not depend on this module.
"""

import re
from services.curriculum_data import (
    CHAPTER8_CODE,
    CHAPTER8_GRADE,
    RETAINED_CATEGORY_CODES,
    RETAINED_LESSON_CODE,
    RETAINED_LESSON_NAME,
    CHAPTER8_TOPIC_CODE,
    CHAPTER8_TOPIC_NAME,
    CHAPTER8_VERSION,
    load_math9_catalog,
    load_chapter8_bundle,
)


CODE_PATTERN = re.compile(r"^[1-9][0-9]*$")


def normalize_curriculum_payload(payload):
    """Normalize and validate one curriculum catalog row."""
    normalized = {
        "grade": re.sub(r"^Lớp\s*", "", str(payload.get("grade", "")).strip(), flags=re.I).upper(),
        "chapter_code": str(payload.get("chapter_code", "")).strip().upper(),
        "chapter_name": str(payload.get("chapter_name", "")).strip(),
        "lesson_code": ("i" if str(payload.get("lesson_code", "")).strip().lower() == "i"
                        else str(payload.get("lesson_code", "")).strip().upper()),
        "lesson_name": str(payload.get("lesson_name", "")).strip(),
        "category_code": str(payload.get("category_code", "")).strip().upper(),
        "category_name": str(payload.get("category_name", "")).strip(),
        # The version is retained internally for compatibility with existing
        # rows and migrations.  It is no longer user-selectable in the ID UI.
        "catalog_version": CHAPTER8_VERSION,
        "is_advanced": bool(payload.get("is_advanced", False)),
        "topic_code": CHAPTER8_TOPIC_CODE,
        "topic_name": CHAPTER8_TOPIC_NAME,
    }

    if normalized["grade"] != CHAPTER8_GRADE:
        raise ValueError("Danh mục ID hiện chỉ hỗ trợ lớp 9, Chương 8.")
    if normalized["chapter_code"] != CHAPTER8_CODE:
        raise ValueError("Danh mục ID hiện chỉ hỗ trợ Chương 8.")
    if normalized["lesson_code"] != RETAINED_LESSON_CODE:
        raise ValueError("Danh mục hiện chỉ giữ bài kết hợp i (Bài 25 + 26): Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố.")
    if normalized["category_code"] not in RETAINED_CATEGORY_CODES:
        raise ValueError("Mã dạng bài i phải từ 1 đến 8.")

    for field, label in (
        ("chapter_name", "Tên chương"),
        ("lesson_name", "Tên bài"),
        ("category_name", "Tên dạng"),
    ):
        if not normalized[field]:
            raise ValueError(f"{label} không được để trống.")
    if normalized["lesson_name"] != RETAINED_LESSON_NAME:
        raise ValueError("Tên bài phải là Bài 25 + 26 (kết hợp): Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố.")

    supplied_topic_code = str(payload.get("topic_code") or "").strip()
    supplied_topic_name = str(payload.get("topic_name") or "").strip()
    if supplied_topic_code and supplied_topic_code != CHAPTER8_TOPIC_CODE:
        raise ValueError("Chương 8 chỉ dùng chủ đề Thống kê và xác suất.")
    if supplied_topic_name and supplied_topic_name != CHAPTER8_TOPIC_NAME:
        raise ValueError("Chương 8 chỉ dùng chủ đề Thống kê và xác suất.")

    return normalized


def parse_catalog_rows(raw_text, catalog_version=CHAPTER8_VERSION):
    """Parse pipe/tab separated curriculum rows for the dedicated catalog UI."""
    rows = []
    errors = []
    for line_number, raw_line in enumerate((raw_text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        delimiter = "|" if "|" in line else "\t" if "\t" in line else None
        if not delimiter:
            errors.append(f"Dòng {line_number}: cần phân cách 7 cột bằng dấu | hoặc tab.")
            continue

        parts = [part.strip() for part in line.split(delimiter)]
        if len(parts) != 7:
            errors.append(f"Dòng {line_number}: nhận {len(parts)} cột, cần đúng 7 cột.")
            continue

        try:
            rows.append(normalize_curriculum_payload({
                "grade": parts[0],
                "chapter_code": parts[1],
                "chapter_name": parts[2],
                "lesson_code": parts[3],
                "lesson_name": parts[4],
                "category_code": parts[5],
                "category_name": parts[6],
                "catalog_version": CHAPTER8_VERSION,
            }))
        except ValueError as exc:
            errors.append(f"Dòng {line_number}: {exc}")

    return rows, errors


def seed_math9_catalog():
    """Seed only the eight retained types in grade 9 Chapter 8 lesson i."""
    from database import db
    from models import CurriculumNode
    load_chapter8_bundle()
    rows = load_math9_catalog()
    existing = {node.canonical_code: node for node in CurriculumNode.query.all()}
    # Do not mix old and new definitions in a partial legacy chapter.
    chapter8_nodes = [n for n in existing.values()
                      if n.grade == CHAPTER8_GRADE and n.chapter_code == CHAPTER8_CODE]
    old_chapter8 = any(n.catalog_version != CHAPTER8_VERSION for n in chapter8_nodes)
    if not old_chapter8 and len(chapter8_nodes) < len(rows):
        # Old imported tags can exist even without catalog FKs. Do not attach
        # those questions to newly seeded definitions with a different meaning.
        from services.curriculum_migration import inspect_chapter6_migration
        old_chapter8 = bool(inspect_chapter6_migration(db.engine)["blockers"])
    for row in rows:
        is_retained = (row["grade"] == CHAPTER8_GRADE
                       and row["chapter_code"] == CHAPTER8_CODE
                       and row["lesson_code"] == RETAINED_LESSON_CODE)
        if is_retained and old_chapter8:
            continue
        code = CurriculumNode.make_canonical_code(row["grade"], row["chapter_code"], row["lesson_code"], row["category_code"])
        node = existing.get(code)
        if node is None:
            db.session.add(CurriculumNode(**row))
        elif node.catalog_version == "math9-v1" and not is_retained:
            for key, value in row.items():
                setattr(node, key, value)
    db.session.commit()
