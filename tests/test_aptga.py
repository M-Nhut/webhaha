"""Behavioral examples for the versioned APTGA specification."""
import datetime as dt
import unittest
from types import SimpleNamespace
from services import aptga


class APTGATests(unittest.TestCase):
    def test_rounding_and_totals(self):
        for n in range(1, 101):
            quota, warnings = aptga.allocate(n, {})
            self.assertEqual(sum(quota.values()), n)
            self.assertTrue(all(v >= 0 for v in quota.values()))
        self.assertTrue(aptga.allocate(2, {})[1])
        self.assertEqual(list(aptga.allocate(7, {}, ['thong_hieu'])[0].values()), [7])

    def test_transfer_is_bounded_and_requires_evidence(self):
        profile = {l: dict(mastery=m, sufficient=True) for l, m in
                   zip(aptga.LEVELS, [.875, .833, .60, .10])}
        quota, _ = aptga.allocate(20, profile)
        self.assertEqual(sum(quota.values()), 20)
        self.assertGreater(quota['van_dung_cao'], 2)
        self.assertLessEqual(quota['van_dung_cao'], 5)
        self.assertGreaterEqual(quota['nhan_biet'], 5)
        self.assertLessEqual(8 - quota['nhan_biet'] + 6 - quota['thong_hieu'], 4)
        for row in profile.values():
            row['sufficient'] = False
        self.assertEqual(aptga.allocate(20, profile)[0], dict(zip(aptga.LEVELS, [8, 6, 4, 2])))
        for row in profile.values():
            row.update(mastery=.9, sufficient=True)
        self.assertEqual(aptga.allocate(20, profile)[0], dict(zip(aptga.LEVELS, [8, 6, 4, 2])))

    def row(self, session, score, question):
        return SimpleNamespace(submission_id=session, normalized_score=score,
                               occurred_at=dt.datetime(2026, 1, session),
                               question_content_hash=str(question), bank_question_id=question,
                               exam_question_id=question, curriculum_code='9C6-4-1',
                               cognitive_level='van_dung')

    def test_recency_distinctness_and_unknown(self):
        self.assertIsNone(aptga.summarize([])['mastery'])
        repeated = [self.row(i, 0, 1) for i in range(1, 7)]
        self.assertFalse(aptga.summarize(repeated)['sufficient'])
        rows = [self.row(1, 0, i) for i in range(1, 4)] + [self.row(2, 1, i) for i in range(4, 7)]
        cell = aptga.summarize(rows)
        self.assertTrue(cell['sufficient'])
        self.assertGreater(cell['mastery'], .5)
        self.assertEqual(cell, aptga.summarize(list(reversed(rows))))
        self.assertIn('9C6-4-1||van_dung', aptga.matrix(rows))
        score, parts = aptga.priority(cell)
        self.assertTrue(0 <= score <= 1)
        self.assertTrue(all(0 <= v <= 1 for v in parts.values()))


if __name__ == '__main__':
    unittest.main()
