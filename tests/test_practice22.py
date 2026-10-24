"""Fixed-paper acceptance tests, isolated before app imports."""
import datetime as dt
import json
import os
import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)
import config
config.load_local_environment = lambda *args, **kwargs: None
from app import app
from database import db
from models import User, Course, Enrollment, QuestionBank, BankQuestion, BankQuestionOption, CurriculumNode, DiagnosticAssignment, Exam, ExamAnswer, ExamQuestion, ExamSubmission, MasterySnapshot, PracticeSession, SubmissionAnswer
from adaptive_engine import AdaptiveEngine
from services import aptga, practice_blueprint as blueprint
import services.practice_selector as selector
from services.practice_evidence import learning_rows, statement_results
from services.practice_selector import skill_targets, progression, select_fixed
from services.database_startup import migrate_existing_sqlite_schema, table_columns


class FixedPaperTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.teacher = User(username="teacher22", fullname="GV", user_code="T22", role="teacher")
        self.student = User(username="student22", fullname="HS", user_code="S22", role="student")
        self.other = User(username="other22", fullname="Khác", user_code="O22", role="student")
        db.session.add_all([self.teacher, self.student, self.other])
        db.session.flush()
        self.course = Course(course_name="Toán 9", subject="Toán", teacher_id=self.teacher.id)
        self.bank = QuestionBank(name="Bài 4", subject="Toán", grade="9", created_by=self.teacher.id)
        db.session.add_all([self.course, self.bank])
        db.session.flush()
        db.session.add_all([Enrollment(student_id=s.id, course_id=self.course.id, status="active") for s in (self.student, self.other)])
        for i, skill in enumerate(blueprint.SKILLS, 1):
            node = CurriculumNode(grade="9", chapter_code="8", chapter_name="Xác suất", lesson_code="i", lesson_name="Bài 4",
                                  category_code=str(i), category_name=skill, canonical_code=skill)
            db.session.add(node)
            db.session.flush()
            for level in blueprint.LEVELS:
                for kind in blueprint.TYPE_QUOTAS:
                    data = ({"statements": [{"curriculum_code": skill, "cognitive_level": level} for _ in range(4)]}
                            if kind == "true_false" else {"short_answer": {"mode": "numeric", "tolerance": "0"}} if kind == "short_answer" else {})
                    q = BankQuestion(bank_id=self.bank.id, created_by=self.teacher.id, question_text=f"{skill}-{level}-{kind}",
                        question_type=kind, difficulty_level=level, curriculum_node_id=node.id,
                        chapter="8", section="i", grade="9", question_category=str(i), learning_metadata=json.dumps(data),
                        classification_status="teacher_confirmed")
                    db.session.add(q)
                    db.session.flush()
                    for index in range(1 if kind == "short_answer" else 4):
                        db.session.add(BankQuestionOption(question_id=q.id, option_text="1/2" if kind == "short_answer" else str(index),
                            is_correct=index == 0, order_index=index))
        db.session.commit()
        # A completed common diagnostic initializes the profile independently
        # of whether all 32 skill cells have evidence.
        diagnostic = Exam(title="Đầu vào Chương 8", course_id=self.course.id, created_by=self.teacher.id,
                          question_bank_id=self.bank.id, exam_type="exam",
                          assessment_purpose="initial_diagnostic", is_active=True)
        db.session.add(diagnostic)
        db.session.flush()
        from services.diagnostic_service import common_diagnostic_selection
        from services.personalization_evidence import refresh_question_snapshot
        from services.source_resolver import attach_source_manifest
        selected = common_diagnostic_selection(BankQuestion.query.all())
        self.assertEqual(selected["status"], "ready")
        pairs = []
        for index, source in enumerate(selected["questions"]):
            frozen = ExamQuestion(exam_id=diagnostic.id, bank_question_id=source.id,
                question_text=source.question_text, question_type=source.question_type,
                difficulty_level=source.difficulty_level, curriculum_code=source.curriculum_node.canonical_code,
                order_index=index, points=1)
            db.session.add(frozen)
            db.session.flush()
            for option in source.options:
                db.session.add(ExamAnswer(question_id=frozen.id, answer_text=option.option_text,
                    is_correct=option.is_correct))
            db.session.flush()
            refresh_question_snapshot(frozen, source)
            pairs.append((frozen, source))
        attach_source_manifest(diagnostic, self.course, pairs, bank_ids=[self.bank.id])
        db.session.flush()
        from services.diagnostic_service import common_item_hash
        db.session.add(DiagnosticAssignment(
            exam_id=diagnostic.id, student_id=self.student.id,
            common_item_hash=common_item_hash(diagnostic), status="completed",
        ))
        db.session.commit()
        # A completed flag alone no longer initializes a learner. Persist the
        # finalized blank entry attempt; leave all skill cells honestly unknown.
        initial_submission = ExamSubmission(exam_id=diagnostic.id, student_id=self.student.id,
            exam_type="exam", submitted_at=dt.datetime.utcnow()-dt.timedelta(days=1),
            finalized_at=dt.datetime.utcnow()-dt.timedelta(days=1), status="graded", is_graded=True,
            total_score=0, max_score=22)
        db.session.add(initial_submission)
        db.session.commit()
        AdaptiveEngine.update_performance(self.student.id, initial_submission)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def client(self, user):
        from flask import g
        g.pop("_login_user", None)
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
        return client

    def select(self):
        return AdaptiveEngine.select_questions(self.student.id, "Toán", [self.bank.id], 5, {"blueprint": blueprint.VERSION})

    def generate(self, teacher=False):
        client = self.client(self.teacher if teacher else self.student)
        path = f"/teacher/practice/{self.student.id}/generate" if teacher else "/practice/generate"
        response = client.post(path, data={"subject": "Toán", "course_id": self.course.id, "bank_ids": [self.bank.id], "total_questions": "1"})
        self.assertEqual(response.status_code, 302)
        exam = Exam.query.filter_by(exam_type="practice").one()
        return client, exam

    def test_exact_three_dimensions_and_determinism(self):
        result = self.select()
        self.assertEqual(result["selected_count"], 22)
        audit = result["aptga"]
        self.assertEqual(audit["actual_types"], blueprint.TYPE_QUOTAS)
        self.assertEqual(audit["actual_skills"], audit["skill_targets"])
        self.assertEqual(audit["actual_quotas"], audit["desired_quotas"])
        self.assertEqual(audit["ai_influence"], 0)
        self.assertEqual([q.id for q in result["questions"]], [q.id for q in self.select()["questions"]])

    def test_profile_exposes_all_32_cells_as_unknown_before_evidence(self):
        profile = AdaptiveEngine.analyze_performance(self.student.id, "Toán")
        self.assertEqual(len(profile["practice_skill_mastery"]), 32)
        self.assertTrue(all(cell["mastery"] is None for cell in profile["practice_skill_mastery"].values()))

    def test_missing_type_and_unreviewed_statements_block_paper(self):
        for q in BankQuestion.query.filter_by(question_type="true_false").all():
            q.learning_metadata = None
        db.session.commit()
        result = self.select()
        self.assertEqual(result["questions"], [])
        self.assertIn("4 ý", result["explanation"])
        client = self.client(self.student)
        client.post("/practice/generate", data={"subject": "Toán", "bank_ids": [self.bank.id]})
        self.assertEqual(Exam.query.filter_by(exam_type="practice").count(), 0)

    def test_unconfirmed_classification_is_not_an_approved_practice_question(self):
        BankQuestion.query.update({BankQuestion.classification_status: "suggested"})
        db.session.commit()
        result = self.select()
        self.assertEqual(result["questions"], [])
        self.assertIn("chưa được giáo viên xác nhận", result["explanation"])

    def test_teacher_publish_preserves_snapshot_and_target_access(self):
        client, exam = self.generate(teacher=True)
        self.assertFalse(exam.is_active)
        self.assertEqual(exam.get_adaptive_metadata()["student_id"], self.student.id)
        ids = [q.id for q in exam.questions]
        self.assertEqual(client.get(f"/teacher/practice/drafts/{exam.id}").status_code, 200)
        response = client.post(f"/teacher/practice/drafts/{exam.id}", data={"title":"Bản đã duyệt", "duration_minutes":"40", "is_active":"1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual([q.id for q in exam.questions], ids)
        self.assertTrue(exam.is_active)
        self.assertEqual(self.client(self.other).get(f"/practice/{exam.id}/take").status_code, 403)

    def test_student_grades_tf_and_numeric_then_updates_evidence(self):
        client, exam = self.generate()
        page = client.get(f"/practice/{exam.id}/take")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Phần III", page.get_data(as_text=True))
        payload = {}
        for q in exam.questions:
            if q.question_type == "single":
                payload[f"q_{q.id}"] = str(next(a.id for a in q.answers if a.is_correct))
            elif q.question_type == "short_answer":
                payload[f"q_{q.id}_text"] = "0,5"
            else:
                for index, a in enumerate(q.answers):
                    payload[f"q_{q.id}_ans_{a.id}"] = str(int(a.is_correct if index < 3 else not a.is_correct))
        self.assertEqual(client.post(f"/practice/{exam.id}/take", data=payload).status_code, 302)
        sub = ExamSubmission.query.filter_by(exam_id=exam.id).one()
        self.assertTrue(sub.is_graded)
        self.assertAlmostEqual(sub.total_score, 8.)
        self.assertAlmostEqual(sub.max_score, 10.)
        tf = next(a for a in sub.answers if a.question.question_type == "true_false")
        self.assertEqual(tf.points_earned, .5)
        self.assertEqual(sum(s["correct"] for s in statement_results(tf)), 3)
        atomic = [r for r in learning_rows([sub]) if r.exam_question_id == tf.question_id]
        cell = aptga.summarize(atomic)
        self.assertEqual(cell["mastery"], .75)
        self.assertEqual(cell["distinct_count"], 1)
        self.assertEqual(sum(r.evidence_weight for r in atomic), 1.)
        self.assertFalse(cell["sufficient"])
        self.assertTrue(all(q.id not in {r.bank_question_id for r in learning_rows([sub])} for q in self.select()["questions"]))
        # Frozen labels must not change when bank metadata changes.
        before = statement_results(tf)
        tf.question.bank_question.learning_metadata = "{}"
        self.assertEqual(statement_results(tf), before)

    def test_continue_claim_uses_updated_profile_once_and_end_is_persisted(self):
        client, exam = self.generate()
        payload = {}
        for question in exam.questions:
            if question.question_type == "single":
                payload[f"q_{question.id}"] = str(next(answer.id for answer in question.answers if answer.is_correct))
            elif question.question_type == "short_answer":
                payload[f"q_{question.id}_text"] = "0,5"
            else:
                for answer in question.answers:
                    payload[f"q_{question.id}_ans_{answer.id}"] = str(int(bool(answer.is_correct)))
        client.post(f"/practice/{exam.id}/take", data=payload)
        submission = ExamSubmission.query.filter_by(exam_id=exam.id).one()
        session = PracticeSession.query.one()
        self.assertEqual(session.status, "awaiting_decision")
        self.assertEqual(session.last_submission_id, submission.id)
        self.assertIsNotNone(MasterySnapshot.query.filter_by(submission_id=submission.id).first())
        page = client.get(f"/practice/{exam.id}/result").get_data(as_text=True)
        self.assertIn("Tiếp tục luyện", page)

        response = client.post(f"/practice/submissions/{submission.id}/continue", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Exam.query.filter_by(exam_type="practice").count(), 2)
        db.session.refresh(session)
        self.assertEqual(session.status, "active")
        # A stale/double click cannot create another paper.
        client.post(f"/practice/submissions/{submission.id}/continue", follow_redirects=False)
        self.assertEqual(Exam.query.filter_by(exam_type="practice").count(), 2)
        self.assertEqual(self.client(self.other).post(
            f"/practice/submissions/{submission.id}/end", follow_redirects=False
        ).status_code, 403)

    def test_end_decision_is_persisted_and_stale_continue_cannot_reopen(self):
        client, exam = self.generate()
        client.post(f"/practice/{exam.id}/take", data={})
        submission = ExamSubmission.query.filter_by(exam_id=exam.id).one()
        session = PracticeSession.query.one()
        self.assertEqual(session.status, "awaiting_decision")
        self.assertEqual(client.post(
            f"/practice/submissions/{submission.id}/end", follow_redirects=False
        ).status_code, 302)
        db.session.refresh(session)
        self.assertEqual(session.status, "ended")
        client.post(f"/practice/submissions/{submission.id}/continue", follow_redirects=False)
        self.assertEqual(Exam.query.filter_by(exam_type="practice").count(), 1)

    def test_diagnostic_report_statistics_use_full_paper_not_only_errors(self):
        from services.diagnostic_report_contract import enrich_packet
        client, exam = self.generate()
        client.post(f"/practice/{exam.id}/take", data={})
        submission = ExamSubmission.query.filter_by(exam_id=exam.id).one()
        packet = enrich_packet({"observed_error_evidence": []}, submission.student_id, exam.course.subject)
        self.assertEqual(packet["target_submission_id"], submission.id)
        stats = packet["section_statistics"]
        self.assertEqual([row["total"] for row in stats], [12, 16, 6])
        self.assertEqual([row["unanswered"] for row in stats], [12, 16, 6])
        self.assertEqual([row["wrong"] for row in stats], [0, 0, 0])
        self.assertEqual([row["correct_percent"] for row in stats], [0, 0, 0])

    def test_unavailable_bank_does_not_consume_continue_decision(self):
        client, exam = self.generate()
        client.post(f"/practice/{exam.id}/take", data={})
        submission = ExamSubmission.query.filter_by(exam_id=exam.id).one()
        session = PracticeSession.query.one()
        self.assertEqual(session.status, "awaiting_decision")
        self.bank.is_active = False
        db.session.commit()
        client.post(f"/practice/submissions/{submission.id}/continue", follow_redirects=False)
        db.session.refresh(session)
        self.assertEqual(session.status, "awaiting_decision")
        self.assertEqual(Exam.query.filter_by(exam_type="practice").count(), 1)

    def test_short_rules_and_tf_table(self):
        for correct, points in enumerate((0, .1, .25, .5, 1)):
            self.assertEqual(blueprint.TF_POINTS[correct], points)
        self.assertEqual(blueprint.grade_short("0,5", ["1/2"], {"mode":"numeric"}), (True, "answered"))
        self.assertEqual(blueprint.grade_short("0.49", ["1/2"], {"mode":"numeric", "tolerance":"0.01"}), (True, "answered"))
        self.assertEqual(blueprint.grade_short("", ["1/2"], {"mode":"numeric"}), (False, "unanswered"))
        self.assertEqual(blueprint.grade_short("1/0", ["1/2"], {"mode":"numeric"}), (False, "answered"))
        self.assertEqual(blueprint.grade_short("0.5", ["1/2"], {"mode":"text"}), (False, "answered"))

    def test_knowledge_weights_and_stable_progression(self):
        base = skill_targets({})
        self.assertEqual(list(base.values()), [3,3,3,3,3,3,2,2])
        weak = {"9C8-i-4||thong_hieu": dict(mastery=.1, sufficiency=1., repetition=1.)}
        target = skill_targets(weak)
        self.assertGreater(target["9C8-i-4"], base["9C8-i-4"])
        self.assertEqual(sum(target.values()), 22)
        self.assertTrue(all(1 <= value <= 5 for value in target.values()))
        rows = [SimpleNamespace(submission_id=i//3, occurred_at=dt.datetime(2026,1,1+i//3), normalized_score=1.,
                  question_content_hash=str(i), bank_question_id=i+1, exam_question_id=i+1,
                  curriculum_code="9C8-i-4", cognitive_level="thong_hieu") for i in range(6)]
        quota, _ = aptga.allocate(22, {})
        adjusted, moves = progression(rows, quota)
        self.assertEqual(adjusted["thong_hieu"], quota["thong_hieu"]-1)
        self.assertEqual(moves[0]["target"], "van_dung")
        rows[-1].normalized_score = 0.
        self.assertEqual(progression(rows, quota)[1], [])

    def test_solver_branches_when_top_item_hash_collides(self):
        """A duplicate top-ranked copy must not hide a valid later copy."""
        make = lambda number, qtype, skill, fingerprint: {
            "question": SimpleNamespace(id=number, question_type=qtype, difficulty_level="L2"),
            "skill": skill, "fingerprint": fingerprint, "score": 1.,
            "components": {"teacher": 0.},
        }
        ranked = [
            make(1, "single", "A", "hash-shared"),
            make(2, "single", "A", "hash-single"),
            make(3, "short_answer", "B", "hash-shared"),
            make(4, "short_answer", "B", "hash-shared"),
        ]
        with patch.object(selector, "TOTAL", 2), patch.object(selector, "TYPE_QUOTAS", {"single": 1, "short_answer": 1}):
            selected, failures, status = select_fixed(
                ranked, {"L2": 2}, {"A": 1, "B": 1}
            )
        self.assertEqual(status, "ready")
        self.assertEqual(failures, [])
        self.assertEqual([item["question"].id for item in selected], [2, 3])

    def test_learning_metadata_migration_is_additive_and_idempotent(self):
        # Use a deliberately tiny old-schema SQLite database in this test
        # context; production startup is never invoked by the test suite.
        db.session.remove()
        db.drop_all()
        db.session.execute(db.text(
            "CREATE TABLE bank_question (id INTEGER PRIMARY KEY, question_text TEXT, "
            "question_type TEXT, points FLOAT)"
        ))
        db.session.execute(db.text(
            "CREATE TABLE exam_question (id INTEGER PRIMARY KEY, exam_id INTEGER, "
            "question_text TEXT, question_type TEXT, points FLOAT)"
        ))
        db.session.commit()

        migrate_existing_sqlite_schema()
        migrate_existing_sqlite_schema()
        self.assertIn("learning_metadata", table_columns("bank_question"))
        self.assertIn("learning_metadata", table_columns("exam_question"))


if __name__ == "__main__":
    unittest.main()
