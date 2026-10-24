"""Account form failures are recoverable, transactional and isolated from real data."""
from __future__ import annotations

import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import g
from sqlalchemy.exc import IntegrityError

from scripts.preview_ui_phase4 import isolate_environment, isolate_storage

_storage = TemporaryDirectory(prefix='linhedu-phase8-user-validation-')
isolate_environment(_storage.name)
from app import app
from database import db
from models import User


def csrf(response):
    html = response.get_data(as_text=True)
    match = re.search(r'name="csrf-token"[^>]*content="([^"]+)"', html) or re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    assert match
    return match.group(1)


@pytest.fixture
def workspace():
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
    isolate_storage(app, _storage.name)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    app.jinja_env.cache.clear()
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        rows = {}
        for name, role in [('admin', 'admin'), ('first', 'student'), ('second', 'teacher')]:
            row = User(username=name, fullname='Hồ sơ '+name, user_code='CODE-'+name,
                       role=role, phone='0900000000', position='Vị trí cũ', is_active=True)
            row.set_password('Synthetic123!')
            db.session.add(row)
            rows[name] = row
        db.session.commit()
        client = app.test_client()
        response = client.get('/login')
        assert client.post('/login', data={'csrf_token': csrf(response), 'username': 'admin',
                                          'password': 'Synthetic123!'}).status_code == 302
        g.pop('_login_user', None)
        yield SimpleNamespace(client=client, users=rows)
        db.session.remove()
        db.drop_all()


def fields(**overrides):
    values = {'username': 'new-name', 'fullname': 'Họ tên mới', 'user_code': 'NEW-CODE',
              'phone': '0911111111', 'position': 'Lớp 9A', 'role': 'student', 'is_active': '1'}
    values.update(overrides)
    return values


def post(workspace, path='/users', values=None, **kwargs):
    values = dict(values or fields())
    values['csrf_token'] = csrf(workspace.client.get('/profile'))
    return workspace.client.post(path, data=values, **kwargs)


def snapshot(user):
    return tuple(getattr(user, name) for name in (
        'username', 'fullname', 'user_code', 'role', 'phone', 'position', 'is_active', 'password_hash'))


@pytest.mark.parametrize(('field', 'value', 'label'), [
    ('username', '  ', 'Tên đăng nhập'), ('fullname', '', 'Họ và tên'),
    ('user_code', '\t', 'Mã người dùng'),
    ('username', 'x'*81, '80'), ('fullname', 'x'*101, '100'),
    ('user_code', 'x'*21, '20'), ('phone', 'x'*21, '20'), ('position', 'x'*101, '100'),
    ('username', ' second ', 'Tên đăng nhập đã được sử dụng'),
    ('user_code', ' CODE-second ', 'Mã người dùng đã được sử dụng'),
])
def test_invalid_creation_redirects_to_right_tab_without_partial_user(workspace, field, value, label):
    before = User.query.count()
    response = post(workspace, values=fields(role='teacher', **{field: value}), follow_redirects=True)
    assert response.status_code == 200
    assert response.request.path == '/users/teachers'
    assert label in response.get_data(as_text=True)
    assert 'flash-danger' in response.get_data(as_text=True)
    assert User.query.count() == before
    # The transaction/session remains usable after validation failure.
    assert post(workspace, values=fields()).status_code == 302
    assert User.query.filter_by(username='new-name').one()


@pytest.mark.parametrize(('field', 'value', 'label'), [
    ('username', ' ', 'Tên đăng nhập'), ('fullname', '', 'Họ và tên'),
    ('user_code', '\n', 'Mã người dùng'),
    ('username', 'x'*81, '80'), ('fullname', 'x'*101, '100'),
    ('user_code', 'x'*21, '20'), ('phone', 'x'*21, '20'), ('position', 'x'*101, '100'),
    ('username', 'second', 'Tên đăng nhập đã được sử dụng'),
    ('user_code', 'CODE-second', 'Mã người dùng đã được sử dụng'),
])
def test_invalid_edit_keeps_submitted_values_and_leaves_database_unchanged(workspace, field, value, label):
    user = workspace.users['first']
    before = snapshot(user)
    values = fields(fullname='Bản nhập cần giữ', phone='0987654321', role='teacher')
    values[field] = value
    values.pop('is_active')
    response = post(workspace, f'/users/{user.id}/edit', values)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert label in html and 'flash-danger' in html
    assert f'value="{values["phone"].strip()}"' in html
    if field != 'fullname':
        assert 'Bản nhập cần giữ' in html
    assert 'value="teacher" selected' in html
    assert 'name="is_active" value="1" checked' not in html
    assert 'password_hash' not in html and 'Synthetic123!' not in html
    db.session.refresh(user)
    assert snapshot(user) == before


