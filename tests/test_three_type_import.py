"""Import contract for the three supported bank question formats.

These tests stay at the parser/normalizer boundary so a change in a document
reader cannot reintroduce essay or multiple-choice rows into the import
preview.
"""

import tempfile
import unittest
from pathlib import Path

from services.latex_parser import parse_latex
from services.question_normalizer import normalize_question
from services.question_policy import canonical_type
from services.question_validator import validate_question


class TestThreeTypeImport(unittest.TestCase):
    def test_legacy_essay_aliases_become_short_answer_without_unsupported_error(self):
        aliases = (
            "essay",
            "tu_luan",
            "tự luận",
            "tu luan",
            "bài tập tự luận",
            "tự luận mở",
            "long_answer",
            "free_response",
        )
        for alias in aliases:
            with self.subTest(alias=alias):
                question = normalize_question({
                    "question_text": "Tính giá trị biểu thức.",
                    "question_type": alias,
                    "options": [],
                    "statements": [],
                    "explanation": "Lời giải tham khảo.",
                })
                validate_question(question)
                self.assertEqual(question["question_type"], "short_answer")
                self.assertEqual(question["type_conversion"]["to"], "short_answer")
                self.assertFalse(any("Chỉ nhận" in error for error in question["errors"]))

    def test_old_free_form_wording_without_a_type_is_short_answer(self):
        question = normalize_question({
            "question_text": "Hãy trình bày cách giải bài toán.",
            "options": [],
            "statements": [],
        })
        validate_question(question)
        self.assertEqual(question["question_type"], "short_answer")
        self.assertFalse(question["errors"])

    def test_multiple_choice_remains_rejected(self):
        question = normalize_question({
            "question_text": "Chọn các đáp án đúng.",
            "question_type": "multiple_choice",
            "options": [
                {"text": "A", "is_correct": True},
                {"text": "B", "is_correct": True},
            ],
            "statements": [],
        })
        validate_question(question)
        self.assertEqual(question["question_type"], "multiple_choice")
        self.assertTrue(any("Chỉ nhận" in error for error in question["errors"]))

    def test_latex_legacy_essay_section_is_short_answer_at_parser_boundary(self):
        source = r"""\cautl
\begin{ex}
Tính diện tích hình tròn.
\loigiai{Diện tích là ...}
\end{ex}
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy-essay.tex"
            path.write_text(source, encoding="utf-8")
            questions = parse_latex(str(path))

        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["question_type"], "short_answer")
        self.assertNotIn(questions[0]["question_type"], {"essay", "multiple_choice"})

    def test_policy_canonicalizes_labels_from_old_preview_sessions(self):
        for value in ("essay", "tu_luan", "tự luận", "đúng/sai", "truefalse"):
            with self.subTest(value=value):
                self.assertIn(canonical_type(value), {"single", "true_false", "short_answer"})


if __name__ == "__main__":
    unittest.main()
