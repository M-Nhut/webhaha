"""Facets built only from the caller's already authorized question set."""
from collections import Counter
from services.practice_blueprint import LEVELS, TYPE_LABELS
from services.question_policy import bank_question_ready
from services.bank_curriculum import bank_readiness_error, category_name

LEVEL_LABELS = ('Nhận biết', 'Thông hiểu', 'Vận dụng', 'Vận dụng cao')


def knowledge_overview(catalog, questions, *, research=True):
    """Index each question once; validate at most once per represented cell."""
    sections = []
    nodes = list(catalog)
    known_ids = {n['id'] for n in catalog}
    totals, counts, ready = Counter(), Counter(), Counter()
    unclassified = False
    for q in questions:
        if research:
            key = q.curriculum_node_id if q.curriculum_node_id in known_ids else 0
            unclassified = unclassified or key == 0
        else:
            key = category_name(q)
        totals[key] += 1
        if q.difficulty_level not in LEVELS or q.question_type not in TYPE_LABELS:
            continue
        cell_key = (key, q.difficulty_level, q.question_type)
        counts[cell_key] += 1
        if not q.adaptive_excluded and bank_question_ready(q) and bank_readiness_error(q, research=research) is None:
            ready[cell_key] += 1
    if research and unclassified:
        nodes.append({'id': 0, 'category': '', 'category_name': 'Chưa gắn dạng kiến thức hiện hành'})
    for node in nodes:
        key = node['id'] if research else node['category_name']
        section = dict(node, count=totals[key], levels=[])
        for level, label in zip(LEVELS, LEVEL_LABELS):
            cells = []
            for kind, type_label in TYPE_LABELS.items():
                cell_key = (key, level, kind)
                cells.append({'kind': kind, 'label': type_label, 'count': counts[cell_key], 'ready': ready[cell_key]})
            section['levels'].append({'key': level, 'label': label, 'cells': cells})
        sections.append(section)
    return sections
