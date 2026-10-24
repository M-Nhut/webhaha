# Question scope — Phase 1

Phase 1 adds the server-side data contract and authorization boundary for
question-level visibility. It does not add overlay authoring/import controls,
new generation UI, or a historical backfill.

## Persisted contract

`bank_question.scope` is nullable and server-owned:

- `shared`: the question is part of an explicitly shared bank;
- `private`: the question belongs to the teacher in
  `bank_question.private_owner_id`;
- `NULL`: a legacy row awaiting reviewed classification.

`private_owner_id` is separate from `created_by`. An administrator can be the
provenance creator/importer while a future teacher supplement remains private
to its teacher. Existing IDs, foreign-key references, question content, and
bank ownership are unchanged.

New rows created through the existing bank flows are stamped from the
authenticated actor and destination bank. A teacher still cannot create or
import into a shared bank in this phase, so this stamp does not enable the
overlay feature.

## Access policy

The policy is centralized in `services/access_control.py`:
`can_view_question`, `can_use_question`, `can_edit_question`, and
`can_delete_question` (with `require_question_view` / `require_question_edit`
for route boundaries).

| Actor / question | View | Use | Edit / delete |
| --- | ---: | ---: | ---: |
| Administrator, any persisted row | yes (audit) | active bank only | yes (audit/repair) |
| Owning teacher, private row in own private bank | yes | active bank only | yes |
| Owning teacher, private supplement in shared bank | yes | active bank only | yes, when the row already exists |
| Other teacher, private row/supplement | no | no | no |
| Teacher, shared row in shared bank | yes | active bank only | no |
| Student or unknown role | no | no | no |
| Teacher, invalid/mismatched/unknown owner | no | no | no |

For a class-scoped runtime decision, callers use the current course teacher via
`can_use_question_for_class`; a student or administrator is never substituted
as the class actor.

### Legacy `NULL` behavior

No row is updated by a read or by startup. The compatibility resolver only
uses facts that cannot widen access:

- a private (or compatible legacy teacher-owned) bank keeps a question
  private to the bank owner;
- in an explicit shared bank, a question created by that bank's administrator
  is safely treated as shared;
- a known teacher-created question in that shared bank is kept private to that
  teacher, never promoted to shared;
- missing creators/owners, conflicting owner references, admin-owned legacy
  banks, malformed scope values, and other ambiguous combinations remain
  admin-only.

An explicit scope is authoritative, but it must still be compatible with the
containing bank. A private row whose owner does not match a private bank's
owner, or a shared row inside a private bank, is denied to teachers. Admins
retain the audit path for repair.

## Schema rollout

The normal startup compatibility path adds the nullable columns and indexes if
an older schema is opened. It never fills existing values. For a reviewed
SQLite file, the standalone additive script is:

```text
python scripts/migrate_question_scope_phase1.py --database /absolute/path/to/tutoring_center.db
```

The script refuses missing/symlink paths, adds only `scope`,
`private_owner_id`, and their indexes, and is repeatable. Review/back up the
target first; this Phase 1 task did not run it against the local or production
database.

## Route coverage and deliberate limits

The bank detail/list aggregates and serialized detail question list are
filtered through the question policy. Direct ID6 preview reads and direct
question adaptive/update/toggle/delete routes re-check the question-level
policy, including the persisted bank/question ID match. Classification export
and mutation selections also reject questions the actor cannot view/edit.

Existing bank-level diagnostic/adaptive selectors and import duplicate scans
remain Phase 3/4 integration work. They are not changed here to introduce
overlay generation. Until those phases wire `can_use_question` into their
queries, no new overlay authoring path is enabled by this change.
