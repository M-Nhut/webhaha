"""Conservative duplicate detection: content identity is independent of ID6/answers.

Never fetch remote assets. Only byte/pixel-identical local assets or known formula
payloads establish identity; unresolved assets force human comparison.
"""
import hashlib
import html
import json
import re
import unicodedata
import uuid
from collections import defaultdict
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from database import db
from models import BankQuestion, FormulaAsset, QuestionBank
from services.access_control import (
    BANK_VISIBILITY_SHARED,
    QUESTION_SCOPE_PRIVATE,
    QUESTION_SCOPE_SHARED,
    can_include_question_in_duplicate_scan,
    bank_visibility,
    new_question_scope,
    question_scope,
)
from services.question_policy import canonical_type, answer_issues

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'content-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def clean(value):
    value = unicodedata.normalize('NFC', html.unescape(str(value or '')))
    # The active source prefix has literal lesson ``i`` (for example
    # ``%[9C8Ni-1D]``).  Keep numeric historical lessons readable too, but
    # never let either label affect semantic duplicate identity.
    value = re.sub(
        r'%?\[\s*[6-9]C[1-9A-Z][NHVC?](?:[1-9]\d*|i)-[1-9]\d*'
        r'(?:(?:TL|D|T|S)(?:\.[1-9]\d*)?)?\s*\]',
        '', value, flags=re.I,
    )
    value = re.sub(r'^(?:Câu|Bài|Question)\s+\d+\s*[.:)\-]\s*', '', value, flags=re.I)
    return re.sub(r'\s+', ' ', value).strip()


def math_identity(value):
    """Ignore TeX layout only; preserve token boundaries, symbols and numbers."""
    value = clean(value)
    value = re.sub(r'\\(?:left|right|big|Big|bigg|Bigg|bigl|bigr|Bigl|Bigr|biggl|biggr|Biggl|Biggr)\b', '', value)
    value = re.sub(r'\\(?:[,;:!]|[ \t]+)|\\(?:quad|qquad|enspace|thinspace)\b', ' ', value)
    # Text inside math is semantic: keep its word boundaries.
    return re.findall(r'\\(?:text|mathrm|operatorname)\{[^{}]*\}|\\[A-Za-z]+|\\.|[^\s]', value)


class VisibleHTML(HTMLParser):
    def __init__(self, asset):
        super().__init__(convert_charrefs=True)
        self.parts, self.asset, self.uncertain = [], asset, False
    def handle_data(self, data): self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img': self.parts.append(self.asset(attrs.get('src','')))
        elif tag in ('sup','sub'): self.parts.append('^{' if tag=='sup' else '_{')
        elif tag in ('td','th','tr','table'): self.parts.append(' |'+tag+'| ')
        elif tag in ('p','div','br','li'): self.parts.append(' ')
        elif tag not in ('b','strong','i','em','u','span','font','a'):
            self.uncertain = True
    def handle_endtag(self, tag):
        if tag in ('sup','sub'): self.parts.append('}')
        elif tag in ('p','div','li','td','th','tr','table'): self.parts.append(' |/'+tag+'| ' if tag in ('td','th','tr','table') else ' ')


