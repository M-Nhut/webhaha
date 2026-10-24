import io
import zipfile
from decimal import Decimal
from xml.etree import ElementTree as ET
from tests.test_personalization_v2 import bank, app, db
from tests.test_standalone_assessment import uploaded, form, login
from services.standalone_assessment import save_paper
from services.assessment_matrix import build_matrix
from services.matrix_xlsx import export_matrix, NS


def test_matrix_missing_labels_and_legacy_scale_do_not_mutate(bank):
    exam = save_paper(uploaded(bank), bank.teacher, form(bank))
    for q in exam.questions:
        q.points = 1
    matrix = build_matrix(exam)
    assert matrix['missing'] == 3 and matrix['count'] == 3
    assert sum(Decimal(str(r['points'])) for r in matrix['details']) == 10
    assert [q.points for q in exam.questions] == [1,1,1]
    assert matrix['details'][1]['statements'] == 4
    assert sum(r['count'] for r in matrix['rows']) == 3


def test_xlsx_data_formulas_styles_and_permissions(bank):
    values = form(bank)
    values.update(dict(q0_report_category='=1+1 * ? & <test>', q0_report_chapter='Chương 1', q0_report_confirmed='yes', q0_difficulty_level='nhan_biet'))
    exam = save_paper(uploaded(bank), bank.teacher, values)
    matrix = build_matrix(exam)
    assert matrix['missing'] == 2
    assert matrix['details'][0]['category'].startswith('=1+1')
    raw = export_matrix(matrix).getvalue()
    ns = {'x': NS}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.testzip() is None
        for name in z.namelist():
            if name.endswith('.xml'):
                ET.fromstring(z.read(name))
        sheet = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        detail = ET.fromstring(z.read('xl/worksheets/sheet2.xml'))
        injected = detail.find(".//x:c[@r='C7']", ns)
        assert injected.get('t') == 'inlineStr' and injected.find('x:f', ns) is None
        assert detail.find(".//x:c[@r='I7']/x:v", ns) is not None
        assert 'SUBSTITUTE' in sheet.find(".//x:c[@r='D10']/x:f", ns).text
        assert detail.find('x:autoFilter', ns) is not None
        merges = {m.get('ref') for m in sheet.findall('x:mergeCells/x:mergeCell', ns)}
        assert {'B6:B9', 'D6:O6', 'D7:L7', 'M7:O8', 'P6:R8', 'S6:S9'} <= merges
        assert sheet.find('x:pageSetup', ns).get('orientation') == 'landscape'
        assert sheet.find('.//x:pane', ns).get('state') == 'frozen'
        total_row = len(matrix['rows']) + 11
        assert sum(float(sheet.find(f".//x:c[@r='{col}{total_row}']/x:v", ns).text) for col in 'DGJM') == 10
    teacher = login(bank.teacher)
    assert teacher.get(f'/assessments/{exam.id}/matrix').status_code == 200
    response = teacher.get(f'/assessments/{exam.id}/matrix?download=xlsx')
    assert response.status_code == 200 and response.data[:2] == b'PK'
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert login(bank.student).get(f'/assessments/{exam.id}/matrix?download=xlsx').status_code == 403
    exam.course.teacher_id = bank.student.id
    db.session.commit()
    assert teacher.get(f'/assessments/{exam.id}/matrix?download=xlsx').status_code == 403


def test_chapters_three_levels_and_original_evidence(bank):
    values = form(bank)
    for i, (chapter, level) in enumerate([('Chương A', 'nhan_biet'), ('Chương A', 'thong_hieu'), ('Chương B', 'van_dung_cao')]):
        values.update({f'q{i}_report_category': 'Cùng tên đơn vị', f'q{i}_report_chapter': chapter,
                       f'q{i}_report_confirmed': 'yes', f'q{i}_difficulty_level': level})
    exam = save_paper(uploaded(bank), bank.teacher, values)
    matrix = build_matrix(exam)
    assert matrix['missing'] == 0 and len(matrix['rows']) == 2
    assert matrix['level_totals'] == [1, 1, 1]
    assert matrix['details'][2]['export_level'] == 'Vận dụng'
    assert matrix['details'][2]['level'] == 'Vận dụng cao'
    assert exam.questions[2].difficulty_level == 'van_dung_cao'
    assert all(row['counts'][9:] == [0, 0, 0] for row in matrix['rows'])
    assert sum(matrix['section_points']) == 10


def test_linked_chapter_is_snapshotted(bank):
    from models import CurriculumNode
    node = CurriculumNode.query.first()
    values = form(bank)
    values.update(dict(q0_report_code=node.canonical_code, q0_report_confirmed='yes'))
    exam = save_paper(uploaded(bank), bank.teacher, values)
    original = build_matrix(exam)['details'][0]['chapter']
    node.chapter_name = 'Tên mới'
    db.session.flush()
    assert build_matrix(exam)['details'][0]['chapter'] == original


def test_unclassified_levels_are_explicit_not_assigned_to_knowledge(bank):
    exam = save_paper(uploaded(bank), bank.teacher, form(bank))
    matrix = build_matrix(exam)
    assert matrix['unknown_count'] == 3 and matrix['unknown_points'] == 10
    assert matrix['level_totals'] == [0, 0, 0]
    assert sum(matrix['section_points']) == 10
