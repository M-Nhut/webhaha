"""Bounded constraint search for the fixed paper, not a greedy partial paper.

Exact type/level/knowledge targets, deterministic ranking, and explicit failure
on search-budget exhaustion. Does not claim global score optimality.
"""
from collections import defaultdict

from services import aptga
from services.practice_blueprint import SKILLS, LEVELS, TYPE_QUOTAS, TOTAL


def skill_targets(cells, offset=0):
    targets = dict.fromkeys(SKILLS, 1)
    order = list(SKILLS[offset % 8:] + SKILLS[:offset % 8])
    weights = {skill: 1 + 3 * max((aptga.priority(cell)[0] for key, cell in cells.items()
                                 if key.startswith(skill + "||")), default=0) for skill in SKILLS}
    for _ in range(TOTAL - len(SKILLS)):
        skill = max((s for s in order if targets[s] < 5), key=lambda s: weights[s] / targets[s])
        targets[skill] += 1
    return targets


def progression(rows, quotas):
    """At most one probe per stable cell, within global floors/caps and 4 moves."""
    result, moves = dict(quotas), []
    baseline, _ = aptga.allocate(TOTAL, {})
    cells = defaultdict(list)
    for row in rows:
        cells[(row.curriculum_code, row.cognitive_level)].append(row)
    for (skill, level), values in sorted(cells.items()):
        if level not in LEVELS[:-1] or not aptga.ready_to_advance(values):
            continue
        target = LEVELS[LEVELS.index(level) + 1]
        # Unknown next level is an opportunity to probe, never assumed mastered.
        if aptga.summarize(cells.get((skill, target), []))["sufficient"]:
            continue
        import math
        proposed = dict(result)
        proposed[level] -= 1
        proposed[target] += 1
        if (proposed[level] >= math.ceil(TOTAL * aptga.FLOOR[level]) and
                proposed[target] <= math.floor(TOTAL * aptga.CEILING[target]) and
                sum(max(0, proposed[l] - baseline[l]) for l in LEVELS) <= 4):
            result = proposed
            moves.append(dict(skill=skill, source=level, target=target))
    return result, moves


def select_fixed(ranked, level_targets, knowledge_targets, max_states=30000):
    groups = defaultdict(list)
    for item in ranked:
        q = item["question"]
        groups[(q.question_type, q.difficulty_level, item["skill"])].append(item)
    targets = [dict(TYPE_QUOTAS), dict(level_targets), dict(knowledge_targets)]

    def fingerprint(item):
        """Return the immutable content identity used by the no-duplicate rule."""
        return item.get("fingerprint") or ("id", item["question"].id)

    failures = []
    for dim, label in enumerate(("dạng câu", "mức nhận thức", "kiến thức")):
        for key, count in targets[dim].items():
            # A duplicate content hash is one usable item, even when it was
            # imported into several groups.  This is only a necessary
            # capacity check; the bounded search below checks intersections.
            capacity = len({fingerprint(item) for group, items in groups.items()
                            if group[dim] == key for item in items})
            if capacity < count:
                failures.append(dict(dimension=label, key=key, required=count, available=capacity, missing=count-capacity))
    if failures:
        return [], failures, "insufficient_candidates"
    # Keep the best-ranked representative for an identical fingerprint within
    # one group.  Identical content in different groups remains a real branch:
    # choosing it for one type/level/skill consumes it for all groups.
    for key, items in list(groups.items()):
        representatives = {}
        for item in items:
            representatives.setdefault(fingerprint(item), item)
        groups[key] = list(representatives.values())

    keys = tuple(groups)
    selected, used_hashes, failed = [], set(), set()
    states = 0
    exhausted = False

    def item_order(choice):
        key, item, fp = choice
        components = item.get("components") or {}
        return (item.get("exposure_tier", 0), item.get("exposure_count", 0),
                -float(item.get("score", 0) or 0),
                -float(components.get("teacher", 0) or 0),
                item["question"].id, repr(fp), key)

    def search():
        nonlocal states, exhausted
        states += 1
        if states > max_states:
            exhausted = True
            return False
        if len(selected) == TOTAL:
            return True
        # A selected fingerprint removes every duplicate copy, but does not
        # force the search to consume a prefix of a group.  That matters when
        # the top-ranked copy collides with another mandatory group.
        available = []
        seen_group_fingerprints = set()
        for key in keys:
            if not all(targets[d].get(key[d], 0) > 0 for d in range(3)):
                continue
            for item in groups[key]:
                fp = fingerprint(item)
                if fp in used_hashes or (key, fp) in seen_group_fingerprints:
                    continue
                seen_group_fingerprints.add((key, fp))
                available.append((key, item, fp))

        constraints = []
        for dim in range(3):
            for value, need in targets[dim].items():
                if not need:
                    continue
                matches = [choice for choice in available if choice[0][dim] == value]
                capacity = len({choice[2] for choice in matches})
                if capacity < need:
                    return False
                constraints.append((capacity / need, capacity, dim, value, matches))
        # The remaining targets plus used content fully describe the state:
        # no prefix/count memo can be reused after a different hash collision.
        state = (tuple(tuple(sorted(target.items())) for target in targets),
                 tuple(sorted(map(repr, used_hashes))))
        if state in failed:
            return False
        _ratio, _capacity, constrained_dim, constrained_value, choices = min(
            constraints, key=lambda entry: entry[:3]
        )
        # Balance knowledge coverage before spending remaining slots on weaknesses.
        choices.sort(key=item_order)
        for key, item, fp in choices:
            used_hashes.add(fp)
            selected.append(item)
            for dim in range(3):
                targets[dim][key[dim]] -= 1
            if search():
                return True
            for dim in range(3):
                targets[dim][key[dim]] += 1
            selected.pop()
            used_hashes.remove(fp)
            if exhausted:
                break
        failed.add(state)
        return False

    if not search():
        return [], [], "search_limit" if exhausted else "incompatible_intersections"
    selected.sort(key=lambda item: (list(TYPE_QUOTAS).index(item["question"].question_type), item["question"].id))
    return selected, [], "ready"
