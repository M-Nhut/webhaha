#!/usr/bin/env python3
"""Add classification audit columns to a live SQLite question bank with backup."""
from contextlib import closing
import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path


def migrate(database_path, backup_directory):
    database = Path(database_path).resolve()
    if not database.is_file():
        raise ValueError('Database file does not exist.')
    with closing(sqlite3.connect(f'file:{database}?mode=rw', uri=True, timeout=30)) as connection:
        columns = {row[1] for row in connection.execute('PRAGMA table_info(bank_question)')}
        if not columns:
            raise ValueError('bank_question table does not exist.')
        wanted = {'classification_status': 'VARCHAR(30)', 'classification_data': 'TEXT'}
        missing = [name for name in wanted if name not in columns]
        if not missing:
            return {'status': 'already_applied', 'database': str(database)}
        backups = Path(backup_directory).resolve(); backups.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup_path = backups / f'question-classification-before-{stamp}.db'
        with closing(sqlite3.connect(backup_path)) as backup:
            connection.backup(backup)
        connection.execute('BEGIN IMMEDIATE')
        columns = {row[1] for row in connection.execute('PRAGMA table_info(bank_question)')}
        for name in missing:
            if name not in columns:
                connection.execute(f'ALTER TABLE bank_question ADD COLUMN {name} {wanted[name]}')
        connection.commit()
        return {'status': 'applied', 'database': str(database), 'backup': str(backup_path),
                'columns': missing, 'integrity': connection.execute('PRAGMA integrity_check').fetchone()[0]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    parser.add_argument('--backup-directory', default='uploads/backups')
    args = parser.parse_args()
    print(json.dumps(migrate(args.database, args.backup_directory), ensure_ascii=False, indent=2))
