"""Preview the real Phase 3 UI with synthetic users and an in-memory database.

Local .env files are deliberately bypassed. Uploaded files live in a temporary
directory, and no real learner data or provider credentials are loaded.
Run: python3 scripts/preview_ui_phase3.py --port 8766
Fixture accounts: qa_teacher / qa_student / qa_admin, password Academy123!
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["FLASK_SECRET_KEY"] = "phase3-local-synthetic-preview"
    for key in tuple(os.environ):
        if key in {"POSTGRES_URL", "VERCEL"} or key.endswith("API_KEY") or key.startswith(("GEMINI_", "GOOGLE_AI_", "OPENAI_")):
            os.environ.pop(key, None)

    with TemporaryDirectory(prefix="linhedu-ui-phase3-") as directory:
        import config
        config.load_local_environment = lambda *args, **kwargs: None
        avatar_directory = Path(directory) / "avatars"
        config.upload_directories = lambda *args, **kwargs: {
            "UPLOAD_FOLDER_AVATARS": str(avatar_directory),
            "UPLOAD_FOLDER_COURSES": str(Path(directory) / "courses"),
        }
        from app import app
        from database import db
        from flask import abort, request, send_from_directory
        from models import BankQuestion, BankQuestionOption, Course, Enrollment, QuestionBank, User
        from whitenoise import WhiteNoise

        assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
        app.wsgi_app = WhiteNoise(app.wsgi_app, root=str(ROOT / "static"), prefix="static/", autorefresh=True, max_age=0)
        app.config.update(TESTING=False, WTF_CSRF_ENABLED=True, TEMPLATES_AUTO_RELOAD=True)
        app.jinja_env.auto_reload = True
        with app.app_context():
            db.drop_all()
            db.create_all()
            users = []
            for role, name, code in (("teacher", "Nguyễn Minh Anh", "GV-QA"), ("student", "Trần Bảo An", "HS-QA"), ("admin", "Quản trị LinhEdu", "AD-QA")):
                user = User(username=f"qa_{role}", fullname=name, user_code=code, role=role, phone="0901234567", is_active=True)
                user.set_password("Academy123!")
                users.append(user)
            db.session.add_all(users)
            db.session.flush()
            teacher, student, _ = users
            course = Course(course_name="Toán 10 · Nền tảng đại số", subject="Toán", teacher_id=teacher.id, classroom="Lớp 10A", description="Dữ liệu minh họa để kiểm tra giao diện.")
            bank = QuestionBank(name="Đại số 10 · Học liệu của tôi", subject="Toán", grade="10", created_by=teacher.id, visibility="private", description="Ngân hàng minh họa, không sử dụng dữ liệu thật.")
            db.session.add_all([course, bank])
            db.session.flush()
            db.session.add(Enrollment(student_id=student.id, course_id=course.id, status="active"))
            question = BankQuestion(bank_id=bank.id, created_by=teacher.id, question_text=r"Giải phương trình $x^2 - 5x + 6 = 0$.", question_type="single", difficulty_level="nhan_biet", subject="Toán", grade="10", classification_status="teacher_confirmed", explanation=r"Ta có $x^2 - 5x + 6 = (x-2)(x-3)$.")
            db.session.add(question)
            db.session.flush()
            for i, text in enumerate((r"$x=2$ hoặc $x=3$", r"$x=1$", r"$x=-2$", r"$x=0$")):
                db.session.add(BankQuestionOption(question_id=question.id, option_text=text, is_correct=i == 0, order_index=i))
            db.session.commit()

        @app.before_request
        def temporary_avatar():
            if request.path.startswith("/static/avatars/"):
                filename = request.path.rsplit("/", 1)[-1]
                if (avatar_directory / filename).is_file():
                    return send_from_directory(avatar_directory, filename)

        @app.get("/qa/errors/<int:code>")
        def qa_error(code):
            if code not in {400, 403, 404, 405, 429, 500}:
                abort(404)
            abort(code)

        print(f"Synthetic Phase 3 preview: http://127.0.0.1:{args.port}", flush=True)
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False, threaded=False)


if __name__ == "__main__":
    main()