class ContentNormalizer:
    def __init__(self):
        self.asset_cache, self.formula_cache = {}, {}
        self.unresolved = False
    def asset(self, url):
        parsed = urlsplit(html.unescape(str(url)))
        path = unquote(parsed.path)
        key = url
        if key not in self.asset_cache:
            result = None
            if not parsed.scheme and not parsed.netloc and path.startswith('/static/uploads/questions/'):
                local = (ROOT / path.lstrip('/')).resolve()
                if local.is_relative_to((ROOT/'static/uploads/questions').resolve()) and local.is_file():
                    try:
                        from PIL import Image
                        with Image.open(local) as image:
                            if getattr(image,'n_frames',1) == 1:
                                result = digest([image.size, hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest()])
                    except (OSError, ValueError):
                        result = hashlib.sha256(local.read_bytes()).hexdigest()
            self.asset_cache[key] = result
        value = self.asset_cache[key]
        if value is None:
            self.unresolved = True
            return ' [[unresolved-asset]] '
        return ' [[asset:'+value+']] '
    def formula(self, identifier, formulas):
        data = formulas.get(identifier)
        if data is None:
            if identifier not in self.formula_cache:
                model = db.session.get(FormulaAsset, identifier)
                self.formula_cache[identifier] = ({k:getattr(model,k,None) for k in ('source_text','source_preamble','latex','mathml')} if model else {})
            data = self.formula_cache[identifier]
        # FormulaAsset keeps the source payload after UUID remapping.
        if data.get('source_text'): payload = ['source', clean(data['source_text']),clean(data.get('source_preamble'))]
        elif data.get('latex'): payload = ['latex', math_identity(data['latex'])]
        elif data.get('mathml'): payload = ['mathml',clean(data['mathml'])]
        else: payload = None
        if payload is None:
            self.unresolved = True
            return ' [[unresolved-formula]] '
        return ' [[formula:'+digest(payload)+']] '
    def text(self, value, formulas):
        value = str(value or '')
        value = re.sub(r'\[\[formula:([^\]]+)\]\]', lambda m:self.formula(m[1], formulas),value)
        value = re.sub(r'\[\[image:([^\]]+)\]\]',lambda m:self.asset(m[1]),value)
        value = re.sub(r'!\[[^\]]*\]\(([^)]+)\)',lambda m:self.asset(m[1]),value)
        if re.search(r'</?[a-zA-Z][^>]*>',value):
            parser = VisibleHTML(self.asset); parser.feed(value)
            self.unresolved |= parser.uncertain
            value = ''.join(parser.parts)
        return clean(value)
    def describe(self, question):
        self.unresolved = False
        formulas = question.get('formulas') or {}
        kind = canonical_type(question.get('question_type'))
        text = lambda v:self.text(v, formulas)
        stem, context = text(question.get('question_text')),text(question.get('context'))
        picture = self.asset(question['image_url']) if question.get('image_url') else ''
        rows = question.get('statements',[]) if kind=='true_false' else question.get('options',[])
        choices = [text(re.sub(r'^\s*' + re.escape(chr(65+i)) + r'[.)]\s+', '', o.get('text') or o.get('option_text') or '', flags=re.I)) for i,o in enumerate(rows)] if kind!='short_answer' else []
        all_content = ' '.join([stem,context,*choices])
        positional = bool(re.search(r'\b[A-D]\b|ý trên|ý dưới|phương án trên|cả (?:hai|ba|bốn)|tất cả.*trên|above|below|first|second|respectively', all_content))
        reorder = not positional and len(set(choices)) == len(choices)
        if kind == 'short_answer':
            answers = sorted(text(o.get('text') or o.get('option_text')) for o in rows if o.get('is_correct') is True)
        else:
            pairs = [(choice, row.get('answer') if kind=='true_false' else row.get('is_correct')) for choice,row in zip(choices,rows)]
            answers = sorted(pairs,key=lambda p:p[0]) if reorder else pairs
        identity = [VERSION,kind,stem,context,picture,sorted(choices) if reorder else choices]
        uncertain = self.unresolved or bool(question.get('has_image') and not picture and not re.search(r'\[\[(?:asset|unresolved-asset):?', all_content))
        # Known numeric, operator, formula and image differences cannot be auto-matched.
        invariants = re.findall(r'\[\[(?:asset|formula):[^\]]+\]\]|\d+(?:[.,]\d+)?|\\[A-Za-z]+|[+−\-*/=<>≤≥≠^%]', ' '.join([all_content,picture]))
        return dict(identity=identity, key=digest(identity) if stem and not uncertain else None,
                    answers=answers, answers_complete=not bool(answer_issues(question, require_answers=True)[0]), has_solution=bool(clean(question.get("explanation"))), unresolved=uncertain, invariants=sorted(invariants),
                    near=' '.join([stem,context,picture,*sorted(choices)]),
                    revision=digest([identity,answers,question.get('explanation'),question.get('formulas'),question.get('image_url')]))


def ensure_sources(questions):
    for i,q in enumerate(questions):
        q.setdefault('import_uid',str(uuid.uuid4()))
        q.setdefault('source_position',i+1)
        q.setdefault('source_label',f"Mục {q.get('index',i+1)} trong file")


def _fresh_revision_actor(actor, session):
    """Reload the principal used for a write-audience fingerprint."""
    if actor is None:
        actor = _scan_actor(session)
    actor_id = getattr(actor, "id", None)
    if actor_id is not None:
        try:
            from models import User
            actor = db.session.get(User, actor_id, populate_existing=True) or actor
        except Exception:
            pass
    return actor


