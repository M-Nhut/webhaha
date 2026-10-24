# Bank visibility — Phase 1

Phase 1 establishes the server-side ownership and access policy for question
banks. It does not add the import destination UI, a new bank listing UI,
adaptive/diagnostic consumers, or historical data backfill.

## Scope contract

`question_bank.visibility` is a nullable, server-owned value:

- `shared`: a bank created by an administrator; teachers may view/use it.
- `private`: a bank created by a teacher; only that teacher and administrators
  may view/use it.
- `NULL`: a legacy row awaiting the reviewed migration. A legacy row owned by
  a teacher remains private to that owner. A legacy row owned by an admin is
  not inferred to be shared for teachers.

New-bank scope is derived from the authenticated server actor. A request body
cannot select `shared` or `private`. Once persisted, an explicit value is
authoritative even if the creator's role later changes; this is why scope is
stored instead of derived from the current role on every request. The create
service is the only supported writer and enforces the creator/scope invariant.

## Permission matrix

| Actor / bank | View | Use | Edit | Import / delete |
| --- | ---: | ---: | ---: | ---: |
| Administrator, valid or legacy bank | yes | active only | yes | yes |
| Owning teacher, `private` (or legacy teacher-owned `NULL`) | yes | active only | yes | yes |
| Non-owner teacher, `private` | no | no | no | no |
| Any teacher, valid `shared` admin-created bank | yes | active only | no | no |
| Student or unknown role | no | no | no | no |
| Teacher and missing/unknown creator or invalid scope | no | no | no | no |

Administrators can inspect/manage orphaned or inconsistent rows so they can
repair them. Such rows are never granted to teachers by the compatibility
fallback.

The policy is centralized in `services/access_control.py`. The legacy
`_get_accessible_question_bank` route helper intentionally remains edit-only;
read access must use `require_bank_view`, so making shared banks readable can
never accidentally permit an import or mutation.

## Schema rollout

The additive migration is intentionally separate from application behavior:

```text
python scripts/migrate_bank_visibility_phase1.py --database /path/to/tutoring_center.db
```

Back up the database and review the target before running it. The script adds
only a nullable column and index; it does not update existing rows. The normal
startup compatibility path also adds this nullable column when an older local
schema is opened, without backfilling scope.

The later historical-data phase must classify existing rows from an audited
ownership snapshot before assigning `shared`/`private`; role-derived promotion
at request time is deliberately not used because roles can change.

## Deliberately deferred

- import flow destination controls beyond the authorization checks;
- teacher/admin bank listing and visibility labels;
- adaptive and diagnostic bank selection changes;
- historical ownership/scope migration and backfill.
