"""Read-time compatibility for stored formula assets; no database mutation."""
from functools import lru_cache
from pathlib import Path

from services.tex_table import display_asset as table_display
from services.latex_renderer import ASSET_DIR, render_latex_block_result


@lru_cache(maxsize=128)
def _recover_legacy(source, preamble):
    # Cache failures too: a broken legacy figure must not recompile every view.
    return render_latex_block_result(source, preamble)


def display_asset(data):
    data = table_display(data)
    if data.get('source_format') != 'LaTeXBlock' or data.get('table'):
        return data
    url = data.get('svg_cache_key') or data.get('preview_url') or ''
    local_exists = url.startswith('/static/uploads/questions/') and (ASSET_DIR / Path(url).name).is_file()
    if local_exists and data.get('conversion_status') != 'failed':
        return data
    if not data.get('source_text'):
        return data
    # Old remote failures and missing old SVGs can be recovered transparently.
    # Failures remain explicit and cached; no repeated compile loop.
    result = _recover_legacy(data['source_text'], data.get('source_preamble') or '')
    if result.get('url'):
        return {**data, 'conversion_status':'fallback_svg', 'verification_status':'verified',
                'needs_review':False, 'preview_url':result['url'], 'svg_cache_key':result['url'],
                'render_method':result['method'], 'render_error':None}
    return {**data, 'render_error':result.get('error') or data.get('render_error')}
