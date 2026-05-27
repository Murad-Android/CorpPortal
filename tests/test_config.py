"""
Тесты конфигурации
"""
from config import Config, DevelopmentConfig, ProductionConfig
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_base_config():
    """Базовая конфигурация содержит обязательные поля"""
    assert Config.SECRET_KEY is not None
    assert Config.SQLALCHEMY_DATABASE_URI is not None
    assert Config.SQLALCHEMY_TRACK_MODIFICATIONS is False


def test_development_config():
    """Конфигурация разработки включает DEBUG"""
    assert DevelopmentConfig.DEBUG is True


def test_production_config():
    """Продакшен конфигурация выключает DEBUG"""
    assert ProductionConfig.DEBUG is False


def test_upload_settings():
    """Настройки загрузки файлов заданы"""
    assert Config.UPLOAD_FOLDER is not None
    assert Config.MAX_CONTENT_LENGTH > 0
    assert 'png' in Config.ALLOWED_EXTENSIONS
    assert 'pdf' in Config.ALLOWED_EXTENSIONS


def test_session_lifetime():
    """Время жизни сессии задано"""
    assert Config.PERMANENT_SESSION_LIFETIME is not None
    assert Config.PERMANENT_SESSION_LIFETIME.total_seconds() > 0
