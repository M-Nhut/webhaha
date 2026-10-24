"""Read-only Jinja checks; never imports the application or opens a database."""
from pathlib import Path
from types import SimpleNamespace as NS
import json
import re
import datetime as dt
from urllib.parse import urlencode
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[4]
env = Environment(loader=ChoiceLoader([
    DictLoader({'base.html': '{% block head %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}'}),
    FileSystemLoader(ROOT / 'templates'),
]), autoescape=select_autoescape(['html']))
env.globals.update(csrf_token=lambda: 'synthetic-csrf', url_for=lambda endpoint, **values: '/' + endpoint + '?' + urlencode(values))
course = NS(id=1, course_name='Lớp dài · Toán học', subject='Toán', teacher_id=2)
student = NS(id=4, fullname='Học sinh giả lập', username='qa_student')
bank = NS(id=1, name='Ngân hàng giả lập', visibility='shared', subject='Toán')
checks = []

def render(name, context, description):
    html = env.get_template(name).render(current_user=NS(id=2, role='teacher'), **context)
    assert not re.search(r'\sstyle\s*=|\son(?:click|change)\s*=', html)
    checks.append(description)
    return html

base_list = dict(courses=[course], selected_course=course, students=[])
render('teacher_practice_list.html', dict(courses=[], selected_course=None, students=[]), 'List: no classes')
render('teacher_practice_list.html', base_list, 'List: no roster')
for average in [None, 0.0, 7.5]:
    html = render('teacher_practice_list.html', dict(base_list, students=[dict(student=student, total_practice=0, total_assessments=1, average=average, latest_activity=None)]), 'List: average ' + str(average))
    assert ('Chưa có dữ liệu</span>' in html) == (average is None)

profile = dict(overall_mastery=0, answer_count=0, cold_start=True, cold_start_min_answers=3, total_attempts=0, weak_regions=[], practice_skill_mastery={})
profile.update({level + '_accuracy': None for level in ['nhan_biet','thong_hieu','van_dung','van_dung_cao']})
base_detail = dict(student=student, selected_course_id=1, course_choices=[course], available_courses=[course], profiles={'Toán': profile}, available_banks=[bank], bank_course_counts={1:{1:22}}, visible_bank_counts={1:22}, assessment_evidence=[], submissions=[])
render('teacher_practice_detail.html', dict(base_detail, profiles={}), 'Detail: no profile')
render('teacher_practice_detail.html', base_detail, 'Detail: unknown and cold start')
render('teacher_practice_detail.html', dict(base_detail, available_banks=[]), 'Detail: no usable banks')
profile_known = dict(profile, answer_count=10, cold_start=False, overall_mastery=.7, nhan_biet_accuracy=0.0, practice_skill_mastery={'9C8-i-1||nhan_biet':dict(mastery=0, sufficient=False, state='Chưa đủ dữ liệu', distinct_count=1, session_count=1)})
render('teacher_practice_detail.html', dict(base_detail, profiles={'Toán':profile_known}), 'Detail: genuine zero differs from missing evidence')
for observation_state in ['dated', 'undated', 'limit-20']:
    observations = [NS(error_label='Sai đáp án ' + str(index), observed_claim='Cần đối chiếu câu trả lời <nội dung>', created_at=None if observation_state == 'undated' else dt.datetime(2026, 10, 16, 9, 30)) for index in range(25 if observation_state == 'limit-20' else 1)]
    html = render('teacher_practice_detail.html', dict(base_detail, error_observations={'Toán': observations}), 'Detail: read-only observed errors / ' + observation_state)
    assert 'Lỗi quan sát từ bài đã chấm' in html and 'Cần đối chiếu câu trả lời &lt;nội dung&gt;' in html
    assert html.count('class="teacher-observation-heading"') == min(20, len(observations))
    observed_html = re.search(r'<ul class="teacher-observation-list">(.*?)</ul>', html, re.S).group(1)
    assert not re.search(r'<(?:form|input|button|select|textarea)\b', observed_html)
    assert 'Kết quả đề kiểm tra' in html

for kind in ['single','multi','multiple_choice','true_false','truefalse','short_answer','essay','tu_luan','unsupported-history']:
    answers = [NS(answer_text='Đáp án giả lập', is_correct=True), NS(answer_text='Lựa chọn khác', is_correct=False)]
    question = NS(id=10, question_type=kind, points=1, question_text='Câu hỏi $x^2 + 1$ giả lập', context='Ngữ cảnh câu hỏi', image_url='/qa/media/graph.svg', curriculum_code=None, source_id6=None, difficulty_level=None, answers=answers, explanation='')
    for state in ['draft','active','locked','source-invalid','former-teacher']:
        exam = NS(id=22, title='Bản nháp giả lập', course_id=1, course=course, is_active=state=='active', submissions=[1] if state=='locked' else [], questions=[question], total_points=1, duration_minutes=30, get_adaptive_metadata=lambda: {'explanation':'Giữ nguyên lý do lựa chọn'})
        html = render('practice_draft.html', dict(exam=exam, draft_locked=state=='locked', draft_source_valid=state!='source-invalid', draft_can_publish=state!='former-teacher', draft_source_message='Nguồn giả lập đã thay đổi.'), 'Draft: ' + kind + ' / ' + state)
        assert 'Ngữ cảnh câu hỏi' in html and '/qa/media/graph.svg' in html
        assert 'Chưa có lời giải chi tiết' in html
        if state=='locked': assert 'fieldset class="teacher-release-fields" disabled' in html and 'Lưu trạng thái phát hành</button>' not in html
        if state in ['source-invalid','former-teacher']: assert 'name="is_active" value="on"  disabled' in html

report = dict(date='2026-10-15', checks=len(checks), passed=checks, applicationImported=False, databaseOpened=False, errors=[])
(ROOT/'docs/ui-redesign/phase-7/teacher-render-qa.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(dict(checks=len(checks), errors=[])))
