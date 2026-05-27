"""
Инициализация Flask приложения
"""
from config import config
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите в систему'
login_manager.login_message_category = 'warning'


def _auto_migrate(db):
    """Автоматически добавляет недостающие колонки в существующие таблицы."""
    import sqlite3
    from sqlalchemy import inspect as sa_inspect

    engine = db.engine
    inspector = sa_inspect(engine)

    for table_name in inspector.get_table_names():
        # Получаем существующие колонки в БД
        existing_columns = {col['name']
                            for col in inspector.get_columns(table_name)}

        # Получаем колонки из модели
        if table_name in db.metadata.tables:
            model_table = db.metadata.tables[table_name]
            for column in model_table.columns:
                if column.name not in existing_columns:
                    # Определяем тип колонки для SQLite
                    col_type = str(column.type)
                    nullable = "NULL" if column.nullable else "NOT NULL"
                    default = ""
                    if column.default is not None:
                        default_val = column.default.arg
                        if isinstance(default_val, str):
                            default = f"DEFAULT '{default_val}'"
                        elif default_val is not None:
                            default = f"DEFAULT {default_val}"

                    sql = f'ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type} {default}'
                    try:
                        db.session.execute(db.text(sql))
                        db.session.commit()
                        print(
                            f'[MIGRATE] Добавлена колонка: {table_name}.{column.name} ({col_type})')
                    except Exception as e:
                        db.session.rollback()


