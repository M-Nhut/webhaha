"""Selection safety required before private overlay authoring is enabled."""
import unittest
from unittest.mock import patch

from tests import test_question_scope_phase1 as fixtures
from adaptive_engine import AdaptiveEngine
from database import db
from models import Course


class OverlaySelectionSafetyTests(unittest.TestCase):
    setUp = fixtures.QuestionScopePolicyTests.setUp
    tearDown = fixtures.QuestionScopePolicyTests.tearDown
    _question = fixtures.QuestionScopePolicyTests._question

    def test_candidates_follow_current_class_teacher_without_changing_rows(self):
        course = Course(course_name="Overlay selection", subject="Toán", teacher_id=self.owner.id)
        db.session.add(course)
        db.session.commit()
        with patch("adaptive_engine.bank_question_ready", return_value=True):
            first = AdaptiveEngine.select_questions(
                self.student.id, "Toán", [self.shared.id], 100,
                {"course_id": course.id},
            )
            first_ids = {question.id for question in first["questions"]}
            self.assertIn(self.shared_q.id, first_ids)
            self.assertIn(self.overlay_q.id, first_ids)
            self.assertNotIn(self.foreign_q.id, first_ids)
            course.teacher_id = self.other.id
            db.session.commit()
            second = AdaptiveEngine.select_questions(
                self.student.id, "Toán", [self.shared.id], 100,
                {"course_id": course.id},
            )
            second_ids = {question.id for question in second["questions"]}
            self.assertIn(self.shared_q.id, second_ids)
            self.assertIn(self.foreign_q.id, second_ids)
            self.assertNotIn(self.overlay_q.id, second_ids)
            missing = AdaptiveEngine.select_questions(
                self.student.id, "Toán", [self.shared.id], 100,
                {"course_id": 999999},
            )
            self.assertEqual(missing["questions"], [])
            without_class = AdaptiveEngine.select_questions(
                self.student.id, "Toán", [self.shared.id], 100,
            )
            self.assertEqual(without_class["questions"], [])
        self.assertEqual(self.overlay_q.private_owner_id, self.owner.id)


if __name__ == "__main__":
    unittest.main()
