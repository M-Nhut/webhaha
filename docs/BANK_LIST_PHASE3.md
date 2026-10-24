# Bank list and read-only detail — Phase 3

Phase 3 exposes the Phase 1 visibility policy in the question-bank list and
detail page without changing bank selection, historical data, or scope values.

## Teacher experience

- **Ngân hàng dùng chung** contains only banks that pass `can_view_bank` and
  have explicit `shared` visibility. They are readable and, when active,
  usable by existing consumers.
- **Ngân hàng của tôi** contains only the teacher's own explicit `private`
  banks and compatible teacher-owned legacy `NULL` banks.
- Other teachers' private banks, legacy admin-owned banks, missing-owner rows,
  and invalid scopes never appear for a teacher.
- A shared-bank detail page is read-only: it retains question display,
  filtering, formula rendering, and answer display, but does not render bank
  edit/delete/import, question add/delete/inline-edit, classification, bulk,
  adaptive controls; answer-toggle buttons are disabled. The client editor
  receives an explicit `canEdit: false` configuration and refuses mutation
  activation.

## Enforcement

The list and detail route use the Phase 1 centralized helpers. Existing direct
mutation routes remain guarded by `require_bank_edit` or `can_edit_bank`; a
teacher who forges a shared-bank URL receives 403 (JSON endpoints retain their
JSON 403 contract). Administrators continue to list and manage every row,
including legacy rows for repair. Students remain excluded by the existing
role and bank policy checks.

## Deferred

Phase 3 does not change diagnostic/adaptive bank selection (Phase 4) and does
not classify or backfill historical `visibility` values (Phase 5).
