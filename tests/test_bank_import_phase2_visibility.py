"""Focused Phase 2 authorization contracts for the bank import wizard."""

from __future__ import annotations

import io
import os
import unittest

# Pin the database before importing the application and bypass local dotenv
# files entirely.  These tests must never discover a developer/production DB.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)
import config  # noqa: E402
config.load_local_environment = lambda project_root=config.PROJECT_ROOT: None

from app import app  # noqa: E402
from database import db  # noqa: E402
from models import BankQuestion, ImportSession, QuestionBank, User  # noqa: E402
from services.access_control import BANK_VISIBILITY_PRIVATE, BANK_VISIBILITY_SHARED  # noqa: E402


SCOPE = dict(
    grade="9",
    chapters=["8"],
    lessons=["8:i"],
    topics=["thong_ke_xac_suat"],
)


def question(label="Một"):
    return dict(
        index=1,
        question_text=f"{label} đồng xu cân đối có xác suất ra mặt ngửa bằng bao nhiêu?",
        question_type="single",
        source_id="9C8Ni-3D",
        grade="Lớp 9", chapter="8", section="i", question_category="3",
        options=[
            dict(text="1/2", is_correct=True),
            dict(text="1/3", is_correct=False),
            dict(text="1/4", is_correct=False),
            dict(text="1", is_correct=False),
        ],
        statements=[], difficulty_level="nhan_biet", points=1, formulas={},
    )


