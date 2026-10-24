"""Bank UI integration contracts, isolated data/storage and native CSRF."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import MultiDict
from scripts.preview_ui_phase4 import isolate_environment, isolate_storage, seed_data

_storage = TemporaryDirectory(prefix="linhedu-phase4-tests-")
isolate_environment(_storage.name)
from app import app
from database import db
from models import BankQuestion, CurriculumNode, QuestionBank
isolate_storage(app, _storage.name)


def token(response):
    html = response.get_data(as_text=True)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html) or re.search(r'name="csrf-token"[^>]*content="([^"]+)"', html)
    return match.group(1)


@pytest.fixture
def bank_ui():
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
    isolate_storage(app, _storage.name)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    with app.app_context():
        fixture = seed_data(db)
        yield SimpleNamespace(client=app.test_client(), data=fixture)
        db.session.remove()
        db.drop_all()


def login(fixture, role="teacher"):
    client = fixture.client
    response = client.get("/login")
    assert client.post("/login", data={"csrf_token": token(response), "username": "qa_" + role, "password": "Academy123!"}).status_code == 302
    from flask import g
    g.pop("_login_user", None)


def bank_url(fixture, name="general", suffix=""):
    return f"/question-banks/{fixture.data['banks'][name]}{suffix}"


@pytest.mark.parametrize("role", ["teacher", "admin"])
def test_bank_pages_preserve_roles_and_modes(bank_ui, role):
    login(bank_ui, role)
    client = bank_ui.client
    for path in ("/question-banks", "/question-banks/new", bank_url(bank_ui), bank_url(bank_ui, "shared"), bank_url(bank_ui, "research"), bank_url(bank_ui, "empty"), bank_url(bank_ui, "research", "/classification?status=all"), bank_url(bank_ui, "research", "/classification/evaluation"), "/curriculum?inactive=1"):
        assert client.get(path).status_code == 200, path
    list_html = client.get("/question-banks").get_data(as_text=True)
    assert ("Học liệu riêng của giáo viên khác" in list_html) == (role == "admin")


def test_student_cannot_access_bank_or_catalog(bank_ui):
    login(bank_ui, "student")
    for path in ("/question-banks", bank_url(bank_ui), "/curriculum"):
        response = bank_ui.client.get(path)
        assert response.status_code == 302 and response.location.endswith("/")


def test_shared_scope_and_pagination_never_disclose_foreign_private(bank_ui):
    login(bank_ui)
    client = bank_ui.client
    first = client.get(bank_url(bank_ui, "shared", "?scope=all&per_page=25"))
    second = client.get(bank_url(bank_ui, "shared", "?scope=all&per_page=25&page=2"))
    assert first.status_code == second.status_code == 200
    for response in (first, second, client.get(bank_url(bank_ui, "shared", "?scope=mine"))):
        assert "Nội dung riêng của giáo viên khác" not in response.get_data(as_text=True)
    overlay_text = db.session.get(BankQuestion, bank_ui.data['questions']['overlay']).question_text
    encoded_text = json.dumps(overlay_text, ensure_ascii=True)[1:-1]
    assert encoded_text in client.get(bank_url(bank_ui, "shared", "?scope=mine")).get_data(as_text=True)
    assert encoded_text not in client.get(bank_url(bank_ui, "shared", "?scope=common")).get_data(as_text=True)


def test_metadata_save_has_csrf_validation_and_retains_draft(bank_ui):
    login(bank_ui)
    client = bank_ui.client
    assert client.post("/question-banks/new", data={"name": "Không CSRF", "subject": "Toán"}).status_code == 400
    before = QuestionBank.query.count()
    response = client.post("/question-banks/new", data={"csrf_token": token(client.get("/question-banks/new")), "name": " ", "subject": "", "description": "Bản nhập vẫn còn"})
    assert response.status_code == 200 and QuestionBank.query.count() == before
    html = response.get_data(as_text=True)
    assert 'href="#name"' in html and 'href="#subject"' in html and "Bản nhập vẫn còn" in html
    response = client.post("/question-banks/new", data={"csrf_token": token(client.get("/question-banks/new")), "name": "Ngân hàng kiểm thử mới", "subject": "Toán", "grade": "10", "topic": "Đại số", "description": "Bản mô tả", "visibility": "shared", "created_by": bank_ui.data['users']['admin']})
    assert response.status_code == 302
    created = QuestionBank.query.filter_by(name="Ngân hàng kiểm thử mới").one()
    assert created.created_by == bank_ui.data['users']['teacher'] and created.visibility == "private"


def test_metadata_edit_validates_before_change_and_saves_timestamp(bank_ui):
    login(bank_ui)
    client, url = bank_ui.client, bank_url(bank_ui, suffix="/edit")
    bank = db.session.get(QuestionBank, bank_ui.data['banks']['general'])
    original = bank.name
    response = client.post(url, data={"csrf_token": token(client.get(url)), "name": "x" * 201, "subject": "Toán"})
    assert response.status_code == 200 and bank.name == original
    response = client.post(url, data={"csrf_token": token(client.get(url)), "name": "Đổi tên ngân hàng", "subject": "Toán", "grade": "10", "topic": "Chủ đề", "description": "Mô tả"})
    assert response.status_code == 302 and bank.name == "Đổi tên ngân hàng" and bank.updated_at is not None
    assert client.get(bank_url(bank_ui, "shared", "/edit")).status_code == 403


def manual_data(csrf, kind, **extra):
    data = MultiDict({"csrf_token": csrf, "question_text": "Câu kiểm thử mới " + kind, "question_category": "Dạng tổng quát", "question_type": kind, "difficulty_level": "nhan_biet", "reviewed": "1", **extra})
    if kind == "single":
        data.setlist("option_text", ["A", "B", "C", "D"])
        data["correct_option"] = "0"
    elif kind == "true_false":
        data.setlist("option_text", ["Ý a", "Ý b", "Ý c", "Ý d"])
        data.setlist("correct_option", ["true", "false", "true", "false"])
    else:
        data.update({"short_answers": "0.5 | 1/2", "short_answer_mode": "numeric", "short_answer_tolerance": "0"})
    return data


@pytest.mark.parametrize("kind", ["single", "true_false", "short_answer"])
def test_general_manual_forms_save_without_research_node(bank_ui, kind):
    login(bank_ui)
    client, url = bank_ui.client, bank_url(bank_ui)
    response = client.post(url + "/questions/add", data=manual_data(token(client.get(url)), kind, scope="mine", page="1", per_page="50"))
    assert response.status_code == 302 and "scope=mine" in response.location and "per_page=50" in response.location
    saved = BankQuestion.query.filter_by(question_text="Câu kiểm thử mới " + kind).one()
    assert saved.curriculum_node_id is None and saved.question_type == kind
    detail = client.get(f"/api/question-banks/{saved.bank_id}/questions/{saved.id}").get_json()
    assert detail['question']['question_category'] == "Dạng tổng quát"
    assert len(saved.options) == (2 if kind == "short_answer" else 4)


def test_teacher_add_to_shared_creates_private_overlay(bank_ui):
    login(bank_ui)
    client, url = bank_ui.client, bank_url(bank_ui, "shared")
    data = manual_data(token(client.get(url)), "single", curriculum_node_id=str(bank_ui.data['nodes'][0]))
    assert client.post(url + "/questions/add", data=data).status_code == 302
    saved = BankQuestion.query.filter_by(question_text="Câu kiểm thử mới single").one()
    assert saved.scope == "private" and saved.private_owner_id == bank_ui.data['users']['teacher']
    common_id = bank_ui.data['questions']['common-0']
    assert client.post(f"/questions/{common_id}/toggle-answer", json={"option_index": 1}, headers={"X-CSRFToken": data['csrf_token']}).status_code == 403


def test_lazy_detail_and_quick_true_false_answer_preserve_permissions(bank_ui):
    login(bank_ui)
    client = bank_ui.client
    question_id = bank_ui.data['questions']['general-tf']
    bank_id = bank_ui.data['banks']['general']
    payload = client.get(f"/api/question-banks/{bank_id}/questions/{question_id}").get_json()
    assert payload['success'] and len(payload['question']['statements']) == 4 and payload['question']['can_edit']
    original = db.session.get(BankQuestion, question_id).options[0].is_correct
    csrf = token(client.get(bank_url(bank_ui)))
    response = client.post(f"/questions/{question_id}/toggle-answer", json={"option_index": 0, "is_correct": not original}, headers={"X-CSRFToken": csrf})
    assert response.status_code == 200 and response.get_json()['question']['can_edit']
    assert db.session.get(BankQuestion, question_id).options[0].is_correct is not original
    assert client.get(f"/api/question-banks/{bank_ui.data['banks']['shared']}/questions/{bank_ui.data['questions']['foreign-overlay']}").status_code == 403


def test_manual_classification_confirmation_has_current_fingerprint(bank_ui):
    login(bank_ui)
    client, url = bank_ui.client, bank_url(bank_ui, "research", "/classification")
    question_id = bank_ui.data['questions']['unclassified']
    response = client.post(url + "/bulk", data={"csrf_token": token(client.get(url)), "question_ids": str(question_id), "curriculum_node_id": str(bank_ui.data['nodes'][0]), "difficulty_level": "thong_hieu", "question_type": "single"})
    assert response.status_code == 302
    saved = db.session.get(BankQuestion, question_id)
    from services.question_classification_service import content_fingerprint
    assert saved.classification_status == "teacher_confirmed"
    assert json.loads(saved.classification_data)['content_fingerprint'] == content_fingerprint(saved.to_dict())


def test_suggestion_acceptance_rejects_stale_content(bank_ui):
    login(bank_ui)
    client, url = bank_ui.client, bank_url(bank_ui, "research", "/classification")
    ids = [str(bank_ui.data['questions'][key]) for key in ("suggested", "stale")]
    response = client.post(url + "/accept-suggestions", data=MultiDict([("csrf_token", token(client.get(url))), *(('question_ids', value) for value in ids)]))
    assert response.status_code == 302
    assert db.session.get(BankQuestion, int(ids[0])).classification_status == "teacher_confirmed"
    assert db.session.get(BankQuestion, int(ids[1])).classification_status == "suggested"


@pytest.mark.parametrize("content,filename", [(b'[42]', "labels.json"), (b'[{"question":[]}]', "labels.json"), (b'[{"question":{"options":[42]}}]', "labels.json"), (b'[{"expected_primary_code":[]}]', "labels.json"), (b'[{"scope":[]}]', "labels.json"), (b'{bad', "labels.json"), (b'{}', "labels.json"), (b'[]', "labels.txt"), (b' ' * (5 * 1024 * 1024 + 1), "labels.json")])
def test_evaluation_invalid_upload_returns_field_error_not_server_error(bank_ui, content, filename):
    login(bank_ui)
    client, url = bank_ui.client, bank_url(bank_ui, "research", "/classification/evaluation")
    response = client.post(url, data={"csrf_token": token(client.get(url)), "labels_file": (io.BytesIO(content), filename)}, content_type="multipart/form-data")
    assert response.status_code == 200 and 'role="alert"' in response.get_data(as_text=True)


def test_evaluation_export_is_blinded_and_empty_report_is_not_ready(bank_ui):
    login(bank_ui)
    client, url = bank_ui.client, bank_url(bank_ui, "research", "/classification/evaluation")
    packet = client.get(url + "/export").get_json()
    assert isinstance(packet, list)
    for row in packet:
        assert not any(key in row for key in ("prediction", "classification_data", "explanation"))
        assert all('is_correct' not in option for option in row.get('options', []))
    response = client.post(url, data={"csrf_token": token(client.get(url)), "labels_file": (io.BytesIO(b'[]'), "labels.json")}, content_type="multipart/form-data")
    assert response.status_code == 200 and "Chưa đạt" in response.get_data(as_text=True)


def test_catalog_teacher_read_only_admin_upsert_and_toggle(bank_ui):
    login(bank_ui)
    client = bank_ui.client
    response = client.get("/curriculum?grade=9&chapter=8")
    assert client.post("/curriculum", data={"csrf_token": token(response), "action": "add_single"}).status_code == 403
    client.get("/logout")
    from flask import g
    g.pop("_login_user", None)
    login(bank_ui, "admin")
    from services.curriculum_data import RETAINED_LESSON_NAME
    payload = {"csrf_token": token(client.get("/curriculum")), "action": "add_single", "grade": "9", "chapter_code": "8", "chapter_name": "Xác suất", "lesson_code": "i", "lesson_name": RETAINED_LESSON_NAME, "category_code": "1", "category_name": "Tên dạng đã cập nhật", "catalog_version": "math9-v1"}
    assert client.post("/curriculum", data=payload).status_code == 302
    node = db.session.get(CurriculumNode, bank_ui.data['nodes'][0])
    assert node.category_name == "Tên dạng đã cập nhật"
    response = client.post(f"/curriculum/{node.id}/toggle", data={"csrf_token": payload['csrf_token']})
    assert response.status_code == 302 and "inactive=1" in response.location
    assert not node.is_active


def test_delete_targets_only_authorized_synthetic_bank(bank_ui):
    login(bank_ui)
    client, url = bank_ui.client, bank_url(bank_ui, "empty")
    csrf = token(client.get("/question-banks"))
    assert client.post(bank_url(bank_ui, "shared", "/delete"), data={"csrf_token": csrf}).status_code == 403
    response = client.post(url + "/delete", data={"csrf_token": csrf})
    assert response.status_code == 302 and db.session.get(QuestionBank, bank_ui.data['banks']['empty']) is None
    assert Path(app.root_path).is_relative_to(Path(_storage.name))
