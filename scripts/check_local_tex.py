"""Smoke test without loading Flask, .env, or the application database."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.local_tex import ROOT, compile_svg

if __name__ == '__main__':
    for asset in ('mathjax/tex-mml-chtml.js', 'alpine/alpine.min.js'):
        if not (ROOT / 'static/vendor' / asset).is_file():
            raise SystemExit('Missing local web assets. Run npm run build (or pnpm build).')
    svg = compile_svg(r'\begin{tikzpicture}\draw[->](0,0)--(2,0) node[right] {$P(A)$};\end{tikzpicture}')
    print(f'Local TeX OK: {len(svg)} bytes; local MathJax and Alpine OK.')