class BankImportPhase2VisibilityTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context = app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        from services.curriculum_service import seed_math9_catalog
        seed_math9_catalog()

        self.teacher = User(
            username="phase2-teacher", user_code="P2T", fullname="Teacher", role="teacher"
        )
        self.admin = User(
            username="phase2-admin", user_code="P2A", fullname="Admin", role="admin"
        )
        db.session.add_all([self.teacher, self.admin])
        db.session.flush()
        self.private = QuestionBank(
            name="Editable private destination", subject="Toán", created_by=self.teacher.id,
            visibility=BANK_VISIBILITY_PRIVATE,
        )
        # This represents an admin-created bank whose creator account was later
        # changed to teacher.  Persisted shared scope remains authoritative.
        self.own_shared = QuestionBank(
            name="Own shared read only", subject="Toán", created_by=self.teacher.id,
            visibility=BANK_VISIBILITY_SHARED,
        )
        db.session.add_all([self.private, self.own_shared])
        db.session.commit()
        self.client = app.test_client()
        self.login(self.teacher)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def login(self, user):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        from flask import g
        g.pop("_login_user", None)

    def preview(self, user=None, bank=None, label="Một"):
        user = user or self.teacher
        session = ImportSession(
            user_id=user.id,
            bank_id=bank.id if bank else None,
            filename="phase2.tex",
            file_type="tex",
            status="preview",
        )
        session.set_parsed_questions([question(label)])
        db.session.add(session)
        db.session.commit()
        return session

    def save_scope(self, session):
        response = self.client.post(
            f"/question-banks/import/{session.id}/scope", json=SCOPE
        )
        self.assertEqual(response.status_code, 200, response.json)
        return response

    def test_destination_list_and_upload_include_authorized_append_banks(self):
        page = self.client.get("/question-banks/import")
        self.assertEqual(page.status_code, 200)
        body = page.get_data(as_text=True)
        self.assertIn(self.private.name, body)
        self.assertIn(self.own_shared.name, body)

        source = (
            b"\\begin{ex}%[9C8Ni-1D.1]\n"
            b"Chon dap an.\\choice{\\True 1}{2}{3}{4}\n\\end{ex}"
        )
        malformed = self.client.post(
            "/question-banks/import/upload",
            data={"file": (io.BytesIO(source), "sample.tex"), "bank_id": "not-an-id"},
        )
        self.assertEqual(malformed.status_code, 400)
        shared_upload = self.client.post(
            "/question-banks/import/upload",
            data={"file": (io.BytesIO(source), "sample.tex"), "bank_id": str(self.own_shared.id)},
        )
        self.assertEqual(shared_upload.status_code, 200, shared_upload.json)
        self.assertEqual(ImportSession.query.count(), 1)

        allowed = self.client.post(
            "/question-banks/import/upload",
            data={"file": (io.BytesIO(source), "sample.tex"), "bank_id": str(self.private.id)},
        )
        self.assertEqual(allowed.status_code, 200, allowed.json)
        self.assertEqual(allowed.json["questions"][0]["source_id"], "9C8Ni-1D.1")

    def test_review_mutations_and_destination_switch_recheck_current_target(self):
        other = QuestionBank(
            name="Other private", subject="Toán", created_by=self.teacher.id,
            visibility=BANK_VISIBILITY_PRIVATE,
        )
        db.session.add(other)
        db.session.commit()
        session = self.preview(bank=self.private)
        self.save_scope(session)

        # Shared is now appendable; revoke by transferring private ownership.
        self.private.created_by = self.admin.id
        db.session.commit()
        update = self.client.post(
            f"/question-banks/import/{session.id}/update",
            json={"index": 0, "question": question("Changed")},
        )
        remove = self.client.post(
            f"/question-banks/import/{session.id}/remove", json={"index": 0}
        )
        switch = self.client.post(
            f"/question-banks/import/{session.id}/destination", json={"bank_id": other.id}
        )
        self.assertEqual([update.status_code, remove.status_code, switch.status_code], [400, 400, 400])
        db.session.refresh(session)
        self.assertEqual(session.bank_id, self.private.id)
        self.assertEqual(session.get_parsed_questions()[0]["question_text"], question()["question_text"])

    def test_confirm_replay_cannot_change_or_disclose_revoked_target(self):
        session = self.preview(bank=self.private)
        scoped = self.save_scope(session)
        token = scoped.json["duplicate_report"]["revision"]
        confirmed = self.client.post(
            f"/question-banks/import/{session.id}/confirm",
            json={"bank_id": self.private.id, "confirmation_token": token},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.json)
        self.assertEqual(BankQuestion.query.count(), 1)

        other = QuestionBank(
            name="Forged replay target", subject="Toán", created_by=self.teacher.id,
            visibility=BANK_VISIBILITY_PRIVATE,
        )
        db.session.add(other)
        db.session.commit()
        wrong_target = self.client.post(
            f"/question-banks/import/{session.id}/confirm",
            json={"bank_id": other.id, "confirmation_token": token},
        )
        self.assertEqual(wrong_target.status_code, 400)
        self.assertFalse((wrong_target.json or {}).get("replayed", False))

        self.private.created_by = self.admin.id
        db.session.commit()
        revoked = self.client.post(
            f"/question-banks/import/{session.id}/confirm",
            json={"bank_id": self.private.id, "confirmation_token": token},
        )
        self.assertEqual(revoked.status_code, 400)
        self.assertFalse((revoked.json or {}).get("replayed", False))
        self.assertEqual(BankQuestion.query.count(), 1)
        self.assertEqual(BankQuestion.query.filter_by(bank_id=other.id).count(), 0)

    def test_new_bank_scope_is_server_stamped_and_cross_bank_rows_stay_distinct(self):
        teacher_session = self.preview(label="Cùng nội dung")
        teacher_scope = self.save_scope(teacher_session)
        teacher_result = self.client.post(
            f"/question-banks/import/{teacher_session.id}/confirm",
            json={
                "new_bank_name": "Teacher-created import bank",
                "visibility": "shared",
                "created_by": self.admin.id,
                "confirmation_token": teacher_scope.json["duplicate_report"]["revision"],
            },
        )
        self.assertEqual(teacher_result.status_code, 200, teacher_result.json)
        teacher_bank = QuestionBank.query.filter_by(name="Teacher-created import bank").one()
        self.assertEqual((teacher_bank.created_by, teacher_bank.visibility),
                         (self.teacher.id, BANK_VISIBILITY_PRIVATE))

        self.login(self.admin)
        admin_session = self.preview(user=self.admin, label="Cùng nội dung")
        admin_scope = self.save_scope(admin_session)
        admin_result = self.client.post(
            f"/question-banks/import/{admin_session.id}/confirm",
            json={
                "new_bank_name": "Admin-created import bank",
                "visibility": "private",
                "created_by": self.teacher.id,
                "confirmation_token": admin_scope.json["duplicate_report"]["revision"],
            },
        )
        self.assertEqual(admin_result.status_code, 200, admin_result.json)
        admin_bank = QuestionBank.query.filter_by(name="Admin-created import bank").one()
        self.assertEqual((admin_bank.created_by, admin_bank.visibility),
                         (self.admin.id, BANK_VISIBILITY_SHARED))

        # Duplicate detection is destination-local: identical content in two
        # newly created banks is preserved as two distinct ready rows.
        rows = BankQuestion.query.filter(
            BankQuestion.bank_id.in_([teacher_bank.id, admin_bank.id])
        ).order_by(BankQuestion.id).all()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.classification_status == "teacher_confirmed" for row in rows))


if __name__ == "__main__":
    unittest.main()
