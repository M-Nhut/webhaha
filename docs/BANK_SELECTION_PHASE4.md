# Bank selection — Phase 4

Phase 4 connects the existing diagnostic and personalized-practice consumers
to the server-owned bank visibility policy.  It changes only eligibility for a
new selection; the fixed-paper contract, scoring, adaptive ranking and stored
history remain unchanged.

## Class-scoped authorization

- A teacher creating an initial diagnostic may select an active explicit
  `shared` bank or that teacher's active `private` (including compatible
  teacher-owned legacy `NULL`) bank.
- A teacher's selector never exposes another teacher's private bank.  The
  request is rechecked server-side, so posting a forged private-bank id cannot
  change the source.
- A class diagnostic source is revalidated through `can_use_bank` using the
  teacher currently assigned to the class.  The student and an administrator
  are never used as the policy actor for this decision.
- Teacher practice selectors use the same policy.  Shared banks appear as
  read/use candidates; private banks remain limited to their owner.

## Teacher transfer behavior

The diagnostic's frozen source remains usable after a class is transferred
when it is a valid shared bank and the new class teacher can use it.  A source
that is private to the former teacher fails closed for new personalized
generation and for Continue.  Frozen papers, submissions and learning history
are retained exactly as stored; Phase 4 does not rewrite or delete them.

Teacher-issued fixed practice provenance is reviewed on Continue.  All banks
captured by its persisted session must be authorized for the current class
teacher.  Thus an authorized shared source can continue across a transfer,
while a former teacher's private pool cannot.  Legacy fixed papers without the
new provenance marker are accepted only when their persisted creator is a
teacher; the same current-teacher bank check still applies.

## Deliberately unchanged

- No visibility backfill or migration is performed (Phase 5 remains separate).
- No import destination or general bank-list behavior is changed here.
- The 22-question / 40-minute paper and 12 single + 4 true/false + 6 short
  answer scoring contract are unchanged.
- AI configuration, key rotation, provider calls and historical rows are
  untouched.

## Focused verification

`tests/test_bank_selection_phase4.py` uses an in-memory SQLite database to
cover selector visibility, forged private-bank rejection, shared-source
survival after teacher transfer, former-private-source blocking, and teacher
provenance transition behavior.  It does not run against a production database
or call an external provider.
