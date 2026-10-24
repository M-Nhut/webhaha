# Refactoring baseline (Phase 0)

> Historical snapshot. This baseline and its remediation notes are retained as
> evidence and are superseded by `REFACTORING_PHASE6.md` for the current tree.

Captured on 2026-09-08 before the remaining route modularisation work.

## Compatibility contract

- **80 public Flask routes** are frozen in `tests/fixtures/route_contract.json`.
- A route comprises its URL rule, endpoint name and explicit HTTP methods.
  Flask's implicit `HEAD` and `OPTIONS` methods are deliberately excluded.
- Run `python3 -m unittest tests.test_route_contract -v` after every route
  migration. Any intentional contract change needs explicit approval and an
  updated baseline in the same change.
- Public endpoint names remain unprefixed (for example `login` and
  `practice_result`). The Phase 2 contract intentionally removes the former
  traditional exam endpoints.
  Route modules therefore register handlers directly on the app rather than
  relying on Flask Blueprint's endpoint prefixing.

## Test commands

The repository currently uses `unittest`, not pytest. The supported checks are:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
node tests/test_id6_picker.js
node tests/test_import_scope.js
```

## Baseline result

The Python discovery run completed **191 tests** with **152 passing, 18 failing
and 21 errors**. These failures are baseline work items; do not treat them as
route-migration regressions until the relevant domain is being repaired.

Known clusters:

1. `templates/base.html` calls absent `payroll`, `tuition`, and
   `parent_dashboard` endpoints, causing template rendering failures.
2. Curriculum/ID6 tests expect a 172-node catalog and older ID6 mutation rules,
   while the checked-in catalog produces 24–25 nodes and current source-ID
   behaviour differs.
3. Import/parser tests expect legacy tag parsing and question-type conversion
   that the current parser output does not provide.
4. Import scope tests reject incomplete scope data; this needs a product rule
   decision before changing the implementation or the test.

## Phase gate

Proceed with the structural route move only when the route-contract test and
the smoke checks for the route domain pass. Baseline failures may be repaired
in separate, feature-scoped changes; they are not authorised by the refactor.

## Functional remediation result

The authorized follow-up remediation completed on 2026-09-08. The stale
baseline assertions were reconciled with the current product contract (the
grade-9, Chapter-6-only 24-node catalog and three supported question types);
production behavior was repaired where the baseline exposed a real defect:

- retired payroll, tuition, parent-dashboard and teaching-record links were
  removed from supported navigation, and dashboard templates no longer render
  retired financial/payroll fields;
- LaTeX command-only questions now infer single, true/false and short-answer
  types correctly; DOCX/PDF/LaTeX ID6 metadata applies the tag's type and
  preserves legacy TL labels for read compatibility;
- new ID6 generation and authoring reject legacy essay types while import
  previews convert them to short answer; historical rows remain editable;
- duplicate tagged imports allocate the next sequence safely across banks and
  concurrent writers.

Verification, always isolated from `.env.local`, is:

    DATABASE_URL=sqlite:///:memory: POSTGRES_URL='' python3 -c 'import config,unittest; config.load_local_environment=lambda *a,**k:None; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover("tests", pattern="test_*.py")); raise SystemExit(not r.wasSuccessful())'
    node tests/test_id6_picker.js
    node tests/test_import_scope.js

Result: **192 Python tests passed, 0 failures, 0 errors, 0 skips**; both
JavaScript suites passed.
