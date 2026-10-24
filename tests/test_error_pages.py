"""Unit tests for custom HTTP error handlers and templates."""

import unittest
from flask import abort
from app import app


class TestErrorPages(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.config["TESTING"] = True

    def test_404_html_rendering(self):
        """Requesting a non-existent URL should return 404 and rendered error page."""
        response = self.client.get("/this-path-definitely-does-not-exist-xyz999")
        self.assertEqual(response.status_code, 404)
        html = response.get_data(as_text=True)
        self.assertIn("HTTP 404", html)
        self.assertIn("KHÔNG TÌM THẤY TRANG", html)
        self.assertIn("Trang bạn tìm kiếm không tồn tại", html)
        self.assertIn("Quay lại trang trước", html)
        self.assertIn("Về trang chủ", html)
        self.assertIn("Thông tin kỹ thuật", html)

    def test_405_html_rendering(self):
        """Sending an invalid method to a GET-only route should return 405."""
        # /login is GET/POST, but /courses is GET only
        response = self.client.post("/courses")
        self.assertEqual(response.status_code, 405)
        html = response.get_data(as_text=True)
        self.assertIn("HTTP 405", html)
        self.assertIn("PHƯƠNG THỨC KHÔNG HỢP LỆ", html)
        self.assertIn("Thao tác không được hỗ trợ", html)

    def test_api_404_returns_json(self):
        """API endpoints should receive structured JSON instead of HTML."""
        response = self.client.get("/api/non-existent-endpoint-test", headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.is_json)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["status_code"], 404)
        self.assertEqual(data["error"], "Not Found")
        self.assertIn("request_id", data)

    def test_custom_abort_routes(self):
        """Direct aborts with 403 and 400 render appropriate custom templates."""
        with app.test_request_context():
            from routes.errors import _make_error_response
            resp_403, code_403 = _make_error_response(
                403, "Forbidden", "TRUY CẬP BỊ TỪ CHỐI", "Khu vực bị hạn chế", "Không có quyền"
            )
            self.assertEqual(code_403, 403)
            self.assertIn("TRUY CẬP BỊ TỪ CHỐI", resp_403)
            self.assertIn("HTTP 403", resp_403)

            resp_500, code_500 = _make_error_response(
                500, "Internal Server Error", "SỰ CỐ MÁY CHỦ NỘI BỘ", "Lỗi máy chủ", "Hệ thống trục trặc"
            )
            self.assertEqual(code_500, 500)
            self.assertIn("SỰ CỐ MÁY CHỦ NỘI BỘ", resp_500)
            self.assertIn("HTTP 500", resp_500)


if __name__ == "__main__":
    unittest.main()
