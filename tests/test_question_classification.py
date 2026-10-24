import unittest

from services.question_classification_service import classify, content_fingerprint


class TestChapter6Classification(unittest.TestCase):
    def question(self, text, **extra):
        data = dict(question_text=text, question_type='single', options=[], statements=[])
        data.update(extra)
        return data

    def test_probability_uses_required_intent_and_multistep_difficulty(self):
        result = classify(self.question('Tung một đồng xu. Hãy lập không gian mẫu, xác định biến cố và tính xác suất xuất hiện mặt ngửa.'),
                          {'grade':'9','chapters':['6']})
        self.assertEqual(result['primary_code'], '9C6-4-3')
        self.assertEqual(result['difficulty_level'], 'van_dung')
        self.assertEqual(result['status'], 'suggested')

    def test_probability_categories_distinguish_space_and_games(self):
        relative = classify(self.question('Viết tập hợp không gian mẫu của phép thử gieo xúc sắc.'),
                            {'grade':'9','chapters':['6']})
        grouped = classify(self.question('Tính xác suất của biến cố khi gieo xúc sắc.'),
                           {'grade':'9','chapters':['6']})
        self.assertEqual((relative['primary_code'], relative['difficulty_level']), ('9C6-4-1','nhan_biet'))
        self.assertEqual((grouped['primary_code'], grouped['difficulty_level']), ('9C6-4-4','van_dung'))

    def test_chart_and_out_of_catalog_are_not_classified_by_context_only(self):
        chart = classify(self.question('Hãy biểu diễn số liệu bằng biểu đồ cột kép.'), {'grade':'9','chapters':['6']})
        ambiguous = classify(self.question('Một biểu đồ cột cho biết số liệu. Hãy cho nhận xét.'), {'grade':'9','chapters':['6']})
        self.assertIsNone(chart['primary_code'])
        self.assertEqual(chart['status'], 'needs_review')
        self.assertEqual(ambiguous['status'], 'needs_review')
        self.assertIsNone(ambiguous['primary_code'])

    def test_fingerprint_changes_with_content_and_missing_image_requires_review(self):
        first = self.question('Xác định tần số của giá trị 2.')
        changed = self.question('Xác định tần số của giá trị 3.')
        self.assertNotEqual(content_fingerprint(first), content_fingerprint(changed))
        result = classify(self.question('Xác định tần số của giá trị 2.', has_image=True), {'grade':'9','chapters':['6']})
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('Thiếu hình', result['rationale'][0])

    def test_true_false_never_invents_statement_levels(self):
        question = self.question('Xét các mệnh đề về xác suất khi gieo xúc sắc.', question_type='true_false',
                                 statements=[{'text':'Tính xác suất của biến cố khi gieo xúc sắc.', 'answer':True}] * 4)
        result = classify(question, {'grade':'9','chapters':['6']})
        self.assertEqual(result['status'], 'suggested')
        self.assertEqual(result['difficulty_level'], 'van_dung')
        self.assertEqual(len(result['statement_levels']), 4)
        self.assertTrue(all(row['level'] == 'van_dung' for row in result['statement_levels']))


if __name__ == '__main__':
    unittest.main()