def create_app(config_name='default'):
    """Фабрика приложения"""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Регистрация blueprints
    from app.blueprints.main import main_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.staff import staff_bp
    from app.blueprints.news import news_bp
    from app.blueprints.vacancies import vacancies_bp
    from app.blueprints.security import security_bp
    from app.blueprints.requests import requests_bp
    from app.blueprints.tables import tables_bp
    from app.blueprints.profile import profile_bp
    from app.blueprints.messenger import messenger_bp
    from app.blueprints.surveys import surveys_bp
    from app.blueprints.tests import tests_bp
    from app.blueprints.vacations import vacations_bp
    from app.blueprints.password_vault import vault_bp
    from app.blueprints.testing_services import testing_bp
    from app.blueprints.appearance import appearance_bp
    from app.blueprints.diagrams import diagrams_bp
    from app.blueprints.bugtracker import bugtracker_bp
    from app.blueprints.server_update import server_update_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(news_bp, url_prefix='/news')
    app.register_blueprint(vacancies_bp, url_prefix='/vacancies')
    app.register_blueprint(security_bp, url_prefix='/security')
    app.register_blueprint(requests_bp, url_prefix='/requests')
    app.register_blueprint(tables_bp, url_prefix='/tables')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(messenger_bp, url_prefix='/messenger')
    app.register_blueprint(surveys_bp, url_prefix='/surveys')
    app.register_blueprint(tests_bp, url_prefix='/tests')
    app.register_blueprint(vacations_bp, url_prefix='/vacations')
    app.register_blueprint(vault_bp, url_prefix='/vault')
    app.register_blueprint(testing_bp, url_prefix='/testing')
    app.register_blueprint(appearance_bp, url_prefix='/appearance')
    app.register_blueprint(diagrams_bp, url_prefix='/diagrams')
    app.register_blueprint(bugtracker_bp, url_prefix='/bugs')
    app.register_blueprint(server_update_bp, url_prefix='/admin/updates')

    # Обработчики ошибок
    from app.blueprints.errors import errors_bp
    app.register_blueprint(errors_bp)

    # Context processor для меню
    @app.context_processor
    def inject_menu():
        """Добавляет функцию получения меню в шаблоны"""
        def get_menu_items():
            from app.models import MenuItem
            MenuItem.init_default()
            return {
                'visible': MenuItem.get_visible(),
                'hidden': MenuItem.get_hidden()
            }
        return {'get_menu_items': get_menu_items}

    # Context processor для настроек внешнего вида
    @app.context_processor
    def inject_appearance():
        """Добавляет настройки внешнего вида в шаблоны"""
        from datetime import datetime

        def get_site_appearance():
            from app.models import SiteAppearance
            return SiteAppearance.get_settings()

        def get_active_decorations():
            from app.models import SiteDecoration
            decorations = SiteDecoration.query.filter_by(is_enabled=True).all()
            return [d for d in decorations if d.is_active_now()]

        return {
            'get_site_appearance': get_site_appearance,
            'get_active_decorations': get_active_decorations,
            'now': datetime.now
        }

    # Context processor для приветственной анимации
    @app.context_processor
    def inject_greeting():
        """Добавляет данные приветственной анимации в шаблоны"""
        from flask import session
        from flask_login import current_user
        from datetime import datetime

        def get_greeting_data():
            """Возвращает данные для приветствия или None если не нужно показывать"""
            if not current_user.is_authenticated:
                return None
            if not session.pop('show_greeting', False):
                return None

            from app.models import Settings
            now = datetime.now()
            current_hour = now.hour

            # Получаем настройки временных диапазонов
            morning_start = int(Settings.get('greeting_morning_start', '6'))
            morning_end = int(Settings.get('greeting_morning_end', '12'))
            afternoon_start = int(Settings.get(
                'greeting_afternoon_start', '12'))
            afternoon_end = int(Settings.get('greeting_afternoon_end', '18'))
            evening_start = int(Settings.get('greeting_evening_start', '18'))
            evening_end = int(Settings.get('greeting_evening_end', '6'))

            # Определяем период дня
            greeting_type = None
            if morning_start <= current_hour < morning_end:
                if Settings.get('greeting_morning_enabled', 'true') == 'true':
                    greeting_type = 'morning'
            elif afternoon_start <= current_hour < afternoon_end:
                if Settings.get('greeting_afternoon_enabled', 'true') == 'true':
                    greeting_type = 'afternoon'
            else:
                # Вечер/ночь - проверяем с учётом перехода через полночь
                if evening_start <= current_hour or current_hour < evening_end:
                    if Settings.get('greeting_evening_enabled', 'true') == 'true':
                        greeting_type = 'evening'

            if not greeting_type:
                return None

            firstname = current_user.firstname or current_user.username

            greetings = {
                'morning': {
                    'text': f'Доброе утро, {firstname}!',
                    'type': 'morning'
                },
                'afternoon': {
                    'text': f'Добрый день, {firstname}!',
                    'type': 'afternoon'
                },
                'evening': {
                    'text': f'Хорошего вечера, {firstname}!',
                    'type': 'evening'
                }
            }

            return greetings.get(greeting_type)

        return {'get_greeting_data': get_greeting_data}

    # Кастомный фильтр для фото пользователя
    @app.template_filter('user_photo')
    def user_photo_filter(photo):
        """Возвращает путь к фото пользователя или дефолтный аватар"""
        if photo and photo != 'image/static_avatar.png':
            return f'staff_photo/{photo}'
        return 'image/static_avatar.png'

    # Фильтр для Markdown
    @app.template_filter('markdown')
    def markdown_filter(text):
        """Конвертирует Markdown в HTML"""
        if not text:
            return ''
        try:
            import markdown
            # Расширения для списков, таблиц и т.д.
            return markdown.markdown(text, extensions=['nl2br', 'tables', 'fenced_code'])
        except ImportError:
            # Если markdown не установлен - простая замена переносов
            import re
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
            text = re.sub(r'^- (.+)$', r'<li>\1</li>',
                          text, flags=re.MULTILINE)
            text = text.replace('\n', '<br>')
            return text

    # Создание таблиц и начальных данных
    with app.app_context():
        db.create_all()

        # Автомиграция: добавляем недостающие колонки в существующие таблицы
        _auto_migrate(db)

        from app.services.init_service import init_default_data
        init_default_data()

    # Инициализация планировщика (только в главном процессе)
    # Для uvicorn с несколькими воркерами - запускаем только если это главный процесс
    is_main_process = (
        os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or  # Flask dev server
        not app.debug  # Production - проверяем ниже
    )

    # Для uvicorn проверяем, что это не дочерний воркер
    if is_main_process and os.environ.get('_SCHEDULER_STARTED') != '1':
        os.environ['_SCHEDULER_STARTED'] = '1'
        try:
            from app.services.scheduler import init_scheduler
            init_scheduler(app)
        except ImportError:
            print(
                '[WARNING] APScheduler не установлен. Автоматическая синхронизация LDAP отключена.')

    return app
