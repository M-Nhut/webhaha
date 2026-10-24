# Question overlays — Phase 2

Phase 2 enables a teacher to add or import a private question into an
explicitly shared bank.  The bank and its existing common questions remain
read-only to that teacher; the new row is visible and usable only by the
owning teacher (and by the classes that teacher currently teaches), with
administrator audit access retained. Existing
private banks keep their owner and existing question scopes.  No backfill,
schema migration, or live database write was performed during implementation.

## Server contract

`can_add_question` / `can_import_questions` are separate from
`can_edit_bank`.  A teacher may author only in their own private bank or add a
private overlay to an explicit shared bank.  `set_new_question_scope` derives
`scope` and `private_owner_id` from the fresh authenticated actor and target;
client-supplied scope/owner fields are ignored.  Administrators add shared
rows to shared banks and retain private-bank ownership semantics.

Duplicate review is actor-scoped: teachers compare shared rows and their own
private rows; an administrator importing common content never compares with a
private overlay.  An administrator importing into an existing private bank
may compare against that bank owner's compatible rows, including legacy
teacher-owned `NULL` rows.  Reports and IDs from foreign private rows are not
placed in a preview.

Confirmation revisions bind the parsed content to the fresh actor role and
resolved destination visibility/owner/write audience.  A role or audience
change between preview and confirm rejects both an old token and a tokenless
confirm until the preview is refreshed.  Historical receipt replays retain
counts and saved IDs but redact cached duplicate match payloads; current
previews rescan under the actor's current authorization.

## Runtime prerequisite

Phase 4 selector safety is a prerequisite for using overlays in practice:
production adaptive/diagnostic candidate queries must pass the server course
context and filter through `can_use_question_for_class`.  Without a class
context, only the existing legacy-compatible `NULL` rows are eligible in the
offline compatibility path; explicit private/shared overlays are not exposed.
Selector ranking and exam/scoring contracts are unchanged.

## Focused verification

The Phase 2 overlay tests cover separate add/import permission, server
stamping, actor-scoped duplicate review, legacy private compatibility,
audience-change rejection (with and without a confirmation token), and
receipt/preview redaction.  Parent selector regression tests cover class
scoping and foreign-overlay exclusion.  Run the bounded checks with:

```text
python3 -m unittest tests.test_question_overlay_phase2
```

Final parent verification (2026-09-17): 36 focused tests passed across overlay
authoring (6), selector isolation (1), question-scope Phase 1 (5), bank
Phases 1–4 (20), and unified practice (4). Python/JavaScript syntax checks
passed. Existing datetime deprecation and SQLite resource warnings remain.
The live SQLite file SHA-256 was unchanged before/after verification.

The pending-confirmation guard also covers a not-yet-created destination bank;
missing review state requires a fresh preview, even without a supplied token.
The production selector safety prerequisite described above is already wired
in this change; broader Phase 3 UI organization and Phase 4 work remain separate.
