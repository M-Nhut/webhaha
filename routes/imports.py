"""Question bank import wizard and session API routes."""

from __future__ import annotations

import json
import os
import uuid

from flask import abort, current_app, jsonify, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.exceptions import HTTPException

from database import db
from models import QuestionBank, ImportSession
from services.import_service import ImportService, _receipt_without_match_payload
from services.question_policy import require_supported_type
from services.import_scope import editable_session, save_scope, refresh_preview
from services.import_transactions import lock_import_transaction
from services.id6_metadata import enrich_preview, prepare_preview_edit
from services.id6_service import catalog_options
from services.access_control import can_import_questions, role_required
from services.import_authorization import (
    ImportSessionNotFound,
    fresh_import_actor,
    fresh_import_bank,
    import_session_context,
)

# ──────────── IMPORT WIZARD & API ROUTES ────────────

def import_session_payload(session, *, actor=None):
    """Serialize an owned session without replaying stale private matches.

    A confirmed session can outlive a teacher's overlay ownership change.  Its
    stored duplicate report was generated under an older authorization view;
    refresh the comparison in memory for the current actor before returning a
    payload so an old report cannot disclose a now-foreign private row.
    """
    questions = session.get_parsed_questions()
    duplicate_report = session.get_duplicate_report()
    if actor is not None and session.bank_id:
        from services.import_duplicates import scan_duplicates
        duplicate_report = scan_duplicates(session, questions, actor=actor)
    results = session.get_results()
    receipt = list(results.values())[-1] if results else None
    # Cached receipts are historical authorization artifacts.  Keep their
    # counts and saved ids, but never replay match text/ids; the fresh report
    # above is the actor-scoped source for any currently visible matches.
    receipt = _receipt_without_match_payload(receipt)
    return dict(success=True,session_id=session.id,status=session.status,questions=questions,
                scope=session.get_scope(),filename=session.filename,bank_id=session.bank_id,
                duplicate_report=duplicate_report,
                result=receipt,
                stats=dict(total=session.total_count,valid=session.valid_count,warning=session.warning_count,error=session.error_count))


def _strict_optional_bank_id(value):
    """Reject malformed destination fields instead of silently unbinding them."""
    if value in (None, ""):
        return None
    try:
        bank_id = int(value)
    except (TypeError, ValueError):
        raise ValueError("Ngân hàng đích không hợp lệ.")
    if isinstance(value, bool) or bank_id <= 0 or str(value).strip() != str(bank_id):
        raise ValueError("Ngân hàng đích không hợp lệ.")
    return bank_id


def _route_import_context(session_id, *, require_open=True, revalidate_target=True):
    try:
        context = import_session_context(
            session_id,
            current_user.id,
            require_open=require_open,
            revalidate_target=revalidate_target,
        )
        if require_open and (context[1].get_scope() or {}).get('document_kind') == 'assessment':
            raise ValueError('Hãy chỉnh đề tại mục Đề kiểm tra; phiên này không nhập vào ngân hàng.')
        return context
    except ImportSessionNotFound:
        abort(404)


@login_required
@role_required("teacher")
def import_questions_page():
    actor = fresh_import_actor(current_user.id)
    candidates = QuestionBank.query.order_by(QuestionBank.name).all()
    # The selector is a mutation surface, not a list of readable banks.  A
    # teacher may now choose an explicit shared bank for a private overlay,
    # but foreign private banks and legacy admin banks remain absent.
    banks = [bank for bank in candidates if can_import_questions(actor, bank)]
    scope_note = (
        "Quản trị viên có thể nhập vào mọi ngân hàng. Ngân hàng tạo mới sẽ ở phạm vi chia sẻ; "
        "nhập vào ngân hàng dùng chung tạo câu dùng chung; nhập vào ngân hàng riêng giữ nguyên "
        "phạm vi và chủ sở hữu ngân hàng."
        if actor.role == "admin" else
        "Giáo viên có thể nhập câu riêng vào ngân hàng dùng chung hoặc ngân hàng riêng do mình sở hữu. "
        "Câu thêm vào ngân hàng dùng chung chỉ hiển thị và sử dụng với chính giáo viên đó; ngân hàng "
        "và câu dùng chung vẫn chỉ đọc. Ngân hàng tạo mới sẽ là riêng tư."
    )
    return render_template(
        "question_bank_import.html", banks=banks, id6_catalog=catalog_options(),
        import_scope_note=scope_note,
        import_defaults={key: request.args.get(key, '') for key in ('node_id', 'difficulty', 'type')},
    )


