"""Populate the bundled workbook template using portable Open XML.

Formatting is authored in assessment_matrix_template.xlsx. Runtime needs only
Python's standard library, no Office installation or external rendering service.
"""
import io
import math
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ET.register_namespace('', NS)
TEMPLATE = Path(__file__).resolve().parents[1] / 'resources' / 'assessment_matrix_template.xlsx'


def tag(name):
    return '{' + NS + '}' + name


def cell(row, address, value, style, formula=None):
    node = ET.SubElement(row, tag('c'), r=address, s=str(style))
    if formula:
        ET.SubElement(node, tag('f')).text = formula
        ET.SubElement(node, tag('v')).text = str(value)
    elif isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError('Giá trị số không hợp lệ trong ma trận.')
        ET.SubElement(node, tag('v')).text = str(value)
    else:
        node.set('t', 'inlineStr')
        # Explicit string cells prevent spreadsheet formula injection.
        text = ET.SubElement(ET.SubElement(node, tag('is')), tag('t'))
        text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        text.text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value or ''))[:32767]


def sheet_xml(source, matrix, detail=False):
    """Fill the styled template; formulas use the visible question ledger."""
    original = ET.fromstring(source)
    styles = {c.get('r'): c.get('s', '0') for c in original.iter(tag('c'))}
    root = ET.Element(tag('worksheet'))
    properties = ET.SubElement(root, tag('sheetPr'))
    ET.SubElement(properties, tag('pageSetUpPr'), fitToPage='1')
    views = ET.SubElement(root, tag('sheetViews'))
    view = ET.SubElement(views, tag('sheetView'), workbookViewId='0', showGridLines='0')
    header_end = 6 if detail else 9
    ET.SubElement(view, tag('pane'), ySplit=str(header_end), topLeftCell=f'A{header_end+1}', activePane='bottomLeft', state='frozen')
    widths = [7, 28, 38, 20, 20, 18, 18, 12, 12, 10, 22, 32] if detail else [5, 23, 30] + [7]*15 + [9]
    last_col = chr(64 + len(widths))
    cols = ET.SubElement(root, tag('cols'))
    for i, width in enumerate(widths, 1):
        ET.SubElement(cols, tag('col'), min=str(i), max=str(i), width=str(width), customWidth='1')
    data = ET.SubElement(root, tag('sheetData'))
    merges = []

    def line(index, values, sample_row, formulas=None, height=None):
        if height is None:
            lines = max((math.ceil(len(str(v)) / max(5, widths[i]-2)) for i,v in enumerate(values)), default=1)
            height = max(30, min(260, lines*16))
        row = ET.SubElement(data, tag('row'), r=str(index), ht=str(height), customHeight='1')
        for i, value in enumerate(values):
            col = chr(65+i)
            style = styles.get(f'{col}{sample_row}', styles.get(f'A{sample_row}', '0'))
            cell(row, f'{col}{index}', value, style, (formulas or {}).get(i))

    def note(index, value, sample=4):
        line(index, [value], sample, height=32)
        merges.append(f'A{index}:{last_col}{index}')

    note(2, 'ĐỐI CHIẾU CÂU HỎI' if detail else 'MA TRẬN ĐỀ KIỂM TRA ĐỊNH KÌ', 2)
    note(3, f"{matrix['title']} · {matrix['course']} · {matrix['duration']} phút · {matrix['count']} câu · 10 điểm", 3)
    note(4, f"Bố cục Phụ lục Công văn 7991/BGDĐT-GDTrH (17/12/2024). {matrix['missing']} câu cần bổ sung nhãn.")
    note(5, f"Chưa phân mức: {matrix['unknown_count']} câu / {matrix['unknown_points']:.4f} điểm; chưa cộng vào các cột Biết–Hiểu–Vận dụng."
         if matrix['unknown_count'] else 'Các mức và điểm được tổng hợp từ nhãn giáo viên xác nhận trong đề đã lưu.')
    end_detail = len(matrix['details']) + 6
    scope = "'Đối chiếu câu'!"
    def escaped(ref):
        return f'SUBSTITUTE(SUBSTITUTE(SUBSTITUTE({ref},"~","~~"),"*","~*"),"?","~?")'
    def criteria(col, ref):
        return f'{scope}${col}$7:${col}${end_detail},{ref}'
    def sum_points(*conditions):
        return f'SUMIFS({scope}$I$7:$I${end_detail},' + ','.join(conditions) + ')'

    if detail:
        line(6, ['Câu','Chủ đề/Chương','Nội dung/đơn vị kiến thức','Mã kiến thức','Hình thức','Mức gốc','Mức xuất','Điểm gốc','Điểm / 10','Số ý Đ/S','Tình trạng nhãn','Ghi chú'], 6, height=46)
        keys = ('number','chapter','category','code','kind','level','export_level','raw_points','points','statements','status','note')
        for index, row in enumerate(matrix['details'], 7):
            line(index, [row[key] for key in keys], 7)
        end = end_detail
        line(end+1, ['Tổng','','','','','','',matrix['raw_total'],10,'','',''], 7,
             {7:f'SUM(H7:H{end})',8:f'SUM(I7:I{end})'}, height=32)
        last_row = end+1
        ET.SubElement(root, tag('autoFilter'), ref=f'A6:L{end}')
    else:
        line(6, ['TT','Chủ đề/Chương','Nội dung/đơn vị kiến thức','Mức độ đánh giá']+['']*11+['Tổng','','','Tỉ lệ % điểm'], 6, height=32)
        line(7, ['','','','TNKQ']+['']*8+['Tự luận']+['']*6, 7, height=26)
        line(8, ['','','','Nhiều lựa chọn','','','Đúng – Sai','','','Trả lời ngắn']+['']*9, 8, height=28)
        line(9, ['','','']+list(matrix['levels'].values())*5+[''], 9, height=40)
        merges.extend(['A6:A9','B6:B9','C6:C9','D6:O6','D7:L7','M7:O8',
                       'D8:F8','G8:I8','J8:L8','P6:R8','S6:S9'])
        chapter_start, chapter_number, previous = 10, 0, None
        for index, row in enumerate(matrix['rows'], 10):
            if row['chapter'] != previous:
                if previous is not None and index-1 > chapter_start:
                    merges.extend([f'A{chapter_start}:A{index-1}',f'B{chapter_start}:B{index-1}'])
                chapter_start, previous = index, row['chapter']
                chapter_number += 1
            formulas = {}
            base = [criteria('B', escaped(f'B{chapter_start}')), criteria('C', escaped(f'C{index}'))]
            for offset, kind in enumerate(matrix['kinds'].values()):
                for level_index, level in enumerate(matrix['levels'].values()):
                    formulas[3+offset*3+level_index] = 'COUNTIFS(' + ','.join(base+[criteria('E', f'"{kind}"'),criteria('G',f'"{level}"')]) + ')'
            for k in range(3):
                refs = ','.join(f'{chr(68+k+3*j)}{index}' for j in range(4))
                formulas[15+k] = f'SUM({refs})'
            formulas[18] = sum_points(*base) + '*10'
            line(index, [chapter_number if index == chapter_start else '',row['chapter'] if index == chapter_start else '',row['category'],
                         *row['counts'],*row['totals'],row['points']*10], 10, formulas)
        end = len(matrix['rows'])+9
        if end > chapter_start:
            merges.extend([f'A{chapter_start}:A{end}',f'B{chapter_start}:B{end}'])
        line(end+1, ['Tổng số câu','','',*matrix['column_totals'],*matrix['level_totals'],''], 11,
             {i:f'SUM({chr(65+i)}10:{chr(65+i)}{end})' for i in range(3,18)}, height=30)
        for offset, label in ((2,'Tổng số điểm'),(3,'Tỉ lệ %')):
            values = [label,'',''] + ['']*16
            formulas = {}
            factor = 1 if offset == 2 else 10
            for j,(kind,point) in enumerate(zip(matrix['kinds'].values(),matrix['section_points'])):
                col = 3+3*j
                values[col] = point*factor
                formulas[col] = sum_points(criteria('E',f'"{kind}"')) + ('' if factor == 1 else '*10')
                merges.append(f'{chr(65+col)}{end+offset}:{chr(67+col)}{end+offset}')
            for j,(level,point) in enumerate(zip(matrix['levels'].values(),matrix['level_points'])):
                values[15+j] = point*factor
                formulas[15+j] = sum_points(criteria('G',f'"{level}"')) + ('' if factor == 1 else '*10')
            line(end+offset, values, 12 if offset == 2 else 13, formulas, height=30)
        for offset in (1,2,3):
            merges.append(f'A{end+offset}:C{end+offset}')
        last_row = end+7
        note(end+5, 'Quy ước xuất: Nhận biết → Biết; Thông hiểu → Hiểu; Vận dụng cao gộp vào Vận dụng. Nhãn gốc giữ ở Đối chiếu câu.')
        note(end+6, 'Đúng – Sai đếm theo câu; số ý ghi riêng. Cột Tự luận giữ theo mẫu; đề không có tự luận thì để trống số câu.')
        note(end+7, 'Tổng điểm các hình thức = 10. Tỉ lệ theo điểm thực tế của đề, không áp đặt các tỉ lệ minh họa trong phụ lục.')
    merged = ET.SubElement(root, tag('mergeCells'), count=str(len(merges)))
    for ref in merges:
        ET.SubElement(merged, tag('mergeCell'), ref=ref)
    ET.SubElement(root, tag('pageMargins'), left='0.25', right='0.25', top='0.4', bottom='0.4', header='0.15', footer='0.15')
    ET.SubElement(root, tag('pageSetup'), paperSize='8', orientation='landscape', fitToWidth='1', fitToHeight='0')
    footer = ET.SubElement(root, tag('headerFooter'))
    ET.SubElement(footer, tag('oddFooter')).text = '&LMa trận đề kiểm tra&RP &P / &N'
    return ET.tostring(root, encoding='utf-8', xml_declaration=True), last_row, last_col


