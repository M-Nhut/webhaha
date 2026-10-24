# APTGA v1 implementation

Specification: `APTGA_SPEC.md`.

Implemented in `services/aptga.py` and integrated in
`AdaptiveEngine.select_questions`. Both practice creation paths save the
versioned `aptga` audit in exam adaptive_metadata. Existing result keys remain.

The legacy aggregate mastery/recommend_difficulty public APIs remain compatible
for existing displays. The actual practice selector uses its own recent,
skill×level evidence and integer quota plan; its returned recommendation is
overridden with that plan. This avoids rewriting old grades/snapshots during
deployment. The v1 matrix is visible in the selection profile and persisted
exam audit; older report mastery displays are not replaced in this change.

No schema migration, external AI call or production database cleanup is needed.
Historical questions without a confirmed skill may be probes only; they cannot
contribute to a known skill estimate. Explicit outside-lesson metadata is excluded.
Cooldown uses both bank ID and content hash, with five days and three sessions.
Exposure comes from frozen questions in submitted sessions of the selected
subject, including unanswered or not-yet-finalized attempts; those rows affect
cooldown only and never become mastery evidence.
Shortfall returns fewer questions and a visible explanation rather than silently
changing levels. Small tests may therefore be empty when no requested-level
questions exist; existing creation routes handle empty selection.

Prerequisite transfer awaits a reviewed domain graph; AI selection influence is
zero pending validated question-to-misconception mapping. Class/individual AI
reports retain their existing observed-errors versus unvalidated-risk contract.
These are explicit v1 boundaries, not claims that learning effectiveness or
prediction accuracy has been established.

Validation: full isolated unittest discovery passed 220 tests. Added pure tests
for integer quotas/evidence/recency and integration checks for weak-skill novel
selection, cooldown and insufficient-bank behavior. The older test that treated
two aggregate errors as mastery now explicitly verifies preserved error context
and unknown/probe status. Both existing JavaScript suites pass.

Tests must set DATABASE_URL to sqlite:///:memory: and mock
config.load_local_environment before test discovery/importing app, so dotenv
cannot select a developer database. See tests/test_aptga.py and the APTGA
cases in test_personalization_mvp.py/test_adaptive_personalization.py.