@login_required
@role_required("teacher")
def import_upload():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "Không tìm thấy file upload."}), 400
    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"success": False, "message": "File không hợp lệ."}), 400
        
    try:
        actor = fresh_import_actor(current_user.id)
        bank_id = _strict_optional_bank_id(request.form.get("bank_id"))
        if bank_id is not None:
            # Import is an edit operation.  The service repeats this after
            # reloading the rows, but the route rejects the upload early.
            fresh_import_bank(bank_id, actor)
        session = ImportService.create_and_process_session(
            user_id=actor.id,
            file_obj=file,
            filename=file.filename,
            bank_id=bank_id
        )
        if request.form.get('document_purpose') == 'assessment':
            session.scope_data = json.dumps({'document_kind': 'assessment', 'source': 'latex'})
        elif request.form.get('default_node_id'):
            # Selecting a knowledge cell is an explicit teacher classification.
            if request.form['default_node_id'] not in {str(n['id']) for n in catalog_options()}:
                raise ValueError('Dạng kiến thức đích không hợp lệ.')
            session.scope_data = None
        if (session.get_scope() or {}).get('document_kind') == 'assessment':
            session.bank_id = None
            db.session.commit()
            return jsonify(success=True, redirect_url=url_for('assessment_import', session_id=session.id))
        if not session.scope_data:
            from services.import_scope import default_inferred_scope
            default_scope, _ = default_inferred_scope()
            session.scope_data = json.dumps(default_scope, ensure_ascii=False)
        enrich_preview(session, commit=False)
        node_id = request.form.get('default_node_id', '')
        level = request.form.get('default_difficulty', '')
        if node_id:
            catalog = {str(n['id']): n for n in catalog_options()}
            if node_id not in catalog:
                raise ValueError('Dạng kiến thức đích không hợp lệ.')
            from services.practice_blueprint import LEVELS
            if level and level not in LEVELS:
                raise ValueError('Mức độ đích không hợp lệ.')
            questions = session.get_parsed_questions()
            for question in questions:
                # Fill missing labels only; never change parsed answer structure.
                if not question.get('curriculum_node_id'):
                    question['curriculum_node_id'] = int(node_id)
                    if level and not question.get('source_id'):
                        question['difficulty_level'] = level
                    prepare_preview_edit(question)
            session.set_parsed_questions(questions)
        refresh_preview(session)
        db.session.commit()
        return jsonify({
            "success": True,
            "session_id": session.id,
            "questions": session.get_parsed_questions(),
            "duplicate_report": session.get_duplicate_report(),
            "scope": session.get_scope(),
            "filename": session.filename,
            "bank_id": session.bank_id,
            "stats": {
                "total": session.total_count,
                "valid": session.valid_count,
                "warning": session.warning_count,
                "error": session.error_count
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 400


@login_required
@role_required("teacher")
def import_preview_api(session_id):
    lock_import_transaction()
    try:
        actor, session, _ = _route_import_context(session_id, require_open=False)
        if (session.get_scope() or {}).get('document_kind') == 'assessment':
            return jsonify(success=True, redirect_url=url_for('assessment_import', session_id=session.id))
        if session.status == 'confirmed':
            db.session.rollback()
            return jsonify(import_session_payload(session, actor=actor))
        if not session.scope_data:
            from services.import_scope import default_inferred_scope
            default_scope, _ = default_inferred_scope()
            session.scope_data = json.dumps(default_scope, ensure_ascii=False)
        editable_session(session_id,current_user.id)
        enrich_preview(session,commit=False)
        scope_error = ''
        try: refresh_preview(session)
        except ValueError as exc: scope_error = str(exc)
        db.session.commit()
        return jsonify(**import_session_payload(session, actor=actor),scope_error=scope_error)
    except ValueError as exc:
        db.session.rollback()
        return jsonify(success=False,message=str(exc)),400


@login_required
@role_required("teacher")
def retry_preview_formula_api(session_id, formula_id):
    lock_import_transaction()
    """Retry a LaTeX block that only exists in an import preview session."""
    try:
        uuid.UUID(formula_id)
    except (ValueError, AttributeError):
        abort(404)

    try:
        actor, session, _ = _route_import_context(session_id)
        session, formula_data, result = ImportService.retry_preview_formula(session_id, formula_id, commit=False)
        # A newly converted formula can change a previously unresolved comparison.
        refresh_preview(session)
        db.session.commit()
        status_code = 200 if result.get("url") else 422
        return jsonify({
            "success": bool(result.get("url")),
            "message": result.get("error"),
            "formula": formula_data,
            "stats": {
                "total": session.total_count,
                "valid": session.valid_count,
                "warning": session.warning_count,
                "error": session.error_count,
            },
        }), status_code
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"success": False, "message": str(exc)}), 404


@login_required
@role_required("teacher")
def import_source_file(session_id):
    """Download the original file for an active comparison, without exposing paths."""
    try:
        actor, session, _ = _route_import_context(session_id)
    except ValueError:
        abort(404)
    if not session.file_path:
        abort(404)
    from services.import_service import UPLOAD_TEMP_DIR
    root = os.path.realpath(UPLOAD_TEMP_DIR)
    target = os.path.realpath(session.file_path)
    if os.path.commonpath((root, target)) != root or not os.path.isfile(target):
        abort(404)
    return send_file(target, as_attachment=True, download_name=session.filename)


@login_required
@role_required("teacher")
def download_latex_template():
    """Download the official LaTeX question bank template (cautrucde.tex)."""
    from pathlib import Path
    root_path = Path(current_app.root_path)
    if request.args.get('profile') == 'assessment':
        return send_file(str(root_path / 'docs/examples/de_kiem_tra_ex.tex'),
                         as_attachment=True, download_name='de_kiem_tra_ex.tex', mimetype='text/x-tex')
    if request.args.get('profile') == 'general':
        return send_file(str(root_path / 'docs/examples/ngan_hang_nhieu_chu_de.tex'),
                         as_attachment=True, download_name='ngan_hang_nhieu_chu_de.tex', mimetype='text/x-tex')
    template_path = root_path / "cautrucde.tex"
    if not template_path.is_file():
        template_path = root_path / "services" / "data" / "cautrucde.tex"
    if not template_path.is_file():
        abort(404, description="Template file not found.")
    return send_file(
        str(template_path),
        as_attachment=True,
        download_name="cautrucde.tex",
        mimetype="text/x-tex",
    )


@login_required
@role_required("teacher")
def import_update_api(session_id):
    lock_import_transaction()
    data = request.json or {}
    q_index = data.get("index")
    question_data = data.get("question")
    if q_index is None or not question_data:
        return jsonify({"success": False, "message": "Dữ liệu không hợp lệ."}), 400

    try:
        _, session, _ = _route_import_context(session_id)
        # An old preview can still carry an essay label; editing it upgrades
        # the row to the supported short-answer format in ImportService.
        require_supported_type(question_data.get("question_type"), allow_legacy=True)
        prepare_preview_edit(question_data)
        session = ImportService.update_preview_question(session_id, q_index, question_data, commit=False)
        enrich_preview(session, commit=False)
        refresh_preview(session)
        db.session.commit()
        return jsonify({
            "success": True,
            "questions": session.get_parsed_questions(),
            "duplicate_report": session.get_duplicate_report(),
            "scope": session.get_scope(),
            "filename": session.filename,
            "bank_id": session.bank_id,
            "stats": {
                "total": session.total_count,
                "valid": session.valid_count,
                "warning": session.warning_count,
                "error": session.error_count
            }
        })
    except HTTPException:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 400


@login_required
@role_required("teacher")
def import_scope_api(session_id):
    lock_import_transaction()
    try:
        actor, session, _ = _route_import_context(session_id)
        save_scope(session, request.get_json() or {})
        return jsonify(import_session_payload(session, actor=actor))
    except ValueError as exc:
        db.session.rollback()
        return jsonify(success=False, message=str(exc)), 400


@login_required
@role_required("teacher")
def import_remove_api(session_id):
    lock_import_transaction()
    try:
        actor, session, _ = _route_import_context(session_id)
        index = (request.get_json() or {}).get('index')
        questions = session.get_parsed_questions()
        if type(index) is not int or not 0 <= index < len(questions):
            raise ValueError('Số câu không hợp lệ.')
        if questions[index].get("saved_question_id"):
            raise ValueError("Câu đã lưu; chỉnh sửa trong ngân hàng.")
        questions.pop(index)
        session.set_parsed_questions(questions)
        refresh_preview(session)
        db.session.commit()
        return jsonify(import_session_payload(session, actor=actor))
    except ValueError as exc:
        db.session.rollback()
        return jsonify(success=False, message=str(exc)), 400


@login_required
@role_required("teacher")
def import_destination_api(session_id):
    lock_import_transaction()
    try:
        actor, session, _ = _route_import_context(session_id)
        if any(q.get('saved_question_id') for q in session.get_parsed_questions()):
            raise ValueError('Phiên đã lưu một phần; tiếp tục dùng ngân hàng hiện tại.')
        value = _strict_optional_bank_id((request.get_json() or {}).get('bank_id'))
        bank = fresh_import_bank(value, actor) if value is not None else None
        session.bank = bank
        session.bank_id = bank.id if bank else None
        session.duplicate_decisions = None
        refresh_preview(session)
        db.session.commit()
        return jsonify(import_session_payload(session, actor=actor))
    except (TypeError,ValueError) as exc:
        db.session.rollback()
        return jsonify(success=False,message=str(exc)),400


@login_required
@role_required("teacher")
def import_duplicate_decision_api(session_id):
    lock_import_transaction()
    try:
        actor, session, _ = _route_import_context(session_id)
        refresh_preview(session)
        data = request.get_json() or {}
        question = next((q for q in session.get_parsed_questions() if q['import_uid']==data.get('import_uid')),None)
        if not question or question.get('saved_question_id'):
            raise ValueError('Câu không còn trong danh sách cần đối chiếu.')
        match = next((m for m in question['duplicate']['matches'] if m['token']==data.get('token')),None)
        if not match or not match.get('reviewable') or data.get('decision') not in ('different','duplicate','incoming','neither'):
            raise ValueError('Kết quả đối chiếu đã thay đổi hoặc không hợp lệ. Hãy tải lại phiên.')
        if data['decision'] in ('incoming', 'neither') and match.get('bank_question_id'):
            from services.access_control import can_edit_question
            from models import BankQuestion
            target = db.session.get(BankQuestion, match['bank_question_id'])
            if data['decision'] == 'neither':
                raise ValueError('Chỉ bỏ cả hai khi hai bản cùng nằm trong file nhập. Câu đã lưu cần được quản lý tại ngân hàng.')
            if not target or not can_edit_question(actor, target):
                raise ValueError('Bạn không có quyền thay thế câu trong ngân hàng này.')
        decisions = session.get_duplicate_decisions()
        decisions.setdefault(question['import_uid'],{})[match['token']] = data['decision']
        session.duplicate_decisions = json.dumps(decisions,ensure_ascii=False)
        refresh_preview(session)
        db.session.commit()
        return jsonify(import_session_payload(session, actor=actor))
    except ValueError as exc:
        db.session.rollback()
        return jsonify(success=False,message=str(exc)),400


@login_required
@role_required("teacher")
def import_confirm_api(session_id):
    data = request.get_json() or {}
    try:
        # Preserve the 404 ownership contract before the service restarts and
        # owns the final write transaction.  It repeats actor/target checks
        # after acquiring the database lock.
        _route_import_context(session_id, require_open=False)
        bank_id = _strict_optional_bank_id(data.get('bank_id'))
        result = ImportService.confirm_import(session_id,bank_id,current_user.id,
            new_bank=dict(name=data.get('new_bank_name') or '',subject=data.get('subject','Toán'),grade=data.get('grade','')),
            confirmation_token=data.get('confirmation_token'))
        return jsonify(result)
    except (ValueError,TypeError) as exc:
        db.session.rollback()
        return jsonify(success=False,message=str(exc)),400
    except HTTPException:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Import confirmation failed')
        return jsonify(success=False,message='Chưa lưu được ngân hàng. Hãy thử lại; hệ thống sẽ kiểm tra trùng lần nữa.'),500


@login_required
@role_required("teacher")
def import_cancel_api(session_id):
    lock_import_transaction()
    try:
        # Cancellation never writes to a bank.  Revalidate the current actor
        # and session but allow cleanup after destination access was revoked.
        _, session, _ = _route_import_context(session_id, revalidate_target=False)
    except ValueError as exc:
        db.session.rollback()
        return jsonify(success=False, message=str(exc)), 400
    ImportService.cancel_session(session_id)
    return jsonify({"success": True, "message": "Đã hủy phiên import."})


def register_imports_routes(app) -> None:
    """Register handlers while preserving the legacy route contract."""
    app.add_url_rule("/question-banks/import", endpoint="import_questions_page", view_func=import_questions_page)
    app.add_url_rule("/question-banks/import/upload", endpoint="import_upload", view_func=import_upload, methods=["POST"])
    app.add_url_rule("/question-banks/import/<session_id>/preview", endpoint="import_preview_api", view_func=import_preview_api)
    app.add_url_rule("/question-banks/import/<session_id>/formulas/<formula_id>/retry", endpoint="retry_preview_formula_api", view_func=retry_preview_formula_api, methods=["POST"])
    app.add_url_rule("/question-banks/import/<session_id>/source", endpoint="import_source_file", view_func=import_source_file, methods=["GET"])
    app.add_url_rule("/question-banks/import/<session_id>/update", endpoint="import_update_api", view_func=import_update_api, methods=["POST"])
    app.add_url_rule("/question-banks/import/<session_id>/scope", endpoint="import_scope_api", view_func=import_scope_api, methods=["POST"])
    app.add_url_rule("/question-banks/import/<session_id>/remove", endpoint="import_remove_api", view_func=import_remove_api, methods=["POST"])
    app.add_url_rule("/question-banks/import/<session_id>/destination", endpoint="import_destination_api", view_func=import_destination_api, methods=["POST"])
    app.add_url_rule("/question-banks/import/<session_id>/duplicate-decision", endpoint="import_duplicate_decision_api", view_func=import_duplicate_decision_api, methods=["POST"])
    app.add_url_rule("/question-banks/import/<session_id>/confirm", endpoint="import_confirm_api", view_func=import_confirm_api, methods=["POST"])
    app.add_url_rule("/question-banks/import/<session_id>/cancel", endpoint="import_cancel_api", view_func=import_cancel_api, methods=["POST"])
    app.add_url_rule("/question-banks/import/template/latex", endpoint="download_latex_template", view_func=download_latex_template, methods=["GET"])
