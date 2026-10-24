# Refactoring Phase 3 — auto-graded practice only

## Completed

- Practice and initial-diagnostic papers now accept only single choice,
  four-statement true/false, and short-answer items with a valid automatic
  key. The fixed practice contract remains 22 items: 12 / 4 / 6.
- Short-answer grading supports numeric tolerance and case-insensitive text.
  A blank response is `unanswered`; malformed numeric learner input is an
  answered, wrong response. Missing or invalid authoring keys/rules fail the
  readiness/preflight gate and never become manual review.
- Student essay/file controls and submission-file persistence were removed.
  Any direct uploaded-file POST is rejected before a submission is created.
  Question-bank import and question/media storage remain available.
- Manual short-answer metadata is no longer an authoring choice. Existing
  manual rules are not silently converted; they fail validation until a
  teacher explicitly selects numeric or text.
- Historical pending/manual/file-only answers remain in place and readable,
  but are excluded from learner evidence. Historical result views do not
  expose submission-file links and do not offer manual regrading.
- Submission, score, mastery/error evidence, and diagnostic completion remain
  one atomic transaction. Diagnostic observed errors and future-risk labels
  remain separate as before.

## Deliberate limits

No historical submission data, answer rows, shared model fields, or uploaded
files are deleted, migrated, or automatically regraded in this phase.

## Verification

Static route/template review and `python3 -m py_compile` were run on the
changed Python modules. The application, real database, AI provider, and test
suite were not run.
