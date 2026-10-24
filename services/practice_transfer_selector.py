"""Bounded skill-quota recovery with immutable level and question-type totals.

Skills are preferences here; cover every skill available in the approved pool
and never exceed five questions per skill. No question metadata is relabelled.
"""
from collections import Counter, defaultdict

from services import aptga
from services.practice_blueprint import LEVELS, SKILLS, TOTAL, TYPE_QUOTAS
from services.practice_source_inventory import same_level_alternatives


def fingerprint(item):
    return item.get("fingerprint") or ("id", item["question"].id)


def item_order(item):
    return (item.get("exposure_tier", 0), item.get("exposure_count", 0),
            -float(item.get("score", 0) or 0),
            -float((item.get("components") or {}).get("teacher", 0) or 0),
            item["question"].id, repr(fingerprint(item)))


def select_same_level(ranked, levels, skills, *, cells=None, max_states=3200, rng=None):
    """Keep exact type/level quotas, soften skill totals only after strict failure.

    With an RNG, shuffle alternative skills within each type/level group.
    Without one, use deterministic mastery priority for offline evaluations.
    Empty skills have no coverage floor. Others retain at least one question.
    Neither policy guarantees a minimum number of quota edits.
    """
    if sum(levels.values()) != TOTAL or sum(skills.values()) != TOTAL:
        raise ValueError("Quota mức và dạng phải có tổng 22 câu.")
    ordered = sorted(ranked, key=item_order)
    # Same content may have genuinely different labels; retain those branches.
    unique = {}
    for x in ordered:
        q = x["question"]
        key = (q.question_type, q.difficulty_level, x["skill"], fingerprint(x))
        unique.setdefault(key, x)
    pool = list(unique.values())
    # Shuffle skills, not individual questions: a large skill bank should not
    # receive more lottery entries merely because it contains more questions.
    random_order = {}
    if rng is not None:
        groups = defaultdict(set)
        for x in pool:
            q = x["question"]
            groups[(q.question_type, q.difficulty_level)].add(x["skill"])
        for group, values in sorted(groups.items()):
            names = sorted(values)
            rng.shuffle(names)
            random_order.update({(*group, skill): index for index, skill in enumerate(names)})
    required_skills = {x["skill"] for x in pool}
    type_left, level_left = dict(TYPE_QUOTAS), dict(levels)
    skill_count = Counter()
    selected, used, failed = [], set(), set()
    states, exhausted = 0, False
    priorities = {(s, l): aptga.priority((cells or {}).get(f"{s}||{l}", aptga.summarize([])))[0]
                  for s in SKILLS for l in LEVELS}

    def search():
        nonlocal states, exhausted
        states += 1
        if states > max_states:
            exhausted = True
            return False
        if len(selected) == TOTAL:
            return all(skill_count[s] >= 1 for s in required_skills)
        available = [x for x in pool if fingerprint(x) not in used
                     and type_left[x["question"].question_type] > 0
                     and level_left[x["question"].difficulty_level] > 0
                     and skill_count[x["skill"]] < 5]
        # Necessary type/level intersection bounds avoid exploring impossible
        # banks where, for example, every single item is NB but NB quota is lower.
        for kind, need in type_left.items():
            capacity = sum(min(level_left[level], len({fingerprint(x) for x in available
                           if x["question"].question_type == kind and x["question"].difficulty_level == level}))
                           for level in LEVELS)
            if capacity < need:
                return False
        for level, need in level_left.items():
            capacity = sum(min(type_left[kind], len({fingerprint(x) for x in available
                           if x["question"].question_type == kind and x["question"].difficulty_level == level}))
                           for kind in TYPE_QUOTAS)
            if capacity < need:
                return False
        constraints = []
        for dimension, remaining, getter in (
            (0, type_left, lambda x: x["question"].question_type),
            (1, level_left, lambda x: x["question"].difficulty_level),
            (2, {s: int(skill_count[s] == 0) for s in required_skills}, lambda x: x["skill"]),
        ):
            for key, need in sorted(remaining.items()):
                if not need:
                    continue
                matches = [x for x in available if getter(x) == key]
                capacity = len({fingerprint(x) for x in matches})
                if capacity < need:
                    return False
                constraints.append((capacity / need, capacity, dimension, key, matches))
        if sum(skill_count[s] == 0 for s in required_skills) > TOTAL-len(selected):
            return False
        if len({fingerprint(x) for x in available}) < TOTAL-len(selected):
            return False
        key = (tuple(type_left[k] for k in TYPE_QUOTAS),
               tuple(level_left[k] for k in LEVELS), tuple(skill_count[s] for s in SKILLS),
               tuple(sorted(repr(fp) for fp in used)))
        if key in failed:
            return False
        choices = min(constraints, key=lambda c: c[:4])[4]
        choices.sort(key=lambda x: (
            skill_count[x["skill"]] >= skills.get(x["skill"], 0),
            (random_order[(x["question"].question_type, x["question"].difficulty_level, x["skill"])]
             if rng is not None else -priorities[(x["skill"], x["question"].difficulty_level)]),
            item_order(x)))
        for x in choices:
            q, fp, skill = x["question"], fingerprint(x), x["skill"]
            selected.append(x)
            used.add(fp)
            type_left[q.question_type] -= 1
            level_left[q.difficulty_level] -= 1
            skill_count[skill] += 1
            if search():
                return True
            skill_count[skill] -= 1
            level_left[q.difficulty_level] += 1
            type_left[q.question_type] += 1
            used.remove(fp)
            selected.pop()
            if exhausted:
                break
        failed.add(key)
        return False

    if not search():
        return [], "search_limit" if exhausted else "incompatible_intersections"
    selected.sort(key=lambda x: (list(TYPE_QUOTAS).index(x["question"].question_type), x["question"].id))
    return selected, "ready"


