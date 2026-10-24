"""Focused Phase 1 import-review contract for the active 9C8 lesson-i catalog."""
import json
import os
import unittest


os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)

SCOPE = {
    "grade": "9",
    "chapters": ["8"],
    "lessons": ["8:i"],
    "topics": ["thong_ke_xac_suat"],
}


def question(kind, source_id, text):
    data = {
        "index": 1,
        "source_position": 1,
        "source_label": text,
        "question_text": text,
        "question_type": kind,
        "source_id": source_id,
        "difficulty_level": "nhan_biet",
        "points": 1,
        "formulas": {},
        "options": [],
        "statements": [],
    }
    if kind == "single":
        data["options"] = [
            {"text": str(value), "is_correct": value == 1}
            for value in range(1, 5)
        ]
    elif kind == "short_answer":
        data["options"] = [{"text": "1/2", "is_correct": True}]
    elif kind == "true_false":
        data["statements"] = [
            {"id": chr(97 + index), "text": f"Mệnh đề {index}", "answer": index % 2 == 0}
            for index in range(4)
        ]
    return data


class TestPhase1ImportReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app
        cls.app = app
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def setUp(self):
        from database import db
        from models import QuestionBank, User
        from services.curriculum_service import seed_math9_catalog

        self.db = db
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        seed_math9_catalog()
        self.teacher = User(username="phase1", user_code="PHASE1", fullname="Phase One", role="teacher")
        db.session.add(self.teacher)
        db.session.flush()
        self.bank = QuestionBank(name="Phase 1", subject="Toán", grade="Lớp 9", created_by=self.teacher.id)
        db.session.add(self.bank)
        db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as flask_session:
            flask_session["_user_id"] = str(self.teacher.id)
            flask_session["_fresh"] = True

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.context.pop()

    def preview(self, questions):
        from models import ImportSession

        session = ImportSession(
            user_id=self.teacher.id,
            bank_id=self.bank.id,
            filename="review.tex",
            file_type="tex",
            status="preview",
        )
        session.set_parsed_questions(questions)
        self.db.session.add(session)
        self.db.session.commit()
        response = self.client.post(f"/question-banks/import/{session.id}/scope", json=SCOPE)
        self.assertEqual(response.status_code, 200, response.json)
        return session

    def test_confirm_assigns_atomic_suffixes_and_reviewed_readiness(self):
        from models import BankQuestion
        from services.practice_blueprint import readiness_error

        session = self.preview([
            question("short_answer", "9C8Ni-1S", "Kết quả thứ nhất"),
            question("short_answer", "9C8Ni-1S", "Kết quả thứ hai"),
            question("true_false", "9C8Ni-1T", "Đánh giá bốn mệnh đề"),
        ])
        preview = self.client.get(f"/question-banks/import/{session.id}/preview").json
        self.assertEqual(preview["questions"][0]["learning_metadata"]["short_answer"]["mode"], "text")
        self.assertEqual(len(preview["questions"][2]["learning_metadata"]["statements"]), 4)

        result = self.client.post(
            f"/question-banks/import/{session.id}/confirm",
            json={"bank_id": self.bank.id, "confirmation_token": preview["duplicate_report"]["revision"]},
        )
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json["imported_count"], 3)

        saved = BankQuestion.query.order_by(BankQuestion.id).all()
        self.assertEqual([row.source_id for row in saved], ["9C8Ni-1S.1", "9C8Ni-1S.2", "9C8Ni-1T.3"])
        self.assertTrue(all(row.classification_status == "teacher_confirmed" for row in saved))
        self.assertTrue(all(readiness_error(row) is None for row in saved))
        audit = json.loads(saved[0].classification_data)
        self.assertEqual(audit["reviewed_by"], self.teacher.id)
        self.assertTrue(audit["reviewed_at"].endswith("Z"))
        completed_preview = self.client.get(f"/question-banks/import/{session.id}/preview").json
        self.assertEqual(completed_preview["questions"][0]["source_id"], "9C8Ni-1S.1")

        saved[0].explanation = "Sửa lời giải không đổi ID"
        self.db.session.commit()
        self.assertEqual(saved[0].source_id, "9C8Ni-1S.1")

    def test_unready_rows_are_skipped_without_approving_old_or_invalid_data(self):
        from models import BankQuestion

        valid = question("single", "9C8Ni-1D", "Câu hợp lệ")
        invalid = question("short_answer", "9C8Ni-1S", "Câu thiếu đáp án")
        invalid["options"] = []
        session = self.preview([valid, invalid])
        result = self.client.post(f"/question-banks/import/{session.id}/confirm", json={"bank_id": self.bank.id})
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json["imported_count"], 1)
        self.assertEqual(result.json["error_count"], 1)
        self.assertFalse(result.json["completed"])
        saved = BankQuestion.query.one()
        self.assertEqual(saved.classification_status, "teacher_confirmed")
        resumed = self.client.get(f"/question-banks/import/{session.id}/preview").json
        self.assertEqual(resumed["status"], "preview")
        self.assertEqual(resumed["questions"][1]["status"], "error")
        self.assertNotEqual(resumed["questions"][1].get("saved_question_id"), saved.id)

    def test_duplicate_cleaner_ignores_the_literal_lesson_i_prefix(self):
        from services.import_duplicates import clean

        self.assertEqual(clean("%[9C8Ni-1D] Tính xác suất."), "Tính xác suất.")


if __name__ == "__main__":
    unittest.main()
