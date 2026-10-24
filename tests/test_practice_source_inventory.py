"""Pure phase-1 tests: no real database, learner data or AI calls."""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest

from services import aptga
from services.practice_blueprint import LEVELS, SKILLS, TYPE_QUOTAS
from services.practice_source_inventory import build_source_inventory, same_level_alternatives


def item(id, skill=SKILLS[0], level=LEVELS[-1], kind="single", **extra):
    return dict(question=SimpleNamespace(id=id, difficulty_level=level, question_type=kind),
                skill=skill, score=0, **extra)


def test_inventory_includes_zero_cells_and_deduplicates_content():
    rows = [item(1, fingerprint="same"), item(2, fingerprint="same"),
            item(3, SKILLS[1], fingerprint="same"), item(4, SKILLS[1])]
    audit = build_source_inventory(rows)
    assert len(audit["cells"]) == len(SKILLS)*len(LEVELS)*len(TYPE_QUOTAS)
    assert audit["unique_content"]["fresh"] == 2
    assert audit["duplicate_rows"] == 2
    cell = next(x for x in audit["cells"] if x["skill"] == SKILLS[1]
                and x["level"] == LEVELS[-1] and x["question_type"] == "single")
    assert cell["available"]["fresh"] == 2
    assert audit["counts_are_additive"] is False
    assert audit["cell_targets_assigned"] is False
    json.dumps(audit)


def test_inventory_separates_empty_from_review_only_and_counts_cumulative_tiers():
    rows = [item(i+1, exposure_tier=i) for i in range(4)]
    audit = build_source_inventory(rows)
    assert list(audit["unique_content"].values()) == [1, 2, 3, 4]
    audit = build_source_inventory(rows[1:])
    assert len(audit["review_only_cells"]) == 1
    assert len(audit["empty_cells"]) == 95
    assert audit["unique_content"]["fresh"] == 0


def test_transfer_preview_keeps_level_and_type_and_excludes_source():
    rows = [item(1), item(2, SKILLS[1]), item(3, SKILLS[2], level=LEVELS[2]),
            item(4, SKILLS[3], kind="true_false"), item(5, SKILLS[4], exposure_tier=2)]
    alternatives = same_level_alternatives(rows, SKILLS[0], LEVELS[-1], "single")
    assert [x["skill"] for x in alternatives] == [SKILLS[1]]
    assert alternatives[0]["question_ids"] == [2]
    assert len(same_level_alternatives(rows, SKILLS[0], LEVELS[-1], "single",
                                     max_exposure_tier=2)) == 2


def test_preview_deduplicates_and_excludes_used_content():
    rows = [item(1, SKILLS[1], fingerprint="used"), item(2, SKILLS[1], fingerprint="same"),
            item(3, SKILLS[1], fingerprint="same")]
    rows[-1]["score"] = 1
    result = same_level_alternatives(rows, SKILLS[0], LEVELS[-1], "single",
                                     excluded_fingerprints={"used"})
    assert result[0]["available"] == 1
    assert result[0]["question_ids"] == [3]


def test_profile_need_precedes_teacher_tie_break_and_results_are_deterministic():
    weak = aptga.summarize([])
    weak.update(mastery=.1, sufficiency=1, sufficient=True, repetition=1)
    rows = [item(1, SKILLS[1], components={"teacher": 1}), item(2, SKILLS[2])]
    cells = {f"{SKILLS[2]}||{LEVELS[-1]}": weak}
    a = same_level_alternatives(rows, SKILLS[0], LEVELS[-1], "single", cells=cells)
    b = same_level_alternatives(rows[::-1], SKILLS[0], LEVELS[-1], "single", cells=cells)
    assert a == b
    assert a[0]["skill"] == SKILLS[2]


def test_empty_cell_does_not_mean_a_required_slot_is_missing():
    audit = build_source_inventory([item(1, SKILLS[1])], level_targets={LEVELS[-1]: 1},
                                   skill_targets={SKILLS[1]: 1})
    assert not [x for x in audit["marginal_shortages"] if x["dimension"] in ("level", "skill")]
    assert audit["full_paper_feasibility_checked"] is False
    assert {"skill": SKILLS[0], "level": LEVELS[-1], "question_type": "single"} in audit["empty_cells"]


def test_no_same_level_source_returns_empty_instead_of_lower_level():
    rows = [item(1, SKILLS[1], level=LEVELS[2])]
    assert same_level_alternatives(rows, SKILLS[0], LEVELS[-1], "single") == []


def test_invalid_labels_do_not_become_sources():
    rows = [item(1, "outside"), item(2, SKILLS[1], level="bad"),
            item(3, SKILLS[1], kind="essay")]
    assert build_source_inventory(rows)["ignored_rows"] == 3
    assert same_level_alternatives(rows, SKILLS[0], LEVELS[-1], "single") == []
    with pytest.raises(ValueError):
        same_level_alternatives([], SKILLS[0], "bad", "single")
    with pytest.raises(ValueError):
        same_level_alternatives([], SKILLS[0], LEVELS[-1], "single", max_exposure_tier=4)


def test_inventory_and_preview_do_not_mutate_input():
    rows = [item(1, SKILLS[1], fingerprint="one", components={"teacher": .5})]
    original = deepcopy(rows)
    levels, skills = {LEVELS[-1]: 1}, {SKILLS[1]: 1}
    build_source_inventory(rows, level_targets=levels, skill_targets=skills)
    same_level_alternatives(rows, SKILLS[0], LEVELS[-1], "single")
    assert rows == original
    assert levels == {LEVELS[-1]: 1} and skills == {SKILLS[1]: 1}
