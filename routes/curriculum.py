"""Curriculum catalog and ID6 preview routes."""

from __future__ import annotations

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from database import db
from models import BankQuestion, CurriculumNode
from services.access_control import require_question_view, role_required
from services.curriculum_service import normalize_curriculum_payload, parse_catalog_rows
from services.curriculum_data import RETAINED_LESSON_NAME
from services.id6_service import parse_id6, parse_bank_question_id6
from routes.question_bank import _get_viewable_question_bank

def _upsert_curriculum_node(payload, user_id):
    normalized = normalize_curriculum_payload(payload)
    canonical_code = CurriculumNode.make_canonical_code(
        normalized["grade"],
        normalized["chapter_code"],
        normalized["lesson_code"],
        normalized["category_code"],
    )
    node = CurriculumNode.query.filter_by(canonical_code=canonical_code).first()
    created = node is None
    if created:
        node = CurriculumNode(canonical_code=canonical_code, created_by=user_id, **normalized)
        db.session.add(node)
    else:
        for field, value in normalized.items():
            setattr(node, field, value)
        node.is_active = True
    return node, created


@login_required
@role_required("teacher")
def curriculum_catalog():
    if request.method == "POST":
        if current_user.role != "admin":
            abort(403)

        action = request.form.get("action", "add_single")
        try:
            if action == "bulk_add":
                rows, errors = parse_catalog_rows(
                    request.form.get("catalog_rows", ""),
                    request.form.get("catalog_version", "math9-v1"),
                )
                created_count = 0
                updated_count = 0
                for row in rows:
                    _, created = _upsert_curriculum_node(row, current_user.id)
                    created_count += int(created)
                    updated_count += int(not created)
                db.session.commit()
                if rows:
                    flash(
                        f"Đã xử lý {len(rows)} dòng: thêm {created_count}, cập nhật {updated_count}.",
                        "success",
                    )
                for error in errors[:10]:
                    flash(error, "warning")
                if len(errors) > 10:
                    flash(f"Còn {len(errors) - 10} lỗi khác chưa hiển thị.", "warning")
            else:
                payload = {
                    "grade": request.form.get("grade", ""),
                    "chapter_code": request.form.get("chapter_code", ""),
                    "chapter_name": request.form.get("chapter_name", ""),
                    "lesson_code": request.form.get("lesson_code", ""),
                    "lesson_name": request.form.get("lesson_name", ""),
                    "category_code": request.form.get("category_code", ""),
                    "category_name": request.form.get("category_name", ""),
                    "catalog_version": request.form.get("catalog_version", "math9-v1"),
                    "is_advanced": request.form.get("is_advanced") == "1",
                }
                node, created = _upsert_curriculum_node(payload, current_user.id)
                db.session.commit()
                flash(
                    f"Đã {'thêm' if created else 'cập nhật'} kỹ năng {node.canonical_code}.",
                    "success",
                )
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except Exception as exc:
            db.session.rollback()
            flash(f"Không thể lưu danh mục: {exc}", "danger")
        return redirect(url_for("curriculum_catalog"))

    grade_filter = request.args.get("grade", "").strip()
    chapter_filter = request.args.get("chapter", "").strip().upper()
    search_q = request.args.get("q", "").strip()
    show_inactive = request.args.get("inactive") == "1"

    query = CurriculumNode.query
    if not show_inactive:
        query = query.filter_by(is_active=True)
    if grade_filter:
        query = query.filter_by(grade=grade_filter)
    if chapter_filter:
        query = query.filter_by(chapter_code=chapter_filter)
    if search_q:
        pattern = f"%{search_q}%"
        query = query.filter(or_(
            CurriculumNode.canonical_code.ilike(pattern),
            CurriculumNode.chapter_name.ilike(pattern),
            CurriculumNode.lesson_name.ilike(pattern),
            CurriculumNode.category_name.ilike(pattern),
        ))

    nodes = query.order_by(
        CurriculumNode.grade,
        CurriculumNode.chapter_code,
        CurriculumNode.lesson_code,
        CurriculumNode.category_code,
    ).all()
    grades = [row[0] for row in db.session.query(CurriculumNode.grade).distinct().order_by(CurriculumNode.grade).all()]
    return render_template("curriculum_catalog.html", nodes=nodes, grades=grades,
                           catalog_lesson_name=RETAINED_LESSON_NAME)


@login_required
@role_required("admin")
def toggle_curriculum_node(node_id):
    node = db.session.get(CurriculumNode, node_id) or abort(404)
    node.is_active = not node.is_active
    db.session.commit()
    flash(
        f"Đã {'kích hoạt' if node.is_active else 'ngừng sử dụng'} {node.canonical_code}.",
        "success",
    )
    return redirect(url_for("curriculum_catalog", inactive="1" if not node.is_active else None))

@login_required
@role_required("teacher")
def id6_preview_api():
    """Return recognized source metadata without generating an ID.

    Older clients called this route to preview a synthesized six-level ID.
    The active contract is read-only: source files provide the prefix and the
    save transaction supplies a suffix.  A persisted question may still
    return its already-issued full ID for display.
    """
    node_id = request.args.get("node_id", type=int)
    node = db.session.get(CurriculumNode, node_id) if node_id else None
    if not node or not node.is_active:
        return jsonify(success=False, message="Chưa chọn đủ lớp, chương, bài, dạng."), 400
    if not (node.grade == "9" and node.chapter_code == "8" and str(node.lesson_code).lower() == "i"):
        return jsonify(success=False, message="Chỉ hỗ trợ Chương 8, bài kết hợp i."), 400
    question_id = request.args.get("question_id", type=int)
    source_id = request.args.get("source_id", "")
    if question_id:
        question = db.session.get(BankQuestion, question_id) or abort(404)
        # ID6 preview reads existing bank metadata; a teacher may read a
        # shared bank but must not be routed through the edit-only helper.
        bank = _get_viewable_question_bank(question.bank_id)
        require_question_view(question, bank=bank)
        source_id = question.source_id or ""
    parsed = (
        parse_bank_question_id6(question)
        if question_id else
        parse_id6(source_id)
    )
    if parsed:
        scope = CurriculumNode.make_canonical_code(
            parsed["grade"].split()[-1], parsed["chapter"], parsed["section"],
            parsed["question_category"]
        )
        if scope != node.canonical_code:
            return jsonify(success=False, message="Tiền tố ID6 không khớp dạng đang chọn."), 400
        return jsonify(success=True, source_id=parsed["source_id"], id6_prefix=parsed["id6_prefix"],
                       sequence=parsed["id6_sequence"], read_only=True)
    return jsonify(success=True, source_id="", id6_prefix="", sequence=None, read_only=True,
                   message="Tiền tố ID6 phải đến từ metadata file; số thứ tự cấp khi lưu.")




def register_curriculum_routes(app) -> None:
    """Register handlers while preserving the legacy route contract."""
    app.add_url_rule("/curriculum", endpoint="curriculum_catalog", view_func=curriculum_catalog, methods=["GET", "POST"])
    app.add_url_rule("/curriculum/<int:node_id>/toggle", endpoint="toggle_curriculum_node", view_func=toggle_curriculum_node, methods=["POST"])
    app.add_url_rule("/curriculum/id6-preview", endpoint="id6_preview_api", view_func=id6_preview_api)
