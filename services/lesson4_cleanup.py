"""Scoped, repeatable cleanup for Math 9 Chapter 6 Lesson 4.

The application now has one supported ID scope: the eight categories in
``9C6-4-1`` through ``9C6-4-8``.  This module is deliberately independent of
Flask startup and uses reflected tables so it can be run against an existing
SQLite database without seeding or importing anything.

The cleanup is conservative about records with no curriculum provenance.  It
removes rows that are provably outside the retained scope and reports
unclassified rows instead of silently treating them as Lesson 4.  Whole exams
are removed when any item is outside the retained scope; this avoids leaving a
score whose denominator or answer key no longer represents the original form.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import defaultdict

from sqlalchemy import MetaData, Table, inspect, select

from services.curriculum_data import (
    CHAPTER6_CODE,
    CHAPTER6_GRADE,
    CHAPTER6_TOPIC_NAME,
    RETAINED_CATEGORY_CODES,
    RETAINED_LESSON_CODE,
    RETAINED_LESSON_NAME,
    is_retained_code,
)


SCOPE = {
    "grade": CHAPTER6_GRADE,
    "chapter_code": CHAPTER6_CODE,
    "lesson_code": RETAINED_LESSON_CODE,
    "lesson_name": RETAINED_LESSON_NAME,
    "category_codes": sorted(RETAINED_CATEGORY_CODES, key=int),
    "topic_name": CHAPTER6_TOPIC_NAME,
}

_CANONICAL_RE = re.compile(r"(?<![A-Z0-9])(?P<grade>[6-9])C(?P<chapter>[1-9A-Z])-?(?P<lesson>[1-9]\d*)-(?P<category>[1-9]\d*)(?![A-Z0-9])", re.I)
_ID6_RE = re.compile(r"(?<![A-Z0-9])(?P<grade>[6-9])C(?P<chapter>[1-9A-Z])[NHVC](?P<lesson>[1-9]\d*)-(?P<category>[1-9]\d*)(?:TL|D|T|S)(?:\.\d+)?(?![A-Z0-9])", re.I)
_CLASS8_FILE_RE = re.compile(r"(?:^|[^0-9])8(?:[-_ ]|$)|lớp\s*8|lop\s*8", re.I)


def _table_map(connection):
    metadata = MetaData()
    return {
        name: Table(name, metadata, autoload_with=connection)
        for name in inspect(connection).get_table_names()
    }


def _rows(connection, table):
    return [dict(row) for row in connection.execute(select(table)).mappings()]


def _norm(value):
    return str(value or "").strip().upper()


def _norm_grade(value):
    return re.sub(r"^LỚP\s*", "", _norm(value), flags=re.I)


def _parse_datetime(value):
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=None)
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(dt.timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed
    except (TypeError, ValueError):
        return None


def _canonical_from_parts(grade, chapter, lesson, category):
    grade = _norm_grade(grade)
    chapter, lesson, category = _norm(chapter), _norm(lesson), _norm(category)
    if not grade or not chapter or not lesson or not category:
        return None
    return f"{grade}C{chapter}-{lesson}-{category}"


def extract_curriculum_codes(value):
    """Extract canonical ``9C6-lesson-category`` codes from arbitrary text."""
    if value is None:
        return set()
    text_value = str(value)
    found = set()
    for pattern in (_CANONICAL_RE, _ID6_RE):
        for match in pattern.finditer(text_value):
            found.add(
                f"{match.group('grade').upper()}C{match.group('chapter').upper()}-"
                f"{match.group('lesson')}-{match.group('category')}"
            )
    return found


def _class_from_codes(codes):
    codes = {str(code).upper() for code in codes if code}
    if not codes:
        return "unknown"
    retained = {code for code in codes if is_retained_code(code)}
    outside = {code for code in codes if not is_retained_code(code)}
    # A code from another chapter/lesson is explicit outside provenance.  A
    # retained and outside code together is a contradiction, not a guess.
    if retained and outside:
        return "unknown"
    return "retained" if retained else "outside"


def _class_from_metadata(row, node_codes=None):
    """Classify one row using only explicit curriculum provenance."""
    evidence = []
    node_id = row.get("curriculum_node_id")
    if node_id is not None and node_codes is not None:
        try:
            node_code = node_codes.get(int(node_id))
        except (TypeError, ValueError):
            node_code = None
        if node_code:
            evidence.append(node_code)
        elif str(node_id).strip():
            # A dangling FK is not allowed to become retained by inference.
            return "unknown"

    for field in ("id6_scope", "source_id", "source_id6", "curriculum_code"):
        evidence.extend(extract_curriculum_codes(row.get(field)))

    direct = _canonical_from_parts(
        row.get("grade"), row.get("chapter") or row.get("chapter_code"),
        row.get("section") or row.get("lesson_code"),
        row.get("question_category") or row.get("category_code"),
    )
    if direct:
        evidence.append(direct)
    elif any(row.get(key) not in (None, "") for key in (
        "grade", "chapter", "chapter_code", "section", "lesson_code",
        "question_category", "category_code",
    )):
        # Partial explicit metadata is enough to identify an outside row when
        # it contradicts the retained grade/chapter/lesson.
        grade = _norm_grade(row.get("grade"))
        chapter = _norm(row.get("chapter") or row.get("chapter_code"))
        lesson = _norm(row.get("section") or row.get("lesson_code"))
        category = _norm(row.get("question_category") or row.get("category_code"))
        if grade and grade != CHAPTER6_GRADE:
            return "outside"
        if chapter and chapter != CHAPTER6_CODE:
            return "outside"
        if lesson and lesson != RETAINED_LESSON_CODE:
            return "outside"
        if category and category not in RETAINED_CATEGORY_CODES:
            return "outside"

    return _class_from_codes(evidence)


def _merge_classifications(*values):
    values = [value for value in values if value and value != "unknown"]
    if not values:
        return "unknown"
    if "retained" in values and "outside" in values:
        return "unknown"
    return values[0]


def _scope_data_classification(value):
    """Classify the structured file scope stored on an ImportSession."""
    if not isinstance(value, dict):
        return "unknown"
    grade = _norm_grade(value.get("grade"))
    chapters = {_norm(item) for item in value.get("chapters") or []}
    lessons = {str(item).strip().upper() for item in value.get("lessons") or []}
    if grade and grade != CHAPTER6_GRADE:
        return "outside"
    if chapters and chapters != {CHAPTER6_CODE}:
        return "outside"
    if lessons:
        if any(not lesson.endswith(f":{RETAINED_LESSON_CODE}") for lesson in lessons):
            return "outside"
        return "retained"
    return "unknown"


def _json_codes(value):
    if value is None:
        return set()
    if isinstance(value, str):
        try:
            return extract_curriculum_codes(value) | _json_codes(json.loads(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return extract_curriculum_codes(value)
    if isinstance(value, dict):
        codes = set()
        for item in value.values():
            codes.update(_json_codes(item))
        return codes
    if isinstance(value, (list, tuple, set)):
        codes = set()
        for item in value:
            codes.update(_json_codes(item))
        return codes
    return set()


def _in_scope_evidence(evidence_by_student_subject, student_id, subject):
    return bool(evidence_by_student_subject.get((student_id, subject)))


def _stable_report(report):
    value = json.loads(json.dumps(report, ensure_ascii=False, sort_keys=True, default=str))
    value.pop("status", None)
    value.pop("integrity", None)
    value.pop("backup", None)
    return value


def _fingerprint(report):
    return hashlib.sha256(
        json.dumps(_stable_report(report), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _add(plan, bucket, value):
    if value is not None:
        plan["delete"][bucket].append(value)


def _new_plan():
    return {
        "scope": dict(SCOPE),
        "delete": defaultdict(list),
        "unknown": defaultdict(list),
        "classifications": {},
    }


def _plan_table_rows(connection, tables, plan):
    """Build the explicit deletion set without changing the database."""
    nodes = _rows(connection, tables["curriculum_node"]) if "curriculum_node" in tables else []
    node_codes = {row["id"]: row.get("canonical_code") or _canonical_from_parts(
        row.get("grade"), row.get("chapter_code"), row.get("lesson_code"), row.get("category_code")
    ) for row in nodes}
    retained_node_ids = {row["id"] for row in nodes if is_retained_code(node_codes.get(row["id"]))}
    outside_node_ids = {row["id"] for row in nodes if row["id"] not in retained_node_ids}
    plan["delete"]["curriculum_node"] = sorted(outside_node_ids)
    plan["classifications"]["node_codes"] = node_codes

    bank_questions = _rows(connection, tables["bank_question"]) if "bank_question" in tables else []
    bank_class = {}
    for row in bank_questions:
        classification = _class_from_metadata(row, node_codes)
        bank_class[row["id"]] = classification
        if classification == "outside":
            _add(plan, "bank_question", row["id"])
        elif classification == "unknown":
            _add(plan, "bank_question", None)
            plan["unknown"]["bank_question"].append(row["id"])
    plan["delete"]["bank_question"] = sorted(set(plan["delete"].get("bank_question", [])))
    plan["classifications"]["bank_question"] = bank_class

    if "question_skill" in tables:
        mappings = _rows(connection, tables["question_skill"])
        for row in mappings:
            if row.get("curriculum_node_id") in outside_node_ids or row.get("question_id") in plan["delete"]["bank_question"]:
                _add(plan, "question_skill", row["id"])

    # Counters are infrastructure, so retain only the eight exact scopes.
    if "id6_counter" in tables:
        for row in _rows(connection, tables["id6_counter"]):
            if not is_retained_code(row.get("scope")):
                _add(plan, "id6_counter", row.get("scope"))

    # Expired/failed import previews are disposable input data.  An active
    # preview with no provenance remains an explicit unknown for review.
    if "import_session" in tables:
        now = dt.datetime.utcnow()
        for row in _rows(connection, tables["import_session"]):
            try:
                scope_payload = json.loads(row.get("scope_data") or "null")
            except (TypeError, ValueError, json.JSONDecodeError):
                scope_payload = None
            classification = _scope_data_classification(scope_payload)
            parsed_classifications = []
            try:
                parsed = json.loads(row.get("parsed_data") or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed = []
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        parsed_classifications.append(_class_from_metadata(item, node_codes))
            classification = _merge_classifications(classification, *parsed_classifications)
            expiry = _parse_datetime(row.get("expires_at"))
            if classification == "unknown" and (
                row.get("status") in {"failed", "cancelled", "expired"}
                or (expiry and expiry <= now)
                or _CLASS8_FILE_RE.search(str(row.get("filename") or ""))
            ):
                classification = "outside"
            if classification == "outside":
                _add(plan, "import_session", row["id"])
            elif classification == "unknown":
                plan["unknown"]["import_session"].append(row["id"])

    # Catalog receipts containing an obsolete outside-scope snapshot must not remain
    # available to a future startup migration.
    if "curriculum_catalog_migration" in tables:
        for row in _rows(connection, tables["curriculum_catalog_migration"]):
            codes = _json_codes(row.get("snapshot_json"))
            classification = _class_from_codes(codes)
            # A receipt is a catalog snapshot, not learner evidence.  Any
            # outside code in it makes the whole receipt obsolete, even when
            # the same snapshot also contains the retained Lesson 4 codes.
            if classification == "outside" or any(not is_retained_code(code) for code in codes):
                _add(plan, "curriculum_catalog_migration", row["migration_key"])
            elif classification == "unknown":
                plan["unknown"]["curriculum_catalog_migration"].append(row["migration_key"])

    # Exam forms are classified before deleting any source bank questions.
    exam_questions = _rows(connection, tables["exam_question"]) if "exam_question" in tables else []
    exam_question_class = {}
    exam_question_by_exam = defaultdict(list)
    for row in exam_questions:
        classification = _class_from_metadata(row, node_codes)
        if row.get("bank_question_id") in bank_class:
            classification = _merge_classifications(classification, bank_class[row["bank_question_id"]])
        exam_question_class[row["id"]] = classification
        exam_question_by_exam[row.get("exam_id")].append(row["id"])
    plan["classifications"]["exam_question"] = exam_question_class

    deleted_exam_ids = set()
    if "exam" in tables:
        for row in _rows(connection, tables["exam"]):
            classes = [exam_question_class.get(question_id, "unknown")
                       for question_id in exam_question_by_exam.get(row["id"], [])]
            if "outside" in classes:
                deleted_exam_ids.add(row["id"])
                continue
            if classes and all(value == "retained" for value in classes):
                continue
            if classes:
                plan["unknown"]["exam"].append(row["id"])
    plan["delete"]["exam"] = sorted(deleted_exam_ids)
    plan["delete"]["exam_question"] = sorted({
        question_id for exam_id, question_ids in exam_question_by_exam.items()
        if exam_id in deleted_exam_ids
        for question_id in question_ids
    })
    for row in exam_questions:
        if row.get("exam_id") is None and exam_question_class.get(row["id"]) == "outside":
            _add(plan, "exam_question", row["id"])
    plan["delete"]["exam_question"] = sorted(set(plan["delete"].get("exam_question", [])))

    submissions = _rows(connection, tables["exam_submission"]) if "exam_submission" in tables else []
    deleted_submission_ids = {row["id"] for row in submissions if row.get("exam_id") in deleted_exam_ids}
    plan["delete"]["exam_submission"] = sorted(deleted_submission_ids)

    submission_answers = _rows(connection, tables["submission_answer"]) if "submission_answer" in tables else []
    deleted_submission_answer_ids = set()
    for row in submission_answers:
        if row.get("submission_id") in deleted_submission_ids or row.get("question_id") in plan["delete"]["exam_question"]:
            deleted_submission_answer_ids.add(row["id"])
    plan["delete"]["submission_answer"] = sorted(deleted_submission_answer_ids)

    # Learning facts are retained only when their frozen question/submission
    # provenance remains retained.  This handles a legacy row that has no
    # curriculum_code but points to a retained exam question.
    learning_rows = _rows(connection, tables["learning_history"]) if "learning_history" in tables else []
    learning_class = {}
    for row in learning_rows:
        classification = _class_from_metadata(row, node_codes)
        if row.get("bank_question_id") in bank_class:
            classification = _merge_classifications(classification, bank_class[row["bank_question_id"]])
        if row.get("exam_question_id") in exam_question_class:
            classification = _merge_classifications(classification, exam_question_class[row["exam_question_id"]])
        learning_class[row["id"]] = classification
        if (classification == "outside"
                or row.get("submission_id") in deleted_submission_ids
                or row.get("exam_question_id") in plan["delete"]["exam_question"]):
            _add(plan, "learning_history", row["id"])
        elif classification == "unknown":
            plan["unknown"]["learning_history"].append(row["id"])
    plan["classifications"]["learning_history"] = learning_class

    # Error observations follow their answer/question/submission evidence.
    error_rows = _rows(connection, tables["error_observation"]) if "error_observation" in tables else []
    error_class = {}
    for row in error_rows:
        classification = _class_from_metadata(row, node_codes)
        if row.get("bank_question_id") in bank_class:
            classification = _merge_classifications(classification, bank_class[row["bank_question_id"]])
        if row.get("exam_question_id") in exam_question_class:
            classification = _merge_classifications(classification, exam_question_class[row["exam_question_id"]])
        error_class[row["id"]] = classification
        if (classification == "outside"
                or row.get("submission_id") in deleted_submission_ids
                or row.get("submission_answer_id") in deleted_submission_answer_ids
                or row.get("exam_question_id") in plan["delete"]["exam_question"]):
            _add(plan, "error_observation", row["id"])
        elif classification == "unknown":
            plan["unknown"]["error_observation"].append(row["id"])
    plan["classifications"]["error_observation"] = error_class

    if "diagnostic_assignment" in tables:
        for row in _rows(connection, tables["diagnostic_assignment"]):
            if row.get("exam_id") in deleted_exam_ids:
                _add(plan, "diagnostic_assignment", row["id"])

    if "exam_answer" in tables:
        for row in _rows(connection, tables["exam_answer"]):
            if row.get("question_id") in plan["delete"]["exam_question"]:
                _add(plan, "exam_answer", row["id"])

    if "mastery_snapshot" in tables:
        for row in _rows(connection, tables["mastery_snapshot"]):
            codes = _json_codes(row.get("profile_data"))
            classification = _class_from_codes(codes)
            if row.get("submission_id") in deleted_submission_ids or classification == "outside":
                _add(plan, "mastery_snapshot", row["id"])
            elif row.get("submission_id") is None and classification == "unknown":
                plan["unknown"]["mastery_snapshot"].append(row["id"])

    # Evidence presence drives stale aggregate cleanup.  A surviving learning
    # row or retained submission is sufficient to keep a learner projection.
    evidence_by_student_subject = defaultdict(bool)
    for row in learning_rows:
        if row["id"] not in set(plan["delete"].get("learning_history", [])) and learning_class.get(row["id"]) == "retained":
            evidence_by_student_subject[(row.get("student_id"), row.get("subject"))] = True
    for row in submissions:
        if row["id"] not in deleted_submission_ids:
            subject = row.get("subject")
            if subject:
                evidence_by_student_subject[(row.get("student_id"), subject)] = True
    plan["classifications"]["evidence_by_student_subject"] = evidence_by_student_subject

    if "student_error_profile" in tables:
        for row in _rows(connection, tables["student_error_profile"]):
            classification = _class_from_codes(extract_curriculum_codes(row.get("curriculum_code")))
            has_evidence = bool([
                item for item in error_rows
                if item.get("student_id") == row.get("student_id")
                and item.get("subject") == row.get("subject")
                and item["id"] not in set(plan["delete"].get("error_observation", []))
                and error_class.get(item["id"]) == "retained"
            ])
            if classification == "outside" or not has_evidence:
                _add(plan, "student_error_profile", row["id"])
            elif classification == "unknown":
                plan["unknown"]["student_error_profile"].append(row["id"])

    for table_name in ("student_mastery", "student_performance"):
        if table_name not in tables:
            continue
        for row in _rows(connection, tables[table_name]):
            codes = extract_curriculum_codes(row.get("dimension_key"))
            classification = _class_from_codes(codes)
            if classification == "outside" or not _in_scope_evidence(
                    evidence_by_student_subject, row.get("student_id"), row.get("subject")):
                _add(plan, table_name, row["id"])
            elif classification == "unknown" and codes:
                plan["unknown"][table_name].append(row["id"])

    for table_name in ("ai_analysis_run", "teacher_learning_report"):
        if table_name not in tables:
            continue
        for row in _rows(connection, tables[table_name]):
            codes = _json_codes(row.get("request_data")) | _json_codes(row.get("response_data")) \
                if table_name == "ai_analysis_run" else _json_codes(row.get("payload"))
            classification = _class_from_codes(codes)
            has_evidence = _in_scope_evidence(evidence_by_student_subject, row.get("student_id"), row.get("subject"))
            if (classification == "outside"
                    or not has_evidence
                    or table_name == "ai_analysis_run" and _norm(row.get("chapter_code")) not in {"", "6"}):
                _add(plan, table_name, row["id"])
            elif classification == "unknown":
                plan["unknown"][table_name].append(row["id"])

    # Empty question banks are removed only when their own explicit metadata
    # identifies them as outside and no surviving exam/import references them.
    if "question_bank" in tables:
        bank_ids_with_questions = defaultdict(list)
        for row in bank_questions:
            if row["id"] not in plan["delete"]["bank_question"]:
                bank_ids_with_questions[row.get("bank_id")].append(row["id"])
        referenced_bank_ids = {
            row.get("question_bank_id") for row in (_rows(connection, tables["exam"]) if "exam" in tables else [])
            if row.get("id") not in deleted_exam_ids and row.get("question_bank_id") is not None
        }
        referenced_bank_ids.update(
            row.get("bank_id") for row in (_rows(connection, tables["import_session"]) if "import_session" in tables else [])
            if row.get("id") not in plan["delete"].get("import_session", []) and row.get("bank_id") is not None
        )
        for row in _rows(connection, tables["question_bank"]):
            if bank_ids_with_questions.get(row["id"]):
                continue
            if row["id"] in referenced_bank_ids:
                continue
            metadata_class = _class_from_metadata(row)
            if metadata_class == "outside":
                _add(plan, "question_bank", row["id"])
            elif metadata_class == "unknown" and row.get("grade"):
                plan["unknown"]["question_bank"].append(row["id"])

    return plan


def _delete_ids(connection, tables, table_name, column_name, ids):
    ids = sorted(set(ids or []))
    if not ids or table_name not in tables or column_name not in tables[table_name].c:
        return 0
    table = tables[table_name]
    removed = 0
    for offset in range(0, len(ids), 500):
        batch = ids[offset:offset + 500]
        result = connection.execute(table.delete().where(getattr(table.c, column_name).in_(batch)))
        removed += int(result.rowcount or 0)
    return removed


def _delete_orphans(connection, tables):
    """Remove child rows made orphaned by an explicit scoped delete."""
    statements = (
        ("bank_question_option", "question_id", "bank_question", "id"),
        ("exam_answer", "question_id", "exam_question", "id"),
        ("submission_answer", "submission_id", "exam_submission", "id"),
        ("submission_answer", "question_id", "exam_question", "id"),
        ("learning_history", "submission_id", "exam_submission", "id"),
        ("learning_history", "exam_question_id", "exam_question", "id"),
        ("error_observation", "submission_id", "exam_submission", "id"),
        ("error_observation", "submission_answer_id", "submission_answer", "id"),
        ("error_observation", "exam_question_id", "exam_question", "id"),
        ("diagnostic_assignment", "exam_id", "exam", "id"),
        ("exam_question", "exam_id", "exam", "id"),
        ("bank_question", "bank_id", "question_bank", "id"),
    )
    removed = defaultdict(int)
    for child, child_col, parent, parent_col in statements:
        if child not in tables or parent not in tables:
            continue
        child_table, parent_table = tables[child], tables[parent]
        if child_col not in child_table.c or parent_col not in parent_table.c:
            continue
        result = connection.execute(child_table.delete().where(
            ~getattr(child_table.c, child_col).in_(select(getattr(parent_table.c, parent_col)))
        ))
        removed[child] += int(result.rowcount or 0)
    return dict(removed)


def _recompute_error_profiles(connection, tables):
    if "student_error_profile" not in tables or "error_observation" not in tables:
        return 0
    profile_table, observation_table = tables["student_error_profile"], tables["error_observation"]
    observations = [row for row in _rows(connection, observation_table) if row.get("status") == "observed"]
    groups = defaultdict(list)
    for row in observations:
        groups[(row.get("student_id"), row.get("subject"), row.get("curriculum_code"), row.get("error_code"))].append(row)
    profiles = _rows(connection, profile_table)
    by_key = {(row.get("student_id"), row.get("subject"), row.get("curriculum_code"), row.get("error_code")): row for row in profiles}
    for key, rows in groups.items():
        row = by_key.get(key)
        if not row:
            continue
        values = {
            "evidence_count": len(rows),
            "confidence": min(0.9, 0.35 + len(rows) * 0.1),
            "status": "observed",
            "first_observed_at": min((item.get("created_at") for item in rows if item.get("created_at")), default=None),
            "last_observed_at": max((item.get("created_at") for item in rows if item.get("created_at")), default=None),
        }
        connection.execute(profile_table.update().where(profile_table.c.id == row["id"]).values(**values))
    stale = [row["id"] for key, row in by_key.items() if key not in groups]
    return _delete_ids(connection, tables, "student_error_profile", "id", stale)


def _recompute_mastery(connection, tables):
    if "student_mastery" not in tables or "learning_history" not in tables:
        return 0
    history = [row for row in _rows(connection, tables["learning_history"])
               if row.get("answer_status") not in {"unanswered", "pending_review"}]
    grouped = defaultdict(list)
    keys = defaultdict(set)
    for row in history:
        student_subject = (row.get("student_id"), row.get("subject"))
        topic = row.get("topic") or "Chưa xác định"
        cognitive = row.get("cognitive_level") or "nhan_biet"
        skill = row.get("curriculum_code") or topic
        for dimension, key in (("topic", topic), ("skill", skill), ("cognitive", cognitive),
                               ("topic_cognitive", f"{topic}||{cognitive}")):
            grouped[(student_subject, dimension, key)].append(row)
            keys[(student_subject, dimension)].add(key)
    table = tables["student_mastery"]
    rows = _rows(connection, table)
    removed = 0
    for row in rows:
        student_subject = (row.get("student_id"), row.get("subject"))
        if row.get("dimension_key") not in keys.get((student_subject, row.get("dimension")), set()):
            removed += _delete_ids(connection, tables, "student_mastery", "id", [row["id"]])
    for (student_subject, dimension, key), values in grouped.items():
        existing = next((row for row in rows if row.get("student_id") == student_subject[0]
                         and row.get("subject") == student_subject[1]
                         and row.get("dimension") == dimension and row.get("dimension_key") == key), None)
        if not existing:
            continue
        weights = [max(float(item.get("weight") or 0), .0001) for item in values]
        scores = [max(0., min(1., float(item.get("normalized_score") or 0))) for item in values]
        total_weight, weighted = sum(weights), sum(weight * score for weight, score in zip(weights, scores))
        mastery = weighted / total_weight if total_weight else 0
        interpretation = "Yếu" if mastery < .4 else "Trung bình" if mastery < .6 else "Khá" if mastery < .8 else "Tốt"
        connection.execute(table.update().where(table.c.id == existing["id"]).values(
            mastery=round(mastery, 4), interpretation=interpretation, sample_count=len(values),
            weighted_score=round(weighted, 6), total_weight=round(total_weight, 6),
            evidence_count=len(values), insufficient_data=len(values) < 3,
            last_evidence_at=max((item.get("occurred_at") for item in values if item.get("occurred_at")), default=None),
        ))
    return removed


def _recompute_performance(connection, tables):
    if "student_performance" not in tables or "learning_history" not in tables:
        return 0
    histories = _rows(connection, tables["learning_history"])
    evidence = {(row.get("student_id"), row.get("subject")) for row in histories}
    rows = _rows(connection, tables["student_performance"])
    removed = 0
    for row in rows:
        if (row.get("student_id"), row.get("subject")) not in evidence:
            removed += _delete_ids(connection, tables, "student_performance", "id", [row["id"]])
    return removed


def _counts(plan):
    counts = {name: len(sorted(set(values))) for name, values in plan["delete"].items()}
    counts["unknown_total"] = sum(len(values) for values in plan["unknown"].values())
    counts["nodes_removed"] = counts.get("curriculum_node", 0)
    counts["questions_removed"] = counts.get("bank_question", 0)
    counts["exams_removed"] = counts.get("exam", 0)
    counts["submissions_removed"] = counts.get("exam_submission", 0)
    counts["learning_history_removed"] = counts.get("learning_history", 0)
    return counts


def _public_report(plan, *, status):
    report = {
        "migration_key": "math9-chapter6-lesson4-only-v1",
        "status": status,
        "scope": dict(SCOPE),
        "mixed_exam_policy": "delete_whole_exam_if_any_item_is_outside_scope",
        "counts": _counts(plan),
        "delete_ids": {name: sorted(set(values)) for name, values in plan["delete"].items()},
        "unknown": {name: sorted(set(values)) for name, values in plan["unknown"].items() if values},
    }
    report["plan_fingerprint"] = _fingerprint(report)
    return report


def inspect_lesson4_cleanup(engine):
    """Return a read-only plan; no tables are created and no rows are changed."""
    with engine.connect() as connection:
        tables = _table_map(connection)
        plan = _new_plan()
        _plan_table_rows(connection, tables, plan)
        return _public_report(plan, status="dry_run")


def apply_lesson4_cleanup(engine, expected_fingerprint=None):
    """Apply the scoped deletion in one transaction and return its receipt."""
    with engine.connect() as connection:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
        try:
            tables = _table_map(connection)
            plan = _new_plan()
            _plan_table_rows(connection, tables, plan)
            report = _public_report(plan, status="planned")
            if expected_fingerprint and report["plan_fingerprint"] != expected_fingerprint:
                report["status"] = "blocked"
                report["blockers"] = [{"kind": "stale_plan", "count": 1}]
                connection.rollback()
                return report

            # Delete children before parents even on SQLite databases where
            # foreign_keys was historically disabled.
            for table_name, column_name in (
                ("question_skill", "id"), ("bank_question_option", "question_id"),
                ("exam_answer", "id"), ("submission_answer", "id"),
                ("error_observation", "id"), ("learning_history", "id"),
                ("diagnostic_assignment", "id"), ("mastery_snapshot", "id"),
                ("exam_question", "id"), ("exam_submission", "id"),
            ):
                ids = plan["delete"].get(table_name, [])
                if table_name == "bank_question_option":
                    _delete_ids(connection, tables, table_name, column_name, plan["delete"].get("bank_question", []))
                else:
                    _delete_ids(connection, tables, table_name, column_name, ids)

            for table_name, column_name in (
                ("exam", "id"), ("bank_question", "id"), ("question_bank", "id"),
                ("curriculum_node", "id"), ("id6_counter", "scope"),
                ("import_session", "id"), ("curriculum_catalog_migration", "migration_key"),
                ("student_error_profile", "id"), ("student_mastery", "id"),
                ("student_performance", "id"), ("ai_analysis_run", "id"),
                ("teacher_learning_report", "id"),
            ):
                _delete_ids(connection, tables, table_name, column_name, plan["delete"].get(table_name, []))

            orphan_counts = _delete_orphans(connection, tables)
            report["orphan_rows_removed"] = orphan_counts
            report["aggregate_rows_recomputed"] = {
                "student_error_profile": _recompute_error_profiles(connection, tables),
                "student_mastery_removed_stale": _recompute_mastery(connection, tables),
                "student_performance_removed_stale": _recompute_performance(connection, tables),
            }
            connection.commit()
            report["status"] = "applied"
            return report
        except Exception:
            connection.rollback()
            raise
