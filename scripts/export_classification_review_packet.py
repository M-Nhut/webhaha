#!/usr/bin/env python3
"""Export blinded, de-duplicated chapter-6 questions for independent labelling."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.evaluation_dataset import build_blinded_rows


def export(database, bank_id):
    path = Path(database).resolve()
    if not path.is_file():
        raise ValueError('Database file does not exist.')
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        questions = connection.execute(
            "SELECT id, question_text, context, image_url, question_type, source_id FROM bank_question WHERE bank_id = ? AND grade IN ('9', 'Lớp 9') AND chapter = '6' ORDER BY id",
            (bank_id,)).fetchall()
        records = []
        for question in questions:
            options = connection.execute('SELECT option_text FROM bank_question_option WHERE question_id = ? ORDER BY order_index, id',
                                         (question['id'],)).fetchall()
            records.append({**dict(question), 'options':[dict(text=row['option_text']) for row in options], 'statements':[]})
    return build_blinded_rows(records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    parser.add_argument('bank_id', type=int)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    packet = export(args.database, args.bank_id)
    Path(args.output).write_text(json.dumps(packet['rows'], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'exported_rows':len(packet['rows']), 'omitted_duplicates':len(packet['omitted_duplicates']),
                      'output':str(Path(args.output).resolve())}, ensure_ascii=False))
