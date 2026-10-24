# Phase 1 — TeX import review

The only accepted import source is TeX.  A source annotation such as
`%[9C8Ni-1D]` is authoritative for grade, Chapter 8, combined lesson `i`,
category, cognitive level, and question type.  The optional numeric suffix in
a source file is audit input only: the application assigns the saved suffix
atomically when the new bank row is written.  Previewing, reopening, or editing
does not allocate a number.  Multiple questions may use the same prefix and
receive distinct suffixes at save time; later ordinary content edits retain the
saved ID.

Teachers can review and edit question content, options, answer keys,
explanations, source-prefix consistency, duplicate decisions, and scoring
metadata before importing.  Duplicate scanning runs after edits and again in
the confirmation transaction against both the file and target bank.  Exact
duplicates are skipped, review matches require a current decision, and a replay
of the same confirmation token is idempotent.

Pressing **Import vào ngân hàng** is the teacher review event.  Only new,
non-duplicate rows that pass the final answer, prefix, selector-readiness, and
auto-scoring checks are saved.  Those rows receive `teacher_confirmed` and a
reviewer ID/time in their existing classification audit JSON.  Existing bank
rows are never auto-approved.  Invalid rows stay in the preview as errors, so a
batch may import its valid rows without silently accepting the rest; that
partially imported session remains open until its remaining errors are fixed or
removed.

For short answers, the persisted metadata is
`{"short_answer":{"mode":"text"|"numeric","tolerance":"0"}}`.  For
true/false questions it is `{"statements":[{"curriculum_code":"9C8-i-1",
"cognitive_level":"nhan_biet"}, ...]}` with exactly four rows.  If omitted,
the preview inherits only the source prefix's one scope and one level (never
distinct inferred statement skills); teachers may change the visible metadata
before confirming.
