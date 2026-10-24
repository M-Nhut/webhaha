"""Question bank CRUD, classification, evaluation and formula routes."""

from __future__ import annotations

import io
import datetime as dt
import json
import os
import re
import uuid

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload
from database import db
from models import (
    Exam, ExamQuestion, QuestionBank, BankQuestion, BankQuestionOption, ImportSession,
    FormulaAsset, CurriculumNode,
)
from services.import_service import ImportService
from services.question_policy import (
    require_supported_type, require_valid_answers,
)
from services.id6_service import LEVEL_CODES, TYPE_CODES, catalog_options, select_curriculum
from services.access_control import (
    BANK_VISIBILITY_PRIVATE,
    BANK_VISIBILITY_SHARED,
    bank_visibility,
    can_edit_bank,
    can_add_question,
    can_use_bank,
    can_view_bank,
    can_view_question,
    can_edit_question,
    can_delete_question,
    question_scope,
    question_source_label,
    resolve_question_source,
    require_question_view,
    require_question_edit,
    require_question_delete,
    set_new_question_scope,
    require_bank_edit,
    require_bank_add,
    require_bank_view,
    role_required,
    set_new_bank_visibility,
)
from services.personalization_evidence import stamp_bank_question_content


def _get_accessible_question_bank(bank_id):
    bank = db.session.get(QuestionBank, bank_id) or abort(404)
    # Historical helper name retained for route compatibility.  It is
    # deliberately edit-only: shared banks may be viewed/used by teachers but
    # can never be reached through a mutation/import path.
    return require_bank_edit(bank)


def _get_viewable_question_bank(bank_id):
    bank = db.session.get(QuestionBank, bank_id) or abort(404)
    return require_bank_view(bank)


_DETAIL_FILTER_KEYS = ("q", "type", "difficulty", "grade", "node_id")
_DETAIL_SCOPE_KEYS = frozenset({"all", "common", "mine"})
_DETAIL_QUESTION_TYPES = frozenset({"single", "multiple_choice", "true_false", "short_answer", "essay"})
_DETAIL_DIFFICULTIES = frozenset({"nhan_biet", "thong_hieu", "van_dung", "van_dung_cao"})


def _detail_redirect_params():
    """Carry only the bank-detail view state through POST redirects."""
    params = {}
    for key in ("scope", "page", "per_page", *_DETAIL_FILTER_KEYS):
        value = request.values.get(key, "")
        if isinstance(value, str):
            value = value.strip()
        if value:
            params[key] = value
    return params


def _serialize_question_for_actor(question, *, bank=None, research_bank=None):
    """Serialize one already-authorized row with actor-aware UI metadata.

    ``BankQuestion.to_dict`` intentionally contains persisted question data
    only.  Detail pages and JSON mutations additionally need the same source
    and mutation decisions, otherwise a successful save can make Alpine lose
    the teacher's edit controls.  The source key is derived by the central
    legacy resolver; no client-supplied owner/scope is trusted here.
    """
    source = resolve_question_source(question, bank=bank)
    serialized = question.to_dict()
    from services.bank_detail_page import is_research_bank
    if research_bank is None:
        research_bank = is_research_bank(bank or question.bank)
    if not research_bank:
        from services.bank_curriculum import category_name
        serialized['curriculum_mode'] = 'general'
        serialized['question_category'] = category_name(question)
    serialized["can_edit"] = can_edit_question(current_user, question, bank=bank)
    serialized["can_delete"] = can_delete_question(current_user, question, bank=bank)
    # Keep the persisted field for compatibility (NULL remains NULL), while
    # exposing a canonical display key for tabs and legacy rows.
    serialized["scope"] = question_scope(question)
    serialized["source"] = source["key"]
    serialized["source_label"] = question_source_label(current_user, question, bank=bank)
    # ``scope_label`` is the existing client/template name; retain it as an
    # alias so older pages/scripts do not lose their source badge.
    serialized["scope_label"] = serialized["source_label"]

    # Attach referenced formula assets so client has complete math dictionary
    all_text = ' '.join([
        str(question.question_text or ''),
        str(question.context or ''),
        str(question.explanation or ''),
        *[str(opt.option_text or '') for opt in getattr(question, 'options', [])],
    ])
    fids = re.findall(r'\[\[formula:([^\]]+)\]\]', all_text)
    if fids:
        assets = FormulaAsset.query.filter(FormulaAsset.id.in_(set(fids))).all()
        serialized["formulas"] = {a.id: a.to_api_dict() for a in assets}
    else:
        serialized["formulas"] = {}

    return serialized


@login_required
@role_required("teacher")
def question_bank_list():
    # Do the final filtering through the centralized policy rather than a
    # creator-only SQL predicate.  This keeps legacy rows fail-closed and lets
    # teachers discover only explicitly shared banks alongside their own
    # private/legacy banks.
    banks = QuestionBank.query.options(selectinload(QuestionBank.creator)).order_by(QuestionBank.updated_at.desc()).all()
    if current_user.role == "admin":
        visible_banks = banks
        shared_banks = []
        my_banks = banks
        teacher_sections = False
    else:
        visible_banks = [bank for bank in banks if can_view_bank(current_user, bank)]
        shared_banks = [
            bank for bank in visible_banks
            if bank_visibility(bank) == BANK_VISIBILITY_SHARED
        ]
        my_banks = [
            bank for bank in visible_banks
            if bank.created_by == current_user.id
            and bank_visibility(bank) in (BANK_VISIBILITY_PRIVATE, None)
        ]
        teacher_sections = True

    # Grouped statistics retain the centralized private/legacy policy without
    # loading the bank.questions collection for every card.
    from services.bank_detail_page import grouped_bank_stats
    bank_question_stats = grouped_bank_stats(visible_banks, current_user)
    return render_template(
        "question_banks.html",
        banks=visible_banks,
        shared_banks=shared_banks,
        my_banks=my_banks,
        teacher_sections=teacher_sections,
        bank_permissions={bank.id: {
            "can_edit": can_edit_bank(current_user, bank),
            "can_add": can_add_question(current_user, bank),
            "can_use": can_use_bank(current_user, bank),
        } for bank in visible_banks},
        bank_question_stats=bank_question_stats,
    )


