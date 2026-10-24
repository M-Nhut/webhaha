import unittest

from services.classification_evaluation import evaluate


class TestClassificationEvaluation(unittest.TestCase):
    def row(self, identifier, text, code, level):
        return dict(id=identifier, question=dict(question_text=text, question_type='single', options=[]),
                    scope=dict(grade='9', chapters=['8'], lessons=['i']), expected_primary_code=code,
                    expected_difficulty_level=level)

    def test_reports_metrics_without_claiming_readiness_on_tiny_set(self):
        rows = [
            self.row('p', 'Tung một đồng xu. Hãy lập không gian mẫu, xác định biến cố và tính xác suất mặt ngửa.', '9C8-i-3', 'van_dung'),
            self.row('s', 'Viết tập hợp không gian mẫu của phép thử gieo xúc sắc.', '9C8-i-1', 'nhan_biet'),
        ]
        report = evaluate(rows)
        self.assertEqual(report['metrics']['labeled_count'], 2)
        self.assertEqual(report['metrics']['pair_accuracy_on_automatic'], 1.0)
        self.assertFalse(report['ready_for_wider_auto_assignment'])

    def test_detects_duplicate_content_and_invalid_labels(self):
        row = self.row('a', 'Viết tập hợp không gian mẫu của phép thử gieo xúc sắc.', '9C8-i-1', 'nhan_biet')
        report = evaluate([row, {**row, 'id':'b'}, {**row, 'id':'bad', 'expected_primary_code':'bad'}],
                          dict(min_labeled_rows=1, min_pair_accuracy=0))
        self.assertEqual(report['metrics']['invalid_count'], 1)
        self.assertEqual(report['metrics']['duplicate_content_groups'], [['a', 'b']])
        self.assertFalse(report['ready_for_wider_auto_assignment'])
