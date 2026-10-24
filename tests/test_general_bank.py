import io
from werkzeug.datastructures import FileStorage
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests.test_personalization_v2 import bank, app, db
from models import QuestionBank, BankQuestion
from services.bank_curriculum import is_probability_bank, catalog_for_bank
from services.import_service import ImportService
from services.import_scope import refresh_preview
from services.id6_metadata import enrich_preview
from services.latex_parser import parse_latex, _process_explanation, _extract_assets, _extract_formulas

SOURCE = r'''% @grade: 10
\section*{Các phép toán vectơ}
\begin{ex}%[10C4Hi-1T]
Cho $a=1$. Giá trị $a+1$ là
\choice{\True $2$}{$3$}{$4$}{$5$}
\loigiai{\begin{itemize}\item $a+1=2$.\item $a=1$.\end{itemize}}
\end{ex}
'''


def test_list_items_do_not_consume_formula_placeholders():
    assets = {}
    text = _process_explanation(r'\begin{itemize}\item $x=1$\item $y=2$\end{itemize}', assets)
    assert text.count('[[formula:') == 2
    assert len(assets) == 2


def test_math_wrapper_around_tikz_does_not_create_math_asset():
    assets = {}
    with patch('services.latex_parser.render_latex_block_result', return_value={'url':'/static/test.svg','verified':True}):
        text = _extract_assets(r'\[\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}\]', assets)
    text = _extract_formulas(text, assets)
    assert len(assets) == 1
    assert text.strip().startswith('[[formula:')


def test_grade10_import_save_and_reimport(bank):
    target = QuestionBank(name='Toán 10', grade='10', topic='Vectơ', subject='Toán', created_by=bank.teacher.id, visibility='private')
    db.session.add(target); db.session.commit()
    assert catalog_for_bank(target, []) == []
    session = ImportService.create_and_process_session(bank.teacher.id, FileStorage(stream=io.BytesIO(SOURCE.encode()), filename='vector.tex'), 'vector.tex', bank_id=target.id)
    enrich_preview(session, commit=False); refresh_preview(session); db.session.commit()
    question = session.get_parsed_questions()[0]
    assert question['grade'] == '10'
    assert question['difficulty_level'] == 'thong_hieu'
    assert question['question_category'] == 'Các phép toán vectơ'
    assert question['status'] != 'error', question['errors']
    assert not question.get('curriculum_node_id')
    ImportService.confirm_import(session.id, target.id, bank.teacher.id)
    stored = BankQuestion.query.filter_by(bank_id=target.id).one()
    assert stored.source_id == '10C4Hi-1T'
    assert stored.classification_status == 'teacher_confirmed'
    assert stored.curriculum_node_id is None
    again = ImportService.create_and_process_session(bank.teacher.id, FileStorage(stream=io.BytesIO(SOURCE.encode()), filename='vector.tex'), 'vector.tex', bank_id=target.id)
    refresh_preview(again)
    assert again.get_duplicate_report()['duplicate'] == 1
    client=app.test_client()
    with client.session_transaction() as login:
        login['_user_id'] = str(bank.teacher.id); login['_fresh'] = True
    page=client.get(f'/question-banks/{target.id}')
    assert page.status_code == 200
    assert 'Các phép toán vectơ' in page.get_data(as_text=True)
    assert 'Viết tập hợp không gian mẫu' not in page.get_data(as_text=True)


def test_grade9_other_topic_is_not_research(bank):
    target = QuestionBank(name='Đại số 9', grade='9', topic='Phương trình', subject='Toán', created_by=bank.teacher.id)
    assert not is_probability_bank(target, [])
    assert is_probability_bank(bank.bank, bank.bank.questions)


def test_duplicate_solution_preference_and_pair_choices(bank):
    from services.import_duplicates import scan_duplicates
    target=QuestionBank(name='General',grade='10',topic='Algebra',subject='Toán',created_by=bank.teacher.id,visibility='private')
    db.session.add(target);db.session.commit()
    source=SOURCE + SOURCE.replace('\\loigiai{\\begin{itemize}\\item $a+1=2$.\\item $a=1$.\\end{itemize}}','')
    session=ImportService.create_and_process_session(bank.teacher.id,FileStorage(stream=io.BytesIO(source.encode()),filename='pair.tex'),'pair.tex',bank_id=target.id)
    refresh_preview(session)
    qs=session.get_parsed_questions()
    rich=next(q for q in qs if q['explanation']);poor=next(q for q in qs if not q['explanation'])
    assert rich['duplicate']['state']=='new' and poor['duplicate']['state']=='duplicate'
    match=poor['duplicate']['matches'][0]
    session.duplicate_decisions=json.dumps({poor['import_uid']:{match['token']:'incoming'}})
    scan_duplicates(session,qs)
    assert poor['duplicate']['state']=='new' and rich['duplicate']['state']=='duplicate'
    session.duplicate_decisions=json.dumps({poor['import_uid']:{match['token']:'neither'}})
    scan_duplicates(session,qs)
    assert all(q['duplicate']['state']=='duplicate' for q in qs)


def test_bank_solution_replacement_preserves_question_id(bank):
    target=QuestionBank(name='General',grade='10',topic='Algebra',subject='Toán',created_by=bank.teacher.id,visibility='private')
    db.session.add(target);db.session.commit()
    def upload(source):
        session=ImportService.create_and_process_session(bank.teacher.id,FileStorage(stream=io.BytesIO(source.encode()),filename='pair.tex'),'pair.tex',bank_id=target.id)
        refresh_preview(session);db.session.commit();return session
    old=upload(SOURCE)
    ImportService.confirm_import(old.id,target.id,bank.teacher.id)
    original=BankQuestion.query.filter_by(bank_id=target.id).one();original.explanation='';db.session.commit()
    identity=original.id
    new=upload(SOURCE)
    q=new.get_parsed_questions()[0];match=q['duplicate']['matches'][0]
    assert q['duplicate']['state']=='review'
    new.duplicate_decisions=json.dumps({q['import_uid']:{match['token']:'incoming'}});db.session.commit()
    refresh_preview(new);db.session.commit()
    ImportService.confirm_import(new.id,target.id,bank.teacher.id)
    db.session.expire_all()
    saved=BankQuestion.query.filter_by(bank_id=target.id).one()
    assert saved.id==identity and saved.explanation and len(saved.options)==4