@login_required
@role_required("teacher")
def create_question_bank():
    if request.method == "POST":
        form_data, form_errors = _bank_form_values()
        if form_errors:
            return render_template("question_bank_form.html", bank=None, form_data=form_data, form_errors=form_errors)
        bank = QuestionBank(
            **form_data,
            created_by=current_user.id
        )
        # Visibility is a server-owned invariant.  The create form has no say
        # in whether the new bank is shared or private.
        set_new_bank_visibility(bank, current_user)
        db.session.add(bank)
        db.session.commit()
        flash("Đã tạo ngân hàng câu hỏi thành công.", "success")
        return redirect(url_for("question_bank_detail", bank_id=bank.id))
    return render_template("question_bank_form.html", bank=None)


def _bank_form_values():
    """Validate the existing metadata fields without discarding a form draft."""
    values = {key: request.form.get(key, "").strip() for key in ("name", "subject", "grade", "topic", "description")}
    errors = {}
    for key, label, limit in (("name", "Tên ngân hàng", 200), ("subject", "Môn học", 80), ("grade", "Khối / Lớp học", 40), ("topic", "Bài / Chủ đề", 200)):
        if key in ("name", "subject") and not values[key]:
            errors[key] = [f"{label} không được để trống."]
        elif len(values[key]) > limit:
            errors[key] = [f"{label} tối đa {limit} ký tự."]
    return values, errors


@login_required
@role_required("teacher")
def question_bank_detail(bank_id):
    bank = _get_viewable_question_bank(bank_id)

    # ``scope`` is a view selector, not an authorization input.  Resolve the
    # full readable set first, then bucket it with the same conservative
    # legacy policy used by access checks.  An invalid scope falls back to the
    # broadest *authorized* view, never to an unfiltered database query.
    requested_scope = request.args.get("scope", "all")
    requested_scope = requested_scope.strip().lower() if isinstance(requested_scope, str) else "all"
    scope_filter = requested_scope if requested_scope in _DETAIL_SCOPE_KEYS else "all"
    from services.bank_detail_page import (
        authorized_metadata, catalog_for_metadata, is_research_bank,
        hydrate_readiness, question_page, preview_payload,
    )
    metadata, all_authorized_questions, source_buckets = authorized_metadata(bank, current_user)

    # For an administrator, ``mine`` is intentionally relabeled as an audit
    # bucket and includes every valid private contribution.  Administrators
    # must retain their ability to audit/manage all rows without a misleading
    # "only you" label.  Teachers can only reach their own private rows in
    # the authorized set, so the same bucket is naturally actor-scoped.
    scope_questions = {
        "all": all_authorized_questions,
        "common": source_buckets["common"],
        "mine": source_buckets["private"],
    }[scope_filter]

    selected_node = request.args.get("node_id", "")
    research_bank = is_research_bank(bank, metadata)
    catalog = catalog_for_metadata(scope_questions, research_bank)
    known_node_ids = {n["id"] for n in catalog}
    q_type_filter = request.args.get("type", "")
    q_type_filter = q_type_filter.strip().lower() if isinstance(q_type_filter, str) else ""
    if q_type_filter == "truefalse":
        q_type_filter = "true_false"
    diff_filter = request.args.get("difficulty", "")
    diff_filter = diff_filter.strip().lower() if isinstance(diff_filter, str) else ""

    # Pagination is applied by the database before prompt content is read.
    filters = {key: request.args.get(key, '') for key in (*_DETAIL_FILTER_KEYS, 'page', 'per_page', 'question_id')}
    questions, pagination = question_page(bank, scope_questions, filters, catalog, research_bank)

    # Facets/stats describe the selected scope before text/type/difficulty/
    # grade filters.  They therefore remain stable while a user searches, and
    # cannot accidentally disclose a foreign private row because the selected
    # scope was built only from ``all_authorized_questions`` above.
    available_grades = sorted(
        {q.grade for q in scope_questions if q.grade},
        key=lambda value: int(re.search(r"\d+", value).group()) if re.search(r"\d+", value) else 999,
    )
    diff_stats = {"nhan_biet": 0, "thong_hieu": 0, "van_dung": 0, "van_dung_cao": 0}
    for question in scope_questions:
        if question.difficulty_level in diff_stats:
            diff_stats[question.difficulty_level] += 1
    type_stats = {kind: 0 for kind in _DETAIL_QUESTION_TYPES}
    for question in scope_questions:
        question_type = "true_false" if question.question_type == "truefalse" else question.question_type
        if question_type in type_stats:
            type_stats[question_type] += 1

    questions_json = preview_payload(questions, scope_questions, bank, current_user, research_bank)
    for item in questions_json:
        item['detail_url'] = url_for('question_bank_question_detail_json', bank_id=bank.id, question_id=item['id'])
    scope_counts = {
        "all": len(all_authorized_questions),
        "common": len(source_buckets["common"]),
        "mine": len(source_buckets["private"]),
    }
    detail_filters = {
        key: request.args.get(key, "")
        for key in (*_DETAIL_FILTER_KEYS, "per_page")
        if request.args.get(key, "")
    }
    scope_urls = {
        key: url_for("question_bank_detail", bank_id=bank.id, **detail_filters, scope=key)
        for key in _DETAIL_SCOPE_KEYS
    }
    page_filters = dict(detail_filters, scope=scope_filter, per_page=pagination['per_page'])
    def page_url(number):
        return url_for('question_bank_detail', bank_id=bank.id, **page_filters, page=number) + '#bank-results'
    visible_pages = sorted({1, pagination['pages'], *range(max(1, pagination['page'] - 2),
        min(pagination['pages'], pagination['page'] + 2) + 1)})
    pagination['links'] = []
    previous = 0
    for number in visible_pages:
        if previous and number - previous > 1:
            pagination['links'].append({'number': None, 'url': ''})
        pagination['links'].append({'number': number, 'url': page_url(number)})
        previous = number
    pagination['previous_url'] = page_url(pagination['page'] - 1) if pagination['page'] > 1 else None
    pagination['next_url'] = page_url(pagination['page'] + 1) if pagination['page'] < pagination['pages'] else None
    if current_user.role == "admin":
        scope_tabs = [
            {"key": "all", "label": "Tất cả câu được phép xem"},
            {"key": "common", "label": "Câu dùng chung"},
            {"key": "mine", "label": "Đóng góp riêng (kiểm toán)"},
        ]
    else:
        scope_tabs = [
            {"key": "all", "label": "Tất cả câu được phép xem"},
            {"key": "common", "label": "Câu dùng chung"},
            {"key": "mine", "label": "Câu riêng của tôi"},
        ]
    from services.bank_overview import knowledge_overview
    hydrate_readiness(scope_questions)
    defaults = {
        "question_type": q_type_filter if q_type_filter in ("single", "true_false", "short_answer") else "single",
        "difficulty_level": diff_filter if diff_filter in _DETAIL_DIFFICULTIES else "nhan_biet",
        "curriculum_node_id": int(selected_node) if selected_node.isdigit() and int(selected_node) in known_node_ids else None,
    }
    if not research_bank:
        defaults.update(curriculum_mode='general', grade=bank.grade, question_category=selected_node.removeprefix('category:') if selected_node else '')
        for item in questions_json:
            item['curriculum_mode'] = 'general'
    return render_template(
        "question_bank_detail.html",
        knowledge_sections=knowledge_overview(catalog, scope_questions, research=research_bank),
        selected_node=selected_node,
        selected_category_name=next((n['category_name'] for n in catalog if str(n['id']) == selected_node), ''),
        manual_defaults=defaults, bank=bank, questions=questions, research_bank=research_bank,
        questions_json=questions_json, available_grades=available_grades,
        id6_catalog=catalog if research_bank else [],
        can_edit=can_edit_bank(current_user, bank),
        can_add=can_add_question(current_user, bank),
        is_admin=current_user.role == "admin",
        question_count=len(scope_questions),
        result_count=pagination["total"], pagination=pagination,
        authorized_count=len(all_authorized_questions),
        scope_counts=scope_counts,
        scope_filter=scope_filter,
        scope_tabs=scope_tabs,
        scope_urls=scope_urls,
        diff_stats=diff_stats, type_stats=type_stats,
    )


