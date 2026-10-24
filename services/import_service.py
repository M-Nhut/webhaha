"""
Import Service — Orchestrates the lifecycle of a TeX ImportSession.
Handles upload, parsing, preview, updating, confirmation, cancellation, and temp file cleanup.

Formula pipeline:
  - Create/get FormulaAsset by content_hash (deduplicate).
  - Preserve LaTeX/MathML source and cached SVGs for existing question content.
  - Remap temporary IDs to FormulaAsset.id in all question text fields.
"""

import hashlib
import logging
import os
import json
import re
import uuid
import datetime as dt
from database import db
from models import ImportSession, QuestionBank, BankQuestion, BankQuestionOption, FormulaAsset
from services.question_normalizer import normalize_questions
from services.question_validator import validate_questions
from services.question_policy import canonical_type
from services.import_scope import editable_session, validate_session_scope, refresh_preview
from services.access_control import set_new_bank_visibility, set_new_question_scope
from services.import_authorization import fresh_import_actor, fresh_import_bank
from services.import_duplicates import duplicate_candidate_rows

UPLOAD_TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "temp")
QUESTION_IMAGE_FILENAME_PATTERN = re.compile(
    r"/static/uploads/questions/([A-Za-z0-9._-]+)"
)
# The bank-import contract intentionally accepts only source TeX.  Rendered
# PDF files remain an internal LaTeX-renderer detail, not an import format.
SUPPORTED_IMPORT_EXTENSIONS = frozenset({"tex", "latex"})
logger = logging.getLogger(__name__)


def ensure_temp_dir():
    """Ensure upload temp directory exists."""
    os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)


def _receipt_without_match_payload(receipt):
    """Return a replay-safe receipt without historical duplicate matches.

    A receipt can outlive the permissions that made its duplicate matches
    visible.  Saved-question ids and summary/count fields remain useful for
    idempotent replay, while match payloads are deliberately reloaded through
    the current actor-scoped preview path instead of being served from cache.
    """
    if not isinstance(receipt, dict):
        return receipt

    safe_receipt = dict(receipt)
    rows = receipt.get("rows")
    if isinstance(rows, list):
        safe_rows = []
        for row in rows:
            if not isinstance(row, dict):
                safe_rows.append(row)
                continue
            safe_row = dict(row)
            safe_row["matches"] = []
            safe_rows.append(safe_row)
        safe_receipt["rows"] = safe_rows
    return safe_receipt


