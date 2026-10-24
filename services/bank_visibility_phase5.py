"""Safe, offline historical backfill for question-bank visibility (Phase 5).

The application intentionally does not run this migration at startup.  A
reviewer first runs the CLI in its default dry-run mode, reviews the counts
and the database fingerprint, and only then supplies ``--apply`` with that
fingerprint.  The migration is deliberately conservative:

* a legacy ``NULL`` row whose current, persisted owner is a teacher becomes
  ``private``;
* a legacy ``NULL`` row whose current owner is an administrator is reported
  for review and stays ``NULL`` unless that exact bank id is explicitly passed
  as ``--shared-bank-id``;
* missing owners, unsupported owner roles, and malformed visibility values are
  never repaired by inference and remain fail-closed;
* explicit ``shared``/``private`` values are never rewritten.

Only the ``question_bank.visibility`` column is updated.  No rows are deleted,
owners are not transferred, and historical exams/submissions are untouched.
The module uses only the standard-library SQLite API; it never imports Flask,
loads dotenv files, or reads provider credentials.
"""

from __future__ import annotations

from contextlib import closing
import datetime as dt
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterable


BANK_TABLE = "question_bank"
USER_TABLE = "user"
BANK_VISIBILITY_PRIVATE = "private"
BANK_VISIBILITY_SHARED = "shared"
BANK_VISIBILITIES = frozenset({BANK_VISIBILITY_PRIVATE, BANK_VISIBILITY_SHARED})
PHASE5_SCHEMA_VERSION = "bank-visibility-phase5-v1"


class MigrationBlocked(ValueError):
    """Raised when a reviewed migration cannot safely proceed."""


def _quote(identifier: str) -> str:
    """Quote a SQLite identifier without accepting caller SQL."""

    return '"' + str(identifier).replace('"', '""') + '"'


def _path(path: str | Path) -> Path:
    """Resolve one existing, regular, non-symlink SQLite path."""

    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise ValueError("Database must be an existing regular file, not a symlink")
    if not candidate.is_file():
        raise ValueError("Database must be an existing regular file")
    return candidate.resolve()


def connect_readonly(path: str | Path) -> sqlite3.Connection:
    """Open an existing database in query-only mode.

    The ``mode=ro`` URI prevents a typo from creating a new database and
    ``query_only`` provides a second guard against accidental writes during a
    dry run.
    """

    database = _path(path)
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(" + _quote(table) + ")")
    }