def test_missing_fields_are_validation_errors_not_bad_request_or_500(workspace):
    response = post(workspace, values={'role': 'student'}, follow_redirects=True)
    assert response.status_code == 200
    assert 'không được để trống' in response.get_data(as_text=True)
    assert User.query.count() == 3


def test_valid_creation_trims_fields_preserves_default_password_and_active_state(workspace):
    response = post(workspace, values=fields(username='  normalized  ', fullname='  Nguyễn An  ',
        user_code='  TRIM-CODE  ', phone='  0901234567  ', position='  Lớp 9A  ', role='teacher'))
    assert response.status_code == 302 and response.location.endswith('/users/teachers')
    row = User.query.filter_by(username='normalized').one()
    assert (row.fullname, row.user_code, row.phone, row.position, row.role, row.is_active) == (
        'Nguyễn An', 'TRIM-CODE', '0901234567', 'Lớp 9A', 'teacher', True)
    assert row.check_password('123456')


def test_custom_password_is_not_trimmed_or_replaced(workspace):
    assert post(workspace, values=fields(password='  valid password  ')).status_code == 302
    row = User.query.filter_by(username='new-name').one()
    assert row.check_password('  valid password  ') and not row.check_password('valid password')


def test_self_identity_edit_is_allowed_and_canonical_role_active_fields_still_work(workspace):
    row = workspace.users['first']
    old_password = row.password_hash
    values = fields(username=' first ', user_code=' CODE-first ', role='teacher', fullname='  Nguyễn Bình  ')
    values.pop('is_active')
    response = post(workspace, f'/users/{row.id}/edit', values)
    assert response.status_code == 302 and response.location.endswith('/users/teachers')
    db.session.refresh(row)
    assert (row.username, row.user_code, row.fullname, row.role, row.is_active, row.password_hash) == (
        'first', 'CODE-first', 'Nguyễn Bình', 'teacher', False, old_password)


@pytest.mark.parametrize('editing', [False, True])
def test_integrity_race_rolls_back_and_allows_retry_without_sql_details(workspace, editing):
    row = workspace.users['first']
    before = snapshot(row)
    path = f'/users/{row.id}/edit' if editing else '/users'
    payload = fields(fullname='Bản nhập giữ sau xung đột')
    error = IntegrityError('synthetic sql must never appear', {'password': 'private-value'}, Exception('constraint race'))
    with patch.object(db.session, 'commit', side_effect=error), patch.object(db.session, 'rollback', wraps=db.session.rollback) as rollback:
        response = post(workspace, path, payload)
        rollback.assert_called_once()
    if editing:
        assert response.status_code == 200 and 'Bản nhập giữ sau xung đột' in response.get_data(as_text=True)
    else:
        assert response.status_code == 302
        response = workspace.client.get(response.location)
    html = response.get_data(as_text=True)
    assert 'Không thể lưu tài khoản' in html
    assert 'synthetic sql' not in html and 'private-value' not in html and 'constraint race' not in html
    db.session.refresh(row)
    assert snapshot(row) == before and User.query.count() == 3
    assert post(workspace, path, payload).status_code == 302


def test_protected_admin_and_unsupported_role_remain_rejected(workspace):
    admin = workspace.users['admin']
    before = snapshot(admin)
    assert post(workspace, f'/users/{admin.id}/edit', fields(role='student')).status_code == 302
    assert snapshot(admin) == before
    row = workspace.users['first']
    before = snapshot(row)
    assert post(workspace, f'/users/{row.id}/edit', fields(role='admin')).status_code == 302
    assert snapshot(row) == before
    assert post(workspace, values=fields(role='admin')).status_code == 302
    assert User.query.count() == 3


def test_csrf_and_admin_only_permissions_are_unchanged(workspace):
    assert workspace.client.post('/users', data=fields()).status_code == 400
    workspace.client.get('/logout'); g.pop('_login_user', None)
    response = workspace.client.get('/login')
    workspace.client.post('/login', data={'csrf_token': csrf(response), 'username': 'first', 'password': 'Synthetic123!'})
    g.pop('_login_user', None)
    assert post(workspace).status_code == 302
    assert User.query.count() == 3
