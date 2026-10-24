"""Exercise the new metadata adapter through the unchanged document pipelines."""
import io
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ.pop('POSTGRES_URL', None)


class TestID6Import(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app
        cls.app = app
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def setUp(self):
        from database import db
        from models import User, QuestionBank
        from services.curriculum_service import seed_math9_catalog
        self.db = db
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all(); db.create_all(); seed_math9_catalog()
        self.user = User(username='id6', user_code='ID6', fullname='ID6', role='teacher')
        db.session.add(self.user); db.session.flush()
        self.bank = QuestionBank(name='ID6 bank', subject='Toán', created_by=self.user.id)
        db.session.add(self.bank); db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.user.id)
            session['_fresh'] = True
        self.temp = tempfile.TemporaryDirectory()
        self.upload_patch = patch('services.import_service.UPLOAD_TEMP_DIR', self.temp.name)
        self.upload_patch.start()

    def tearDown(self):
        self.upload_patch.stop()
        self.db.session.remove(); self.db.drop_all(); self.context.pop()
        self.temp.cleanup()

    def upload(self, data, filename):
        response = self.client.post('/question-banks/import/upload', data={'file': (io.BytesIO(data), filename), 'bank_id': self.bank.id})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    def confirm(self, session_id):
        response = self.client.post(f'/question-banks/import/{session_id}/scope', json={
            'grade':'9', 'chapters':['6'], 'lessons':['6:4'], 'topics':['thong_ke_xac_suat']})
        self.assertEqual(response.status_code, 200, response.json)
        response = self.client.post(f'/question-banks/import/{session_id}/confirm', json={'bank_id': self.bank.id})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    def test_tex_four_types_preview_resume_edit_and_confirm(self):
        from models import BankQuestion
        source = r'''\begin{ex}%[9C6N4-1D.1]
Chọn đáp án bằng một.
\choice{\True 1}{2}{3}{4}
\end{ex}
\begin{ex}%[9C6N4-1T.2]
Đánh giá các phát biểu.
\choiceTF{\True Một bằng một}{Một bằng hai}{\True Hai bằng hai}{Ba bằng bốn}
\end{ex}
\begin{ex}%[9C6H4-1S.3]
Điền kết quả phép cộng.
\shortans{3}
\end{ex}
\begin{ex}%[9C6V4-1TL.4]
Trình bày cách giải bài toán.
\loigiai{Bài giải mẫu.}
\end{ex}'''
        result = self.upload(source.encode(), 'four.tex')
        self.assertEqual([q['question_type'] for q in result['questions']], ['single','true_false','short_answer','short_answer'])
        self.assertEqual([q['source_id'] for q in result['questions']], ['9C6N4-1D.1','9C6N4-1T.2','9C6H4-1S.3','9C6V4-1TL.4'])
        sid = result['session_id']
        resumed = self.client.get(f'/question-banks/import/{sid}/preview')
        self.assertEqual(resumed.status_code, 200)
        converted = resumed.json['questions'][3]
        self.assertEqual(converted['question_type'], 'short_answer')
        self.assertEqual(converted['status'], 'warning')
        self.assertFalse(any('Chỉ nhận' in error for error in converted['errors']))
        converted['options'] = [{'text':'42', 'is_correct':True}]
        converted['difficulty_level'] = 'van_dung_cao'
        edit = self.client.post(f'/question-banks/import/{sid}/update', json={'index':3,'question':converted})
        self.assertEqual(edit.json['questions'][3]['source_id'], '9C6C4-1S.4')
        confirmed = self.confirm(sid)
        self.assertEqual(confirmed['imported_count'], 4)
        saved = BankQuestion.query.order_by(BankQuestion.id).all()
        self.assertEqual([q.id6_sequence for q in saved], [1,2,3,4])
        self.assertEqual(saved[3].source_id, '9C6C4-1S.4')
        self.assertEqual(len(saved[1].options), 4)
        self.assertEqual([o.is_correct for o in saved[1].options], [True, False, True, False])

    def test_partially_tagged_tex_does_not_shift_ids(self):
        result = self.upload(r'''\begin{ex}
Bài không có mã.
\loigiai{Bài giải.}
\end{ex}
\begin{ex}%[9C6V4-1TL.8]
Bài có mã hình trụ.
\loigiai{Bài giải.}
\end{ex}'''.encode(), 'partial.tex')
        self.assertFalse(result['questions'][0]['source_id'])
        self.assertEqual(result['questions'][1]['source_id'], '9C6V4-1TL.8')

    def test_preview_cannot_be_read_or_edited_by_another_teacher(self):
        from models import User
        result=self.upload(b'\\begin{ex}%[9C6N4-1TL.1]\nA question.\n\\end{ex}', 'private.tex')
        other=User(username='other',user_code='OTHER',fullname='Other',role='teacher')
        self.db.session.add(other); self.db.session.commit()
        with self.client.session_transaction() as session:
            session['_user_id']=str(other.id)
        from flask import g
        g.pop('_login_user', None)
        sid=result['session_id']
        self.assertEqual(self.client.get(f'/question-banks/import/{sid}/preview').status_code,404)
        self.assertEqual(self.client.post(f'/question-banks/import/{sid}/update',json={'index':0,'question':result['questions'][0]}).status_code,404)

    def test_duplicate_import_tags_warn_and_save_unique_ids(self):
        from models import BankQuestion
        source = b'\\begin{ex}%[9C6N4-1S.1]\nFirst question.\n\\shortans{1}\n\\end{ex}\n\\begin{ex}%[9C6H4-1S.1]\nSecond question.\n\\shortans{2}\n\\end{ex}'
        result = self.upload(source, 'duplicate.tex')
        self.assertTrue(any('Số thứ tự ID6' in warning for warning in result['questions'][1]['warnings']))
        self.confirm(result['session_id'])
        self.assertEqual([q.source_id for q in BankQuestion.query.order_by(BankQuestion.id)], ['9C6N4-1S.1','9C6H4-1S.2'])

    def test_legacy_tag_is_upgraded_by_adapter(self):
        result = self.upload(b'\\caulc\n\\begin{ex}%[9C6N4-1]\nOld tag question.\n\\choice{\\True 1}{2}{3}{4}\n\\end{ex}', 'legacy.tex')
        self.assertEqual(result['questions'][0]['source_id'], '9C6N4-1D.1')

    def test_invalid_tag_does_not_change_question_type(self):
        from services.id6_service import parse_id6
        for tag in ['9C6N4-1TL.0','5C1N1-1D.1','9C6N4-1X.1','9C6N4-1TL.1junk']:
            self.assertIsNone(parse_id6(tag))

if __name__ == '__main__':
    unittest.main()