def _fresh_revision_bank(session, bank=None):
    """Reload destination scope/owner before deriving a confirmation token."""
    bank_id = getattr(session, "bank_id", None)
    if bank_id is not None:
        try:
            bank = db.session.get(QuestionBank, bank_id, populate_existing=True) or bank
        except Exception:
            pass
    if bank is not None and getattr(bank, "created_by", None):
        try:
            from models import User
            db.session.get(User, bank.created_by, populate_existing=True)
            db.session.expire(bank, ["creator"])
        except Exception:
            pass
    return bank


def _write_audience(session, questions, actor=None, bank=None):
    """Describe the server-resolved audience for newly written rows.

    The import confirmation token must bind more than content: a role or
    destination ownership change can change a teacher overlay into common
    content (or make it inaccessible).  Request-supplied ``scope`` and owner
    values are intentionally ignored; ``new_question_scope`` is the same
    server policy used at the final row write.
    """
    actor = _fresh_revision_actor(actor, session)
    bank = _fresh_revision_bank(session, bank)
    actor_id = getattr(actor, "id", None)
    actor_role = getattr(actor, "role", None)
    bank_id = getattr(bank, "id", None) if bank is not None else None
    bank_creator_id = getattr(bank, "created_by", None) if bank is not None else None
    bank_creator = getattr(bank, "creator", None) if bank is not None else None
    bank_creator_role = getattr(bank_creator, "role", None)

    if bank is None:
        # A new bank's scope is server-derived even though no QuestionBank row
        # exists yet.  Its owner is the creating actor for a teacher-private
        # bank and there is no private owner for an admin common bank.
        if actor_role == "teacher":
            planned_scope, planned_owner_id = QUESTION_SCOPE_PRIVATE, actor_id
        elif actor_role == "admin":
            planned_scope, planned_owner_id = QUESTION_SCOPE_SHARED, None
        else:
            planned_scope, planned_owner_id = "denied", None
        target_visibility = "new"
        target_id = None
    else:
        target_visibility = bank_visibility(bank)
        target_id = bank_id
        try:
            planned_scope = new_question_scope(actor, bank)
        except Exception:
            planned_scope = "denied"
        if planned_scope == QUESTION_SCOPE_PRIVATE:
            if actor_role == "teacher" and target_visibility == BANK_VISIBILITY_SHARED:
                planned_owner_id = actor_id
            else:
                planned_owner_id = bank_creator_id
        else:
            planned_owner_id = None

    question_audience = []
    for question in questions or ():
        saved_id = question.get("saved_question_id") if isinstance(question, dict) else None
        persisted = None
        if saved_id:
            try:
                persisted = db.session.get(BankQuestion, saved_id, populate_existing=True)
            except Exception:
                persisted = None
        if persisted is not None:
            resolved_scope = question_scope(persisted)
            resolved_owner_id = getattr(persisted, "private_owner_id", None)
        else:
            resolved_scope = planned_scope
            resolved_owner_id = planned_owner_id
        question_audience.append({
            "import_uid": question.get("import_uid") if isinstance(question, dict) else None,
            "scope": resolved_scope,
            "private_owner_id": resolved_owner_id,
        })

    return {
        "actor": {"id": actor_id, "role": actor_role},
        "target": {
            "id": target_id,
            "visibility": target_visibility,
            "created_by": bank_creator_id,
            "owner_role": bank_creator_role,
        },
        "write": {"scope": planned_scope, "private_owner_id": planned_owner_id},
        "questions": question_audience,
    }


def revision(session, questions, *, actor=None, bank=None):
    """Return a review revision bound to content and server write audience."""
    fields = ('import_uid','question_text','context','image_url','options','statements','formulas','explanation',
              'question_type','source_id','grade','chapter','section','question_category','difficulty_level','points',
              'learning_metadata')
    audience = _write_audience(session, questions, actor=actor, bank=bank)
    return digest([VERSION, "write-audience-v3", session.bank_id,
                   session.scope_data,
                   session.get_duplicate_decisions(), audience,
                   [{k:q.get(k) for k in fields} for q in questions]])


