"""Phase 3 UI contracts exercised with native CSRF and synthetic data only."""
from __future__ import annotations

import io
import os
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_SECRET_KEY"] = "phase3-synthetic-tests"
for _key in tuple(os.environ):
    if _key in {"POSTGRES_URL", "VERCEL"} or _key.endswith("API_KEY") or _key.startswith(("GEMINI_", "GOOGLE_AI_", "OPENAI_")):
        os.environ.pop(_key, None)
import config

_uploads = TemporaryDirectory(prefix="linhedu-ui-phase3-tests-")
config.load_local_environment = lambda *args, **kwargs: None
config.upload_directories = lambda *args, **kwargs: {
    "UPLOAD_FOLDER_AVATARS": str(Path(_uploads.name) / "avatars"),
    "UPLOAD_FOLDER_COURSES": str(Path(_uploads.name) / "courses"),
}
from app import app
from database import db
from models import User


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def csrf(response):
    return next(attrs["value"] for tag, attrs in Markup(response.get_data(as_text=True)).tags if tag == "input" and attrs.get("name") == "csrf_token")


@pytest.fixture
def ui():
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:", "UI tests must never use the application database."
    previous = {key: app.config.get(key) for key in ("TESTING", "WTF_CSRF_ENABLED", "UPLOAD_FOLDER_AVATARS")}
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=True, UPLOAD_FOLDER_AVATARS=str(Path(_uploads.name) / "avatars"))
    Path(app.config["UPLOAD_FOLDER_AVATARS"]).mkdir(exist_ok=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        for role in ("teacher", "student", "admin"):
            user = User(username=f"qa_{role}", fullname=f"Tài khoản {role}", user_code=f"QA-{role}", role=role, is_active=True)
            user.set_password("Academy123!")
            db.session.add(user)
        db.session.commit()
        client = app.test_client()
        yield client
        db.session.remove()
        db.drop_all()
    app.config.update(previous)


def sign_in(client, role="teacher"):
    token = csrf(client.get("/login?next=/profile"))
    response = client.post("/login?next=/profile", data={"csrf_token": token, "username": f"qa_{role}", "password": "Academy123!", "submit": "Đăng nhập"})
    assert response.status_code == 302 and response.location.endswith("/profile")
    return client.get("/profile")


def profile_payload(token, **changes):
    return {"csrf_token": token, "fullname": "Nguyễn Minh Anh", "username": "qa_teacher", "phone": "0901234567", "position": "Giáo viên Toán", "birth_date": "1995-06-12", "submit_profile": "Lưu thông tin", **changes}


def test_login_retains_csrf_and_field_error_summary(ui):
    assert ui.post("/login", data={"username": "qa_teacher", "password": "Academy123!"}).status_code == 400
    response = ui.post("/login", data={"csrf_token": csrf(ui.get("/login")), "username": "", "password": ""})
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "data-auth-validation-summary" in html and 'href="#username"' in html and 'href="#password"' in html
    assert 'aria-invalid="true"' in html


def test_login_next_and_logout(ui):
    sign_in(ui)
    assert ui.get("/logout").status_code == 302
    assert ui.get("/profile").status_code == 302


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_registration_uses_supported_roles(ui, role):
    response = ui.post("/register", data={"csrf_token": csrf(ui.get("/register")), "user_code": "NEW-001", "fullname": "Người dùng thử", "username": "new_account", "role": role, "password": "Academy123!", "confirm_password": "Academy123!", "submit": "Đăng ký"})
    assert response.status_code == 302 and response.location.endswith("/login")
    user = User.query.filter_by(username="new_account").one()
    assert user.role == role and user.check_password("Academy123!")


def test_registration_rejects_invalid_role_and_duplicate_name(ui):
    response = ui.post("/register", data={"csrf_token": csrf(ui.get("/register")), "user_code": "NEW-001", "fullname": "Người dùng thử", "username": "qa_teacher", "role": "admin", "password": "Academy123!", "confirm_password": "Academy123!"})
    assert response.status_code == 200 and User.query.count() == 3
    html = response.get_data(as_text=True)
    assert "data-auth-validation-summary" in html and "Tên đăng nhập đã tồn tại" in html and "Vai trò đăng ký không hợp lệ" in html


def test_profile_forms_have_unique_ids_and_native_submit_fields(ui):
    response = sign_in(ui)
    tags = Markup(response.get_data(as_text=True)).tags
    ids = [attrs["id"] for _, attrs in tags if "id" in attrs]
    assert len(ids) == len(set(ids))
    forms = [attrs for tag, attrs in tags if tag == "form"]
    assert len(forms) == 2 and all(attrs.get("method") == "POST" and attrs.get("action") == "/profile" for attrs in forms)
    assert forms[0].get("enctype") == "multipart/form-data"
    names = [attrs.get("name") for tag, attrs in tags if tag == "input"]
    assert names.count("csrf_token") == 2 and "submit_profile" in names and "submit_password" in names


def test_profile_info_native_submit_saves_only_profile(ui):
    response = ui.post("/profile", data=profile_payload(csrf(sign_in(ui))))
    assert response.status_code == 302
    user = User.query.filter_by(username="qa_teacher").one()
    assert user.fullname == "Nguyễn Minh Anh" and user.phone == "0901234567" and user.birth_date.isoformat() == "1995-06-12"
    assert user.check_password("Academy123!")
    assert "Cập nhật hồ sơ thành công" in ui.get("/profile").get_data(as_text=True)


def test_profile_validation_preserves_attempted_input(ui):
    response = ui.post("/profile", data=profile_payload(csrf(sign_in(ui)), username="x", fullname="Tên đang sửa"))
    html = response.get_data(as_text=True)
    assert response.status_code == 200 and "data-profile-error-summary" in html
    assert 'href="#username"' in html and 'value="Tên đang sửa"' in html
    assert User.query.filter_by(username="qa_teacher").one().fullname == "Tài khoản teacher"


def test_password_old_failure_then_success(ui):
    token = csrf(sign_in(ui))
    data = {"csrf_token": token, "old_password": "incorrect", "new_password": "Academy456!", "confirm_password": "Academy456!", "submit_password": "Đổi mật khẩu"}
    response = ui.post("/profile", data=data)
    assert response.status_code == 200 and "Mật khẩu cũ không đúng" in response.get_data(as_text=True)
    assert User.query.filter_by(username="qa_teacher").one().check_password("Academy123!")
    data["old_password"] = "Academy123!"
    response = ui.post("/profile", data=data)
    assert response.status_code == 302
    user = User.query.filter_by(username="qa_teacher").one()
    assert user.check_password("Academy456!") and user.fullname == "Tài khoản teacher"


def test_password_server_mismatch_has_linked_error(ui):
    response = ui.post("/profile", data={"csrf_token": csrf(sign_in(ui)), "old_password": "Academy123!", "new_password": "Academy456!", "confirm_password": "different", "submit_password": "Đổi mật khẩu"})
    html = response.get_data(as_text=True)
    assert response.status_code == 200 and 'href="#confirm_password"' in html and 'id="confirm_password-errors"' in html
    assert User.query.filter_by(username="qa_teacher").one().check_password("Academy123!")


def test_avatar_upload_is_isolated_and_invalid_file_stays_in_form(ui):
    data = profile_payload(csrf(sign_in(ui)))
    data["avatar"] = (io.BytesIO(b"not an image"), "invalid.txt")
    response = ui.post("/profile", data=data, content_type="multipart/form-data")
    assert response.status_code == 200 and "Chỉ nhận file ảnh" in response.get_data(as_text=True)
    assert User.query.filter_by(username="qa_teacher").one().avatar == "default.jpg"
    # The existing server contract validates extensions and preserves bytes.
    payload = b"synthetic-upload-contract"
    data["avatar"] = (io.BytesIO(payload), "avatar.png")
    response = ui.post("/profile", data=data, content_type="multipart/form-data")
    assert response.status_code == 302
    filename = User.query.filter_by(username="qa_teacher").one().avatar
    assert (Path(app.config["UPLOAD_FOLDER_AVATARS"]) / filename).read_bytes() == payload
    assert Path(app.config["UPLOAD_FOLDER_AVATARS"]).is_relative_to(Path(_uploads.name))


@pytest.mark.parametrize("role", ["student", "teacher", "admin"])
def test_role_navigation_does_not_expand_permissions(ui, role):
    html = sign_in(ui, role).get_data(as_text=True)
    assert ('href="/practice"' in html) == (role == "student")
    assert ('href="/teacher/ai-settings"' in html) == (role == "teacher")
    assert ('href="/users/students"' in html) == (role == "admin")
    assert ('href="/question-banks"' in html) == (role in {"admin", "teacher"})
