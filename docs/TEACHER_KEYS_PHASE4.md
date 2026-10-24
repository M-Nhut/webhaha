# Teacher Gemini keys — Phase 4

Phase 4 adds bounded runtime rotation to the teacher-owned Gemini gateway.
The effective pool is still the current teacher's oldest default group (an
inactive oldest default fails closed rather than falling through to a newer
one);
course mappings, other teachers' groups, migrations, and deletion are outside
this phase.

## Runtime policy

- Only keys with an explicit successful probe (`last_test_status == "ok"`) and
  `is_paused == false` are eligible.  A key that was never verified is never
  promoted by a provider response.
- The gateway claims the head of the existing `sort_order` queue and moves it
  to the tail before an outbound call.  This gives round-robin behavior across
  requests without changing the group's `config_revision`, so queue rotation
  does not invalidate report/fallback cache identity.  The per-group process
  lock and a database `FOR UPDATE` request prevent duplicate claims within a
  worker; fairness across independent web workers is best effort until a later
  schema phase adds an explicit cursor/claim column.
- A 401 (or an explicit invalid/revoked marker) pauses that key and it stays
  ineligible until a successful manual verification.  An explicit per-key
  permission denial is handled the same way.  A generic model/configuration,
  malformed-response, or bad-request error stops the current request without
  trying every key.
- 5xx and network errors use the existing bounded transient retry,
  `AI_GEMINI_MAX_HTTP_ATTEMPTS`, and deadline settings.  A runtime transport
  error does not overwrite successful verification with `failed`; the key can
  be considered again by a later request.  No provider response is persisted.

## Quota and `Retry-After`

429/quota responses create or extend the existing `AIProjectCooldown` row.  A
cooling project is skipped without consuming the HTTP-attempt budget, and
keys carrying the same project scope are not blindly cycled after the first
quota response.  The request never sleeps for the full provider wait; it may
try a known-different project within the bounded budget and otherwise returns
a safe unavailable/cooldown error.  `Retry-After` accepts both delta seconds
and an HTTP-date.  A valid provider delay is never truncated to the old
one-hour cap; malformed headers use the bounded server cooldown setting.

Cooldown is runtime state, not probe state.  A previously verified key keeps
its `last_test_status == "ok"` and test timestamp while its project is waiting.
The teacher settings page shows “đã xác minh · đang chờ hạn mức” separately.

`project_ref` is an operator label, not proof of the provider project behind a
credential.  The default label conservatively treats keys using that label as
one shared scope, which can reduce availability.  Different labels do not
prove that their real projects differ, so this behavior must not be described
as quota circumvention.  Accurate project identity belongs to a later phase.

## Safety and fallback

If the verified pool is paused, unverified, cooled, or exhausted by bounded
provider failures, the gateway returns a sanitized actionable unavailable
error.  Existing class/learner services may record their deterministic
observed-data fallback; that fallback contains no fabricated AI answer and
does not unblock a practice attempt by inventing provider output.

No plaintext key is logged or rendered.  Phase 4 adds no database migration,
does not mutate `.env`/production secrets, and does not merge or delete legacy
groups.

## Focused verification

The Phase 4 tests use an in-memory database and fake HTTP sessions only:

```bash
python3 -m unittest tests.test_teacher_keys_phase4 -v
```
