import datetime as dt
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)

# Prevent a developer .env.local from replacing the isolated database before
# the application is imported during unittest discovery.
import config
config.load_local_environment = lambda *args, **kwargs: None


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class TestAdaptivePersonalization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app
        cls.app = app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def setUp(self):
        from database import db
        from models import Course, Enrollment, Exam, QuestionBank, User
        self.db = db
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="teacher-adaptive", fullname="Teacher", user_code="GVA", role="teacher")
        self.student = User(username="student-adaptive", fullname="Student", user_code="HSA", role="student")
        db.session.add_all([self.teacher, self.student])
        db.session.flush()
        self.course = Course(course_name="Toán 9", subject="Toán", teacher_id=self.teacher.id)
        db.session.add(self.course)
        db.session.flush()
        db.session.add(Enrollment(student_id=self.student.id, course_id=self.course.id, status="active"))
        self.bank = QuestionBank(name="Chương 6", subject="Toán", grade="9", created_by=self.teacher.id)
        db.session.add(self.bank)
        db.session.flush()
        self.exam = Exam(title="Bài thích ứng", course_id=self.course.id, created_by=self.teacher.id, exam_type="practice")
        db.session.add(self.exam)
        db.session.commit()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def _bank_question(self, text, topic, level, priority=0, excluded=False, band=None):
        from models import BankQuestion, BankQuestionOption
        question = BankQuestion(
            bank_id=self.bank.id, question_text=text, question_type="single", difficulty_level=level,
            topic=topic, created_by=self.teacher.id, adaptive_priority=priority,
            adaptive_excluded=excluded, difficulty_band=band,
        )
        self.db.session.add(question)
        self.db.session.flush()
        for index in range(4):
            self.db.session.add(BankQuestionOption(
                question_id=question.id, option_text=str(index + 1), is_correct=index == 0, order_index=index
            ))
        self.db.session.flush()
        return question

    def _exam_answer(self, bank_question, points, seconds):
        from models import ExamAnswer, ExamQuestion, SubmissionAnswer
        question = ExamQuestion(
            exam_id=self.exam.id, bank_question_id=bank_question.id, question_text=bank_question.question_text,
            question_type="single", difficulty_level=bank_question.difficulty_level, points=1,
        )
        self.db.session.add(question)
        self.db.session.flush()
        self.db.session.add_all([
            ExamAnswer(question_id=question.id, answer_text="1", is_correct=True),
            ExamAnswer(question_id=question.id, answer_text="2", is_correct=False),
        ])
        answer = SubmissionAnswer(
            question_id=question.id, selected_answer_ids="[]", points_earned=points,
            is_correct=points == 1, time_spent_seconds=seconds,
        )
        return question, answer

    def _chapter6_question(self):
        from models import CurriculumNode
        node = CurriculumNode(
            grade="9", chapter_code="6", chapter_name="Một số yếu tố thống kê và xác suất",
            lesson_code="4", lesson_name="Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố",
            category_code="3", category_name="Tính xác suất của biến cố trong trò chơi Tung đồng xu",
            topic_name="Thống kê và xác suất", created_by=self.teacher.id,
        )
        self.db.session.add(node)
        self.db.session.flush()
        question = self._bank_question("Tung đồng xu và tính xác suất xuất hiện mặt ngửa", "Thống kê và xác suất", "thong_hieu")
        question.grade = "9"
        question.chapter = "6"
        question.section = "4"
        question.question_category = "3"
        question.curriculum_node_id = node.id
        self.db.session.flush()
        return question

    def _initialize_lesson4_profile(self, status="completed"):
        from models import DiagnosticAssignment, Exam, ExamAnswer, ExamQuestion
        from services.diagnostic_service import common_item_hash

        bank_question = self._chapter6_question()
        diagnostic = Exam(
            title="Đầu vào Bài 4", course_id=self.course.id,
            created_by=self.teacher.id, exam_type="exam",
            assessment_purpose="initial_diagnostic", is_active=True,
        )
        self.db.session.add(diagnostic)
        self.db.session.flush()
        question = ExamQuestion(
            exam_id=diagnostic.id, bank_question_id=bank_question.id,
            question_text=bank_question.question_text, question_type="single",
            difficulty_level="thong_hieu", curriculum_code=bank_question.curriculum_node.canonical_code,
            points=1,
        )
        self.db.session.add(question)
        self.db.session.flush()
        self.db.session.add_all([
            ExamAnswer(question_id=question.id, answer_text="A", is_correct=True),
            ExamAnswer(question_id=question.id, answer_text="B", is_correct=False),
        ])
        self.db.session.flush()
        assignment = DiagnosticAssignment(
            exam_id=diagnostic.id, student_id=self.student.id,
            common_item_hash=common_item_hash(diagnostic), status=status,
        )
        self.db.session.add(assignment)
        self.db.session.commit()
        return diagnostic, assignment

    def test_blank_finalized_diagnostic_initializes_unknown_profile_once(self):
        from adaptive_engine import AdaptiveEngine
        from models import MasterySnapshot
        from services.diagnostic_service import learner_profile_state

        diagnostic, assignment = self._initialize_lesson4_profile(status="assigned")
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.student.id)
            session["_fresh"] = True
        response = client.post(f"/practice/{diagnostic.id}/take", data={}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.db.session.refresh(assignment)
        self.assertEqual(assignment.status, "completed")
        self.assertTrue(learner_profile_state(self.student.id, "Toán")["initialized"])
        self.assertEqual(MasterySnapshot.query.filter_by(student_id=self.student.id, subject="Toán").count(), 1)
        profile = AdaptiveEngine.analyze_performance(self.student.id, "Toán")
        self.assertTrue(all(cell["mastery"] is None for cell in profile["practice_skill_mastery"].values()))

    def test_submission_creates_weighted_mastery_and_is_idempotent(self):
        from adaptive_engine import AdaptiveEngine
        from models import ExamSubmission, LearningHistory, MasterySnapshot, StudentPerformance
        hard = self._bank_question("Câu xác suất khó", "Thống kê và xác suất", "thong_hieu", band="hard")
        easy = self._bank_question("Câu xác suất dễ", "Thống kê và xác suất", "nhan_biet", band="easy")
        submission = ExamSubmission(
            exam_id=self.exam.id, student_id=self.student.id, exam_type="practice",
            submitted_at=dt.datetime.utcnow(), total_score=1.5, max_score=2, time_spent_seconds=90,
        )
        self.db.session.add(submission)
        self.db.session.flush()
        _, first = self._exam_answer(hard, .5, 55)
        _, second = self._exam_answer(easy, 1, 35)
        first.submission_id = submission.id
        second.submission_id = submission.id
        self.db.session.add_all([first, second])
        self.db.session.commit()

        AdaptiveEngine.update_performance(self.student.id, submission)
        rows = LearningHistory.query.order_by(LearningHistory.id).all()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].topic, "Thống kê và xác suất")
        self.assertEqual(rows[0].cognitive_level, "thong_hieu")
        self.assertEqual(rows[0].difficulty_band, "hard")
        self.assertEqual(rows[0].normalized_score, .5)
        self.assertEqual(rows[0].time_spent_seconds, 55)
        expected = (.5 * rows[0].weight + rows[1].weight) / (rows[0].weight + rows[1].weight)
        profile = AdaptiveEngine.analyze_performance(self.student.id, "Toán")
        self.assertAlmostEqual(profile["topic_mastery"]["Thống kê và xác suất"]["mastery"], expected, places=4)
        self.assertEqual(profile["topic_mastery"]["Thống kê và xác suất"]["interpretation"], "Khá")
        self.assertEqual(StudentPerformance.query.one().thong_hieu_accuracy, 50.0)

        AdaptiveEngine.update_performance(self.student.id, submission)
        self.assertEqual(LearningHistory.query.count(), 2)
        self.assertEqual(MasterySnapshot.query.count(), 1)

    def test_cold_start_and_four_level_difficulty_distribution(self):
        from adaptive_engine import AdaptiveEngine
        profile = AdaptiveEngine.analyze_performance(self.student.id, "Toán")
        self.assertTrue(profile["cold_start"])
        self.assertEqual(profile["thong_hieu_accuracy"], 50.0)
        self.assertEqual(
            AdaptiveEngine.recommend_difficulty(profile)["diff_config"],
            {"nhan_biet": 25, "thong_hieu": 50, "van_dung": 20, "van_dung_cao": 5},
        )
        profile["cold_start"] = False
        profile["overall_mastery"] = .85
        config = AdaptiveEngine.recommend_difficulty(profile)["diff_config"]
        self.assertEqual(config["van_dung"], 40)
        self.assertEqual(config["van_dung_cao"], 30)
        self.assertGreater(config["nhan_biet"], 0)

    def test_selector_honors_teacher_exclusion_priority_and_constraints(self):
        from adaptive_engine import AdaptiveEngine
        low = self._bank_question("Ưu tiên thấp", "Thống kê và xác suất", "thong_hieu", priority=0)
        high = self._bank_question("Ưu tiên cao", "Thống kê và xác suất", "thong_hieu", priority=100)
        excluded = self._bank_question("Đã loại", "Thống kê và xác suất", "thong_hieu", priority=100, excluded=True)
        wrong_level = self._bank_question("Sai mức", "Thống kê và xác suất", "van_dung", priority=100)
        self.db.session.commit()
        result = AdaptiveEngine.select_questions(
            self.student.id, "Toán", [self.bank.id], 2,
            constraints={"cognitive_levels": ["thong_hieu"]},
        )
        ids = [question.id for question in result["questions"]]
        self.assertEqual(ids[0], high.id)
        self.assertIn(low.id, ids)
        self.assertNotIn(excluded.id, ids)
        self.assertNotIn(wrong_level.id, ids)
        self.assertIn("dữ liệu đầu vào", result["explanation"])
        self.assertEqual(result["ranked"][0]["components"]["teacher"], 1.0)

        explicitly_excluded = AdaptiveEngine.select_questions(
            self.student.id, "Toán", [self.bank.id], 2,
            constraints={
                "cognitive_levels": ["thong_hieu"],
                "excluded_question_ids": [high.id],
            },
        )
        self.assertNotIn(high.id, [question.id for question in explicitly_excluded["questions"]])

    def test_cooldown_uses_recent_exposures_from_the_selected_subject(self):
        from adaptive_engine import AdaptiveEngine
        from models import Course, Exam, ExamQuestion, ExamSubmission, LearningHistory

        now = dt.datetime.utcnow()
        seen = self._chapter6_question()
        seen.adaptive_priority = 100
        node = seen.curriculum_node
        unseen = self._bank_question(
            "Câu Bài 4 chưa gặp", "Thống kê và xác suất", "thong_hieu"
        )
        unseen.grade = "9"
        unseen.chapter = "6"
        unseen.section = "4"
        unseen.question_category = "3"
        unseen.curriculum_node_id = node.id

        historical_question = ExamQuestion(
            exam_id=self.exam.id, bank_question_id=seen.id,
            question_text=seen.question_text, question_type="single",
            difficulty_level="thong_hieu", points=1,
            curriculum_code=node.canonical_code,
        )
        self.db.session.add(historical_question)
        self.db.session.flush()
        pending = ExamSubmission(
            exam_id=self.exam.id, student_id=self.student.id, exam_type="practice",
            submitted_at=now - dt.timedelta(days=10), status="submitted", is_graded=False,
        )
        self.db.session.add(pending)
        self.db.session.flush()
        self.db.session.add(LearningHistory(
            student_id=self.student.id, submission_id=pending.id,
            exam_question_id=historical_question.id, bank_question_id=seen.id,
            subject="Toán", curriculum_code=node.canonical_code,
            topic="Thống kê và xác suất", difficulty_band="medium",
            cognitive_level="thong_hieu", is_correct=False, normalized_score=0,
            occurred_at=now - dt.timedelta(days=10), answer_status="answered",
        ))

        other_course = Course(
            course_name="Ngữ văn 9", subject="Ngữ văn", teacher_id=self.teacher.id
        )
        self.db.session.add(other_course)
        self.db.session.flush()
        other_exam = Exam(
            title="Ba phiên môn khác", course_id=other_course.id,
            created_by=self.teacher.id, exam_type="practice",
        )
        self.db.session.add(other_exam)
        self.db.session.flush()
        for days_ago in (3, 2, 1):
            self.db.session.add(ExamSubmission(
                exam_id=other_exam.id, student_id=self.student.id,
                exam_type="practice", submitted_at=now - dt.timedelta(days=days_ago),
                status="graded", is_graded=True,
            ))
        self.db.session.commit()

        result = AdaptiveEngine.select_questions(
            self.student.id, "Toán", [self.bank.id], 1,
            constraints={"cognitive_levels": ["thong_hieu"]},
        )
        self.assertEqual([question.id for question in result["questions"]], [unseen.id])
        self.assertNotIn(
            f"{node.canonical_code}||thong_hieu",
            result["aptga"]["skill_cognitive_mastery"],
        )

        LearningHistory.query.delete()
        self.db.session.commit()
        snapshot_only = AdaptiveEngine.select_questions(
            self.student.id, "Toán", [self.bank.id], 1,
            constraints={"cognitive_levels": ["thong_hieu"]},
        )
        self.assertEqual(
            [question.id for question in snapshot_only["questions"]], [unseen.id]
        )

        newer_exam = Exam(
            title="Ba phiên Toán mới hơn", course_id=self.course.id,
            created_by=self.teacher.id, exam_type="practice",
        )
        self.db.session.add(newer_exam)
        self.db.session.flush()
        self.db.session.add(ExamQuestion(
            exam_id=newer_exam.id, bank_question_id=unseen.id,
            question_text=unseen.question_text, question_type="single",
            difficulty_level="thong_hieu", points=1,
            curriculum_code=node.canonical_code,
        ))
        for days_ago in (9, 8, 7):
            self.db.session.add(ExamSubmission(
                exam_id=newer_exam.id, student_id=self.student.id,
                exam_type="practice", submitted_at=now - dt.timedelta(days=days_ago),
                status="graded", is_graded=True,
            ))
        self.db.session.commit()
        released = AdaptiveEngine.select_questions(
            self.student.id, "Toán", [self.bank.id], 1,
            constraints={"cognitive_levels": ["thong_hieu"]},
        )
        self.assertEqual([question.id for question in released["questions"]], [seen.id])

    def test_teacher_can_save_question_controls(self):
        from models import BankQuestion
        question = self._bank_question("Câu có kiểm soát", "Thống kê và xác suất", "van_dung")
        self.db.session.commit()
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.teacher.id)
            session["_fresh"] = True
        response = client.post(
            f"/question-banks/{self.bank.id}/questions/{question.id}/adaptive",
            data={"adaptive_priority": "75", "adaptive_excluded": "1", "difficulty_band": "hard"},
        )
        self.assertEqual(response.status_code, 302)
        saved = self.db.session.get(BankQuestion, question.id)
        self.assertEqual(saved.adaptive_priority, 75)
        self.assertTrue(saved.adaptive_excluded)
        self.assertEqual(saved.difficulty_band, "hard")

    def test_aptga_does_not_fill_missing_levels_with_other_questions(self):
        from adaptive_engine import AdaptiveEngine
        for index in range(8):
            self._bank_question(f"Only TH {index}", "Thống kê và xác suất", "thong_hieu")
        self.db.session.commit()
        result = AdaptiveEngine.select_questions(self.student.id, "Toán", [self.bank.id], 20)
        self.assertEqual(result['selected_count'], 6)
        self.assertEqual(result['aptga']['actual_quotas']['thong_hieu'], 6)
        self.assertEqual(result['aptga']['shortfall']['nhan_biet'], 8)
        self.assertTrue(result['aptga']['warnings'])
        self.assertEqual(len({q.id for q in result['questions']}), 6)
        self.assertTrue(all(row['role'] == 'probe' for row in result['ranked']))
        self.assertEqual(result['aptga']['ai_influence'], 0)

    def test_student_generation_refuses_short_paper(self):
        from models import Exam
        self._initialize_lesson4_profile()
        self._bank_question("Câu duy nhất", "Thống kê và xác suất", "thong_hieu")
        self.db.session.commit()
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.student.id)
            session["_fresh"] = True
        response = client.post(
            "/practice/generate",
            data={
                "subject": "Toán", "bank_ids": [str(self.bank.id)],
                "total_questions": "5", "cognitive_levels": ["thong_hieu"],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Không tạo đề", response.get_data(as_text=True))
        self.assertEqual(Exam.query.filter_by(created_by=self.student.id, exam_type="practice").count(), 0)

    def test_teacher_refuses_incomplete_fixed_draft(self):
        from models import Exam
        for index in range(5):
            self._bank_question(f"Câu {index}", "Thống kê và xác suất", "thong_hieu", priority=index)
        self.db.session.commit()
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.teacher.id)
            session["_fresh"] = True
        page = client.get(f"/teacher/practice/{self.student.id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Tạo bản nháp để duyệt", page.get_data(as_text=True))
        response = client.post(
            f"/teacher/practice/{self.student.id}/generate",
            data={
                "course_id": str(self.course.id), "bank_ids": [str(self.bank.id)],
                "total_questions": "5", "cognitive_levels": ["thong_hieu"],
                "mix_weak": "60", "mix_middle": "25", "mix_strong": "15",
                "topics": "Thống kê và xác suất",
            },
        )
        self.assertEqual(response.status_code, 302)
        draft = Exam.query.filter(Exam.title.like("Bài luyện cá nhân hóa%")).first()
        self.assertIsNone(draft)

    def test_student_profile_and_exam_pages_render_explanations(self):
        question = self._bank_question("Câu hiển thị", "Thống kê và xác suất", "thong_hieu")
        exam_question, _answer = self._exam_answer(question, 0, 0)
        self.exam.adaptive_metadata = '{"explanation":"Ưu tiên chủ đề Thống kê và xác suất."}'
        self.exam.is_active = True
        self.db.session.commit()
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.student.id)
            session["_fresh"] = True
        practice = client.get("/practice")
        progress = client.get("/practice/progress?subject=Toán")
        take = client.get(f"/practice/{self.exam.id}/take")
        self.assertEqual(practice.status_code, 200)
        self.assertEqual(progress.status_code, 200)
        self.assertEqual(take.status_code, 200)
        self.assertIn("Thông hiểu", practice.get_data(as_text=True))
        self.assertIn("Vì sao hệ thống chọn bài này?", take.get_data(as_text=True))
        self.assertIn(str(exam_question.id), take.get_data(as_text=True))

    def test_existing_submissions_are_backfilled_in_chronological_order(self):
        from app import backfill_adaptive_learning_history
        from models import ExamSubmission, LearningHistory, MasterySnapshot
        bank_question = self._bank_question("Câu lịch sử", "Thống kê và xác suất", "nhan_biet")
        first = ExamSubmission(
            exam_id=self.exam.id, student_id=self.student.id, exam_type="practice",
            submitted_at=dt.datetime(2026, 1, 1), total_score=0, max_score=1,
        )
        second = ExamSubmission(
            exam_id=self.exam.id, student_id=self.student.id, exam_type="practice",
            submitted_at=dt.datetime(2026, 1, 2), total_score=1, max_score=1,
        )
        self.db.session.add_all([first, second])
        self.db.session.flush()
        _, wrong = self._exam_answer(bank_question, 0, 20)
        _, correct = self._exam_answer(bank_question, 1, 18)
        wrong.submission_id = first.id
        correct.submission_id = second.id
        self.db.session.add_all([wrong, correct])
        self.db.session.commit()

        backfill_adaptive_learning_history()
        snapshots = MasterySnapshot.query.order_by(MasterySnapshot.created_at).all()
        self.assertEqual(LearningHistory.query.count(), 2)
        self.assertEqual(len(snapshots), 2)
        values = [json.loads(item.profile_data)["overall_mastery"] for item in snapshots]
        self.assertLess(values[0], values[1])
        backfill_adaptive_learning_history()
        self.assertEqual(LearningHistory.query.count(), 2)
        self.assertEqual(MasterySnapshot.query.count(), 2)

    def test_chapter6_profile_groups_recent_results_by_lesson_type_and_cognition(self):
        from adaptive_engine import AdaptiveEngine
        from models import ExamSubmission
        from services.chapter6_profile_service import build_chapter6_profile
        bank_question = self._chapter6_question()
        for index, score in enumerate((0, 0, 1, 1), start=1):
            submission = ExamSubmission(
                exam_id=self.exam.id, student_id=self.student.id, exam_type="practice",
                submitted_at=dt.datetime(2026, 2, index), total_score=score, max_score=1,
            )
            self.db.session.add(submission)
            self.db.session.flush()
            _, answer = self._exam_answer(bank_question, score, 40 + index)
            answer.submission_id = submission.id
            self.db.session.add(answer)
            self.db.session.commit()
            AdaptiveEngine.update_performance(self.student.id, submission)
        profile = build_chapter6_profile(self.student.id, "Toán")
        self.assertEqual(profile["topic"], "Thống kê và xác suất")
        self.assertEqual(profile["recent_window"]["answer_count"], 4)
        self.assertNotEqual(profile["student_ref"], f"student_{self.student.id}")
        result = profile["skill_results"][0]
        self.assertEqual((result["lesson"], result["exercise_type"]), ("4", "3"))
        self.assertEqual(result["cognitive_level"], "thong_hieu")
        self.assertEqual(result["recent_trend"], "improving")
        self.assertAlmostEqual(result["mastery"], .5)

    def test_ai_api_response_is_validated_saved_and_cached(self):
        from adaptive_engine import AdaptiveEngine
        from models import AIAnalysisRun, ExamSubmission
        from services.ai_profile_analysis import AIProfileAnalyzer
        bank_question = self._chapter6_question()
        submission = ExamSubmission(
            exam_id=self.exam.id, student_id=self.student.id, exam_type="practice",
            submitted_at=dt.datetime(2026, 3, 1), total_score=0, max_score=1,
        )
        self.db.session.add(submission)
        self.db.session.flush()
        _, answer = self._exam_answer(bank_question, 0, 80)
        answer.submission_id = submission.id
        self.db.session.add(answer)
        self.db.session.commit()
        AdaptiveEngine.update_performance(self.student.id, submission)
        result = {"schema_version": "lesson4-diagnostic-report-v1",
                  "overview": "Chưa đủ bằng chứng để kết luận nguyên nhân.",
                  "error_analysis": [], "future_risks": [], "interventions": []}
        fake = FakeSession([
            FakeResponse({"error": "temporary"}, status_code=500),
            FakeResponse({"choices": [{"message": {"content": json.dumps(result)}}]}),
        ])
        with patch.dict(os.environ, {
            "AI_ANALYSIS_API_URL": "https://ai.example/v1/chat/completions",
            "AI_ANALYSIS_API_KEY": "secret", "AI_ANALYSIS_MODEL": "test-model",
            "AI_ANALYSIS_RETRIES": "1",
        }):
            analyzer = AIProfileAnalyzer(http_session=fake, sleep_fn=lambda _value: None)
            run, cached = analyzer.analyze(self.student.id, "Toán", requested_by=self.teacher.id)
            cached_run, was_cached = analyzer.analyze(self.student.id, "Toán", requested_by=self.teacher.id)
        self.assertFalse(cached)
        self.assertTrue(was_cached)
        self.assertEqual(run.id, cached_run.id)
        self.assertEqual(run.status, "completed")
        self.assertEqual(AIAnalysisRun.query.count(), 1)
        self.assertEqual(len(fake.calls), 2)
        sent = json.dumps(fake.calls[1][1]["json"], ensure_ascii=False)
        self.assertNotIn(self.student.fullname, sent)
        self.assertNotIn(self.student.username, sent)
        self.assertEqual(run.get_response_data()["schema_version"], "lesson4-diagnostic-report-v1")
        self.assertNotIn("difficulty_mix", sent)

    def test_invalid_ai_result_uses_safe_fallback_and_teacher_route_renders_it(self):
        from models import AIAnalysisRun
        invalid = {"overall_diagnosis": "Bịa dạng ngoài danh mục", "confidence": 1,
                   "strengths": [], "weaknesses": [],
                   "next_objectives": [{"lesson": "9", "exercise_type": "99", "target_cognitive_level": "van_dung", "priority": 1, "recommended_question_count": 5}],
                   "difficulty_mix": {"nhan_biet": 100}, "student_explanation": "Không hợp lệ"}
        fake = FakeSession([FakeResponse({"choices": [{"message": {"content": json.dumps(invalid)}}]})])
        from services.ai_profile_analysis import AIProfileAnalyzer
        with patch.dict(os.environ, {"AI_ANALYSIS_API_URL": "https://ai.example", "AI_ANALYSIS_RETRIES": "0"}):
            run, _ = AIProfileAnalyzer(http_session=fake).analyze(self.student.id, "Toán", requested_by=self.teacher.id, force=True)
        self.assertEqual(run.status, "fallback")
        self.assertTrue(run.error_message)
        self.assertEqual(AIAnalysisRun.query.count(), 1)

        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.teacher.id)
            session["_fresh"] = True
        page = client.get(f"/teacher/practice/{self.student.id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Phân tích Chương 6", page.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
