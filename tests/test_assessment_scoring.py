from decimal import Decimal
import pytest
from services.assessment_scoring import allocate
from models import ExamSubmission


def questions(n, kind='single'):
    return [{'question_type': kind, 'points': 1} for _ in range(n)]


@pytest.mark.parametrize('count', [1, 3, 11, 22, 100])
def test_any_length_totals_ten_and_repeated_save_is_stable(count):
    items = questions(count)
    allocate(items)
    first = [q['points'] for q in items]
    assert sum(Decimal(str(q['points'])) for q in items) == 10
    allocate(items)
    assert first == [q['points'] for q in items]


def test_section_budgets_and_relative_weights():
    items = questions(12) + questions(4, 'true_false') + questions(6, 'short_answer')
    budgets = {'single': 3, 'true_false': 4, 'short_answer': 3}
    assert allocate(items, budgets) == budgets
    assert items[0]['points'] == .25 and items[12]['points'] == 1 and items[-1]['points'] == .5
    items[0]['weight'] = 2
    assert allocate(items, budgets) == budgets
    assert abs(items[0]['points'] - 2 * items[1]['points']) < .0002


@pytest.mark.parametrize('budgets', [
    {'single': 11}, {'single': 9}, {'single': 'NaN'}, {'single': 'Infinity'},
    {'single': 9, 'short_answer': 1}, {'single': -1, 'true_false': 11},
])
def test_invalid_budgets_are_rejected(budgets):
    with pytest.raises(ValueError):
        allocate(questions(11), budgets)


def test_legacy_result_converts_without_mutating_evidence():
    submission = ExamSubmission(total_score=11, max_score=11)
    assert submission.score_on_ten == 10
    assert submission.total_score == 11 and submission.max_score == 11
    submission.total_score = 7.315
    submission.max_score = 10
    assert submission.score_on_ten == 7.3
    submission.total_score = 7.35
    assert submission.score_on_ten == 7.4


def test_editor_section_defaults_have_exact_cent_budgets():
    from services.assessment_scoring import section_defaults
    items = questions(4) + questions(4, 'truefalse') + questions(3, 'short_answer')
    counts, budgets = section_defaults(items)
    assert counts == {'single': 4, 'true_false': 4, 'short_answer': 3}
    assert sum(Decimal(str(value)) for value in budgets.values()) == 10
    assert all(Decimal(str(value)).as_tuple().exponent >= -2 for value in budgets.values())
    assert section_defaults([]) == (dict.fromkeys(counts, 0), dict.fromkeys(counts, 0))