@login_required
@role_required("teacher")
def question_bank_question_detail_json(bank_id, question_id):
    """Read exactly one question, rechecking current bank/question access."""
    bank = _get_viewable_question_bank(bank_id)
    question = BankQuestion.query.filter_by(id=question_id, bank_id=bank.id).first_or_404()
    require_question_view(question, bank=bank)
    response = jsonify(success=True, question=_serialize_question_for_actor(question, bank=bank))
    # Full answer data is cached only in this page's component, never by a
    # shared HTTP cache or beyond the currently authenticated session.
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@login_required
@role_required("teacher")
def update_question_adaptive_control(bank_id, question_id):
    bank = _get_viewable_question_bank(bank_id)
    question = BankQuestion.query.filter_by(id=question_id, bank_id=bank.id).first_or_404()
    require_question_edit(question, bank=bank)
    try:
        priority = int(request.form.get("adaptive_priority", 0))
    except (TypeError, ValueError):
        priority = 0
    question.adaptive_priority = max(0, min(100, priority))
    question.adaptive_excluded = request.form.get("adaptive_excluded") == "1"
    band = request.form.get("difficulty_band", "")
    question.difficulty_band = band if band in ("easy", "medium", "hard", "challenge") else None
    db.session.commit()
    flash("Đã lưu quyền kiểm soát thích ứng cho câu hỏi.", "success")
    return redirect(url_for("question_bank_detail", bank_id=bank.id, **_detail_redirect_params()))
@login_required
@role_required("teacher")
def question_bank_classification(bank_id):
    bank = _get_accessible_question_bank(bank_id)
    status_filter = request.args.get("status", "unclassified")
    node_filter = request.args.get("node_id", type=int)
    search_q = request.args.get("q", "").strip()

    query = BankQuestion.query.filter_by(bank_id=bank.id)
    if status_filter == "classified":
        query = query.filter(BankQuestion.curriculum_node_id.is_not(None))
    elif status_filter == "unclassified":
        query = query.filter(BankQuestion.curriculum_node_id.is_(None))
    elif status_filter in ('suggested', 'needs_review', 'teacher_confirmed'):
        query = query.filter_by(classification_status=status_filter)
    if node_filter:
        query = query.filter_by(curriculum_node_id=node_filter)
    if search_q:
        query = query.filter(BankQuestion.question_text.ilike(f"%{search_q}%"))

    questions = [
        question for question in query.order_by(BankQuestion.id).limit(500).all()
        if can_view_question(current_user, question, bank=bank)
    ]
    classified_count = sum(1 for question in bank.questions
                           if can_view_question(current_user, question, bank=bank)
                           and question.curriculum_node_id is not None)
    visible_question_count = sum(1 for question in bank.questions
                                if can_view_question(current_user, question, bank=bank))
    suggested_count = sum(1 for question in bank.questions
                          if can_view_question(current_user, question, bank=bank)
                          and question.classification_status == "suggested")
    nodes = CurriculumNode.query.filter_by(is_active=True).order_by(
        CurriculumNode.grade,
        CurriculumNode.chapter_code,
        CurriculumNode.lesson_code,
        CurriculumNode.category_code,
    ).all()
    from services.question_classification_service import content_fingerprint
    classification_views = {}
    for question in questions:
        try:
            value = json.loads(question.classification_data or '{}')
        except (TypeError, ValueError):
            value = {}
        if value and value.get('content_fingerprint') != content_fingerprint(question.to_dict()):
            value = {**value, 'status': 'stale', 'rationale': ['Nội dung đã thay đổi; hãy chạy phân loại lại hoặc gán thủ công.']}
        classification_views[question.id] = value
    return render_template(
        "question_bank_classification.html",
        bank=bank,
        questions=questions,
        id6_catalog=catalog_options(),
        nodes=nodes,
        classification_views=classification_views,
        classified_count=classified_count,
        visible_question_count=visible_question_count,
        unclassified_count=max(visible_question_count - classified_count, 0),
        suggested_count=suggested_count,
        can_edit=can_edit_bank(current_user, bank),
        question_permissions={question.id: {
            "can_edit": can_edit_question(current_user, question, bank=bank),
            "source_label": question_source_label(current_user, question, bank=bank),
        } for question in questions},
    )


