"""Server-side renderer for LaTeX blocks that MathJax cannot render.

The default uses the bundled Node/WebAssembly engine on this computer.
All compilation stays on this computer; legacy service settings are ignored.
"""
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path


ASSET_DIR = Path(os.path.dirname(os.path.dirname(__file__))) / "static" / "uploads" / "questions"
_BLOCKED_TEX_TOKENS = (
    r"\input", r"\include", r"\openin", r"\openout", r"\read",
    r"\write", r"\immediate", r"\write18", r"\directlua",
    r"\documentclass", r"\begin{document}", r"\end{document}",
)


def _render_result(url=None, *, verified=False, method=None, error=None):
    return {
        "url": url,
        "verified": bool(verified),
        "method": method,
        "error": error,
    }


def _asset_digest(source, preamble=""):
    payload = f"{preamble}\n%__QUESTION_BLOCK__%\n{source}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def render_latex_block(source, preamble=""):
    """Backward-compatible URL-only wrapper around the detailed renderer."""
    return render_latex_block_result(source, preamble=preamble).get("url")


def render_latex_block_result(source, preamble=""):
    """Compile a bounded TeX block, cache the SVG atomically, retain errors."""
    if not source or len(source) > 200_000:
        return _render_result(error="Khối LaTeX trống hoặc vượt quá 200 KB")
    if len(preamble.encode("utf-8")) > 50_000:
        return _render_result(error="Preamble LaTeX vượt quá 50 KB")
    lowered_source = (source + "\n" + preamble).lower()
    if any(token.lower() in lowered_source for token in _BLOCKED_TEX_TOKENS):
        return _render_result(error="Source chứa lệnh TeX I/O không được phép")
    digest = _asset_digest(source, "local-wasm-v4-vietnamese-accents\n" + preamble)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    output = ASSET_DIR / f"latex_{digest}.svg"
    url = f"/static/uploads/questions/{output.name}"
    if output.exists():
        return _render_result(url, verified=True, method="cached_tex")
    try:
        from services.local_tex import compile_svg
        svg = compile_svg(source, preamble)
        # Atomic replace prevents another request seeing a partially written SVG.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=ASSET_DIR,
                                         suffix=".svg.tmp", delete=False) as handle:
            handle.write(svg)
            temporary = handle.name
        os.replace(temporary, output)
        return _render_result(url, verified=True, method="local_wasm_tex")
    except subprocess.TimeoutExpired:
        return _render_result(error="Hình vượt quá thời gian biên dịch 40 giây. Hãy kiểm tra vòng lặp và độ phức tạp của mã TeX.", method="local_wasm_tex")
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        return _render_result(error=str(exc)[:600], method="local_wasm_tex")

