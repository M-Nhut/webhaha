#!/usr/bin/env python3
"""Add stage-2a import audit columns to an existing SQLite database safely.

This script never imports the web application or seeds data. It creates a
consistent SQLite backup before any schema change and may be run repeatedly.
"""
from contextlib import closing
import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path


COLUMNS = {
    'duplicate_decisions': 'TEXT',
    'duplicate_report': 'TEXT',
    'result_data': 'TEXT',
}


def migrate(database_path, backup_directory):
    path = Path(database_path).resolve()
    if not path.is_file():
        raise ValueError('Database file does not exist.')
    with closing(sqlite3.connect(f'file:{path}?mode=rw', uri=True, timeout=30)) as connection:
        present = {row[1] for row in connection.execute('PRAGMA table_info(import_session)')}
        if not present:
            raise ValueError('import_session table does not exist.')
        missing = [name for name in COLUMNS if name not in present]
        if not missing:
            return dict(status='already_applied', database=str(path))
        backup_dir = Path(backup_directory).resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup_path = backup_dir / f'import-duplicates-before-{stamp}.db'
        with closing(sqlite3.connect(backup_path)) as backup:
            connection.backup(backup)
        connection.execute('BEGIN IMMEDIATE')
        present = {row[1] for row in connection.execute('PRAGMA table_info(import_session)')}
        applied = []
        for name in missing:
            if name not in present:
                connection.execute(f'ALTER TABLE import_session ADD COLUMN {name} {COLUMNS[name]}')
                applied.append(name)
        connection.commit()
        return dict(status='applied', database=str(path), backup=str(backup_path), columns=applied,
                    integrity=connection.execute('PRAGMA integrity_check').fetchone()[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    parser.add_argument('--backup-directory', default='uploads/backups')
    args = parser.parse_args()
    print(json.dumps(migrate(args.database, args.backup_directory), ensure_ascii=False, indent=2))
