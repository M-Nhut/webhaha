"""Targeted tests for the TeX formula and import pipeline.

Document readers are intentionally out of scope. These checks protect the
FormulaAsset contract used by LaTeX imports and existing question-bank pages.
"""

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)


class FormulaTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app

        cls.app = app
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def setUp(self):
        from database import db
        from models import User, QuestionBank

        self.db = db
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        self.user = User(
            username="formula-test",
            fullname="Formula Test",
            user_code="FORMULA",
            role="teacher",
        )
        db.session.add(self.user)
        db.session.flush()
        self.bank = QuestionBank(name="TeX bank", subject="Toán", created_by=self.user.id)
        db.session.add(self.bank)
        db.session.commit()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.context.pop()


class TestLatexImport(FormulaTestCase):
    def test_latex_parser_keeps_supported_answer_formats_and_id6(self):
        from services.latex_parser import parse_latex

        source = r"""\begin{ex}%[9C8Ni-1D.1]
Chọn một đáp án.\choice{\True 1}{2}{3}{4}
\end{ex}
\begin{ex}%[9C8Hi-2T.1]
Đánh giá.\choiceTF{\True Đúng}{Sai}{\True Đúng}{Sai}
\end{ex}
\begin{ex}%[9C8Vi-3S.1]
Điền kết quả.\shortans{3}
\end{ex}"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "questions.tex"
            path.write_text(source, encoding="utf-8")
            questions = parse_latex(str(path))

        self.assertEqual(
            [q["question_type"] for q in questions],
            ["single", "true_false", "short_answer"],
        )
        self.assertEqual(questions[0]["source_id"], "9C8Ni-1D.1")

    def test_tex_upload_uses_latex_parser_and_persists_session(self):
        from services.import_service import ImportService
        from werkzeug.datastructures import FileStorage

        with tempfile.TemporaryDirectory() as directory, patch(
            "services.import_service.UPLOAD_TEMP_DIR", directory
        ), patch(
            "services.latex_parser.parse_latex",
            return_value=[
                {
                    "question_text": "Tính x.",
                    "question_type": "short_answer",
                    "options": [],
                    "statements": [],
                }
            ],
        ) as parser:
            session = ImportService.create_and_process_session(
                self.user.id,
                FileStorage(stream=io.BytesIO(b"tex"), filename="questions.tex"),
                "questions.tex",
                self.bank.id,
            )

        parser.assert_called_once()
        self.assertEqual(session.file_type, "tex")
        self.assertEqual(session.status, "preview")


class TestFormulaAssets(FormulaTestCase):
    def test_api_dict_exposes_only_safe_formula_fields(self):
        from models import FormulaAsset

        asset = FormulaAsset(
            content_hash="legacy-binary",
            source_format="MathType",
            latex="x^2",
            conversion_status="converted",
            verification_status="verified",
        )
        self.db.session.add(asset)
        self.db.session.commit()
        payload = asset.to_api_dict()
        self.assertEqual(payload["latex"], "x^2")
        self.assertNotIn("converter_name", payload)
        self.assertNotIn("converter_version", payload)

    def test_latex_block_retry_preserves_cached_render(self):
        from models import FormulaAsset
        from services.import_service import ImportService

        asset = FormulaAsset(
            content_hash="latex-retry",
            source_format="LaTeXBlock",
            source_text=r"x^2",
            conversion_status="failed",
            verification_status="needs_review",
        )
        self.db.session.add(asset)
        self.db.session.commit()
        with patch(
            "services.latex_renderer.render_latex_block_result",
            return_value={
                "url": "/static/uploads/questions/latex_retry.svg",
                "verified": True,
                "method": "remote_tex",
                "error": None,
            },
        ):
            result = ImportService.retry_formula_asset(asset)
        self.assertTrue(result["success"])
        self.assertEqual(asset.conversion_status, "fallback_svg")
        self.assertEqual(asset.svg_cache_key, "/static/uploads/questions/latex_retry.svg")

    def test_batch_formula_api_returns_latex_without_binary(self):
        from models import FormulaAsset

        asset = FormulaAsset(
            content_hash="api-latex",
            source_format="LaTeX",
            latex=r"x^2",
            conversion_status="converted",
            verification_status="verified",
        )
        self.db.session.add(asset)
        self.db.session.commit()
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.user.id)
            session["_fresh"] = True
        response = client.post("/api/formulas/batch", json={"uuids": [asset.id]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["formulas"][asset.id]["latex"], r"x^2")


if __name__ == "__main__":
    unittest.main()
