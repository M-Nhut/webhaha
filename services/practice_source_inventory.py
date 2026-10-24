"""Read-only candidate inventory for same-level skill transfer (phase 1).

Input is the approved, scoped, ranked pool from AdaptiveEngine, not raw bank
rows. This module neither selects a paper nor alters targets or question labels.
"""
from collections import defaultdict

from services import aptga
from services.practice_blueprint import LEVELS, SKILLS, TYPE_QUOTAS

VERSION = "practice-source-inventory-v1"
EXPOSURE_STAGES = ("fresh", "spaced_review", "recent_review", "immediate_review")


def _fingerprint(item):
    return item.get("fingerprint") or ("id", item["question"].id)


def _usable(item):
    q = item["question"]
    return (item.get("skill") in SKILLS and q.difficulty_level in LEVELS
            and q.question_type in TYPE_QUOTAS
            and item.get("exposure_tier", 0) in range(4))


def _rank(item):
    """Same candidate order as select_fixed; profile priority ranks skills first."""
    return (item.get("exposure_tier", 0), item.get("exposure_count", 0),
            -float(item.get("score", 0) or 0),
            -float((item.get("components") or {}).get("teacher", 0) or 0),
            item["question"].id, repr(_fingerprint(item)))


def same_level_alternatives(ranked, source_skill, level, question_type, *,
                            cells=None, max_exposure_tier=0,
                            excluded_fingerprints=()):
    """Preview other skills at exactly the same level AND question type.

    Counts are independent alternatives, not additive capacity or a promise
    that the whole paper can be assembled. Already-used content is excluded.
    No source/target label is ever changed on a question.
    """
    if source_skill not in SKILLS or level not in LEVELS or question_type not in TYPE_QUOTAS:
        raise ValueError("Dạng, mức độ hoặc hình thức câu hỏi không hợp lệ.")
    if max_exposure_tier not in range(4):
        raise ValueError("Tầng tiếp xúc phải từ 0 đến 3.")
    excluded = set(excluded_fingerprints)
    grouped = defaultdict(list)
    for item in ranked:
        q = item["question"]
        if (_usable(item) and item["skill"] != source_skill
                and q.difficulty_level == level and q.question_type == question_type
                and item.get("exposure_tier", 0) <= max_exposure_tier
                and _fingerprint(item) not in excluded):
            grouped[item["skill"]].append(item)
    result = []
    for skill, items in grouped.items():
        unique = {}
        for item in sorted(items, key=_rank):
            unique.setdefault(_fingerprint(item), item)
        best = next(iter(unique.values()))
        cell = (cells or {}).get(f"{skill}||{level}", aptga.summarize([]))
        priority = aptga.priority(cell)[0]
        result.append(dict(skill=skill, level=level, question_type=question_type,
                           available=len(unique), priority=priority,
                           question_ids=[x["question"].id for x in unique.values()]))
    result.sort(key=lambda row: (-row["priority"],
                                _rank(next(x for x in grouped[row["skill"]]
                                           if x["question"].id == row["question_ids"][0])),
                                SKILLS.index(row["skill"])))
    return result


def build_source_inventory(ranked, *, level_targets=None, skill_targets=None):
    """Count unique content at each cumulative exposure tier, including zeros.

    A zero skill/level/type cell is an availability gap, not a quota shortage:
    today's selector uses marginal skill and level quotas, not cell quotas.
    Shared fingerprints may appear in several cells; counts cannot be summed.
    """
    usable = [item for item in ranked if _usable(item)]
    by_cell = defaultdict(list)
    for item in usable:
        q = item["question"]
        by_cell[(item["skill"], q.difficulty_level, q.question_type)].append(item)

    def counts(items):
        return {stage: len({_fingerprint(x) for x in items
                            if x.get("exposure_tier", 0) <= tier})
                for tier, stage in enumerate(EXPOSURE_STAGES)}

    matrix, empty, review_only = [], [], []
    for skill in SKILLS:
        for level in LEVELS:
            for kind in TYPE_QUOTAS:
                available = counts(by_cell[(skill, level, kind)])
                row = dict(skill=skill, level=level, question_type=kind,
                           available=available)
                matrix.append(row)
                ref = dict(skill=skill, level=level, question_type=kind)
                if not available["immediate_review"]:
                    empty.append(ref)
                elif not available["fresh"]:
                    review_only.append(ref)
    shortages = []
    for dimension, targets, getter in (
        ("level", level_targets or {}, lambda x: x["question"].difficulty_level),
        ("skill", skill_targets or {}, lambda x: x["skill"]),
        ("question_type", TYPE_QUOTAS, lambda x: x["question"].question_type),
    ):
        for key, required in targets.items():
            available = len({_fingerprint(x) for x in usable if getter(x) == key})
            if available < required:
                shortages.append(dict(dimension=dimension, key=key, required=required,
                                      available=available, missing=required-available))
    return dict(version=VERSION, mode="observe_only", candidate_rows=len(usable),
                ignored_rows=len(ranked)-len(usable),
                unique_content=counts(usable),
                duplicate_rows=len(usable)-counts(usable)["immediate_review"],
                cells=matrix, empty_cells=empty, review_only_cells=review_only,
                marginal_shortages=shortages,
                cell_targets_assigned=False, counts_are_additive=False,
                scope="approved_ranked_pool", full_paper_feasibility_checked=False)
