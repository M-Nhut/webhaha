"""Stage 2a: semantic-preserving dedupe, decisions, audit and transactional replay."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import test_phase2_import as phase2
from services.import_duplicates import ContentNormalizer

class TestImportDuplicates(unittest.TestCase):
    setUp=phase2.TestPhase2.setUp
    tearDown=phase2.TestPhase2.tearDown
    preview=phase2.TestPhase2.preview
    scope=phase2.TestPhase2.scope
    confirm=phase2.TestPhase2.confirm

    def store(self, q=None):
        from models import BankQuestion
        session=self.preview([q or phase2.question()]);self.scope(session)
        result=self.confirm(session)
        self.assertEqual(result.status_code,200,result.json)
        return BankQuestion.query.order_by(BankQuestion.id.desc()).first()

    def test_repeat_file_reports_zero_and_never_reserves_another_id(self):
        from models import BankQuestion,ID6Counter
        q=phase2.question(); q.update(source_id='9C6N4-1D.12',chapter='6',section='4',question_category='1',grade='Lớp 9')
        original=self.store(q)
        row=self.preview([copy.deepcopy(q)]);self.scope(row)
        self.assertEqual(row.get_duplicate_report()['duplicate'],1)
        result=self.confirm(row).json
        self.assertEqual(result['imported_count'],0)
        self.assertEqual(result['skipped_count'],1)
        self.assertTrue(result['completed'])
        self.assertEqual(BankQuestion.query.count(),1)
        self.assertEqual(ID6Counter.query.one().last_sequence,12)
        self.assertEqual(result['rows'][0]['matches'][0]['bank_question_id'],original.id)
        self.assertTrue(self.confirm(row).json['replayed'])

    def test_duplicate_inside_file_chooses_answered_copy_and_preserves_labels(self):
        from models import BankQuestion
        first=phase2.question(); first['options'][0]['is_correct']=False; first['source_label']='Phần I — Câu 7'
        second=phase2.question();second['index']=8;second['source_label']='Phần II — Câu 3'
        row=self.preview([first,second]);self.scope(row)
        report=row.get_duplicate_report()
        self.assertEqual(report['skipped_labels'],['Phần I — Câu 7'])
        self.assertEqual(report['eligible'],1)
        self.assertEqual(self.confirm(row).json['imported_count'],1)
        self.assertTrue(BankQuestion.query.one().options[0].is_correct)

    def test_reordered_options_duplicate_and_conflicting_answer_does_not_edit_bank(self):
        q=phase2.question(); original=self.store(q)
        q['options']=list(reversed(q['options']))
        row=self.preview([q]);self.scope(row)
        self.assertEqual(row.get_duplicate_report()['duplicate'],1)
        self.assertFalse(row.get_parsed_questions()[0]['duplicate']['matches'][0]['answer_conflict'])
        q['options'][0]['is_correct']=True; q['options'][-1]['is_correct']=False
        changed=self.preview([q]);self.scope(changed)
        self.assertTrue(changed.get_parsed_questions()[0]['duplicate']['matches'][0]['answer_conflict'])
        self.assertEqual(self.confirm(changed).json['imported_count'],0)
        self.assertTrue(original.options[0].is_correct)

    def test_math_data_and_position_dependent_choices_never_auto_collapse(self):
        normalizer=ContentNormalizer()
        base=phase2.question();base['question_text']='Tính x khi x + 2 = 3, x > 0 và y^2 = 4.'
        key=normalizer.describe(base)['key']
        for content in ['Tính x khi x - 2 = 3, x > 0 và y^2 = 4.',
                        'Tính x khi x + 2 = 3, x < 0 và y^2 = 4.',
                        'Tính x khi x + 2 = 3, x > 0 và y^3 = 4.',
                        'Tính x khi x + 2 = 5, x > 0 và y^2 = 4.']:
            other={**base,'question_text':content}
            self.assertNotEqual(key,normalizer.describe(other)['key'])
        self.store(base)
        row=self.preview([{**base,'question_text':'Tính x khi x + 2 = 5, x > 0 và y^2 = 4.'}]);self.scope(row)
        self.assertEqual(row.get_duplicate_report()['new'],1)
        positional=phase2.question();positional['options'][3]['text']='Cả hai phương án A và B'
        reverse=copy.deepcopy(positional);reverse['options'].reverse()
        self.assertNotEqual(normalizer.describe(positional)['key'],normalizer.describe(reverse)['key'])

    def test_formula_uuid_is_not_identity_and_unresolved_asset_requires_review(self):
        from models import FormulaAsset
        q=phase2.question();q['question_text']='Tính [[formula:first]]';q['formulas']={'first':{'latex':'x^2 + 1','source_format':'OMML'}}
        self.store(q)
        copied=copy.deepcopy(q);copied['question_text']='Tính [[formula:second]]';copied['formulas']={'second':q['formulas']['first']}
        row=self.preview([copied]);self.scope(row)
        self.assertEqual(row.get_duplicate_report()['duplicate'],1)
        self.assertEqual(self.confirm(row).json['imported_count'],0)
        self.assertEqual(FormulaAsset.query.count(),1)
        unresolved=phase2.question();unresolved['image_url']='/static/uploads/questions/missing-A.png'
        other=copy.deepcopy(unresolved);other['image_url']='/static/uploads/questions/missing-B.png'
        row=self.preview([unresolved,other]);self.scope(row)
        self.assertEqual(row.get_duplicate_report()['duplicate'],0)
        self.assertEqual(row.get_duplicate_report()['review'],1)

    def test_equal_local_pixels_under_different_names_match(self):
        from PIL import Image
        import services.import_duplicates as module
        with tempfile.TemporaryDirectory() as folder:
            images=Path(folder)/'static/uploads/questions';images.mkdir(parents=True)
            Image.new('RGB',(3,3),'red').save(images/'a.png')
            Image.new('RGB',(3,3),'red').save(images/'b.png')
            Image.new('RGB',(3,3),'blue').save(images/'c.png')
            with patch.object(module,'ROOT',Path(folder)):
                normalizer=ContentNormalizer();q=phase2.question()
                a=normalizer.describe({**q,'image_url':'/static/uploads/questions/a.png'})['key']
                self.assertEqual(a,normalizer.describe({**q,'image_url':'/static/uploads/questions/b.png'})['key'])
                self.assertNotEqual(a,normalizer.describe({**q,'image_url':'/static/uploads/questions/c.png'})['key'])

    def test_near_decision_bound_to_contents_and_partial_save_replay(self):
        from models import BankQuestion
        original=phase2.question();self.store(original)
        near=copy.deepcopy(original);near['question_text']='Tung một đồng xu và tính xác suất xuất hiện mặt ngửa của biến cố.'
        fresh=phase2.question('short_answer');fresh['question_text']='Có bao nhiêu học sinh trong lớp?'
        row=self.preview([near,fresh]);self.scope(row)
        report=row.get_duplicate_report();self.assertEqual(report['review'],1)
        token=report['revision']
        first=self.confirm(row,dict(bank_id=self.bank.id,confirmation_token=token)).json
        self.assertEqual(first['imported_count'],1);self.assertFalse(first['completed'])
        repeated=self.confirm(row,dict(bank_id=self.bank.id,confirmation_token=token)).json
        self.assertTrue(repeated['replayed']);self.assertEqual(BankQuestion.query.count(),2)
        resumed=self.client.get(f'/question-banks/import/{row.id}/preview').json
        q=resumed['questions'][0];match=q['duplicate']['matches'][0]
        decision=self.client.post(f'/question-banks/import/{row.id}/duplicate-decision',json=dict(import_uid=q['import_uid'],token=match['token'],decision='different'))
        self.assertEqual(decision.status_code,200,decision.json)
        self.assertEqual(decision.json['duplicate_report']['eligible'],1)
        # Changing the bank-side solution invalidates the teacher's comparison.
        stored=BankQuestion.query.order_by(BankQuestion.id).first();stored.explanation='Lời giải bổ sung';self.db.session.commit()
        refreshed=self.client.get(f'/question-banks/import/{row.id}/preview').json
        self.assertEqual(refreshed['duplicate_report']['review'],1)
        self.assertEqual(BankQuestion.query.count(),2)

    def test_bank_change_rescans_and_unauthorized_target_fails(self):
        from models import QuestionBank,User
        self.store()
        row=self.preview();self.scope(row)
        self.assertEqual(row.get_duplicate_report()['duplicate'],1)
        bank=QuestionBank(name='Empty',subject='Toán',created_by=self.user.id)
        other=User(username='dup_other',user_code='DUP_OTHER',fullname='Other',role='teacher')
        self.db.session.add_all([bank,other]);self.db.session.flush()
        private=QuestionBank(name='Private',subject='Toán',created_by=other.id)
        self.db.session.add(private);self.db.session.commit()
        result=self.client.post(f'/question-banks/import/{row.id}/destination',json={'bank_id':bank.id})
        self.assertEqual(result.json['duplicate_report']['duplicate'],0)
        denied=self.client.post(f'/question-banks/import/{row.id}/destination',json={'bank_id':private.id})
        self.assertEqual(denied.status_code,403)
        self.assertEqual(self.db.session.get(type(row),row.id).bank_id,bank.id)

    def test_source_numbers_survive_tex_restarts_and_deletion(self):
        first=phase2.question(); first.update(index=7, source_label='Câu 7 — dòng 1')
        second=phase2.question('short_answer'); second.update(index=7, source_label='Câu 7 — dòng 2')
        row=self.preview([first, second]); self.scope(row)
        labels=[q['source_label'] for q in row.get_parsed_questions()]
        self.assertEqual(labels, ['Câu 7 — dòng 1', 'Câu 7 — dòng 2'])
        removed=self.client.post(f'/question-banks/import/{row.id}/remove',json={'index':0})
        self.assertEqual(removed.status_code,200,removed.json)
        self.assertEqual(removed.json['questions'][0]['source_label'],'Câu 7 — dòng 2')

    def test_receipt_survives_post_commit_cleanup_error_and_retry(self):
        from models import BankQuestion
        row=self.preview();self.scope(row)
        with patch('services.import_service.ImportService.cleanup_temp_file',side_effect=OSError('cleanup')):
            result=self.confirm(row)
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(self.confirm(row).json['imported_count'],1)
        self.assertEqual(BankQuestion.query.count(),1)

    def test_source_download_is_limited_to_the_active_owner_session(self):
        from services.import_service import UPLOAD_TEMP_DIR
        row=self.preview()
        source=Path(UPLOAD_TEMP_DIR)/f'{row.id}_source.tex'
        source.parent.mkdir(parents=True,exist_ok=True);source.write_text('Câu 1',encoding='utf-8')
        row.file_path=str(source);self.db.session.commit()
        response=self.client.get(f'/question-banks/import/{row.id}/source')
        self.assertEqual(response.status_code,200)
        self.assertIn('attachment',response.headers['Content-Disposition'])
        response.close()
        self.scope(row);self.confirm(row)
        self.assertEqual(self.client.get(f'/question-banks/import/{row.id}/source').status_code,404)
        self.assertEqual(self.client.post(f'/question-banks/import/{row.id}/cancel').status_code,400)

    def test_two_concurrent_imports_into_one_bank_add_only_one_question(self):
        from flask import Flask
        from database import db
        from models import User,QuestionBank,ImportSession,BankQuestion,ID6Counter
        from services.curriculum_service import seed_math9_catalog
        from services.import_scope import save_scope
        from services.import_service import ImportService
        with tempfile.TemporaryDirectory() as folder:
            app=Flask('duplicate_concurrency');app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///'+folder+'/race.db'
            db.init_app(app)
            with app.app_context():
                db.create_all();seed_math9_catalog()
                user=User(username='race',user_code='RACE',fullname='Race',role='teacher');db.session.add(user);db.session.flush()
                bank=QuestionBank(name='Race bank',subject='Toán',created_by=user.id);db.session.add(bank);db.session.commit()
                uid,bid=user.id,bank.id;ids=[]
                for index in range(2):
                    row=ImportSession(user_id=uid,bank_id=bid,filename='race.tex',file_type='tex',status='preview')
                    q=phase2.question();q.update(source_id='9C6N4-1D.1',grade='Lớp 9',chapter='6',section='4',question_category='1')
                    row.set_parsed_questions([q]);db.session.add(row);db.session.commit();save_scope(row,phase2.SCOPE);ids.append(row.id)
            barrier=threading.Barrier(2)
            def save(sid):
                with app.app_context():
                    barrier.wait(timeout=10)
                    return ImportService.confirm_import(sid,bid,uid)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(save,ids))
            self.assertEqual(sorted(r['imported_count'] for r in results),[0,1])
            with app.app_context():
                self.assertEqual(BankQuestion.query.count(),1)
                self.assertEqual(ID6Counter.query.one().last_sequence,1)
                db.session.remove();db.engine.dispose()