@login_required
@role_required("teacher")
def accept_classification_suggestions(bank_id):
    """Lock unchanged automatic suggestions selected by the teacher."""
    bank = _get_accessible_question_bank(bank_id)
    ids = []
    for value in request.form.getlist('question_ids'):
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            pass
    if not ids:
        flash('Hãy chọn ít nhất một gợi ý.', 'warning')
        return redirect(url_for('question_bank_classification', bank_id=bank.id, status='suggested'))
    questions = BankQuestion.query.filter(BankQuestion.bank_id == bank.id, BankQuestion.id.in_(ids)).all()
    if len(questions) != len(set(ids)):
        abort(400)
    if any(not can_edit_question(current_user, question, bank=bank) for question in questions):
        abort(403)
    from services.question_classification_service import content_fingerprint
    accepted, stale = 0, []
    try:
        for question in questions:
            data = json.loads(question.classification_data or '{}')
            if data.get('status') != 'suggested' or data.get('content_fingerprint') != content_fingerprint(question.to_dict()):
                stale.append(question.id)
                continue
            node = CurriculumNode.query.filter_by(canonical_code=data.get('primary_code'), is_active=True).first()
            if not node or data.get('difficulty_level') not in LEVEL_CODES:
                stale.append(question.id)
                continue
            question.difficulty_level = data['difficulty_level']
            select_curriculum(question, node.id)
            data.update(status='teacher_confirmed', locked=True,
                        rationale=(data.get('rationale') or []) + ['Giáo viên đã xác nhận gợi ý tự động.'])
            question.classification_status = 'teacher_confirmed'
            question.classification_data = json.dumps(data, ensure_ascii=False)
            accepted += 1
        db.session.commit()
    except (TypeError, ValueError):
        db.session.rollback()
        flash('Không thể xác nhận một hoặc nhiều gợi ý.', 'danger')
        return redirect(url_for('question_bank_classification', bank_id=bank.id, status='suggested'))
    if accepted:
        flash(f'Đã xác nhận {accepted} gợi ý và khóa nhãn giáo viên.', 'success')
    if stale:
        flash('Không xác nhận được câu #' + ', #'.join(map(str, stale)) + ' vì nội dung hoặc danh mục đã thay đổi.', 'warning')
    return redirect(url_for('question_bank_classification', bank_id=bank.id, status='suggested'))


@login_required
@role_required("teacher")
def classification_evaluation_page(bank_id):
    bank = _get_accessible_question_bank(bank_id)
    report, error = None, None
    if request.method == 'POST':
        uploaded = request.files.get('labels_file')
        try:
            if not uploaded or not uploaded.filename.lower().endswith('.json'):
                raise ValueError('Hãy chọn file nhãn JSON.')
            raw = uploaded.stream.read(5 * 1024 * 1024 + 1)
            if len(raw) > 5 * 1024 * 1024:
                raise ValueError('File nhãn vượt quá 5 MB.')
            rows = json.loads(raw.decode('utf-8'))
            if not isinstance(rows, list):
                raise ValueError('File nhãn phải là một mảng JSON.')
            if any(not isinstance(row, dict) for row in rows):
                raise ValueError('Mỗi dòng nhãn phải là một đối tượng JSON.')
            if any('question' in row and row['question'] is not None and not isinstance(row['question'], dict) for row in rows):
                raise ValueError('Nội dung question phải là một đối tượng JSON.')
            for row in rows:
                question = row.get('question') or row
                if row.get('scope') is not None and not isinstance(row['scope'], dict):
                    raise ValueError('Phạm vi scope phải là một đối tượng JSON.')
                for label in ('expected_primary_code', 'expected_difficulty_level'):
                    if row.get(label) is not None and not isinstance(row[label], str):
                        raise ValueError('Nhãn dạng và mức nhận thức phải là chuỗi ký tự.')
                for field in ('options', 'statements'):
                    answers = question.get(field)
                    if answers is not None and (not isinstance(answers, list) or any(not isinstance(answer, dict) for answer in answers)):
                        raise ValueError('Phương án và phát biểu phải là mảng các đối tượng JSON.')
            from services.classification_evaluation import evaluate
            report = evaluate(rows)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            error = str(exc)
    return render_template('classification_evaluation.html', bank=bank, report=report, error=error)


@login_required
@role_required("teacher")
def classification_evaluation_export(bank_id):
    bank = _get_accessible_question_bank(bank_id)
    questions = [
        question for question in BankQuestion.query.filter(
            BankQuestion.bank_id == bank.id,
            BankQuestion.grade.in_(('9', 'Lớp 9')),
            BankQuestion.chapter == '8',
            BankQuestion.section == 'i',
        ).order_by(BankQuestion.id).all()
        if can_view_question(current_user, question, bank=bank)
    ]
    from services.evaluation_dataset import build_blinded_rows
    packet = build_blinded_rows([question.to_dict() for question in questions])
    payload = json.dumps(packet['rows'], ensure_ascii=False, indent=2).encode('utf-8')
    return send_file(io.BytesIO(payload), as_attachment=True,
                     download_name=f'nhan-doc-lap-ngan-hang-{bank.id}.json', mimetype='application/json')


@login_required
@role_required("teacher")
def bulk_classify_questions(bank_id):
    bank = _get_accessible_question_bank(bank_id)
    question_ids = []
    for raw_id in request.form.getlist("question_ids"):
        try:
            question_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not question_ids:
        flash("Hãy chọn ít nhất một câu hỏi.", "warning")
        return redirect(url_for("question_bank_classification", bank_id=bank.id))

    questions = BankQuestion.query.filter(
        BankQuestion.bank_id == bank.id,
        BankQuestion.id.in_(question_ids),
    ).all()
    if len(questions) != len(set(question_ids)):
        abort(400)
    if any(not can_edit_question(current_user, question, bank=bank) for question in questions):
        abort(403)

    try:
        difficulty = request.form.get("difficulty_level", "")
        question_type = request.form.get("question_type", "")
        if difficulty not in LEVEL_CODES or question_type not in TYPE_CODES:
            raise ValueError("Hãy chọn mức độ và loại câu hỏi D/T/S.")
        # Changing answer structure requires reviewing the dynamic answer form.
        if any(("true_false" if q.question_type == "truefalse" else q.question_type) != question_type for q in questions):
            raise ValueError("Chỉ gán hàng loạt cho các câu cùng hình thức đã chọn. Đổi hình thức và đáp án tại phần sửa từng câu.")
        for question in questions:
            question.question_type = question_type
            question.difficulty_level = difficulty
            select_curriculum(question, request.form.get("curriculum_node_id"))
            try:
                classification = json.loads(question.classification_data or '{}')
            except (TypeError, ValueError):
                classification = {}
            classification.update(status='teacher_confirmed', locked=True,
                                  primary_code=question.curriculum_node.canonical_code,
                                  difficulty_level=difficulty,
                                  rationale=['Giáo viên đã xác nhận dạng kiến thức và mức nhận thức.'])
            from services.question_classification_service import content_fingerprint
            classification['content_fingerprint'] = content_fingerprint(question.to_dict())
            question.classification_status = 'teacher_confirmed'
            question.classification_data = json.dumps(classification, ensure_ascii=False)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("question_bank_classification", bank_id=bank.id))
    flash(f"Đã xác nhận phân loại kiến thức cho {len(questions)} câu.", "success")
    return redirect(url_for("question_bank_classification", bank_id=bank.id, status="classified"))


