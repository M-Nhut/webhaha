"""Same-level recovery tests with synthetic approved pools, no DB/AI."""
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace
import json

from services.practice_blueprint import LEVELS, SKILLS, TYPE_QUOTAS
from services.practice_recovery import select_resilient
from services.practice_selector import select_fixed
from services.practice_transfer_selector import select_same_level

LEVEL_TARGETS = dict(zip(LEVELS, (7, 7, 5, 3)))


def make_pool():
    kinds = [k for k, n in TYPE_QUOTAS.items() for _ in range(n)]
    levels = [l for l, n in LEVEL_TARGETS.items() for _ in range(n)]
    return [dict(question=SimpleNamespace(id=i+1, question_type=k, difficulty_level=l),
                 skill=SKILLS[i % 8], fingerprint=f"q{i}", score=0,
                 exposure_tier=0, exposure_count=0)
            for i, (k, l) in enumerate(zip(kinds, levels))]


def targets(pool):
    counts = Counter(x['skill'] for x in pool)
    return {s: counts[s] for s in SKILLS}


def assert_contract(selected, audit):
    assert len(selected) == 22
    assert Counter(x['question'].question_type for x in selected) == TYPE_QUOTAS
    assert Counter(x['question'].difficulty_level for x in selected) == LEVEL_TARGETS
    assert len({x['fingerprint'] for x in selected}) == 22
    assert max(Counter(x['skill'] for x in selected).values()) <= 5
    assert audit['effective_level_targets'] == LEVEL_TARGETS
    assert audit['level_targets_preserved']
    assert len(audit['skill_transfers']) == audit['quota_changes']
    json.dumps(audit)


def test_full_source_keeps_original_strict_selection():
    pool = make_pool()
    skills = targets(pool)
    strict = select_fixed(pool, LEVEL_TARGETS, skills)[0]
    selected, shortage, status, audit = select_resilient(pool, LEVEL_TARGETS, skills)
    assert status == 'ready' and not shortage
    assert [x['question'].id for x in selected] == [x['question'].id for x in strict]
    assert audit['recovery_stage'] == 'fresh' and not audit['skill_transfers']
    assert_contract(selected, audit)


def test_skill_shift_preserves_every_level_and_records_real_question():
    pool = make_pool()
    skills = targets(pool)
    skills[SKILLS[0]] += 1
    skills[SKILLS[1]] -= 1
    selected, _, status, audit = select_resilient(pool, LEVEL_TARGETS, skills)
    assert status == 'ready'
    assert audit['recovery_stage'] == 'same_level_skill_transfer'
    assert audit['quota_changes'] == 1
    change = audit['skill_transfers'][0]
    q = next(x for x in selected if x['question'].id == change['question_id'])
    assert change['source_skill'] == SKILLS[0] and change['target_skill'] == SKILLS[1]
    assert change['level'] == q['question'].difficulty_level
    assert change['question_type'] == q['question'].question_type
    assert q['skill'] == SKILLS[1]
    assert_contract(selected, audit)


def test_entire_missing_skill_is_transferred_more_than_two_slots():
    pool = make_pool()
    original = targets(pool)
    for x in pool:
        if x['skill'] == SKILLS[0]:
            x['skill'] = SKILLS[6] if x['question'].id % 2 else SKILLS[7]
    selected, _, status, audit = select_resilient(pool, LEVEL_TARGETS, original)
    assert status == 'ready'
    assert audit['unavailable_skills'] == [SKILLS[0]]
    assert audit['covered_skill_count'] == 7
    assert audit['quota_changes'] == original[SKILLS[0]] == 3
    assert all(x['source_skill'] == SKILLS[0] and x['source_available'] == 0
               for x in audit['skill_transfers'])
    assert_contract(selected, audit)


def test_fresh_transfer_is_tried_before_exact_quota_repeat():
    pool = make_pool()
    original = targets(pool)
    q = deepcopy(pool[0])
    q['question'].id = 99
    q['fingerprint'] = 'fresh-other'
    q['skill'] = SKILLS[1]
    pool[0]['exposure_tier'] = 3
    pool[0]['exposure_count'] = 1
    pool.append(q)
    selected, _, status, audit = select_resilient(pool, LEVEL_TARGETS, original)
    assert status == 'ready' and audit['exposure_stage'] == 'fresh'
    assert audit['quota_changes'] == 1
    assert all(x['exposure_tier'] == 0 for x in selected)
    assert_contract(selected, audit)


def test_cooldown_does_not_make_a_skill_entirely_unavailable():
    pool = make_pool()
    original = targets(pool)
    for x in pool:
        if x['skill'] == SKILLS[0]:
            x['exposure_tier'] = 3
            x['exposure_count'] = 1
    # Add enough fresh alternatives; still retain coverage of the real skill.
    for x in list(pool):
        if x['skill'] == SKILLS[0]:
            new = deepcopy(x)
            new['question'].id += 100
            new.update(skill=SKILLS[7], fingerprint=f"new-{new['question'].id}", exposure_tier=0, exposure_count=0)
            pool.append(new)
    selected, _, status, audit = select_resilient(pool, LEVEL_TARGETS, original)
    assert status == 'ready' and not audit['unavailable_skills']
    assert any(x['skill'] == SKILLS[0] for x in selected)
    assert audit['exposure_stage'] == 'immediate_review'
    assert_contract(selected, audit)


