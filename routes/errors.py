"""HTTP Error handlers and custom error presentation.

Provides rich, responsive visual error pages for HTML visitors and clean
structured JSON responses for API/AJAX requests.
"""

from __future__ import annotations

import logging
import uuid
import datetime as dt
from typing import Any

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from database import db

logger = logging.getLogger(__name__)


def _is_api_request() -> bool:
    """Detect whether the incoming request expects a JSON response."""
    path = request.path.lower()
    if path.startswith("/api/") or path.startswith("/questions/") and ("toggle" in path or "update" in path):
        return True
    if request.is_json:
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json" and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]


def _make_error_response(
    status_code: int,
    status_name: str,
    badge_text: str,
    title: str,
    message: str,
    details: str | None = None,
):
    req_id = f"ERR-{status_code}-{uuid.uuid4().hex[:6].upper()}"

    if _is_api_request():
        payload: dict[str, Any] = {
            "success": False,
            "status_code": status_code,
            "error": status_name,
            "message": message,
            "path": request.path,
            "request_id": req_id,
        }
        if details and (request.path.startswith("/api/formulas") or status_code != 500):
            payload["details"] = details
        return jsonify(payload), status_code

    template_file = f"errors/{status_code}.html"
    try:
        return (
            render_template(
                template_file,
                status_code=status_code,
                status_name=status_name,
                badge_text=badge_text,
                title=title,
                message=message,
                details=details,
                request_id=req_id,
                now=dt.datetime.now(),
            ),
            status_code,
        )
    except Exception:
        # Fallback to master error.html if specific template fails
        return (
            render_template(
                "errors/error.html",
                status_code=status_code,
                status_name=status_name,
                badge_text=badge_text,
                title=title,
                message=message,
                details=details,
                request_id=req_id,
                now=dt.datetime.now(),
            ),
            status_code,
        )


def register_error_handlers(app: Flask) -> None:
    """Register all HTTP status code handlers onto the Flask application."""

    @app.errorhandler(400)
    def handle_bad_request(error):
        desc = getattr(error, "description", None) or "Yêu cầu gửi lên máy chủ không hợp lệ hoặc thiếu tham số cần thiết."
        return _make_error_response(
            status_code=400,
            status_name="Bad Request",
            badge_text="YÊU CẦU KHÔNG HỢP LỆ",
            title="Yêu cầu không thể xử lý",
            message=desc,
        )

    @app.errorhandler(403)
    def handle_forbidden(error):
        desc = getattr(error, "description", None) or "Bạn không có quyền truy cập vào tài nguyên hoặc trang này."
        return _make_error_response(
            status_code=403,
            status_name="Forbidden",
            badge_text="TRUY CẬP BỊ TỪ CHỐI",
            title="Khu vực bị hạn chế truy cập",
            message=desc,
        )

    @app.errorhandler(404)
    def handle_not_found(error):
        desc = getattr(error, "description", None) or "Trang hoặc tài nguyên bạn tìm kiếm không tồn tại trên hệ thống."
        return _make_error_response(
            status_code=404,
            status_name="Not Found",
            badge_text="KHÔNG TÌM THẤY TRANG",
            title="Trang bạn tìm kiếm không tồn tại",
            message=desc,
        )

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        method = request.method
        return _make_error_response(
            status_code=405,
            status_name="Method Not Allowed",
            badge_text="PHƯƠNG THỨC KHÔNG HỢP LỆ",
            title="Thao tác không được hỗ trợ",
            message=f"Phương thức gửi yêu cầu '{method}' không được phép trên đường dẫn này. Vui lòng quay lại hoặc thực hiện lại từ giao diện hợp lệ.",
        )

    @app.errorhandler(429)
    def handle_too_many_requests(error):
        desc = getattr(error, "description", None) or "Bạn đã gửi quá nhiều yêu cầu trong thời gian ngắn. Vui lòng chờ ít phút và thử lại."
        return _make_error_response(
            status_code=429,
            status_name="Too Many Requests",
            badge_text="QUÁ NHIỀU YÊU CẦU",
            title="Tạm thời giới hạn truy cập",
            message=desc,
        )

    @app.errorhandler(500)
    def handle_internal_server_error(error):
        # Roll back broken session to keep connection pool and state clean
        try:
            db.session.rollback()
        except Exception:
            pass

        logger.exception("500 Internal Server Error at %s: %s", request.path, error)
        details = str(error) if app.debug else None
        return _make_error_response(
            status_code=500,
            status_name="Internal Server Error",
            badge_text="SỰ CỐ MÁY CHỦ NỘI BỘ",
            title="Đã xảy ra sự cố ngoài ý muốn",
            message="Hệ thống máy chủ gặp sự cố tạm thời khi xử lý yêu cầu. Đội ngũ kỹ thuật đã được thông báo và đang tiến hành xử lý.",
            details=details,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        code = error.code or 500
        if code in (400, 403, 404, 405, 429, 500):
            # Handled by specific handlers above
            return error
        return _make_error_response(
            status_code=code,
            status_name=error.name,
            badge_text=f"MÃ LỖI {code}",
            title=f"Lỗi {code} - {error.name}",
            message=error.description or "Đã xảy ra sự cố khi xử lý yêu cầu của bạn.",
        )

    @app.errorhandler(Exception)
    def handle_unhandled_exception(error: Exception):
        try:
            db.session.rollback()
        except Exception:
            pass

        logger.exception("Unhandled Exception at %s: %s", request.path, error)
        details = str(error) if app.debug else None
        return _make_error_response(
            status_code=500,
            status_name="Internal Server Error",
            badge_text="SỰ CỐ MÁY CHỦ NỘI BỘ",
            title="Đã xảy ra sự cố ngoài ý muốn",
            message="Hệ thống máy chủ gặp sự cố tạm thời khi xử lý yêu cầu. Đội ngũ kỹ thuật đã được thông báo và đang tiến hành xử lý.",
            details=details,
        )
