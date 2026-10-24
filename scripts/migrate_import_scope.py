#!/usr/bin/env python3
"""Add the stage-2 import scope column to an existing local SQLite database.

No app import, seeding or question updates. Writes a backup before the DDL change.
"""
from contextlib import closing
import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path


def migrate(database_path, backup_directory):
    path = Path(database_path).resolve()
    if not path.is_file():
        raise ValueError('Database file does not exist.')
    with closing(sqlite3.connect(f'file:{path}?mode=rw', uri=True, timeout=30)) as connection:
        columns = [row[1] for row in connection.execute('PRAGMA table_info(import_session)')]
        if not columns:
            raise ValueError('import_session table does not exist.')
        if 'scope_data' in columns:
            return dict(status='already_applied', database=str(path))
        backup_dir = Path(backup_directory).resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup_path = backup_dir / f'import-scope-before-{timestamp}.db'
        with closing(sqlite3.connect(backup_path)) as backup:
            connection.backup(backup)
        connection.execute('BEGIN IMMEDIATE')
        # Recheck after acquiring the write lock; another worker may have migrated.
        if 'scope_data' not in [row[1] for row in connection.execute('PRAGMA table_info(import_session)')]:
            connection.execute('ALTER TABLE import_session ADD COLUMN scope_data TEXT')
        connection.commit()
        return dict(status='applied', database=str(path), backup=str(backup_path),
                    integrity=connection.execute('PRAGMA integrity_check').fetchone()[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    parser.add_argument('--backup-directory', default='uploads/backups')
    args = parser.parse_args()
    print(json.dumps(migrate(args.database, args.backup_directory), ensure_ascii=False, indent=2))