def test_exact_high_level_shortage_never_downgrades_even_above_old_floor():
    pool = make_pool()
    # Five VDC required but only three exist; v2 floor check alone would pass.
    levels = dict(LEVEL_TARGETS, van_dung=3, van_dung_cao=5)
    selected, shortages, status, audit = select_resilient(pool, levels, targets(pool))
    assert not selected and status == 'insufficient_candidates'
    assert any(x['key'] == 'van_dung_cao' and x['missing'] == 2 for x in shortages)
    assert audit['effective_level_targets'] == levels
    assert not audit['skill_transfers']


def test_whole_level_missing_and_duplicate_content_cannot_be_substituted():
    pool = make_pool()
    skills = targets(pool)
    for x in pool:
        if x['question'].difficulty_level == LEVELS[-1]:
            x['question'].difficulty_level = LEVELS[-2]
    selected, shortages, status, _ = select_resilient(pool, LEVEL_TARGETS, skills)
    assert not selected and status == 'insufficient_candidates'
    assert any(x['key'] == LEVELS[-1] for x in shortages)
    pool = make_pool()
    for x in pool:
        x['fingerprint'] = 'same-content'
    assert select_resilient(pool, LEVEL_TARGETS, skills)[2] == 'insufficient_candidates'


def test_type_shortage_is_not_repaired_using_another_type():
    pool = make_pool()
    skills = targets(pool)
    pool = [x for x in pool if x['question'].question_type != 'true_false']
    selected, shortages, status, _ = select_resilient(pool, LEVEL_TARGETS, skills)
    assert not selected and status == 'insufficient_candidates'
    assert any(x['key'] == 'true_false' and x['missing'] == 4 for x in shortages)


def test_search_limit_is_not_reported_as_impossible_bank():
    pool = make_pool()
    assert select_same_level(pool, LEVEL_TARGETS, targets(pool), max_states=1)[1] == 'search_limit'


def test_input_order_is_deterministic_and_labels_targets_are_unchanged():
    pool = make_pool()
    skills = targets(pool)
    skills[SKILLS[0]] += 1
    skills[SKILLS[1]] -= 1
    before = deepcopy(pool), dict(skills), dict(LEVEL_TARGETS)
    first = select_resilient(pool, LEVEL_TARGETS, skills)
    second = select_resilient(pool[::-1], LEVEL_TARGETS, skills)
    assert [x['question'].id for x in first[0]] == [x['question'].id for x in second[0]]
    assert first[3]['skill_transfers'] == second[3]['skill_transfers']
    assert pool == before[0] and skills == before[1] and LEVEL_TARGETS == before[2]

def test_receiving_skill_priority_guides_extra_questions_at_the_same_level():
    from services import aptga
    pool = []
    i = 0
    for skill in SKILLS[1:]:
        for level in LEVELS:
            for kind in TYPE_QUOTAS:
                i += 1
                pool.append(dict(question=SimpleNamespace(id=i, question_type=kind, difficulty_level=level),
                                 skill=skill, fingerprint=f'p{i}', score=0, exposure_tier=0))
    original = {s: 3 if n < 6 else 2 for n, s in enumerate(SKILLS)}
    weak = aptga.summarize([])
    weak.update(mastery=0, sufficient=True, sufficiency=1, repetition=1)
    cells = {f'{SKILLS[1]}||{level}': weak for level in LEVELS}
    selected, _, status, audit = select_resilient(pool, LEVEL_TARGETS, original, cells=cells)
    assert status == 'ready'
    counts = Counter(x['skill'] for x in selected)
    assert counts[SKILLS[1]] == 5
    assert sum(x['target_skill'] == SKILLS[1] for x in audit['skill_transfers']) == 2
    assert_contract(selected, audit)


def test_conflicting_type_level_intersections_are_not_a_level_downgrade():
    pool = []
    specs = [('single', LEVELS[0], 12), ('true_false', LEVELS[1], 14),
             ('short_answer', LEVELS[2], 10), ('short_answer', LEVELS[3], 5)]
    for kind, level, count in specs:
        for _ in range(count):
            i = len(pool)
            pool.append(dict(question=SimpleNamespace(id=i, question_type=kind, difficulty_level=level),
                             skill=SKILLS[i % 8], fingerprint=f'c{i}', score=0))
    selected, status = select_same_level(pool, LEVEL_TARGETS,
                                        {s: 3 if i < 6 else 2 for i, s in enumerate(SKILLS)})
    assert not selected and status == 'incompatible_intersections'

def test_cross_bank_duplicates_remain_unique_during_skill_transfer():
    pool = make_pool()
    original = targets(pool)
    pool[1]['fingerprint'] = pool[0]['fingerprint']
    backup = deepcopy(pool[0])
    backup['question'].id = 99
    backup.update(skill=SKILLS[2], fingerprint='unique-backup')
    pool.append(backup)
    selected, _, status, audit = select_resilient(pool, LEVEL_TARGETS, original)
    assert status == 'ready' and audit['quota_changes'] == 1
    assert_contract(selected, audit)


def test_per_skill_cap_blocks_a_paper_when_only_four_skills_have_sources():
    pool = make_pool()
    original = targets(pool)
    for i, x in enumerate(pool):
        x['skill'] = SKILLS[i % 4]
    selected, shortages, status, _ = select_resilient(pool, LEVEL_TARGETS, original)
    assert not selected and status == 'insufficient_candidates'
    assert any(x['dimension'] == 'giới hạn số câu theo dạng' for x in shortages)