@login_required
@role_required("teacher")
def edit_question_bank(bank_id):
    bank = _get_accessible_question_bank(bank_id)

    if request.method == "POST":
        form_data, form_errors = _bank_form_values()
        if form_errors:
            return render_template("question_bank_form.html", bank=bank, form_data=form_data, form_errors=form_errors)
        for key, value in form_data.items():
            setattr(bank, key, value)
        bank.updated_at = dt.datetime.utcnow()
        db.session.commit()
        flash("Đã cập nhật thông tin ngân hàng câu hỏi.", "success")
        return redirect(url_for("question_bank_detail", bank_id=bank.id))
    return render_template("question_bank_form.html", bank=bank)


@login_required
@role_required("teacher")
def delete_question_bank(bank_id):
    bank = _get_accessible_question_bank(bank_id)

    try:
        # 1. Clean up linked ImportSessions & their temporary files
        sessions = ImportSession.query.filter_by(bank_id=bank.id).all()
        for session in sessions:
            ImportService.cleanup_temp_file(session)
            db.session.delete(session)

        # 2. Delete all question images and option images on disk
        for q in bank.questions:
            if q.image_url:
                rel_path = q.image_url.lstrip("/")
                full_path = os.path.join(current_app.root_path, rel_path)
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    try:
                        os.remove(full_path)
                    except OSError:
                        pass
            for opt in q.options:
                if hasattr(opt, "image_url") and opt.image_url:
                    opt_rel = opt.image_url.lstrip("/")
                    opt_full = os.path.join(current_app.root_path, opt_rel)
                    if os.path.exists(opt_full) and os.path.isfile(opt_full):
                        try:
                            os.remove(opt_full)
                        except OSError:
                            pass

        # 3. Delete any import_temp folder associated with this bank
        bank_temp_dir = os.path.join(current_app.root_path, "static", "uploads", "import_temp", str(bank.id))
        if os.path.exists(bank_temp_dir):
            import shutil
            shutil.rmtree(bank_temp_dir, ignore_errors=True)

        # 4. Unlink foreign keys in Exam & ExamQuestion
        exams = Exam.query.filter_by(question_bank_id=bank.id).all()
        for ex in exams:
            ex.question_bank_id = None

        q_ids = [q.id for q in bank.questions]
        if q_ids:
            exam_qs = ExamQuestion.query.filter(ExamQuestion.bank_question_id.in_(q_ids)).all()
            for eq in exam_qs:
                eq.bank_question_id = None

        # 5. Delete the QuestionBank record (cascades to questions & options)
        db.session.delete(bank)
        db.session.commit()

        # 6. Purge any orphan unreferenced image files from static/uploads/questions
        ImportService.cleanup_orphan_question_images()

        flash("Đã xóa hoàn toàn ngân hàng câu hỏi và toàn bộ dữ liệu liên quan.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Lỗi khi xóa ngân hàng câu hỏi: {str(e)}", "danger")

    return redirect(url_for("question_bank_list"))


