"""Serialize final duplicate checks with all bank/import writers in supported DBs."""
from database import db


def lock_import_transaction():
    # Call before reading/mutating request data; this service owns the transaction.
    db.session.rollback()
    if db.engine.dialect.name == 'sqlite':
        db.session.execute(db.text('BEGIN IMMEDIATE'))
    elif db.engine.dialect.name == 'postgresql':
        # User roles and creator roles participate in the import policy just
        # as much as the bank row does.  Lock them in the same transaction so
        # a concurrent role edit cannot invalidate an authorization decision
        # between the fresh read and the final write/receipt replay.
        db.session.execute(db.text(
            'LOCK TABLE import_session, question_bank, bank_question, '
            'bank_question_option, "user" IN SHARE ROW EXCLUSIVE MODE'
        ))
    else:
        raise ValueError('Dò trùng khi lưu cần SQLite hoặc PostgreSQL.')
