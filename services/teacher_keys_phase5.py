"""Safe, offline migration for teacher-owned Gemini credentials (Phase 5).

The application deliberately does not run this migration at startup.  The
module only uses the Python SQLite API and never imports Flask, loads an
environment file, decrypts a credential, or serializes a credential value.

``build_plan`` is read-only and returns counts/identifiers plus a fingerprint
of the database state.  ``apply_plan`` requires that exact fingerprint,
creates a recoverable SQLite backup with ``Connection.backup`` first, and
performs the conversion inside ``BEGIN IMMEDIATE``.  A failed invariant check
rolls the transaction back; the backup is left in place for recovery.

The effective runtime group after conversion is one deterministic group per
teacher: the lowest-id default, otherwise the lowest-id internal default,
otherwise the lowest-id existing group.  Historical report references keep a
non-canonical group row as an inactive archive.  Unreferenced redundant
groups are removed after their keys have been merged.  Report rows and their
stored model/configuration values are never rewritten.
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import closing
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sqlite3


FIXED_MODEL = "gemini-3.8-flash"
INTERNAL_GROUP_NAME = "__teacher_internal_default__"
PHASE5_SCHEMA_VERSION = "teacher-keys-phase5-v1"

GROUP_TABLE = "teacher_ai_key_group"
KEY_TABLE = "teacher_ai_key"
COURSE_TABLE = "course"
USER_TABLE = "user"

_HEX = re.compile(r"^[0-9a-fA-F]+$")


class MigrationBlocked(ValueError):
    """Raised when the local schema/data needs an explicit review."""


def _quote(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def _path(path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise ValueError("Database must be an existing regular file, not a symlink")
    if not candidate.is_file():
        raise ValueError("Database must be an existing regular file")
    return candidate.resolve()


def connect_readonly(path):
    """Open an existing SQLite database in query-only mode.

    The URI is built from an explicitly resolved regular file.  This avoids a
    migration accidentally following a symlink or creating a new database.
    """

    database = _path(path)
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _table_names(connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _columns(connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(" + _quote(table) + ")")
    }


def _json_default(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value)


def _stable(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def _digest(value) -> str:
    return hashlib.sha256(_stable(value).encode("utf-8")).hexdigest()


def _table_snapshot(connection) -> dict[str, dict[str, object]]:
    """Digest table contents without returning row values.

    The row digest may include encrypted material in memory, but the digest is
    the only value retained in the result.  This makes fingerprints useful for
    optimistic concurrency checks without leaking a raw or encrypted key.
    """

    result = {}
    for table in sorted(_table_names(connection)):
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        row_digests = []
        for row in connection.execute("SELECT * FROM " + _quote(table)):
            row_digests.append(_digest(list(row)))
        row_digests.sort()
        result[table] = {
            "schema": sql,
            "rows": len(row_digests),
            "digest": _digest(row_digests),
        }
    return result


def snapshot(connection) -> dict[str, dict[str, object]]:
    """Public safe database snapshot used by tests and audit tooling."""

    return _table_snapshot(connection)


def fingerprint(state: dict) -> str:
    """Return a stable state fingerprint; ``state`` must contain no secrets."""

    return _digest(state)


def _safe_group(row) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "owner_id": int(row["owner_id"]),
        "name": str(row["name"] or ""),
        "model_name": str(row["model_name"] or ""),
        "is_active": bool(row["is_active"]),
        "is_default": bool(row["is_default"]),
        "config_revision": int(row["config_revision"] or 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _safe_key(row) -> dict[str, object]:
    """Copy non-secret key metadata for planning.

    ``encrypted_key`` is intentionally represented only by a digest.  No
    report or CLI output should ever contain the ciphertext.
    """

    fingerprint_value = str(row["key_fingerprint"] or "")
    return {
        "id": int(row["id"]),
        "group_id": int(row["group_id"]),
        "key_fingerprint": fingerprint_value,
        "encrypted_digest": _digest(str(row["encrypted_key"] or "")),
        "key_hint_present": bool(str(row["key_hint"] or "")),
        "project_ref": str(row["project_ref"] or "default").strip() or "default",
        "label_present": bool(str(row["label"] or "")),
        "sort_order": int(row["sort_order"] or 0),
        "is_paused": bool(row["is_paused"]),
        "last_tested_at": row["last_tested_at"],
        "last_test_status": row["last_test_status"],
        "last_error_code": row["last_error_code"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _date_sort(value):
    if value is None:
        return ""
    return str(value)


def _group_sort(group: dict[str, object]):
    # Phase 3's runtime resolver uses id ASC.  Use that exact rule here so
    # migration and runtime cannot disagree when timestamps were backfilled.
    return int(group["id"])


def _key_sort(key: dict[str, object]):
    return (
        _date_sort(key.get("created_at")),
        int(key["id"]),
    )


def _canonical_group(groups: list[dict[str, object]]) -> dict[str, object] | None:
    if not groups:
        return None
    defaults = [row for row in groups if row["is_default"]]
    if defaults:
        return min(defaults, key=_group_sort)
    internal = [row for row in groups if row["name"] == INTERNAL_GROUP_NAME]
    if internal:
        return min(internal, key=_group_sort)
    return min(groups, key=_group_sort)


def _status_severity(status):
    # A duplicate with no successful proof is never allowed to turn an
    # otherwise eligible key into an eligible key.  Unknown/unverified is the
    # most restrictive state; failed/deferred remain non-eligible as well.
    return {"ok": 0, "deferred": 1, "failed": 2, None: 3, "": 3}.get(status, 3)


def _operation_key_sort(key, groups_by_id):
    group = groups_by_id[int(key["group_id"])]
    # Canonical keys stay ahead of imported keys, retaining the Phase 4 queue
    # semantics.  Remaining ties are stable by source group/key id.
    return (
        0 if group.get("_canonical") else 1,
        int(key["group_id"]),
        int(key.get("sort_order") or 0),
        int(key["id"]),
    )


def _required_schema(connection) -> list[str]:
    tables = _table_names(connection)
    required = {GROUP_TABLE, KEY_TABLE, USER_TABLE, COURSE_TABLE}
    missing = sorted(required - tables)
    blockers = []
    if missing:
        blockers.append("Missing teacher-key table(s): " + ", ".join(missing))
    required_columns = {
        GROUP_TABLE: {"id", "owner_id", "name", "model_name", "is_active", "is_default", "config_revision"},
        KEY_TABLE: {
            "id", "group_id", "encrypted_key", "key_fingerprint", "key_hint", "project_ref",
            "sort_order", "is_paused", "last_tested_at", "last_test_status", "last_error_code",
        },
        USER_TABLE: {"id"},
        COURSE_TABLE: {"id", "teacher_id", "ai_key_group_id"},
    }
    for table, columns in required_columns.items():
        if table in tables:
            absent = sorted(columns - _columns(connection, table))
            if absent:
                blockers.append("Unexpected " + table + " schema; missing " + ", ".join(absent))
    return blockers


def _report_references(connection, group_ids: set[int]) -> dict[str, dict[int, list[int]]]:
    """Find every historical table carrying an ai_key_group_id column."""

    refs: dict[str, dict[int, list[int]]] = {}
    for table in sorted(_table_names(connection)):
        if table in {GROUP_TABLE, KEY_TABLE, COURSE_TABLE}:
            continue
        if "ai_key_group_id" not in _columns(connection, table):
            continue
        table_refs: dict[int, list[int]] = defaultdict(list)
        columns = _columns(connection, table)
        id_column = "id" if "id" in columns else None
        select_columns = "ai_key_group_id" + (", id" if id_column else "")
        for row in connection.execute("SELECT " + select_columns + " FROM " + _quote(table)):
            group_id = row[0]
            if group_id is None:
                continue
            try:
                group_id = int(group_id)
            except (TypeError, ValueError):
                continue
            if group_id in group_ids:
                table_refs[group_id].append(int(row[1]) if id_column and row[1] is not None else 0)
        if table_refs:
            refs[table] = {group_id: sorted(ids) for group_id, ids in sorted(table_refs.items())}
    return refs


def _build_internal_state(connection):
    groups = [
        _safe_group(row)
        for row in connection.execute("SELECT * FROM " + _quote(GROUP_TABLE) + " ORDER BY id ASC")
    ]
    keys = [
        _safe_key(row)
        for row in connection.execute("SELECT * FROM " + _quote(KEY_TABLE) + " ORDER BY id ASC")
    ]
    owners = {int(row["id"]) for row in connection.execute("SELECT id FROM " + _quote(USER_TABLE))}
    courses = [
        {"id": int(row["id"]), "teacher_id": row["teacher_id"], "ai_key_group_id": row["ai_key_group_id"]}
        for row in connection.execute("SELECT id,teacher_id,ai_key_group_id FROM " + _quote(COURSE_TABLE) + " ORDER BY id ASC")
        if row["ai_key_group_id"] is not None
    ]
    group_ids = {int(row["id"]) for row in groups}
    refs = _report_references(connection, group_ids)
    return {
        "groups": groups,
        "keys": keys,
        "owner_ids": owners,
        "courses": courses,
        "report_references": refs,
    }


def _public_group_plan(item):
    return {
        key: item[key]
        for key in (
            "owner_id", "canonical_group_id", "group_ids", "archive_group_ids", "delete_group_ids",
            "model_update", "default_updates", "key_moves", "key_deletes", "key_updates", "key_conflicts",
            "mapping_course_ids", "mapping_owner_mismatches", "historical_references",
        )
        if key in item
    }


def _plan_has_changes(plan: dict) -> bool:
    return bool(
        plan["counts"].get("groups_to_archive")
        or plan["counts"].get("groups_to_delete")
        or plan["counts"].get("keys_to_move")
        or plan["counts"].get("keys_to_delete")
        or plan["counts"].get("keys_to_update")
        or plan["counts"].get("course_mappings_to_clear")
        or plan["counts"].get("groups_to_set_default")
        or plan["counts"].get("groups_to_fix_model")
    )


def build_plan(connection) -> dict[str, object]:
    """Build a deterministic, no-write Phase 5 conversion plan.

    The returned dictionary is safe to print.  It contains no key hints,
    fingerprints, ciphertext, project labels, request data, or environment
    values.
    """

    blockers = _required_schema(connection)
    state = _build_internal_state(connection) if not blockers else {
        "groups": [], "keys": [], "owner_ids": set(), "courses": [], "report_references": {},
    }
    groups = state["groups"]
    keys = state["keys"]
    groups_by_id = {int(row["id"]): row for row in groups}
    for row in groups:
        row["_canonical"] = False

    for key in keys:
        if int(key["group_id"]) not in groups_by_id:
            blockers.append("Key references missing group")
        if not str(key["key_fingerprint"] or "").strip():
            blockers.append("Key has empty fingerprint; explicit review required")
    for group in groups:
        if int(group["owner_id"]) not in state["owner_ids"]:
            blockers.append("Group references missing owner")

    report_refs = state["report_references"]
    refs_by_group: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for table, grouped in report_refs.items():
        for group_id, row_ids in grouped.items():
            for row_id in row_ids:
                refs_by_group[int(group_id)].append((table, int(row_id)))

    groups_by_owner: dict[int, list[dict[str, object]]] = defaultdict(list)
    for group in groups:
        groups_by_owner[int(group["owner_id"])].append(group)

    owner_plans = []
    all_move_ids: set[int] = set()
    all_delete_key_ids: set[int] = set()
    all_update_key_ids: set[int] = set()
    all_archive_group_ids: set[int] = set()
    all_delete_group_ids: set[int] = set()
    all_mapping_ids: set[int] = set()
    all_default_update_ids: set[int] = set()
    all_model_update_ids: set[int] = set()

    for owner_id in sorted(groups_by_owner):
        owner_groups = sorted(groups_by_owner[owner_id], key=_group_sort)
        canonical = _canonical_group(owner_groups)
        if canonical is None:
            continue
        canonical_id = int(canonical["id"])
        canonical["_canonical"] = True
        owner_keys = [key for key in keys if int(key["group_id"]) in {int(g["id"]) for g in owner_groups}]
        keys_by_fp: dict[str, list[dict[str, object]]] = defaultdict(list)
        for key in owner_keys:
            keys_by_fp[str(key["key_fingerprint"])].append(key)

        key_moves = []
        key_deletes = []
        key_updates = []
        key_conflicts = []
        canonical_key_by_fp: dict[str, dict[str, object]] = {}
        canonical_order = []
        # Keep the existing canonical queue first.  This is deterministic and
        # avoids an unexpected fairness jump on the first post-migration call.
        for key in sorted(owner_keys, key=lambda row: _operation_key_sort(row, groups_by_id)):
            fp = str(key["key_fingerprint"])
            if fp in canonical_key_by_fp:
                continue
            candidates = sorted(keys_by_fp[fp], key=lambda row: _operation_key_sort(row, groups_by_id))
            keeper = candidates[0]
            canonical_key_by_fp[fp] = keeper
            canonical_order.append(keeper)
            losers = [candidate for candidate in candidates if candidate is not keeper]
            if int(keeper["group_id"]) != canonical_id:
                key_moves.append({"key_id": int(keeper["id"]), "from_group_id": int(keeper["group_id"]), "to_group_id": canonical_id})
                all_move_ids.add(int(keeper["id"]))
            for loser in losers:
                key_deletes.append({"key_id": int(loser["id"]), "group_id": int(loser["group_id"]), "keeper_id": int(keeper["id"])})
                all_delete_key_ids.add(int(loser["id"]))
            if len(candidates) > 1:
                statuses = sorted({candidate.get("last_test_status") or "unverified" for candidate in candidates})
                paused = any(bool(candidate["is_paused"]) for candidate in candidates)
                source_inactive = any(
                    int(candidate["group_id"]) != canonical_id
                    and not groups_by_id[int(candidate["group_id"])] ["is_active"]
                    for candidate in candidates
                )
                projects = sorted({str(candidate.get("project_ref") or "default") for candidate in candidates})
                key_conflicts.append({
                    "fingerprint_group_size": len(candidates),
                    "keeper_id": int(keeper["id"]),
                    "key_ids": [int(candidate["id"]) for candidate in candidates],
                    "statuses": statuses,
                    "paused_present": paused,
                    "inactive_source_present": source_inactive,
                    "project_labels_count": len(projects),
                })
            # Most restrictive readiness wins.  Status metadata is kept
            # coherent with the selected duplicate instead of mixing an old
            # error with a newer probe timestamp.
            state_keeper = max(
                candidates,
                key=lambda row: (_status_severity(row.get("last_test_status")), bool(row["is_paused"]), _key_sort(row)),
            )
            desired_paused = bool(state_keeper["is_paused"]) or any(
                int(candidate["group_id"]) != canonical_id
                and not groups_by_id[int(candidate["group_id"])] ["is_active"]
                for candidate in candidates
            )
            desired_project = str(keeper.get("project_ref") or "default")
            if len({str(candidate.get("project_ref") or "default") for candidate in candidates}) > 1:
                # A label cannot prove project identity.  The shared default
                # scope is the conservative cooldown behavior on conflict.
                desired_project = "default"
            changes = {}
            if bool(keeper["is_paused"]) != desired_paused:
                changes["is_paused"] = desired_paused
            if keeper.get("last_test_status") != state_keeper.get("last_test_status"):
                changes["last_test_status"] = state_keeper.get("last_test_status")
            if keeper.get("last_tested_at") != state_keeper.get("last_tested_at"):
                changes["last_tested_at"] = state_keeper.get("last_tested_at")
            if keeper.get("last_error_code") != state_keeper.get("last_error_code"):
                changes["last_error_code"] = state_keeper.get("last_error_code")
            if keeper.get("project_ref") != desired_project:
                changes["project_ref"] = desired_project
            # Do not alter a successful key's verification state merely due to
            # a duplicate unless a stricter duplicate requires it.
            if changes:
                key_updates.append({"key_id": int(keeper["id"]), "changes": changes})
                all_update_key_ids.add(int(keeper["id"]))

        noncanonical = [group for group in owner_groups if int(group["id"]) != canonical_id]
        archive_group_ids = sorted(
            int(group["id"])
            for group in noncanonical
            if int(group["id"]) in refs_by_group
            and (group["is_active"] or group["is_default"])
        )
        delete_group_ids = sorted(
            int(group["id"])
            for group in noncanonical
            if int(group["id"]) not in refs_by_group
        )
        all_archive_group_ids.update(archive_group_ids)
        all_delete_group_ids.update(delete_group_ids)

        # A canonical with no default is promoted, but an inactive canonical
        # is intentionally not activated.  That preserves an operator stop.
        default_updates = sorted(
            int(group["id"])
            for group in owner_groups
            if (int(group["id"]) == canonical_id and not group["is_default"])
            or (int(group["id"]) != canonical_id and group["is_default"])
        )
        all_default_update_ids.update(default_updates)
        model_update = canonical.get("model_name") != FIXED_MODEL
        if model_update:
            all_model_update_ids.add(canonical_id)

        mapping_course_ids = []
        mapping_owner_mismatches = []
        group_owner = {int(group["id"]): int(group["owner_id"]) for group in owner_groups}
        for course in state["courses"]:
            mapped = course["ai_key_group_id"]
            try:
                mapped_id = int(mapped)
            except (TypeError, ValueError):
                continue
            if mapped_id not in group_owner:
                continue
            mapping_course_ids.append(int(course["id"]))
            all_mapping_ids.add(int(course["id"]))
            if course["teacher_id"] is not None and int(course["teacher_id"]) != owner_id:
                mapping_owner_mismatches.append(int(course["id"]))

        historical = {
            str(group_id): {
                "tables": sorted({table for table, _ in refs_by_group.get(group_id, [])}),
                "row_count": len(refs_by_group.get(group_id, [])),
            }
            for group_id in sorted(refs_by_group)
            if group_id in {int(group["id"]) for group in owner_groups}
        }
        owner_item = {
            "owner_id": owner_id,
            "canonical_group_id": canonical_id,
            "group_ids": [int(group["id"]) for group in owner_groups],
            "archive_group_ids": archive_group_ids,
            "delete_group_ids": delete_group_ids,
            "model_update": {"group_id": canonical_id, "from_fixed": False} if model_update else None,
            "default_updates": default_updates,
            "key_moves": key_moves,
            "key_deletes": key_deletes,
            "key_updates": key_updates,
            "key_conflicts": key_conflicts,
            "mapping_course_ids": sorted(mapping_course_ids),
            "mapping_owner_mismatches": sorted(mapping_owner_mismatches),
            "historical_references": historical,
        }
        owner_plans.append(_public_group_plan(owner_item))

    # Mappings to a group whose owner was not represented above are stale but
    # still removable; report them as blockers rather than guessing ownership.
    known_group_ids = set(groups_by_id)
    for course in state["courses"]:
        try:
            mapped_id = int(course["ai_key_group_id"])
        except (TypeError, ValueError):
            continue
        if mapped_id not in known_group_ids:
            blockers.append("Course mapping references missing group")

    # Foreign keys/triggers are checked before any destructive group delete.
    # A physical FK to a group table that is not represented by SQLAlchemy must
    # be reviewed explicitly; report/history rows are intentionally handled as
    # archive references above.
    for table in sorted(_table_names(connection)):
        if table in {GROUP_TABLE, KEY_TABLE}:
            continue
        for row in connection.execute("PRAGMA foreign_key_list(" + _quote(table) + ")"):
            if row[2] == GROUP_TABLE and table not in {COURSE_TABLE}:
                # A report table with a real FK is safe only when its referenced
                # group is archived; deleting it would violate the FK.
                if table not in state["report_references"]:
                    blockers.append("Foreign key to teacher group needs review: " + table)

    current_fingerprint = fingerprint(_table_snapshot(connection))
    counts = {
        "owners": len(owner_plans),
        "groups_before": len(groups),
        "groups_to_archive": len(all_archive_group_ids),
        "groups_to_delete": len(all_delete_group_ids),
        "groups_to_set_default": len(all_default_update_ids),
        "groups_to_fix_model": len(all_model_update_ids),
        "keys_before": len(keys),
        "keys_to_move": len(all_move_ids),
        "keys_to_delete": len(all_delete_key_ids),
        "keys_to_update": len(all_update_key_ids),
        "course_mappings_before": len(state["courses"]),
        "course_mappings_to_clear": len(all_mapping_ids),
        "historical_group_references": sum(len(items) for items in refs_by_group.values()),
        "duplicate_conflict_groups": sum(len(item.get("key_conflicts", [])) for item in owner_plans),
    }
    public_state = {
        "schema_version": PHASE5_SCHEMA_VERSION,
        "database_fingerprint": current_fingerprint,
        "counts": counts,
        "owners": owner_plans,
        "blockers": sorted(set(blockers)),
    }
    public_state["status"] = "blocked" if public_state["blockers"] else ("ready" if _plan_has_changes(public_state) else "no_changes")
    return public_state


def public_plan(plan: dict) -> dict:
    """Strip private planning state before a plan is displayed or persisted."""

    return {key: value for key, value in plan.items() if key != "_internal"}


def _exec(connection, sql, params=()):
    return connection.execute(sql, tuple(params))


def _apply_owner(connection, owner_item):
    canonical_id = int(owner_item["canonical_group_id"])
    owner_id = int(owner_item["owner_id"])

    # Demote all other defaults first; the unique name constraint does not
    # constrain defaults, but this order gives a clear one-owner invariant.
    _exec(
        connection,
        "UPDATE " + _quote(GROUP_TABLE) + " SET is_default=0 WHERE owner_id=? AND id<>?",
        (owner_id, canonical_id),
    )
    _exec(
        connection,
        "UPDATE " + _quote(GROUP_TABLE) + " SET is_default=1, model_name=? WHERE id=?",
        (FIXED_MODEL, canonical_id),
    )

    # Delete duplicate losers before moving a keeper into the canonical group,
    # otherwise the per-group fingerprint unique constraint could transiently
    # reject a perfectly deterministic merge.
    for item in owner_item.get("key_deletes", []):
        _exec(connection, "DELETE FROM " + _quote(KEY_TABLE) + " WHERE id=?", (int(item["key_id"]),))
    for item in owner_item.get("key_moves", []):
        _exec(
            connection,
            "UPDATE " + _quote(KEY_TABLE) + " SET group_id=? WHERE id=?",
            (canonical_id, int(item["key_id"])),
        )
    for item in owner_item.get("key_updates", []):
        changes = item.get("changes") or {}
        allowed = {"is_paused", "last_test_status", "last_tested_at", "last_error_code", "project_ref"}
        for column, value in changes.items():
            if column not in allowed:
                raise MigrationBlocked("Unexpected key migration field")
            _exec(connection, "UPDATE " + _quote(KEY_TABLE) + " SET " + _quote(column) + "=? WHERE id=?", (value, int(item["key_id"])))

    if owner_item.get("default_updates") or owner_item.get("model_update") or owner_item.get("key_moves") or owner_item.get("key_deletes") or owner_item.get("key_updates"):
        # Touch only the effective group.  Queue rotation in later runtime
        # requests still avoids this method and therefore keeps its revision.
        _exec(
            connection,
            "UPDATE " + _quote(GROUP_TABLE) + " SET config_revision=CASE WHEN COALESCE(config_revision,0)<1 THEN 1 ELSE config_revision END + 1 WHERE id=?",
            (canonical_id,),
        )

    # A referenced legacy group remains as a keyless, inactive archive.  The
    # historical report rows retain their original group/model/revision data.
    for group_id in owner_item.get("archive_group_ids", []):
        _exec(
            connection,
            "UPDATE " + _quote(GROUP_TABLE) + " SET is_active=0, is_default=0 WHERE id=?",
            (int(group_id),),
        )
    for group_id in owner_item.get("delete_group_ids", []):
        _exec(connection, "DELETE FROM " + _quote(KEY_TABLE) + " WHERE group_id=?", (int(group_id),))
        _exec(connection, "DELETE FROM " + _quote(GROUP_TABLE) + " WHERE id=?", (int(group_id),))


def _apply_plan_in_transaction(connection, plan):
    for owner_item in plan.get("owners", []):
        _apply_owner(connection, owner_item)
    # Manual per-course assignment is retired.  Clear only existing mapping
    # values; all original ids are already in the safe plan/backup manifest.
    _exec(connection, "UPDATE " + _quote(COURSE_TABLE) + " SET ai_key_group_id=NULL WHERE ai_key_group_id IS NOT NULL")


def _verify_invariants(connection):
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise MigrationBlocked("Integrity check failed after migration")
    fk = connection.execute("PRAGMA foreign_key_check").fetchone()
    if fk:
        raise MigrationBlocked("Foreign-key check failed after migration")
    groups = [dict(row) for row in connection.execute("SELECT id,owner_id,is_active,is_default,model_name FROM " + _quote(GROUP_TABLE))]
    defaults = defaultdict(list)
    for group in groups:
        if group["is_default"]:
            defaults[int(group["owner_id"])].append(group)
            if group["model_name"] != FIXED_MODEL:
                raise MigrationBlocked("Effective group model is not fixed")
    if any(len(items) != 1 for items in defaults.values()):
        raise MigrationBlocked("Owner has more than one default group")
    for row in connection.execute("SELECT id,teacher_id,ai_key_group_id FROM " + _quote(COURSE_TABLE) + " WHERE ai_key_group_id IS NOT NULL"):
        raise MigrationBlocked("Course mapping was not cleared")
    # Runtime keys are owned through their group.  Archived rows may remain,
    # but no fingerprint may occur twice in one owner's effective group.
    owner_by_group = {int(row["id"]): int(row["owner_id"]) for row in connection.execute("SELECT id,owner_id FROM " + _quote(GROUP_TABLE))}
    seen = set()
    for row in connection.execute("SELECT group_id,key_fingerprint FROM " + _quote(KEY_TABLE)):
        group_id, key_fp = int(row[0]), str(row[1] or "")
        if group_id not in owner_by_group:
            raise MigrationBlocked("Key ownership was lost")
        marker = (owner_by_group[group_id], key_fp)
        # Archived groups are not effective runtime pools.  Duplicates in
        # archives are allowed only for audit, while canonical active/default
        # groups must be unique per owner.
        group = connection.execute("SELECT is_default,is_active FROM " + _quote(GROUP_TABLE) + " WHERE id=?", (group_id,)).fetchone()
        if group and group[0] and marker in seen:
            raise MigrationBlocked("Duplicate fingerprint remains in effective owner pool")
        if group and group[0]:
            seen.add(marker)


def apply_plan(database, backup, expected_fingerprint) -> dict[str, object]:
    """Backup then apply a reviewed plan to one explicit SQLite file.

    ``expected_fingerprint`` must come from a fresh dry-run.  The caller owns
    the approval decision; this function never applies implicitly.
    """

    database_path = _path(database)
    backup_path = Path(backup).expanduser()
    if backup_path.exists() or backup_path.is_symlink():
        raise ValueError("Backup path already exists")
    with closing(connect_readonly(database_path)) as source:
        plan = build_plan(source)
        if plan["blockers"]:
            raise ValueError("Migration blocked; run the dry-run report")
        if str(plan["database_fingerprint"]) != str(expected_fingerprint):
            raise ValueError("Database changed; run a fresh dry-run")
        if plan["status"] == "no_changes":
            return {"status": "no_changes", "database_fingerprint": plan["database_fingerprint"], "counts": plan["counts"]}
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
            if fingerprint(_table_snapshot(saved)) != plan["database_fingerprint"]:
                raise ValueError("Backup does not match the reviewed database")

    live = sqlite3.connect(str(database_path), timeout=30)
    live.row_factory = sqlite3.Row
    live.execute("PRAGMA foreign_keys=ON")
    live.execute("PRAGMA busy_timeout=30000")
    try:
        live.execute("BEGIN IMMEDIATE")
        current = build_plan(live)
        if current["blockers"] or str(current["database_fingerprint"]) != str(expected_fingerprint):
            raise ValueError("Database changed before conversion; transaction rolled back")
        _apply_plan_in_transaction(live, current)
        _verify_invariants(live)
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
        "database_fingerprint_before": plan["database_fingerprint"],
        "database_fingerprint_after": after_plan["database_fingerprint"],
        "after_status": after_plan["status"],
    }
