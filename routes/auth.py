"""Authentication and profile HTTP handlers.

Routes are registered directly on the provided Flask app so public endpoint
names (``login``, ``profile`` …) remain exactly compatible with templates and
external links during the gradual migration away from a monolithic app module.

Social sign-in (Google first, Facebook later) never replaces the local
account: a provider identity is linked to a local ``User`` through
``SocialAccount``, and a brand-new social identity must complete the local
profile (role, username, user_code) once before it can sign in.  That keeps
the existing username/password flow, roles and enrollments untouched, and
keeps a later Supabase Auth migration to the identity boundary only.
"""

from __future__ import annotations

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from database import db
from forms import (
    ChangePasswordForm,
    LoginForm,
    RegistrationForm,
    SocialCompleteForm,
    UpdateProfileForm,
)
from models import Course, Enrollment, SocialAccount, User
from services.media_storage import save_picture
from services.social_auth import (
    exchange_google_code,
    google_configured,
    google_login_url,
    safe_next,
)


def _finish_social_login(identity: dict) -> str:
    """Sign in a linked account, or stash a new identity for completion.

    Returns the redirect target: the saved ``next`` URL for an existing
    account, or the profile-completion page for a new identity.
    """
    next_url = safe_next(session.pop("google_oauth_next", None))
    account = SocialAccount.query.filter_by(
        provider=identity["provider"], provider_user_id=identity["provider_user_id"]
    ).first()
    if account and account.user and account.user.is_active:
        login_user(account.user)
        return next_url or url_for("index")
    user = User.query.filter_by(email=identity["email"]).first() if identity["email"] else None
    if user and user.is_active:
        # The email was verified by Google, so linking here cannot hijack an
        # account whose email was never set by its owner: local accounts have
        # no email until a social sign-in sets one.
        db.session.add(
            SocialAccount(
                user_id=user.id,
                provider=identity["provider"],
                provider_user_id=identity["provider_user_id"],
                email=identity["email"],
            )
        )
        db.session.commit()
        login_user(user)
        return next_url or url_for("index")
    session["social_pending"] = identity
    if next_url:
        session["social_pending_next"] = next_url
    return url_for("social_complete")


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
        return render_template("register.html", form=form, google_enabled=google_configured())

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data) and user.is_active:
                login_user(user)
                return redirect(safe_next(request.args.get("next")) or url_for("index"))
            flash("Sai tên đăng nhập, mật khẩu hoặc tài khoản đã bị khóa.", "danger")
        return render_template("login.html", form=form, google_enabled=google_configured())

    @app.route("/auth/google")
    def google_login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        if not google_configured():
            flash("Đăng nhập Google chưa được cấu hình.", "danger")
            return redirect(url_for("login"))
        return redirect(google_login_url(safe_next(request.args.get("next"))))

    @app.route("/auth/google/callback")
    def google_callback():
        if request.args.get("error"):
            flash("Bạn đã hủy đăng nhập Google.", "info")
            return redirect(url_for("login"))
        code = request.args.get("code")
        if not code:
            flash("Google không trả về mã xác nhận.", "danger")
            return redirect(url_for("login"))
        try:
            identity = exchange_google_code(code, request.args.get("state"))
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("login"))
        return redirect(_finish_social_login(identity))

    @app.route("/auth/complete", methods=["GET", "POST"])
    def social_complete():
        pending = session.get("social_pending")
        if not pending:
            return redirect(url_for("login"))
        form = SocialCompleteForm()
        if request.method == "GET" and pending.get("name") and not form.fullname.data:
            form.fullname.data = pending["name"]
        if form.validate_on_submit():
            if form.role.data not in ("student", "teacher"):
                flash("Không thể đăng ký vai trò này.", "danger")
                return redirect(url_for("social_complete"))
            user = User(
                username=form.username.data,
                fullname=form.fullname.data,
                user_code=form.user_code.data,
                role=form.role.data,
                email=pending["email"],
                is_active=True,
            )
            # No local password: this account signs in through Google.
            # check_password on an empty hash already fails safely.
            db.session.add(user)
            db.session.flush()
            db.session.add(
                SocialAccount(
                    user_id=user.id,
                    provider=pending["provider"],
                    provider_user_id=pending["provider_user_id"],
                    email=pending["email"],
                )
            )
            db.session.commit()
            session.pop("social_pending", None)
            next_url = safe_next(session.pop("social_pending_next", None))
            login_user(user)
            session["just_registered"] = True
            if next_url and next_url.startswith("/join/") and user.role == "student":
                return redirect(next_url)
            flash("Đăng ký bằng Google thành công.", "success")
            return redirect(url_for("onboarding"))
        return render_template(
            "social_complete.html", form=form, email=pending["email"], provider=pending["provider"]
        )

    @app.route("/onboarding")
    @login_required
    def onboarding():
        if current_user.role == "teacher":
            courses = Course.query.filter_by(teacher_id=current_user.id).order_by(Course.course_name).all()
            return render_template(
                "onboarding_teacher.html",
                courses=courses,
                just_registered=bool(session.pop("just_registered", False)),
            )
        if current_user.role == "student":
            enrollments = Enrollment.query.filter_by(student_id=current_user.id, status="active").all()
            return render_template(
                "onboarding_student.html",
                enrollments=enrollments,
                just_registered=bool(session.pop("just_registered", False)),
            )
        return redirect(url_for("index"))

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
