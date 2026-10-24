"""Acceptance checks for the local renderer and teacher workflow."""
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

try:
    from tests.test_personalization_v2 import app, bank
except ImportError:
    from test_personalization_v2 import app, bank
from database import db
from models import BankQuestion, CurriculumNode
from services.local_tex import clean_svg, compile_svg
from services.practice_blueprint import readiness_error


def teacher_client(data):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(data.teacher.id)
        session['_fresh'] = True
    return client


def test_real_local_tikz_and_table():
    for source in [r'\begin{tikzpicture}\draw[->](0,0)--(2,0) node[right] {$x$};\end{tikzpicture}',
                   r'\begin{tabular}{|c|c|}\hline A & B \\\hline 1 & 2 \\\hline\end{tabular}']:
        svg = compile_svg(source)
        root = ET.fromstring(svg)
        assert root.get('data-render-method') == 'local_wasm_tex'
        assert 'data:font/ttf;base64,' in svg
        assert any(n.tag.endswith('path') for n in root.iter())
        assert 'https://' not in svg


def test_svg_disallows_active_content():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" onload="evil()"><script>evil()</script><foreignObject/><image href="https://evil/"/><path style="fill:url(https://evil)"/><use href="#safe"/></svg>'
    cleaned = ET.tostring(clean_svg(svg), encoding='unicode')
    assert all(s not in cleaned for s in ['onload', 'evil', 'script', 'foreignObject', '<image'])
    assert '#safe' in cleaned


def test_old_remote_url_does_not_send_files(monkeypatch, tmp_path):
    from services import latex_renderer
    monkeypatch.setattr(latex_renderer, 'ASSET_DIR', tmp_path)
    monkeypatch.setenv('LATEX_RENDERER_URL', 'https://old-renderer.invalid')
    monkeypatch.delenv('LATEX_RENDER_MODE', raising=False)
    monkeypatch.setenv('LATEX_RENDER_MODE', 'remote')
    result = latex_renderer.render_latex_block_result(r'\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}')
    assert result['verified'] and result['method'] == 'local_wasm_tex'


def test_bank_matrix_and_group_defaults(bank):
    node = CurriculumNode.query.first()
    response = teacher_client(bank).get(f'/question-banks/{bank.bank.id}?node_id={node.id}&difficulty=thong_hieu&type=short_answer')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'knowledge-matrix' in html and 'Độ phủ ngân hàng' in html
    assert '1 câu phù hợp' in html
    assert f'node_id={node.id}' in html
    assert 'manual_question.js' in html
    assert 'vendor/mathjax/tex-mml-chtml.js' in html


def test_manual_reviewed_and_duplicate_blocked(bank):
    client = teacher_client(bank)
    node = CurriculumNode.query.first()
    url = next(rule.rule for rule in app.url_map.iter_rules() if rule.endpoint == 'add_bank_question').replace('<int:bank_id>', str(bank.bank.id))
    data = dict(question_text='Gieo xúc xắc, xác suất ra 2?', question_type='single',
                difficulty_level='nhan_biet', curriculum_node_id=str(node.id), reviewed='1',
                option_text=['1/6', '1/2', '1/3', '1'], correct_option='0')
    count = BankQuestion.query.count()
    assert client.post(url, data=data).status_code == 302
    new = BankQuestion.query.order_by(BankQuestion.id.desc()).first()
    assert BankQuestion.query.count() == count + 1
    assert readiness_error(new) is None
    response = client.post(url, data=data, follow_redirects=True)
    assert BankQuestion.query.count() == count + 1
    assert 'không lưu bản trùng' in response.get_data(as_text=True)
    data['correct_option'] = '1'
    response = client.post(url, data=data, follow_redirects=True)
    assert BankQuestion.query.count() == count + 1
    assert 'đáp án khác' in response.get_data(as_text=True)


