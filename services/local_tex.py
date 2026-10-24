"""Local, bounded WebAssembly TeX worker; no rendering service or network."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SVG = 'http://www.w3.org/2000/svg'


def clean_svg(source):
    if len(source) > 4_000_000 or '<!DOCTYPE' in source.upper() or '<!ENTITY' in source.upper():
        raise ValueError('SVG không hợp lệ hoặc quá lớn')
    root = ET.fromstring(source)
    if root.tag != '{%s}svg' % SVG:
        raise ValueError('Kết quả không phải SVG')
    allowed = {'svg', 'g', 'defs', 'path', 'rect', 'circle', 'ellipse', 'line',
               'polyline', 'polygon', 'text', 'tspan', 'use', 'clipPath', 'mask',
               'linearGradient', 'radialGradient', 'stop', 'title', 'desc'}
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag.rsplit('}', 1)[-1] not in allowed:
                parent.remove(child)
        for key, value in list(parent.attrib.items()):
            local = key.rsplit('}', 1)[-1].lower()
            urls = re.findall(r'url\s*\(([^)]*)\)', value, re.I)
            if (local.startswith('on') or local == 'base'
                    or (local == 'href' and not re.fullmatch(r'#[\w:.-]+', value))
                    or any(not re.fullmatch(r'#[\w:.-]+', url.strip().strip('\'"')) for url in urls)
                    or (local == 'style' and ('\\' in value or '@' in value))
                    or re.search(r'javascript:|@import|expression\s*\(', value, re.I)):
                del parent.attrib[key]
    ET.register_namespace('', SVG)
    return root



def _hook_above(value):
    # OT1 has no Vietnamese hook accent. Turn its cedilla upward and place
    # it above the complete base, including any circumflex/breve or horn.
    return (r'\hbox{\setbox0=\hbox{' + value
            + r'}\setbox2=\hbox{\rotatebox[origin=c]{180}{\c{}}}'
              r'\dimen0=\ht0\advance\dimen0 by\dp2\advance\dimen0 by.1ex'
              r'\rlap{\raise\dimen0\hbox to\wd0{\hfil\box2\hfil}}\box0}')


def encode_text_accents(source):
    """Use equivalent TeX accents for Latin text supported by the bundled fonts.

    Preserve unsupported letters so the compiler reports
    them instead of silently removing accents or changing the label.
    """
    accents = {'\u0300': '`', '\u0301': "'", '\u0302': '^', '\u0303': '~',
               '\u0308': '"', '\u0306': 'u', '\u030c': 'v', '\u0327': 'c', '\u0323': 'd'}
    output = []
    for char in unicodedata.normalize('NFC', source):
        if char in ('Đ', 'đ'):
            output.append(r'\hbox{\rlap{\kern.05em\raise.45ex\hbox{\rule{.5em}{.04em}}}D}' if char == 'Đ'
                          else r'\hbox{\rlap{\kern.08em\raise.8ex\hbox{\rule{.48em}{.035em}}}d}')
            continue
        parts = unicodedata.normalize('NFD', char)
        if '\u0309' in parts and parts[0].isascii() and parts[0].isalpha():
            base = parts.replace('\u0309', '')
            if all(mark in accents or mark == '\u031b' for mark in base[1:]):
                # Dotless i keeps the hỏi mark from colliding with its dot.
                value = r'\i' if base == 'i' else encode_text_accents(base)
                output.append(_hook_above(value))
                continue
        if '\u031b' in parts and parts[0] in 'oOuU':
            # Compose the horn on the original Latin glyph; retain tone marks.
            # This avoids replacing Vietnamese labels with unaccented text.
            value = r'\hbox{' + parts[0] + r"\kern-.12em\raise.65ex\hbox{\tiny'}\kern-.06em}"
            remaining = [mark for mark in parts[1:] if mark != '\u031b']
            if all(mark in accents for mark in remaining):
                for mark in remaining: value = '\\' + accents[mark] + '{' + value + '}'
                output.append(value)
                continue
        if len(parts) > 1 and parts[0].isascii() and parts[0].isalpha() and all(c in accents for c in parts[1:]):
            stacked = {'\u0300':'grave', '\u0301':'acute', '\u0302':'hat', '\u0303':'tilde', '\u0308':'ddot', '\u0306':'breve', '\u030c':'check'}
            if len(parts) > 2 and all(mark in stacked for mark in parts[1:]):
                # Text accents do not stack correctly with the bundled OT1 font.
                # AMS math accents stack while \text retains the label font.
                value = r'\text{' + parts[0] + '}'
                for mark in parts[1:]: value = '\\' + stacked[mark] + '{' + value + '}'
                value = r'\ensuremath{' + value + '}'
            else:
                value = parts[0]
                for mark in parts[1:]: value = '\\' + accents[mark] + '{' + value + '}'
            output.append(value)
        else:
            output.append(char)
    return ''.join(output)


def fragment_preamble(source, preamble):
    """Do not load document-only packages into the isolated figure compiler.

    Missing packages that the fragment actually uses remain explicit errors.
    Never substitute another figure or drop drawing commands on failure.
    """
    requirements = {
        'pgfplots': r'\\(?:begin\{(?:axis|semilogxaxis|semilogyaxis|loglogaxis)\}|addplot)',
        'tabularx': r'\\begin\{tabularx\}', 'diagbox': r'\\diagbox\b',
        'colortbl': r'\\(?:cellcolor|rowcolor|columncolor)\b',
        'booktabs': r'\\(?:toprule|midrule|bottomrule)\b',
        'caption': r'\\caption\b', 'subcaption': r'\\begin\{subfigure\}',
        'longtable': r'\\begin\{longtable\}', 'multirow': r'\\multirow\b',
        'makecell': r'\\makecell\b', 'forest': r'\\begin\{forest\}',
        'siunitx': r'\\(?:SI|si|num)\b', 'tkz-euclide': r'\\tkz',
    }
    def packages(match):
        names = [name.strip() for name in match.group(1).split(',')]
        names = [name for name in names if name not in requirements or re.search(requirements[name], source)]
        return r'\usepackage{' + ','.join(names) + '}' if names else ''
    if not re.search(requirements['pgfplots'], source):
        preamble = re.sub(r'\\pgfplotsset\{[^{}]*\}', '', preamble)
        preamble = re.sub(r'\\usepgfplotslibrary\{[^{}]*\}', '', preamble)
    preamble = re.sub(r'\\usepackage(?:\[[^]]*\])?\{([^}]+)\}', packages, preamble)
    # Older imported assets can contain the first line of a multiline macro.
    # Such an incomplete declaration consumes the following figure as its body.
    return '\n'.join(line for line in preamble.splitlines()
                     if line.count('{') == line.count('}'))

def expand_basic_geometry(source):
    """Exact equivalents for the three elementary tkz drawing commands.

    Other tkz commands stay untouched and report missing-library errors.
    """
    source = re.sub(r'\\tkzDrawPoints\(([A-Za-z0-9_, ]+)\)',
                    lambda m: ''.join(r'\fill (' + p.strip() + ') circle (1.5pt);' for p in m[1].split(',')), source)
    source = re.sub(r'\\tkzLabelPoints(?:\[([a-z ]+)\])?\(([A-Za-z0-9_, ]+)\)',
                    lambda m: ''.join(r'\node[' + (m[1] or 'below right') + '] at (' + p.strip() + ') {$' + p.strip() + '$};' for p in m[2].split(',')), source)
    source = re.sub(r'\\tkzMarkRightAngle\(([A-Za-z0-9_]+),([A-Za-z0-9_]+),([A-Za-z0-9_]+)\)',
                    lambda m: r'\pic[draw,angle radius=3mm] {right angle=' + '--'.join(m.groups()) + '};', source)
    return source


def compile_svg(source, preamble=''):
    source = expand_basic_geometry(source)
    node = os.environ.get('LATEX_NODE_BINARY') or shutil.which('node')
    saved_path = ROOT / '.latex-node-path'
    if not node and saved_path.is_file():
        candidate = saved_path.read_text(encoding='utf-8').strip()
        if Path(candidate).is_file():
            node = candidate
    if not node or not (ROOT / 'node_modules/node-tikzjax').exists():
        raise ValueError('Chưa cài bộ TeX tích hợp. Cài Node.js rồi chạy npm install và npm run build trong FNWEB2.')
    result = subprocess.run(
        [node, '--max-old-space-size=384', str(ROOT / 'scripts/render_tex.cjs')],
        input=json.dumps({'source': encode_text_accents(source), 'preamble': encode_text_accents(fragment_preamble(source, preamble))}),
        encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=ROOT, timeout=40, check=False,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    try:
        data = json.loads(result.stdout)
    except ValueError:
        raise ValueError('Bộ TeX không trả về kết quả; kiểm tra cài đặt Node.js.') from None
    if result.returncode or data.get('error'):
        errors = [line.strip() for line in data.get('log', '').splitlines() if line.startswith('!')]
        raise ValueError('Không biên dịch được hình/bảng: ' + (errors[0] if errors else data.get('error', 'Lỗi TeX')))
    root = clean_svg(data['svg'])
    root.set('data-render-method', 'local_wasm_tex')
    # Font bytes come exclusively from the installed package, never TeX input.
    style = ET.SubElement(root, '{%s}style' % SVG)
    style.text = data.get('fonts', '')
    return ET.tostring(root, encoding='unicode')
