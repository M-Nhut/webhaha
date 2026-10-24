"""Stage 0 guardrails for the existing question-import dispatch contract.

These tests lock the TeX-only import boundary so other features cannot
silently reintroduce document readers.
"""

import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.datastructures import FileStorage


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)


class TestImportDispatchContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app

        cls.app = app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def setUp(self):
        from database import db
        from models import User

        self.db = db
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        user = User(username="guard", fullname="Import Guard", user_code="GUARD", role="teacher")
        db.session.add(user)
        db.session.commit()
        self.user_id = user.id
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()
        self.temp_dir.cleanup()

    @staticmethod
    def _upload(filename):
        return FileStorage(stream=io.BytesIO(b"regression-guard"), filename=filename)

    @staticmethod
    def _validated(raw_questions, existing_questions=None):
        return {
            "questions": raw_questions,
            "stats": {"total": len(raw_questions), "valid": len(raw_questions), "warning": 0, "error": 0},
        }

    def _common_patches(self):
        return (
            patch("services.import_service.UPLOAD_TEMP_DIR", self.temp_dir.name),
            patch("services.import_service.normalize_questions", side_effect=lambda questions: questions),
            patch("services.import_service.validate_questions", side_effect=self._validated),
        )

    def test_document_formats_are_rejected_before_persisting(self):
        from services.import_service import ImportService

        for extension in ("doc", "docx", "pdf"):
            with self.subTest(extension=extension):
                with patch("services.import_service.UPLOAD_TEMP_DIR", self.temp_dir.name):
                    with self.assertRaises(ValueError) as error:
                        ImportService.create_and_process_session(
                            self.user_id,
                            self._upload(f"guard.{extension}"),
                            f"guard.{extension}",
                        )
                self.assertIn("không được hỗ trợ", str(error.exception))

    def test_tex_keeps_using_latex_parser(self):
        from services.import_service import ImportService

        raw = [{"question_text": "tex"}]
        common = self._common_patches()
        with common[0], common[1], common[2], \
             patch("services.latex_parser.parse_latex", return_value=raw) as parse:
            session = ImportService.create_and_process_session(
                self.user_id,
                self._upload("guard.tex"),
                "guard.tex",
            )

        parse.assert_called_once()
        self.assertEqual(session.file_type, "tex")
        self.assertEqual(session.get_parsed_questions(), raw)


if __name__ == "__main__":
    unittest.main()
