"""Practice recovery changes skill totals only; level/type targets stay exact."""
from collections import Counter

from services.practice_blueprint import LEVELS, SKILLS, TOTAL, TYPE_QUOTAS
from services.practice_selector import select_fixed
from services.practice_transfer_selector import explain_transfers, fingerprint, select_same_level

VERSION = "aptga-recovery-v3-same-level"
STAGES = ("fresh", "spaced_review", "recent_review", "immediate_review")


def select_resilient(ranked, levels, skills, max_variants=80, *, cells=None, rng=None):
    attempts = []
    # Retain the old public budget argument, now bounding states per soft search.
    max_states = max(1, max_variants) * 40
    searched_out = False
    missing_skills = [s for s in SKILLS if not any(x["skill"] == s for x in ranked)]

    def audit(stage, selected=(), transfers=(), exposure_stage=None):
        actual = Counter(x["skill"] for x in selected)
        reused = [x for x in selected if x.get("exposure_count", 0)]
        return dict(algorithm_version=VERSION, recovery_stage=stage,
                    exposure_stage=exposure_stage, attempts=attempts,
                    effective_level_targets=dict(levels),
                    effective_skill_targets={s: actual[s] for s in SKILLS} if selected else dict(skills),
                    repeated_count=len(reused), fresh_count=len(selected)-len(reused),
                    immediate_repeat_count=sum(x.get("exposure_tier", 0) == 3 for x in selected),
                    quota_changes=sum(max(0, actual[s]-skills[s]) for s in SKILLS) if selected else 0,
                    skill_transfers=list(transfers), level_targets_preserved=True,
                    replacement_policy=("random_other_skill_same_level" if rng is not None
                                        else "priority_other_skill_same_level"),
                    coverage_policy="cover_available_skills", unavailable_skills=missing_skills,
                    covered_skill_count=sum(actual[s] > 0 for s in SKILLS))

    hard_shortages = []
    total_available = len({fingerprint(x) for x in ranked})
    if total_available < TOTAL:
        hard_shortages.append(dict(dimension="nội dung khác nhau", key="total", required=TOTAL,
                                   available=total_available, missing=TOTAL-total_available))
    # Exact requested levels, never the weaker global floor used by v2.
    for dimension, quotas, getter in (
        ("dạng câu", TYPE_QUOTAS, lambda x: x["question"].question_type),
        ("mức nhận thức", levels, lambda x: x["question"].difficulty_level),
    ):
        for key, need in quotas.items():
            available = len({fingerprint(x) for x in ranked if getter(x) == key})
            if available < need:
                hard_shortages.append(dict(dimension=dimension, key=key, required=need,
                                           available=available, missing=need-available))
    skill_capacity = sum(min(5, len({fingerprint(x) for x in ranked if x["skill"] == skill}))
                         for skill in SKILLS)
    if skill_capacity < TOTAL:
        hard_shortages.append(dict(dimension="giới hạn số câu theo dạng", key="total",
                                   required=TOTAL, available=skill_capacity, missing=TOTAL-skill_capacity))
    if hard_shortages:
        return [], hard_shortages, "insufficient_candidates", audit("unavailable")

    last_status = "incompatible_intersections"
    for tier, stage in enumerate(STAGES):
        pool = [x for x in ranked if x.get("exposure_tier", 0) <= tier]
        selected, shortages, status = select_fixed(pool, levels, skills, max_states=3000)
        searched_out |= status == "search_limit"
        attempts.append(dict(stage=stage, strategy="original_targets", candidates=len(pool),
                             status=status, levels=dict(levels), skills=dict(skills)))
        if selected:
            return selected, [], "ready", audit(stage, selected, exposure_stage=stage)
        # A skill with valid full-pool content must still be covered. Do not
        # call it unavailable just because its only candidates are in cooldown.
        if any(not any(x["skill"] == s for x in pool) for s in SKILLS if s not in missing_skills):
            continue
        selected, status = select_same_level(pool, levels, skills, cells=cells, max_states=max_states, rng=rng)
        searched_out |= status == "search_limit"
        attempts.append(dict(stage=stage, strategy="same_level_skill_transfer", candidates=len(pool),
                             status=status, levels=dict(levels),
                             skills=dict(Counter(x["skill"] for x in selected)) if selected else None))
        last_status = status
        if selected:
            transfers = explain_transfers(selected, pool, skills, cells=cells, max_exposure_tier=tier)
            return selected, [], "ready", audit("same_level_skill_transfer", selected, transfers, stage)
    if searched_out:
        last_status = "search_limit"
    return [], [], last_status, audit("unavailable")
