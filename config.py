"""
Конфигурация приложения
"""
import os
import configparser
from datetime import timedelta


def _get_max_upload_size():
    """Читает лимит загрузки из server_config.ini"""
    default = 100  # МБ по умолчанию
    try:
        cfg = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'server_config.ini')
        if os.path.exists(config_path):
            cfg.read(config_path, encoding='utf-8')
            return cfg.getint('app', 'max_upload_size_mb', fallback=default)
    except Exception:
        pass
    return default


class Config:
    """Базовая конфигурация"""
    SECRET_KEY = os.environ.get(
        'SECRET_KEY') or 'super-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL') or 'sqlite:///portal.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Сессии
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # CSRF — время жизни токена (24 часа, чтобы не протухал при долгом просмотре)
    WTF_CSRF_TIME_LIMIT = 86400  # секунд (24 часа)

    # Загрузка файлов
    UPLOAD_FOLDER = 'static/uploads'
    STAFF_PHOTO_FOLDER = 'static/staff_photo'
    MAX_CONTENT_LENGTH = _get_max_upload_size() * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'xlsx'}

    # Babel
    BABEL_DEFAULT_LOCALE = 'ru'


class DevelopmentConfig(Config):
    """Конфигурация для разработки"""
    DEBUG = True


class ProductionConfig(Config):
    """Конфигурация для продакшена"""
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
