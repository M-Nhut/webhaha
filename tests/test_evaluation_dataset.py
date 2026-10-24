import unittest

from services.evaluation_dataset import build_blinded_rows


class TestEvaluationDataset(unittest.TestCase):
    def test_packet_hides_answers_and_removes_duplicate_content(self):
        rows = [
            dict(id=1, source_id='9C6N4-1D.1', question_text='Viết tập hợp không gian mẫu của phép thử.', question_type='single',
                 options=[dict(text='2', is_correct=True), dict(text='3', is_correct=False)]),
            dict(id=2, source_id='9C6N4-1D.2', question_text='Viết tập hợp không gian mẫu của phép thử.', question_type='single',
                 options=[dict(text='2', is_correct=False), dict(text='3', is_correct=True)]),
        ]
        packet = build_blinded_rows(rows)
        self.assertEqual(len(packet['rows']), 1)
        self.assertEqual(packet['omitted_duplicates'], [{'question_id':2, 'duplicate_of':'bank-1'}])
        self.assertNotIn('is_correct', packet['rows'][0]['question']['options'][0])
        self.assertEqual(packet['rows'][0]['expected_primary_code'], '')