@login_required
@role_required("teacher")
def add_bank_question(bank_id):
    # Appending a new row is a separate permission from editing bank
    # metadata/existing rows.  This is what enables teacher-owned private
    # overlays in an admin shared bank without making the shared bank editable.
    bank = db.session.get(QuestionBank, bank_id) or abort(404)
    bank = require_bank_add(bank)

    context = request.form.get("context", "").strip()
    question_text = request.form.get("question_text", "").strip()
    question_type = request.form.get("question_type", "single")
    if question_type == "truefalse":
        question_type = "true_false"
    difficulty_level = request.form.get("difficulty_level", "nhan_biet")
    points = 1.0  # Practice papers apply their own versioned scoring weights.
    explanation = request.form.get("explanation", "").strip()
    short_answer_mode = request.form.get("short_answer_mode", "").strip()
    short_answer_tolerance = request.form.get("short_answer_tolerance", "0").strip() or "0"
    
    if not question_text:
        flash("Nội dung câu hỏi không được để trống.", "danger")
        return redirect(url_for("question_bank_detail", bank_id=bank.id, **_detail_redirect_params()))
        
    bq = BankQuestion(
        bank_id=bank.id,
        question_text=question_text,
        context=context,
        question_type=question_type,
        difficulty_level=difficulty_level,
        points=points,
        explanation=explanation,
        subject=bank.subject,
        grade=bank.grade,
        topic=bank.topic,
        created_by=current_user.id
    )
    try:
        # Scope is server-owned.  Existing teacher routes still target only
        # their own private bank; this stamp does not enable shared-bank
        # overlays.
        set_new_question_scope(bq, current_user, bank)
        require_supported_type(question_type)
        if question_type == 'short_answer':
            if not any(part.strip() for part in request.form.get('short_answers', '').split('|')):
                raise ValueError('Trả lời ngắn cần có đáp án mẫu.')
            if short_answer_mode not in ("numeric", "text"):
                raise ValueError('Trả lời ngắn phải chọn cách chấm tự động: số hoặc văn bản.')
            from services.practice_blueprint import numeric_value
            tolerance = numeric_value(short_answer_tolerance)
            if tolerance < 0 or tolerance > 1:
                raise ValueError('Sai số tuyệt đối phải từ 0 đến 1.')
        from services.bank_detail_page import is_research_bank
        research_bank = is_research_bank(bank)
        if research_bank:
            select_curriculum(bq, request.form.get("curriculum_node_id"))
        else:
            from services.bank_curriculum import set_general_category
            set_general_category(bq, request.form.get('question_category'))

        if difficulty_level not in _DETAIL_DIFFICULTIES:
            raise ValueError('Chọn mức độ hợp lệ.')
        if request.form.get('reviewed') != '1':
            raise ValueError('Vui lòng xác nhận nội dung, đáp án và nhãn kiến thức trước khi lưu.')
        bq.classification_status = 'teacher_confirmed'
        if question_type == 'true_false' and research_bank:
            from services.practice_blueprint import validate_metadata
            statement_nodes = request.form.getlist('statement_node')
            statement_levels = request.form.getlist('statement_level')
            if len(statement_nodes) != 4 or len(statement_levels) != 4:
                raise ValueError('Cần nhãn cho đủ bốn ý Đúng/Sai.')
            statements = []
            for node_id, level in zip(statement_nodes, statement_levels):
                node = db.session.get(CurriculumNode, int(node_id)) if node_id else bq.curriculum_node
                if not node or not node.is_active:
                    raise ValueError('Dạng kiến thức của ý Đúng/Sai không hợp lệ.')
                statements.append({'curriculum_code': node.canonical_code, 'cognitive_level': level or difficulty_level})
            bq.learning_metadata = json.dumps(validate_metadata({'statements': statements}), ensure_ascii=False)
        if question_type == "single":
            options = request.form.getlist("option_text")
            if len(options) != 4 or any(not opt.strip() for opt in options) or request.form.get("correct_option") not in {"0", "1", "2", "3"}:
                raise ValueError("Loại D cần đủ 4 phương án và một đáp án đúng.")
        elif question_type == "true_false":
            flags = request.form.getlist("correct_option")
            if len(flags) != 4 or any(flag not in ("true", "false") for flag in flags):
                raise ValueError("Chọn Đúng/Sai cho đủ bốn mệnh đề.")
            if len(request.form.getlist("option_text")) != 4 or any(not opt.strip() for opt in request.form.getlist("option_text")):
                raise ValueError("Loại T cần đủ 4 phát biểu a, b, c, d.")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("question_bank_detail", bank_id=bank.id, **_detail_redirect_params()))
    db.session.add(bq)
    if question_type == "short_answer":
        bq.learning_metadata = json.dumps({
            "short_answer": {"mode": short_answer_mode, "tolerance": str(tolerance)},
        }, ensure_ascii=False)
    db.session.flush()
    
    # Process options based on question_type
    if question_type == "single":
        option_texts = request.form.getlist("option_text")
        correct_index = int(request.form.get("correct_option", 0)) if request.form.get("correct_option") else 0
        for idx, opt_text in enumerate(option_texts):
            if opt_text.strip():
                opt = BankQuestionOption(
                    question_id=bq.id,
                    option_text=opt_text.strip(),
                    is_correct=(idx == correct_index),
                    order_index=idx
                )
                db.session.add(opt)
    elif question_type == "true_false":
        option_texts = request.form.getlist("option_text")
        correct_values = request.form.getlist("correct_option")
        labels = ["a", "b", "c", "d", "e", "f"]
        for idx, opt_text in enumerate(option_texts):
            if opt_text.strip():
                stmt_label = labels[idx] if idx < len(labels) else f"s{idx+1}"
                full_text = f"{stmt_label}) {opt_text.strip()}" if not opt_text.strip().startswith(f"{stmt_label})") else opt_text.strip()
                is_corr = correct_values[idx] == "true" if idx < len(correct_values) else False
                opt = BankQuestionOption(
                    question_id=bq.id,
                    option_text=full_text,
                    is_correct=is_corr,
                    order_index=idx
                )
                db.session.add(opt)
    elif question_type == "short_answer":
        answers_raw = request.form.get("short_answers", "").strip()
        answers = [a.strip() for a in answers_raw.split("|") if a.strip()]
        for idx, ans in enumerate(answers):
            opt = BankQuestionOption(
                question_id=bq.id,
                option_text=ans,
                is_correct=True,
                order_index=idx
            )
            db.session.add(opt)
    db.session.flush()
    from services.practice_blueprint import readiness_error
    from services.bank_curriculum import bank_readiness_error
    error = bank_readiness_error(bq, research=research_bank)
    if error:
        db.session.rollback()
        flash(error, 'danger')
        return redirect(url_for('question_bank_detail', bank_id=bank.id, **_detail_redirect_params()))
    upload = request.files.get('question_image')
    if upload and upload.filename:
        try:
            from services.question_images import save_question_image
            bq.image_url = save_question_image(upload)
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), 'danger')
            return redirect(url_for('question_bank_detail', bank_id=bank.id, **_detail_redirect_params()))
    from services.question_latex import normalize_bank_latex
    normalize_bank_latex(bq)
    from services.import_duplicates import ContentNormalizer
    normalizer = ContentNormalizer()
    candidate = normalizer.describe(bq.to_dict())
    for existing in bank.questions:
        if existing.id == bq.id or not can_view_question(current_user, existing, bank=bank):
            continue
        prior = normalizer.describe(existing.to_dict())
        if candidate['key'] and candidate['key'] == prior['key']:
            same_answers = candidate['answers'] == prior['answers']
            db.session.rollback()
            flash('Câu này đã có trong ngân hàng; không lưu bản trùng.' if same_answers else
                  'Nội dung trùng câu đã có nhưng đáp án khác. Hãy kiểm tra và sửa câu hiện có.', 'warning')
            return redirect(url_for('question_bank_detail', bank_id=bank.id, **_detail_redirect_params()))
    stamp_bank_question_content(bq)
    db.session.commit()
    flash("Đã thêm câu hỏi mới vào ngân hàng.", "success")
    return redirect(url_for("question_bank_detail", bank_id=bank.id, **_detail_redirect_params()))


@login_required
@role_required("teacher")
def delete_bank_question(question_id):
    bq = db.session.get(BankQuestion, question_id) or abort(404)
    require_question_delete(bq)
    bank_id = bq.bank_id
    db.session.delete(bq)
    db.session.commit()
    flash("Đã xóa câu hỏi.", "success")
    return redirect(url_for("question_bank_detail", bank_id=bank_id))


