"""Class join codes: the short code a teacher shares, and the link built on it.

Codes are uppercase letters and digits without the easily confused
characters (0/O, 1/I), so a code read aloud or copied from a board still
works.  Uniqueness is checked in the application layer as well as by the
model, because existing deployments gain the column by migration without
a database-level unique constraint.
"""

from __future__ import annotations

import secrets
import string

from database import db
from models import Course

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 6


def generate_join_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))


def normalize_join_code(value: str | None) -> str:
    return (value or "").strip().upper()


def ensure_join_code(course: Course) -> str:
    """Give a course a join code if it does not have one yet, and save it."""
    if course.join_code:
        return course.join_code
    while True:
        code = generate_join_code()
        if not Course.query.filter_by(join_code=code).first():
            course.join_code = code
            db.session.add(course)
            db.session.commit()
            return code
