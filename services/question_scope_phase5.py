"""Offline, conservative backfill for legacy bank-question scope.

The application deliberately leaves legacy ``bank_question.scope`` values
NULL.  This module builds an operator-reviewed plan without creating the
Flask app or loading an application environment.  Its classification is
delegated to the same
``resolve_question_source`` policy used at runtime, using lightweight objects
populated from SQLite.  Only ``scope`` and ``private_owner_id`` may change.
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from services.access_control import resolve_question_source
from services.bank_visibility_phase5 import (
    _backup_database,
    _coerce_id,
    _columns,
    _digest,
    _path,
    _quote,
    _table_names,
    _table_snapshot,
    connect_readonly,
    fingerprint,
)


USER_TABLE = "user"
BANK_TABLE = "question_bank"
QUESTION_TABLE = "bank_question"
QUESTION_SCOPE_PRIVATE = "private"
QUESTION_SCOPE_SHARED = "shared"
QUESTION_SCOPES = frozenset({QUESTION_SCOPE_PRIVATE, QUESTION_SCOPE_SHARED})
PHASE5_SCHEMA_VERSION = "question-scope-phase5-v1"
MUTABLE_COLUMNS = frozenset({"scope", "private_owner_id"})


class MigrationBlocked(ValueError):
    """Raised when a reviewed migration cannot safely proceed."""


def snapshot(connection: sqlite3.Connection) -> dict[str, dict[str, object]]:
    """Return the shared metadata-only snapshot used by the fingerprint."""

    return _table_snapshot(connection)


def _related_actor(users: dict[int, SimpleNamespace], value):
    """Return a loaded actor or a non-authorizing sentinel.

    ``resolve_question_source`` normally performs a lazy SQLAlchemy lookup
    when a relationship is absent.  The migration must never let that lookup
    escape into a different application/session database, so missing or
    malformed references are represented by an explicit unsupported actor.
    """

    if value is None:
        return None
    user_id = _coerce_id(value)
    if user_id is not None and user_id in users:
        return users[user_id]
    return SimpleNamespace(id=user_id if user_id is not None else value, role=None)


def _question_immutable_snapshot(connection: sqlite3.Connection) -> dict[int, str]:
    """Digest question rows excluding the two columns this migration owns."""

    columns = [
        str(row[1])
        for row in connection.execute("PRAGMA table_info(" + _quote(QUESTION_TABLE) + ")")
    ]
    retained = [column for column in columns if column not in MUTABLE_COLUMNS]
    if "id" not in columns:
        return {}
    rows = {}
    for row in connection.execute("SELECT * FROM " + _quote(QUESTION_TABLE) + " ORDER BY id"):
        question_id = _coerce_id(row[columns.index("id")])
        if question_id is None:
            continue
        rows[question_id] = _digest({
            column: row[columns.index(column)] for column in retained
        })
    return rows


def _required_schema(connection: sqlite3.Connection) -> list[str]:
    tables = _table_names(connection)
    blockers: list[str] = []
    required_columns = {
        USER_TABLE: {"id", "role"},
        BANK_TABLE: {"id", "created_by", "visibility"},
        QUESTION_TABLE: {"id", "bank_id", "created_by", "scope", "private_owner_id"},
    }
    for table in required_columns:
        if table not in tables:
            blockers.append("Missing required table: " + table)
            continue
        absent = sorted(required_columns[table] - _columns(connection, table))
        if absent:
            blockers.append(
                "Unexpected " + table + " schema; missing " + ", ".join(absent)
            )
    return blockers


def _preflight_blockers(connection: sqlite3.Connection) -> list[str]:
    blockers = _required_schema(connection)
    if blockers:
        return blockers
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError:
        blockers.append("SQLite integrity check could not be completed")
    else:
        if integrity != "ok":
            blockers.append("SQLite integrity check failed")
    try:
        foreign_key = connection.execute("PRAGMA foreign_key_check").fetchone()
    except sqlite3.DatabaseError:
        blockers.append("SQLite foreign-key check could not be completed")
    else:
        if foreign_key:
            blockers.append("SQLite foreign-key check failed")
    return blockers


def _load_objects(connection: sqlite3.Connection):
    users: dict[int, SimpleNamespace] = {}
    for row in connection.execute(
        "SELECT id, role FROM " + _quote(USER_TABLE) + " ORDER BY id"
    ):
        user_id = _coerce_id(row[0])
        if user_id is not None:
            users[user_id] = SimpleNamespace(id=user_id, role=row[1])

    banks: dict[int, SimpleNamespace] = {}
    for row in connection.execute(
        "SELECT id, created_by, visibility FROM " + _quote(BANK_TABLE) + " ORDER BY id"
    ):
        bank_id = _coerce_id(row[0])
        if bank_id is None:
            continue
        created_by = _coerce_id(row[1])
        banks[bank_id] = SimpleNamespace(
            id=bank_id,
            created_by=created_by,
            visibility=row[2],
            creator=_related_actor(users, row[1]),
            is_active=True,
        )

    questions = []
    for row in connection.execute(
        "SELECT id, bank_id, created_by, scope, private_owner_id FROM "
        + _quote(QUESTION_TABLE) + " ORDER BY id"
    ):
        question_id = _coerce_id(row[0])
        bank_id = _coerce_id(row[1])
        created_by = _coerce_id(row[2])
        raw_owner_id = row[4]
        owner_id = _coerce_id(raw_owner_id) if raw_owner_id is not None else None
        questions.append({
            "id": question_id,
            "bank_id": bank_id,
            "created_by": created_by,
            "scope": row[3],
            # Keep malformed/non-integer values visible to the central
            # resolver.  Collapsing them to NULL would incorrectly turn a
            # corrupt owner reference into a legacy creator fallback.
            "private_owner_id": raw_owner_id,
            "bank": banks.get(bank_id) or SimpleNamespace(
                id=bank_id, created_by=None, visibility="__missing__",
                creator=None, is_active=True, _missing=True,
            ),
            "creator": _related_actor(users, row[2]),
            "private_owner": _related_actor(users, raw_owner_id),
        })
    return users, banks, questions


def _legacy_reason(question: dict) -> str:
    """Give operators a stable, conservative reason for an unknown legacy row."""

    bank = question.get("bank")
    if bank is None:
        return "bank_missing"
    if getattr(bank, "_missing", False):
        return "bank_missing"
    bank_creator = getattr(bank, "creator", None)
    if bank_creator is None:
        return "bank_owner_missing"
    visibility = getattr(bank, "visibility", None)
    if visibility not in ("private", "shared", None):
        return "bank_visibility_invalid"
    owner_id = question.get("private_owner_id")
    private_owner = question.get("private_owner")
    if owner_id is not None and private_owner is None:
        return "private_owner_missing"
    if private_owner is not None and getattr(private_owner, "role", None) != "teacher":
        return "private_owner_not_teacher"
    if visibility in ("private", None) and getattr(bank_creator, "role", None) != "teacher":
        return "private_bank_owner_not_teacher"
    if visibility is None:
        return "legacy_admin_or_unsupported_bank"
    creator = question.get("creator")
    if creator is None:
        return "question_creator_missing"
    if getattr(creator, "role", None) not in ("admin", "teacher"):
        return "question_creator_unsupported"
    if visibility == "shared" and getattr(creator, "role", None) == "admin":
        if getattr(creator, "id", None) != getattr(bank_creator, "id", None):
            return "shared_admin_creator_mismatch"
    if visibility == "shared" and private_owner is not None:
        return "shared_private_owner_unresolved"
    return "legacy_source_unknown"


def _update_reason(question: dict, source: dict) -> str:
    bank = question.get("bank")
    if source.get("key") == "common":
        return "legacy_shared_bank_admin_creator"
    if getattr(bank, "visibility", None) == "shared":
        if question.get("private_owner_id") is not None:
            return "legacy_shared_bank_private_owner"
        return "legacy_shared_bank_teacher_creator"
    if getattr(bank, "visibility", None) == "private":
        return "legacy_private_bank_owner"
    return "legacy_teacher_owned_legacy_bank"


def _scope_is_explicit(value) -> bool:
    return value is not None


def _plan_has_changes(plan: dict) -> bool:
    return bool(plan.get("updates"))


def build_plan(connection: sqlite3.Connection) -> dict[str, object]:
    """Build a deterministic, no-write question-scope backfill plan.

    The resolver is the sole classifier.  In particular, a row is never
    promoted to ``shared`` merely because a creator currently has an admin
    role: it must be the explicit legacy-shared shape accepted by the central
    policy (an admin-created question in that same explicit shared bank).
    """

    table_state = _table_snapshot(connection)
    database_fingerprint = fingerprint(table_state)
    blockers = _preflight_blockers(connection)
    if blockers:
        return {
            "schema_version": PHASE5_SCHEMA_VERSION,
            "database_fingerprint": database_fingerprint,
            "counts": {},
            "updates": [],
            "preserved": {},
            "review": {},
            "blockers": sorted(set(blockers)),
            "status": "blocked",
            "_internal": {
                "table_snapshot": table_state,
                "question_schema": None,
                "question_immutable_snapshot": {},
                "scope_by_id": {},
            },
        }

    _users, _banks, rows = _load_objects(connection)
    explicit_shared_ids: list[int] = []
    explicit_private_ids: list[int] = []
    explicit_invalid_ids: list[int] = []
    explicit_incompatible_ids: list[int] = []
    ambiguous_ids: list[int] = []
    ambiguous_reasons: dict[str, str] = {}
    updates: list[dict[str, object]] = []
    blockers = []
    scope_by_id: dict[int, tuple[object, object]] = {}

    for question in rows:
        question_id = question["id"]
        if question_id is None or question_id <= 0:
            blockers.append("Bank-question row has a malformed id")
            continue
        scope = question["scope"]
        owner_id = question["private_owner_id"]
        scope_by_id[question_id] = (scope, owner_id)

        # Existing values are authoritative, even when inconsistent.  The
        # migration reports them but never rewrites an explicit row.
        if _scope_is_explicit(scope):
            if scope == QUESTION_SCOPE_SHARED:
                explicit_shared_ids.append(question_id)
            elif scope == QUESTION_SCOPE_PRIVATE:
                explicit_private_ids.append(question_id)
            else:
                explicit_invalid_ids.append(question_id)
            source = resolve_question_source(
                SimpleNamespace(
                    id=question_id,
                    bank_id=question["bank_id"],
                    created_by=question["created_by"],
                    scope=scope,
                    private_owner_id=owner_id,
                    bank=question["bank"],
                    creator=question["creator"],
                    private_owner=question["private_owner"],
                )
            )
            if source.get("key") == "unknown":
                explicit_incompatible_ids.append(question_id)
            continue

        source_question = SimpleNamespace(
            id=question_id,
            bank_id=question["bank_id"],
            created_by=question["created_by"],
            scope=None,
            private_owner_id=owner_id,
            bank=question["bank"],
            creator=question["creator"],
            private_owner=question["private_owner"],
        )
        source = resolve_question_source(source_question)
        if source.get("key") == "common":
            updates.append({
                "question_id": question_id,
                "bank_id": question["bank_id"],
                "scope_from": None,
                "scope_to": QUESTION_SCOPE_SHARED,
                "private_owner_from": owner_id,
                "private_owner_to": None,
                "reason": _update_reason(question, source),
            })
        elif source.get("key") == "private":
            target_owner = _coerce_id(source.get("owner_id"))
            if target_owner is None:
                # The central resolver normally guarantees a real teacher
                # owner.  Keep an extra guard here because this is a write
                # boundary fed by untrusted SQLite values.
                ambiguous_ids.append(question_id)
                ambiguous_reasons[str(question_id)] = "private_owner_unresolved"
                continue
            updates.append({
                "question_id": question_id,
                "bank_id": question["bank_id"],
                "scope_from": None,
                "scope_to": QUESTION_SCOPE_PRIVATE,
                "private_owner_from": owner_id,
                "private_owner_to": target_owner,
                "reason": _update_reason(question, source),
            })
        else:
            ambiguous_ids.append(question_id)
            ambiguous_reasons[str(question_id)] = _legacy_reason(question)

    question_columns = _columns(connection, QUESTION_TABLE)
    question_schema = next(
        (
            value["schema"]
            for key, value in table_state.items()
            if key == QUESTION_TABLE
        ),
        None,
    )
    counts = {
        "questions_before": len(rows),
        "null_scope_before": sum(row["scope"] is None for row in rows),
        "updates": len(updates),
        "null_to_private": sum(item["scope_to"] == QUESTION_SCOPE_PRIVATE for item in updates),
        "null_to_shared": sum(item["scope_to"] == QUESTION_SCOPE_SHARED for item in updates),
        "ambiguous_null": len(ambiguous_ids),
        "explicit_shared_preserved": len(explicit_shared_ids),
        "explicit_private_preserved": len(explicit_private_ids),
        "explicit_invalid_scope_preserved": len(explicit_invalid_ids),
        "explicit_incompatible_preserved": len(explicit_incompatible_ids),
    }
    public = {
        "schema_version": PHASE5_SCHEMA_VERSION,
        "database_fingerprint": database_fingerprint,
        "counts": counts,
        "updates": updates,
        "preserved": {
            "explicit_shared_question_ids": sorted(explicit_shared_ids),
            "explicit_private_question_ids": sorted(explicit_private_ids),
            "explicit_invalid_scope_question_ids": sorted(explicit_invalid_ids),
            "explicit_incompatible_question_ids": sorted(explicit_incompatible_ids),
        },
        "review": {
            "ambiguous_question_ids": sorted(ambiguous_ids),
            "ambiguous_reasons": {
                str(question_id): ambiguous_reasons[str(question_id)]
                for question_id in sorted(ambiguous_ids)
            },
        },
        "blockers": sorted(set(blockers)),
        "_internal": {
            "table_snapshot": table_state,
            "question_schema": question_schema,
            "question_columns": sorted(question_columns),
            "question_immutable_snapshot": _question_immutable_snapshot(connection),
            "scope_by_id": scope_by_id,
        },
    }
    if public["blockers"]:
        public["status"] = "blocked"
    elif ambiguous_ids or explicit_invalid_ids or explicit_incompatible_ids:
        # Safe rows may still be applied in a reviewed partial rollout, while
        # unresolved rows remain visible in the report for later repair.
        public["status"] = "review_required"
    elif _plan_has_changes(public):
        public["status"] = "ready"
    else:
        public["status"] = "no_changes"
    return public


def public_plan(plan: dict) -> dict:
    return {key: value for key, value in plan.items() if key != "_internal"}


def _apply_plan_in_transaction(connection: sqlite3.Connection, plan: dict) -> None:
    for update in plan.get("updates", []):
        question_id = _coerce_id(update.get("question_id"))
        target_scope = update.get("scope_to")
        target_owner = update.get("private_owner_to")
        if question_id is None or target_scope not in QUESTION_SCOPES:
            raise MigrationBlocked("Unexpected question-scope migration plan")
        if target_scope == QUESTION_SCOPE_SHARED and target_owner is not None:
            raise MigrationBlocked("Shared question cannot carry a private owner")
        if target_scope == QUESTION_SCOPE_PRIVATE and _coerce_id(target_owner) is None:
            raise MigrationBlocked("Private question requires a teacher owner")
        result = connection.execute(
            "UPDATE " + _quote(QUESTION_TABLE) + " SET scope=?, private_owner_id=? "
            "WHERE id=? AND scope IS NULL AND private_owner_id IS ?",
            (target_scope, target_owner, question_id, update.get("private_owner_from")),
        )
        if result.rowcount != 1:
            raise MigrationBlocked("Bank-question changed before conversion; transaction rolled back")


def _verify_invariants(connection: sqlite3.Connection, plan: dict) -> None:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise MigrationBlocked("SQLite integrity check failed after migration")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise MigrationBlocked("SQLite foreign-key check failed after migration")

    internal = plan.get("_internal") or {}
    before_tables = internal.get("table_snapshot") or {}
    after_tables = _table_snapshot(connection)
    if set(before_tables) != set(after_tables):
        raise MigrationBlocked("Migration changed the table set")
    before_question = before_tables.get(QUESTION_TABLE) or {}
    after_question = after_tables.get(QUESTION_TABLE) or {}
    if before_question.get("schema") != after_question.get("schema"):
        raise MigrationBlocked("Migration changed the bank-question schema")
    for table in before_tables:
        if table != QUESTION_TABLE and before_tables[table] != after_tables[table]:
            raise MigrationBlocked("Migration changed a table outside bank_question")
    if internal.get("question_immutable_snapshot") != _question_immutable_snapshot(connection):
        raise MigrationBlocked("Migration changed bank-question data outside scope columns")

    before_scopes = internal.get("scope_by_id") or {}
    columns = [
        str(row[1])
        for row in connection.execute("PRAGMA table_info(" + _quote(QUESTION_TABLE) + ")")
    ]
    id_index = columns.index("id")
    scope_index = columns.index("scope")
    owner_index = columns.index("private_owner_id")
    rows = {
        _coerce_id(row[id_index]): (row[scope_index], row[owner_index])
        for row in connection.execute("SELECT * FROM " + _quote(QUESTION_TABLE) + " ORDER BY id")
    }
    if set(rows) != set(before_scopes):
        raise MigrationBlocked("Migration deleted or created a bank-question row")
    expected_updates = {
        _coerce_id(item["question_id"]): (
            item["scope_to"], _coerce_id(item.get("private_owner_to"))
        )
        for item in plan.get("updates", [])
    }
    for question_id, old_state in before_scopes.items():
        expected_state = expected_updates.get(question_id, old_state)
        if rows.get(question_id) != expected_state:
            raise MigrationBlocked("Bank-question scope invariant failed")


def apply_plan(
    database: str | Path,
    backup: str | Path,
    expected_fingerprint: str,
) -> dict[str, object]:
    """Backup then apply one reviewed plan; no-op replays create no backup."""

    database_path = _path(database)
    backup_candidate = Path(backup).expanduser()
    if backup_candidate.is_symlink():
        raise ValueError("Backup must be a new regular path, not a symlink")
    backup_path = backup_candidate.resolve()
    if backup_path == database_path:
        raise ValueError("Backup path must differ from the database path")

    with closing(connect_readonly(database_path)) as source:
        plan = build_plan(source)
        if plan["blockers"]:
            raise ValueError("Migration blocked; run the dry-run report")
        if str(plan["database_fingerprint"]) != str(expected_fingerprint):
            raise ValueError("Database changed; run a fresh dry-run")
        if not _plan_has_changes(plan):
            return {
                "status": plan["status"],
                "database_fingerprint": plan["database_fingerprint"],
                "counts": plan["counts"],
                "review": plan["review"],
            }
        _backup_database(source, backup_path, str(plan["database_fingerprint"]))

    live = sqlite3.connect(database_path.as_uri() + "?mode=rw", uri=True, timeout=30)
    live.row_factory = sqlite3.Row
    live.execute("PRAGMA foreign_keys=ON")
    live.execute("PRAGMA busy_timeout=30000")
    try:
        live.execute("BEGIN IMMEDIATE")
        current = build_plan(live)
        if current["blockers"] or str(current["database_fingerprint"]) != str(expected_fingerprint):
            raise ValueError("Database changed before conversion; transaction rolled back")
        _apply_plan_in_transaction(live, current)
        _verify_invariants(live, current)
        live.commit()
    except Exception:
        live.rollback()
        raise
    finally:
        live.close()

    with closing(connect_readonly(database_path)) as after:
        after_plan = build_plan(after)
    return {
        "status": "applied",
        "backup": str(backup_path),
        "counts": plan["counts"],
        "review": after_plan["review"],
        "database_fingerprint_before": plan["database_fingerprint"],
        "database_fingerprint_after": after_plan["database_fingerprint"],
        "after_status": after_plan["status"],
    }
