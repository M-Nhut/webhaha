"""Stage 2 contracts: three authoring formats and persisted file scope."""
from contextlib import closing
import datetime as dt
import io
import os
import unittest
from unittest.mock import patch
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ.pop('POSTGRES_URL', None)

SCOPE = dict(grade='9', chapters=['6'], lessons=['6:4'], topics=['thong_ke_xac_suat'])

def question(kind='single'):
    return dict(index=1, question_text='Tung một đồng xu và tính xác suất xuất hiện mặt ngửa.', question_type=kind,
                options=[dict(text=str(i), is_correct=i==0) for i in range(4)] if kind=='single' else
                        [dict(text='25', is_correct=True)] if kind=='short_answer' else [],
                statements=[dict(id=chr(97+i), text=f'Mệnh đề {i}', answer=i%2==0) for i in range(4)] if kind=='true_false' else [],
                difficulty_level='nhan_biet', points=1, formulas={})

class TestPhase2(unittest.TestCase):
    def setUp(self):
        from app import app
        from database import db
        from models import User, QuestionBank
        from services.curriculum_service import seed_math9_catalog
        self.app, self.db = app, db
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.context=app.app_context(); self.context.push()
        db.drop_all(); db.create_all(); seed_math9_catalog()
        self.user=User(username='phase2', user_code='P2', fullname='Teacher', role='teacher')
        db.session.add(self.user); db.session.flush()
        self.bank=QuestionBank(name='Phase 2', subject='Toán', created_by=self.user.id)
        db.session.add(self.bank); db.session.commit()
        self.client=app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id']=str(self.user.id); session['_fresh']=True

    def tearDown(self):
        self.db.session.remove(); self.db.drop_all(); self.context.pop()

    def preview(self, rows=None):
        from models import ImportSession
        row=ImportSession(user_id=self.user.id, bank_id=self.bank.id, filename='chapter6.tex', file_type='tex', status='preview')
        row.set_parsed_questions(rows or [question()]); self.db.session.add(row); self.db.session.commit()
        return row

    def scope(self, session, payload=None):
        return self.client.post(f'/question-banks/import/{session.id}/scope', json=payload or SCOPE)

    def confirm(self, session, payload=None):
        return self.client.post(f'/question-banks/import/{session.id}/confirm', json=payload or dict(bank_id=self.bank.id))

    def test_scope_required_persists_multi_lesson_and_topic_without_guessing_category(self):
        from models import BankQuestion
        row=self.preview()
        self.assertEqual(self.confirm(row).status_code,400)
        result=self.scope(row); self.assertEqual(result.status_code,200,result.json)
        q=result.json['questions'][0]
        self.assertEqual(q['chapter'],'6'); self.assertEqual(q.get('section'), '4')
        self.assertFalse(q.get('question_category')); self.assertEqual(q['topic'],'Thống kê và xác suất')
        resumed=self.client.get(f'/question-banks/import/{row.id}/preview')
        self.assertEqual(resumed.json['scope']['lessons'],SCOPE['lessons'])
        self.assertEqual(resumed.json['bank_id'],self.bank.id)
        self.assertEqual(self.confirm(row).json['imported_count'],1)
        self.assertEqual(BankQuestion.query.one().topic,'Thống kê và xác suất')
        self.assertTrue(self.confirm(row).json['replayed'])
        self.assertEqual(BankQuestion.query.count(),1)

    def test_change_scope_removes_old_defaults_and_rejects_cross_hierarchy(self):
        row=self.preview()
        initial={**SCOPE,'lessons':['6:4']}
        self.assertEqual(self.scope(row,initial).json['questions'][0]['section'],'4')
        self.assertEqual(self.scope(row,{**SCOPE,'lessons':['6:2']}).status_code,400)
        self.assertEqual(self.scope(row,{**SCOPE,'lessons':['1:1']}).status_code,400)
        self.assertEqual(row.get_scope()['lessons'],['6:4'])

    def test_explicit_out_of_scope_tag_is_not_overwritten_or_saved(self):
        q=question(); q.update(source_id='9C1N1-1D.12',grade='Lớp 9',chapter='1',section='1',question_category='1')
        row=self.preview([q]); result=self.scope(row)
        self.assertEqual(result.json['questions'][0]['chapter'],'1')
        self.assertEqual(result.json['stats']['error'],1)
        self.assertEqual(self.confirm(row).status_code,400)

    def test_delete_preview_is_persisted_and_keeps_source_number(self):
        q2=question('short_answer'); q2['index']=12
        row=self.preview([question(),q2]); self.scope(row)
        removed=self.client.post(f'/question-banks/import/{row.id}/remove',json={'index':0})
        self.assertEqual(removed.json['questions'][0]['index'],12)
        self.assertEqual(self.client.get(f'/question-banks/import/{row.id}/preview').json['stats']['total'],1)
        self.assertEqual(self.confirm(row).json['imported_count'],1)

    def test_unsupported_and_incomplete_types_cannot_enter_new_practice_papers(self):
        from services.question_policy import bank_question_ready
        from models import BankQuestion
        rows=[question(kind) for kind in ['single','true_false','short_answer','essay','multiple_choice']]
        rows[1]['statements'][2]['answer']=None
        row=self.preview(rows); self.scope(row)
        # Legacy essay labels are converted to short-answer at the import
        # boundary; only the unsupported multiple-choice row is an error.
        self.assertEqual(row.error_count,1)
        result=self.confirm(row); self.assertEqual(result.json['imported_count'],3,result.json)
        saved=BankQuestion.query.order_by(BankQuestion.id).all()
        self.assertEqual([bank_question_ready(q) for q in saved],[True,False,True])
        self.assertIsNone(saved[1].options[2].is_correct)

    def test_scope_and_session_permissions_expiry_and_catalog_change(self):
        from models import CurriculumNode
        row=self.preview(); self.scope(row)
        node=CurriculumNode.query.filter_by(chapter_code='6').first()
        node.category_name+=' updated'; self.db.session.commit()
        self.assertEqual(self.confirm(row).status_code,400)
        self.assertEqual(self.scope(row).status_code,200)
        row.expires_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)-dt.timedelta(seconds=1)
        self.db.session.commit()
        self.assertEqual(self.scope(row).status_code,400)
        self.assertEqual(self.confirm(row).status_code,400)

    def test_api_disallows_legacy_new_questions_without_curriculum(self):
        from models import BankQuestion
        for kind in ['essay','multiple_choice','nonsense']:
            self.client.post(f'/question-banks/{self.bank.id}/questions/add',data=dict(question_text='Test',question_type=kind))
        self.assertEqual(BankQuestion.query.count(),0)
        self.client.post(f'/question-banks/{self.bank.id}/questions/add',data=dict(question_text='Test',question_type='short_answer',short_answers=' | '))
        self.assertEqual(BankQuestion.query.count(),0)
        row=self.preview(); self.scope(row); self.confirm(row)
        saved=BankQuestion.query.one()
        self.assertEqual(self.client.post(f'/questions/{saved.id}/update',json={'question_type':'essay'}).status_code,400)
        self.assertEqual(saved.question_type,'single')

    def test_legacy_codes_remain_readable_but_cannot_be_generated(self):
        from services.id6_service import parse_id6, make_id6
        from models import BankQuestion
        self.assertEqual(parse_id6('9C6H4-1TL.7')['question_type'],'essay')
        with self.assertRaises(ValueError): make_id6('9','6','4','1','thong_hieu','essay',7)
        self.db.session.execute(BankQuestion.__table__.insert().values(bank_id=self.bank.id,question_text='Historical essay',question_type='essay',source_id='9C6H4-1TL.7',created_by=self.user.id))
        self.db.session.commit()
        q=BankQuestion.query.one(); q.explanation='Historical note'; self.db.session.commit()
        self.assertEqual(q.source_id,'9C6H4-1TL.7')
        response=self.client.get(f'/question-banks/{self.bank.id}')
        self.assertEqual(response.status_code,200)

    def test_only_tex_upload_is_supported(self):
        rejected=self.client.post('/question-banks/import/upload',data={'file':(io.BytesIO(b'not supported'),'sample.docx'),'bank_id':self.bank.id})
        self.assertEqual(rejected.status_code,400)
        source=(b'\\begin{ex}%[9C6N4-1D.1]\n'
                b'Chon dap an.\\choice{\\True 1}{2}{3}{4}\n\\end{ex}')
        response=self.client.post('/question-banks/import/upload',data={'file':(io.BytesIO(source),'sample.tex'),'bank_id':self.bank.id})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['questions'][0]['question_type'],'single')

    def test_other_teacher_cannot_scope_delete_cancel_or_confirm_session(self):
        from models import User
        from flask import g
        row=self.preview(); self.scope(row)
        other=User(username='other_phase2',user_code='P2OTHER',fullname='Other',role='teacher')
        self.db.session.add(other); self.db.session.commit()
        with self.client.session_transaction() as session: session['_user_id']=str(other.id)
        g.pop('_login_user',None)
        for action,payload in [('scope',SCOPE),('remove',{'index':0}),('cancel',{}),('confirm',{'bank_id':self.bank.id})]:
            result=self.client.post(f'/question-banks/import/{row.id}/{action}',json=payload)
            self.assertEqual(result.status_code,404,(action,result.status_code))
        self.assertEqual(row.status,'preview')

    def test_changed_catalog_preview_can_reopen_scope_and_destination_is_locked(self):
        from models import CurriculumNode,QuestionBank
        row=self.preview();self.scope(row)
        other=QuestionBank(name='Another',subject='Toán',created_by=self.user.id)
        self.db.session.add(other);self.db.session.commit()
        self.assertEqual(self.confirm(row,dict(bank_id=other.id)).status_code,400)
        node=CurriculumNode.query.filter_by(chapter_code='6').first()
        node.category_name+=' new';self.db.session.commit()
        result=self.client.get(f'/question-banks/import/{row.id}/preview')
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.json['scope_error'])
        self.assertEqual(self.scope(row).status_code,200)

    def test_sqlite_scope_migration_preserves_rows_and_is_repeatable(self):
        import tempfile,sqlite3
        from pathlib import Path
        from scripts.migrate_import_scope import migrate
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.db'
            with closing(sqlite3.connect(path)) as con, con:
                con.execute('CREATE TABLE import_session (id TEXT PRIMARY KEY, parsed_data TEXT)')
                con.execute('INSERT INTO import_session VALUES (?,?)',('sample','unchanged'))
            result=migrate(path,Path(folder)/'backups')
            self.assertEqual(result['status'],'applied')
            self.assertEqual(migrate(path,Path(folder)/'backups')['status'],'already_applied')
            with closing(sqlite3.connect(path)) as con, con:
                self.assertEqual(con.execute('SELECT * FROM import_session').fetchone(),('sample','unchanged',None))
            with closing(sqlite3.connect(result['backup'])) as con:
                self.assertEqual(con.execute('SELECT * FROM import_session').fetchone(),('sample','unchanged'))
