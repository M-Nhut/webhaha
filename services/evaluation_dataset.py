"""Build blinded, de-duplicated labelling packets for independent review."""
from services.question_classification_service import content_fingerprint


def build_blinded_rows(question_rows):
    """Remove answers and predictions so a second teacher can label independently."""
    seen, rows, omitted = {}, [], []
    for source in question_rows:
        option_rows = source.get('options') or []
        statement_rows = source.get('statements') or []
        if source.get('question_type') in ('true_false', 'truefalse') and not statement_rows:
            statement_rows, option_rows = option_rows, []
        question = dict(question_text=source.get('question_text', ''), context=source.get('context', ''),
                        image_url=source.get('image_url', ''), question_type=source.get('question_type', ''),
                        explanation='', formulas={},
                        options=[{'text': item.get('text') or item.get('option_text') or ''} for item in option_rows],
                        statements=[{'text': item.get('text') or item.get('option_text') or ''}
                                    for item in statement_rows])
        fingerprint = content_fingerprint(question)
        if fingerprint in seen:
            omitted.append(dict(question_id=source.get('id'), duplicate_of=seen[fingerprint]))
            continue
        row_id = f"bank-{source.get('id')}"
        seen[fingerprint] = row_id
        rows.append(dict(id=row_id, source=dict(bank_question_id=source.get('id'), source_id=source.get('source_id') or ''),
                        question=question, scope=dict(grade='9', chapters=['8'], lessons=['i']),
                         expected_primary_code='', expected_difficulty_level='',
                         labeler='', review_note=''))
    return dict(rows=rows, omitted_duplicates=omitted)
