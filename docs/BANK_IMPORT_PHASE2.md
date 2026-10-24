# Bank import — Phase 2

Phase 2 connects the existing LaTeX import/review pipeline to the Phase 1 bank
visibility policy. It deliberately does not redesign the general bank list,
change diagnostic/adaptive consumers, or migrate historical bank scope.

## Supported flow

1. An authenticated administrator or teacher uploads a `.tex`/`.latex` file.
2. The parser preserves supported source IDs and produces an editable review
   session. File scope and teacher edits remain persisted in that session.
3. Duplicate detection compares the file with itself and with the selected
   destination bank only. It never merges, deletes, or updates another bank.
4. The teacher reviews/edits answers and metadata, resolves ambiguous matches,
   and confirms the import. Saved rows retain the existing
   `teacher_confirmed` readiness contract.

## Destination and creation policy

- Administrators can import into every bank. A bank newly created from the
  wizard is server-stamped `shared` and owned by that administrator.
- Teachers can import only into an owned `private` bank or an allowed legacy
  teacher-owned `NULL` bank. A new bank is server-stamped `private` and owned
  by that teacher.
- A valid `shared` bank is read-only to teachers, including a bank whose
  persisted creator is now a teacher after a role change.
- Request fields cannot select visibility or forge ownership. Importing into
  an existing bank never changes its scope or owner.

The destination controls show only banks for which the current actor has edit
permission and explain the read-only shared-bank rule.

## Stale-session and replay safety

The server reloads the actor, import session, destination bank, and destination
creator before upload binding, destination switching, review mutations, and
the final save. A destination switch also requires the old captured target to
remain authorized; otherwise the file must be uploaded into a new session.

Final confirmation owns one database transaction and re-runs validation and
destination-local duplicate detection after acquiring the write lock. The
session's persisted destination is authoritative. A receipt replay is returned
only after that real destination is reauthorized and any request destination is
verified to match it. Replays therefore produce no duplicate writes and cannot
be used to expose a receipt for a revoked or forged target.

## Deferred

- bank-list redesign and broader scope labels (Phase 3);
- diagnostic/adaptive selection changes (Phase 4);
- historical visibility backfill or migration (Phase 5).
