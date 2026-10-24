"""Minimal sandboxed LaTeX block renderer for production deployment."""
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)
MAX_SOURCE_SIZE = 200_000
MAX_PREAMBLE_SIZE = 50_000
ALLOWED_PACKAGES = {
    "amsmath", "amssymb", "array", "booktabs", "caption", "colortbl",
    "diagbox", "forest", "graphicx", "longtable", "makecell", "mathtools",
    "multirow", "pgfplots", "siunitx", "subcaption", "tabularx", "tikz",
    "tkz-euclide", "xcolor",
}
SAFE_DEFINITION_PREFIXES = (
    r"\newcommand", r"\providecommand",
    r"\newcolumntype", r"\definecolor", r"\colorlet",
    r"\tikzset", r"\pgfplotsset",
)
BLOCKED_TEX_TOKENS = (
    r"\input", r"\include", r"\openin", r"\openout", r"\read",
    r"\write", r"\immediate", r"\write18", r"\directlua",
    r"\documentclass", r"\begin{document}", r"\end{document}",
)


def _safe_preamble(raw_preamble):
    if not isinstance(raw_preamble, str):
        return ""
    if len(raw_preamble.encode("utf-8")) > MAX_PREAMBLE_SIZE:
        raise ValueError("preamble is too large")

    kept = []
    package_pattern = re.compile(r"\\usepackage(?:\[[^]]*\])?\{([^{}]+)\}", re.IGNORECASE)
    for match in package_pattern.finditer(raw_preamble):
        packages = [name.strip() for name in match.group(1).split(",")]
        allowed = [name for name in packages if name.lower() in ALLOWED_PACKAGES]
        if allowed:
            kept.append(r"\usepackage{" + ",".join(allowed) + "}")

    for command in (r"\usetikzlibrary", r"\usepgfplotslibrary"):
        pattern = re.compile(re.escape(command) + r"\{([a-zA-Z0-9,._-]+)\}")
        kept.extend(match.group(0) for match in pattern.finditer(raw_preamble))

    for raw_line in raw_preamble.splitlines():
        line = raw_line.strip()
        if not line.startswith(SAFE_DEFINITION_PREFIXES):
            continue
        lowered = line.lower()
        # Preambles extracted from full exam templates often contain only the
        # opening line of a multi-line macro or internal class commands using
        # ``@``.  Injecting either fragment into the standalone document makes
        # every otherwise valid table/TikZ block fail.  Keep only complete,
        # self-contained public definitions.
        if (
            len(line) > 2000
            or "@" in line
            or line.count("{") != line.count("}")
            or any(token.lower() in lowered for token in BLOCKED_TEX_TOKENS)
        ):
            continue
        # A user macro should not make rendering fail merely because a loaded
        # package already owns the same name.
        if line.startswith(r"\newcommand"):
            line = r"\providecommand" + line[len(r"\newcommand"):]
        kept.append(line)
    return "\n".join(dict.fromkeys(kept))


def _source_is_safe(source):
    lowered = source.lower()
    return not any(token.lower() in lowered for token in BLOCKED_TEX_TOKENS)


def _latex_error_summary(output):
    text = (output or b"").decode("utf-8", errors="replace")
    errors = [line.strip() for line in text.splitlines() if line.lstrip().startswith("!")]
    return (errors[0] if errors else "LaTeX compilation failed")[:500]


@app.get("/health")
def health():
    latex_engine = shutil.which("xelatex") or shutil.which("pdflatex")
    pdftocairo = shutil.which("pdftocairo")
    ready = bool(latex_engine and pdftocairo)
    return jsonify({
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "latex_engine": os.path.basename(latex_engine) if latex_engine else None,
        "pdftocairo": bool(pdftocairo),
    })


@app.get("/")
def index():
    return jsonify({
        "service": "question-latex-renderer",
        "status": "ok",
        "endpoints": {
            "health": "/health",
            "render": "POST /render",
        },
    })


@app.post("/render")
def render():
    expected_token = os.environ.get("LATEX_RENDERER_TOKEN", "")
    if expected_token:
        supplied = request.headers.get("Authorization", "")
        if supplied != f"Bearer {expected_token}":
            return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    source = payload.get("source", "")
    raw_preamble = payload.get("preamble", "")
    if not isinstance(source, str) or not source.strip():
        return jsonify({"error": "source is required"}), 400
    if len(source.encode("utf-8")) > MAX_SOURCE_SIZE:
        return jsonify({"error": "source is too large"}), 413
    if not _source_is_safe(source):
        return jsonify({"error": "source contains a blocked TeX I/O command"}), 422
    try:
        preamble = _safe_preamble(raw_preamble)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 413

    latex_engine = shutil.which("xelatex") or shutil.which("pdflatex")
    pdftocairo = shutil.which("pdftocairo")
    if not latex_engine or not pdftocairo:
        return jsonify({"error": "renderer dependencies are unavailable"}), 503

    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    workdir = Path(tempfile.mkdtemp(prefix="latex_block_"))
    try:
        tex_path = workdir / "block.tex"
        unicode_setup = (
            "\\usepackage{fontspec}\n\\setmainfont{DejaVu Sans}\n"
            if os.path.basename(latex_engine).lower().startswith("xelatex")
            else "\\usepackage[utf8]{inputenc}\n\\usepackage[T5]{fontenc}\n"
        )
        tex_path.write_text(
            "\\documentclass[preview,border=2pt]{standalone}\n"
            + unicode_setup
            + "\\usepackage{amsmath,amssymb,graphicx,array,booktabs,tabularx,longtable,tikz}\n"
            "\\usepackage{multirow,makecell,colortbl,xcolor,siunitx,diagbox,pgfplots}\n"
            "\\usetikzlibrary{arrows.meta,calc,angles,quotes,patterns,positioning,shapes.geometric}\n"
            "\\pgfplotsset{compat=1.18}\n"
            + preamble + "\n\\pagestyle{empty}\n\\begin{document}\n"
            + source + "\n\\end{document}\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [latex_engine, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", tex_path.name],
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return jsonify({"error": _latex_error_summary(result.stdout), "cache_key": digest}), 422

        svg_path = workdir / "block.svg"
        result = subprocess.run(
            [pdftocairo, "-svg", "block.pdf", str(svg_path)],
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        if result.returncode != 0 or not svg_path.exists():
            return jsonify({"error": "SVG conversion failed", "cache_key": digest}), 422
        return jsonify({"svg": svg_path.read_text(encoding="utf-8"), "cache_key": digest})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "LaTeX compilation timed out", "cache_key": digest}), 408
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

