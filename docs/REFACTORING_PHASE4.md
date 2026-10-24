# Refactoring Phase 4 — retire classroom scheduling and attendance

## Completed

- Removed the `Schedule` and `Attendance` ORM models and the corresponding
  `User`/`Course` relationships. `Course.classroom` remains because it is
  independent course metadata.
- Removed schedule CRUD, center/teacher/student timetable, personal schedule,
  attendance listing, and attendance marking handlers and URL registrations
  from `routes/academic.py`.
- Moved retained enrollment/roster visibility and dashboard learning summaries
  to `services/dashboard.py`; teacher/student dashboard cards no longer depend
  on calendar or attendance metrics.
- Removed the retired scheduling service, helper exports, navigation links,
  dashboard timetable panel, course inline schedule panel, timetable/attendance
  templates, and exclusive CSS.
- Removed startup sample schedule seeding and legacy schedule/attendance schema
  rewrite/alter code. Question-bank dormant imports and the route-contract
  fixture were updated accordingly.

## Removed files

- `services/scheduling.py`
- `templates/schedules.html`
- `templates/schedule_form.html`
- `templates/timetable.html`
- `templates/partials/timetable_grid.html`
- `templates/attendance.html`
- `templates/mark_attendance.html`

## Retained data limitation

This phase changes the application mapping and startup behavior only. It does
not drop or alter physical `schedule`/`attendance` tables, rows, uploads, or
other real database data. Existing tables stay untouched for the phase-5 data
cleanup/migration decision.

## Verification

Static route/template/reference review and `python3 -m py_compile` were run on
the changed Python modules. The application, real database, AI provider, and
test suite were not run.
