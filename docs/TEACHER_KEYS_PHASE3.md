# Teacher-owned Gemini keys (Phase 3)

Phase 3 makes the assigned teacher's deterministic default key group the only
effective credential pool for every class report and teacher-triggered learner
analysis.  The resolver selects the oldest row marked `is_default` for the
current `Course.teacher_id` (`id ASC`).  A course's retained
`ai_key_group_id` is legacy metadata only: it is not consulted for routing,
availability, cache identity, or provider calls.

## Course behavior

- A newly-created course leaves the legacy group column empty and resolves the
  assigned teacher's default at request time.
- Editing a course keeps an existing legacy value untouched when the teacher
  is unchanged.  Transferring a course clears that stale legacy value, while
  the next request resolves the new teacher's default.
- The old per-course assignment endpoint remains routable for stale clients,
  but is a no-op.  Submitted group ids cannot override the owner default.
- Existing groups, encrypted keys, report rows, and ownership/history are not
  merged, deleted, or migrated in this phase.

## Availability and cache safety

No default group, paused/deleted default, missing teacher, or missing verified
key is an actionable unavailable configuration.  The gateway never falls back
to another teacher or to a process environment credential for a course.  A
default group with no eligible (`last_test_status == "ok"`) key fails at the
provider boundary without an outbound request.

The default lookup is read-only and shared by settings, gateway, and report
identity checks.  Unavailable report identities use the current owner/default,
not a stale course mapping.  When no default exists, the existing configuration
revision field carries a negative owner marker for new unavailable snapshots;
this avoids a schema migration while preventing a fallback from being reused
after course reassignment.  The owner is also included in the report input
fingerprint.

Before each outbound attempt, including a transient retry, the gateway
revalidates the course, current teacher, selected oldest default, group
revision, group activity, and key membership/activity.  A transfer, deletion,
pause, or configuration change therefore stops a stale request instead of
sending the former owner's credential.

## Scope

Phase 3 does not add rotation policy, project controls, migrations, schema
changes, or provider calls outside the existing encrypted gateway.  Tests use
an in-memory database and mocked HTTP sessions only.
