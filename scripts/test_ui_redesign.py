"""Run the repository tests with memory DB, temporary storage and no outbound HTTP.

python3 scripts/test_ui_redesign.py                  # all tests/ modules
python3 scripts/test_ui_redesign.py tests/test_route_contract.py -q
Never loads dotenv or production DB/upload/provider configuration.
"""
from __future__ import annotations

import json
import socket
import sys
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Results:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []
        self.collection_errors = []
        self.subtests = []

    def pytest_runtest_logreport(self, report):
        if 'subtest' in type(report).__name__.lower():
            self.subtests.append({'node':report.nodeid,'outcome':report.outcome})
            return
        if report.failed:
            self.failed.append({'node': report.nodeid, 'when': report.when,
                                'message': str(report.longrepr)})
        elif report.when == 'call' and report.passed:
            self.passed.append(report.nodeid)
        elif report.skipped:
            self.skipped.append({'node':report.nodeid, 'reason':str(report.longrepr)})

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append({'node':report.nodeid, 'message':str(report.longrepr)})


def main():
    from scripts.preview_ui_phase8 import isolate_phase8_environment, isolate_phase5
    with TemporaryDirectory(prefix='linhedu-final-tests-') as directory:
        isolate_phase8_environment(directory)
        from app import app
        isolate_phase5(app, directory)
        assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
        from services import latex_renderer, question_images
        assert str(latex_renderer.ASSET_DIR).startswith(directory)
        assert str(question_images.DIRECTORY).startswith(directory)
        import pytest
        import requests
        blocked_requests, blocked_sockets = [], []

        def no_http(self, method, url, **kwargs):
            from urllib.parse import urlsplit
            blocked_requests.append({'method':method, 'host':urlsplit(str(url)).hostname})
            raise requests.ConnectionError('Outbound HTTP disabled by the isolated test runner.')

        def no_socket(self, address):
            blocked_sockets.append(str(address)[:120])
            raise OSError('Network disabled by the isolated test runner.')

        args = sys.argv[1:] or ['tests', '-q', '--tb=short', '--disable-warnings', '--continue-on-collection-errors']
        results = Results()
        with ExitStack() as stack:
            stack.enter_context(patch('requests.sessions.Session.request', no_http))
            stack.enter_context(patch.object(socket.socket, 'connect', no_socket))
            code = pytest.main(args, plugins=[results])
        out = ROOT/'docs/ui-redesign/phase-9'
        out.mkdir(parents=True, exist_ok=True)
        report = {'date':'2026-10-19', 'args':args, 'exitCode':int(code),
                  'passed':len(results.passed), 'failed':len(results.failed),
                  'skipped':len(results.skipped), 'collectionErrors':results.collection_errors,
                  'subtests':results.subtests,
                  'failedCases':results.failed, 'skippedCases':results.skipped,
                  'databaseURI':app.config['SQLALCHEMY_DATABASE_URI'],
                  'dotenvLoaded':False, 'storageTemporary':True,
                  'blockedRequests':blocked_requests, 'blockedSockets':blocked_sockets}
        (out/'python-regression.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        return int(code)


if __name__ == '__main__': raise SystemExit(main())