def _json_default(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _stable(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def _digest(value) -> str:
    return hashlib.sha256(_stable(value).encode("utf-8")).hexdigest()


def _table_snapshot(connection: sqlite3.Connection) -> dict[str, dict[str, object]]:
    """Digest every user table without returning row values.

    The digest is used only as an optimistic-concurrency token and for the
    backup consistency check.  Raw question text and any other table values
    never enter the public dry-run report.
    """

    result: dict[str, dict[str, object]] = {}
    for table in sorted(_table_names(connection)):
        sql_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        schema = sql_row[0] if sql_row else None
        row_digests = []
        for row in connection.execute("SELECT * FROM " + _quote(table)):
            row_digests.append(_digest(list(row)))
        row_digests.sort()
        result[table] = {
            "schema": schema,
            "rows": len(row_digests),
            "digest": _digest(row_digests),
        }
    return result


def snapshot(connection: sqlite3.Connection) -> dict[str, dict[str, object]]:
    """Return a safe, metadata-only snapshot for audit tooling/tests."""

    return _table_snapshot(connection)


def fingerprint(state: dict) -> str:
    """Return a stable SHA-256 fingerprint for a safe snapshot."""

    return _digest(state)


def _question_bank_immutable_snapshot(connection: sqlite3.Connection) -> dict[int, str]:
    """Digest bank rows while deliberately excluding ``visibility``.

    This lets post-transaction verification prove that the migration changed
    only the intended column, including proving that ``created_by`` and all
    question-bank metadata stayed intact.
    """

    columns = [
        str(row[1])
        for row in connection.execute("PRAGMA table_info(" + _quote(BANK_TABLE) + ")")
    ]
    retained = [column for column in columns if column != "visibility"]
    result: dict[int, str] = {}
    select = "SELECT * FROM " + _quote(BANK_TABLE) + " ORDER BY id"
    for row in connection.execute(select):
        bank_id = _coerce_id(row[columns.index("id")])
        if bank_id is None:
            continue
        values = {
            column: row[columns.index(column)]
            for column in retained
        }
        result[bank_id] = _digest(values)
    return result


def _coerce_id(value) -> int | None:
    """Coerce a SQLite integer id conservatively; malformed values fail closed."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text or (text[0] in "+-" and not text[1:].isdigit()) or (text[0] not in "+-" and not text.isdigit()):
            return None
        try:
            return int(text)
        except ValueError:
            return None
    return None


def _normalize_shared_ids(shared_bank_ids: Iterable[int] | None) -> tuple[int, ...]:
    if shared_bank_ids is None:
        return ()
    normalized = set()
    for value in shared_bank_ids:
        parsed = _coerce_id(value)
        if parsed is None or parsed <= 0:
            raise ValueError("Shared-bank IDs must be positive integers")
        normalized.add(parsed)
    return tuple(sorted(normalized))


def _required_schema(connection: sqlite3.Connection) -> list[str]:
    tables = _table_names(connection)
    blockers: list[str] = []
    for table in (BANK_TABLE, USER_TABLE):
        if table not in tables:
            blockers.append("Missing required table: " + table)
    required_columns = {
        BANK_TABLE: {"id", "created_by", "visibility"},
        USER_TABLE: {"id", "role"},
    }
    for table, columns in required_columns.items():
        if table not in tables:
            continue
        absent = sorted(columns - _columns(connection, table))
        if absent:
            blockers.append(
                "Unexpected " + table + " schema; missing " + ", ".join(absent)
            )
    return blockers


def _preflight_blockers(connection: sqlite3.Connection) -> list[str]:
    """Check physical integrity before any plan can be applied."""

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


def _load_state(connection: sqlite3.Connection):
    users = {}
    for row in connection.execute(
        "SELECT id, role FROM " + _quote(USER_TABLE) + " ORDER BY id"
    ):
        user_id = _coerce_id(row[0])
        if user_id is not None:
            users[user_id] = row[1]

    banks = []
    for row in connection.execute(
        "SELECT id, created_by, visibility FROM " + _quote(BANK_TABLE) + " ORDER BY id"
    ):
        banks.append(
            {
                "id": _coerce_id(row[0]),
                "created_by": _coerce_id(row[1]),
                "visibility": row[2],
            }
        )
    return users, banks


def _owner_category(created_by: int | None, users: dict[int, object]) -> str:
    if created_by is None or created_by not in users:
        return "missing_owner"
    role = users[created_by]
    if role == "teacher":
        return "teacher"
    if role == "admin":
        return "admin"
    return "unsupported_role"


def _plan_has_changes(plan: dict) -> bool:
    return bool(plan.get("updates"))


def build_plan(
    connection: sqlite3.Connection,
    shared_bank_ids: Iterable[int] | None = None,
) -> dict[str, object]:
    """Build a deterministic, no-write backfill plan.

    ``shared_bank_ids`` is an explicit operator mapping.  It is accepted only
    for existing ``NULL`` rows with an existing current administrator owner.
    Passing an id for any other row creates a blocker, preventing accidental
    scope widening or an owner transfer.
    """

    requested_shared_ids = _normalize_shared_ids(shared_bank_ids)
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
                "bank_immutable_snapshot": {},
                "scope_by_id": {},
            },
        }

    users, banks = _load_state(connection)
    banks_by_id = {bank["id"]: bank for bank in banks if bank["id"] is not None}
    teacher_null_ids: list[int] = []
    admin_null_ids: list[int] = []
    missing_owner_ids: list[int] = []
    unsupported_role_ids: list[int] = []
    invalid_visibility_ids: list[int] = []
    explicit_shared_ids: list[int] = []
    explicit_private_ids: list[int] = []
    explicit_missing_owner_ids: list[int] = []
    explicit_unsupported_role_ids: list[int] = []

    for bank in banks:
        bank_id = bank["id"]
        if bank_id is None:
            blockers.append("Question-bank row has a malformed id")
            continue
        visibility = bank["visibility"]
        owner_category = _owner_category(bank["created_by"], users)
        if visibility is None:
            if owner_category == "teacher":
                teacher_null_ids.append(bank_id)
            elif owner_category == "admin":
                admin_null_ids.append(bank_id)
            elif owner_category == "missing_owner":
                missing_owner_ids.append(bank_id)
            else:
                unsupported_role_ids.append(bank_id)
        elif visibility == BANK_VISIBILITY_SHARED:
            explicit_shared_ids.append(bank_id)
            if owner_category == "missing_owner":
                explicit_missing_owner_ids.append(bank_id)
            elif owner_category == "unsupported_role":
                explicit_unsupported_role_ids.append(bank_id)
        elif visibility == BANK_VISIBILITY_PRIVATE:
            explicit_private_ids.append(bank_id)
            if owner_category == "missing_owner":
                explicit_missing_owner_ids.append(bank_id)
            elif owner_category == "unsupported_role":
                explicit_unsupported_role_ids.append(bank_id)
        else:
            # Keep the original malformed value in the database.  The public
            # report exposes ids/counts only, never arbitrary row content.
            invalid_visibility_ids.append(bank_id)

    mappings_to_shared: list[int] = []
    already_shared_ids: list[int] = []
    for requested_id in requested_shared_ids:
        bank = banks_by_id.get(requested_id)
        if bank is None:
            blockers.append("Requested shared mapping references missing bank: " + str(requested_id))
            continue
        visibility = bank["visibility"]
        owner_category = _owner_category(bank["created_by"], users)
        if visibility == BANK_VISIBILITY_SHARED:
            # Repeating an already-applied mapping is idempotent and safe.
            already_shared_ids.append(requested_id)
        elif visibility is None and owner_category == "admin":
            mappings_to_shared.append(requested_id)
        elif visibility is None and owner_category == "teacher":
            blockers.append("Cannot map teacher-owned NULL bank as shared: " + str(requested_id))
        elif visibility is None and owner_category == "missing_owner":
            blockers.append("Cannot map orphaned NULL bank as shared: " + str(requested_id))
        elif visibility is None:
            blockers.append("Cannot map NULL bank with unsupported owner role as shared: " + str(requested_id))
        elif visibility == BANK_VISIBILITY_PRIVATE:
            blockers.append("Cannot override explicit private bank: " + str(requested_id))
        else:
            blockers.append("Cannot map bank with invalid visibility: " + str(requested_id))

    mapped_set = set(mappings_to_shared)
    pending_admin_ids = sorted(set(admin_null_ids) - mapped_set)
    updates = [
        {"bank_id": bank_id, "from": None, "to": BANK_VISIBILITY_PRIVATE, "reason": "teacher_owner"}
        for bank_id in sorted(teacher_null_ids)
    ]
    updates.extend(
        {"bank_id": bank_id, "from": None, "to": BANK_VISIBILITY_SHARED, "reason": "explicit_admin_mapping"}
        for bank_id in sorted(mappings_to_shared)
    )

    counts = {
        "banks_before": len(banks),
        "null_before": sum(bank["visibility"] is None for bank in banks),
        "updates": len(updates),
        "teacher_null_to_private": len(teacher_null_ids),
        "admin_null_to_shared": len(mappings_to_shared),
        "admin_null_pending_review": len(pending_admin_ids),
        "admin_mapping_already_shared": len(already_shared_ids),
        "missing_owner_null": len(missing_owner_ids),
        "unsupported_role_null": len(unsupported_role_ids),
        "invalid_visibility": len(invalid_visibility_ids),
        "explicit_shared_preserved": len(explicit_shared_ids),
        "explicit_private_preserved": len(explicit_private_ids),
        "explicit_scope_missing_owner": len(explicit_missing_owner_ids),
        "explicit_scope_unsupported_role": len(explicit_unsupported_role_ids),
    }

    public_state = {
        "schema_version": PHASE5_SCHEMA_VERSION,
        "database_fingerprint": database_fingerprint,
        "counts": counts,
        "updates": updates,
        "preserved": {
            "explicit_shared_bank_ids": sorted(explicit_shared_ids),
            "explicit_private_bank_ids": sorted(explicit_private_ids),
            "missing_owner_null_bank_ids": sorted(missing_owner_ids),
            "unsupported_role_null_bank_ids": sorted(unsupported_role_ids),
            "invalid_visibility_bank_ids": sorted(invalid_visibility_ids),
            "explicit_scope_missing_owner_bank_ids": sorted(explicit_missing_owner_ids),
            "explicit_scope_unsupported_role_bank_ids": sorted(explicit_unsupported_role_ids),
        },
        "review": {
            "admin_null_pending_bank_ids": pending_admin_ids,
            "admin_mapping_bank_ids": sorted(mappings_to_shared),
            "already_shared_mapping_bank_ids": sorted(already_shared_ids),
        },
        "blockers": sorted(set(blockers)),
        "_internal": {
            "table_snapshot": table_state,
            "bank_immutable_snapshot": _question_bank_immutable_snapshot(connection),
            "scope_by_id": {
                bank["id"]: bank["visibility"]
                for bank in banks
                if bank["id"] is not None
            },
            "requested_shared_ids": requested_shared_ids,
        },
    }
    if public_state["blockers"]:
        public_state["status"] = "blocked"
    elif pending_admin_ids:
        # There may still be safe teacher-owned updates in this partial plan;
        # the status records that an operator review remains outstanding.
        public_state["status"] = "review_required"
    elif _plan_has_changes(public_state):
        public_state["status"] = "ready"
    else:
        public_state["status"] = "no_changes"
    return public_state


def public_plan(plan: dict) -> dict:
    """Strip internal snapshots before a report or manifest is written."""

    return {key: value for key, value in plan.items() if key != "_internal"}


def _apply_plan_in_transaction(connection: sqlite3.Connection, plan: dict) -> None:
    for update in plan.get("updates", []):
        bank_id = int(update["bank_id"])
        target = update["to"]
        if target not in BANK_VISIBILITIES:
            raise MigrationBlocked("Unexpected bank visibility in migration plan")
        result = connection.execute(
            "UPDATE " + _quote(BANK_TABLE) + " SET visibility=? "
            "WHERE id=? AND visibility IS NULL",
            (target, bank_id),
        )
        if result.rowcount != 1:
            raise MigrationBlocked("Bank changed before conversion; transaction rolled back")


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
    for table in before_tables:
        if table != BANK_TABLE and before_tables[table] != after_tables[table]:
            raise MigrationBlocked("Migration changed a table outside question_bank")

    if internal.get("bank_immutable_snapshot") != _question_bank_immutable_snapshot(connection):
        raise MigrationBlocked("Migration changed bank metadata or ownership")

    before_scopes = internal.get("scope_by_id") or {}
    rows = {
        _coerce_id(row[0]): row[1]
        for row in connection.execute(
            "SELECT id, visibility FROM " + _quote(BANK_TABLE) + " ORDER BY id"
        )
    }
    if set(rows) != set(before_scopes):
        raise MigrationBlocked("Migration deleted or created a question bank")
    expected_updates = {
        int(item["bank_id"]): item["to"]
        for item in plan.get("updates", [])
    }
    for bank_id, old_scope in before_scopes.items():
        expected_scope = expected_updates.get(bank_id, old_scope)
        if rows.get(bank_id) != expected_scope:
            raise MigrationBlocked("Question-bank visibility invariant failed")


def _backup_database(source: sqlite3.Connection, backup_path: Path, expected_fingerprint: str) -> None:
    """Create and verify one recoverable SQLite backup before the writer lock."""

    if backup_path.exists() or backup_path.is_symlink():
        raise ValueError("Backup path already exists")
    backup_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with backup_path.open("xb"):
        pass
    backup_path.chmod(0o600)
    with closing(sqlite3.connect(str(backup_path))) as destination:
        destination.execute("PRAGMA foreign_keys=ON")
        source.backup(destination)
        destination.commit()
    with closing(connect_readonly(backup_path)) as saved:
        if saved.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup integrity check failed")
        if saved.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Backup foreign-key check failed")
        if fingerprint(_table_snapshot(saved)) != expected_fingerprint:
            raise ValueError("Backup does not match the reviewed database")


def apply_plan(
    database: str | Path,
    backup: str | Path,
    expected_fingerprint: str,
    shared_bank_ids: Iterable[int] | None = None,
) -> dict[str, object]:
    """Backup then apply a reviewed plan to one explicit SQLite file.

    The fingerprint verifies the database snapshot, not the operator mapping.
    The operator must separately review the explicit shared-bank IDs. A stale
    fingerprint, a blocker, or any failed
    invariant aborts before commit and leaves the live database unchanged.
    """

    database_path = _path(database)
    backup_candidate = Path(backup).expanduser()
    if backup_candidate.is_symlink():
        raise ValueError("Backup must be a new regular path, not a symlink")
    backup_path = backup_candidate.resolve()
    if backup_path == database_path:
        raise ValueError("Backup path must differ from the database path")

    with closing(connect_readonly(database_path)) as source:
        plan = build_plan(source, shared_bank_ids)
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

    live_uri = database_path.as_uri() + "?mode=rw"
    live = sqlite3.connect(live_uri, uri=True, timeout=30)
    live.row_factory = sqlite3.Row
    live.execute("PRAGMA foreign_keys=ON")
    live.execute("PRAGMA busy_timeout=30000")
    try:
        live.execute("BEGIN IMMEDIATE")
        current = build_plan(live, shared_bank_ids)
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
        after_plan = build_plan(after, shared_bank_ids)
    return {
        "status": "applied",
        "backup": str(backup_path),
        "counts": plan["counts"],
        "review": after_plan["review"],
        "database_fingerprint_before": plan["database_fingerprint"],
        "database_fingerprint_after": after_plan["database_fingerprint"],
        "after_status": after_plan["status"],
    }
