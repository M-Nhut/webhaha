"""Shared web routes and template context registration."""

from __future__ import annotations

import datetime as dt
import os
from os import PathLike

from flask import send_from_directory

from helpers import ROLE_LABELS


def register_main_routes(app, project_root: str | PathLike[str], is_vercel: bool) -> None:
    """Register static-upload routes and globals without changing URLs."""
    root = os.fspath(project_root)

    def serve_static_upload(folder_key: str, filename: str, fallback_subfolder: str):
        folder = app.config[folder_key]
        if is_vercel and os.path.exists(os.path.join(folder, filename)):
            return send_from_directory(folder, filename)
        return send_from_directory(os.path.join(root, "static", fallback_subfolder), filename)

    @app.route("/static/avatars/<path:filename>")
    def serve_avatar(filename):
        return serve_static_upload("UPLOAD_FOLDER_AVATARS", filename, "avatars")

    @app.route("/static/course_images/<path:filename>")
    def serve_course_image(filename):
        return serve_static_upload("UPLOAD_FOLDER_COURSES", filename, "course_images")

    @app.context_processor
    def inject_globals():
        today = dt.date.today()
        return {
            "ROLE_LABELS": ROLE_LABELS,
            "money": lambda value: f"{int(value or 0):,}".replace(",", "."),
            "today_date": today.strftime("%d/%m/%Y"),
            "now": dt.datetime.now(),
        }
