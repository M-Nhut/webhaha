"""Vietnamese labels in imported TikZ must render without losing their tones."""
from pathlib import Path
import unicodedata

from services.local_tex import compile_svg, encode_text_accents


def test_hook_tones_preserve_accents_and_normalize_decomposed_input():
    labels = 'Thẻ đỏ · Bảng · Ả Ẩ Ẳ Ẻ Ể Ỉ Ỏ Ổ Ở Ủ Ử Ỷ · ả ẩ ẳ ẻ ể ỉ ỏ ổ ở ủ ử ỷ'
    # The middle dot is unrelated to Vietnamese accent handling.
    labels = labels.replace(' · ', ' / ')
    encoded = encode_text_accents(labels)
    assert encoded.isascii()
    assert encoded == encode_text_accents(unicodedata.normalize('NFD', labels))
    assert encode_text_accents('ẻ') != 'e'
    assert encode_text_accents('ỏ') != 'o'


def test_hook_tones_compile_with_stacked_accents_horns_and_dotless_i():
    labels = 'Ả Ẩ Ẳ Ẻ Ể Ỉ Ỏ Ổ Ở Ủ Ử Ỷ / ả ẩ ẳ ẻ ể ỉ ỏ ổ ở ủ ử ỷ'
    svg = compile_svg(r'\begin{tikzpicture}\node {' + labels + r'};\end{tikzpicture}')
    assert 'data-render-method="local_wasm_tex"' in svg


def test_failed_imported_card_diagram_recovers_without_database_changes(monkeypatch, tmp_path):
    from services import formula_display, latex_renderer

    monkeypatch.setattr(latex_renderer, 'ASSET_DIR', tmp_path)
    monkeypatch.setattr(formula_display, 'ASSET_DIR', tmp_path)
    formula_display._recover_legacy.cache_clear()
    source = (Path(__file__).parent / 'fixtures/vietnamese_card_diagram.tex').read_text(encoding='utf-8')
    saved = {
        'source_format': 'LaTeXBlock', 'source_text': source,
        'conversion_status': 'failed', 'verification_status': 'needs_review',
        'render_error': 'Unicode character U+1EBB',
    }
    displayed = formula_display.display_asset(saved)
    assert displayed['conversion_status'] == 'fallback_svg', displayed
    assert displayed['verification_status'] == 'verified', displayed
    assert displayed['render_error'] is None
    assert (tmp_path / Path(displayed['svg_cache_key']).name).is_file()
    assert saved['conversion_status'] == 'failed'
