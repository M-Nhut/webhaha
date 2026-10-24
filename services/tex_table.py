"""Parse supported tabular syntax into data, never HTML or executable code.

Native browser text handles Vietnamese; MathJax handles math within cells.
Unknown constructs fail closed and remain available to the TeX renderer.
"""
import re


def braced(text, pos):
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != '{':
        raise ValueError('Missing table argument')
    start, depth = pos + 1, 1
    pos += 1
    while pos < len(text):
        if text[pos] == '\\':
            pos += 2
            continue
        if text[pos] == '{': depth += 1
        if text[pos] == '}': depth -= 1
        if depth == 0: return text[start:pos], pos + 1
        pos += 1
    raise ValueError('Unbalanced table argument')


def split_top(text, separator):
    result, start, i, depth, environments, math = [], 0, 0, 0, 0, False
    while i < len(text):
        if text[i] == '$':
            math = not math
            i += 1
            continue
        if not depth and not environments and not math and text.startswith(separator, i):
            result.append(text[start:i]); i += len(separator); start = i
            continue
        if text[i] == '\\':
            match = re.match(r'\\(begin|end)\{[^}]+\}', text[i:])
            if match:
                environments += 1 if match[1] == 'begin' else -1
                i += len(match[0]); continue
            i += 2; continue
        if text[i] == '{': depth += 1
        elif text[i] == '}': depth -= 1
        if depth < 0: raise ValueError('Unbalanced cell')
        i += 1
    if depth or environments or math: raise ValueError('Unbalanced table')
    result.append(text[start:])
    return result


def columns(spec):
    output, i = [], 0
    while i < len(spec):
        char = spec[i]
        if char in '| \t\n': i += 1; continue
        if char in 'lcr': output.append(char); i += 1; continue
        if char in 'pmb':
            _, i = braced(spec, i + 1); output.append('l'); continue
        if char == '*':
            count, i = braced(spec, i + 1)
            inner, i = braced(spec, i)
            n = int(count)
            if not 1 <= n <= 30: raise ValueError('Too many columns')
            output.extend(columns(inner) * n); continue
        raise ValueError('Unsupported column syntax')
    if not 1 <= len(output) <= 30: raise ValueError('Invalid column count')
    return output


def parse_table(source):
    if not source or len(source) > 200_000: return None
    match = re.match(r'\s*\\begin\{tabular\}(?:\[[tbc]\])?', source)
    if not match: return None
    try:
        spec, pos = braced(source, match.end())
        alignments = columns(spec)
        tail = re.search(r'\\end\{tabular\}\s*$', source)
        if not tail: return None
        body = source[pos:tail.start()]
        body = re.sub(r'\\(?:hline|toprule|midrule|bottomrule)\b', '', body)
        body = re.sub(r'\\cline\{\d+-\d+\}', '', body)
        rows = []
        for raw_row in split_top(body, r'\\'):
            raw_row = re.sub(r'^\s*\[[\d.]+(?:pt|ex|em|cm)\]', '', raw_row).strip()
            if not raw_row: continue
            cells, column = [], 0
            for raw in split_top(raw_row, '&'):
                value, span, align = raw.strip(), 1, None
                if value.startswith(r'\multicolumn'):
                    span_text, end = braced(value, len(r'\multicolumn'))
                    cell_spec, end = braced(value, end)
                    content, end = braced(value, end)
                    if value[end:].strip(): raise ValueError('Extra span content')
                    span = int(span_text)
                    if not 1 <= span <= 30: raise ValueError('Invalid span')
                    align = columns(cell_spec)[0]
                    value = content
                if column + span > len(alignments): raise ValueError('Table column mismatch')
                # Do not silently drop semantic constructs unsupported by this parser.
                if re.search(r'\\(?:multirow|multicolumn|begin\{tabular|shortstack|makecell|input|include|def|newcommand)\b', value):
                    raise ValueError('Unsupported cell syntax')
                value = re.sub(r'\\(?:textbf|textit|emph)\{([^{}]*)\}', r'\1', value)
                value = value.replace(r'\&', '&').replace(r'\%', '%')
                outside_math = re.sub(r'\$.*?\$|\\\(.*?\\\)|\\\[.*?\\\]', '', value, flags=re.S)
                if re.search(r'\\[A-Za-z]+', outside_math):
                    raise ValueError('Unsupported text macro in cell')
                cells.append({'text': value, 'colspan': span, 'align': align or alignments[column]})
                column += span
            if column != len(alignments): raise ValueError('Table column mismatch')
            rows.append(cells)
        if not rows or len(rows) > 200: return None
        return {'version': 1, 'columns': len(alignments), 'rows': rows}
    except (ValueError, IndexError):
        return None


def display_asset(data):
    """Recover old failed table assets in responses, without changing saved work."""
    if data.get('source_format') == 'LaTeXBlock':
        table = parse_table(data.get('source_text'))
        if table:
            return {**data, 'table': table, 'conversion_status': 'converted',
                    'verification_status': 'verified', 'needs_review': False,
                    'render_method': 'structured_table_v1', 'render_error': None}
    return data
