"""Add nullable question-level scope columns (Phase 1 schema only).

This migration is additive and deliberately performs no ownership inference or
data backfill.  Existing ``bank_question`` rows remain ``NULL`` until a
separate, reviewed migration can classify them.  The application policy is
conservative for those legacy rows and fails closed when the bank/owner facts
do not make access unambiguous.

The script uses sqlite3 directly so it can be reviewed/run independently of
the Flask application.  It refuses missing or symlink database paths and does
not load application configuration or secrets.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


SCOPE_COLUMN = "scope"
OWNER_COLUMN = "private_owner_id"
SCOPE_INDEX = "ix_bank_question_scope"
OWNER_INDEX = "ix_bank_question_private_owner_id"


def migrate(database: str | Path) -> bool:
    """Add nullable scope/owner columns and indexes; return whether changed."""
    database_path = Path(database)
    # sqlite3 creates a new empty file for a typo.  Refuse that behavior and
    # refuse symlink targets so the reviewed path is always the target.
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
        if "bank_question" not in tables:
            raise RuntimeError("Không tìm thấy bảng bank_question.")

        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(bank_question)")
        }
        added = False
        if SCOPE_COLUMN not in columns:
            connection.execute(
                "ALTER TABLE bank_question ADD COLUMN scope VARCHAR(20)"
            )
            added = True
        if OWNER_COLUMN not in columns:
            connection.execute(
                "ALTER TABLE bank_question ADD COLUMN private_owner_id INTEGER REFERENCES \"user\"(id)"
            )
            added = True
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {SCOPE_INDEX} ON bank_question (scope)"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {OWNER_INDEX} "
            "ON bank_question (private_owner_id)"
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
        description=(
            "Add nullable BankQuestion.scope and private_owner_id for "
            "question-scope Phase 1. Existing rows are not backfilled."
        )
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Path to the SQLite database to update (review/backup first).",
    )
    args = parser.parse_args()
    added = migrate(args.database)
    print(
        "question scope columns added."
        if added
        else "question scope columns already present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
