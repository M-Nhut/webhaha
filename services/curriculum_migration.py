"""Audited, conservative migration of the supplied chapter 6 catalog.

Dry runs are read-only. Apply/rollback lock writers and never reinterpret an
existing question. Referenced or customized definitions require content review.
"""

import datetime as dt
import hashlib
import json
import re

from sqlalchemy import DateTime, MetaData, Table, inspect, select, text

from services.curriculum_data import (
    CHAPTER6_MIGRATION, CHAPTER6_VERSION, canonical_code, load_chapter6_bundle,
)


TABLE_NAMES = ("curriculum_node", "bank_question", "id6_counter", "import_session", "question_skill")
CONTENT_FIELDS = ("grade", "chapter_code", "chapter_name", "lesson_code", "lesson_name",
                  "category_code", "category_name")
TOPIC_FIELDS = {"topic_code": "VARCHAR(40)", "topic_name": "VARCHAR(100)"}
CHAPTER6_ONLY_MIGRATION = "id6-catalog-chapter6-only-v1"
CHAPTER6_SCOPE_PREFIX = "9C6-"
_LEGACY_ID_RE = re.compile(
    r"(?:%\[\s*)?(?P<grade>[6-9])C(?P<chapter>[1-9A-Z])"
    r"[NHVC][1-9]\d*-[1-9]\d*(?:(?:TL|D|T|S)\.\d+)?\s*\]?",
    re.I,
)


class CatalogMigrationBlocked(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__("Chưa chuyển danh mục: cần xử lý các mục được chỉ rõ trong báo cáo.")


def _non_chapter6_source(value):
    """Classify old ID labels without allowing them back into active ID6 logic."""
    match = _LEGACY_ID_RE.fullmatch(str(value or "").strip())
    if not match:
        return False
    return (match.group("grade").upper(), match.group("chapter").upper()) != ("9", "6")


def cleanup_non_chapter6_id6(engine, *, dry_run=False):
    """Compatibility alias for the destructive Lesson 4-only migration."""
    from services.lesson4_cleanup import apply_lesson4_cleanup, inspect_lesson4_cleanup
    return apply_lesson4_cleanup(engine) if not dry_run else inspect_lesson4_cleanup(engine)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=lambda item: item.isoformat())


