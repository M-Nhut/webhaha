# Teacher-owned Gemini keys (Phase 1–2)

The teacher surface intentionally has one small workflow: paste up to 20
Gemini keys, one per line, and choose **Kiểm tra và lưu**. The server encrypts
each key, sends one minimal synthetic JSON probe, and marks a key ready only
after a successful response. The configured teacher model is the backend
constant `gemini-3.8-flash`; the browser cannot override it.

Every key/group remains owned by exactly one teacher. A course uses its
explicitly retained group mapping when one exists, otherwise the teacher's
default group. The gateway never searches another teacher's credentials and
teacher web requests never fall back to a shared process environment key.

## Server setup

Before enabling the teacher AI settings page, configure these two independent,
stable server secrets on every web worker:

```text
FLASK_SECRET_KEY=<long random session-signing secret>
AI_CREDENTIAL_ENCRYPTION_KEY=<Fernet key>
```

Generate the encryption value outside the application with:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`AI_CREDENTIAL_ENCRYPTION_KEY` is the only secret used to encrypt provider
keys at rest. The application never derives encryption from Flask's session
secret and fails closed when the encryption key is missing or invalid. A
process-local Flask secret lets a developer run ordinary local pages, but
sessions will not survive a restart and teacher credentials cannot be managed
or used until `FLASK_SECRET_KEY` is explicitly configured.

Teacher groups call Gemini through its OpenAI-compatible endpoint by default:

```text
GEMINI_OPENAI_API_URL=https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
```

Teacher probes and new teacher report requests use `gemini-3.8-flash`. Older
rows may retain their historical `model_name` value so report/history records
are not rewritten; that value is not a client-selectable routing override.

## Key and quota behavior

The existing `TeacherAIKey` columns are reused: Fernet ciphertext, SHA-256
duplicate fingerprint, masked final hint, `last_tested_at`,
`last_test_status`, and `last_error_code`. Plaintext is never rendered or
logged. The list exposes only the masked key, safe status, last-check time,
**Thử lại**, and **Xóa**. A failed/unverified key is never a report rotation
candidate.

Probe failures are reduced to safe categories: invalid/revoked, permission,
quota/rate limit, network unavailable, model not found, malformed response,
or provider request failure. Response bodies and credentials are never
persisted in report errors. A quota response retains the existing project
cooldown behavior; the simplified form uses the safe default project scope
because project labels are a later phase concern.

`AI_GEMINI_MAX_HTTP_ATTEMPTS` is the per-request outbound-call budget
(including transient retries). The deprecated `AI_GEMINI_MAX_PROJECT_ATTEMPTS`
name is accepted only for compatibility. Projects skipped because they are
already cooling down do not consume that budget.

Class report fallbacks are reusable only for a short configured retry window
(`CLASS_REPORT_FALLBACK_RETRY_SECONDS`, default 60 seconds). A group
configuration revision remains part of report cache identity. Adding/deleting
or invalidating a key therefore cannot make an unrelated old report appear to
be a current provider result.

If several historical groups exist, the oldest existing default is displayed
and used by the simplified page. Other encrypted keys and explicit course
mappings are intentionally not merged or migrated in Phase 1–2. If no default
exists, the first successful save creates an internal teacher-owned default
group; this does not rewrite old group rows or course mappings.

## Legacy process environment key

Existing direct service integrations can still use `AI_ANALYSIS_API_URL`,
`AI_ANALYSIS_API_KEY`, and `AI_ANALYSIS_MODEL` when they explicitly construct
the legacy configuration. Teacher web requests do not use them, even when
`AI_LEGACY_ENV_FALLBACK_ENABLED` is set. An explicit missing, disabled, or
wrong-owner group is an error, never a path to the shared key.

## Verification

Tests use an in-memory database and fake HTTP sessions. They do not read local
environment files or call Gemini:

```bash
python3 -c 'import os,unittest; from unittest.mock import patch; os.environ["DATABASE_URL"]="sqlite:///:memory:"; p=patch("config.load_local_environment"); p.start(); result=unittest.TextTestRunner().run(unittest.defaultTestLoader.discover("tests",pattern="test*.py")); raise SystemExit(not result.wasSuccessful())'
```
