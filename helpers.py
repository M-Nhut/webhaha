"""Legacy compatibility exports for shared application helpers.

New code imports from the focused modules in ``services``.  This module keeps
the old import path stable for scripts and third-party extensions.
"""

from __future__ import annotations

import datetime as dt

from database import db
from models import User
ROLE_LABELS = {"admin": "Admin", "teacher": "Giáo viên", "student": "Học sinh"}


def parse_date(value: str | None) -> dt.date | None:
    return dt.datetime.strptime(value, "%Y-%m-%d").date() if value else None


def resolve_student_id(value: str | int | None) -> int | None:
    """Resolve the legacy input formats accepted by enrollment forms."""
    if not value:
        return None
    try:
        numeric_id = int(value)
    except (TypeError, ValueError):
        numeric_id = None
    if numeric_id is not None:
        user = db.session.get(User, numeric_id)
        if user and user.role == "student":
            return user.id

    text = str(value)
    user = User.query.filter(
        (User.role == "student") & (
            (User.username == text.lower()) | (User.user_code == text.upper()) |
            (User.user_code == text) | (User.username == text)
        )
    ).first()
    return user.id if user else None


__all__ = [
    "ROLE_LABELS", "parse_date", "resolve_student_id",
]
