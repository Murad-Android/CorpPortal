"""
Тесты моделей
"""
from werkzeug.security import generate_password_hash, check_password_hash


def test_password_hashing():
    """Хеширование паролей работает"""
    password = 'test_password_123'
    hashed = generate_password_hash(password)

    assert hashed != password
    assert check_password_hash(hashed, password)
    assert not check_password_hash(hashed, 'wrong_password')


def test_user_model_exists(app):
    """Модель User доступна"""
    with app.app_context():
        from app.models import User
        assert User is not None


def test_role_model_exists(app):
    """Модель Role доступна"""
    with app.app_context():
        from app.models import Role
        assert Role is not None


def test_admin_user_exists(app, db):
    """Пользователь admin создан при инициализации"""
    with app.app_context():
        from app.models import User
        admin = User.query.filter_by(username='admin').first()
        assert admin is not None
        assert admin.username == 'admin'


def test_admin_role_exists(app, db):
    """Роль admin создана"""
    with app.app_context():
        from app.models import Role
        role = Role.query.filter_by(name='admin').first()
        assert role is not None


def test_role_has_permissions(app, db):
    """Роль admin имеет права"""
    with app.app_context():
        from app.models import Role
        role = Role.query.filter_by(name='admin').first()
        assert role is not None
        assert role.permissions is not None
