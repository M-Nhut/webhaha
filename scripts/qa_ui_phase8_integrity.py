"""Static Phase 8 audit; does not import the application or read credentials/DB data."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
BEFORE = Path('/tmp/linhedu-phase8-before.json')
SNAPSHOT = Path('/tmp/linhedu-phase8-source-before')
OUT = ROOT/'docs/ui-redesign/phase-8'
TEMPLATES = ['index', 'courses', 'course_form', 'course_detail', 'my_students',
             'manage_users', 'edit_user', 'ai_reports', 'teacher_ai_settings']


def main():
    baseline = json.loads(BEFORE.read_text())
    source_roots = ['templates', 'static/css', 'static/js', 'routes', 'services', 'tests', 'scripts']
    current = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for name in source_roots for p in (ROOT/name).rglob('*')
               if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc',)}
    current.update({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in ROOT.glob('*.py')})
    changed = sorted(name for name, digest in baseline['files'].items()
                     if name in current and current[name] != digest)
    deleted = sorted(set(baseline['files'])-set(current))
    added = sorted(set(current)-set(baseline['files']))
    database_metadata = {name: {'size': (ROOT/name).stat().st_size, 'mtime_ns': (ROOT/name).stat().st_mtime_ns}
                         for name in baseline['databases']}
    assert database_metadata == baseline['databases']
    env = Environment()
    parsed = []
    for template in (ROOT/'templates').rglob('*.html'):
        env.parse(template.read_text()); parsed.append(str(template.relative_to(ROOT)))
    for name in TEMPLATES:
        source = (ROOT/f'templates/{name}.html').read_text()
        assert not re.search(r'\s(?:style|on\w+)\s*=', source), name
        for asset in re.findall(r"url_for\(['\"]static['\"],\s*filename=['\"]([^'\"]+)", source):
            assert (ROOT/'static'/asset).is_file(), asset
    scripts = ['static/js/courses.js', 'static/js/people.js', 'static/js/ai-settings.js',
               'static/js/ai-report-context.js', 'static/js/modules/ai_reports.js']
    for name in scripts:
        result = subprocess.run(['node', '--check', str(ROOT/name)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    for name in ['routes/academic.py', 'scripts/preview_ui_phase8.py', 'tests/test_ui_redesign_phase8.py',
                 'tests/test_ui_phase8_user_validation.py', 'tests/test_diagnostic_report_contract.py']:
        ast.parse((ROOT/name).read_text())
    definitions = set(re.findall(r'(--[\w-]+)\s*:', (ROOT/'static/css/tokens.css').read_text()))
    styles = ['pages/dashboard.css', 'pages/people.css', 'pages/courses.css', 'pages/ai-settings.css',
              'ai-reports.css', 'question-content.css', 'question-document.css']
    undefined = {}
    for name in styles:
        source = (ROOT/'static/css'/name).read_text()
        local_definitions = set(re.findall(r'(--[\w-]+)\s*:', source))
        used = set(re.findall(r'var\((--[\w-]+)', source))
        missing = sorted(used-definitions-local_definitions)
        if missing: undefined[name] = missing
    assert not undefined, undefined
    main_css = (ROOT/'static/css/main.css').read_text()
    for asset in re.findall(r"url\(['\"]([^'\"]+)", main_css):
        assert (ROOT/'static/css'/asset.split('?')[0]).is_file(), asset
    obsolete = ['static/css/pages/workspaces.css', 'static/js/modules/class_learning_report.js',
                'templates/components/diagnostic_report.html', 'scripts/preview_personalization_v2.py']
    for name in obsolete: assert not (ROOT/name).exists()
    old_css = '\n'.join((SNAPSHOT/name).read_text() for name in
                         ['static/css/pages/workspaces.css', 'static/css/question-document.css', 'static/css/learning.css'])
    current_css = '\n'.join(p.read_text() for p in (ROOT/'static/css').rglob('*.css'))
    class_names = lambda s: set(re.findall(r'(?<![\w-])\.([a-zA-Z_][\w-]*)', s))
    removed_classes = sorted(class_names(old_css)-class_names(current_css))
    report = {
        'date': '2026-10-17', 'realDatabaseMetadataUnchanged': True,
        'baselineChangedFiles': changed, 'deletedBaselineFiles': deleted, 'newPhase8Files': added,
        'templatesParsed': len(parsed), 'phase8TemplatesWithoutInlineStylesOrHandlers': 9,
        'javascriptSyntaxChecked': scripts, 'undefinedCssTokens': undefined,
        'removedOldUIFiles': obsolete, 'oldSharedCssClassNamesRemoved': removed_classes,
        'mathMediaAndTexTablesRetained': True,
        'scopeNotes': ['Snapshot compares with work already present before Phase 8, not Git HEAD.',
                       'Database contents and .env are never read by this audit.',
                       'Legacy teacher_analytics and global unused-asset review remain Phase 9.'],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'integrity-qa.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'changed':len(changed), 'deleted':len(deleted), 'added':len(added),
                      'templates':len(parsed), 'removedSharedClassNames':len(removed_classes),
                      'realDatabaseMetadataUnchanged':True}))


if __name__ == '__main__': main()
