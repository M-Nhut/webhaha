# Question overlays — Phase 3

Phase 3 organizes the bank-detail page into three server-filtered views:

- `scope=all`: every question the current actor may view;
- `scope=common`: questions resolved as shared/common;
- `scope=mine`: questions resolved as private contributions. For a teacher,
  the Phase 1/2 authorization set makes this the teacher's own contributions.
  For an administrator it is an audit bucket containing private contributions
  owned by any teacher and is labeled accordingly.

The `scope` value is a display selector, never an authorization input. The
route first evaluates `can_view_question` for every row and only then applies
the source bucket, search, type, difficulty, and grade filters. Unknown or
incompatible legacy rows remain in an administrator's `all` audit view but do
not get promoted into common/private tabs. An invalid scope falls back to the
authorized `all` view; invalid type/difficulty values produce no matches.

Tab counts are computed from the complete authorized set. Difficulty/type
statistics and grade facets are computed from the selected tab before the
ordinary filters, so searching cannot make a facet reveal an unauthorized
private row or change the meaning of the tab total. `result_count` is the
separate number of rows matching the current filters. The existing detail
page has no pagination layer, so Phase 3 does not add one.

Each serialized row has an actor-safe `source`/`source_label` pair and
`can_edit`/`can_delete` flags. Legacy NULL scopes use the centralized
conservative resolver. Administrators see `Riêng tư — giáo viên sở hữu` and
an audit notice; ordinary teachers see `Riêng tư — chỉ bạn` only for their own
authorized contribution. Mutation JSON responses use the same serializer,
and the browser checks failed responses and reloads the preserved detail URL
after destructive/content-changing mutations to recalculate counts/facets.

Focused verification:

```text
python3 -m unittest tests.test_question_overlay_phase3
```

Parent verification (2026-09-17): the five Phase-3 tests, five Phase-1
question-scope tests, six Phase-2 overlay tests, and four bank-list Phase-3
regression tests passed (20 total). Python compilation, Jinja rendering, and
three bounded JavaScript mutation checks (shared-row guard, failed-response
handling, successful reload) also passed. No live database or provider call
was used.
