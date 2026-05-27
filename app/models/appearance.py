"""
Модели для настройки внешнего вида сайта
"""
from app import db
from datetime import datetime
import json


class SiteAppearance(db.Model):
    """Настройки внешнего вида сайта"""
    __tablename__ = 'site_appearance'

    id = db.Column(db.Integer, primary_key=True)

    # Название сайта
    site_name = db.Column(db.String(255), default='Корпоративный портал')

    # Цвета
    primary_color = db.Column(db.String(7), default='#0078D7')  # Основной цвет
    secondary_color = db.Column(
        db.String(7), default='#005a9e')  # Вторичный цвет

    # Часовой пояс
    timezone = db.Column(db.String(50), default='Europe/Moscow')

    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_settings():
        """Получить настройки (создать если не существуют)"""
        settings = SiteAppearance.query.first()
        if not settings:
            settings = SiteAppearance()
            db.session.add(settings)
            db.session.commit()
        return settings


class SiteDecoration(db.Model):
    """Украшения сайта"""
    __tablename__ = 'site_decorations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Название украшения
    # garland, newyear_balls, snow, etc.
    decoration_type = db.Column(db.String(50), nullable=False)

    # Период активности
    start_date = db.Column(db.Date)  # Дата начала показа
    end_date = db.Column(db.Date)  # Дата окончания показа

    # Или всегда активно
    is_always_active = db.Column(db.Boolean, default=False)
    is_enabled = db.Column(db.Boolean, default=True)

    # Дополнительные настройки (JSON)
    settings = db.Column(db.Text, default='{}')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_settings(self):
        try:
            return json.loads(self.settings) if self.settings else {}
        except:
            return {}

    def set_settings(self, data):
        self.settings = json.dumps(data, ensure_ascii=False)

    def is_active_now(self):
        """Проверить, активно ли украшение сейчас"""
        if not self.is_enabled:
            return False
        if self.is_always_active:
            return True

        today = datetime.now().date()
        if self.start_date and self.end_date:
            return self.start_date <= today <= self.end_date
        return False

    # Типы украшений
    DECORATION_TYPES = {
        'garland': {
            'name': 'Гирлянда (мигающая)',
            'description': 'Классическая мигающая гирлянда в верхней части сайта',
            'icon': 'lightbulb'
        },
        'newyear_balls': {
            'name': 'Новогодние шары (Яндекс)',
            'description': 'Интерактивные новогодние шары с анимацией',
            'icon': 'circle'
        },
        'snow': {
            'name': 'Падающий снег',
            'description': 'Анимация падающего снега',
            'icon': 'snowflake'
        },
        'hearts': {
            'name': 'Сердечки',
            'description': 'Летающие сердечки (День Святого Валентина)',
            'icon': 'heart'
        },
        'confetti': {
            'name': 'Конфетти',
            'description': 'Праздничное конфетти',
            'icon': 'gift'
        }
    }
