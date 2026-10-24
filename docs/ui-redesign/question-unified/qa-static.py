"""Validate the shared question stylesheet and live template syntax."""
from collections import Counter
import json
from pathlib import Path
import re

from jinja2 import Environment
import tinycss2

ROOT = Path(__file__).resolve().parents[3]
errors = []
env = Environment()
templates = list((ROOT / 'templates').rglob('*.html'))
stylesheets = list((ROOT / 'static/css').rglob('*.css'))


def declarations(items, source):
    for item in tinycss2.parse_declaration_list(items, skip_whitespace=True, skip_comments=True):
        if item.type == 'error':
            errors.append({'file': source, 'error': item.message})


def rules(items, source):
    for item in items:
        if item.type == 'error':
            errors.append({'file': source, 'error': item.message})
        elif item.type == 'qualified-rule':
            declarations(item.content, source)
        elif item.type == 'at-rule' and item.content:
            if item.lower_at_keyword in ('font-face', 'page', 'property', 'counter-style'):
                declarations(item.content, source)
            else:
                rules(tinycss2.parse_rule_list(item.content, skip_whitespace=True, skip_comments=True), source)


for file in templates:
    try:
        env.parse(file.read_text())
    except Exception as error:
        errors.append({'file': str(file.relative_to(ROOT)), 'error': str(error)})
for file in stylesheets:
    rules(tinycss2.parse_stylesheet(file.read_text(), skip_whitespace=True, skip_comments=True), str(file.relative_to(ROOT)))

styles = '\n'.join(p.read_text() for p in stylesheets)
defined = set(re.findall(r'(--[\w-]+)\s*:', styles))
used = set(re.findall(r'var\((--[\w-]+)', styles))
missing = sorted(used - defined)
take = (ROOT / 'templates/exam_take.html').read_text()
removed = 'Đến cuối bài' not in take and 'taking-review-link' not in take
retained = 'id="taking-end"' in take and 'data-taking-submit' in take
old_tokens = sorted(set(re.findall(r'--exam-(?:card-radius|option-radius|surface-shadow|option-shadow)', styles)))

baseline = Path('/tmp/lmath-question-unified-before/templates/exam_take.html')
controls_unchanged = None
if baseline.exists():
    def controls(source):
        return Counter(re.sub(r'\sclass="[^"]*"', '', tag) for tag in re.findall(r'<(?:form|input|textarea|select|button)\b[^>]*>', source))
    controls_unchanged = controls(baseline.read_text()) == controls(take)

report = {'templates': len(templates), 'cssFiles': len(stylesheets), 'errors': errors,
          'undefinedTokens': missing, 'removedEndLinks': removed, 'bottomSubmitRetained': retained,
          'removedLegacyLayoutTokens': not old_tokens, 'takingNativeControlAttributesUnchanged': controls_unchanged}
(Path(__file__).parent / 'static-qa.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False))
assert not errors and not missing and removed and retained and not old_tokens and controls_unchanged is not False
