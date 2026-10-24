"""Add the nullable question-bank visibility column (Phase 1 schema only).

This script deliberately performs no ownership inference or data backfill.
Existing rows remain ``NULL`` until a separately reviewed migration assigns
their scope.  A NULL row is handled conservatively by the application policy.

The script uses sqlite3 directly so it can be reviewed/run independently of
the Flask application and never imports application configuration or secrets.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


COLUMN_NAME = "visibility"
INDEX_NAME = "ix_question_bank_visibility"


def migrate(database: str | Path) -> bool:
    """Add the nullable visibility column and index; return whether added."""
    database_path = Path(database)
    # sqlite3 creates a new empty file for a typo.  Refuse that behavior and
    # refuse symlink targets so a reviewed backup/path is always the target.
    if database_path.is_symlink() or not database_path.is_file():
        raise FileNotFoundError(
            f"Database path must be an existing regular SQLite file: {database_path}"
        )

    connection = sqlite3.connect(str(database_path))
    try:
        connection.execute("BEGIN IMMEDIATE")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if "question_bank" not in tables:
            raise RuntimeError("Không tìm thấy bảng question_bank.")

        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(question_bank)")
        }
        added = COLUMN_NAME not in columns
        if added:
            connection.execute(
                "ALTER TABLE question_bank ADD COLUMN visibility VARCHAR(20)"
            )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} "
            "ON question_bank (visibility)"
        )
        connection.commit()
        return added
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add nullable QuestionBank.visibility for bank visibility Phase 1."
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Path to the SQLite database to update (review/backup first).",
    )
    args = parser.parse_args()
    added = migrate(args.database)
    print("visibility column added." if added else "visibility column already present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
