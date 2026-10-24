# Refactor integration report

> Historical integration report. It records the earlier modularisation shape;
> the current route/template inventory and final cleanup are documented in
> `REFACTORING_PHASE6.md`.

## Delivered structure

- `app.py`: 37-line composition root, same local port and WSGI export.
- `extensions.py`: shared DB, CSRF and login initialization.
- `services/database_startup.py`: existing migration SQL, seeds and backfill
  copied without changing statements, commit boundaries or execution order.
  Existing startup function imports remain available from `app`.
- `routes/`: main, auth, academic, curriculum, question_bank, imports, exams,
  practice. Central explicit registration preserves 80 public route contracts.
- `templates/components/`: navigation, header, flash messages, footer.
- `static/js/modules/`: import wizard, question bank detail, exam form/take,
  student progress charts and teacher practice filters.

Integration review fixed two extraction regressions in import_wizard.js:
upload and cancel redirect now read configuration values instead of literal
strings `config.uploadUrl` and `config.bankListUrl`. The JavaScript test now
exercises both requests and the redirect, including the CSRF header.

The authorized functional remediation then repaired the remaining baseline
defects without restoring retired roles or routes. Supported navigation no
longer calls absent payroll, tuition, parent-dashboard or teaching-record
endpoints; the dashboard no longer references retired financial/payroll
fields. LaTeX command-only questions infer their actual answer format, and
the DOCX/PDF/LaTeX ID6 adapter applies type metadata consistently. Legacy TL
tags remain readable, but new ID6 generation and authoring reject legacy essay
types while import previews convert them to short answer. Concurrent and
cross-bank duplicate tags retain unique sequences.

## Verification

- Full Python discovery: **192 tests, 192 pass, 0 failures, 0 errors, 0 skips**.
- 80-route snapshot test passes.
- Both JavaScript suites pass, including new configured-URL assertions.
- All six extracted JavaScript files pass `node --check`.
- Python compilation passes.
- In-memory startup repeated successfully; table/column names unchanged after
  the second initialization. Compatibility backfill export checked.
- Flask test client: login 200, logo 200, missing avatar 404.
- HTML templates compile. Non-HTML metadata files are excluded from this check.

Verification used an in-memory SQLite database and mocked local dotenv loading
so .env.local cannot redirect checks to a developer database.

## Reproduction and remaining limits

Run the full isolated verification with:

    DATABASE_URL=sqlite:///:memory: POSTGRES_URL='' python3 -c 'import config,unittest; config.load_local_environment=lambda *a,**k:None; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover("tests", pattern="test_*.py")); raise SystemExit(not r.wasSuccessful())'
    node tests/test_id6_picker.js
    node tests/test_import_scope.js

No production deployment, production database migration, or authenticated
browser end-to-end acceptance was performed. Existing SQL migrations still
run on application import.
