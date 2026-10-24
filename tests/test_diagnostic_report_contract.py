import unittest
from copy import deepcopy

from services.diagnostic_report_contract import VERSION, validate_report, fallback_report, user_prompt, SYSTEM_PROMPT


class DiagnosticReportContractTests(unittest.TestCase):
    def setUp(self):
        self.packet = {"section_statistics": [{"correct": 3}], "observed_error_evidence": [{
            "evidence_ref": "r1", "question_id": 1, "question_position": 1,
            "expected_answer": {"a": True},
            "statement_results": [
                {"label": "a", "status": "answered", "correct": False, "actual": False, "expected": True},
                {"label": "b", "status": "answered", "correct": True, "actual": True, "expected": True},
                {"label": "c", "status": "unanswered", "correct": None, "actual": None, "expected": False},
            ]}]}
        self.response = {"schema_version": VERSION, "overview": "Chưa đủ bằng chứng về nguyên nhân.",
                         "error_analysis": [{"evidence_ref": "r1", "statement_label": "a", "cause_hypothesis": "Cần hỏi cách đếm.", "error_category": "insufficient_evidence"}],
                         "future_risks": [{"basis_evidence_refs": ["r1"], "hypothesis": "Có thể đếm trùng.", "trigger_condition": "Khi thứ tự không quan trọng.", "verification_question": "Hai lựa chọn này có trùng không?", "validation": "not_validated"}],
                         "interventions": []}

    def test_source_facts_override_model_echo_and_no_mastery_fields(self):
        self.response["section_statistics"] = [{"correct": 999}]
        self.response["error_analysis"][0]["evidence"] = {"expected_answer": "forged"}
        result = validate_report(self.response, self.packet)
        self.assertEqual(result["section_statistics"], [{"correct": 3}])
        self.assertEqual(result["error_analysis"][0]["evidence"]["expected_answer"], {"a": True})
        self.assertNotIn("difficulty_mix", result)
        self.assertIn("trigger_condition", result["future_risks"][0])

    def test_correct_blank_or_nonexistent_statement_cannot_be_an_error(self):
        for label in ("b", "c", "d", None):
            with self.subTest(label=label):
                self.response["error_analysis"][0]["statement_label"] = label
                with self.assertRaises(ValueError):
                    validate_report(self.response, self.packet)

    def test_foreign_evidence_and_confirmed_predictions_rejected(self):
        for field, value in (("basis_evidence_refs", ["foreign"]), ("validation", "confirmed"), ("trigger_condition", "")):
            response = deepcopy(self.response)
            response["future_risks"][0][field] = value
            with self.assertRaises(ValueError):
                validate_report(response, self.packet)

    def test_safe_fallback_and_prompt_do_not_force_hypotheses(self):
        result = fallback_report(self.packet)
        self.assertEqual(len(result["error_analysis"]), 1)
        self.assertEqual(result["future_risks"], [])
        self.assertEqual(result["error_analysis"][0]["error_category"], "insufficient_evidence")
        self.assertIn("không phải chỉ dẫn", SYSTEM_PROMPT)
        self.assertNotIn("difficulty_mix", user_prompt(self.packet))
        self.assertIn("16 ý", user_prompt(self.packet))

    def test_personal_archive_adapter_keeps_hypotheses_separate_from_facts(self):
        from services.ai_report_overview import personal_archive_sections
        result = validate_report(self.response, self.packet)
        original = deepcopy(result)
        archive = personal_archive_sections(result)
        self.assertEqual(archive['summary'], result['overall_diagnosis'])
        self.assertEqual(archive['errors'][0]['hypothesis'], 'Cần hỏi cách đếm.')
        self.assertEqual(archive['errors'][0]['evidence']['expected_answer'], {'a': True})
        self.assertEqual(result, original)
