"""Serve only the Phase 2 proposal and required math/logo assets, on loopback."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
import argparse

PHASE = Path(__file__).resolve().parent
PROJECT = PHASE.parents[2]

class Preview(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        requested = unquote(urlsplit(path).path)
        if requested in ('/', '/index.html'):
            return str(PHASE / 'prototype/index.html')
        if requested.startswith('/static/vendor/mathjax/'):
            candidate = PROJECT / requested.lstrip('/')
            allowed = PROJECT / 'static/vendor/mathjax'
        elif requested == '/static/images/logo-transparent.png':
            return str(PROJECT / 'static/images/logo-transparent.png')
        elif requested == '/phase-2-screen-specs.md':
            return str(PHASE.parent / 'phase-2-screen-specs.md')
        else:
            candidate = PHASE / requested.lstrip('/')
            allowed = PHASE
        resolved = candidate.resolve()
        if not resolved.is_relative_to(allowed.resolve()):
            return str(PHASE / '__not_found__')
        return str(resolved)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    options = parser.parse_args()
    print(f'LinhEdu Phase 2: http://127.0.0.1:{options.port}/prototype/index.html#bank', flush=True)
    ThreadingHTTPServer(('127.0.0.1', options.port), Preview).serve_forever()
