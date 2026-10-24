"""Read-only projection of saved papers into the 7991 matrix layout."""
import json
from collections import OrderedDict
from decimal import Decimal
from models import CurriculumNode
from services.assessment_scoring import kind_of, distribute

KINDS = OrderedDict(single='Nhiều lựa chọn', true_false='Đúng – Sai', short_answer='Trả lời ngắn', essay='Tự luận')
LEVELS = OrderedDict(nhan_biet='Biết', thong_hieu='Hiểu', van_dung='Vận dụng')
ORIGINAL_LEVELS = dict(nhan_biet='Nhận biết', thong_hieu='Thông hiểu', van_dung='Vận dụng', van_dung_cao='Vận dụng cao')


def build_matrix(exam):
    questions = sorted(exam.questions, key=lambda q: (q.order_index, q.id))
    if not questions:
        raise ValueError('Đề chưa có câu hỏi để xuất ma trận.')
    weights = [Decimal(str(q.points or 0)) for q in questions]
    if any(not p.is_finite() or p <= 0 for p in weights):
        raise ValueError('Đề có điểm câu hỏi không hợp lệ; cần kiểm tra trước khi xuất.')
    points = distribute(weights, Decimal(10))
    codes = {q.curriculum_code for q in questions if q.curriculum_code}
    nodes = {n.canonical_code: n for n in CurriculumNode.query.filter(CurriculumNode.canonical_code.in_(codes)).all()} if codes else {}
    details, groups = [], OrderedDict()
    for index, (question, point) in enumerate(zip(questions, points), 1):
        reporting = json.loads(question.learning_metadata or '{}').get('reporting', {})
        confirmed = reporting.get('confirmed') is True
        category = (question.topic_snapshot or '').strip() if confirmed else ''
        code = (question.curriculum_code or '').strip() if confirmed else ''
        chapter = (reporting.get('chapter') or '').strip() if confirmed else ''
        # Older papers lack a chapter snapshot; resolve only their explicit code.
        if not chapter and code in nodes:
            node = nodes[code]
            chapter = f'Chương {node.chapter_code}: {node.chapter_name}'
        original_level = question.difficulty_level if confirmed else ''
        level = 'van_dung' if original_level == 'van_dung_cao' else original_level
        level = level if level in LEVELS else 'unknown'
        incomplete = not category or not chapter or level == 'unknown'
        chapter = chapter or 'Chưa xác nhận chủ đề/chương'
        category = category or 'Chưa xác nhận kiến thức'
        label = f'{category} ({code})' if code else category
        kind = kind_of(question.question_type)
        if kind not in KINDS:
            raise ValueError('Đề có hình thức câu hỏi chưa hỗ trợ xuất ma trận.')
        details.append(dict(number=index, chapter=chapter, category=label, code=code,
            kind=KINDS[kind], kind_key=kind, level=ORIGINAL_LEVELS.get(original_level, 'Chưa xác nhận'),
            export_level=LEVELS.get(level, 'Chưa xác nhận'), level_key=level,
            raw_points=float(weights[index-1]), points=float(point),
            statements=len(question.answers) if kind == 'true_false' else 0,
            status='Cần bổ sung nhãn' if incomplete else 'Đã xác nhận',
            note='Gộp Vận dụng cao vào Vận dụng khi xuất' if original_level == 'van_dung_cao' else ''))
        key = (chapter.casefold(), label.casefold())
        if key not in groups:
            groups[key] = dict(chapter=chapter, category=label, counts=[0]*12, totals=[0]*3, count=0, points=Decimal(0))
        group = groups[key]
        group['count'] += 1
        group['points'] += point
        if level != 'unknown':
            offset = list(LEVELS).index(level)
            group['counts'][list(KINDS).index(kind)*3 + offset] += 1
            group['totals'][offset] += 1
    rows = sorted(groups.values(), key=lambda r: (r['chapter'].casefold(), r['category'].casefold()))
    for row in rows:
        row['points'] = float(row['points'])
    level_points = [float(sum(Decimal(str(r['points'])) for r in details if r['level_key'] == key)) for key in LEVELS]
    section_points = [float(sum(Decimal(str(r['points'])) for r in details if r['kind_key'] == key)) for key in KINDS]
    return dict(title=exam.title, course=exam.course.course_name, duration=exam.duration_minutes,
        exam_id=exam.id, published=exam.is_active, count=len(questions),
        missing=sum(r['status'] != 'Đã xác nhận' for r in details),
        unknown_count=sum(r['level_key'] == 'unknown' for r in details),
        unknown_points=float(sum(Decimal(str(r['points'])) for r in details if r['level_key'] == 'unknown')),
        raw_total=float(sum(weights)), rows=rows, details=details, levels=LEVELS,
        kinds=KINDS, level_points=level_points, section_points=section_points,
        column_totals=[sum(row['counts'][i] for row in rows) for i in range(12)],
        level_totals=[sum(row['totals'][i] for row in rows) for i in range(3)])
