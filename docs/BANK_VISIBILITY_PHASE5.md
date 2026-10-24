# Bank visibility — Phase 5 historical backfill

Phase 5 is an offline, operator-reviewed migration for legacy
`question_bank.visibility` values.  It is deliberately separate from startup
and from the Flask application.  The migration changes only the
`question_bank.visibility` column.

## Classification contract

The script uses the current persisted `user.role` only as a conservative
ownership check:

- A `NULL` row with an existing owner whose role is exactly `teacher` is
  backfilled to `private`.
- A `NULL` row with an existing owner whose role is `admin` is reported as
  ambiguous.  It remains `NULL` unless that exact bank id is explicitly
  reviewed and supplied with `--shared-bank-id`.
- Missing owners and unsupported roles remain `NULL` and are reported.
- Malformed visibility values remain unchanged and are reported.
- Existing explicit `shared` and `private` values are preserved, including
  rows whose owner is now missing or has an unsupported role.  The runtime
  policy continues to fail closed for such inconsistent rows.

The migration never infers historical ownership from a role transition.  It
does not delete banks/questions, transfer owners, or update frozen exams,
exam questions, submissions, reports, or any other table.

## Review and apply workflow

The command requires an existing regular SQLite file.  It is a dry run unless
`--apply` is supplied:

```text
python scripts/migrate_bank_visibility_phase5.py \
  --database /absolute/path/to/tutoring_center.db
```

The JSON report contains counts, bank ids needing review, and a
`database_fingerprint`.  A pending admin-owned `NULL` row makes the report's
status `review_required`; it is not silently widened to teachers.

After an administrator explicitly approves a bank, include its id in the
matching dry run.  The option may be repeated:

```text
python scripts/migrate_bank_visibility_phase5.py \
  --database /absolute/path/to/tutoring_center.db \
  --shared-bank-id 1
```

Review that report, then run the same mapping with the exact fingerprint:

```text
python scripts/migrate_bank_visibility_phase5.py \
  --database /absolute/path/to/tutoring_center.db \
  --shared-bank-id 1 \
  --apply \
  --expect <database_fingerprint>
```

An operator may apply only the unambiguous teacher-owned rows while leaving
unreviewed admin-owned rows `NULL`; the report remains `review_required` until
those rows are explicitly mapped or otherwise repaired by an administrator.

## Safety guarantees

`--apply` requires the exact fresh fingerprint.  The migration then:

1. creates a new `before.sqlite3` backup before taking the writer lock;
2. verifies backup integrity, foreign keys, and the backup fingerprint;
3. acquires `BEGIN IMMEDIATE` and rechecks the fingerprint and plan;
4. updates only rows still `NULL` and in the reviewed plan;
5. verifies SQLite integrity, foreign keys, bank ownership/metadata, bank row
   count, and that every non-`question_bank` table is unchanged before commit.

The default backup directory is
`backups/bank-visibility-phase5-<UTC timestamp>/`; `--backup-dir` can choose a
different directory.  It contains a mode-600 `before.sqlite3` and, after a
successful apply, a mode-600 `manifest.json` containing only the safe report,
fingerprints, counts, ids, and result metadata.  A failed transaction is
rolled back and the verified backup is retained.

The migration is idempotent.  Re-running a previously applied explicit
mapping is accepted as a no-op; explicit scopes and unresolved legacy rows are
not rewritten.

## Local rollout status (2026-09-16)

The parent reviewed the migration and ran all six focused tests successfully.
Python syntax checks passed. A read-only dry run of the local database found
one legacy admin-owned bank (ID 1, 185 questions), with no unambiguous updates.
Its status is `review_required`. No live migration or backup has been performed;
explicit approval to make this bank shared remains outstanding.

The fingerprint binds the database snapshot, not the supplied mapping. Review
the exact `--shared-bank-id` arguments separately before applying. The CLI
returns a nonzero exit status when review remains outstanding, including after
a partial migration of unambiguous teacher-owned banks.
