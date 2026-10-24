"""Authentication and profile HTTP handlers.

Routes are registered directly on the provided Flask app so public endpoint
names (``login``, ``profile`` …) remain exactly compatible with templates and
external links during the gradual migration away from a monolithic app module.
"""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from database import db
from forms import ChangePasswordForm, LoginForm, RegistrationForm, UpdateProfileForm
from models import User
from services.media_storage import save_picture


def register_auth_routes(app) -> None:
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        form = RegistrationForm()
        if form.validate_on_submit():
            if form.role.data not in ("student", "teacher"):
                flash("Không thể đăng ký vai trò này.", "danger")
                return redirect(url_for("register"))
            user = User(
                username=form.username.data,
                fullname=form.fullname.data,
                user_code=form.user_code.data,
                role=form.role.data,
                phone=form.phone.data,
                position=form.position.data,
                is_active=True,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash("Đăng ký tài khoản thành công.", "success")
            return redirect(url_for("login"))
        return render_template("register.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data) and user.is_active:
                login_user(user)
                return redirect(request.args.get("next") or url_for("index"))
            flash("Sai tên đăng nhập, mật khẩu hoặc tài khoản đã bị khóa.", "danger")
        return render_template("login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        profile_form = UpdateProfileForm()
        password_form = ChangePasswordForm()

        if profile_form.submit_profile.data and profile_form.validate():
            if profile_form.avatar.data:
                current_user.avatar = save_picture(profile_form.avatar.data, app.config["UPLOAD_FOLDER_AVATARS"])
            current_user.fullname = profile_form.fullname.data
            current_user.username = profile_form.username.data
            current_user.phone = profile_form.phone.data
            current_user.position = profile_form.position.data
            current_user.birth_date = profile_form.birth_date.data
            db.session.commit()
            flash("Cập nhật hồ sơ thành công.", "success")
            return redirect(url_for("profile"))

        if password_form.submit_password.data and password_form.validate():
            if not current_user.check_password(password_form.old_password.data):
                flash("Mật khẩu cũ không đúng.", "danger")
            else:
                current_user.set_password(password_form.new_password.data)
                db.session.commit()
                flash("Đổi mật khẩu thành công.", "success")
                return redirect(url_for("profile"))

        if request.method == "GET":
            profile_form.fullname.data = current_user.fullname
            profile_form.username.data = current_user.username
            profile_form.phone.data = current_user.phone
            profile_form.position.data = current_user.position
            profile_form.birth_date.data = current_user.birth_date

        image_file = url_for("static", filename="avatars/" + (current_user.avatar or "default.jpg"))
        return render_template("profile.html", profile_form=profile_form, password_form=password_form, image_file=image_file)
