"""Persist local TeX assets when a teacher adds or edits a bank question."""
from database import db
from models import FormulaAsset
from services.latex_parser import normalize_question_latex


def normalize_bank_latex(question):
    options = list(question.options)
    payload = dict(question_text=question.question_text, context=question.context or '',
                   explanation=question.explanation or '', question_type=question.question_type,
                   options=[{'text': option.option_text} for option in options], formulas={})
    normalize_question_latex(payload)
    remap = {}
    for key, data in payload['formulas'].items():
        asset = FormulaAsset.query.filter_by(content_hash=data['content_hash']).first()
        if not asset:
            fields = ('content_hash', 'latex', 'mathml', 'source_text', 'source_preamble',
                      'source_format', 'parse_confidence', 'conversion_status', 'render_method', 'render_error')
            asset = FormulaAsset(**{field: data.get(field) for field in fields},
                                 verification_status=data.get('verification_status', 'verified'),
                                 svg_cache_key=data.get('svg_cache_key'))
            db.session.add(asset)
            db.session.flush()
        remap[key] = asset.id
    def resolved(text):
        for old, new in remap.items():
            text = text.replace('[[formula:' + old + ']]', '[[formula:' + new + ']]')
        return text
    for field in ('question_text', 'context', 'explanation'):
        setattr(question, field, resolved(payload[field]))
    if question.question_type != 'short_answer':
        for option, data in zip(options, payload['options']):
            option.option_text = resolved(data['text'])
