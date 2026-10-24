# Teacher-owned Gemini keys — Phase 5

Phase 5 makes the teacher's credential pool deterministic and removes the
retired group/model/course-assignment controls.  Runtime still uses the
current teacher's oldest default group, the strict Phase 4 verification gate,
round-robin `sort_order`, and project-scoped cooldowns.  The provider model is
server-owned and fixed to `gemini-3.8-flash`.

## Migration safety

The migration is explicit and dry-run by default.  It does not import Flask,
load `.env`, decrypt a key, call Gemini, or print key material:

```sh
python3 scripts/migrate_teacher_keys_phase5.py --database tutoring_center.db
```

Review the owner/group/key/mapping counts and the
`database_fingerprint`.  Apply only that exact reviewed fingerprint:

```sh
python3 scripts/migrate_teacher_keys_phase5.py \
  --database tutoring_center.db --apply --expect <database_fingerprint>
```

Before conversion the tool creates `before.sqlite3` using Python's SQLite
`Connection.backup()` API, verifies its integrity and mode (`0600`), then
revalidates the live file under `BEGIN IMMEDIATE`.  A failed check rolls the
transaction back and leaves the backup available.  A second dry-run after a
successful conversion reports `no_changes`.  No production database was
changed while this code was developed.

### Local reviewed run

The reviewed local file was applied on 2026-09-15 after the dry-run
fingerprint was checked by the parent task.  The run reported one owner and
one existing group: model fix `1`, mapping clear `1`, key moves/deletes `0`,
group archive/delete `0`, and three historical references in
`class_ai_analysis_run`.  Integrity and foreign-key checks passed, and a
second plan returned `no_changes`.  The recoverable backup is
`backups/teacher-keys-phase5-20260915T135051631634Z/before.sqlite3`; its
manifest contains metadata only.

## Conversion policy

- One canonical group is selected per owner: the lowest-id default; if no
  default exists, the lowest-id internal group; otherwise the lowest-id group.
- The canonical group is marked default and its runtime model is fixed.  An
  inactive canonical group remains inactive; migration never activates a
  paused operator decision.
- Keys are merged only among groups owned by the same teacher.  A duplicate
  fingerprint is kept once in the canonical runtime group.  Conflicting
  verification/project state uses the most restrictive readiness; a key from
  an inactive source remains paused.  A project-label conflict falls back to
  the shared `default` cooldown scope.  The plan reports conflicts without
  showing fingerprints or ciphertext.
- A redundant group with historical `ai_key_group_id` report references is
  retained as an inactive, keyless archive.  Its report rows and stored
  `model_name`/revision are not rewritten.  An unreferenced redundant group
  is removed after its retained keys are merged into the canonical group.
- Every legacy `course.ai_key_group_id` mapping is cleared and listed in the
  plan/backup; the gateway already ignores that field.  Cross-owner stale
  mappings are reported rather than moving ownership.

The admin disable endpoint remains available.  Teachers retain encrypted
save, synthetic test, retry and delete operations.  Group creation/editing,
per-course mapping, project/model editing, key reorder and key pause controls
are no longer registered or rendered.

## Recovery

Stop web workers before restoring.  Use the `before.sqlite3` backup with a
SQLite connection backup/restore operation, then run `PRAGMA integrity_check`
and `PRAGMA foreign_key_check` before reopening the application.  Restoring a
full snapshot also removes writes made after that backup, so reconcile those
writes separately.  The manifest contains only safe metadata and counts.

Focused verification:

```sh
python3 -m unittest tests.test_teacher_keys_phase5 tests.test_route_contract -v
```
