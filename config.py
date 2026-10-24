"""Application configuration and environment loading.

Keeping configuration outside the HTTP entry point makes the same settings
available to Flask, CLI commands and tests without importing route modules.
"""

from __future__ import annotations

import os
import secrets
import shutil
from pathlib import Path
from typing import Final


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent


def load_local_environment(project_root: Path = PROJECT_ROOT) -> None:
    """Load local environment files, preserving normal process precedence.

    ``.env.local`` intentionally overrides ``.env`` to retain the behaviour of
    the original bootstrap code.  python-dotenv is optional for local setup.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(project_root / ".env")
        load_dotenv(project_root / ".env.local", override=True)
        return
    except ImportError:
        pass

    for filename, override in ((".env", False), (".env.local", True)):
        try:
            for raw_line in (project_root / filename).read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = (part.strip() for part in line.split("=", 1))
                if not key or not key.replace("_", "").isalnum():
                    continue
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                if override:
                    os.environ[key] = value
                else:
                    os.environ.setdefault(key, value)
        except OSError:
            # Environment files are optional. The deployment environment is
            # still the authoritative configuration source.
            continue


def is_vercel_environment() -> bool:
    return os.environ.get("VERCEL") is not None


def database_uri(project_root: Path, *, is_vercel: bool) -> str:
    """Return the configured database URI, preserving legacy Vercel fallback."""
    configured_uri = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if configured_uri:
        return configured_uri.replace("postgres://", "postgresql://", 1)

    if not is_vercel:
        return f"sqlite:///{project_root / 'tutoring_center.db'}"

    temporary_database = Path("/tmp/tutoring_center.db")
    bundled_database = project_root / "tutoring_center.db"
    if bundled_database.exists() and not temporary_database.exists():
        shutil.copy(bundled_database, temporary_database)
    return f"sqlite:///{temporary_database}"


def upload_directories(project_root: Path, *, is_vercel: bool) -> dict[str, str]:
    """Return the avatar and course upload paths used by the existing routes."""
    if is_vercel:
        return {
            "UPLOAD_FOLDER_AVATARS": "/tmp/static/avatars",
            "UPLOAD_FOLDER_COURSES": "/tmp/static/course_images",
        }
    static_root = project_root / "static"
    return {
        "UPLOAD_FOLDER_AVATARS": str(static_root / "avatars"),
        "UPLOAD_FOLDER_COURSES": str(static_root / "course_images"),
    }


def configure_application(app) -> bool:
    """Apply all infrastructure settings and return whether this is Vercel."""
    load_local_environment()
    deployed_on_vercel = is_vercel_environment()
    uri = database_uri(PROJECT_ROOT, is_vercel=deployed_on_vercel)

    # Session signing and credential encryption deliberately use different
    # server secrets.  A missing signing secret gets a process-local value so
    # development/test imports remain usable, but credential administration is
    # explicitly gated on ``FLASK_SECRET_KEY`` being configured (see
    # services.ai_gateway.credential_security_ready).  Never use this value to
    # encrypt provider keys.
    flask_secret = os.environ.get("FLASK_SECRET_KEY", "").strip()
    app.config.update(
        SECRET_KEY=flask_secret or secrets.token_urlsafe(48),
        FLASK_SECRET_KEY_CONFIGURED=bool(flask_secret),
        SQLALCHEMY_DATABASE_URI=uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        **upload_directories(PROJECT_ROOT, is_vercel=deployed_on_vercel),
    )
    if uri.startswith("postgresql"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_recycle": 300,
            "pool_pre_ping": True,
        }

    for folder_key in ("UPLOAD_FOLDER_AVATARS", "UPLOAD_FOLDER_COURSES"):
        os.makedirs(app.config[folder_key], exist_ok=True)
    return deployed_on_vercel
