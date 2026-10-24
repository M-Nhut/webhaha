from pathlib import Path
from types import SimpleNamespace as NS
import datetime,json,re
from jinja2 import Environment,FileSystemLoader,ChoiceLoader,DictLoader
import tinycss2
root=Path.cwd(); out=root/'docs/ui-redesign/phase-8'; checks=[]
env=Environment(loader=ChoiceLoader([DictLoader({'base.html':'{% block head %}{% endblock %}<main>{% block content %}{% endblock %}</main>{% block scripts %}{% endblock %}'}),FileSystemLoader(root/'templates')]),autoescape=True)
env.globals.update(url_for=lambda endpoint,**kwargs:'/'+endpoint+'?'+ '&'.join(f'{k}={v}'for k,v in kwargs.items()),csrf_token=lambda:'synthetic-csrf')
def user(role='student',active=True):return NS(id=1 if role=='admin' else 2,role=role,fullname='Nguyễn Thị '+('Tên rất dài '*10),username='qa_'+role+'x'*70,user_code='HS'+'0'*18,phone=None,position=None,avatar=None,is_active=active)
admin=user('admin');cases=[]
for scope in ['center','teacher','student']:
 for state in ['empty','rich','missing-time','string-time']:
  activities=[]if state=='empty'else[NS(icon='file-check',title='Bài đầu vào '+('dài '*30),desc='Bằng chứng học tập đã ghi nhận.',time=None if state=='missing-time'else 'Hôm nay'if state=='string-time'else datetime.datetime(2026,10,17,8,30))]
  cases.append(('index.html',{'dashboard_scope':scope,'current_user':user('admin'if scope=='center'else scope),'teacher_data':NS(assigned_classes=0,student_count=0),'student_data':NS(course_count=0,exams_taken=0),'total_students':99999,'total_teachers':0,'activities':activities},scope+'-'+state))
for role in ['student','teacher']:
 for state in ['empty','rich']:
  cases.append(('manage_users.html',{'current_user':admin,'users':[]if state=='empty'else[user(role),user(role,False)],'role_name':'students'if role=='student'else'teachers'},role+'-'+state))
for role in ['admin','student','teacher']:
 for active in [True,False]:cases.append(('edit_user.html',{'current_user':admin,'user':user(role,active)},role+'-'+str(active)))
for state in ['empty','rich']:cases.append(('my_students.html',{'current_user':user('teacher'),'students':[]if state=='empty'else[user(),user(active=False)]},state))
for template,context,name in cases:
 html=env.get_template(template).render(**context);
 assert not re.search(r'\b(?:style|onclick|onchange|onsubmit|x-data)\s*=',html),(template,name)
 assert len(re.findall(r'<h1\b',html))==1,(template,name)
 for label in re.findall(r'<label[^>]*for="([^"]+)"',html):assert 'id="'+label+'"'in html,(template,name,label)
 if template=='edit_user.html'and context['user'].role=='admin':assert not re.search(r'<form\b|<button[^>]*type="submit"',html) and re.search(r'<fieldset[^>]+disabled',html)
 if template=='manage_users.html':assert re.findall(r'<option value="([^"]+)"',re.search(r'<select id="add_role".*?</select>',html,re.S)[0])==['student','teacher']
 checks.append(template+':'+name)
css_errors=[]
for filename in ['dashboard','people']:
 css=(root/'static/css/pages'/f'{filename}.css').read_text()
 def inspect(items):
  for item in items:
   if item.type=='error':css_errors.append(str(item))
   if item.type=='at-rule'and item.content:inspect(tinycss2.parse_rule_list(item.content,skip_whitespace=True,skip_comments=True))
 inspect(tinycss2.parse_stylesheet(css,skip_whitespace=True,skip_comments=True))
 assert not css_errors
all_css='\n'.join(p.read_text()for p in (root/'static/css').rglob('*.css'));defined=set(re.findall(r'(--[\w-]+)\s*:',all_css));used=set(re.findall(r'var\((--[\w-]+)', '\n'.join((root/'static/css/pages'/f'{n}.css').read_text()for n in ['dashboard','people'])));assert used<=defined,used-defined
removed={}
for name in ['index','my_students','manage_users','edit_user']:
 p=Path('/tmp/linhedu-phase8-source-before/templates')/(name+'.html')
 before=p.read_text();after=(root/'templates'/(name+'.html')).read_text()
 removed[name]={'inlineStyleBefore':len(re.findall(r'\bstyle\s*=',before)),'inlineStyleAfter':len(re.findall(r'\bstyle\s*=',after)),'inlineEventsBefore':len(re.findall(r'\bon(?:click|change|submit)\s*=',before)),'inlineEventsAfter':len(re.findall(r'\bon(?:click|change|submit)\s*=',after)),'alpineBefore':len(re.findall(r'(?:\bx-data|\bx-show|\bx-model|@click)',before)),'alpineAfter':len(re.findall(r'(?:\bx-data|\bx-show|\bx-model|@click)',after))}
report={'status':'passed','isolatedJinjaRenders':len(checks),'cases':checks,'cssParseErrors':css_errors,'undefinedCSSTokens':sorted(used-defined),'cleanup':removed,'note':'Synthetic renderer overrides base only; no Flask app, environment secrets, database or external services imported.'}
(out/'people-dashboard-static-qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
