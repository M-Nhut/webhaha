from pathlib import Path
import os,sys,json,socket,hashlib
os.environ['DATABASE_URL']='sqlite:///:memory:'
os.environ['FLASK_SECRET_KEY']='phase8-baseline-audit-synthetic-session'
for key in tuple(os.environ):
 if key in {'POSTGRES_URL','VERCEL','AI_CREDENTIAL_ENCRYPTION_KEY'} or key.endswith(('API_KEY','API_URL')) or key.startswith(('GEMINI_','GOOGLE_AI_','OPENAI_','AI_LEGACY_')):os.environ.pop(key,None)
network=[]
def deny_network(self,address):
 network.append(str(address));raise RuntimeError('Network disabled for isolated Phase8 baseline audit')
socket.socket.connect=deny_network
import config
config.load_local_environment=lambda *a,**k:None
import app as application
app=application.app
assert app.config['SQLALCHEMY_DATABASE_URI']=='sqlite:///:memory:'
assert app.root_path==str(Path(__file__).parent)
from services import import_service
import_service.ImportService.cleanup_orphan_question_images=staticmethod(lambda:None)
import pytest
records=[]
class ReportPlugin:
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or(report.failed and report.when in {'setup','teardown'}):
   records.append({'node':report.nodeid,'when':report.when,'outcome':report.outcome,'message':str(report.longrepr)[:10000]if report.failed else''})
files=['tests/test_class_lesson4_report.py','tests/test_ai_gateway_review.py','tests/test_phase5_reports.py','tests/test_route_contract.py']
args=files+['-q','--tb=short','--disable-warnings']
code=pytest.main(args,plugins=[ReportPlugin()])
import importlib.util
spec=importlib.util.spec_from_file_location("baseline_route_contract",Path(__file__).parent/"tests/test_route_contract.py");route_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(route_module)
current_route_contract=route_module.current_route_contract;CONTRACT_PATH=route_module.CONTRACT_PATH
expected=json.loads(CONTRACT_PATH.read_text());actual=current_route_contract();bykey=lambda rows:{(r['rule'],r['endpoint']):r for r in rows};a=bykey(actual);e=bykey(expected)
route_diff={'actualCount':len(actual),'expectedCount':len(expected),'missingFixtureRoutes':[a[k]for k in a.keys()-e.keys()],'removedRoutes':[e[k]for k in e.keys()-a.keys()],'methodsChanged':[{'actual':a[k],'fixture':e[k]}for k in a.keys()&e.keys()if a[k]!=e[k]]}
root=Path(__file__).parent;workspace=Path(sys.argv[1]);snapshot=Path('/tmp/linhedu-phase8-source-before')
files_to_check=['services/ai_gateway.py','services/class_lesson4_report.py','services/diagnostic_report_contract.py','services/teacher_keys_phase5.py','routes/ai_settings.py','routes/reports.py','tests/test_class_lesson4_report.py','tests/test_ai_gateway_review.py','tests/test_phase5_reports.py','tests/test_route_contract.py','tests/fixtures/route_contract.json']
hash_check=[]
for filename in files_to_check:
 paths=[snapshot/filename,workspace/filename,root/filename]
 if not all(p.exists()for p in paths):continue
 values=[hashlib.sha256(p.read_bytes()).hexdigest()for p in paths]
 hash_check.append({'file':filename,'snapshotSHA256':values[0],'currentSHA256':values[1],'copySHA256':values[2],'allEqual':len(set(values))==1})
report={'status':'baseline reproduced','pytestExitCode':int(code),'command':'python3 '+str(Path(__file__).resolve())+' '+str(workspace),'pytestArgs':args,'source':json.loads((root/'provenance.json').read_text()),'databaseURI':app.config['SQLALCHEMY_DATABASE_URI'],'dotenvLoaded':False,'socketConnectionsBlocked':network,'summary':{outcome:sum(r['outcome']==outcome for r in records)for outcome in ['passed','failed','skipped']},'cases':records,'sourceHashes':hash_check,'routeContractDiff':route_diff}
output=workspace/'docs/ui-redesign/phase-8/baseline-ai-report-route-audit.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2));print('\nBASELINE_AUDIT_SUMMARY '+json.dumps({'exitCode':int(code),'summary':report['summary'],'routeDiff':{'expected':len(expected),'actual':len(actual),'missing':len(route_diff['missingFixtureRoutes']),'methods':len(route_diff['methodsChanged'])},'connectionsBlocked':len(network),'output':str(output)},ensure_ascii=False))