def candidate_record(question, description, *, bank=False):
    reference = f"bank:{question['id']}" if bank else 'file:'+question['import_uid']
    label = question.get('source_id') or f"Câu ngân hàng #{question['id']}" if bank else question['source_label']
    return dict(reference=reference,label=label,bank_question_id=question.get('id') if bank else None,
                import_uid=None if bank else question['import_uid'], question=question,description=description)


def duplicate_candidate_rows(bank, actor):
    """Return only rows the importing actor may compare against.

    ``BankQuestion.query`` is intentionally narrowed before any row is turned
    into a candidate/report.  A teacher therefore cannot receive a foreign
    private question's text, source id, or database id merely because it is in
    the same shared bank.  Administrators' audit visibility is not reused for
    duplicate comparison: their common imports compare with shared rows only.
    """
    if not bank or not actor:
        return []
    return [
        question for question in getattr(bank, "questions", ())
        if can_include_question_in_duplicate_scan(actor, question, bank=bank)
    ]


def _scan_actor(session, actor=None):
    """Resolve a fresh actor for direct service callers as well as routes."""
    if actor is not None:
        return actor
    try:
        from services.import_authorization import fresh_import_actor
        return fresh_import_actor(session.user_id)
    except Exception:
        # Route boundaries already reject this state.  A failed-closed empty
        # candidate set is safer for maintenance/test callers than exposing
        # rows while the actor cannot be resolved.
        return None


def match_info(candidate, current, session, state, reason, normalizer=None):
    d = candidate['description']
    conflict = bool(current['answers_complete'] and d['answers_complete'] and current['answers'] != d['answers'])
    token = digest([session.bank_id, current['revision'],candidate['reference'],d['revision']])
    q = candidate['question']
    question_dict = {k:q.get(k) for k in ('question_text','context','question_type','options','statements','explanation','image_url')}
    formulas = dict(q.get('formulas') or {})
    all_text = ' '.join([
        str(question_dict.get('question_text') or ''),
        str(question_dict.get('context') or ''),
        str(question_dict.get('explanation') or ''),
        *[str(o.get('text') or o.get('option_text') or '') for o in question_dict.get('options') or []],
        *[str(s.get('text') or s.get('option_text') or '') for s in question_dict.get('statements') or []],
    ])
    fids = re.findall(r'\[\[formula:([^\]]+)\]\]', all_text)
    for fid in fids:
        if fid not in formulas:
            data = None
            if normalizer and fid in normalizer.formula_cache:
                data = normalizer.formula_cache[fid]
            if not data:
                asset = db.session.get(FormulaAsset, fid)
                if asset:
                    data = asset.to_api_dict()
            if data:
                formulas[fid] = data
    question_dict['formulas'] = formulas
    return dict(reference=candidate['reference'], label=candidate['label'], bank_question_id=candidate['bank_question_id'],
                token=token, state=state, reviewable=True, reason=reason, answer_conflict=conflict,
                answer_missing=not current['answers_complete'] or not d['answers_complete'],
                preferred='incoming' if current['answers_complete'] and current['has_solution'] and not d['has_solution'] and not conflict else 'existing',
                question=question_dict)


