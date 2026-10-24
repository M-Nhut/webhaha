# Bank visibility Phase 5 test report

Date: 2026-09-16

## Scope

The focused Phase 5 migration tests were run together with the requested
bank-visibility regression tests for Phases 1–4.  The Phase 5 test module now
has 11 tests: the original six service-level tests plus five small CLI tests
covering:

- dry-run output, read-only behavior, and nonzero exit status while review is pending;
- `--apply` rejection when `--expect` is missing, without creating a backup;
- missing and non-regular database paths, without creating a database file;
- an explicitly approved mapping with a verified `before.sqlite3` backup and `manifest.json`;
- replay idempotence, no second backup, and isolation of unrelated bank scopes.

All Phase 5 database fixtures are temporary regular SQLite files.  The CLI
tests invoke the migration script in a subprocess with an explicit fixture
path.  The Phase 1–4 application tests use the in-memory SQLite URL; the
Phase 1 fixture also disables local dotenv loading and asserts the engine is
`sqlite:///:memory:` before destructive fixture setup.

## Commands and results

Each command exited with status 0 and reported `OK`:

| Command | Result |
| --- | --- |
| `python3 -m unittest tests.test_bank_visibility_phase5` | 11 tests passed |
| `python3 -m unittest tests.test_bank_visibility_phase1` | 6 tests passed |
| `python3 -m unittest tests.test_bank_import_phase2_visibility` | 4 tests passed |
| `python3 -m unittest tests.test_bank_list_phase3` | 4 tests passed |
| `python3 -m unittest tests.test_bank_selection_phase4` | 6 tests passed |

Focused total: 31 tests passed (11 Phase 5 + 20 Phase 1–4 regression).

## Warnings and boundaries

Python 3.13 emitted existing `DeprecationWarning` messages for
`datetime.datetime.utcnow()` from SQLAlchemy schema setup and
`models.py:411`.  A combined regression invocation also emitted two
SQLAlchemy `ResourceWarning` messages for unclosed SQLite connections; the
individual module invocations passed.  These warnings did not fail tests and
were not changed in this test-only pass.

No production implementation, provider, environment file, or real database
was used or modified.  No live Phase 5 migration or backup was performed;
the production admin-owned legacy bank remains pending explicit review.
