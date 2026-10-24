"""Run the real bank UI with synthetic data and isolated storage only.

python3 scripts/preview_ui_phase4.py --port 8766
Accounts qa_teacher / qa_admin / qa_student; password Academy123!
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def isolate_environment(directory):
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["FLASK_SECRET_KEY"] = "phase4-synthetic-preview-only"
    for key in tuple(os.environ):
        if key in {"POSTGRES_URL", "VERCEL"} or key.endswith("API_KEY") or key.startswith(("GEMINI_", "GOOGLE_AI_", "OPENAI_")):
            os.environ.pop(key, None)
    import config
    config.load_local_environment = lambda *args, **kwargs: None
    config.upload_directories = lambda *args, **kwargs: {
        "UPLOAD_FOLDER_AVATARS": str(Path(directory) / "static/avatars"),
        "UPLOAD_FOLDER_COURSES": str(Path(directory) / "static/course_images"),
    }


def isolate_storage(app, directory):
    """Keep mutations, including legacy bank cleanup, away from real uploads."""
    from services import import_service, question_images
    app.template_folder = str(ROOT / "templates")
    app.static_folder = str(ROOT / "static")
    app.root_path = str(directory)
    question_images.DIRECTORY = Path(directory) / "static/uploads/questions"
    import_service.UPLOAD_TEMP_DIR = str(Path(directory) / "uploads/temp")
    # This legacy collector has a module-derived production path, rather than
    # app.root_path. It is irrelevant to the synthetic bank fixture.
    import_service.ImportService.cleanup_orphan_question_images = staticmethod(lambda: None)


def seed_data(db):
    from models import BankQuestion, BankQuestionOption, Course, CurriculumNode, Enrollment, QuestionBank, User
    from services.question_classification_service import content_fingerprint
    from services.curriculum_data import RETAINED_LESSON_NAME
    db.drop_all()
    db.create_all()
    users = {}
    for role, fullname in (("admin", "Quản trị LinhEdu"), ("teacher", "Nguyễn Minh Anh"), ("other", "Lê Quang Huy"), ("student", "Trần Bảo An")):
        user = User(username="qa_" + role, fullname=fullname, user_code="QA-" + role, role="teacher" if role == "other" else role, is_active=True)
        user.set_password("Academy123!")
        db.session.add(user)
        users[role] = user
    db.session.flush()
    teacher, admin, other = users["teacher"], users["admin"], users["other"]
    names = ("Mô tả không gian mẫu", "Tính xác suất của biến cố", "Quy tắc đếm", "Xác suất khi gieo xúc xắc", "Xác suất khi rút thẻ", "Biến cố đối", "Phép thử nhiều bước", "Ứng dụng xác suất")
    nodes = []
    for number, name in enumerate(names, 1):
        node = CurriculumNode(grade="9", chapter_code="8", chapter_name="Thống kê và xác suất", lesson_code="i", lesson_name=RETAINED_LESSON_NAME, category_code=str(number), category_name=name, created_by=admin.id, is_active=True)
        db.session.add(node)
        nodes.append(node)
    db.session.add(CurriculumNode(grade="9", chapter_code="8", chapter_name="Thống kê và xác suất", lesson_code="i", lesson_name=RETAINED_LESSON_NAME, category_code="9", category_name="Dạng đã ngừng sử dụng", created_by=admin.id, is_active=False))
    banks = {}
    for key, name, owner, grade, shared, active in (
        ("shared", "Toán 9 · Không gian mẫu và xác suất", admin, "9", True, True),
        ("general", "Đại số 10 · Học liệu của tôi", teacher, "10", False, True),
        ("research", "Toán 9 · Xác suất · Duyệt nhãn", teacher, "9", False, True),
        ("inactive", "Ngân hàng ôn tập học kỳ trước · Tạm ngừng dùng cho bài mới", teacher, "10", False, False),
        ("foreign", "Học liệu riêng của giáo viên khác", other, "10", False, True),
        ("empty", "Ngân hàng mới chưa có câu hỏi", teacher, "10", False, True),
    ):
        bank = QuestionBank(name=name, subject="Toán", grade=grade, topic="Không gian mẫu và xác suất · Chương 8 · Bài i" if grade == "9" else "Phương trình và bất phương trình", description="Dữ liệu minh họa để kiểm tra giao diện, không sử dụng dữ liệu thật.", created_by=owner.id, visibility="shared" if shared else "private", is_active=active)
        db.session.add(bank)
        banks[key] = bank
    db.session.flush()
    question_ids = {}

    def question(key, bank_key, kind, text, *, owner=teacher, node=None, status="teacher_confirmed", shared=False, category="Phương trình bậc hai", difficulty="nhan_biet"):
        bank = banks[bank_key]
        row = BankQuestion(bank_id=bank.id, created_by=owner.id, private_owner_id=None if shared else owner.id, scope="shared" if shared else "private", subject="Toán", grade=bank.grade, question_text=text, question_type=kind if kind in {"single", "true_false", "short_answer"} else "single", difficulty_level=difficulty, classification_status=status, question_category=category if node is None else node.category_code, curriculum_node_id=node.id if node else None, chapter="8" if bank.grade == "9" else None, section="i" if bank.grade == "9" else None, explanation=r"Đối chiếu các kết quả rồi áp dụng công thức $P(A)=\frac{n(A)}{n(\Omega)}$.")
        db.session.add(row)
        db.session.flush()
        options = [r"$x=2$ hoặc $x=3$", r"$x=1$", r"$x=-2$", r"$x=0$"]
        if kind == "true_false":
            options = [r"a) Phương trình có hai nghiệm phân biệt.", r"b) Tổng hai nghiệm bằng $5$.", r"c) Tích hai nghiệm bằng $-6$.", r"d) Một nghiệm bằng $0$."]
            if node:
                row.learning_metadata = json.dumps({"statements": [{"curriculum_code": node.canonical_code, "cognitive_level": difficulty} for _ in range(4)]})
        elif kind == "short_answer":
            options = ["0.5", "1/2"]
            row.learning_metadata = json.dumps({"short_answer": {"mode": "numeric", "tolerance": "0"}})
        elif kind == "essay":
            options = []
        for i, text in enumerate(options):
            db.session.add(BankQuestionOption(question_id=row.id, option_text=text, is_correct=i < 2 if kind in {"true_false", "short_answer", "multiple_choice"} else i == 0, order_index=i))
        db.session.flush()
        if kind in {"multiple_choice", "essay"}:
            # Simulate a historical row in this disposable DB. The live ORM
            # rightly rejects creating new questions in these retired types.
            from sqlalchemy import update
            db.session.execute(update(BankQuestion).where(BankQuestion.id == row.id).values(question_type=kind).execution_options(synchronize_session=False))
        question_ids[key] = row.id
        return row

    for i in range(28):
        question(f"common-{i}", "shared", ("single", "true_false", "short_answer")[i % 3], rf"Câu {i + 1}. Gieo một xúc xắc cân đối. Xác định xác suất của biến cố có $n(A)={i % 5 + 1}$ kết quả thuận lợi.", owner=admin, node=nodes[i % 8], shared=True, difficulty=("nhan_biet", "thong_hieu", "van_dung", "van_dung_cao")[i % 4])
    question("overlay", "shared", "single", r"Câu bổ sung riêng. Tính $P(A)$ khi có ba kết quả thuận lợi trong sáu kết quả.", node=nodes[0])
    question("foreign-overlay", "shared", "single", "Nội dung riêng của giáo viên khác không được hiện cho qa_teacher.", owner=other, node=nodes[0])
    question("general-single", "general", "single", r"Giải phương trình $x^2-5x+6=0$.")
    question("general-tf", "general", "true_false", r"Cho phương trình $x^2-5x+6=0$. Xác định tính đúng sai của các phát biểu.")
    question("general-short", "general", "short_answer", r"Một hộp có 5 thẻ đỏ trong 10 thẻ. Tính xác suất lấy được thẻ đỏ.", category="Xác suất cơ bản")
    question("general-long", "general", "single", "Một lớp học tổ chức buổi nghiên cứu về đại số. " * 12 + r"Giải thích và chọn nghiệm của phương trình $x^2-5x+6=0$.", category="Nội dung dài và công thức")
    question("general-legacy", "general", "multiple_choice", "Câu lưu trữ cũ có nhiều phương án đúng; vẫn xem được theo hợp đồng hiện tại.")
    question("general-essay", "general", "essay", "Câu tự luận lưu trữ: giải thích cách tìm nghiệm của phương trình.")
    image = question("general-image", "general", "single", "Đọc hình minh họa và xác định hoành độ giao điểm.")
    image.image_url = "/qa/media/graph.svg"
    for i, kind in enumerate(("single", "true_false", "short_answer")):
        question("research-" + kind, "research", kind, f"Câu nghiên cứu {i+1}. Gieo một xúc xắc cân đối và xét biến cố có số chấm chẵn.", node=nodes[i])
    suggestion = question("suggested", "research", "single", "Gieo một xúc xắc cân đối. Biến cố số chấm chẵn có bao nhiêu kết quả?", status="suggested", node=nodes[3])
    db.session.flush()
    suggestion.classification_data = json.dumps({"status": "suggested", "primary_code": nodes[3].canonical_code, "difficulty_level": "nhan_biet", "content_fingerprint": content_fingerprint(suggestion.to_dict()), "rationale": ["Đối chiếu kết quả của phép thử gieo xúc xắc."], "confidence": .9}, ensure_ascii=False)
    stale = question("stale", "research", "single", "Nội dung đã sửa sau khi gợi ý; cần đối chiếu lại nhãn.", status="suggested", node=nodes[0])
    stale.classification_data = json.dumps({"status": "suggested", "primary_code": nodes[0].canonical_code, "difficulty_level": "nhan_biet", "content_fingerprint": "old-fingerprint", "rationale": ["Gợi ý cũ."]})
    question("unclassified", "research", "single", "Câu chưa gán kiến thức, cần giáo viên xem và chọn dạng.", node=None, status="needs_review", category=None)
    course = Course(course_name="Toán 9 · Lớp 9A", subject="Toán", teacher_id=teacher.id)
    db.session.add(course)
    db.session.flush()
    db.session.add(Enrollment(student_id=users["student"].id, course_id=course.id, status="active"))
    db.session.commit()
    return {"users": {key: user.id for key, user in users.items()}, "banks": {key: bank.id for key, bank in banks.items()}, "questions": question_ids, "nodes": [node.id for node in nodes]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="linhedu-ui-phase4-") as directory:
        isolate_environment(directory)
        from app import app
        from database import db
        from flask import request, send_from_directory, Response, jsonify
        from whitenoise import WhiteNoise
        isolate_storage(app, directory)
        assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
        app.wsgi_app = WhiteNoise(app.wsgi_app, root=str(ROOT / "static"), prefix="static/", autorefresh=True, max_age=0)
        app.config.update(TESTING=False, WTF_CSRF_ENABLED=True, TEMPLATES_AUTO_RELOAD=True)
        app.jinja_env.auto_reload = True
        with app.app_context():
            data = seed_data(db)

        @app.before_request
        def preview_media():
            if request.path.startswith("/static/uploads/questions/") or request.path.startswith("/static/avatars/"):
                path = Path(directory) / request.path.lstrip("/")
                if path.is_file() and path.resolve().is_relative_to(Path(directory).resolve()):
                    return send_from_directory(path.parent, path.name)

        @app.get("/qa/fixture")
        def fixture_info():
            return jsonify(data)

        @app.get("/qa/media/graph.svg")
        def graph():
            return Response('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="220" viewBox="0 0 480 220"><rect width="480" height="220" fill="white"/><path d="M40 185H440M60 200V20" stroke="#596579" stroke-width="2"/><path d="M90 45Q230 290 370 45" fill="none" stroke="#1d4ed8" stroke-width="3"/><text x="435" y="210" font-family="Arial" font-size="15">x</text><text x="40" y="24" font-family="Arial" font-size="15">y</text><text x="135" y="205" font-family="Arial" font-size="15">2</text><text x="310" y="205" font-family="Arial" font-size="15">3</text></svg>', mimetype="image/svg+xml")

        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        print(f"Synthetic Phase 4 preview: http://127.0.0.1:{args.port}/login", flush=True)
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False, threaded=False)


if __name__ == "__main__":
    main()
