# Route refactor — Phase 1: practice runtime

Phase 1 moved the student self-practice runtime out of the former exam route.
Practice and legacy `initial_diagnostic` papers now use dedicated handlers:

- `practice_take`: `GET/POST /practice/<exam_id>/take`
- `practice_result`: `GET /practice/<exam_id>/result`

The handlers enforce the existing fixed-paper ownership and active-course
enrollment checks. They retain the 22-item scoring contract, frozen question
snapshots, atomic submission/evidence/mastery updates, diagnostic completion,
and `PracticeSession` continue/end behavior. AI report routes remain available
in their existing locations.

The compatibility URLs described during Phase 1 were removed in Phase 2 along
with the traditional exam authoring/taking/result/grading surface. Canonical
practice and diagnostic runtime URLs are the only supported taking/result
entry points.

The public route contract fixture includes the two intentional Phase 1
runtime routes.