def scan_duplicates(session, questions, *, actor=None, bank=None):
    """Refresh all comparisons; decisions apply only to an unchanged content pair."""
    ensure_sources(questions)
    normalizer = ContentNormalizer()
    actor = _scan_actor(session, actor)
    if bank is None and session.bank_id:
        bank = db.session.get(QuestionBank, session.bank_id)
    bank_rows = []
    if bank is not None:
        bank_rows = sorted(duplicate_candidate_rows(bank, actor), key=lambda row: row.id)
    candidates = [candidate_record(q.to_dict(),normalizer.describe(q.to_dict()),bank=True) for q in bank_rows]
    exact = defaultdict(list)
    for c in candidates:
        if c['description']['key']: exact[c['description']['key']].append(c)
    decisions = session.get_duplicate_decisions()
    descriptions = {q['import_uid']:normalizer.describe(q) for q in questions}
    # Keep the best structurally valid and answered representative of each file group.
    ordered = sorted(questions,key=lambda q:(q.get('status')=='error',bool(answer_issues(q,require_answers=True)[0]),not bool(clean(q.get('explanation'))),q['source_position']))
    for q in ordered:
        d = descriptions[q['import_uid']]
        if q.get('saved_question_id'):
            q['duplicate'] = dict(state='imported',matches=[],reason='Đã lưu trong lần xác nhận trước.')
            continue
        matches = []
        exact_candidates = exact.get(d['key'],[]) if d['key'] else []
        if exact_candidates:
            candidate = exact_candidates[0]
            review = d['answers_complete'] and d['has_solution'] and not candidate['description']['has_solution'] and candidate['bank_question_id'] is not None
            matches = [match_info(candidate,d,session,'review' if review else 'duplicate','Nội dung, dữ kiện và phương án trùng nhau.',normalizer=normalizer)]
        else:
            for candidate in candidates:
                other = candidate['description']
                if d['identity'][1] != other['identity'][1]: continue
                if not d['unresolved'] and not other['unresolved'] and d['invariants'] != other['invariants']: continue
                near = re.sub(r'\[\[(?:unresolved-)?(?:asset|formula)(?::[^\]]+)?\]\]',' [tài sản] ',d['near'])
                other_near = re.sub(r'\[\[(?:unresolved-)?(?:asset|formula)(?::[^\]]+)?\]\]',' [tài sản] ',other['near'])
                if not near or SequenceMatcher(None,near,other_near,autojunk=False).ratio() < 0.88: continue
                match = match_info(candidate,d,session,'review','Nội dung gần giống; cần đối chiếu hình/công thức hoặc cách diễn đạt.',normalizer=normalizer)
                decision = decisions.get(q['import_uid'],{}).get(match['token'])
                if decision == 'different': match['state']='different'
                elif decision == 'duplicate': match['state']='duplicate'
                matches.append(match)
        q.pop('replace_question_id', None)
        for match in matches:
            decision = decisions.get(q['import_uid'], {}).get(match['token'])
            from services.access_control import can_edit_question
            target = db.session.get(BankQuestion, match['bank_question_id']) if match['bank_question_id'] else None
            match['can_replace'] = target is None or can_edit_question(actor, target)
            if decision == 'incoming' and target is not None and not match['can_replace']:
                decision = None
                match['state'] = 'review'
            if match['answer_conflict'] and decision is None:
                match['state'] = 'review'
            match['decision'] = decision
            if decision in ('different', 'incoming'): match['state'] = 'different'
            elif decision in ('duplicate', 'neither'): match['state'] = 'duplicate'
            if decision == 'incoming' and match['bank_question_id']:
                q['replace_question_id'] = match['bank_question_id']
        state = 'duplicate' if any(m['state']=='duplicate' for m in matches) else 'review' if any(m['state']=='review' for m in matches) else 'new'
        q['duplicate'] = dict(state=state,matches=matches,reason=matches[0]['reason'] if matches else 'Chưa phát hiện câu trùng.')
        # Duplicate representatives are not used as an independent new target.
        if state != 'duplicate':
            candidate = candidate_record(q,d)
            candidates.append(candidate)
            if d['key']: exact[d['key']].append(candidate)
    # Pair decisions are applied after scanning so choosing a later file copy
    # also suppresses its earlier representative, without deleting source data.
    by_uid = {q['import_uid']: q for q in questions}
    for q in questions:
        for match in q['duplicate']['matches']:
            if match.get('decision') in ('incoming', 'neither') and match['reference'].startswith('file:'):
                peer = by_uid.get(match['reference'][5:])
                if peer and not peer.get('saved_question_id'):
                    peer['duplicate']['state'] = 'duplicate'
                    peer['duplicate']['reason'] = 'Đã bỏ qua theo lựa chọn đối chiếu của giáo viên.'
    counts = {state:sum(q['duplicate']['state']==state for q in questions) for state in ('new','duplicate','review','imported')}
    counts['eligible'] = sum(q['duplicate']['state']=='new' and q.get('status')!='error' for q in questions)
    counts['error'] = sum(q['duplicate']['state']=='new' and q.get('status')=='error' for q in questions)
    counts['total'] = len(questions)
    counts['revision'] = revision(session, questions, actor=actor, bank=bank)
    counts['bank_id'] = session.bank_id
    counts['bank_name'] = session.bank.name if session.bank else None
    counts['skipped_labels'] = [q['source_label'] for q in questions if q['duplicate']['state']=='duplicate']
    return counts