class ImportService:

    @staticmethod
    def _store_validation_result(session, validation_result):
        """Persist a validator result in one place so preview counters agree."""
        session.set_parsed_questions(validation_result["questions"])
        stats = validation_result["stats"]
        session.total_count = stats["total"]
        session.valid_count = stats["valid"]
        session.warning_count = stats["warning"]
        session.error_count = stats["error"]

    @staticmethod
    def _parse_upload(temp_file_path, file_extension):
        """Dispatch to the parser matching a validated uploaded file type."""
        if file_extension in ("tex", "latex"):
            from services.latex_parser import parse_latex
            return parse_latex(temp_file_path)
        # Retained as a defensive fallback even though callers validate types.
        return []

    @staticmethod
    def create_and_process_session(user_id, file_obj, filename, bank_id=None):
        """
        1. Save uploaded file to temp storage
        2. Create ImportSession DB record
        3. Parse the TeX source file
        4. Normalize & validate questions
        5. Save parsed JSON to ImportSession
        6. Return ImportSession instance
        """
        # Route checks are intentionally repeated here because this service is
        # also callable from maintenance/integration code.  Importing into a
        # shared bank is never allowed for a teacher, regardless of client
        # supplied bank ids.
        actor = fresh_import_actor(user_id)
        if bank_id is not None:
            fresh_import_bank(bank_id, actor)

        ensure_temp_dir()
        ImportService.cleanup_expired_temp_files()
        
        file_ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if file_ext not in SUPPORTED_IMPORT_EXTENSIONS:
            raise ValueError(
                f"Định dạng file .{file_ext} không được hỗ trợ. "
                "Chỉ nhận LaTeX (.tex, .latex)."
            )

        session_id = str(uuid.uuid4())
        safe_filename = f"{session_id}_{filename}"
        temp_file_path = os.path.join(UPLOAD_TEMP_DIR, safe_filename)
        
        # Save file to disk temporarily
        file_obj.save(temp_file_path)

        session = ImportSession(
            id=session_id,
            user_id=user_id,
            bank_id=bank_id,
            filename=filename,
            file_type=file_ext,
            file_path=temp_file_path,
            status="processing",
        )
        db.session.add(session)
        db.session.commit()

        try:
            raw_questions = ImportService._parse_upload(temp_file_path, file_ext)
            if not raw_questions:
                raise ValueError('Không tìm thấy câu hỏi. Hãy thêm các khối ex vào mẫu; ví dụ nằm trong dòng chú thích % không được nhập.')
            from services.latex_document import document_profile
            profile = document_profile(raw_questions)
            if profile['document_kind'] == 'assessment':
                session.scope_data = json.dumps(profile, ensure_ascii=False)

            # Normalize questions
            normalized = normalize_questions(raw_questions)

            # Get only actor-authorized bank rows for the validator's early
            # duplicate warning.  The stronger review report is refreshed by
            # ``refresh_preview``/``scan_duplicates``; this first pass must
            # still avoid putting a foreign private supplement's text into
            # the session before that report exists.
            existing_bank_questions = []
            if bank_id:
                bank = db.session.get(QuestionBank, bank_id)
                if bank:
                    existing_bank_questions = duplicate_candidate_rows(bank, actor)

            # Validate questions
            val_result = validate_questions(normalized, existing_bank_questions)
            ImportService._store_validation_result(session, val_result)
            session.status = "preview"
            
            db.session.commit()
            return session

        except Exception:
            session.status = "failed"
            db.session.commit()
            raise

    @staticmethod
    def get_session(session_id):
        """Retrieve an ImportSession by ID."""
        return db.session.get(ImportSession, session_id)

    @staticmethod
    def update_preview_question(session_id, q_index, updated_question_data, *, commit=True):
        """Update a specific question in the parsed data preview."""
        session = db.session.get(ImportSession, session_id)
        if not session or session.status != "preview":
            raise ValueError("Phiên import không tồn tại hoặc đã đóng.")

        questions = session.get_parsed_questions()
        if q_index < 0 or q_index >= len(questions):
            raise IndexError("Chỉ số câu hỏi không hợp lệ.")

        # Merge updated data
        target_q = questions[q_index]
        if target_q.get('saved_question_id'):
            raise ValueError('Câu đã được lưu; chỉnh sửa tại ngân hàng câu hỏi.')
        protected = {
            'import_uid', 'source_position', 'source_label', 'index',
            'saved_question_id', 'duplicate',
        }
        updates = {k: v for k, v in updated_question_data.items() if k not in protected}
        if "question_type" in updates:
            # Inline edits may come from a browser resuming an older preview.
            # Apply the same legacy essay -> short answer migration as uploads.
            updates["question_type"] = canonical_type(updates["question_type"])
        target_q.update(updates)
        from services.latex_parser import normalize_question_latex
        normalize_question_latex(target_q)
        # A teacher edit is a new review attempt. Any confirmation-only
        # readiness error is recalculated by the next preview/confirm pass.
        target_q.pop('confirmation_errors', None)
        
        # Reset errors/warnings and re-validate single question
        target_q["errors"] = []
        target_q["warnings"] = []
        
        # Re-validate all questions to keep stats accurate
        ImportService._store_validation_result(session, validate_questions(questions))
        
        if commit:
            db.session.commit()
        return session

    @staticmethod
    def retry_preview_formula(session_id, formula_id, *, commit=True):
        """Re-render one temporary LaTeX block in an open import preview."""
        session = db.session.get(ImportSession, session_id)
        if not session or session.status != "preview":
            raise ValueError("Phiên import không tồn tại hoặc đã đóng.")

        questions = session.get_parsed_questions()
        formula_data = None
        for question in questions:
            formulas = question.get("formulas") or {}
            if formula_id in formulas:
                formula_data = formulas[formula_id]
                break

        if not formula_data:
            raise ValueError("Không tìm thấy công thức trong phiên import.")
        if formula_data.get("source_format") != "LaTeXBlock" or not formula_data.get("source_text"):
            raise ValueError("Công thức tạm không có source LaTeX để chạy lại.")

        from services.latex_renderer import render_latex_block_result
        result = render_latex_block_result(
            formula_data["source_text"],
            preamble=formula_data.get("source_preamble") or "",
        )
        formula_data["svg_cache_key"] = result.get("url")
        formula_data["render_method"] = result.get("method")
        formula_data["render_error"] = result.get("error")
        formula_data["conversion_status"] = "fallback_svg" if result.get("url") else "failed"
        formula_data["verification_status"] = "verified" if result.get("verified") else "needs_review"
        formula_data["needs_review"] = not bool(result.get("verified"))

        ImportService._store_validation_result(session, validate_questions(questions))
        if commit:
            db.session.commit()
        return session, formula_data, result

    @staticmethod
    def confirm_import(session_id, bank_id, user_id, *, new_bank=None, confirmation_token=None):
        """
        Confirm import: Write valid and warning questions to database inside a transaction.
        
        FormulaAsset handling:
          - Deduplicate by content_hash (SHA-256).
          - LaTeX formulas with source metadata remain retryable/renderable.
          - Existing formula assets remain deduplicated by content hash.
          - Remap temp UUIDs → FormulaAsset.id in all text fields.
        """
        # This method owns its transaction. Restart after route-level read checks
        # so SQLite acquires its write lock before reading the current bank.
        from services.import_transactions import lock_import_transaction
        lock_import_transaction()
        session = db.session.get(ImportSession, session_id, populate_existing=True)
        actor = fresh_import_actor(user_id)
        if not session or session.user_id != user_id:
            raise ValueError('Không có quyền truy cập phiên import.')
        if (session.get_scope() or {}).get('document_kind') == 'assessment':
            raise ValueError('Đề chưa phân dạng cần được lưu tại mục Đề kiểm tra.')
        results = session.get_results()

        # The session's persisted target is authoritative.  Reload and
        # authorize it before considering an idempotent receipt so a replay
        # cannot disclose an old target after access is revoked.  A forged
        # request target must also fail before receipt lookup.
        persisted_bank = (
            fresh_import_bank(session.bank_id, actor)
            if session.bank_id is not None else None
        )
        if session.bank_id is not None:
            if bank_id is not None and bank_id != session.bank_id:
                raise ValueError('Ngân hàng đích không khớp phiên import. Hãy đổi đích và dò lại trước khi lưu.')
            bank = persisted_bank
        else:
            bank = fresh_import_bank(bank_id, actor) if bank_id is not None else None

        # A preview revision is also an authorization snapshot.  Recompute it
        # with the fresh actor and target before looking up a cached receipt;
        # otherwise an optional confirmation token could bypass a teacher ->
        # admin (or target-owner/scope) change between preview and confirm.
        stored_report = session.get_duplicate_report() or {}
        stored_revision = stored_report.get('revision')
        if session.status != 'confirmed':
            if not stored_revision:
                raise ValueError('Hãy tải bản xem trước và duyệt câu hỏi trước khi lưu.')
            from services.import_duplicates import revision
            fresh_revision = revision(
                session,
                session.get_parsed_questions(),
                actor=actor,
                bank=bank,
            )
            if fresh_revision != stored_revision:
                raise ValueError('Quyền hoặc phạm vi ngân hàng đã thay đổi. Hãy tải lại bản xem trước trước khi lưu.')
        if confirmation_token and confirmation_token in results:
            db.session.rollback()
            receipt = _receipt_without_match_payload(results[confirmation_token])
            return {**receipt, 'replayed':True}
        if session.status == 'confirmed' and results and not confirmation_token:
            receipt = _receipt_without_match_payload(list(results.values())[-1])
            db.session.rollback()
            return {**receipt,'replayed':True}
        editable_session(session_id,user_id)
        validate_session_scope(session)
        if not bank and not (new_bank or {}).get('name','').strip():
            raise ValueError('Hãy chọn ngân hàng hoặc nhập tên ngân hàng mới.')
        if bank and not session.bank_id:
            session.bank = bank
            session.bank_id = bank.id
            session.duplicate_decisions = None
        refresh_preview(session)
        questions = session.get_parsed_questions()
        # A review confirmation is stricter than a draft preview: answer keys
        # and auto-scoring metadata must already make the new row selectable.
        # Invalid rows become per-row errors and are skipped; old rows are not
        # retroactively approved or changed.
        from services.id6_metadata import validate_teacher_confirmation
        from services.import_duplicates import scan_duplicates
        general = session.get_scope().get('mode') == 'general'
        if general:
            from services.question_policy import require_valid_answers
            for question in questions:
                if question.get('saved_question_id'):
                    continue
                try:
                    require_valid_answers(question)
                except ValueError as exc:
                    question.setdefault('errors', []).append(str(exc))
                    # Retain the stricter save error when a partial receipt
                    # is resumed; editing the row clears it at the boundary.
                    question['confirmation_errors'] = [str(exc)]
                    question['status'] = 'error'
        else:
            validate_teacher_confirmation(questions)
        report = scan_duplicates(session, questions, actor=actor, bank=bank)
        session.duplicate_report = json.dumps(report, ensure_ascii=False)
        session.set_parsed_questions(questions)
        for status in ('valid', 'warning', 'error'):
            setattr(session, status + '_count', sum(q.get('status') == status for q in questions))
        current_revision = report['revision']
        if confirmation_token and confirmation_token != current_revision:
            raise ValueError('Phiên đã thay đổi. Hãy tải lại kết quả trước khi lưu.')
        token = confirmation_token or current_revision
        if not report['eligible'] and not report['duplicate'] and not report['review']:
            raise ValueError('Không có câu hợp lệ để lưu.')
        if not bank and report['eligible']:
            bank = QuestionBank(name=new_bank['name'].strip(), subject=new_bank.get('subject','Toán'),
                                grade=new_bank.get('grade',''),created_by=user_id)
            # New scope is derived from the authenticated actor, never from
            # the request's ``new_bank`` payload.
            set_new_bank_visibility(bank, actor)
            db.session.add(bank); db.session.flush()
            session.bank = bank
            session.bank_id = bank.id
        imported_count = 0
        updated_count = 0

        try:
            # Transaction block
            for q_data in questions:
                # Skip error questions
                if q_data.get("status") == "error" or q_data.get('duplicate',{}).get('state') != 'new':
                    continue

                # Process formulas and remap UUIDs → FormulaAsset IDs
                uuid_map = {}
                formulas_data = q_data.get("formulas", {})
                for old_uuid, f_data in formulas_data.items():
                    # Compute content_hash if not already present
                    content_hash = f_data.get("content_hash")
                    if not content_hash:
                        # Generate hash from available data
                        hash_source = (
                            f_data.get("latex")
                            or f_data.get("mathml")
                            or f_data.get("source_text")
                            or old_uuid
                        )
                        content_hash = hashlib.sha256(hash_source.encode("utf-8") if isinstance(hash_source, str) else hash_source).hexdigest()
                        
                    # Deduplicate by content_hash
                    existing_asset = db.session.query(FormulaAsset).filter_by(content_hash=content_hash).first()
                    if existing_asset:
                        # A previous import may have created a pending asset
                        # before SVG preview extraction was available. Enrich
                        # it so every later bank/exam view can display the
                        # formula immediately after confirmation.
                        preview_url = f_data.get("preview_url")
                        if preview_url:
                            existing_asset.svg_cache_key = preview_url
                            if f_data.get("source_format") == "LaTeXBlock":
                                # For document-level TeX the SVG is the final
                                # browser representation.
                                existing_asset.conversion_status = "fallback_svg"
                                existing_asset.verification_status = f_data.get(
                                    "verification_status", "needs_review"
                                )
                            elif existing_asset.conversion_status != "converted":
                                # Preserve a legacy pending asset's state when
                                # a later preview only contributes an image.
                                existing_asset.conversion_status = f_data.get(
                                    "conversion_status", "pending"
                                )
                                existing_asset.verification_status = "needs_review"

                        for field_name in (
                            "source_text", "source_preamble", "render_method", "render_error"
                        ):
                            incoming_value = f_data.get(field_name)
                            if incoming_value is not None:
                                setattr(existing_asset, field_name, incoming_value)

                        incoming_status = f_data.get("conversion_status")
                        if incoming_status == "converted":
                            if f_data.get("mathml"):
                                existing_asset.mathml = f_data["mathml"]
                            if f_data.get("latex"):
                                existing_asset.latex = f_data["latex"]
                            existing_asset.conversion_status = "converted"
                            if not f_data.get("needs_review", False):
                                existing_asset.verification_status = "verified"
                        uuid_map[old_uuid] = existing_asset.id
                    else:
                        # Determine conversion and verification status
                        conversion_status = f_data.get("conversion_status", "pending")
                        needs_review = f_data.get("needs_review", False)
                        
                        if conversion_status == "converted" and not needs_review:
                            verification_status = "verified"
                        elif needs_review:
                            verification_status = "needs_review"
                        else:
                            verification_status = "needs_review"
                        
                        new_asset = FormulaAsset(
                            content_hash=content_hash,
                            mathml=f_data.get("mathml"),
                            latex=f_data.get("latex"),
                            source_text=f_data.get("source_text"),
                            source_preamble=f_data.get("source_preamble"),
                            source_format=f_data.get("source_format"),
                            parse_confidence=f_data.get("parse_confidence", 1.0),
                            conversion_status=conversion_status,
                            verification_status=verification_status,
                            svg_cache_key=f_data.get("preview_url"),
                            render_method=f_data.get("render_method"),
                            render_error=f_data.get("render_error"),
                        )
                        
                        db.session.add(new_asset)
                        db.session.flush()  # get new_asset.id
                        uuid_map[old_uuid] = new_asset.id

                # Helper to remap UUIDs in text
                def remap_text(text):
                    if not text:
                        return text
                    for old_u, new_u in uuid_map.items():
                        text = text.replace(f"[[formula:{old_u}]]", f"[[formula:{new_u}]]")
                    return text

                q_type = canonical_type(q_data.get("question_type", "single"))
                source_id = q_data.get("source_id") or None

                conf_scores = q_data.get("confidence_scores")
                conf_json = json.dumps(conf_scores) if isinstance(conf_scores, dict) else None
                reviewed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
                classification = dict(q_data.get('classification') or {})
                classification['curriculum_mode'] = 'general' if general else 'probability9'
                classification.update(
                    status='teacher_confirmed', locked=True,
                    reviewed_by=user_id, reviewed_at=reviewed_at,
                    review_source='import_confirm',
                )

                bq = BankQuestion(
                    bank_id=bank.id,
                    question_text=remap_text(q_data.get("question_text", "")),
                    context=remap_text(q_data.get("context", "")),
                    image_url=q_data.get("image_url", ""),
                    question_type=q_type,
                    difficulty_level=q_data.get("difficulty_level", "nhan_biet"),
                    points=float(q_data.get("points", 1.0)),
                    explanation=remap_text(q_data.get("explanation", "")),
                    confidence_scores=conf_json,
                    subject=bank.subject,
                    grade=q_data.get("grade") or bank.grade,
                    topic=q_data.get("topic") or bank.topic,
                    source_id=source_id,
                    chapter=q_data.get("chapter") or None,
                    section=q_data.get("section") or None,
                    question_category=q_data.get("question_category") or None,
                    curriculum_node_id=q_data.get("curriculum_node_id") or None,
                    classification_status='teacher_confirmed',
                    classification_data=json.dumps(classification, ensure_ascii=False),
                    learning_metadata=json.dumps(q_data.get('learning_metadata') or {}, ensure_ascii=False),
                    created_by=user_id
                )
                # Scope is derived from the already-authorized destination
                # bank and actor.  Request/preview payloads cannot opt a row
                # into shared or private visibility.  This keeps existing
                # private-bank imports explicit without enabling teacher
                # overlays in the Phase-1 flow.
                if general:
                    from services.bank_curriculum import set_general_category
                    set_general_category(bq, q_data.get('question_category'))
                set_new_question_scope(bq, actor, bank)
                db.session.add(bq)
                db.session.flush()  # get bq.id

                # Save options for the three supported formats. Legacy essay
                # rows have already been canonicalised to short_answer.
                for idx, opt_data in enumerate(q_data.get("options", []) if q_type != "true_false" else []):
                    opt = BankQuestionOption(
                        question_id=bq.id,
                        option_text=remap_text(opt_data["text"]),
                        is_correct=bool(opt_data.get("is_correct", False)),
                        order_index=idx
                    )
                    db.session.add(opt)

                # Save statements (for true_false)
                for idx, stmt_data in enumerate(q_data.get("statements", []) if q_type == "true_false" else []):
                    stmt_label = stmt_data.get("id", chr(97 + idx))
                    stmt_text_raw = stmt_data['text']
                    stmt_text = f"{stmt_label}) {stmt_text_raw}" if not stmt_text_raw.startswith(f"{stmt_label})") else stmt_text_raw
                    opt = BankQuestionOption(
                        question_id=bq.id,
                        option_text=remap_text(stmt_text),
                        is_correct=stmt_data.get("answer") if isinstance(stmt_data.get("answer"), bool) else db.null(),
                        order_index=idx
                    )
                    db.session.add(opt)

                # ``before_flush`` has now assigned the atomic suffix.  Check
                # the exact persisted shape before marking it approved so only
                # rows usable by existing selectors become teacher-confirmed.
                db.session.flush()
                from services.practice_blueprint import readiness_error
                from services.bank_curriculum import bank_readiness_error
                readiness = bank_readiness_error(bq, research=not general)
                if readiness:
                    # The preflight should make this path exceptional, but a
                    # late ORM/readiness change must not leave child options
                    # behind when this row is skipped.
                    for option in list(bq.options):
                        db.session.delete(option)
                    db.session.delete(bq)
                    db.session.flush()
                    q_data.setdefault('errors', []).append(readiness)
                    q_data['status'] = 'error'
                    continue

                if q_data.get('replace_question_id'):
                    from services.access_control import can_edit_question
                    from services.personalization_evidence import stamp_bank_question_content
                    target = db.session.get(BankQuestion, q_data['replace_question_id'])
                    if not target or target.bank_id != bank.id or not can_edit_question(actor, target):
                        raise ValueError('Quyền thay thế câu đã thay đổi. Hãy đối chiếu lại.')
                    # Preserve the original identity and frozen exam snapshots.
                    for field in ('question_text', 'context', 'image_url', 'question_type', 'difficulty_level',
                                  'points', 'explanation', 'confidence_scores', 'grade', 'topic',
                                  'question_category', 'curriculum_node_id', 'classification_status',
                                  'classification_data', 'learning_metadata'):
                        setattr(target, field, getattr(bq, field))
                    target.options.clear()
                    for option in list(bq.options):
                        bq.options.remove(option)
                        target.options.append(option)
                    db.session.delete(bq)
                    db.session.flush()
                    stamp_bank_question_content(target)
                    bq = target
                    updated_count += 1
                q_data['saved_question_id'] = bq.id
                # Keep the completed preview truthful: the prefix came from
                # TeX, while this full source ID now contains the allocator's
                # committed suffix.
                q_data['source_id'] = bq.source_id
                q_data['id6_scope'] = bq.id6_scope
                q_data['id6_sequence'] = bq.id6_sequence
                q_data['duplicate'] = dict(state='imported',matches=[],reason='Đã lưu vào ngân hàng.')
                imported_count += 1

            # Re-scan the final in-memory batch.  This keeps a defensive
            # post-persist readiness failure visible as an error and records
            # imported rows without treating them as fresh candidates again.
            report = scan_duplicates(session, questions, actor=actor, bank=bank)
            session.set_parsed_questions(questions)
            for status in ('valid', 'warning', 'error'):
                setattr(session, status + '_count', sum(q.get('status') == status for q in questions))
            # A partially imported batch remains editable until every
            # remaining row is either imported, explicitly skipped as a
            # duplicate, or removed by the teacher.
            session.status = "preview" if report['review'] or report['error'] else "confirmed"
            receipt = dict(success=True, imported_count=imported_count, total_count=len(questions),
                           added_count=imported_count-updated_count, updated_count=updated_count,
                           bank_id=bank.id if bank else None, bank_name=bank.name if bank else None,
                           skipped_count=report['duplicate'], skipped_labels=report['skipped_labels'],
                           review_count=report['review'], error_count=report['error'],
                           completed=session.status=='confirmed', confirmation_token=token,
                           message='Không có câu cần lưu.' if not imported_count else f'Đã thêm {imported_count-updated_count} câu mới và cập nhật {updated_count} câu.',
                           rows=[dict(source_label=q['source_label'],state=q['duplicate']['state'],
                                      saved_question_id=q.get('saved_question_id'),matches=q['duplicate']['matches']) for q in questions])
            results[token] = receipt
            session.result_data = json.dumps(results,ensure_ascii=False)
            session.duplicate_report = json.dumps(report,ensure_ascii=False)
            db.session.commit()

            # Post-commit tasks cannot turn a successful import into a failed/retry write.
            try:
                if session.status == 'confirmed':
                    ImportService.cleanup_temp_file(session)
            except Exception:
                # Import is already committed; retain its successful response
                # while making background-cleanup failures observable.
                logger.exception("Post-import background task failed for session %s", session_id)
            return receipt
        except Exception:
            db.session.rollback()
            raise

    @staticmethod
    def retry_formula_asset(asset):
        """Retry one persisted formula without requiring a full re-import."""
        if asset.source_format == "LaTeXBlock":
            if not asset.source_text:
                asset.conversion_status = "failed"
                asset.verification_status = "needs_review"
                asset.render_error = "Không còn source LaTeX để chạy lại"
                return {"success": False, "message": asset.render_error}

            from services.latex_renderer import render_latex_block_result
            result = render_latex_block_result(
                asset.source_text,
                preamble=asset.source_preamble or "",
            )
            asset.svg_cache_key = result.get("url")
            asset.render_method = result.get("method")
            asset.render_error = result.get("error")
            asset.conversion_status = "fallback_svg" if result.get("url") else "failed"
            asset.verification_status = "verified" if result.get("verified") else "needs_review"
            return {
                "success": bool(result.get("url")),
                "verified": bool(result.get("verified")),
                "message": result.get("error"),
            }

        # Legacy non-TeX assets remain readable through their stored LaTeX,
        # MathML, or cached image.  They are no longer converted or retried.
        return {"success": False, "message": "Asset không có dữ liệu LaTeX để chuyển đổi"}

    @staticmethod
    def cancel_session(session_id):
        """Cancel an import session and clean up temp files."""
        session = db.session.get(ImportSession, session_id)
        if session:
            ImportService.cleanup_temp_file(session)
            db.session.delete(session)
            db.session.commit()
        return True

    @staticmethod
    def cleanup_temp_file(session):
        """Remove temp file and extracted images on disk."""
        if not session:
            return
            
        # 1. Delete main uploaded file
        if session.file_path and os.path.exists(session.file_path):
            try:
                os.remove(session.file_path)
            except OSError:
                pass
                
        # 2. Delete any extracted temp images for this session
        try:
            temp_dir = os.path.join("static", "uploads", "import_temp", str(session.id))
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            logger.exception("Could not clean temporary import image directory for session %s", session.id)

    @staticmethod
    def cleanup_expired_temp_files(max_age_minutes=30):
        """Remove orphan files in uploads/temp older than max_age_minutes."""
        try:
            ensure_temp_dir()
            now = dt.datetime.now().timestamp()
            max_age_sec = max_age_minutes * 60
            for fname in os.listdir(UPLOAD_TEMP_DIR):
                fpath = os.path.join(UPLOAD_TEMP_DIR, fname)
                if os.path.isfile(fpath):
                    file_age = now - os.path.getmtime(fpath)
                    if file_age > max_age_sec:
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
        except Exception:
            logger.exception("Could not clean expired temporary import files")

    @staticmethod
    def cleanup_orphan_question_images():
        """Remove image files in static/uploads/questions that are not referenced anywhere in DB."""
        try:
            from database import db
            from models import (
                BankQuestion,
                BankQuestionOption,
                ExamAnswer,
                ExamQuestion,
                ImportSession,
            )
            
            referenced_files = set()
            
            # 1. Bank questions & options
            for bq in db.session.query(BankQuestion).all():
                if bq.image_url:
                    referenced_files.add(os.path.basename(bq.image_url))
                for text_field in [bq.question_text, bq.explanation, bq.context]:
                    if text_field:
                        for img_src in QUESTION_IMAGE_FILENAME_PATTERN.findall(text_field):
                            referenced_files.add(os.path.basename(img_src))
                            
            for opt in db.session.query(BankQuestionOption).all():
                if hasattr(opt, 'image_url') and opt.image_url:
                    referenced_files.add(os.path.basename(opt.image_url))
                if opt.option_text:
                    for img_src in QUESTION_IMAGE_FILENAME_PATTERN.findall(opt.option_text):
                        referenced_files.add(os.path.basename(img_src))

            # 2. Exam questions
            for eq in db.session.query(ExamQuestion).all():
                if eq.image_url:
                    referenced_files.add(os.path.basename(eq.image_url))
                for text_field in [eq.question_text, eq.explanation, eq.context]:
                    if text_field:
                        for img_src in QUESTION_IMAGE_FILENAME_PATTERN.findall(text_field):
                            referenced_files.add(os.path.basename(img_src))

            for answer in db.session.query(ExamAnswer).all():
                if answer.answer_text:
                    for img_src in QUESTION_IMAGE_FILENAME_PATTERN.findall(answer.answer_text):
                        referenced_files.add(os.path.basename(img_src))

            # 3. Active import sessions
            for s in db.session.query(ImportSession).all():
                for q in s.get_parsed_questions():
                    if q.get('image_url'):
                        referenced_files.add(os.path.basename(q['image_url']))
                    reference_fields = [
                        q.get('question_text', ''),
                        q.get('explanation', ''),
                        q.get('context', ''),
                        *[option.get('text', '') for option in q.get('options', [])],
                        *[statement.get('text', '') for statement in q.get('statements', [])],
                        *q.get('image_paths', []),
                    ]
                    for field in reference_fields:
                        if field:
                            for img_src in QUESTION_IMAGE_FILENAME_PATTERN.findall(field):
                                referenced_files.add(os.path.basename(img_src))

            # 4. Clean up unreferenced files in static/uploads/questions
            base_dir = os.path.dirname(os.path.dirname(__file__))
            upload_dir = os.path.join(base_dir, "static", "uploads", "questions")
            if not os.path.exists(upload_dir):
                return
                
            all_files = set(os.listdir(upload_dir))
            orphan_files = all_files - referenced_files
            
            for fname in orphan_files:
                fpath = os.path.join(upload_dir, fname)
                if os.path.isfile(fpath):
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass
        except Exception:
            logger.exception("Orphan question-image cleanup failed")
