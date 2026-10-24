import json
import os
import unittest
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)
import config
config.load_local_environment = lambda *args, **kwargs: None

from app import app
from database import db
from models import (
    User, Course, Enrollment, DiagnosticAssignment, Exam, ExamAnswer, ExamQuestion,
    ExamSubmission, SubmissionAnswer, LearningHistory, MasterySnapshot
)


class TestDiagnosticDeleteAndExplanation(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.client = app.test_client()

        # Tạo người dùng
        self.admin = User(username='admin_test', fullname='Admin Test', role='admin', user_code='ADM001')
        self.admin.set_password('123456')

        self.teacher1 = User(username='teacher1_test', fullname='Teacher 1', role='teacher', user_code='GV001')
        self.teacher1.set_password('123456')

        self.teacher2 = User(username='teacher2_test', fullname='Teacher 2', role='teacher', user_code='GV002')
        self.teacher2.set_password('123456')

        self.student = User(username='student_test', fullname='Student Test', role='student', user_code='HS001')
        self.student.set_password('123456')

        db.session.add_all([self.admin, self.teacher1, self.teacher2, self.student])
        db.session.commit()

        # Tạo khóa học của teacher1
        self.course = Course(
            course_name='Toán 9 Test',
            subject='Toán',
            teacher_id=self.teacher1.id
        )
        db.session.add(self.course)
        db.session.commit()

        # Học sinh tham gia khóa học
        self.enrollment = Enrollment(student_id=self.student.id, course_id=self.course.id)
        db.session.add(self.enrollment)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _create_diagnostic_exam(self):
        exam = Exam(
            title='Đánh giá đầu vào · Toán 9',
            course_id=self.course.id,
            created_by=self.teacher1.id,
            assessment_purpose='initial_diagnostic',
            exam_type='exam',
            duration_minutes=30,
            is_active=True
        )
        db.session.add(exam)
        db.session.commit()

        q1 = ExamQuestion(
            exam_id=exam.id,
            question_text='Tính giá trị của biểu thức A',
            question_type='single',
            points=1.0,
            order_index=0,
            explanation='Giải chi tiết: Áp dụng hằng đẳng thức ta có kết quả là 5.'
        )
        q2 = ExamQuestion(
            exam_id=exam.id,
            question_text='Cho bảng số liệu...',
            question_type='true_false',
            points=1.0,
            order_index=1,
            explanation='Giải thích: Ý a đúng vì..., ý b sai do...'
        )
        db.session.add_all([q1, q2])
        db.session.commit()

        ans1 = ExamAnswer(question_id=q1.id, answer_text='5', is_correct=True)
        ans2 = ExamAnswer(question_id=q1.id, answer_text='10', is_correct=False)
        db.session.add_all([ans1, ans2])

        # Assignment
        assignment = DiagnosticAssignment(
            exam_id=exam.id,
            student_id=self.student.id,
            assigned_by=self.teacher1.id,
            common_item_hash='test-hash'
        )
        db.session.add(assignment)

        # Submission
        sub = ExamSubmission(
            exam_id=exam.id,
            student_id=self.student.id,
            total_score=1.0,
            max_score=2.0,
            is_graded=True,
            status='graded',
            submitted_at=datetime.utcnow()
        )
        db.session.add(sub)
        db.session.commit()

        sa = SubmissionAnswer(
            submission_id=sub.id,
            question_id=q1.id,
            selected_answer_ids=json.dumps([ans1.id]),
            is_correct=True,
            points_earned=1.0
        )
        db.session.add(sa)
        db.session.commit()

        lh = LearningHistory(
            student_id=self.student.id,
            submission_id=sub.id,
            exam_question_id=q1.id,
            subject='Toán',
            topic='Đại số',
            difficulty_band='nhan_biet',
            cognitive_level='nhan_biet',
            is_correct=True,
            normalized_score=1.0,
            points_earned=1.0,
            max_points=1.0
        )
        db.session.add(lh)
        db.session.commit()

        return exam, sub

    def test_delete_diagnostic_by_teacher(self):
        exam, sub = self._create_diagnostic_exam()
        exam_id = exam.id
        sub_id = sub.id

        # Teacher 1 (chủ khóa học) đăng nhập và xóa
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.teacher1.id)

        res = self.client.post(f'/diagnostics/{exam_id}/delete', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Kiểm tra exam đã bị xóa khỏi DB
        deleted_exam = db.session.get(Exam, exam_id)
        self.assertIsNone(deleted_exam)

        # Kiểm tra các dữ liệu phụ thuộc đã được dọn sạch
        self.assertEqual(ExamQuestion.query.filter_by(exam_id=exam_id).count(), 0)
        self.assertEqual(DiagnosticAssignment.query.filter_by(exam_id=exam_id).count(), 0)
        self.assertEqual(ExamSubmission.query.filter_by(exam_id=exam_id).count(), 0)
        self.assertEqual(LearningHistory.query.filter_by(submission_id=sub_id).count(), 0)

    def test_delete_diagnostic_forbidden_for_other_teacher(self):
        exam, _ = self._create_diagnostic_exam()
        exam_id = exam.id

        # Teacher 2 không dạy lớp này đăng nhập và cố xóa
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.teacher2.id)

        res = self.client.post(f'/diagnostics/{exam_id}/delete')
        self.assertEqual(res.status_code, 403)

        # Exam vẫn tồn tại
        self.assertIsNotNone(db.session.get(Exam, exam_id))

    def test_delete_diagnostic_forbidden_for_student(self):
        exam, _ = self._create_diagnostic_exam()
        exam_id = exam.id

        # Student đăng nhập và cố xóa
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.student.id)

        res = self.client.post(f'/diagnostics/{exam_id}/delete')
        self.assertEqual(res.status_code, 403)
        self.assertIsNotNone(db.session.get(Exam, exam_id))

    def test_explanation_in_exam_result_page(self):
        exam, sub = self._create_diagnostic_exam()

        # Student đăng nhập và xem kết quả bài làm
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.student.id)

        res = self.client.get(f'/practice/{exam.id}/result')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # Native disclosure replaces the removed inline toggle handler.
        self.assertRegex(html, r'<details\b[^>]*data-result-explanation')
        self.assertIn('Lời giải câu 1', html)
        self.assertIn('Giải chi tiết: Áp dụng hằng đẳng thức ta có kết quả là 5.', html)
        self.assertIn('Giải thích: Ý a đúng vì..., ý b sai do...', html)
        self.assertNotIn('toggleExplanation', html)

    def test_delete_diagnostic_by_admin(self):
        exam, sub = self._create_diagnostic_exam()
        exam_id = exam.id

        # Admin đăng nhập và xóa
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.admin.id)

        res = self.client.post(f'/diagnostics/{exam_id}/delete', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Kiểm tra exam đã bị xóa khỏi DB
        deleted_exam = db.session.get(Exam, exam_id)
        self.assertIsNone(deleted_exam)

    def test_teacher_view_student_submission_detail(self):
        exam, sub = self._create_diagnostic_exam()

        # Teacher 1 đăng nhập và xem chi tiết bài làm của học sinh qua query param submission_id
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.teacher1.id)

        res = self.client.get(f'/practice/{exam.id}/result?submission_id={sub.id}')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # Kiểm tra chế độ xem chi tiết được kích hoạt
        self.assertIn('Chi tiết bài làm', html)
        self.assertRegex(html, r'<details\b[^>]*data-result-explanation')
        self.assertIn('Lời giải câu 1', html)
        self.assertIn('Giải chi tiết: Áp dụng hằng đẳng thức ta có kết quả là 5.', html)
        self.assertIn('Danh sách bài nộp', html)


if __name__ == '__main__':
    unittest.main()