def test_manual_tf_labels_and_numeric_validation(bank):
    client = teacher_client(bank)
    node = CurriculumNode.query.first()
    url = next(rule.rule for rule in app.url_map.iter_rules() if rule.endpoint == 'add_bank_question').replace('<int:bank_id>', str(bank.bank.id))
    data = dict(question_text='Xét bốn nhận định về phép thử', question_type='true_false',
                difficulty_level='thong_hieu', curriculum_node_id=str(node.id), reviewed='1',
                option_text=['Có 6 kết quả', 'Có 2 kết quả', 'Có 3 số chẵn', 'Có 7 kết quả'],
                correct_option=['true', 'false', 'true', 'false'],
                statement_node=['']*4, statement_level=['']*4)
    client.post(url, data=data)
    new = BankQuestion.query.order_by(BankQuestion.id.desc()).first()
    assert readiness_error(new) is None
    assert len(json.loads(new.learning_metadata)['statements']) == 4
    count = BankQuestion.query.count()
    data.update(question_text='Xác suất bằng bao nhiêu?', question_type='short_answer',
                short_answers='không phải số', short_answer_mode='numeric')
    client.post(url, data=data)
    assert BankQuestion.query.count() == count


def test_import_uses_group_but_preserves_question_type(bank):
    client = teacher_client(bank)
    node = CurriculumNode.query.first()
    source = r'\begin{ex}Gieo xúc xắc.\shortans{0.5}\loigiai{Có ba số chẵn.}\end{ex}'
    url = next(rule.rule for rule in app.url_map.iter_rules() if rule.endpoint == 'import_upload')
    response = client.post(url, data={'bank_id':str(bank.bank.id), 'default_node_id':str(node.id),
        'default_difficulty':'thong_hieu', 'file':(io.BytesIO(source.encode()),'group.tex')})
    assert response.status_code == 200, response.get_json()
    q = response.get_json()['questions'][0]
    assert q['curriculum_node_id'] == node.id
    assert q['difficulty_level'] == 'thong_hieu'
    assert q['question_type'] == 'short_answer'
    assert q.get('classification_status') != 'teacher_confirmed'


def test_tex_file_to_bank_with_figures_and_repeat_dedup(bank):
    client = teacher_client(bank)
    node = CurriculumNode.query.first()
    source = Path('docs/examples/nhap_cau_hoi_tikz.tex').read_bytes()
    upload = next(rule.rule for rule in app.url_map.iter_rules() if rule.endpoint == 'import_upload')
    before = BankQuestion.query.count()
    for repeat in (False, True):
        response = client.post(upload, data={'bank_id':str(bank.bank.id), 'default_node_id':str(node.id),
            'default_difficulty':'nhan_biet', 'file':(io.BytesIO(source),'demo.tex')})
        assert response.status_code == 200, response.get_json()
        preview = response.get_json()
        assert len(preview['questions']) == 3
        blocks = [f for q in preview['questions'] for f in q['formulas'].values() if f.get('source_format') == 'LaTeXBlock']
        assert len(blocks) == 2
        assert all(f['verification_status'] == 'verified' for f in blocks)
        result = client.post(f"/question-banks/import/{preview['session_id']}/confirm", json={'bank_id':bank.bank.id})
        assert result.status_code == 200, result.get_json()
        assert result.get_json()['imported_count'] == (0 if repeat else 3)
        assert BankQuestion.query.count() == before + 3


def test_document_packages_do_not_break_independent_figure():
    from services.local_tex import fragment_preamble
    preamble=r"\usepackage{tabularx}" + "\n" + r"\pgfplotsset{compat=1.18}" + "\n" + r"\renewcommand{\loigiai}[1]{"
    clean=fragment_preamble(r"\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}",preamble)
    assert 'tabularx' not in clean and 'pgfplotsset' not in clean and 'loigiai' not in clean


def test_tkz_tab_is_bundled_and_different_sources_have_distinct_figures():
    from services.latex_renderer import render_latex_block_result
    source=r"\begin{tikzpicture}\tkzTabInit{$x$/1,$f(x)$/2}{$0$,$1$}\tkzTabVar{-/$0$,+/$1$}\end{tikzpicture}"
    first=render_latex_block_result(source)
    second=render_latex_block_result(source.replace('+/$1$','+/$2$'))
    assert first['verified'] and second['verified'], (first,second)
    assert first['url']!=second['url']
