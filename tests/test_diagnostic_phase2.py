"""Common-paper selection compatibility and current manual-authoring contracts."""
import json
import os
import unittest
from collections import Counter

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)
import config
config.load_local_environment = lambda *args, **kwargs: None

from app import app
from database import db
from models import (
    BankQuestion, BankQuestionOption, Course, CurriculumNode, DiagnosticAssignment,
    Enrollment, Exam, ExamQuestion, QuestionBank, User,
)
from services import practice_blueprint as blueprint
from services.diagnostic_service import (
    common_diagnostic_selection, class_diagnostic_source, common_item_hash,
    diagnostic_assignment_is_eligible, learner_profile_state,
)
from services.id6_service import make_id6


class DiagnosticPhase2Tests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="phase2_teacher", user_code="D2T", fullname="Teacher", role="teacher")
        self.admin = User(username="phase2_admin", user_code="D2A", fullname="Admin", role="admin")
        self.student = User(username="phase2_student", user_code="D2S", fullname="Student", role="student")
        db.session.add_all((self.teacher, self.admin, self.student))
        db.session.flush()
        self.course = Course(course_name="Lớp 9A", subject="Toán", teacher_id=self.teacher.id)
        self.bank = QuestionBank(name="Ngân hàng đầu vào", subject="Toán", grade="9", created_by=self.teacher.id)
        db.session.add_all((self.course, self.bank))
        db.session.flush()
        self._make_ready_bank()
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _client(self, user):
        from flask import g
        g.pop("_login_user", None)
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return client

    def _make_ready_bank(self):
        for skill_index, skill in enumerate(blueprint.SKILLS, 1):
            node = CurriculumNode(
                grade="9", chapter_code="8", chapter_name="Xác suất", lesson_code="i",
                lesson_name="Bài 25 + 26", category_code=str(skill_index),
                category_name=skill, canonical_code=skill, is_active=True,
            )
            db.session.add(node)
            db.session.flush()
            sequence = 0
            for level in blueprint.LEVELS:
                for kind in blueprint.TYPE_QUOTAS:
                    sequence += 1
                    metadata = ({"statements": [
                        {"curriculum_code": skill, "cognitive_level": level} for _ in range(4)
                    ]} if kind == "true_false" else
                                {"short_answer": {"mode": "numeric", "tolerance": "0"}} if kind == "short_answer" else {})
                    question = BankQuestion(
                        bank_id=self.bank.id, created_by=self.teacher.id,
                        question_text=f"{skill}-{level}-{kind}", question_type=kind,
                        difficulty_level=level, curriculum_node_id=node.id,
                        source_id=make_id6("9", "8", "i", str(skill_index), level, kind, sequence),
                        id6_scope=skill, id6_sequence=sequence, classification_status="teacher_confirmed",
                        learning_metadata=json.dumps(metadata),
                    )
                    db.session.add(question)
                    db.session.flush()
                    if kind == "true_false":
                        answers = [(str(index), index % 2 == 0) for index in range(4)]
                    elif kind == "single":
                        answers = [(str(index), index == 0) for index in range(4)]
                    else:
                        answers = [("1/2", True)]
                    for order, (text, correct) in enumerate(answers):
                        db.session.add(BankQuestionOption(
                            question_id=question.id, option_text=text, is_correct=correct, order_index=order
                        ))

    def test_common_selector_uses_baseline_and_all_dimensions(self):
        selection = common_diagnostic_selection(self.bank.questions)
        self.assertEqual(selection["status"], "ready")
        self.assertEqual(selection["level_targets"], {
            "nhan_biet": 9, "thong_hieu": 7, "van_dung": 4, "van_dung_cao": 2,
        })
        self.assertEqual(Counter(q.question_type for q in selection["questions"]), blueprint.TYPE_QUOTAS)
        self.assertEqual(Counter(q.difficulty_level for q in selection["questions"]), selection["level_targets"])
        self.assertEqual(Counter(q.curriculum_node.canonical_code for q in selection["questions"]), selection["skill_targets"])
        self.assertEqual(len({q.content_hash or q.id for q in selection["questions"]}), blueprint.TOTAL)

    def test_post_ignores_legacy_tampered_authoring_fields(self):
        client = self._client(self.admin)
        selected = common_diagnostic_selection(self.bank.questions)["questions"]
        fields = {"question_bank_id": str(self.bank.id), "question_ids": [str(q.id) for q in selected]}
        review = client.post("/api/diagnostics/review", data=fields)
        self.assertEqual(review.status_code, 200)
        response = client.post("/diagnostics/new", data={
            **fields, "review_digest": review.json["review_digest"], "confirmed": "yes",
            "course_id": self.course.id, "question_bank_id": self.bank.id,
            "title": "", "total_questions": "1", "duration_minutes": "5",
            "is_active": "", "shuffle_questions": "1", "shuffle_answers": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        exam = Exam.query.filter_by(assessment_purpose="initial_diagnostic").one()
        self.assertEqual(exam.title, "Đánh giá đầu vào · Lớp 9A")
        self.assertEqual((exam.total_questions, exam.duration_minutes), (blueprint.TOTAL, blueprint.DURATION_MINUTES))
        self.assertEqual(exam.question_bank_id, self.bank.id)
        self.assertTrue(exam.is_active)
        self.assertFalse(exam.shuffle_questions)
        self.assertFalse(exam.shuffle_answers)
        self.assertEqual(Counter(q.question_type for q in exam.questions), blueprint.TYPE_QUOTAS)
        self.assertEqual({q.points for q in exam.questions if q.question_type == "single"}, {.25})
        self.assertEqual({q.points for q in exam.questions if q.question_type == "true_false"}, {1.})
        self.assertEqual({q.points for q in exam.questions if q.question_type == "short_answer"}, {.5})

    def test_late_enrollment_receives_existing_active_diagnostic(self):
        exam = Exam(
            title="Frozen", course_id=self.course.id, created_by=self.teacher.id,
            assessment_purpose="initial_diagnostic", exam_type="exam", is_active=True,
        )
        db.session.add(exam)
        db.session.flush()
        db.session.add(ExamQuestion(exam_id=exam.id, question_text="Frozen item", question_type="single", points=.25))
        db.session.commit()
        response = self._client(self.admin).post("/enrollments", data={
            "student_id": self.student.user_code, "course_id": self.course.id,
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(Enrollment.query.filter_by(student_id=self.student.id, course_id=self.course.id, status="active").first())
        assignment = DiagnosticAssignment.query.filter_by(exam_id=exam.id, student_id=self.student.id).one()
        self.assertTrue(assignment.common_item_hash)


    def _exclude_skill(self, skill):
        for question in self.bank.questions:
            if question.curriculum_node.canonical_code == skill:
                question.adaptive_excluded = True
        db.session.commit()

    def _create_missing_sixth(self):
        # The admin wizard now requires eight skills and manual review. Keep
        # recovery compatibility tests at the frozen-paper service boundary;
        # do not grant teachers access to the replacement authoring route.
        from routes.diagnostics import _copy_bank_questions
        from services.diagnostic_service import assign_diagnostic_cohort
        from services.source_resolver import attach_source_manifest
        self._exclude_skill(blueprint.SKILLS[5])
        db.session.add(Enrollment(student_id=self.student.id, course_id=self.course.id, status="active"))
        selection = common_diagnostic_selection([q for q in self.bank.questions if not q.adaptive_excluded])
        self.assertEqual(selection["status"], "ready")
        self.assertTrue(any("Đã tự động thay" in warning for warning in selection["warnings"]))
        metadata = {"diagnostic": {"version": blueprint.VERSION,
            "selection_policy": selection["selection_policy"], "recovery": selection["recovery"],
            "level_targets": selection["level_targets"], "skill_targets": selection["skill_targets"]}}
        exam = Exam(title="Frozen recovery compatibility", course_id=self.course.id,
            created_by=self.admin.id, question_bank_id=self.bank.id, assessment_purpose="initial_diagnostic",
            exam_type="exam", is_active=True, duration_minutes=40, total_questions=22,
            adaptive_metadata=json.dumps(metadata))
        db.session.add(exam); db.session.flush()
        pairs = _copy_bank_questions(exam, selection["questions"])
        attach_source_manifest(exam, self.course, pairs, bank_ids=[self.bank.id])
        assign_diagnostic_cohort(exam, assigned_by=self.admin.id)
        db.session.commit()
        return exam

    def test_missing_sixth_skill_creates_full_common_paper_and_student_can_start(self):
        from services.source_resolver import validate_exam_source
        exam = self._create_missing_sixth()
        recovery = exam.get_adaptive_metadata()["diagnostic"]["recovery"]
        self.assertEqual(recovery["unavailable_skills"], [blueprint.SKILLS[5]])
        self.assertEqual(recovery["covered_skill_count"], 7)
        self.assertEqual(recovery["replacement_policy"], "random_other_skill_same_level")
        self.assertGreaterEqual(recovery["quota_changes"], 3)
        self.assertEqual(len(exam.questions), 22)
        self.assertEqual(Counter(q.question_type for q in exam.questions), blueprint.TYPE_QUOTAS)
        self.assertEqual(Counter(q.difficulty_level for q in exam.questions), {
            "nhan_biet": 9, "thong_hieu": 7, "van_dung": 4, "van_dung_cao": 2,
        })
        self.assertNotIn(blueprint.SKILLS[5], {q.curriculum_code for q in exam.questions})
        frozen = {q.bank_question_id: q for q in exam.questions}
        for transfer in recovery["skill_transfers"]:
            question = frozen[transfer["question_id"]]
            self.assertEqual(question.curriculum_code, transfer["target_skill"])
            self.assertEqual(question.difficulty_level, transfer["level"])
            self.assertEqual(question.question_type, transfer["question_type"])
        self.assertTrue(validate_exam_source(exam, require_live=True)["valid"])
        assignment = DiagnosticAssignment.query.filter_by(exam_id=exam.id, student_id=self.student.id).one()
        self.assertTrue(diagnostic_assignment_is_eligible(assignment, exam))
        self.assertEqual(class_diagnostic_source(self.student.id, self.course)["status"], "ready")
        state = learner_profile_state(self.student.id, "Toán", course_id=self.course.id)
        self.assertEqual((state["status"], state["exam"]), ("diagnostic_required", exam.id))
        response = self._client(self.student).get(f"/practice/{exam.id}/take")
        self.assertEqual(response.status_code, 200)

    def test_replacement_paper_is_frozen_for_original_and_late_cohort(self):
        exam = self._create_missing_sixth()
        expected = common_item_hash(exam)
        ids = [q.bank_question_id for q in exam.questions]
        late = User(username="transfer_late", user_code="DL", fullname="Late", role="student")
        db.session.add(late)
        db.session.flush()
        enrollment = Enrollment(student_id=late.id, course_id=self.course.id, status="active")
        db.session.add(enrollment)
        db.session.flush()
        from services.diagnostic_service import assign_existing_diagnostics_for_enrollment
        assign_existing_diagnostics_for_enrollment(enrollment, assigned_by=self.teacher.id)
        db.session.commit()
        assignments = DiagnosticAssignment.query.filter_by(exam_id=exam.id).all()
        self.assertEqual(len(assignments), 2)
        self.assertEqual({a.common_item_hash for a in assignments}, {expected})
        self.assertTrue(all(diagnostic_assignment_is_eligible(a, exam) for a in assignments))
        self.assertEqual(self._client(late).get(f"/practice/{exam.id}/take").status_code, 200)
        self.assertEqual([q.bank_question_id for q in exam.questions], ids)

    def test_random_alternative_skills_change_across_seeded_generations(self):
        from random import Random
        pool = [q for q in self.bank.questions if q.curriculum_node.canonical_code != blueprint.SKILLS[5]]
        choices = set()
        for seed in range(8):
            selection = common_diagnostic_selection(pool, rng=Random(seed))
            self.assertEqual(selection["status"], "ready")
            self.assertEqual(Counter(q.difficulty_level for q in selection["questions"]), selection["level_targets"])
            self.assertEqual(Counter(q.question_type for q in selection["questions"]), blueprint.TYPE_QUOTAS)
            choices.add(tuple(sorted(t["target_skill"] for t in selection["recovery"]["skill_transfers"])))
        self.assertGreater(len(choices), 1)
        first = common_diagnostic_selection(pool, rng=Random(17))
        repeat = common_diagnostic_selection(pool[::-1], rng=Random(17))
        self.assertEqual([q.id for q in first["questions"]], [q.id for q in repeat["questions"]])

    def test_missing_high_difficulty_cell_uses_other_skill_at_same_level(self):
        pool = [q for q in self.bank.questions if not (
            q.curriculum_node.canonical_code == blueprint.SKILLS[0] and q.difficulty_level == "van_dung_cao"
        )]
        selection = common_diagnostic_selection(pool)
        self.assertEqual(selection["status"], "ready")
        high = [q for q in selection["questions"] if q.difficulty_level == "van_dung_cao"]
        self.assertEqual(len(high), 2)
        self.assertTrue(all(q.curriculum_node.canonical_code != blueprint.SKILLS[0] for q in high))
        self.assertEqual({q.curriculum_node.canonical_code for q in selection["questions"]}, set(blueprint.SKILLS))

    def test_common_paper_still_requires_actual_questions_at_every_requested_level(self):
        for question in self.bank.questions:
            if question.difficulty_level == "van_dung_cao":
                question.adaptive_excluded = True
        db.session.commit()
        selection = common_diagnostic_selection([q for q in self.bank.questions if not q.adaptive_excluded])
        self.assertFalse(selection["questions"])
        self.assertEqual(Exam.query.filter_by(assessment_purpose="initial_diagnostic").count(), 0)
        self.assertIn("van_dung_cao", json.dumps(selection["shortages"]))

    def test_transferred_coverage_requires_matching_frozen_audit(self):
        exam = self._create_missing_sixth()
        assignment = DiagnosticAssignment.query.filter_by(exam_id=exam.id, student_id=self.student.id).one()
        original = exam.adaptive_metadata
        metadata = exam.get_adaptive_metadata()
        metadata["diagnostic"]["recovery"]["unavailable_skills"] = []
        exam.adaptive_metadata = json.dumps(metadata)
        self.assertFalse(diagnostic_assignment_is_eligible(assignment, exam))
        exam.adaptive_metadata = original
        metadata = exam.get_adaptive_metadata()
        metadata["diagnostic"]["recovery"]["skill_transfers"][0]["level"] = "unknown"
        exam.adaptive_metadata = json.dumps(metadata)
        self.assertFalse(diagnostic_assignment_is_eligible(assignment, exam))
        exam.adaptive_metadata = "{}"
        self.assertFalse(diagnostic_assignment_is_eligible(assignment, exam))
        exam.adaptive_metadata = original
        self.assertTrue(diagnostic_assignment_is_eligible(assignment, exam))

    def test_excluded_skill_cannot_be_reintroduced_by_recovery(self):
        from services.personalization_evidence import bank_question_content_hash
        exam = self._create_missing_sixth()
        source_ids = {q.id for q in self.bank.questions if not q.adaptive_excluded}
        self.assertTrue({q.bank_question_id for q in exam.questions} <= source_ids)
        self.assertEqual(len({bank_question_content_hash(q.bank_question) for q in exam.questions}), 22)


if __name__ == "__main__":
    unittest.main()
