import io
import pytest
from PIL import Image
from services.tex_table import parse_table, display_asset
from services.latex_parser import _extract_assets, _process_explanation

TABLE = r'''\begin{tabular}{|c|*{2}{c|}}\hline
Lần đầu & \multicolumn{2}{c|}{Kết quả}\\\hline
$5$ & $(5;10;15)$ & $(5;15;10)$\\\hline
\end{tabular}'''


def test_vietnamese_table_spans_and_repeated_columns():
    table = parse_table(TABLE)
    assert table['columns'] == 3
    assert table['rows'][0][1] == {'text':'Kết quả','colspan':2,'align':'c'}
    assert table['rows'][1][1]['text'] == '$(5;10;15)$'


def test_nested_math_rows_and_escaped_ampersands():
    table = parse_table(r'\begin{tabular}{cc} A\&B & $\begin{matrix}1&2\\3&4\end{matrix}$\\ C & D\end{tabular}')
    assert len(table['rows']) == 2
    assert table['rows'][0][0]['text'] == 'A&B'
    assert r'3&4' in table['rows'][0][1]['text']


@pytest.mark.parametrize('source', [r'\begin{tabular}{cc}A&B&C\end{tabular}',r'\begin{tabular}{c}\multirow{2}{*}{A}\end{tabular}',r'\begin{tabular}{c}\custommacro{A}\end{tabular}'])
def test_unknown_or_malformed_tables_are_not_silently_rewritten(source):
    assert parse_table(source) is None


def test_old_failed_asset_is_recovered_without_mutation():
    saved = dict(source_format='LaTeXBlock', source_text=TABLE, conversion_status='failed',render_error='old remote unavailable')
    rendered = display_asset(saved)
    assert rendered['table']['columns'] == 3
    assert rendered['conversion_status'] == 'converted'
    assert saved['conversion_status'] == 'failed'


def test_layout_cleanup_keeps_explanation_order_and_table():
    assets = {}
    content = _process_explanation('Mở đầu. '+r'\small\renewcommand{\arraystretch}{1.15}'+TABLE+' Kết luận.', assets)
    assert content.index('Mở đầu') < content.index('[[formula:') < content.index('Kết luận')
    assert r'\small' not in content and r'\renewcommand' not in content
    assert next(iter(assets.values()))['table']['rows'][0][0]['text'] == 'Lần đầu'


def test_inline_tikz_is_compiled_locally():
    assets = {}
    content = _extract_assets(r'Hình: \tikz[scale=1]{\draw[->] (0,0)--(1,1) node[right] {$A$};} hết.', assets)
    assert len(assets) == 1 and '[[formula:' in content and content.endswith(' hết.')
    item = next(iter(assets.values()))
    assert item['render_method'] in ('local_wasm_tex', 'cached_tex'), item
    assert item['verification_status'] == 'verified', item


def test_question_image_decodes_and_rejects_fake_image(monkeypatch, tmp_path):
    from services import question_images
    monkeypatch.setattr(question_images, 'DIRECTORY', tmp_path)
    upload = io.BytesIO()
    Image.new('RGB', (20,10), 'white').save(upload,format='PNG')
    upload.seek(0)
    url = question_images.save_question_image(upload)
    assert url.startswith('/static/uploads/questions/manual_')
    assert Image.open(tmp_path / url.rsplit('/',1)[1]).size == (20,10)
    with pytest.raises(ValueError): question_images.save_question_image(io.BytesIO(b'<svg onload="evil()"/>'))


def test_duplicate_math_layout_does_not_change_identity():
    from services.import_duplicates import math_identity
    assert math_identity(r'\Omega=\left\{1,\ 2\right\}') == math_identity(r'\Omega=\{1,2\}')
    assert math_identity(r'\Omega=\bigl\{1,2\bigr\}') == math_identity(r'\Omega=\{1,2\}')
    assert math_identity(r'P=\frac{1}{2}') != math_identity(r'P=\frac{1}{3}')
    assert math_identity(r'\{(1;2)\}') != math_identity(r'\{(2;1)\}')
    assert math_identity(r'\alpha b') != math_identity(r'\alphab')
    assert math_identity(r'\text{a b}') != math_identity(r'\text{ab}')


def test_immini_optional_and_answers_keep_the_diagram(tmp_path):
    from services.latex_parser import parse_latex
    source = r'''
\begin{ex}\immini[thm]{Quan sát hình.\choiceTF{\True A}{B}{\True C}{D}}{
\definecolor{wheelBlue}{RGB}{50,100,180}
\begin{tikzpicture}\fill[wheelBlue] (0,0) circle (1);\end{tikzpicture}}
\loigiai{Có hai ý đúng.}\end{ex}
'''
    path = tmp_path / 'wheel.tex'; path.write_text(source,encoding='utf-8')
    q = parse_latex(path)[0]
    assert len(q['statements']) == 4
    assert r'\immini' not in q['question_text']
    assert r'\definecolor' not in q['question_text']
    assert '[[formula:' in q['question_text']
    block = next(f for f in q['formulas'].values() if f.get('source_format')=='LaTeXBlock')
    assert block['verification_status']=='verified', block
    assert r'\definecolor{wheelBlue}' in block['source_preamble']


def test_old_failed_tikz_recovers_on_first_read(monkeypatch, tmp_path):
    from services import formula_display, latex_renderer
    monkeypatch.setattr(latex_renderer,'ASSET_DIR',tmp_path)
    formula_display._recover_legacy.cache_clear()
    old = dict(source_format='LaTeXBlock',source_text=r'\begin{tikzpicture}\draw (0,0)--(1,0);\end{tikzpicture}',conversion_status='failed',render_method='remote_tex')
    shown = formula_display.display_asset(old)
    assert shown['conversion_status']=='fallback_svg'
    assert shown['svg_cache_key'].startswith('/static/uploads/questions/')
    assert old['conversion_status']=='failed'


def test_vietnamese_node_labels_keep_accents():
    from services.local_tex import encode_text_accents, compile_svg
    assert encode_text_accents('Tấm bìa') == r"T\ensuremath{\acute{\hat{\text{a}}}}m b\`{i}a"
    assert r'\hbox{u' in encode_text_accents('ư')
    assert encode_text_accents('ờ').startswith(r'\`{\hbox{o')
    svg = compile_svg(r'\begin{tikzpicture}\node {Tấm bìa A, Đường};\end{tikzpicture}')
    assert 'data-render-method="local_wasm_tex"' in svg
