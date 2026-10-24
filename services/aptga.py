"""APTGA v1 pure allocation rules; see docs/APTGA_SPEC.md for assumptions."""
import math
from collections import defaultdict

VERSION = 'aptga-v1'
LEVELS = ('nhan_biet', 'thong_hieu', 'van_dung', 'van_dung_cao')
BASE = dict(zip(LEVELS, (.4, .3, .2, .1)))
FLOOR = dict(zip(LEVELS, (.25, .25, .2, .1)))
CEILING = dict(zip(LEVELS, (.4, .35, .4, .25)))


def apportion(total, weights):
    total_weight = sum(max(0, value) for value in weights.values())
    if not total_weight:
        return {key: 0 for key in weights}
    raw = {key: total * max(0, value) / total_weight for key, value in weights.items()}
    result = {key: math.floor(value) for key, value in raw.items()}
    order = sorted(raw, key=lambda key: (-(raw[key] - result[key]), list(weights).index(key)))
    for key in order[:total - sum(result.values())]:
        result[key] += 1
    return result


def summarize(rows):
    if not rows:
        return dict(mastery=None, sufficiency=0., sufficient=False, sample_count=0,
                    distinct_count=0, session_count=0, repetition=0., state='Chưa đủ dữ liệu')
    sessions = defaultdict(list)
    for row in rows:
        sessions[row.submission_id].append(row)
    ordered = sorted(sessions, key=lambda key: (
        max(row.occurred_at for row in sessions[key]), key), reverse=True)
    numerator = denominator = 0.
    for age, key in enumerate(ordered):
        weight = .8 ** age
        for row in sessions[key]:
            effective = weight * getattr(row, "evidence_weight", 1.)
            numerator += effective * max(0., min(1., row.normalized_score))
            denominator += effective
    distinct = len({row.question_content_hash or
                    (('bank', row.bank_question_id) if row.bank_question_id else ('exam', row.exam_question_id))
                    for row in rows})
    sufficiency = min(1., distinct / 5) * min(1., len(sessions) / 2)
    mastery = numerator / denominator
    recent = ordered[:3]
    session_scores = [sum(r.normalized_score * getattr(r, "evidence_weight", 1.) for r in sessions[key]) /
                      sum(getattr(r, "evidence_weight", 1.) for r in sessions[key]) for key in recent]
    repetition = sum(value < .7 for value in session_scores) / len(recent)
    state = ('Vững' if mastery >= .85 else 'Đạt' if mastery >= .7 else
             'Cần củng cố' if mastery >= .5 else 'Yếu')
    return dict(mastery=mastery, sufficiency=sufficiency, sufficient=sufficiency == 1,
                sample_count=len(rows), distinct_count=distinct, session_count=len(sessions),
                repetition=repetition, state=state if sufficiency == 1 else 'Chưa đủ dữ liệu')


def ready_to_advance(rows):
    cell = summarize(rows)
    sessions = sorted({r.submission_id for r in rows},
                      key=lambda key: max(r.occurred_at for r in rows if r.submission_id == key), reverse=True)
    return bool(cell['sufficient'] and cell['mastery'] >= .85 and len(sessions) >= 2 and all(
        summarize([r for r in rows if r.submission_id == key])['mastery'] >= .8 for key in sessions[:2]))


def matrix(rows):
    groups = defaultdict(list)
    for row in rows:
        if row.curriculum_code and row.cognitive_level in LEVELS:
            groups[(row.curriculum_code, row.cognitive_level)].append(row)
    return {f'{skill}||{level}': summarize(items) for (skill, level), items in groups.items()}


def priority(cell):
    deficit = max(0., .7 - (cell['mastery'] if cell['mastery'] is not None else .7)) / .7
    parts = dict(deficit=deficit * cell['sufficiency'], repetition=cell['repetition'],
                 uncertainty=1 - cell['sufficiency'])
    return .6 * parts['deficit'] + .25 * parts['repetition'] + .15 * parts['uncertainty'], parts


def allocate(total, level_profile, allowed=None):
    allowed = [level for level in LEVELS if allowed is None or level in allowed]
    if not allowed:
        return {}, ['Không có mức nhận thức được phép.']
    quota = apportion(total, {level: BASE[level] for level in allowed})
    warnings = []
    if len(allowed) != 4:
        return quota, ['Giới hạn giáo viên thay thế cấu trúc đủ bốn mức.']
    lower = {level: math.ceil(total * FLOOR[level]) for level in allowed}
    upper = {level: math.floor(total * CEILING[level]) for level in allowed}
    if sum(lower.values()) > total or sum(upper.values()) < total or any(lower[l] > upper[l] for l in allowed):
        return quota, ['Số câu không đủ để giữ sàn/trần phần trăm; dùng cấu trúc nền làm tròn.']
    # Repair rounding before adaptation, with a stable level order.
    for level in allowed:
        while quota[level] < lower[level]:
            donors = [l for l in allowed if quota[l] > lower[l]]
            donor = max(donors, key=lambda l: quota[l] - lower[l])
            quota[donor] -= 1
            quota[level] += 1
    need = {l: max(0., .7 - level_profile[l]['mastery']) / .7
            if level_profile.get(l, {}).get('sufficient') else 0. for l in allowed}
    added = defaultdict(int)
    for _ in range(math.floor(.2 * total)):
        donors = [l for l in allowed if level_profile.get(l, {}).get('sufficient')
                  and level_profile[l]['mastery'] >= .7 and quota[l] > lower[l]]
        receivers = [l for l in allowed if need[l] > 0 and quota[l] < upper[l]]
        if not donors or not receivers:
            break
        donor = max(donors, key=lambda l: quota[l] - lower[l])
        receiver = max(receivers, key=lambda l: need[l] / (added[l] + 1))
        quota[donor] -= 1
        quota[receiver] += 1
        added[receiver] += 1
    return quota, warnings
