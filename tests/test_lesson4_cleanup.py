"""Isolated regression tests for the destructive Lesson 4 scope migration."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

from sqlalchemy import create_engine, text

from database import db
from models import (
    BankQuestion,
    BankQuestionOption,
    Course,
    CurriculumCatalogMigration,
    CurriculumNode,
    Exam,
    ExamAnswer,
    ExamQuestion,
    ExamSubmission,
    ID6Counter,
    ImportSession,
    LearningHistory,
    QuestionBank,
    SubmissionAnswer,
    User,
)
from services.lesson4_cleanup import apply_lesson4_cleanup, inspect_lesson4_cleanup
from scripts.cleanup_math9_chapter6_lesson4 import _backup_sqlite


class Lesson4CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "scope.db"
        self.engine = create_engine("sqlite:///" + str(self.path))
        db.metadata.create_all(self.engine)
        self._seed_mixed_rows()

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def _seed_mixed_rows(self):
        now = dt.datetime.utcnow()
        with self.engine.begin() as connection:
            connection.execute(User.__table__.insert(), [
                {"id": 1, "username": "teacher", "fullname": "Teacher", "user_code": "T1", "role": "teacher"},
                {"id": 2, "username": "student", "fullname": "Student", "user_code": "S1", "role": "student"},
            ])
            connection.execute(Course.__table__.insert().values(
                id=1, course_name="Toán 9", subject="Toán", teacher_id=1
            ))
            connection.execute(QuestionBank.__table__.insert().values(
                id=1, name="Mixed", subject="Toán", grade="9", created_by=1
            ))
            connection.execute(CurriculumNode.__table__.insert(), [
                {
                    "id": 1, "grade": "9", "chapter_code": "6",
                    "chapter_name": "Một số yếu tố thống kê và xác suất",
                    "lesson_code": "4",
                    "lesson_name": "Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố",
                    "category_code": "1", "category_name": "Viết tập hợp không gian mẫu",
                    "canonical_code": "9C6-4-1", "is_active": True,
                    "catalog_version": "math9-c6-v4",
                },
                {
                    "id": 2, "grade": "9", "chapter_code": "6",
                    "chapter_name": "Một số yếu tố thống kê và xác suất",
                    "lesson_code": "1", "lesson_name": "Dữ liệu",
                    "category_code": "1", "category_name": "Biểu đồ",
                    "canonical_code": "9C6-1-1", "is_active": True,
                    "catalog_version": "math9-c6-v4",
                },
            ])
            connection.execute(BankQuestion.__table__.insert(), [
                {
                    "id": 1, "bank_id": 1, "created_by": 1, "question_text": "Không gian mẫu",
                    "question_type": "single", "difficulty_level": "nhan_biet",
                    "curriculum_node_id": 1, "grade": "Lớp 9", "chapter": "6",
                    "section": "4", "question_category": "1", "id6_scope": "9C6-4-1",
                    "id6_sequence": 1, "source_id": "9C6N4-1D.1",
                },
                {
                    "id": 2, "bank_id": 1, "created_by": 1, "question_text": "Biểu đồ",
                    "question_type": "single", "difficulty_level": "nhan_biet",
                    "curriculum_node_id": 2, "grade": "Lớp 9", "chapter": "6",
                    "section": "1", "question_category": "1", "id6_scope": "9C6-1-1",
                    "id6_sequence": 1, "source_id": "9C6N1-1D.1",
                },
            ])
            connection.execute(BankQuestionOption.__table__.insert(), [
                {"id": 1, "question_id": 1, "option_text": "A", "is_correct": True},
                {"id": 2, "question_id": 2, "option_text": "A", "is_correct": True},
            ])
            connection.execute(ID6Counter.__table__.insert(), [
                {"scope": "9C6-4-1", "last_sequence": 1},
                {"scope": "9C6-1-1", "last_sequence": 1},
            ])
            connection.execute(Exam.__table__.insert(), [
                {"id": 1, "title": "Mixed form", "course_id": 1, "created_by": 1, "question_bank_id": 1},
                {"id": 2, "title": "Retained form", "course_id": 1, "created_by": 1, "question_bank_id": 1},
            ])
            connection.execute(ExamQuestion.__table__.insert(), [
                {"id": 1, "exam_id": 1, "question_text": "Không gian mẫu", "question_type": "single", "bank_question_id": 1, "curriculum_code": "9C6-4-1", "points": 1},
                {"id": 2, "exam_id": 1, "question_text": "Biểu đồ", "question_type": "single", "bank_question_id": 2, "curriculum_code": "9C6-1-1", "points": 1},
                {"id": 3, "exam_id": 2, "question_text": "Không gian mẫu", "question_type": "single", "bank_question_id": 1, "curriculum_code": "9C6-4-1", "points": 1},
            ])
            connection.execute(ExamAnswer.__table__.insert(), [
                {"id": 1, "question_id": 1, "answer_text": "A", "is_correct": True},
                {"id": 2, "question_id": 2, "answer_text": "A", "is_correct": True},
                {"id": 3, "question_id": 3, "answer_text": "A", "is_correct": True},
            ])
            connection.execute(ExamSubmission.__table__.insert(), [
                {"id": 1, "exam_id": 1, "student_id": 2, "submitted_at": now, "is_graded": True, "status": "graded"},
                {"id": 2, "exam_id": 2, "student_id": 2, "submitted_at": now, "is_graded": True, "status": "graded"},
            ])
            connection.execute(SubmissionAnswer.__table__.insert(), [
                {"id": 1, "submission_id": 1, "question_id": 1, "selected_answer_ids": "[1]", "is_correct": True, "answer_status": "answered"},
                {"id": 2, "submission_id": 1, "question_id": 2, "selected_answer_ids": "[2]", "is_correct": True, "answer_status": "answered"},
                {"id": 3, "submission_id": 2, "question_id": 3, "selected_answer_ids": "[3]", "is_correct": True, "answer_status": "answered"},
            ])
            connection.execute(LearningHistory.__table__.insert(), [
                {"id": 1, "student_id": 2, "submission_id": 1, "exam_question_id": 1, "bank_question_id": 1, "subject": "Toán", "curriculum_code": "9C6-4-1", "topic": "Xác suất", "difficulty_band": "easy", "cognitive_level": "nhan_biet", "is_correct": True, "normalized_score": 1, "points_earned": 1, "max_points": 1, "weight": 1},
                {"id": 2, "student_id": 2, "submission_id": 1, "exam_question_id": 2, "bank_question_id": 2, "subject": "Toán", "curriculum_code": "9C6-1-1", "topic": "Biểu đồ", "difficulty_band": "easy", "cognitive_level": "nhan_biet", "is_correct": True, "normalized_score": 1, "points_earned": 1, "max_points": 1, "weight": 1},
                {"id": 3, "student_id": 2, "submission_id": 2, "exam_question_id": 3, "bank_question_id": 1, "subject": "Toán", "curriculum_code": "9C6-4-1", "topic": "Xác suất", "difficulty_band": "easy", "cognitive_level": "nhan_biet", "is_correct": True, "normalized_score": 1, "points_earned": 1, "max_points": 1, "weight": 1},
            ])
            connection.execute(CurriculumCatalogMigration.__table__.insert().values(
                migration_key="old-catalog", catalog_version="math9-c6-v4", status="applied",
                applied_at=now, snapshot_json=json.dumps({"codes": ["9C6-1-1", "9C6-4-1"]}),
                after_fingerprint="old",
            ))

    def test_mixed_exam_is_removed_as_a_whole_and_retained_evidence_survives(self):
        preview = inspect_lesson4_cleanup(self.engine)
        self.assertEqual(preview["counts"]["curriculum_node"], 1)
        self.assertEqual(preview["counts"]["bank_question"], 1)
        self.assertEqual(preview["counts"]["exam"], 1)
        self.assertEqual(preview["mixed_exam_policy"], "delete_whole_exam_if_any_item_is_outside_scope")
        report = apply_lesson4_cleanup(self.engine, preview["plan_fingerprint"])
        self.assertEqual(report["status"], "applied")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("select count(*) from curriculum_node")).scalar(), 1)
            self.assertEqual(connection.execute(text("select canonical_code from curriculum_node")).scalar(), "9C6-4-1")
            self.assertEqual(connection.execute(text("select count(*) from bank_question")).scalar(), 1)
            self.assertEqual(connection.execute(text("select count(*) from exam")).scalar(), 1)
            self.assertEqual(connection.execute(text("select count(*) from exam_submission")).scalar(), 1)
            self.assertEqual(connection.execute(text("select count(*) from learning_history")).scalar(), 1)
            self.assertEqual(connection.execute(text("select count(*) from exam_answer")).scalar(), 1)
            self.assertEqual(connection.execute(text("select count(*) from bank_question_option")).scalar(), 1)
            self.assertEqual(connection.exec_driver_sql("PRAGMA integrity_check").scalar(), "ok")
            self.assertEqual(connection.execute(text("select count(*) from user")).scalar(), 2)
            self.assertEqual(connection.execute(text("select count(*) from course")).scalar(), 1)

    def test_active_unclassified_import_is_reported_and_not_guessed(self):
        with self.engine.begin() as connection:
            connection.execute(ImportSession.__table__.insert().values(
                id="unknown", user_id=1, filename="unknown.tex", file_type="tex",
                status="preview", parsed_data="[]",
                expires_at=dt.datetime.utcnow() + dt.timedelta(hours=1),
            ))
            connection.execute(ImportSession.__table__.insert().values(
                id="retained", user_id=1, filename="lesson4.tex", file_type="tex",
                status="preview", parsed_data="[]",
                scope_data=json.dumps({"grade": "9", "chapters": ["6"], "lessons": ["6:4"], "topics": ["thong_ke_xac_suat"]}),
                expires_at=dt.datetime.utcnow() + dt.timedelta(hours=1),
            ))
        preview = inspect_lesson4_cleanup(self.engine)
        self.assertIn("unknown", preview["unknown"]["import_session"])
        report = apply_lesson4_cleanup(self.engine)
        self.assertIn("unknown", report["unknown"]["import_session"])
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("select count(*) from import_session where id='unknown'")).scalar(), 1)
            self.assertEqual(connection.execute(text("select count(*) from import_session where id='retained'")).scalar(), 1)

    def test_sqlite_backup_is_consistent_before_apply(self):
        backup, integrity = _backup_sqlite(self.path, Path(self.temp.name) / "backups")
        self.assertTrue(backup.is_file())
        self.assertEqual(integrity, "ok")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("select count(*) from user")).scalar(), 2)


if __name__ == "__main__":
    unittest.main()
