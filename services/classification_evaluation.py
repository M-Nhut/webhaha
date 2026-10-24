"""Evaluate classification suggestions against independently teacher-labelled rows."""
from collections import defaultdict

from services.curriculum_data import load_chapter8_bundle
from services.question_classification_service import classify, content_fingerprint


DEFAULT_GATE = dict(min_labeled_rows=240, min_pair_accuracy=.95, min_auto_coverage=0.0)


def _row_question(row):
    question = dict(row.get('question') or {})
    for key in ('question_text', 'context', 'image_url', 'formulas', 'options', 'statements', 'question_type', 'explanation'):
        if key in row and key not in question:
            question[key] = row[key]
    return question


def evaluate(rows, gate=None):
    """Return only measured metrics; never treat review rows as correct predictions."""
    bundle = load_chapter8_bundle()
    valid_codes = {item['canonical_code'] for item in bundle['rules']['categories']}
    valid_levels = set(bundle['rules']['difficulty_rubric'])
    gate = {**DEFAULT_GATE, **(gate or {})}
    evaluated, invalid, groups = [], [], defaultdict(list)
    for index, row in enumerate(rows):
        question = _row_question(row)
        expected_code = row.get('expected_primary_code')
        expected_level = row.get('expected_difficulty_level')
        if expected_code not in valid_codes or expected_level not in valid_levels or not question.get('question_text'):
            invalid.append(dict(index=index, id=row.get('id'), reason='Thiếu nhãn giáo viên hoặc nhãn ngoài danh mục.'))
            continue
        fingerprint = content_fingerprint(question)
        groups[fingerprint].append(row.get('id', index))
        prediction = classify(question, row.get('scope') or {'grade':'9', 'chapters':['8'], 'lessons':['i']})
        automatic = prediction['status'] == 'suggested'
        evaluated.append(dict(id=row.get('id', index), automatic=automatic, expected_code=expected_code,
                              expected_level=expected_level, prediction=prediction,
                              category_correct=automatic and prediction['primary_code'] == expected_code,
                              difficulty_correct=automatic and prediction['difficulty_level'] == expected_level,
                              pair_correct=automatic and prediction['primary_code'] == expected_code
                                           and prediction['difficulty_level'] == expected_level))
    automatic = [item for item in evaluated if item['automatic']]
    def rate(items, field):
        return round(sum(bool(item[field]) for item in items) / len(items), 4) if items else None
    by_code = {}
    for code in valid_codes:
        rows_for_code = [item for item in automatic if item['expected_code'] == code]
        if rows_for_code:
            by_code[code] = dict(count=len(rows_for_code), pair_accuracy=rate(rows_for_code, 'pair_correct'))
    metrics = dict(labeled_count=len(evaluated), invalid_count=len(invalid), automatic_count=len(automatic),
                   automatic_coverage=round(len(automatic) / len(evaluated), 4) if evaluated else 0,
                   category_accuracy_on_automatic=rate(automatic, 'category_correct'),
                   difficulty_accuracy_on_automatic=rate(automatic, 'difficulty_correct'),
                   pair_accuracy_on_automatic=rate(automatic, 'pair_correct'), by_category=by_code,
                   duplicate_content_groups=[ids for ids in groups.values() if len(ids) > 1])
    ready = (metrics['labeled_count'] >= gate['min_labeled_rows']
             and metrics['automatic_coverage'] >= gate['min_auto_coverage']
             and metrics['pair_accuracy_on_automatic'] is not None
             and metrics['pair_accuracy_on_automatic'] >= gate['min_pair_accuracy']
             and not metrics['duplicate_content_groups'])
    return dict(gate=gate, ready_for_wider_auto_assignment=ready, metrics=metrics, invalid_rows=invalid,
                rows=evaluated)