def _fingerprint(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _tables(connection):
    names = set(inspect(connection).get_table_names())
    required = {"curriculum_node", "bank_question", "id6_counter", "import_session"}
    missing = required - names
    if missing:
        raise ValueError("Cần nâng cấp schema ID6 trước; thiếu bảng: " + ", ".join(sorted(missing)))
    metadata = MetaData()
    return {name: Table(name, metadata, autoload_with=connection)
            for name in TABLE_NAMES if name in names}


def _rows(connection, table):
    return [dict(row) for row in connection.execute(select(table)).mappings()]


def _state(connection, tables):
    nodes = [row for row in _rows(connection, tables["curriculum_node"])
             if row["grade"] == "9" and row["chapter_code"] == "6"]
    counters = [row for row in _rows(connection, tables["id6_counter"])
                if row["scope"].startswith("9C6-")]
    return {"nodes": sorted(nodes, key=lambda row: row["id"]),
            "counters": sorted(counters, key=lambda row: row["scope"])}


def _question_codes(row, node_codes):
    codes = set()
    node_code = node_codes.get(row.get("curriculum_node_id"))
    if node_code:
        codes.add(node_code)
    if str(row.get("id6_scope") or "").startswith("9C6-"):
        codes.add(row["id6_scope"])
    grade = re.sub(r"^Lớp\s*", "", str(row.get("grade") or "").strip(), flags=re.I)
    if grade in ("9", "") and str(row.get("chapter") or "") == "6":
        if row.get("section") and row.get("question_category"):
            codes.add(f"9C6-{row['section']}-{row['question_category']}")
        else:
            codes.add("9C6-*")
    match = re.match(r"(?:%\[\s*)?9C6[NHVC?]([1-9]\d*)-([1-9]\d*)", str(row.get("source_id") or ""), re.I)
    if match:
        codes.add(f"9C6-{match[1]}-{match[2]}")
    return codes


def _references(connection, tables, state, affected_codes):
    node_codes = {row["id"]: row["canonical_code"] for row in state["nodes"]}
    all_questions = _rows(connection, tables["bank_question"])
    references = []
    for row in all_questions:
        codes = _question_codes(row, node_codes)
        if affected_codes and codes and ("9C6-*" in codes or codes & affected_codes):
            references.append({"question_id": row["id"], "bank_id": row["bank_id"],
                               "source_id": row.get("source_id"), "codes": sorted(codes),
                               "difficulty_level": row.get("difficulty_level")})
    legacy_refs = []
    if "question_skill" in tables:
        for row in _rows(connection, tables["question_skill"]):
            if node_codes.get(row.get("curriculum_node_id")) in affected_codes:
                legacy_refs.append(row)
    sessions = []
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    if affected_codes:
        for row in _rows(connection, tables["import_session"]):
            if row["status"] not in {"uploaded", "processing", "preview"}:
                continue
            expiry = row.get("expires_at")
            if isinstance(expiry, str):
                expiry = dt.datetime.fromisoformat(expiry)
            if expiry and expiry.tzinfo:
                expiry = expiry.astimezone(dt.timezone.utc).replace(tzinfo=None)
            if expiry and expiry <= now:
                continue
            # A pending file may still contain old tags; protect the entire
            # active import rather than guess from partially parsed JSON.
            sessions.append({"session_id": row["id"], "status": row["status"],
                             "filename": row["filename"]})
    return {"questions": references, "legacy_mappings": legacy_refs, "active_imports": sessions}


def _report(connection, tables):
    bundle = load_chapter6_bundle()
    before = _state(connection, tables)
    current = {row["canonical_code"]: row for row in before["nodes"]}
    old = {canonical_code(row): row for row in bundle.get("legacy", [])}
    changes, conflicts = [], []
    for target in bundle["rows"]:
        code = canonical_code(target)
        existing = current.get(code)
        desired = {**target, "canonical_code": code}
        if existing is None:
            changes.append({"code": code, "action": "insert", "before": None, "after": desired})
            continue
        same_content = all(existing.get(key) == desired[key] for key in CONTENT_FIELDS)
        known_legacy = (existing["catalog_version"] in {"math9-user-v2", "math9-v1"}
                        and all(existing.get(key) == old[code][key] for key in CONTENT_FIELDS))
        previous_topic = (("xac_suat", "Xác suất") if target["lesson_code"] == "4"
                          else ("thong_ke", "Thống kê"))
        known_previous_release = (
            same_content and existing["catalog_version"] == "math9-c6-v3"
            and (existing.get("topic_code"), existing.get("topic_name")) == previous_topic
        )
        known_target = (same_content and existing["catalog_version"] == CHAPTER6_VERSION) or known_previous_release
        if not known_legacy and not known_target:
            conflicts.append({"code": code, "node_id": existing["id"],
                              "reason": "Danh mục đã tùy chỉnh hoặc không khớp bản nguồn được hỗ trợ."})
            continue
        differing = {key: value for key, value in desired.items() if existing.get(key) != value}
        if differing:
            changes.append({"code": code, "node_id": existing["id"], "action": "update",
                            "before": existing, "after": desired})
    expected = {canonical_code(row) for row in bundle["rows"]}
    for code in sorted(set(current) - expected):
        conflicts.append({"code": code, "node_id": current[code]["id"],
                          "reason": "Dạng ngoài 8 mã Bài 4 chuẩn; cleanup phạm vi xử lý riêng, không tự tái seed."})
    affected = {change["code"] for change in changes}
    refs = _references(connection, tables, before, affected)
    blockers = []
    for key, items in (("custom_catalog", conflicts), ("referenced_questions", refs["questions"]),
                       ("legacy_mappings", refs["legacy_mappings"]), ("active_imports", refs["active_imports"])):
        if items:
            blockers.append({"kind": key, "count": len(items), "items": items})
    report = {"migration_key": CHAPTER6_MIGRATION, "catalog_version": CHAPTER6_VERSION,
              "status": "blocked" if blockers else "ready" if changes else "up_to_date",
              "counts": {"existing_nodes": len(current), "insert": sum(c["action"] == "insert" for c in changes),
                         "update": sum(c["action"] == "update" for c in changes),
                         "affected_questions": len(refs["questions"]),
                         "active_imports": len(refs["active_imports"]), "conflicts": len(conflicts)},
              "changes": changes, "blockers": blockers, "before": before,
              "transition": bundle.get("transition", {})}
    report["plan_fingerprint"] = _fingerprint(report)
    return report


def inspect_chapter6_migration(engine):
    """Read-only inventory: does not initialize the app, seed, or run DDL."""
    with engine.connect() as connection:
        return _report(connection, _tables(connection))


def _lock(connection):
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    elif connection.dialect.name == "postgresql":
        names = set(inspect(connection).get_table_names())
        lock_names = [name for name in TABLE_NAMES if name in names]
        if lock_names:
            connection.execute(text("LOCK TABLE " + ", ".join(lock_names) + " IN SHARE ROW EXCLUSIVE MODE"))
    else:
        raise ValueError("Chuyển danh mục chỉ hỗ trợ SQLite hoặc PostgreSQL.")


def _audit_table(connection):
    from models import CurriculumCatalogMigration
    table = CurriculumCatalogMigration.__table__
    table.create(connection, checkfirst=True)
    return table


def apply_chapter6_migration(engine, expected_fingerprint=None):
    with engine.connect() as connection, connection.begin():
        _lock(connection)
        tables = _tables(connection)
        report = _report(connection, tables)
        # Read an existing receipt without creating tables in blocked runs.
        receipt = None
        if inspect(connection).has_table("curriculum_catalog_migration"):
            audit = _audit_table(connection)
            receipt = connection.execute(select(audit).where(audit.c.migration_key == CHAPTER6_MIGRATION)).mappings().first()
        if receipt and receipt["status"] == "applied":
            report["status"] = "already_applied"
            return report
        if receipt and receipt["status"] == "rolled_back":
            report["blockers"].append({"kind": "previously_rolled_back", "count": 1,
                                       "items": ["Giữ lịch sử phục hồi; cần phiên migration mới để áp dụng lại."]})
        if expected_fingerprint and report["plan_fingerprint"] != expected_fingerprint:
            report["blockers"].append({"kind": "stale_plan", "count": 1, "items": ["Dữ liệu đã đổi sau lúc chạy thử."]})
        if report["blockers"]:
            report["status"] = "blocked"
            raise CatalogMigrationBlocked(report)
        if not report["changes"]:
            return report
        for name, sql_type in TOPIC_FIELDS.items():
            if name not in tables["curriculum_node"].c:
                connection.execute(text(f"ALTER TABLE curriculum_node ADD COLUMN {name} {sql_type}"))
        tables = _tables(connection)
        table = tables["curriculum_node"]
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        for change in report["changes"]:
            values = {**change["after"], "updated_at": now}
            if change["action"] == "insert":
                values.update(created_at=now, is_active=True, is_advanced=False)
                connection.execute(table.insert().values(**values))
            else:
                connection.execute(table.update().where(table.c.id == change["node_id"]).values(**values))
        after = _state(connection, tables)
        audit = _audit_table(connection)
        connection.execute(audit.insert().values(
            migration_key=CHAPTER6_MIGRATION, catalog_version=CHAPTER6_VERSION, status="applied",
            applied_at=now, snapshot_json=_json({"before": report["before"], "after": after,
                                                "changes": report["changes"], "transition": report["transition"]}),
            after_fingerprint=_fingerprint(after),
        ))
        report["status"] = "applied"
        report["after_fingerprint"] = _fingerprint(after)
        return report


def rollback_chapter6_migration(engine):
    """Restore only an unchanged migrated catalog with no new references."""
    with engine.connect() as connection, connection.begin():
        _lock(connection)
        tables = _tables(connection)
        if not inspect(connection).has_table("curriculum_catalog_migration"):
            raise ValueError("Không có bản chụp để phục hồi.")
        audit = _audit_table(connection)
        receipt = connection.execute(select(audit).where(audit.c.migration_key == CHAPTER6_MIGRATION)).mappings().first()
        if not receipt:
            raise ValueError("Không có bản chụp Chương 6 để phục hồi.")
        if receipt["status"] == "rolled_back":
            return {"status": "already_rolled_back", "migration_key": CHAPTER6_MIGRATION}
        current = _state(connection, tables)
        snapshot = json.loads(receipt["snapshot_json"])
        affected = {change["code"] for change in snapshot["changes"]}
        refs = _references(connection, tables, current, affected)
        blockers = [{"kind": key, "count": len(items), "items": items}
                    for key, items in refs.items() if items]
        if _fingerprint(current) != receipt["after_fingerprint"]:
            blockers.append({"kind": "changed_since_migration", "count": 1,
                             "items": ["Danh mục hoặc bộ đếm đã thay đổi; không ghi đè dữ liệu mới."]})
        if blockers:
            raise CatalogMigrationBlocked({"status": "blocked", "migration_key": CHAPTER6_MIGRATION,
                                           "blockers": blockers})
        table = tables["curriculum_node"]
        for change in snapshot["changes"]:
            if change["action"] == "insert":
                connection.execute(table.delete().where(table.c.canonical_code == change["code"]))
            else:
                values = dict(change["before"])
                for name in TOPIC_FIELDS:
                    values.setdefault(name, None)
                for name, value in list(values.items()):
                    if value is not None and isinstance(table.c[name].type, DateTime):
                        values[name] = dt.datetime.fromisoformat(value)
                connection.execute(table.update().where(table.c.id == change["node_id"]).values(**values))
        connection.execute(audit.update().where(audit.c.migration_key == CHAPTER6_MIGRATION).values(
            status="rolled_back", rolled_back_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)))
        return {"status": "rolled_back", "migration_key": CHAPTER6_MIGRATION,
                "restored_nodes": len(snapshot["changes"])}