def export_matrix(matrix):
    output = io.BytesIO()
    with zipfile.ZipFile(TEMPLATE) as source, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as target:
        pages = []
        replacements = {}
        for i in (1,2):
            name = f'xl/worksheets/sheet{i}.xml'
            replacements[name], end, col = sheet_xml(source.read(name), matrix, detail=i == 2)
            pages.append((end,col))
        workbook = ET.fromstring(source.read('xl/workbook.xml'))
        old = workbook.find(tag('definedNames'))
        if old is not None:
            workbook.remove(old)
        names = ET.SubElement(workbook, tag('definedNames'))
        for i, (name, (end,col)) in enumerate(zip(('Ma trận','Đối chiếu câu'),pages)):
            ET.SubElement(names, tag('definedName'), name='_xlnm.Print_Area', localSheetId=str(i)).text = f"'{name}'!$A$1:${col}${end}"
            ET.SubElement(names, tag('definedName'), name='_xlnm.Print_Titles', localSheetId=str(i)).text = f"'{name}'!$1:${9 if i == 0 else 6}"
        calc = workbook.find(tag('calcPr'))
        if calc is not None:
            workbook.remove(calc)
        ET.SubElement(workbook, tag('calcPr'), calcId='191029', fullCalcOnLoad='1')
        replacements['xl/workbook.xml'] = ET.tostring(workbook, encoding='utf-8', xml_declaration=True)
        for name in source.namelist():
            target.writestr(name, replacements.get(name, source.read(name)))
    output.seek(0)
    return output
