"""MVP regression tests for evidence, diagnostic assignment and teacher reports."""

from __future__ import annotations

import datetime as dt
import json
import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)

# Do not let a developer .env select a persistent database or an external AI
# endpoint when this module imports the application.
import config
config.load_local_environment = lambda *args, **kwargs: None

from adaptive_engine import AdaptiveEngine
from app import app
from database import db
from models import (
    BankQuestion,
    BankQuestionOption,
    Course,
    CurriculumNode,
    DiagnosticAssignment,
    ErrorObservation,
    Exam,
    ExamAnswer,
    ExamQuestion,
    ExamSubmission,
    LearningHistory,
    StudentErrorProfile,
    SubmissionAnswer,
    TeacherLearningReport,
    User,
)
from services.ai_profile_analysis import validate_evidence_analysis
from services.diagnostic_service import assign_diagnostic_cohort
from services.personalization_evidence import (
    content_hash,
    refresh_question_snapshot,
    report_payload,
    upsert_teacher_report,
)


class PersonalizationMVPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="mvp-teacher", fullname="Teacher", user_code="MVP-T", role="teacher")
        self.other_teacher = User(username="mvp-other", fullname="Other teacher", user_code="MVP-O", role="teacher")
        self.student = User(username="mvp-student", fullname="Student", user_code="MVP-S", role="student")
        self.other_student = User(username="mvp-other-student", fullname="Other student", user_code="MVP-OS", role="student")
        for user in (self.teacher, self.other_teacher, self.student, self.other_student):
            user.set_password("mvp-password")
        db.session.add_all([self.teacher, self.other_teacher, self.student, self.other_student])
        db.session.flush()
        self.course = Course(course_name="Toán 9 MVP", subject="Toán", teacher_id=self.teacher.id)
        self.other_course = Course(course_name="Toán 9 other", subject="Toán", teacher_id=self.other_teacher.id)
        db.session.add_all([self.course, self.other_course])
        db.session.flush()
        from models import Enrollment
        db.session.add_all([
            Enrollment(student_id=self.student.id, course_id=self.course.id, status="active"),
            Enrollment(student_id=self.other_student.id, course_id=self.course.id, status="active"),
        ])
        self.bank = __import__("models", fromlist=["QuestionBank"]).QuestionBank(
            name="MVP bank", subject="Toán", grade="9", created_by=self.teacher.id
        )
        db.session.add(self.bank)
        db.session.flush()
        self.exam = Exam(
            title="MVP attempt", course_id=self.course.id, created_by=self.teacher.id,
            exam_type="exam", assessment_purpose="summative", shuffle_questions=False,
        )
        db.session.add(self.exam)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def make_bank_question(self, text, *, qtype="single", topic="Skill A", node=None):
        question = BankQuestion(
            bank_id=self.bank.id, question_text=text, question_type=qtype,
            difficulty_level="thong_hieu", topic=topic, created_by=self.teacher.id,
            curriculum_node=node,
            learning_metadata=json.dumps({"short_answer": {"mode": "numeric", "tolerance": "0"}}) if qtype == "short_answer" else None,
        )
        db.session.add(question)
        db.session.flush()
        return question

    def make_exam_question(self, bank, *, qtype=None, answers=None, points=1.0):
        question = ExamQuestion(
            exam_id=self.exam.id, bank_question_id=bank.id, question_text=bank.question_text,
            question_type=qtype or bank.question_type, difficulty_level=bank.difficulty_level,
            points=points, topic_snapshot=bank.topic,
            curriculum_code=bank.curriculum_node.canonical_code if bank.curriculum_node else None,
        )
        db.session.add(question)
        db.session.flush()
        for answer_text, is_correct in answers or [("A", True), ("B", False)]:
            db.session.add(ExamAnswer(question_id=question.id, answer_text=answer_text, is_correct=is_correct))
        db.session.flush()
        refresh_question_snapshot(question, bank)
        return question

    def make_submission(self, questions, actuals, *, revision=1, graded=True):
        submission = ExamSubmission(
            exam_id=self.exam.id, student_id=self.student.id, exam_type="exam",
            submitted_at=dt.datetime.utcnow(), is_graded=graded,
            status="graded" if graded else "submitted", grading_revision=revision,
            total_score=0, max_score=sum(q.points for q in questions),
        )
        db.session.add(submission)
        db.session.flush()
        for question, actual in zip(questions, actuals):
            qtype = question.question_type
            if qtype in ("truefalse", "true_false"):
                payload = actual
                selected = [int(key) for key, value in payload.items() if value is True]
                correct = payload == {str(a.id): bool(a.is_correct) for a in question.answers}
                answer_text = json.dumps(payload)
            elif qtype in ("short_answer", "essay"):
                payload = {"text": actual}
                selected = []
                accepted = {a.answer_text.strip().lower() for a in question.answers}
                correct = str(actual).strip().lower() in accepted
                answer_text = json.dumps(payload)
            else:
                selected = list(actual)
                correct_ids = {a.id for a in question.answers if a.is_correct}
                correct = set(selected) == correct_ids and bool(selected)
                answer_text = None
            status = "answered" if actual not in (None, [], {}) and actual != "" else "unanswered"
            answer = SubmissionAnswer(
                submission_id=submission.id, question_id=question.id,
                selected_answer_ids=json.dumps(selected), answer_text=answer_text,
                is_correct=correct, points_earned=question.points if correct else 0,
                answer_status=status,
            )
            answer.answer_snapshot = json.dumps({"actual": actual}, ensure_ascii=False)
            answer.evidence_hash = content_hash({"question": question.source_content_hash, "actual": actual})
            db.session.add(answer)
        db.session.commit()
        AdaptiveEngine.update_performance(self.student.id, submission)
        return submission

    def login_as(self, user):
        from flask import g
        g.pop("_login_user", None)
        client = app.test_client()
        response = client.post(
            "/login", data={"username": user.username, "password": "mvp-password", "submit": "Đăng nhập"},
            follow_redirects=False,
        )
        if response.status_code != 302:
            raise AssertionError(f"test login failed: {response.status_code}")
        return client

    def test_d_t_s_answer_snapshots_and_pending_items_are_excluded(self):
        d = self.make_bank_question("Chọn D", qtype="single")
        t = self.make_bank_question("Đúng sai", qtype="true_false")
        s = self.make_bank_question("Trả lời ngắn", qtype="short_answer")
        blank = self.make_bank_question("Bỏ trống", qtype="single")
        dq = self.make_exam_question(d, answers=[("A", True), ("B", False)])
        tq = self.make_exam_question(t, qtype="true_false", answers=[("a) mệnh đề", True), ("b) mệnh đề", False), ("c) mệnh đề", True), ("d) mệnh đề", False)])
        sq = self.make_exam_question(s, qtype="short_answer", answers=[("42", True)])
        bq = self.make_exam_question(blank, answers=[("A", True), ("B", False)])
        wrong_tf = {str(item.id): (not bool(item.is_correct)) for item in tq.answers}
        submission = self.make_submission(
            [dq, tq, sq, bq], [[dq.answers[1].id], wrong_tf, "41", []]
        )
        # The blank answer is explicitly unanswered even though the attempt is
        # finalized; it must not become a wrong-answer misconception.
        rows = LearningHistory.query.order_by(LearningHistory.exam_question_id).all()
        self.assertEqual(len(rows), 3)
        self.assertEqual({row.answer_status for row in rows}, {"answered"})
        self.assertTrue(all(row.evidence_ref for row in rows))
        errors = ErrorObservation.query.filter_by(student_id=self.student.id, status="observed").all()
        self.assertEqual(len(errors), 3)
        self.assertEqual({row.error_code for row in errors}, {"choice_mismatch", "statement_mismatch", "short_answer_mismatch"})
        answer_texts = {row.answer.get_answer_payload().get("text") for row in errors if row.answer}
        self.assertIn("41", answer_texts)
        self.assertEqual(SubmissionAnswer.query.filter_by(question_id=bq.id).one().answer_status, "unanswered")

    def test_regrade_updates_one_fact_and_supersedes_error_without_duplicates(self):
        bank = self.make_bank_question("Regrade")
        question = self.make_exam_question(bank, answers=[("A", True), ("B", False)])
        submission = self.make_submission([question], [[question.answers[1].id]], revision=1)
        self.assertEqual(LearningHistory.query.count(), 1)
        first_row = LearningHistory.query.one()
        first_error = ErrorObservation.query.filter_by(status="observed").one()
        answer = SubmissionAnswer.query.one()
        answer.selected_answer_ids = json.dumps([question.answers[0].id])
        answer.is_correct = True
        answer.points_earned = question.points
        answer.answer_status = "answered"
        submission.grading_revision = 2
        submission.status = "graded"
        db.session.commit()
        AdaptiveEngine.update_performance(self.student.id, submission)
        self.assertEqual(LearningHistory.query.count(), 1)
        self.assertEqual(LearningHistory.query.one().id, first_row.id)
        self.assertEqual(LearningHistory.query.one().grading_revision, 2)
        self.assertEqual(ErrorObservation.query.get(first_error.id).status, "superseded")
        self.assertEqual(StudentErrorProfile.query.filter_by(status="observed").count(), 0)

        AdaptiveEngine.update_performance(self.student.id, submission)
        self.assertEqual(LearningHistory.query.count(), 1)
        self.assertEqual(ErrorObservation.query.count(), 1)

    def test_initial_diagnostic_assigns_same_frozen_item_hash_idempotently(self):
        diagnostic = Exam(
            title="Diagnostic", course_id=self.course.id, created_by=self.teacher.id,
            exam_type="exam", assessment_purpose="initial_diagnostic",
        )
        db.session.add(diagnostic)
        db.session.flush()
        bank = self.make_bank_question("Diagnostic question")
        question = ExamQuestion(
            exam_id=diagnostic.id, bank_question_id=bank.id, question_text=bank.question_text,
            question_type=bank.question_type, difficulty_level=bank.difficulty_level, points=1,
        )
        db.session.add(question)
        db.session.flush()
        db.session.add_all([
            ExamAnswer(question_id=question.id, answer_text="A", is_correct=True),
            ExamAnswer(question_id=question.id, answer_text="B", is_correct=False),
        ])
        db.session.flush()
        refresh_question_snapshot(question, bank)
        db.session.commit()
        rows = assign_diagnostic_cohort(diagnostic, self.teacher.id)
        db.session.commit()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row.common_item_hash for row in rows}, {rows[0].common_item_hash})
        self.assertEqual(DiagnosticAssignment.query.count(), 2)
        self.assertEqual(diagnostic.get_diagnostic_coverage()["item_count"], 1)
        self.assertEqual(diagnostic.get_diagnostic_coverage()["unknown_skill_count"], 1)
        assign_diagnostic_cohort(diagnostic, self.teacher.id)
        db.session.commit()
        self.assertEqual(DiagnosticAssignment.query.count(), 2)

    def test_bank_edit_advances_source_revision_without_rewriting_frozen_exam(self):
        bank = self.make_bank_question("Original")
        for index, label in enumerate(("A", "B", "C", "D")):
            db.session.add(BankQuestionOption(question_id=bank.id, option_text=label, is_correct=index == 0))
        db.session.flush()
        frozen = self.make_exam_question(bank, answers=[("A", True), ("B", False)])
        db.session.commit()
        original_revision = bank.content_revision
        original_hash = bank.content_hash
        frozen_hash = frozen.source_content_hash
        bank.question_text = "Edited in bank"
        db.session.commit()
        self.assertGreater(bank.content_revision, original_revision)
        self.assertNotEqual(bank.content_hash, original_hash)
        self.assertEqual(frozen.source_content_hash, frozen_hash)
        self.assertEqual(frozen.question_text, "Original")

    def test_selector_preserves_observed_error_context_without_claiming_mastery(self):
        node_weak = CurriculumNode(
            grade="9", chapter_code="8", chapter_name="Chương 6", lesson_code="i",
            lesson_name="Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố", category_code="1", category_name="Dạng 1",
            topic_name="Skill weak", created_by=self.teacher.id,
        )
        node_other = CurriculumNode(
            grade="9", chapter_code="8", chapter_name="Chương 6", lesson_code="i",
            lesson_name="Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố", category_code="2", category_name="Dạng 2",
            topic_name="Skill other", created_by=self.teacher.id,
        )
        db.session.add_all([node_weak, node_other])
        db.session.flush()
        weak = self.make_bank_question("Weak", topic="Skill weak", node=node_weak)
        other = self.make_bank_question("Other", topic="Skill other", node=node_other)
        for question in (weak, other):
            for index, label in enumerate(("A", "B", "C", "D")):
                db.session.add(BankQuestionOption(question_id=question.id, option_text=label, is_correct=index == 0))
        db.session.commit()
        profile = StudentErrorProfile(
            student_id=self.student.id, subject="Toán", curriculum_code=node_weak.canonical_code,
            error_code="choice_mismatch", evidence_count=2, confidence=.55, status="observed",
        )
        db.session.add(profile)
        db.session.commit()
        # APTGA no longer interprets an aggregate error count as a sufficient
        # skill estimate. Constrain the level for this one-question probe.
        selection = AdaptiveEngine.select_questions(self.student.id, "Toán", [self.bank.id], 1,
                                                     constraints={'cognitive_levels': ['thong_hieu']})
        self.assertEqual(selection["questions"][0].id, weak.id)
        self.assertEqual(selection["error_targets"][0]["curriculum_code"], node_weak.canonical_code)
        self.assertEqual(selection['ranked'][0]['role'], 'probe')
        self.assertEqual(selection['ranked'][0]['state'], 'Chưa đủ dữ liệu')

    def test_aptga_selects_new_question_for_weak_skill_and_excludes_recent(self):
        nodes = []
        for code in ('1', '2'):
            node = CurriculumNode(grade='9', chapter_code='8', chapter_name='Chương 6',
                                  lesson_code='i', lesson_name='Xác suất', category_code=code,
                                  category_name='Dạng ' + code, created_by=self.teacher.id)
            db.session.add(node)
            nodes.append(node)
        db.session.flush()
        historical_ids = []
        for session in range(2):
            questions = []
            actuals = []
            for skill, node in enumerate(nodes):
                for index in range(3):
                    bank = self.make_bank_question(f'History {session}/{skill}/{index}', node=node)
                    for option in range(4):
                        db.session.add(BankQuestionOption(question_id=bank.id, option_text=str(option), is_correct=option == 0))
                    question = self.make_exam_question(bank)
                    questions.append(question)
                    actuals.append([question.answers[1 if skill == 0 else 0].id])
                    historical_ids.append(bank.id)
            self.make_submission(questions, actuals)
        # Create strong candidate first so ID tie-breaking cannot explain the result.
        strong = self.make_bank_question('New strong', node=nodes[1])
        weak = self.make_bank_question('New weak', node=nodes[0])
        for question in (strong, weak):
            for index in range(4):
                db.session.add(BankQuestionOption(question_id=question.id, option_text=str(index), is_correct=index == 0))
        db.session.commit()
        result = AdaptiveEngine.select_questions(self.student.id, 'Toán', [self.bank.id], 1,
                                                 constraints={'cognitive_levels': ['thong_hieu']})
        self.assertEqual(result['questions'][0].id, weak.id)
        self.assertEqual(result['ranked'][0]['role'], 'remedial')
        self.assertNotIn(result['questions'][0].id, historical_ids)
        self.assertTrue(result['aptga']['skill_cognitive_mastery']['9C8-i-1||thong_hieu']['sufficient'])
        many = AdaptiveEngine.select_questions(self.student.id, 'Toán', [self.bank.id], 10,
                                               constraints={'cognitive_levels': ['thong_hieu']})
        self.assertEqual({q.id for q in many['questions']}, {weak.id, strong.id})
        self.assertEqual(many['aptga']['shortfall'], {'thong_hieu': 8})

    def test_ai_fabricated_evidence_is_rejected_and_unavailable_api_fails(self):
        profile = {
            "observed_error_evidence": [{"evidence_ref": "submission:1:answer:2:revision:1"}],
        }
        base = {
            "schema_version": "chapter6-analysis-v2", "overall_diagnosis": "Có quan sát.",
            "student_explanation": "Em sẽ luyện thêm.", "confidence": .5,
            "observed_errors": [{"curriculum_code": "9C8-i-1", "error_code": "choice_mismatch", "claim": "x", "evidence_refs": ["fake"], "confidence": .5}],
            "future_error_risks": [],
        }
        with self.assertRaises(ValueError):
            validate_evidence_analysis(base, profile)
        from services.ai_profile_analysis import AIProfileAnalyzer
        with patch.dict(os.environ, {"AI_ANALYSIS_API_URL": ""}, clear=False):
            run, _ = AIProfileAnalyzer().analyze(self.student.id, "Toán", requested_by=self.teacher.id, force=True)
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.schema_version, "lesson4-diagnostic-report-v1")
        self.assertEqual(run.get_response_data(), {})

    def test_individual_ai_request_has_frozen_comparison_without_mastery_or_quota(self):
        node = CurriculumNode(
            grade="9", chapter_code="8", chapter_name="Chương 6", lesson_code="i",
            lesson_name="Bài 4", category_code="1", category_name="Dạng 1",
            topic_name="Không gian mẫu", created_by=self.teacher.id,
        )
        db.session.add(node)
        db.session.flush()
        self.exam.assessment_purpose = "initial_diagnostic"
        bank = self.make_bank_question("Câu sai Bài 4", node=node)
        question = self.make_exam_question(bank, answers=[("A", True), ("B", False)])
        # The report accepts a finalized 12/4/6 paper, not a one-item probe.
        # Only the first response is wrong; the other 21 provide the full denominator.
        questions, actuals = [question], [[question.answers[1].id]]
        for kind, count in (("single", 11), ("true_false", 4), ("short_answer", 6)):
            for index in range(count):
                source = self.make_bank_question(f"Ngữ cảnh đúng {kind} {index}", qtype=kind, node=node)
                if kind == "true_false":
                    source.learning_metadata = json.dumps({"statements": [
                        {"curriculum_code": node.canonical_code, "cognitive_level": "thong_hieu"}
                        for _ in range(4)]})
                    frozen = self.make_exam_question(source, answers=[("a", True), ("b", False), ("c", True), ("d", False)])
                    actual = {str(answer.id): bool(answer.is_correct) for answer in frozen.answers}
                elif kind == "short_answer":
                    frozen = self.make_exam_question(source, answers=[("42", True)])
                    actual = "42"
                else:
                    frozen = self.make_exam_question(source, answers=[("A", True), ("B", False)])
                    actual = [frozen.answers[0].id]
                questions.append(frozen)
                actuals.append(actual)
        self.make_submission(questions, actuals)
        from services.ai_profile_analysis import AIProfileAnalyzer
        with patch.dict(os.environ, {"AI_ANALYSIS_API_URL": ""}, clear=False):
            run, _ = AIProfileAnalyzer().analyze(
                self.student.id, "Toán", requested_by=self.teacher.id, force=True
            )
        request_copy = run.get_request_data()
        serialized = json.dumps(request_copy, ensure_ascii=False)
        self.assertEqual(request_copy["scope"]["scope_code"], "9C8-i")
        self.assertEqual(len(request_copy["observed_error_evidence"]), 1)
        self.assertNotIn('"mastery"', serialized)
        self.assertIn("expected_answer", serialized)
        self.assertEqual(request_copy["observed_error_evidence"][0]["actual_answer"], ["B"])
        self.assertEqual(request_copy["observed_error_evidence"][0]["expected_answer"], ["A"])
        self.assertNotIn('"quota":', serialized)

    def test_teacher_report_and_ownership_controls(self):
        profile = AdaptiveEngine.analyze_performance(self.student.id, "Toán")
        payload = report_payload(self.student.id, "Toán", profile)
        report = upsert_teacher_report(self.student.id, "Toán", payload, generated_by=self.teacher.id)
        db.session.commit()
        self.assertEqual(TeacherLearningReport.query.count(), 1)
        self.assertTrue(any("future_error_risks" in key for key in report.get_payload()))
        self.assertTrue(any("chưa" in item for item in report.get_payload()["limitations"]))

        other_client = self.login_as(self.other_teacher)
        self.assertEqual(other_client.get(f"/analytics/teacher?student_id={self.student.id}", follow_redirects=True).status_code, 403)
        self.assertEqual(other_client.post(
            f"/teacher/practice/{self.student.id}/reports/{report.id}/review",
            data={"review_note": "không thuộc lớp"}, follow_redirects=False,
        ).status_code, 403)

if __name__ == "__main__":
    unittest.main()
