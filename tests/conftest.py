"""
Фикстуры для тестов
"""
from app import create_app, db as _db
import os
import sys
import pytest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope='session')
def app():
    """Создает экземпляр приложения для тестов"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
    os.environ['SECRET_KEY'] = 'test-secret-key'

    application = create_app('development')
    application.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
    })

    with application.app_context():
        _db.create_all()

    yield application

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='function')
def db(app):
    """Предоставляет чистую БД для каждого теста"""
    with app.app_context():
        yield _db


@pytest.fixture(scope='function')
def client(app):
    """HTTP-клиент для тестов"""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """CLI runner"""
    return app.test_cli_runner()
