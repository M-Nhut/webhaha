# Phase 2: common diagnostic contract

The initial diagnostic is one frozen, common paper for a class.  It never uses
a student's profile or learning history to select questions.

- `22` questions in `40` minutes.
- Type quotas: `12` single choice, `4` true/false, `6` short answer.
- The non-personalized APTGA baseline `.4/.3/.2/.1` is apportioned to
  `9/7/4/2` for nhận biết/thông hiểu/vận dụng/vận dụng cao.
- Eight skill codes are all covered: the deterministic common target is three
  items for the first six catalog skills and two for the final two.
- The selector satisfies type, level, and skill quotas simultaneously.  It
  does not add duplicate fillers or silently relax a quota when the bank is
  insufficient or intersections are impossible.

The `Exam.question_bank_id` association records the class-level source bank;
each copied `ExamQuestion` also holds its frozen source snapshot.  Generated
practice papers now use the same 40-minute constant, while historical papers
retain their stored duration.  Broader practice-source association/presentation
is not changed in Phase 2 and remains deferred to Phase 3.