@login_required
@role_required("teacher")
def update_bank_question_json(question_id):
    bq = db.session.get(BankQuestion, question_id)
    if not bq:
        return jsonify({"success": False, "message": "Không tìm thấy câu hỏi."}), 404
    if not can_edit_question(current_user, bq):
        # Preserve the JSON endpoint contract for unauthorized mutation
        # attempts while using the same centralized policy as HTML routes.
        return jsonify({"success": False, "message": "Không có quyền chỉnh sửa."}), 403

    data = request.get_json() or {}
    try:
        data['question_type'] = require_supported_type(data.get('question_type', bq.question_type))
        merged = {**bq.to_dict(), **data}
        require_valid_answers(merged)
        from services.practice_blueprint import validate_metadata
        from services.bank_curriculum import general_metadata
        from services.bank_detail_page import is_research_bank
        research_bank = is_research_bank(bq.bank)
        merged["learning_metadata"] = (validate_metadata(merged.get("learning_metadata", {}))
                                       if research_bank else general_metadata(merged))
        data = merged
    except ValueError as exc:
        return jsonify(success=False, message=str(exc)), 400
    bq.question_text = data.get("question_text", bq.question_text).strip()
    bq.context = data.get("context", bq.context or "").strip()
    q_type = data.get("question_type", bq.question_type)
    if q_type == "truefalse":
        q_type = "true_false"
    bq.question_type = q_type
    bq.learning_metadata = json.dumps(data.get("learning_metadata", {}), ensure_ascii=False)
    bq.difficulty_level = data.get("difficulty_level", bq.difficulty_level)
    bq.explanation = data.get("explanation", bq.explanation or "").strip()
    bq.image_url = data.get("image_url", bq.image_url or "").strip()

    try:
        if not research_bank:
            bq.curriculum_node_id = None
            from services.bank_curriculum import set_general_category
            set_general_category(bq, data.get('question_category'))
        elif data.get("curriculum_node_id"):
            select_curriculum(bq, data["curriculum_node_id"])
        if bq.id6_scope or bq.curriculum_node_id:
            if bq.question_type not in TYPE_CODES or bq.difficulty_level not in LEVEL_CODES:
                raise ValueError("Hình thức trả lời hoặc mức nhận thức không hợp lệ.")
            if q_type == "single":
                options = data.get("options", [])
                if len(options) != 4 or any(not (o.get("text") or o.get("option_text") or "").strip() for o in options) or sum(o.get("is_correct") is True for o in options) != 1:
                    raise ValueError("Trắc nghiệm cần đủ 4 phương án và một đáp án đúng.")
            if q_type == "true_false":
                statements = data.get("statements", [])
                if len(statements) != 4 or any(not item.get("text", "").strip() or not isinstance(item.get("answer"), bool) for item in statements):
                    raise ValueError("Đúng/Sai cần 4 phát biểu và đáp án cho từng ý.")
        if not bq.question_text:
            raise ValueError("Nội dung câu hỏi không được để trống.")
    except ValueError as exc:
        db.session.rollback()
        return jsonify(success=False, message=str(exc)), 400

    data = merged
    # Clear existing options
    BankQuestionOption.query.filter_by(question_id=bq.id).delete()

    # Re-create options based on question_type
    if q_type in ("single", "multiple_choice"):
        opts_data = data.get("options", [])
        for idx, opt_item in enumerate(opts_data):
            opt_text = opt_item.get("text") or opt_item.get("option_text") or ""
            if opt_text.strip():
                opt = BankQuestionOption(
                    question_id=bq.id,
                    option_text=opt_text.strip(),
                    is_correct=bool(opt_item.get("is_correct")),
                    order_index=idx
                )
                db.session.add(opt)
    elif q_type == "true_false":
        stmts_data = data.get("statements", [])
        labels = ["a", "b", "c", "d", "e", "f"]
        for idx, stmt in enumerate(stmts_data):
            s_text = stmt.get("text", "").strip()
            s_id = stmt.get("id") or (labels[idx] if idx < len(labels) else f"s{idx+1}")
            if s_text:
                full_text = f"{s_id}) {s_text}" if not s_text.startswith(f"{s_id})") else s_text
                is_corr = bool(stmt.get("answer")) if stmt.get("answer") is not None else False
                opt = BankQuestionOption(
                    question_id=bq.id,
                    option_text=full_text,
                    is_correct=is_corr,
                    order_index=idx
                )
                db.session.add(opt)
    elif q_type == "short_answer":
        opts_data = data.get("options", [])
        for idx, opt_item in enumerate(opts_data):
            opt_text = opt_item.get("text") or opt_item.get("option_text") or ""
            if opt_text.strip():
                opt = BankQuestionOption(
                    question_id=bq.id,
                    option_text=opt_text.strip(),
                    is_correct=True,
                    order_index=idx
                )
                db.session.add(opt)

    db.session.flush()
    from services.question_latex import normalize_bank_latex
    normalize_bank_latex(bq)
    stamp_bank_question_content(bq)
    db.session.commit()
    return jsonify({"success": True, "question": _serialize_question_for_actor(bq, bank=bq.bank)})


@login_required
@role_required("teacher")
def toggle_bank_question_answer_json(question_id):
    bq = db.session.get(BankQuestion, question_id)
    if not bq:
        return jsonify({"success": False, "message": "Không tìm thấy câu hỏi."}), 404
    if not can_edit_question(current_user, bq):
        return jsonify({"success": False, "message": "Không có quyền chỉnh sửa."}), 403

    try:
        require_supported_type(bq.question_type)
    except ValueError as exc:
        return jsonify(success=False, message=str(exc)), 400
    data = request.get_json() or {}
    option_idx = data.get("option_index")
    is_correct = data.get("is_correct")
    stmt_id = data.get("statement_id")

    if option_idx is not None and (not isinstance(option_idx, int) or isinstance(option_idx, bool)):
        return jsonify(success=False, message="Vị trí đáp án không hợp lệ."), 400
    if is_correct is not None and not isinstance(is_correct, bool):
        return jsonify(success=False, message="Đáp án phải là Đúng hoặc Sai."), 400
    opts = BankQuestionOption.query.filter_by(question_id=bq.id).order_by(BankQuestionOption.order_index).all()
    
    if bq.question_type == "single":
        if option_idx is not None and 0 <= option_idx < len(opts):
            for idx, opt in enumerate(opts):
                opt.is_correct = (idx == option_idx)
    elif bq.question_type == "multiple_choice":
        if option_idx is not None and 0 <= option_idx < len(opts):
            if is_correct is not None:
                opts[option_idx].is_correct = bool(is_correct)
            else:
                opts[option_idx].is_correct = not opts[option_idx].is_correct
    elif bq.question_type in ("true_false", "truefalse"):
        if option_idx is not None and 0 <= option_idx < len(opts):
            if is_correct is not None:
                opts[option_idx].is_correct = bool(is_correct)
            else:
                opts[option_idx].is_correct = not opts[option_idx].is_correct
        elif stmt_id:
            for opt in opts:
                if opt.option_text.lower().startswith(stmt_id.lower() + ")") or opt.option_text.lower().startswith(stmt_id.lower() + "."):
                    opt.is_correct = bool(is_correct)
                    break

    db.session.commit()
    return jsonify({"success": True, "question": _serialize_question_for_actor(bq, bank=bq.bank)})