def explain_transfers(selected, ranked, skills, *, cells=None, max_exposure_tier=0):
    """Attribute net skill-quota changes to actual replacement questions.

    There was no original skill/level cell quota or original source question.
    The level/type describes the actual added target question, not an invented
    old question. Independent counts do not establish full-paper feasibility.
    """
    actual = Counter(x["skill"] for x in selected)
    deficits = {s: max(0, skills[s]-actual[s]) for s in SKILLS}
    extras = {}
    for s in SKILLS:
        count = max(0, actual[s]-skills[s])
        if count:
            # Mark the best-ranked extra questions as representatives of the shift.
            extras[s] = sorted((x for x in selected if x["skill"] == s), key=item_order)[:count]
    remaining = [x for values in extras.values() for x in values]
    records = []
    available = defaultdict(set)
    for x in ranked:
        q = x["question"]
        available[(x["skill"], q.difficulty_level, q.question_type)].add(fingerprint(x))
    for source in SKILLS:
        for _ in range(deficits[source]):
            candidates = []
            for x in remaining:
                q = x["question"]
                alternatives = same_level_alternatives(
                    ranked, source, q.difficulty_level, q.question_type,
                    cells=cells, max_exposure_tier=max_exposure_tier)
                priority = next(row["priority"] for row in alternatives if row["skill"] == x["skill"])
                source_count = len(available[(source, q.difficulty_level, q.question_type)])
                candidates.append((source_count != 0, -priority, item_order(x), x, source_count))
            _, _, _, chosen, source_count = min(candidates, key=lambda c: c[:3])
            remaining.remove(chosen)
            q = chosen["question"]
            records.append(dict(source_skill=source, target_skill=chosen["skill"],
                                level=q.difficulty_level, question_type=q.question_type,
                                question_id=q.id, count=1, source_available=source_count,
                                reason="source_cell_empty" if source_count == 0 else "initial_targets_unresolved"))
    return records
