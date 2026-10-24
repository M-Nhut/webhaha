"""Audit current UI consumers and syntax without importing the application."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

import tinycss2
from jinja2 import Environment, nodes

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/ui-redesign/phase-9'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def css_errors(rules):
    errors = []
    for rule in rules:
        if rule.type == 'error': errors.append(str(rule))
        elif rule.type == 'at-rule' and rule.lower_at_keyword in ('media','supports','layer') and rule.content:
            errors.extend(css_errors(tinycss2.parse_rule_list(rule.content, skip_whitespace=True, skip_comments=True)))
        elif rule.type == 'qualified-rule':
            errors.extend(str(v) for v in tinycss2.parse_declaration_list(rule.content, skip_whitespace=True, skip_comments=True) if v.type == 'error')
    return errors


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before_path = OUT/'baseline-source.json'
    if not before_path.exists(): before_path.write_bytes(Path('/tmp/linhedu-phase9-before.json').read_bytes())
    baseline = json.loads(before_path.read_text())
    env, trees = Environment(), {}
    for file in (ROOT/'templates').rglob('*.html'):
        name = str(file.relative_to(ROOT/'templates'))
        trees[name] = env.parse(file.read_text())
        assert not re.search(r'\s(?:style|on\w+)\s*=', file.read_text()), name
    edges = {name: [] for name in trees}
    for name, tree in trees.items():
        for kind in (nodes.Include, nodes.Extends, nodes.Import, nodes.FromImport):
            for node in tree.find_all(kind):
                assert isinstance(node.template,nodes.Const), f'Declare dynamic template consumer: {name}'
                target = node.template.value
                assert target in trees, (name,target)
                edges[name].append(target)
    roots = set()
    for route in (ROOT/'routes').glob('*.py'):
        for node in ast.walk(ast.parse(route.read_text())):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='render_template' and node.args and isinstance(node.args[0],ast.Constant):
                roots.add(node.args[0].value)
    roots.update('errors/'+name+'.html' for name in ('400','403','404','405','500'))
    reached = set()
    def visit(name):
        assert name in trees, name
        if name in reached: return
        reached.add(name)
        for target in edges[name]: visit(target)
    for name in roots: visit(name)
    assert reached == set(trees), sorted(set(trees)-reached)
    styles = sorted((ROOT/'static/css').rglob('*.css'))
    scripts = sorted((ROOT/'static/js').rglob('*.js'))
    definitions = set()
    for file in styles: definitions.update(re.findall(r'(--[\w-]+)\s*:',file.read_text()))
    undefined = {}
    for file in styles:
        errors = css_errors(tinycss2.parse_stylesheet(file.read_text(), skip_whitespace=True, skip_comments=True))
        assert not errors, (str(file),errors)
        missing = sorted(set(re.findall(r'var\((--[\w-]+)',file.read_text()))-definitions)
        if missing: undefined[str(file.relative_to(ROOT))] = missing
        for asset in re.findall(r'url\([\s\x22\x27]*([^\x22\x27)\s]+)', file.read_text()):
            if asset.startswith(('data:','http:','https:','#')): continue
            assert (file.parent/asset.split('?')[0].split('#')[0]).is_file(), (str(file),asset)
    assert not undefined, undefined
    for file in scripts:
        result = subprocess.run(['node','--check',str(file)],capture_output=True,text=True)
        assert result.returncode == 0, result.stderr
    static_files = []
    for file in (ROOT/'templates').rglob('*.html'):
        for asset in re.findall(r"url_for\(['\"]static['\"],\s*filename=['\"]([^'\"]+)",file.read_text()):
            assert (ROOT/'static'/asset).is_file(), (str(file),asset)
            static_files.append(asset)
    current = {}
    for folder in ['templates','static/css','static/js','routes','services','tests','scripts']:
        for file in (ROOT/folder).rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc': current[str(file.relative_to(ROOT))]=sha(file)
    current.update({p.name:sha(p) for p in ROOT.glob('*.py')})
    changed = sorted(k for k,v in baseline['files'].items() if k in current and current[k]!=v)
    deleted = sorted(set(baseline['files'])-set(current))
    added = sorted(set(current)-set(baseline['files']))
    unchanged_backend = [k for k,v in baseline['files'].items() if k.endswith('.py') and (k.startswith(('routes/','services/')) or '/' not in k)]
    assert all(current.get(k)==baseline['files'][k] for k in unchanged_backend)
    database_metadata = {k:{'size':(ROOT/k).stat().st_size,'mtime_ns':(ROOT/k).stat().st_mtime_ns} for k in baseline['databases']}
    assert database_metadata==baseline['databases']
    asset_changes, removed_metadata = [], []
    for name, data in baseline['assets'].items():
        path = ROOT/name
        if Path(name).name == '.DS_Store' and not path.exists(): removed_metadata.append(name); continue
        if not path.is_file() or sha(path)!=data['sha256']: asset_changes.append(name)
    assert not asset_changes, asset_changes
    report = {'date':'2026-10-19','status':'passed','templates':len(trees),
        'activePageTemplates':len([k for k in roots if not k.startswith('errors/')]),
        'allTemplatesReachable':True,'templateRoots':sorted(roots),'templateEdges':edges,
        'stylesheetsParsed':len(styles),'javascriptSyntaxChecked':len(scripts),'undefinedCssTokens':undefined,
        'literalStaticAssetsResolved':len(set(static_files)), 'baselineChangedFiles':changed,
        'deletedBaselineFiles':deleted,'newPhase9Files':added,'backendPythonFilesUnchanged':len(unchanged_backend),
        'realDatabaseMetadataUnchanged':True,'brandFontVendorAssetsUnchanged':len(baseline['assets'])-len(removed_metadata),
        'removedFinderMetadata':removed_metadata,'notes':['Application, dotenv and database contents are not imported/read.',
        'MathJax dynamically loads its local fonts; runtime vendor/TeX libraries and uploaded media are explicitly retained.',
        'Phase1–8 design/QA records remain historical evidence; obsolete active guides and ad hoc exporters were removed.']}
    (OUT/'integrity-qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['templates','activePageTemplates','stylesheetsParsed','javascriptSyntaxChecked','allTemplatesReachable','realDatabaseMetadataUnchanged']}))


if __name__=='__main__': main()