@login_required
def batch_get_formulas():
    """
    Return MathML/LaTeX/status for a list of FormulaAsset IDs.
    Access control: only return formulas that appear in banks the user can access.
    """
    data = request.get_json() or {}
    uuids = data.get("uuids", [])
    if not isinstance(uuids, list):
        return jsonify({"success": False, "message": "uuids must be a list"}), 400
    
    # Limit batch size
    uuids = uuids[:200]
        
    results = {}
    if uuids:
        assets = FormulaAsset.query.filter(FormulaAsset.id.in_(uuids)).all()
        for asset in assets:
            results[asset.id] = asset.to_api_dict()
            
    return jsonify({"success": True, "formulas": results})


@login_required
def render_formula_svg(formula_id):
    """
    SVG vector rendering endpoint for formula fallback.
    
    Cached SVGs remain available through the formula API.  This endpoint only
    handles the legacy uncached fallback and no longer starts a converter.
    """
    # Validate formula_id format
    try:
        uuid.UUID(formula_id)
    except (ValueError, AttributeError):
        abort(404)
    
    asset = db.session.get(FormulaAsset, formula_id)
    if not asset:
        abort(404)
    
    # If conversion is pending, return 202
    if asset.conversion_status == "pending":
        return jsonify({
            "status": "pending",
            "message": "Đang chuyển đổi công thức..."
        }), 202
    
    # If conversion failed, return 404
    if asset.conversion_status == "failed":
        return jsonify({
            "status": "failed",
            "message": "Không thể chuyển đổi công thức"
        }), 404
    
    # Legacy binary assets are intentionally not converted anymore.  A cached
    # SVG (when present) is still returned by the formula batch API and remains
    # visible to existing questions; this endpoint only handles uncached TeX.
    return jsonify({
        "status": "no_svg",
        "message": "SVG chưa sẵn sàng"
    }), 404


@login_required
@role_required("teacher")
def retry_formula_conversion(formula_id):
    """Retry a failed/pending document-level LaTeX asset."""
    try:
        uuid.UUID(formula_id)
    except (ValueError, AttributeError):
        abort(404)

    asset = db.session.get(FormulaAsset, formula_id)
    if not asset:
        abort(404)

    result = ImportService.retry_formula_asset(asset)
    db.session.commit()
    status_code = 200 if result.get("success") else (202 if result.get("pending") else 422)
    formula_data = asset.to_api_dict()
    return jsonify({
        **result,
        "formula": formula_data,
    }), status_code



def register_question_bank_routes(app) -> None:
    """Register handlers while preserving the legacy route contract."""
    app.add_url_rule("/question-banks", endpoint="question_bank_list", view_func=question_bank_list)
    app.add_url_rule("/question-banks/new", endpoint="create_question_bank", view_func=create_question_bank, methods=["GET", "POST"])
    app.add_url_rule("/question-banks/<int:bank_id>", endpoint="question_bank_detail", view_func=question_bank_detail)
    app.add_url_rule("/api/question-banks/<int:bank_id>/questions/<int:question_id>", endpoint="question_bank_question_detail_json", view_func=question_bank_question_detail_json)
    app.add_url_rule("/question-banks/<int:bank_id>/questions/<int:question_id>/adaptive", endpoint="update_question_adaptive_control", view_func=update_question_adaptive_control, methods=["POST"])
    app.add_url_rule("/question-banks/<int:bank_id>/classification", endpoint="question_bank_classification", view_func=question_bank_classification)
    app.add_url_rule("/question-banks/<int:bank_id>/classification/accept-suggestions", endpoint="accept_classification_suggestions", view_func=accept_classification_suggestions, methods=["POST"])
    app.add_url_rule("/question-banks/<int:bank_id>/classification/evaluation", endpoint="classification_evaluation_page", view_func=classification_evaluation_page, methods=["GET", "POST"])
    app.add_url_rule("/question-banks/<int:bank_id>/classification/evaluation/export", endpoint="classification_evaluation_export", view_func=classification_evaluation_export)
    app.add_url_rule("/question-banks/<int:bank_id>/classification/bulk", endpoint="bulk_classify_questions", view_func=bulk_classify_questions, methods=["POST"])
    app.add_url_rule("/question-banks/<int:bank_id>/edit", endpoint="edit_question_bank", view_func=edit_question_bank, methods=["GET", "POST"])
    app.add_url_rule("/question-banks/<int:bank_id>/delete", endpoint="delete_question_bank", view_func=delete_question_bank, methods=["POST"])
    app.add_url_rule("/question-banks/<int:bank_id>/questions/add", endpoint="add_bank_question", view_func=add_bank_question, methods=["POST"])
    app.add_url_rule("/questions/<int:question_id>/delete", endpoint="delete_bank_question", view_func=delete_bank_question, methods=["POST"])
    app.add_url_rule("/questions/<int:question_id>/update", endpoint="update_bank_question_json", view_func=update_bank_question_json, methods=["POST"])
    app.add_url_rule("/questions/<int:question_id>/toggle-answer", endpoint="toggle_bank_question_answer_json", view_func=toggle_bank_question_answer_json, methods=["POST"])
    app.add_url_rule("/api/formulas/batch", endpoint="batch_get_formulas", view_func=batch_get_formulas, methods=["POST"])
    app.add_url_rule("/api/formulas/<formula_id>/render.svg", endpoint="render_formula_svg", view_func=render_formula_svg)
    app.add_url_rule("/api/formulas/<formula_id>/retry", endpoint="retry_formula_conversion", view_func=retry_formula_conversion, methods=["POST"])
