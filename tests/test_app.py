"""
Тесты инициализации приложения
"""


def test_app_creates(app):
    """Приложение создается без ошибок"""
    assert app is not None


def test_app_is_testing(app):
    """Флаг TESTING установлен"""
    assert app.config['TESTING'] is True


def test_csrf_disabled_in_tests(app):
    """CSRF отключен в тестах"""
    assert app.config['WTF_CSRF_ENABLED'] is False


def test_secret_key_set(app):
    """Секретный ключ задан"""
    assert app.config['SECRET_KEY'] is not None
    assert len(app.config['SECRET_KEY']) > 0
