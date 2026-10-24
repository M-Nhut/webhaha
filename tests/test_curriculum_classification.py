import os
import sys
import unittest
import io
import json


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)


class TestCurriculumClassification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app

        cls.app = app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def setUp(self):
        from database import db
        from models import BankQuestion, CurriculumNode, QuestionBank, User

        self.db = db
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

        self.teacher = User(username="teacher", fullname="Teacher", user_code="GV001", role="teacher")
        db.session.add(self.teacher)
        db.session.flush()
        self.bank = QuestionBank(name="Toán 9", subject="Toán", grade="Lớp 9", created_by=self.teacher.id)
        db.session.add(self.bank)
        db.session.flush()
        self.question = BankQuestion(
            bank_id=self.bank.id,
            question_text="Rút gọn biểu thức đã cho",
            question_type="single",
            difficulty_level="nhan_biet",
            source_id="SOURCE-UNCHANGED",
            created_by=self.teacher.id,
        )
        db.session.add(self.question)
        self.node = CurriculumNode(
            grade="9",
            chapter_code="6",
            chapter_name="Một số yếu tố thống kê và xác suất",
            lesson_code="4",
            lesson_name="Một số yếu tố xác suất",
            category_code="6",
            category_name="Xác suất thực nghiệm",
            created_by=self.teacher.id,
        )
        db.session.add(self.node)
        db.session.commit()

        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.teacher.id)
            session["_fresh"] = True

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def test_canonical_code_separates_skill_from_difficulty(self):
        self.assertEqual(self.node.canonical_code, "9C6-4-6")
        from services.id6_service import make_id6
        self.assertEqual(make_id6('9', '6', '4', '6', 'thong_hieu', 'single', 1), '9C6H4-6D.1')
        self.assertEqual(make_id6('9', '6', '4', '6', 'van_dung_cao', 'short_answer', 2), '9C6C4-6S.2')

    def test_catalog_and_classification_pages_render(self):
        catalog_response = self.client.get("/curriculum")
        classification_response = self.client.get(
            f"/question-banks/{self.bank.id}/classification?status=all"
        )

        self.assertEqual(catalog_response.status_code, 200)
        self.assertIn("9C6-4-6", catalog_response.get_data(as_text=True))
        self.assertEqual(classification_response.status_code, 200)
        self.assertIn("Rút gọn biểu thức đã cho", classification_response.get_data(as_text=True))

    def test_bulk_assignment_replaces_source_id_and_preserves_content_and_original(self):
        from models import BankQuestion

        response = self.client.post(
            f"/question-banks/{self.bank.id}/classification/bulk",
            data={
                "question_ids": [str(self.question.id)],
                "curriculum_node_id": str(self.node.id),
                "difficulty_level": "thong_hieu",
                "action": "assign",
                "question_type": "single",
            },
        )

        self.assertEqual(response.status_code, 302)
        saved = self.db.session.get(BankQuestion, self.question.id)
        self.assertEqual(saved.curriculum_node_id, self.node.id)
        self.assertEqual(saved.source_id, "9C6H4-6D.1")
        self.assertEqual(saved.difficulty_level, "thong_hieu")
        self.assertEqual(saved.classification_status, 'teacher_confirmed')
        self.assertTrue(saved.to_dict()['classification']['locked'])
        self.assertEqual(saved.question_text, "Rút gọn biểu thức đã cho")
        self.assertEqual(saved.original_source_id, "SOURCE-UNCHANGED")

    def test_teacher_can_accept_unchanged_suggestion_but_not_a_stale_one(self):
        from models import BankQuestion
        from services.question_classification_service import content_fingerprint
        import json
        self.question.classification_status = 'suggested'
        self.question.classification_data = json.dumps({
            'status':'suggested', 'primary_code':self.node.canonical_code,
            'difficulty_level':'thong_hieu',
            'content_fingerprint':content_fingerprint(self.question.to_dict()),
            'rationale':['Gợi ý kiểm thử'],
        })
        self.db.session.commit()
        response = self.client.post(f'/question-banks/{self.bank.id}/classification/accept-suggestions',
                                    data={'question_ids':[str(self.question.id)]})
        self.assertEqual(response.status_code,302)
        saved=self.db.session.get(BankQuestion,self.question.id)
        self.assertEqual(saved.classification_status,'teacher_confirmed')
        self.assertEqual(saved.curriculum_node_id,self.node.id)
        self.assertTrue(saved.to_dict()['classification']['locked'])
        saved.classification_status='suggested'
        data=saved.to_dict()['classification'];data.update(status='suggested',locked=False,
            content_fingerprint=content_fingerprint(saved.to_dict()))
        saved.classification_data=json.dumps(data);saved.question_text='Nội dung đã sửa';self.db.session.commit()
        stale=self.client.post(f'/question-banks/{self.bank.id}/classification/accept-suggestions',
                               data={'question_ids':[str(saved.id)]})
        self.assertEqual(stale.status_code,302)
        self.assertEqual(self.db.session.get(BankQuestion,saved.id).classification_status,'suggested')

    def test_evaluation_page_exports_blinded_packet_and_scores_uploaded_labels(self):
        self.question.grade='Lớp 9';self.question.chapter='6'
        from models import BankQuestionOption
        self.db.session.add_all([
            BankQuestionOption(question_id=self.question.id, option_text='2', is_correct=True, order_index=0),
            BankQuestionOption(question_id=self.question.id, option_text='3', is_correct=False, order_index=1),
        ])
        self.db.session.commit()
        exported=self.client.get(f'/question-banks/{self.bank.id}/classification/evaluation/export')
        self.assertEqual(exported.status_code,200)
        packet=json.loads(exported.get_data(as_text=True))
        self.assertEqual(packet[0]['source']['bank_question_id'],self.question.id)
        self.assertNotIn('is_correct',packet[0]['question']['options'][0])
        labels=[dict(id='label-1',question=dict(question_text='Tung một đồng xu. Hãy lập không gian mẫu, xác định biến cố và tính xác suất mặt ngửa.',
                    question_type='single',options=[]),scope=dict(grade='9',chapters=['6']),
                    expected_primary_code='9C6-4-3',expected_difficulty_level='van_dung')]
        report=self.client.post(f'/question-banks/{self.bank.id}/classification/evaluation',
            data={'labels_file':(io.BytesIO(json.dumps(labels).encode()),'labels.json')},
            content_type='multipart/form-data')
        self.assertEqual(report.status_code,200)
        text=report.get_data(as_text=True)
        self.assertIn('Chưa đạt cổng chất lượng',text)
        self.assertIn('100.0%',text)
        invalid=self.client.post(f'/question-banks/{self.bank.id}/classification/evaluation',
            data={'labels_file':(io.BytesIO(b'not-json'),'labels.json')},content_type='multipart/form-data')
        self.assertIn('Expecting value',invalid.get_data(as_text=True))

    def test_teacher_cannot_assign_questions_from_another_bank(self):
        from models import BankQuestion, QuestionBank, User

        other_teacher = User(username="other", fullname="Other", user_code="GV002", role="teacher")
        self.db.session.add(other_teacher)
        self.db.session.flush()
        other_bank = QuestionBank(name="Other", subject="Toán", created_by=other_teacher.id)
        self.db.session.add(other_bank)
        self.db.session.flush()
        other_question = BankQuestion(
            bank_id=other_bank.id,
            question_text="Không thuộc ngân hàng",
            created_by=other_teacher.id,
        )
        self.db.session.add(other_question)
        self.db.session.commit()

        response = self.client.post(
            f"/question-banks/{self.bank.id}/classification/bulk",
            data={
                "question_ids": [str(other_question.id)],
                "curriculum_node_id": str(self.node.id),
                "difficulty_level": "nhan_biet",
                "action": "assign",
                "question_type": "single",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(f'/question-banks/{other_bank.id}/classification/evaluation').status_code,403)
        self.assertEqual(self.client.get(f'/question-banks/{other_bank.id}/classification/evaluation/export').status_code,403)


    def test_sequences_shared_across_types_and_levels_and_stable_on_edit(self):
        from models import BankQuestion
        from services.id6_service import select_curriculum
        saved = []
        for kind, level in [('single','nhan_biet'), ('true_false','nhan_biet'), ('short_answer','thong_hieu'), ('short_answer','van_dung')]:
            q = BankQuestion(bank_id=self.bank.id, question_text=kind, question_type=kind, difficulty_level=level, created_by=self.teacher.id)
            select_curriculum(q, self.node.id)
            self.db.session.add(q)
            self.db.session.flush()
            saved.append(q)
        self.db.session.commit()
        self.assertEqual([q.source_id for q in saved], ['9C6N4-6D.1','9C6N4-6T.2','9C6H4-6S.3','9C6V4-6S.4'])
        saved[0].difficulty_level = 'van_dung_cao'
        saved[0].question_type = 'short_answer'
        self.db.session.commit()
        self.assertEqual(saved[0].source_id, '9C6C4-6S.1')
        self.db.session.delete(saved[3])
        self.db.session.commit()
        q = BankQuestion(bank_id=self.bank.id, question_text='next', question_type='short_answer', difficulty_level='van_dung', created_by=self.teacher.id)
        select_curriculum(q, self.node.id)
        self.db.session.add(q)
        self.db.session.commit()
        self.assertEqual(q.id6_sequence, 5)

    def test_imported_duplicate_tags_get_distinct_sequence_across_banks(self):
        from models import BankQuestion, QuestionBank
        other = QuestionBank(name='Other', subject='Toán', created_by=self.teacher.id)
        self.db.session.add(other)
        self.db.session.flush()
        questions = [BankQuestion(bank_id=bank_id, question_text='tagged', source_id='9C6H4-6S.7', created_by=self.teacher.id) for bank_id in [self.bank.id, other.id]]
        self.db.session.add_all(questions)
        self.db.session.commit()
        self.assertEqual([q.source_id for q in questions], ['9C6H4-6S.7', '9C6H4-6S.8'])
        self.assertEqual([q.question_type for q in questions], ['short_answer', 'short_answer'])

    def test_preview_does_not_reserve_numbers(self):
        from models import ID6Counter
        url = f'/curriculum/id6-preview?node_id={self.node.id}&question_type=short_answer&difficulty_level=nhan_biet'
        for _ in range(2):
            self.assertEqual(self.client.get(url).json['source_id'], '9C6N4-6S.1')
        self.assertEqual(ID6Counter.query.count(), 0)

    def test_manual_true_false_saves_false_and_four_answers(self):
        from models import BankQuestion
        response = self.client.post(f'/question-banks/{self.bank.id}/questions/add', data={
            'curriculum_node_id': self.node.id, 'question_text': 'Các mệnh đề',
            'question_type': 'true_false', 'difficulty_level': 'nhan_biet',
            'option_text': ['a text','b text','c text','d text'],
            'correct_option': ['false','true','false','true'],
        })
        self.assertEqual(response.status_code, 302)
        saved = BankQuestion.query.order_by(BankQuestion.id.desc()).first()
        self.assertEqual(saved.source_id, '9C6N4-6T.1')
        self.assertEqual([o.is_correct for o in saved.options], [False, True, False, True])
        self.assertEqual([o.option_text for o in saved.options], ['a) a text','b) b text','c) c text','d) d text'])

    def test_invalid_selection_or_answers_does_not_save(self):
        from models import BankQuestion
        self.client.post(f'/question-banks/{self.bank.id}/questions/add', data={
            'curriculum_node_id': self.node.id, 'question_text': 'invalid',
            'question_type': 'single', 'difficulty_level': 'nhan_biet',
            'option_text': ['A','B'], 'correct_option': '0',
        })
        self.assertEqual(BankQuestion.query.count(), 1)

    def test_catalog_seed_matches_user_data_and_is_idempotent(self):
        from models import CurriculumNode
        from services.curriculum_service import seed_math9_catalog, normalize_curriculum_payload
        self.db.session.delete(self.node)
        self.db.session.commit()
        seed_math9_catalog()
        seed_math9_catalog()
        self.assertEqual(CurriculumNode.query.count(), 8)
        node = CurriculumNode.query.filter_by(canonical_code='9C6-4-2').one()
        self.assertEqual(node.chapter_name, 'Một số yếu tố thống kê và xác suất')
        self.assertEqual(node.lesson_name, 'Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố')
        with self.assertRaises(ValueError):
            normalize_curriculum_payload({'grade':'12'})

    def test_migration_retains_legacy_source_and_is_idempotent(self):
        from services.id6_service import migrate_id6_metadata
        from models import BankQuestion
        self.question.source_id = '9C6H4-6'
        self.db.session.commit()
        migrate_id6_metadata()
        migrate_id6_metadata()
        saved = self.db.session.get(BankQuestion, self.question.id)
        self.assertEqual(saved.source_id, '9C6H4-6D.1')
        self.assertEqual(saved.original_source_id, '9C6H4-6')
        self.assertEqual(saved.curriculum_node_id, self.node.id)

    def test_legacy_mapping_does_not_block_question_deletion(self):
        from sqlalchemy import text
        from services.id6_service import migrate_id6_metadata
        self.db.session.execute(text('CREATE TABLE question_skill (id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL REFERENCES bank_question(id), curriculum_node_id INTEGER NOT NULL, difficulty_level TEXT NOT NULL, is_primary BOOLEAN NOT NULL)'))
        try:
            self.db.session.execute(text('INSERT INTO question_skill VALUES (1, :qid, :nid, :level, true)'), {'qid':self.question.id,'nid':self.node.id,'level':'thong_hieu'})
            self.db.session.commit()
            migrate_id6_metadata()
            self.assertEqual(self.question.source_id, '9C6H4-6D.1')
            self.db.session.delete(self.question)
            self.db.session.commit()
            self.assertEqual(self.db.session.execute(text('SELECT count(*) FROM question_skill')).scalar(), 0)
        finally:
            self.db.session.execute(text('DROP TABLE question_skill'))
            self.db.session.commit()

    def test_concurrent_writers_cannot_allocate_the_same_sequence(self):
        import tempfile
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from models import BankQuestion, User, QuestionBank
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine('sqlite:///' + directory + '/concurrent.db', connect_args={'timeout': 20})
            self.db.metadata.create_all(engine)
            with Session(engine) as session:
                user = User(username='writer',user_code='WRITER',fullname='Writer',role='teacher')
                session.add(user); session.flush()
                bank = QuestionBank(name='Concurrent',subject='Toán',created_by=user.id)
                session.add(bank); session.flush()
                uid, bid = user.id, bank.id
                session.commit()
            barrier = threading.Barrier(4)
            def save(index):
                with Session(engine) as session:
                    question = BankQuestion(bank_id=bid,created_by=uid,question_text=str(index),source_id='9C6N4-1S.1')
                    session.add(question)
                    barrier.wait(timeout=10)
                    session.commit()
                    return question.source_id
            with ThreadPoolExecutor(max_workers=4) as executor:
                ids = list(executor.map(save, range(4)))
            self.assertEqual(set(ids), {'9C6N4-1S.1','9C6N4-1S.2','9C6N4-1S.3','9C6N4-1S.4'})
            engine.dispose()

if __name__ == "__main__":
    unittest.main()
