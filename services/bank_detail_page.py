"""Bounded question content reads; ownership/facets use compact projections.

Detail facets still scan compact bank metadata to preserve the legacy access
policy. Ownership roles are joined in one query; readiness reads aggregate
answer structure. Bank-list statistics use grouped rows rather than questions.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

from sqlalchemy import Integer, case, cast, false, func, select
from sqlalchemy.orm import aliased
from database import db
from models import BankQuestion, BankQuestionOption, CurriculumNode, FormulaAsset, User
from services.access_control import (
    can_view_question, can_edit_question, can_delete_question,
    resolve_question_source, question_source_label, question_scope,
)
from services.bank_curriculum import category_name
from services.id6_service import catalog_options
from services.question_normalizer import remove_diacritics


class QuestionFacet(SimpleNamespace):
    """Validation DTO: answers carry presence flags and bounded grading keys."""

    def to_dict(self):
        return {
            'question_type': 'true_false' if self.question_type == 'truefalse' else self.question_type,
            'options': [{'option_text': o.option_text, 'is_correct': o.is_correct} for o in self.options],
            'statements': [{'text': o.statement_text, 'answer': o.is_correct} for o in self.options]
                if self.question_type in ('true_false', 'truefalse') else [],
        }


def text_expressions():
    """Keep Python strip/casefold semantics, including Vietnamese on SQLite."""
    if db.session.get_bind().dialect.name == 'sqlite':
        raw = db.session.connection().connection.driver_connection
        raw.create_function('linhedu_strip', 1, lambda s: str(s or '').strip(), deterministic=True)
        raw.create_function('linhedu_casefold', 1, lambda s: str(s or '').casefold(), deterministic=True)
        raw.create_function('linhedu_statement_present', 1, lambda s: bool(
            (str(s or '')[2:] if len(str(s or '')) > 1 and str(s or '')[1] in ').:'
             else str(s or '')).strip()), deterministic=True)
        return func.linhedu_strip, func.linhedu_casefold, func.linhedu_statement_present
    # PostgreSQL's lower supports Unicode. btrim receives Python's whitespace
    # set rather than stripping only ASCII spaces.
    whitespace = ''.join(chr(i) for i in range(0x3100) if chr(i).isspace())
    strip = lambda value: func.btrim(func.coalesce(value, ''), whitespace)
    statement = lambda value: func.length(strip(case(
        (func.substr(value, 2, 1).in_([')', '.', ':']), func.substr(value, 3)), else_=value))) > 0
    return strip, func.lower, statement


def metadata_for_bank(bank):
    strip, _, _ = text_expressions()
    columns = (
        'id', 'bank_id', 'created_by', 'scope', 'private_owner_id',
        'curriculum_node_id', 'source_id', 'question_type', 'difficulty_level',
        'grade', 'question_category', 'classification_data', 'classification_status',
        'learning_metadata', 'adaptive_excluded',
    )
    creator, owner = aliased(User), aliased(User)
    tuples = db.session.query(*[getattr(BankQuestion, key) for key in columns],
        (func.length(strip(BankQuestion.question_text)) > 0).label('prompt_present'),
        creator.role.label('creator_role'), owner.role.label('owner_role'),
    ).select_from(BankQuestion).outerjoin(creator, creator.id == BankQuestion.created_by).outerjoin(
        owner, owner.id == BankQuestion.private_owner_id
    ).filter(BankQuestion.bank_id == bank.id).all()
    rows = []
    for record in tuples:
        data = {key: getattr(record, key) for key in columns}
        rows.append(QuestionFacet(**data, bank=bank, creator=SimpleNamespace(id=record.created_by, role=record.creator_role) if record.created_by is not None else None,
            private_owner=SimpleNamespace(id=record.private_owner_id, role=record.owner_role) if record.private_owner_id is not None else None,
            question_text='x' if record.prompt_present else '', options=[], curriculum_node=None))
    return rows


def is_research_bank(bank, metadata=None):
    """Same classification as bank_curriculum without touching bank.questions."""
    grade = re.search(r'\d+', bank.grade or '')
    if grade and grade.group() != '9':
        return False
    topic = remove_diacritics(bank.topic or '').lower().strip()
    if topic:
        return 'xac suat' in topic or 'khong gian mau' in topic
    if 'xac suat' in remove_diacritics(bank.name or '').lower():
        return True
    if metadata is None:
        return db.session.query(BankQuestion.id).filter(BankQuestion.bank_id == bank.id,
            BankQuestion.curriculum_node_id.isnot(None), BankQuestion.curriculum_node_id != 0).first() is not None
    return any(q.curriculum_node_id for q in metadata)


def catalog_for_metadata(rows, research):
    if research:
        return catalog_options()
    return [dict(id='category:' + name, category='', category_name=name)
        for name in sorted({category_name(q) for q in rows})]


def _id_membership(column, ids):
    """Use one bound collection on supported databases, including large banks."""
    if not ids:
        return false()
    dialect = db.session.get_bind().dialect.name
    if dialect == 'sqlite':
        allowed = func.json_each(json.dumps(ids)).table_valued('value')
        return column.in_(select(allowed.c.value))
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import ARRAY
        return column.in_(select(func.unnest(cast(ids, ARRAY(Integer)))))
    return column.in_(ids)


def hydrate_readiness(rows):
    """Batch answer structure in SQL; only numeric keys need actual characters.

    Validation DTOs preserve the same structural conditions as answer_issues:
    exact four options/statements, any blank, any missing key and correct-key
    counts. More than four options can be represented by five for validation.
    Short numeric keys remain bounded to 81 characters (parser limit is 80).
    """
    # Excluded/unreviewed/blank/unsupported rows cannot be ready. Keep their
    # facet counts, but do not query their answers merely to compute zero.
    rows = [q for q in rows if not q.adaptive_excluded and q.question_text
        and q.classification_status == 'teacher_confirmed'
        and q.difficulty_level in ('nhan_biet', 'thong_hieu', 'van_dung', 'van_dung_cao')
        and q.question_type in ('single', 'true_false', 'short_answer')]
    if not rows:
        return
    strip, _, statement_present = text_expressions()
    by_id = {q.id: q for q in rows}
    membership = _id_membership(BankQuestionOption.question_id, list(by_id))
    node_ids = {q.curriculum_node_id for q in rows if q.curriculum_node_id}
    nodes = {n.id: SimpleNamespace(id=n.id, canonical_code=n.canonical_code, is_active=n.is_active)
        for n in db.session.query(CurriculumNode.id, CurriculumNode.canonical_code, CurriculumNode.is_active)
        .filter(_id_membership(CurriculumNode.id, list(node_ids))).all()} if node_ids else {}
    aggregates = db.session.query(
        BankQuestionOption.question_id,
        func.count(BankQuestionOption.id).label('option_count'),
        func.sum(case((func.length(strip(BankQuestionOption.option_text)) == 0, 1), else_=0)).label('blank'),
        func.sum(case((statement_present(BankQuestionOption.option_text), 0), else_=1)).label('blank_statement'),
        func.sum(case((BankQuestionOption.is_correct.is_(True), 1), else_=0)).label('correct'),
        func.sum(case((BankQuestionOption.is_correct.is_(None), 1), else_=0)).label('unanswered'),
    ).filter(membership).group_by(BankQuestionOption.question_id).all()
    stats = {item.question_id: item for item in aggregates}
    numeric_ids = []
    for q in rows:
        q.curriculum_node = nodes.get(q.curriculum_node_id)
        q.options = []
        stat = stats.get(q.id)
        if not stat:
            continue
        try:
            learning = json.loads(q.learning_metadata or '{}')
            numeric = q.question_type == 'short_answer' and learning.get('short_answer', {}).get('mode') == 'numeric'
        except (ValueError, TypeError, AttributeError):
            numeric = False
        if numeric:
            numeric_ids.append(q.id)
            # False sentinel preserves blank-option errors without creating
            # a fabricated accepted key. Actual correct keys follow below.
            q.options = [SimpleNamespace(option_text='' if stat.blank else 'x',
                is_correct=False, statement_text='x')]
            continue
        size = min(stat.option_count, 5)
        for index in range(size):
            correct = True if index < stat.correct else (None if index >= size - stat.unanswered else False)
            q.options.append(SimpleNamespace(
                option_text='' if index == 0 and stat.blank else 'x',
                statement_text='' if index == 0 and stat.blank_statement else 'x', is_correct=correct))
    if numeric_ids:
        for key in db.session.query(BankQuestionOption.question_id,
            func.substr(strip(BankQuestionOption.option_text), 1, 81).label('text')
        ).filter(_id_membership(BankQuestionOption.question_id, numeric_ids),
            BankQuestionOption.is_correct.is_(True)).all():
            by_id[key.question_id].options.append(SimpleNamespace(
                option_text=key.text, is_correct=True, statement_text='x'))


def grouped_bank_stats(banks, actor):
    """Group by access principals, then apply the unchanged central policy.

    No question text/options/relationships are loaded. The access policy can
    evaluate each aggregate because every grouped row has identical bank,
    persisted scope, creator and private owner.
    """
    by_id = {bank.id: bank for bank in banks}
    result = {bank.id: {'count': 0, 'difficulty': dict.fromkeys(
        ('nhan_biet', 'thong_hieu', 'van_dung', 'van_dung_cao'), 0)} for bank in banks}
    creator, owner = aliased(User), aliased(User)
    columns = [BankQuestion.bank_id, BankQuestion.scope, BankQuestion.created_by,
        BankQuestion.private_owner_id, BankQuestion.difficulty_level, creator.role, owner.role]
    grouped = db.session.query(
        *columns[:5], creator.role.label('creator_role'), owner.role.label('owner_role'),
        func.count(BankQuestion.id).label('question_count'),
    ).select_from(BankQuestion).outerjoin(creator, creator.id == BankQuestion.created_by).outerjoin(
        owner, owner.id == BankQuestion.private_owner_id
    ).filter(_id_membership(BankQuestion.bank_id, list(by_id))).group_by(*columns).all() if by_id else []
    for item in grouped:
        bank = by_id[item.bank_id]
        principal = SimpleNamespace(bank_id=bank.id, bank=bank, scope=item.scope,
            created_by=item.created_by, private_owner_id=item.private_owner_id,
            creator=SimpleNamespace(id=item.created_by, role=item.creator_role) if item.created_by is not None else None,
            private_owner=SimpleNamespace(id=item.private_owner_id, role=item.owner_role) if item.private_owner_id is not None else None)
        if not can_view_question(actor, principal, bank=bank):
            continue
        summary = result[bank.id]
        summary['count'] += item.question_count
        if item.difficulty_level in summary['difficulty']:
            summary['difficulty'][item.difficulty_level] += item.question_count
    return result


def authorized_metadata(bank, actor):
    metadata = metadata_for_bank(bank)
    rows = [q for q in metadata if can_view_question(actor, q, bank=bank)]
    buckets = {'common': [], 'private': [], 'unknown': []}
    for q in rows:
        buckets[resolve_question_source(q, bank=bank)['key']].append(q)
    return metadata, rows, buckets


def question_page(bank, rows, filters, catalog, research):
    """Apply readable IDs and all filters before COUNT, ORDER, LIMIT/OFFSET."""
    selected = filters.get('node_id', '')
    node_ids = {node['id'] for node in catalog}
    if selected:
        if not research:
            rows = [q for q in rows if 'category:' + category_name(q) == selected]
        elif selected == '0':
            rows = [q for q in rows if q.curriculum_node_id not in node_ids]
        else:
            rows = [q for q in rows if str(q.curriculum_node_id) == selected]
    query = BankQuestion.query.filter(BankQuestion.bank_id == bank.id)
    query = query.filter(_id_membership(BankQuestion.id, [q.id for q in rows]))
    kind = filters.get('type', '').strip().lower()
    kind = 'true_false' if kind == 'truefalse' else kind
    if kind and kind not in ('single', 'multiple_choice', 'true_false', 'short_answer', 'essay'):
        query = query.filter(false())
    if kind:
        query = query.filter(BankQuestion.question_type.in_(['true_false', 'truefalse']) if kind == 'true_false'
            else BankQuestion.question_type == kind)
    if filters.get('difficulty', '').strip():
        difficulty = filters['difficulty'].strip().lower()
        if difficulty not in ('nhan_biet', 'thong_hieu', 'van_dung', 'van_dung_cao'):
            query = query.filter(false())
        query = query.filter(BankQuestion.difficulty_level == difficulty)
    if filters.get('grade', '').strip():
        query = query.filter(BankQuestion.grade == filters['grade'].strip())
    search = filters.get('q', '').strip()
    if search:
        _, fold, _ = text_expressions()
        query = query.filter(fold(BankQuestion.question_text).contains(search.casefold(), autoescape=True))
    total = query.count()
    try:
        per_page = int(filters.get('per_page', 25))
    except (TypeError, ValueError):
        per_page = 25
    per_page = per_page if per_page in (25, 50) else 25
    pages = max(1, (total + per_page - 1) // per_page)
    try:
        page = max(1, min(int(filters.get('page', 1)), pages))
    except (TypeError, ValueError):
        page = 1
    levels = {key: i for i, key in enumerate(('nhan_biet', 'thong_hieu', 'van_dung', 'van_dung_cao'))}
    kinds = {'single': 0, 'true_false': 1, 'short_answer': 2}
    ordered = query.order_by(func.coalesce(BankQuestion.curriculum_node_id, 0),
        case(levels, value=BankQuestion.difficulty_level, else_=9),
        case(kinds, value=BankQuestion.question_type, else_=9), BankQuestion.id.desc())
    # Duplicate review links may reference a question beyond the first page.
    # Resolve its position using only IDs from the same authorized, filtered
    # query; unreadable or removed IDs leave the ordinary page unchanged.
    try:
        target_id = int(filters.get('question_id', ''))
    except (TypeError, ValueError):
        target_id = None
    if target_id is not None and any(row.id == target_id for row in rows):
        ordered_ids = [item.id for item in ordered.with_entities(BankQuestion.id).all()]
        if target_id in ordered_ids:
            page = ordered_ids.index(target_id) // per_page + 1
    offset = (page - 1) * per_page
    preview_columns = ('id', 'bank_id', 'question_text', 'context', 'image_url', 'question_type',
        'difficulty_level', 'grade', 'source_id', 'curriculum_node_id')
    records = ordered.with_entities(*[getattr(BankQuestion, key) for key in preview_columns]).offset(offset).limit(per_page).all()
    return records, dict(page=page, per_page=per_page, pages=pages, total=total, offset=offset,
        first=offset + 1 if total else 0, last=offset + len(records))


def preview_payload(records, facets, bank, actor, research):
    by_id = {q.id: q for q in facets}
    result = []
    references = set()
    for record in records:
        q = by_id[record.id]
        data = dict(record._mapping)
        data['question_type'] = 'true_false' if data['question_type'] == 'truefalse' else data['question_type']
        data['context'] = data['context'] or ''
        data['image_url'] = data['image_url'] or ''
        source = resolve_question_source(q, bank=bank)['key']
        label = question_source_label(actor, q, bank=bank)
        data.update(source=source, source_label=label, scope_label=label, scope=question_scope(q),
            can_edit=can_edit_question(actor, q, bank=bank), can_delete=can_delete_question(actor, q, bank=bank))
        if not research:
            data.update(curriculum_mode='general', question_category=category_name(q))
        references.update(re.findall(r'\[\[formula:([^\]]+)\]\]', data['question_text'] + ' ' + data['context']))
        result.append(data)
    assets = {a.id: a.to_api_dict() for a in FormulaAsset.query.filter(FormulaAsset.id.in_(references)).all()} if references else {}
    for data in result:
        ids = set(re.findall(r'\[\[formula:([^\]]+)\]\]', data['question_text'] + ' ' + data['context']))
        data['formulas'] = {key: assets[key] for key in ids if key in assets}
    return result
