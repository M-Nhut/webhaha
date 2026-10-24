"""Flask extension instances and application-bound configuration.

Extensions are created once and bound in ``init_extensions`` so routes and
services can import shared instances without importing the Flask application.
"""

from __future__ import annotations

from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from database import db


csrf = CSRFProtect()
login_manager = LoginManager()


def init_extensions(app) -> None:
    """Bind persistence, CSRF and login support using existing settings."""
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Vui lòng đăng nhập để sử dụng tính năng này."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        # Local import keeps this infrastructure module independent from ORM
        # model loading order and prevents future circular imports.
        from models import User

        user = db.session.get(User, int(user_id))
        if not user or not user.is_active or user.role not in {"admin", "teacher", "student"}:
            return None
        return user
