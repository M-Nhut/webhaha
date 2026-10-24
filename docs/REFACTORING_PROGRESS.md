# Refactoring progress

> Historical progress log. The Phase 4/5 notes below are retained for audit
> history and are superseded for current architecture by
> `REFACTORING_PHASE6.md`.

This workspace keeps the frozen route contract in docs/REFACTORING_BASELINE.md.

## Phase 4

- Moved exam list/create/edit/delete/take/grade/result and bank-check handlers to routes/exams.py.
- Moved student practice, progress, teacher practice, AI analysis and analytics handlers to routes/practice.py.
- Registered both groups directly with app.add_url_rule, preserving endpoint names, URLs and explicit methods.
- Kept app._select_random_bank_questions and app.backfill_adaptive_learning_history import compatibility.

## Phase 5

- Extracted base navigation, topbar header, flash area and footer scripts to templates/components/; composition and absent legacy navigation endpoints remain unchanged.
- Extracted complex client behavior to static/js/modules/ for import wizard, question-bank editing, exam form/taking, practice progress charts and teacher-practice filtering.
- Template data, route URLs and CSRF values are passed through small JSON/config initialization blocks; extracted JavaScript contains no Jinja syntax.
- Updated tests/test_import_scope.js to execute the extracted wizard module with the same scope/duplicate composition.

## Validation

- python3 -m unittest tests.test_route_contract -v — pass (80-route contract).
- node tests/test_import_scope.js — pass.
- node tests/test_id6_picker.js — pass.
- All extracted templates compile; extracted JavaScript passes node --check.
- The broader suite remains at 192 tests, 18 failures and 21 errors. The observed IDs are:
  - Adaptive/navigation: test_invalid_ai_result_uses_safe_fallback_and_teacher_route_renders_it, test_student_profile_and_exam_pages_render_explanations, test_teacher_generates_reviewable_draft_with_explanation, test_remaining_dashboards_and_forms_render_for_supported_roles, test_removed_features_have_no_routes_or_navigation.
  - Curriculum/migration: test_fresh_seed_and_catalog_options_preserve_later_edits, test_other_chapters_questions_and_high_water_marks_are_untouched, test_topic_payload_does_not_erase_existing_metadata_when_absent, test_bulk_assignment_replaces_source_id_and_preserves_content_and_original, test_canonical_code_separates_skill_from_difficulty, test_catalog_and_classification_pages_render, test_catalog_seed_matches_user_data_and_is_idempotent, test_concurrent_writers_cannot_allocate_the_same_sequence, test_evaluation_page_exports_blinded_packet_and_scores_uploaded_labels, test_imported_duplicate_tags_get_distinct_sequence_across_banks, test_legacy_mapping_does_not_block_question_deletion, test_manual_true_false_saves_false_and_four_answers, test_migration_retains_legacy_source_and_is_idempotent, test_preview_does_not_reserve_numbers, test_sequences_shared_across_types_and_levels_and_stable_on_edit, test_teacher_can_accept_unchanged_suggestion_but_not_a_stale_one.
  - Formula/import/parser: test_retry_endpoint_rerenders_persisted_latex_source, test_id6_metadata_is_saved_per_question, test_docx_split_runs_tag_detects_essay, test_duplicate_import_tags_warn_and_save_unique_ids, test_legacy_tag_is_upgraded_by_adapter, test_partially_tagged_tex_does_not_shift_ids, test_pdf_upload_detects_tag_type, test_tex_four_types_preview_resume_edit_and_confirm.
  - Phase-2 policy: test_api_disallows_legacy_new_questions_without_curriculum, test_legacy_codes_remain_readable_but_cannot_be_generated, test_manual_exam_three_formats_and_invalid_edit_keeps_old_questions, test_unsupported_and_incomplete_types_cannot_enter_new_exams.
  Rendering templates that include the preserved base navigation still raises for absent payroll, tuition, and related endpoints; these were intentionally not repaired in this refactor.
