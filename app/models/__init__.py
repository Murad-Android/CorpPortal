"""
Модели базы данных
"""
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
import secrets
import string


def get_photo_path(photo):
    """Возвращает путь к фото пользователя для API"""
    if photo and photo != 'image/static_avatar.png':
        return f'staff_photo/{photo}'
    return 'image/static_avatar.png'


class Role(db.Model):
    """Модель роли пользователя"""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100))
    description = db.Column(db.String(255))
    permissions = db.Column(db.Text, default='{}')
    # Системная роль (нельзя удалить)
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='role', lazy='dynamic')

    # Все доступные права в системе
    AVAILABLE_PERMISSIONS = {
        # Контент
        'news': {'name': 'Новости', 'description': 'Создание и редактирование новостей', 'group': 'Контент'},
        'vacancies': {'name': 'Вакансии', 'description': 'Управление вакансиями и откликами', 'group': 'Контент'},
        'surveys': {'name': 'Опросы', 'description': 'Создание и управление опросами', 'group': 'Контент'},
        'tests': {'name': 'Тесты', 'description': 'Создание и управление тестами', 'group': 'Контент'},
        'security_articles': {'name': 'Центр безопасности', 'description': 'Статьи центра безопасности', 'group': 'Контент'},
        'comments_moderate': {'name': 'Модерация комментариев', 'description': 'Удаление любых комментариев к новостям', 'group': 'Контент'},

        # Заявки
        'passes': {'name': 'Пропуска', 'description': 'Обработка заявок на пропуска', 'group': 'Заявки'},
        'orders': {'name': 'Заказы товаров', 'description': 'Обработка заявок на заказ товаров', 'group': 'Заявки'},
        'vacations': {'name': 'Отпуска', 'description': 'Управление заявками на отпуск (HR)', 'group': 'Заявки'},

        # Пользователи
        'users_view': {'name': 'Просмотр пользователей', 'description': 'Просмотр списка пользователей в админке', 'group': 'Пользователи'},
        'users_create': {'name': 'Создание пользователей', 'description': 'Создание новых пользователей', 'group': 'Пользователи'},
        'users_edit': {'name': 'Редактирование пользователей', 'description': 'Редактирование данных пользователей', 'group': 'Пользователи'},
        'users_delete': {'name': 'Удаление пользователей', 'description': 'Удаление пользователей из системы', 'group': 'Пользователи'},
        'roles_manage': {'name': 'Управление ролями', 'description': 'Создание и редактирование ролей', 'group': 'Пользователи'},

        # Безопасность
        'password_vault_view': {'name': 'Просмотр хранилища паролей', 'description': 'Доступ к хранилищу паролей', 'group': 'Безопасность'},
        'password_vault_create': {'name': 'Создание записей паролей', 'description': 'Добавление новых паролей в хранилище', 'group': 'Безопасность'},
        'password_vault_edit': {'name': 'Редактирование паролей', 'description': 'Изменение записей в хранилище', 'group': 'Безопасность'},
        'password_vault_delete': {'name': 'Удаление паролей', 'description': 'Удаление записей из хранилища', 'group': 'Безопасность'},
        'password_vault_share': {'name': 'Предоставление доступа', 'description': 'Предоставление доступа к паролям другим пользователям', 'group': 'Безопасность'},

        # Сервисы тестирования
        'testing_services_view': {'name': 'Просмотр сервисов', 'description': 'Просмотр списка сервисов тестирования', 'group': 'Тестирование'},
        'testing_services_create': {'name': 'Создание сервисов', 'description': 'Добавление новых сервисов тестирования', 'group': 'Тестирование'},
        'testing_services_edit': {'name': 'Редактирование сервисов', 'description': 'Изменение сервисов тестирования', 'group': 'Тестирование'},
        'testing_services_delete': {'name': 'Удаление сервисов', 'description': 'Удаление сервисов тестирования', 'group': 'Тестирование'},
        'testing_services_toggle': {'name': 'Вкл/Выкл сервисов', 'description': 'Включение и выключение сервисов', 'group': 'Тестирование'},

        # Настройки системы
        'settings_general': {'name': 'Общие настройки', 'description': 'Настройки портала', 'group': 'Система'},
        'settings_ldap': {'name': 'Настройки LDAP', 'description': 'Конфигурация LDAP/AD', 'group': 'Система'},
        'settings_smtp': {'name': 'Настройки SMTP', 'description': 'Конфигурация почты', 'group': 'Система'},
        'settings_menu': {'name': 'Настройки меню', 'description': 'Конфигурация меню портала', 'group': 'Система'},
        'logs_view': {'name': 'Просмотр логов', 'description': 'Просмотр журнала действий', 'group': 'Система'},

        # Полный доступ
        'all': {'name': 'Полный доступ', 'description': 'Все права администратора', 'group': 'Специальные'},
    }

    def get_permissions(self):
        return json.loads(self.permissions) if self.permissions else {}

    def set_permissions(self, perms):
        self.permissions = json.dumps(perms)

    def has_permission(self, perm):
        perms = self.get_permissions()
        return perms.get(perm, False) or perms.get('all', False)

    def get_permissions_list(self):
        """Возвращает список активных прав"""
        perms = self.get_permissions()
        return [k for k, v in perms.items() if v]

    @staticmethod
    def get_permissions_grouped():
        """Возвращает права сгруппированные по категориям"""
        groups = {}
        for perm_key, perm_data in Role.AVAILABLE_PERMISSIONS.items():
            group = perm_data['group']
            if group not in groups:
                groups[group] = []
            groups[group].append({
                'key': perm_key,
                'name': perm_data['name'],
                'description': perm_data['description']
            })
        return groups

    @staticmethod
    def get_default_roles():
        return [
            {'name': 'admin', 'display_name': 'Администратор', 'is_system': True,
             'description': 'Полный доступ ко всем функциям',
             'permissions': {'all': True}},
            {'name': 'hr', 'display_name': 'HR-менеджер', 'is_system': True,
             'description': 'Управление персоналом, новостями, вакансиями',
             'permissions': {'news': True, 'vacancies': True, 'surveys': True, 'tests': True, 'vacations': True, 'users_view': True}},
            {'name': 'secretary', 'display_name': 'Секретарь', 'is_system': True,
             'description': 'Обработка заявок на пропуска и заказы',
             'permissions': {'passes': True, 'orders': True, 'users_view': True}},
            {'name': 'user', 'display_name': 'Пользователь', 'is_system': True,
             'description': 'Базовый доступ к порталу',
             'permissions': {}},
        ]


class User(UserMixin, db.Model):
    """Модель пользователя системы"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True,
                         nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    is_active = db.Column(db.Boolean, default=True)
    is_ldap_user = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Данные сотрудника (встроены в пользователя)
    firstname = db.Column(db.String(100))
    lastname = db.Column(db.String(100))
    middlename = db.Column(db.String(100))
    position = db.Column(db.String(200))
    department = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    internal_phone = db.Column(db.String(20))
    location = db.Column(db.String(200))
    birthday = db.Column(db.Date)
    hire_date = db.Column(db.Date)
    photo = db.Column(db.String(255), default='image/static_avatar.png')

    # Статус сотрудника: working, vacation, fired
    employment_status = db.Column(db.String(20), default='working')

    # Руководитель
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    manager = db.relationship(
        'User', remote_side=[id], backref='subordinates', foreign_keys=[manager_id])

    # Уведомления
    notifications = db.relationship('Notification', backref='user',
                                    lazy='dynamic', cascade='all, delete-orphan')

    @property
    def is_admin(self):
        return self.role and self.role.name == 'admin'

    @property
    def full_name(self):
        parts = []
        if self.lastname:
            parts.append(self.lastname)
        if self.firstname:
            parts.append(self.firstname)
        if self.middlename:
            parts.append(self.middlename)
        return ' '.join(parts) if parts else self.username

    @property
    def short_name(self):
        if not self.lastname:
            return self.username
        result = self.lastname
        if self.firstname:
            result += f' {self.firstname[0]}.'
        if self.middlename:
            result += f'{self.middlename[0]}.'
        return result

    @property
    def status_display(self):
        """Отображаемый статус сотрудника"""
        statuses = {
            'working': 'Работает',
            'vacation': 'В отпуске',
            'fired': 'Уволен'
        }
        return statuses.get(self.employment_status, 'Работает')

    @property
    def status_color(self):
        """Цвет статуса"""
        colors = {
            'working': 'green',
            'vacation': 'blue',
            'fired': 'red'
        }
        return colors.get(self.employment_status, 'gray')

    def has_permission(self, perm):
        if not self.role:
            return False
        return self.role.has_permission(perm)

    def can_access_admin(self):
        """Проверка доступа к админ-панели"""
        if not self.role:
            return False
        perms = self.role.get_permissions()
        # Доступ есть если есть хотя бы одно право из админки
        admin_perms = ['all', 'news', 'vacancies', 'surveys', 'tests', 'security_articles',
                       'passes', 'orders', 'vacations', 'users_view', 'users_create',
                       'users_edit', 'roles_manage', 'settings_general', 'settings_ldap',
                       'settings_smtp', 'settings_menu', 'logs_view']
        return any(perms.get(p) for p in admin_perms)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def unread_notifications_count(self):
        return self.notifications.filter_by(is_read=False).count()

    @staticmethod
    def generate_password(length=12):
        """Генерация безопасного пароля"""
        lower = string.ascii_lowercase
        upper = string.ascii_uppercase
        digits = string.digits
        password = [
            secrets.choice(lower),
            secrets.choice(upper),
            secrets.choice(digits),
        ]
        all_chars = lower + upper + digits
        password += [secrets.choice(all_chars) for _ in range(length - 3)]
        secrets.SystemRandom().shuffle(password)
        return ''.join(password)

    def __repr__(self):
        return f'<User {self.username}>'


class Notification(db.Model):
    """Модель уведомления"""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text)
    link = db.Column(db.String(255))
    icon = db.Column(db.String(50), default='bell')
    # info, success, warning, error
    type = db.Column(db.String(20), default='info')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def create(user_id, title, message=None, link=None, icon='bell', type='info'):
        notif = Notification(
            user_id=user_id, title=title, message=message,
            link=link, icon=icon, type=type
        )
        db.session.add(notif)
        db.session.commit()
        return notif


class News(db.Model):
    """Модель новости"""
    __tablename__ = 'news'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)
    short_description = db.Column(db.String(500))
    image = db.Column(db.String(255))
    is_published = db.Column(db.Boolean, default=True)
    is_pinned = db.Column(db.Boolean, default=False)
    # Разрешены ли комментарии
    comments_enabled = db.Column(db.Boolean, default=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = db.relationship('User', backref='news')
    comments = db.relationship('NewsComment', backref='news', lazy='dynamic',
                               cascade='all, delete-orphan')

    def get_comments_count(self):
        return self.comments.filter_by(is_deleted=False).count()

    def get_root_comments(self):
        """Получить комментарии верхнего уровня"""
        return self.comments.filter_by(parent_id=None, is_deleted=False).order_by(
            NewsComment.created_at.desc()).all()


class NewsComment(db.Model):
    """Комментарий к новости"""
    __tablename__ = 'news_comments'

    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey('news.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey(
        'news_comments.id'))  # Для ответов

    content = db.Column(db.Text, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='news_comments')
    replies = db.relationship('NewsComment', backref=db.backref('parent', remote_side=[id]),
                              lazy='dynamic')

    def get_replies(self):
        """Получить ответы на комментарий"""
        return self.replies.filter_by(is_deleted=False).order_by(NewsComment.created_at.asc()).all()

    def can_delete(self, user):
        """Проверка права на удаление"""
        if not user:
            return False
        # Автор комментария
        if self.user_id == user.id:
            return True
        # Админ или HR или право на модерацию комментариев
        if user.has_permission('all') or user.has_permission('news') or user.has_permission('comments_moderate'):
            return True
        return False


class Vacancy(db.Model):
    """Модель вакансии"""
    __tablename__ = 'vacancies'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(200))
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)
    conditions = db.Column(db.Text)
    salary_from = db.Column(db.Integer)
    salary_to = db.Column(db.Integer)
    employment_type = db.Column(db.String(50))
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SecurityArticle(db.Model):
    """Модель статьи центра безопасности"""
    __tablename__ = 'security_articles'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    short_description = db.Column(db.String(500))
    content = db.Column(db.Text)
    priority = db.Column(db.String(20), default='info')
    icon = db.Column(db.String(50), default='shield-alt')
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PassRequest(db.Model):
    """Модель заявки на пропуск"""
    __tablename__ = 'pass_requests'

    id = db.Column(db.Integer, primary_key=True)
    visitor_name = db.Column(db.String(255), nullable=False)
    visitor_company = db.Column(db.String(255))
    visitor_document = db.Column(db.String(100))
    visit_date = db.Column(db.Date, nullable=False)
    visit_end_date = db.Column(db.Date)
    purpose = db.Column(db.Text)
    host_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='pending')
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    processed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comment = db.Column(db.Text)

    host = db.relationship('User', foreign_keys=[
                           host_id], backref='hosted_passes')
    created_by = db.relationship(
        'User', foreign_keys=[created_by_id], backref='created_passes')
    processed_by = db.relationship('User', foreign_keys=[processed_by_id])


class OrderRequest(db.Model):
    """Модель заявки на заказ товаров"""
    __tablename__ = 'order_requests'

    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(200), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    article = db.Column(db.String(100))
    quantity = db.Column(db.Integer, default=1)
    priority = db.Column(db.String(20), default='normal')
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    processed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    created_by = db.relationship(
        'User', foreign_keys=[created_by_id], backref='created_orders')
    processed_by = db.relationship('User', foreign_keys=[processed_by_id])


class Table(db.Model):
    """Модель электронной таблицы"""
    __tablename__ = 'tables'

    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    data = db.Column(db.Text, default='{}')
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship('User', backref='owned_tables')
    permissions = db.relationship(
        'TablePermission', backref='table', cascade='all, delete-orphan')

    def get_data(self):
        return json.loads(self.data) if self.data else {}

    def set_data(self, data):
        self.data = json.dumps(data, ensure_ascii=False)


class TablePermission(db.Model):
    """Модель прав доступа к таблице"""
    __tablename__ = 'table_permissions'

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.String(36), db.ForeignKey(
        'tables.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    can_edit = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref='table_permissions')


# Модели настроек

class Settings(db.Model):
    """Общие настройки системы"""
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))

    @staticmethod
    def get(key, default=None):
        setting = Settings.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value, description=None):
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value, description=description)
            db.session.add(setting)
        db.session.commit()


class LdapSettings(db.Model):
    """Настройки LDAP"""
    __tablename__ = 'ldap_settings'

    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, default=False)
    server = db.Column(db.String(255))
    port = db.Column(db.Integer, default=389)
    use_ssl = db.Column(db.Boolean, default=False)
    domain = db.Column(db.String(255))
    base_dn = db.Column(db.String(255))
    bind_user = db.Column(db.String(255))
    bind_password = db.Column(db.String(255))
    user_filter = db.Column(
        db.String(255), default='(sAMAccountName={username})')
    # Атрибуты LDAP для маппинга
    attr_firstname = db.Column(db.String(50), default='givenName')
    attr_lastname = db.Column(db.String(50), default='sn')
    attr_email = db.Column(db.String(50), default='mail')
    attr_phone = db.Column(db.String(50), default='telephoneNumber')
    attr_department = db.Column(db.String(50), default='department')
    attr_position = db.Column(db.String(50), default='title')
    attr_manager = db.Column(db.String(50), default='manager')

    # Группа для синхронизации (если указана - синхронизируются только члены этой группы)
    sync_group_dn = db.Column(db.String(500))
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связь с группами
    groups = db.relationship(
        'LdapGroup', backref='ldap_settings', cascade='all, delete-orphan')


class LdapGroup(db.Model):
    """Группа LDAP с привязкой к роли"""
    __tablename__ = 'ldap_groups'

    id = db.Column(db.Integer, primary_key=True)
    ldap_settings_id = db.Column(db.Integer, db.ForeignKey('ldap_settings.id'))
    group_dn = db.Column(db.String(500), nullable=False)
    group_name = db.Column(db.String(255))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    role = db.relationship('Role')


class LdapCustomAttribute(db.Model):
    """Кастомный атрибут LDAP для маппинга"""
    __tablename__ = 'ldap_custom_attributes'

    id = db.Column(db.Integer, primary_key=True)
    ldap_settings_id = db.Column(db.Integer, db.ForeignKey('ldap_settings.id'))
    # Атрибут в LDAP (например, physicalDeliveryOfficeName)
    ldap_attr = db.Column(db.String(100), nullable=False)
    # Поле на портале (например, location)
    portal_field = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100))  # Отображаемое название
    is_active = db.Column(db.Boolean, default=True)

    ldap_settings = db.relationship(
        'LdapSettings', backref='custom_attributes')


class UserCardField(db.Model):
    """Настройка поля в карточке пользователя"""
    __tablename__ = 'user_card_fields'

    id = db.Column(db.Integer, primary_key=True)
    # Имя поля (email, phone, location, etc.)
    field_name = db.Column(db.String(100), nullable=False)
    # Отображаемое название
    display_name = db.Column(db.String(100), nullable=False)
    # fontawesome, svg, image
    icon_type = db.Column(db.String(20), default='fontawesome')
    icon_value = db.Column(db.String(500))  # fa-envelope, путь к svg/image
    # Цвет иконки (blue, green, purple, etc.)
    icon_color = db.Column(db.String(50), default='blue')
    position = db.Column(db.Integer, default=0)  # Порядок отображения
    is_visible = db.Column(db.Boolean, default=True)
    # Является ли ссылкой (mailto:, tel:)
    is_link = db.Column(db.Boolean, default=False)
    link_prefix = db.Column(db.String(50))  # mailto:, tel:, https://
    # contact, info, additional
    section = db.Column(db.String(50), default='contact')

    @staticmethod
    def get_default_fields():
        """Поля по умолчанию"""
        return [
            {'field_name': 'email', 'display_name': 'Email', 'icon_type': 'fontawesome',
             'icon_value': 'fa-envelope', 'icon_color': 'blue', 'position': 1,
             'is_link': True, 'link_prefix': 'mailto:', 'section': 'contact'},
            {'field_name': 'phone', 'display_name': 'Телефон', 'icon_type': 'fontawesome',
             'icon_value': 'fa-phone', 'icon_color': 'green', 'position': 2,
             'is_link': True, 'link_prefix': 'tel:', 'section': 'contact'},
            {'field_name': 'internal_phone', 'display_name': 'Внутренний', 'icon_type': 'fontawesome',
             'icon_value': 'fa-phone-office', 'icon_color': 'purple', 'position': 3,
             'section': 'contact'},
            {'field_name': 'location', 'display_name': 'Местоположение', 'icon_type': 'fontawesome',
             'icon_value': 'fa-map-marker-alt', 'icon_color': 'amber', 'position': 4,
             'section': 'contact'},
            {'field_name': 'department', 'display_name': 'Отдел', 'icon_type': 'fontawesome',
             'icon_value': 'fa-building', 'icon_color': 'indigo', 'position': 5,
             'section': 'info'},
            {'field_name': 'birthday', 'display_name': 'День рождения', 'icon_type': 'fontawesome',
             'icon_value': 'fa-birthday-cake', 'icon_color': 'pink', 'position': 6,
             'section': 'info'},
            {'field_name': 'hire_date', 'display_name': 'Дата приёма', 'icon_type': 'fontawesome',
             'icon_value': 'fa-calendar-check', 'icon_color': 'green', 'position': 7,
             'section': 'info'},
        ]


class UserCustomField(db.Model):
    """Кастомное поле пользователя (для дополнительных данных)"""
    __tablename__ = 'user_custom_fields'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    field_name = db.Column(db.String(100), nullable=False)
    field_value = db.Column(db.Text)

    user = db.relationship('User', backref='custom_fields')

    __table_args__ = (db.UniqueConstraint('user_id', 'field_name'),)


class SmtpSettings(db.Model):
    """Настройки SMTP"""
    __tablename__ = 'smtp_settings'

    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, default=False)
    server = db.Column(db.String(255))
    port = db.Column(db.Integer, default=587)
    use_tls = db.Column(db.Boolean, default=True)
    use_ssl = db.Column(db.Boolean, default=False)
    username = db.Column(db.String(255))
    password = db.Column(db.String(255))
    sender_email = db.Column(db.String(255))
    sender_name = db.Column(db.String(255), default='Корпоративный портал')
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(db.Model):
    """Журнал аудита"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='audit_logs')


# === Модели мессенджера ===

class Chat(db.Model):
    """Модель чата (диалога между двумя пользователями)"""
    __tablename__ = 'chats'

    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # Чат "Избранное" (user1 == user2)
    is_favorites = db.Column(db.Boolean, default=False)
    is_deleted_for_user1 = db.Column(db.Boolean, default=False)
    is_deleted_for_user2 = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user1 = db.relationship('User', foreign_keys=[
                            user1_id], backref='chats_as_user1')
    user2 = db.relationship('User', foreign_keys=[
                            user2_id], backref='chats_as_user2')
    messages = db.relationship('Message', backref='chat', lazy='dynamic',
                               cascade='all, delete-orphan', order_by='Message.created_at')

    @staticmethod
    def get_or_create(user1_id, user2_id):
        """Получить или создать чат между двумя пользователями"""
        # Для избранного user1 == user2
        if user1_id == user2_id:
            chat = Chat.query.filter_by(
                user1_id=user1_id, user2_id=user2_id, is_favorites=True).first()
            if not chat:
                chat = Chat(user1_id=user1_id,
                            user2_id=user2_id, is_favorites=True)
                db.session.add(chat)
                db.session.commit()
            return chat

        # Нормализуем порядок ID
        if user1_id > user2_id:
            user1_id, user2_id = user2_id, user1_id

        chat = Chat.query.filter(
            (Chat.user1_id == user1_id) & (Chat.user2_id ==
                                           user2_id) & (Chat.is_favorites == False)
        ).first()

        if not chat:
            chat = Chat(user1_id=user1_id, user2_id=user2_id)
            db.session.add(chat)
            db.session.commit()

        return chat

    @staticmethod
    def get_favorites(user_id):
        """Получить или создать чат Избранное"""
        return Chat.get_or_create(user_id, user_id)

    def get_other_user(self, current_user_id):
        """Получить собеседника"""
        if self.is_favorites:
            return self.user1  # Для избранного возвращаем того же пользователя
        return self.user2 if self.user1_id == current_user_id else self.user1

    def is_visible_for_user(self, user_id):
        """Проверить видимость чата для пользователя"""
        if self.user1_id == user_id and self.is_deleted_for_user1:
            return False
        if self.user2_id == user_id and self.is_deleted_for_user2:
            return False
        return True

    def get_last_message(self, user_id=None):
        """Получить последнее видимое сообщение"""
        query = self.messages.filter(Message.is_deleted == False)
        if user_id:
            if self.user1_id == user_id:
                query = query.filter(Message.is_deleted_for_user1 == False)
            else:
                query = query.filter(Message.is_deleted_for_user2 == False)
        return query.order_by(Message.created_at.desc()).first()

    def get_unread_count(self, user_id):
        """Количество непрочитанных сообщений для пользователя"""
        query = self.messages.filter(
            Message.sender_id != user_id,
            Message.is_read == False,
            Message.is_deleted == False
        )
        if self.user1_id == user_id:
            query = query.filter(Message.is_deleted_for_user1 == False)
        else:
            query = query.filter(Message.is_deleted_for_user2 == False)
        return query.count()


class Message(db.Model):
    """Модель сообщения"""
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey(
        'chats.id'), nullable=True)  # Для личных чатов
    sender_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text)
    # text, voice, file, sticker
    message_type = db.Column(db.String(20), default='text')
    file_path = db.Column(db.String(500))
    file_name = db.Column(db.String(255))
    duration = db.Column(db.Integer)
    is_sticker = db.Column(db.Boolean, default=False)
    reply_to_id = db.Column(db.Integer, db.ForeignKey('messages.id'))

    # Пересылка
    forwarded_from_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    forwarded_message_id = db.Column(db.Integer)

    # Избранное
    is_favorite_user1 = db.Column(db.Boolean, default=False)
    is_favorite_user2 = db.Column(db.Boolean, default=False)

    # Удаление
    is_deleted = db.Column(db.Boolean, default=False)
    is_deleted_for_user1 = db.Column(db.Boolean, default=False)
    is_deleted_for_user2 = db.Column(db.Boolean, default=False)

    # Редактирование
    is_edited = db.Column(db.Boolean, default=False)
    edited_at = db.Column(db.DateTime)

    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Для групповых чатов/каналов
    group_id = db.Column(db.Integer, db.ForeignKey('chat_groups.id'))

    sender = db.relationship('User', foreign_keys=[
                             sender_id], backref='sent_messages')
    forwarded_from = db.relationship('User', foreign_keys=[forwarded_from_id])
    reply_to = db.relationship(
        'Message', remote_side='Message.id', backref='replies')

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            db.session.commit()

    def is_visible_for_user(self, user_id, chat):
        """Проверить видимость сообщения для пользователя"""
        if self.is_deleted:
            return False
        if chat.user1_id == user_id and self.is_deleted_for_user1:
            return False
        if chat.user2_id == user_id and self.is_deleted_for_user2:
            return False
        return True

    def to_dict(self, current_user_id=None, chat=None):
        reply_data = None
        if self.reply_to_id and self.reply_to:
            reply_data = {
                'id': self.reply_to.id,
                'sender_name': self.reply_to.sender.short_name if self.reply_to.sender else 'Unknown',
                'content': self.reply_to.content[:50] if self.reply_to.content else '',
                'is_sticker': self.reply_to.is_sticker,
                'message_type': self.reply_to.message_type
            }

        forwarded_data = None
        if self.forwarded_from_id and self.forwarded_from:
            forwarded_data = {
                'user_id': self.forwarded_from.id,
                'user_name': self.forwarded_from.short_name,
                'user_full_name': self.forwarded_from.full_name
            }

        # Определяем избранное для текущего пользователя
        is_favorite = False
        if current_user_id and chat:
            if chat.user1_id == current_user_id:
                is_favorite = self.is_favorite_user1
            else:
                is_favorite = self.is_favorite_user2

        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'group_id': self.group_id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.short_name if self.sender else 'Unknown',
            'sender_photo': get_photo_path(self.sender.photo) if self.sender else 'image/static_avatar.png',
            'content': self.content if not self.is_deleted else '[Сообщение удалено]',
            'message_type': self.message_type,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'duration': self.duration,
            'is_sticker': self.is_sticker,
            'reply_to': reply_data,
            'forwarded_from': forwarded_data,
            'is_favorite': is_favorite,
            'is_read': self.is_read,
            'is_deleted': self.is_deleted,
            'is_edited': self.is_edited,
            'edited_at': self.edited_at.strftime('%d.%m.%Y %H:%M') if self.edited_at else None,
            'created_at': self.created_at.strftime('%d.%m.%Y %H:%M'),
            'time': self.created_at.strftime('%H:%M')
        }


# === Групповые чаты и каналы ===

class ChatGroup(db.Model):
    """Модель группового чата или канала"""
    __tablename__ = 'chat_groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    avatar = db.Column(db.String(255), default='group_default.png')

    # Тип: 'group' - групповой чат, 'channel' - канал
    type = db.Column(db.String(20), default='group')

    # Настройки
    # Публичный (можно найти в поиске)
    is_public = db.Column(db.Boolean, default=False)
    invite_link = db.Column(db.String(64), unique=True)  # Ссылка-приглашение
    invite_link_enabled = db.Column(db.Boolean, default=True)

    # Для каналов: только админы могут писать
    only_admins_can_post = db.Column(db.Boolean, default=False)

    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship('User', foreign_keys=[
                            owner_id], backref='owned_groups')
    members = db.relationship(
        'ChatGroupMember', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='group', lazy='dynamic',
                               foreign_keys='Message.group_id', order_by='Message.created_at')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.invite_link:
            self.invite_link = secrets.token_urlsafe(32)

    def regenerate_invite_link(self):
        self.invite_link = secrets.token_urlsafe(32)
        db.session.commit()
        return self.invite_link

    def get_member(self, user_id):
        return self.members.filter_by(user_id=user_id).first()

    def is_member(self, user_id):
        return self.get_member(user_id) is not None

    def is_admin(self, user_id):
        member = self.get_member(user_id)
        return member and member.role in ('owner', 'admin')

    def can_post(self, user_id):
        """Может ли пользователь писать сообщения"""
        member = self.get_member(user_id)
        if not member:
            return False
        if self.only_admins_can_post:
            return member.role in ('owner', 'admin')
        return not member.is_muted

    def can_manage_members(self, user_id):
        """Может ли управлять участниками"""
        member = self.get_member(user_id)
        if not member:
            return False
        if member.role == 'owner':
            return True
        if member.role == 'admin':
            return member.can_add_members or member.can_remove_members
        return False

    def get_last_message(self):
        return self.messages.filter(Message.is_deleted == False).order_by(Message.created_at.desc()).first()

    def get_unread_count(self, user_id):
        member = self.get_member(user_id)
        if not member or not member.last_read_at:
            return self.messages.filter(Message.is_deleted == False).count()
        return self.messages.filter(
            Message.is_deleted == False,
            Message.created_at > member.last_read_at
        ).count()

    def to_dict(self, current_user_id=None):
        last_msg = self.get_last_message()
        unread = self.get_unread_count(
            current_user_id) if current_user_id else 0
        member = self.get_member(current_user_id) if current_user_id else None

        last_msg_text = ''
        if last_msg:
            if last_msg.is_sticker:
                last_msg_text = '🎨 Стикер'
            elif last_msg.message_type == 'voice':
                last_msg_text = '🎤 Голосовое'
            elif last_msg.message_type == 'file':
                last_msg_text = '📎 Файл'
            elif last_msg.content:
                last_msg_text = last_msg.content[:50]

        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'avatar': self.avatar,
            'type': self.type,
            'is_public': self.is_public,
            'only_admins_can_post': self.only_admins_can_post,
            'member_count': self.members.count(),
            'owner_id': self.owner_id,
            'my_role': member.role if member else None,
            'can_post': self.can_post(current_user_id) if current_user_id else False,
            'last_message': last_msg_text,
            'last_message_time': last_msg.created_at.strftime('%H:%M') if last_msg else '',
            'unread_count': unread,
            'updated_at': self.updated_at.isoformat() if self.updated_at else ''
        }


class ChatGroupMember(db.Model):
    """Участник группового чата/канала"""
    __tablename__ = 'chat_group_members'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey(
        'chat_groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Роль: owner, admin, member
    role = db.Column(db.String(20), default='member')

    # Права админа (если role == 'admin')
    # Редактировать название/описание
    can_edit_info = db.Column(db.Boolean, default=False)
    can_delete_messages = db.Column(
        db.Boolean, default=False)  # Удалять чужие сообщения
    can_add_members = db.Column(
        db.Boolean, default=True)  # Добавлять участников
    can_remove_members = db.Column(
        db.Boolean, default=False)  # Удалять участников
    can_manage_admins = db.Column(
        db.Boolean, default=False)  # Назначать админов
    can_pin_messages = db.Column(
        db.Boolean, default=False)  # Закреплять сообщения

    # Ограничения
    # Запрет на отправку сообщений
    is_muted = db.Column(db.Boolean, default=False)
    muted_until = db.Column(db.DateTime)  # До какого времени мут

    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_read_at = db.Column(db.DateTime)  # Когда последний раз читал

    # Уникальность: один пользователь - один раз в группе
    __table_args__ = (db.UniqueConstraint('group_id', 'user_id'),)

    user = db.relationship('User', backref='group_memberships')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.short_name if self.user else 'Unknown',
            'user_full_name': self.user.full_name if self.user else 'Unknown',
            'user_photo': get_photo_path(self.user.photo) if self.user else 'image/static_avatar.png',
            'role': self.role,
            'can_edit_info': self.can_edit_info,
            'can_delete_messages': self.can_delete_messages,
            'can_add_members': self.can_add_members,
            'can_remove_members': self.can_remove_members,
            'can_manage_admins': self.can_manage_admins,
            'can_pin_messages': self.can_pin_messages,
            'is_muted': self.is_muted,
            'joined_at': self.joined_at.strftime('%d.%m.%Y') if self.joined_at else ''
        }


class Referral(db.Model):
    """Модель реферальной рекомендации кандидата"""
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    vacancy_id = db.Column(db.Integer, db.ForeignKey(
        'vacancies.id'), nullable=False)
    referrer_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Данные кандидата
    candidate_name = db.Column(db.String(255), nullable=False)
    candidate_email = db.Column(db.String(120))
    candidate_phone = db.Column(db.String(50))
    comment = db.Column(db.Text)

    # Файл резюме
    resume_file = db.Column(db.String(500))
    resume_filename = db.Column(db.String(255))

    # Согласие на обработку данных
    consent_given = db.Column(db.Boolean, default=False)

    # Статус: new, reviewed, contacted, hired, rejected
    status = db.Column(db.String(20), default='new')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    hr_comment = db.Column(db.Text)

    vacancy = db.relationship('Vacancy', backref='referrals')
    referrer = db.relationship('User', foreign_keys=[
                               referrer_id], backref='my_referrals')
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])

    @property
    def status_display(self):
        statuses = {
            'new': 'Новая',
            'reviewed': 'Просмотрено',
            'contacted': 'Связались',
            'hired': 'Принят',
            'rejected': 'Отклонён'
        }
        return statuses.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {
            'new': 'blue',
            'reviewed': 'yellow',
            'contacted': 'purple',
            'hired': 'green',
            'rejected': 'red'
        }
        return colors.get(self.status, 'gray')


# === Модели опросов ===

class Survey(db.Model):
    """Модель опроса"""
    __tablename__ = 'surveys'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    # Настройки доступа
    is_active = db.Column(db.Boolean, default=True)
    # Анонимное голосование
    is_anonymous = db.Column(db.Boolean, default=False)
    allow_multiple_answers = db.Column(
        db.Boolean, default=False)  # Несколько ответов
    show_results = db.Column(db.Boolean, default=True)  # Показывать результаты

    # Публикация
    # Доступен по ссылке без авторизации
    is_public = db.Column(db.Boolean, default=False)
    # Токен для публичной ссылки
    public_token = db.Column(db.String(64), unique=True)
    # Опубликовать в новостях
    publish_in_news = db.Column(db.Boolean, default=False)

    # Ограничение по отделам (JSON список отделов или пустой для всех)
    departments = db.Column(db.Text, default='[]')

    # Даты
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship('User', backref='created_surveys')
    questions = db.relationship('SurveyQuestion', backref='survey', lazy='dynamic',
                                cascade='all, delete-orphan', order_by='SurveyQuestion.position')
    responses = db.relationship('SurveyResponse', backref='survey', lazy='dynamic',
                                cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.public_token:
            self.public_token = secrets.token_urlsafe(32)

    def get_departments(self):
        return json.loads(self.departments) if self.departments else []

    def set_departments(self, deps):
        self.departments = json.dumps(deps, ensure_ascii=False)

    def is_available_for_user(self, user):
        """Проверка доступности опроса для пользователя"""
        if not self.is_active:
            return False

        # Проверка дат
        now = datetime.utcnow()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False

        # Проверка отделов
        deps = self.get_departments()
        if deps and user.department not in deps:
            return False

        return True

    def has_user_voted(self, user_id):
        """Проверка, голосовал ли пользователь"""
        return self.responses.filter_by(user_id=user_id).first() is not None

    def get_total_responses(self):
        """Общее количество ответов"""
        return self.responses.count()

    def regenerate_token(self):
        self.public_token = secrets.token_urlsafe(32)
        db.session.commit()
        return self.public_token

    @property
    def status(self):
        now = datetime.utcnow()
        if not self.is_active:
            return 'inactive'
        if self.start_date and now < self.start_date:
            return 'scheduled'
        if self.end_date and now > self.end_date:
            return 'ended'
        return 'active'

    @property
    def status_display(self):
        statuses = {
            'active': 'Активен',
            'inactive': 'Неактивен',
            'scheduled': 'Запланирован',
            'ended': 'Завершён'
        }
        return statuses.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {
            'active': 'green',
            'inactive': 'gray',
            'scheduled': 'blue',
            'ended': 'yellow'
        }
        return colors.get(self.status, 'gray')


class SurveyQuestion(db.Model):
    """Вопрос опроса"""
    __tablename__ = 'survey_questions'

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey(
        'surveys.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    # single - один ответ, multiple - несколько, text - текстовый ответ
    question_type = db.Column(db.String(20), default='single')
    is_required = db.Column(db.Boolean, default=True)
    position = db.Column(db.Integer, default=0)

    options = db.relationship('SurveyOption', backref='question', lazy='dynamic',
                              cascade='all, delete-orphan', order_by='SurveyOption.position')
    answers = db.relationship('SurveyAnswer', backref='question', lazy='dynamic',
                              cascade='all, delete-orphan')


class SurveyOption(db.Model):
    """Вариант ответа"""
    __tablename__ = 'survey_options'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey(
        'survey_questions.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    position = db.Column(db.Integer, default=0)

    def get_votes_count(self):
        return SurveyAnswer.query.filter_by(option_id=self.id).count()

    def get_percentage(self):
        total = self.question.answers.count()
        if total == 0:
            return 0
        return round(self.get_votes_count() / total * 100, 1)


class SurveyResponse(db.Model):
    """Ответ пользователя на опрос (сессия голосования)"""
    __tablename__ = 'survey_responses'

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey(
        'surveys.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id'))  # NULL для анонимных
    # Для публичных опросов без авторизации
    session_id = db.Column(db.String(64))
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='survey_responses')
    answers = db.relationship('SurveyAnswer', backref='response', lazy='dynamic',
                              cascade='all, delete-orphan')


class SurveyAnswer(db.Model):
    """Конкретный ответ на вопрос"""
    __tablename__ = 'survey_answers'

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey(
        'survey_responses.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey(
        'survey_questions.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey(
        'survey_options.id'))  # Для single/multiple
    text_answer = db.Column(db.Text)  # Для текстовых ответов
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# === Модели тестов ===

class Test(db.Model):
    """Модель теста"""
    __tablename__ = 'tests'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    # Категория: general - общий, security - информационная безопасность
    category = db.Column(db.String(50), default='general')

    # Настройки
    is_active = db.Column(db.Boolean, default=True)
    # Лимит времени в минутах (NULL = без лимита)
    time_limit = db.Column(db.Integer)
    # Минимальный % для прохождения
    passing_score = db.Column(db.Integer, default=60)
    # Показывать правильные ответы после
    show_correct_answers = db.Column(db.Boolean, default=True)
    allow_retake = db.Column(db.Boolean, default=True)  # Разрешить пересдачу
    shuffle_questions = db.Column(
        db.Boolean, default=False)  # Перемешивать вопросы
    # Перемешивать варианты ответов
    shuffle_options = db.Column(db.Boolean, default=False)

    # Ограничение по отделам
    departments = db.Column(db.Text, default='[]')

    # Обязательный тест (для security)
    is_mandatory = db.Column(db.Boolean, default=False)
    deadline = db.Column(db.DateTime)  # Срок прохождения

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship('User', backref='created_tests')
    questions = db.relationship('TestQuestion', backref='test', lazy='dynamic',
                                cascade='all, delete-orphan', order_by='TestQuestion.position')
    attempts = db.relationship('TestAttempt', backref='test', lazy='dynamic',
                               cascade='all, delete-orphan')

    def get_departments(self):
        return json.loads(self.departments) if self.departments else []

    def set_departments(self, deps):
        self.departments = json.dumps(deps, ensure_ascii=False)

    def get_total_points(self):
        """Общее количество баллов за тест"""
        return sum(q.points for q in self.questions)

    def is_available_for_user(self, user):
        """Проверка доступности теста для пользователя"""
        if not self.is_active:
            return False
        deps = self.get_departments()
        if deps and user.department not in deps:
            return False
        return True

    def get_user_best_attempt(self, user_id):
        """Лучшая попытка пользователя"""
        return self.attempts.filter_by(
            user_id=user_id,
            is_completed=True
        ).order_by(TestAttempt.score.desc()).first()

    def get_user_attempts_count(self, user_id):
        """Количество попыток пользователя"""
        return self.attempts.filter_by(user_id=user_id, is_completed=True).count()

    def has_user_passed(self, user_id):
        """Прошёл ли пользователь тест"""
        best = self.get_user_best_attempt(user_id)
        if not best:
            return False
        return best.percentage >= self.passing_score

    @property
    def category_display(self):
        categories = {
            'general': 'Общий',
            'security': 'Информационная безопасность'
        }
        return categories.get(self.category, self.category)

    @property
    def category_icon(self):
        icons = {
            'general': 'clipboard-check',
            'security': 'shield-alt'
        }
        return icons.get(self.category, 'clipboard-check')

    @property
    def category_color(self):
        colors = {
            'general': 'blue',
            'security': 'red'
        }
        return colors.get(self.category, 'blue')


class TestQuestion(db.Model):
    """Вопрос теста"""
    __tablename__ = 'test_questions'

    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text)  # Пояснение к правильному ответу
    # single - один ответ, multiple - несколько правильных
    question_type = db.Column(db.String(20), default='single')
    points = db.Column(db.Integer, default=1)  # Баллы за вопрос
    position = db.Column(db.Integer, default=0)

    options = db.relationship('TestOption', backref='question', lazy='dynamic',
                              cascade='all, delete-orphan', order_by='TestOption.position')

    def get_correct_options(self):
        """Получить правильные варианты"""
        return self.options.filter_by(is_correct=True).all()


class TestOption(db.Model):
    """Вариант ответа теста"""
    __tablename__ = 'test_options'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey(
        'test_questions.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)  # Правильный ответ
    position = db.Column(db.Integer, default=0)


class TestAttempt(db.Model):
    """Попытка прохождения теста"""
    __tablename__ = 'test_attempts'

    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)
    is_completed = db.Column(db.Boolean, default=False)

    score = db.Column(db.Integer, default=0)  # Набранные баллы
    max_score = db.Column(db.Integer, default=0)  # Максимум баллов
    percentage = db.Column(db.Float, default=0)  # Процент
    passed = db.Column(db.Boolean, default=False)  # Пройден ли

    ip_address = db.Column(db.String(45))

    user = db.relationship('User', backref='test_attempts')
    answers = db.relationship('TestAnswer', backref='attempt', lazy='dynamic',
                              cascade='all, delete-orphan')

    def calculate_score(self):
        """Подсчёт результата"""
        total_score = 0
        max_score = 0

        for question in self.test.questions:
            max_score += question.points

            # Получаем ответы пользователя на этот вопрос
            user_answers = self.answers.filter_by(
                question_id=question.id).all()
            user_option_ids = {a.option_id for a in user_answers}

            # Правильные ответы
            correct_option_ids = {o.id for o in question.get_correct_options()}

            # Проверяем правильность
            if question.question_type == 'single':
                if user_option_ids == correct_option_ids:
                    total_score += question.points
            else:  # multiple
                if user_option_ids == correct_option_ids:
                    total_score += question.points

        self.score = total_score
        self.max_score = max_score
        self.percentage = round(
            total_score / max_score * 100, 1) if max_score > 0 else 0
        self.passed = self.percentage >= self.test.passing_score
        self.is_completed = True
        self.finished_at = datetime.utcnow()

        db.session.commit()
        return self.passed


class TestAnswer(db.Model):
    """Ответ пользователя на вопрос теста"""
    __tablename__ = 'test_answers'

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey(
        'test_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey(
        'test_questions.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('test_options.id'))

    question = db.relationship('TestQuestion')
    option = db.relationship('TestOption')


# === Настройки меню ===

class MenuItem(db.Model):
    """Пункт меню"""
    __tablename__ = 'menu_items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True,
                     nullable=False)  # Идентификатор
    title = db.Column(db.String(100), nullable=False)  # Отображаемое название
    icon = db.Column(db.String(50), default='link')  # FontAwesome иконка
    url = db.Column(db.String(255), nullable=False)  # URL или endpoint
    # Показывать в основном меню
    is_visible = db.Column(db.Boolean, default=True)
    position = db.Column(db.Integer, default=0)  # Порядок

    @staticmethod
    def get_default_items():
        """Пункты меню по умолчанию"""
        return [
            {'name': 'home', 'title': 'Главная', 'icon': 'home',
                'url': 'main.index', 'is_visible': True, 'position': 1},
            {'name': 'news', 'title': 'Новости', 'icon': 'newspaper',
                'url': 'news.index', 'is_visible': True, 'position': 2},
            {'name': 'staff', 'title': 'Сотрудники', 'icon': 'users',
                'url': 'staff.index', 'is_visible': True, 'position': 3},
            {'name': 'vacancies', 'title': 'Вакансии', 'icon': 'briefcase',
                'url': 'vacancies.index', 'is_visible': True, 'position': 4},
            {'name': 'vacations', 'title': 'Отпуска', 'icon': 'umbrella-beach',
                'url': 'vacations.index', 'is_visible': False, 'position': 5},
            {'name': 'surveys', 'title': 'Опросы', 'icon': 'poll',
                'url': 'surveys.index', 'is_visible': False, 'position': 6},
            {'name': 'tests', 'title': 'Тесты', 'icon': 'clipboard-check',
                'url': 'tests.index', 'is_visible': False, 'position': 7},
            {'name': 'security', 'title': 'Безопасность', 'icon': 'shield-alt',
                'url': 'security.index', 'is_visible': False, 'position': 8},
            {'name': 'tables', 'title': 'Таблицы', 'icon': 'table',
                'url': 'tables.index', 'is_visible': False, 'position': 9},
            {'name': 'testing', 'title': 'Сервисы тестирования', 'icon': 'flask',
                'url': 'testing.index', 'is_visible': False, 'position': 10},
            {'name': 'bugtracker', 'title': 'Баг-трекер', 'icon': 'bug',
                'url': 'bugtracker.index', 'is_visible': False, 'position': 11},
        ]

    @staticmethod
    def init_default():
        """Инициализация пунктов меню по умолчанию"""
        if MenuItem.query.count() == 0:
            for item_data in MenuItem.get_default_items():
                item = MenuItem(**item_data)
                db.session.add(item)
            db.session.commit()
        else:
            # Добавить новые пункты если их нет
            for item_data in MenuItem.get_default_items():
                existing = MenuItem.query.filter_by(
                    name=item_data['name']).first()
                if not existing:
                    item = MenuItem(**item_data)
                    db.session.add(item)
            db.session.commit()

    @staticmethod
    def get_visible():
        """Получить видимые пункты меню (макс 4)"""
        return MenuItem.query.filter_by(is_visible=True).order_by(MenuItem.position).limit(4).all()

    @staticmethod
    def get_hidden():
        """Получить скрытые пункты меню"""
        visible_ids = [m.id for m in MenuItem.get_visible()]
        return MenuItem.query.filter(~MenuItem.id.in_(visible_ids)).order_by(MenuItem.position).all()


# === Модели планера отпусков ===

class VacationSettings(db.Model):
    """Настройки системы отпусков"""
    __tablename__ = 'vacation_settings'

    id = db.Column(db.Integer, primary_key=True)
    # Количество дней ежегодного оплачиваемого отпуска по умолчанию
    annual_days_default = db.Column(db.Integer, default=28)
    # Включить day off
    dayoff_enabled = db.Column(db.Boolean, default=False)
    # Количество дней day off доступных для всех
    dayoff_days_limit = db.Column(db.Integer, default=0)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_settings():
        """Получить настройки (создать если не существуют)"""
        settings = VacationSettings.query.first()
        if not settings:
            settings = VacationSettings()
            db.session.add(settings)
            db.session.commit()
        return settings


class UserVacationBalance(db.Model):
    """Баланс отпускных дней пользователя"""
    __tablename__ = 'user_vacation_balance'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id'), nullable=False, unique=True)
    year = db.Column(db.Integer, nullable=False)
    # Доступные дни ежегодного отпуска
    annual_days_total = db.Column(db.Integer, default=28)
    annual_days_used = db.Column(db.Integer, default=0)
    # Доступные дни day off
    dayoff_days_total = db.Column(db.Integer, default=0)
    dayoff_days_used = db.Column(db.Integer, default=0)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='vacation_balance')

    @property
    def annual_days_remaining(self):
        return max(0, self.annual_days_total - self.annual_days_used)

    @property
    def dayoff_days_remaining(self):
        return max(0, self.dayoff_days_total - self.dayoff_days_used)

    @staticmethod
    def get_or_create(user_id, year=None):
        """Получить или создать баланс для пользователя"""
        if year is None:
            year = datetime.now().year

        balance = UserVacationBalance.query.filter_by(
            user_id=user_id, year=year).first()
        if not balance:
            settings = VacationSettings.get_settings()
            balance = UserVacationBalance(
                user_id=user_id,
                year=year,
                annual_days_total=settings.annual_days_default,
                dayoff_days_total=settings.dayoff_days_limit if settings.dayoff_enabled else 0
            )
            db.session.add(balance)
            db.session.commit()
        return balance


class VacationRequest(db.Model):
    """Заявка на отпуск"""
    __tablename__ = 'vacation_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    vacation_type = db.Column(
        db.String(50), default='annual')  # annual, unpaid, dayoff
    comment = db.Column(db.Text)

    # Статусы: pending_manager, pending_hr, approved, rejected_manager, rejected_hr
    status = db.Column(db.String(30), default='pending_manager')

    # Согласование руководителем
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    manager_approved_at = db.Column(db.DateTime)
    manager_comment = db.Column(db.Text)

    # Согласование HR
    hr_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    hr_approved_at = db.Column(db.DateTime)
    hr_comment = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[
                           user_id], backref='vacation_requests')
    manager = db.relationship('User', foreign_keys=[manager_id])
    hr = db.relationship('User', foreign_keys=[hr_id])

    @property
    def days_count(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def status_display(self):
        statuses = {
            'pending_manager': 'Ожидает руководителя',
            'pending_hr': 'Ожидает HR',
            'approved': 'Одобрено',
            'rejected_manager': 'Отклонено руководителем',
            'rejected_hr': 'Отклонено HR'
        }
        return statuses.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {
            'pending_manager': 'yellow',
            'pending_hr': 'blue',
            'approved': 'green',
            'rejected_manager': 'red',
            'rejected_hr': 'red'
        }
        return colors.get(self.status, 'gray')

    @property
    def vacation_type_display(self):
        types = {
            'annual': 'Ежегодный оплачиваемый',
            'unpaid': 'За свой счёт',
            'dayoff': 'Day Off'
        }
        return types.get(self.vacation_type, self.vacation_type)

    def overlaps_with(self, other_request):
        """Проверка пересечения дат с другой заявкой"""
        return not (self.end_date < other_request.start_date or self.start_date > other_request.end_date)

    @staticmethod
    def get_approved_in_range(start_date, end_date, department=None):
        """Получить одобренные отпуска в диапазоне дат"""
        query = VacationRequest.query.filter(
            VacationRequest.status == 'approved',
            VacationRequest.start_date <= end_date,
            VacationRequest.end_date >= start_date
        )
        if department:
            query = query.join(User, VacationRequest.user_id == User.id).filter(
                User.department == department)
        return query.all()


class VacationConflictRule(db.Model):
    """Правило конфликта отпусков (кто не может пересекаться)"""
    __tablename__ = 'vacation_conflict_rules'

    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(200))  # Отдел или NULL для всех
    user1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.String(255))  # Причина
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])

    __table_args__ = (db.UniqueConstraint('user1_id', 'user2_id'),)

    @staticmethod
    def get_conflicts_for_user(user_id):
        """Получить список пользователей, с которыми нельзя пересекаться"""
        rules = VacationConflictRule.query.filter(
            db.or_(
                VacationConflictRule.user1_id == user_id,
                VacationConflictRule.user2_id == user_id
            )
        ).all()

        conflict_user_ids = set()
        for rule in rules:
            if rule.user1_id == user_id:
                conflict_user_ids.add(rule.user2_id)
            else:
                conflict_user_ids.add(rule.user1_id)

        return conflict_user_ids

    @staticmethod
    def check_conflict(user1_id, user2_id):
        """Проверить, есть ли конфликт между двумя пользователями"""
        return VacationConflictRule.query.filter(
            db.or_(
                db.and_(VacationConflictRule.user1_id == user1_id,
                        VacationConflictRule.user2_id == user2_id),
                db.and_(VacationConflictRule.user1_id == user2_id,
                        VacationConflictRule.user2_id == user1_id)
            )
        ).first() is not None


# === Хранилище паролей ===

class PasswordVault(db.Model):
    """Хранилище паролей с шифрованием"""
    __tablename__ = 'password_vault'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    service_name = db.Column(db.String(255))
    url = db.Column(db.String(500))
    username = db.Column(db.String(255))
    encrypted_password = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text)
    category = db.Column(db.String(100))

    # Права доступа
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_shared = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed = db.Column(db.DateTime)

    owner = db.relationship('User', backref='password_vaults')
    permissions = db.relationship('PasswordVaultPermission', backref='vault',
                                  cascade='all, delete-orphan')
    access_logs = db.relationship('PasswordVaultLog', backref='vault',
                                  cascade='all, delete-orphan')

    def can_view(self, user):
        """Проверка прав на просмотр"""
        if self.owner_id == user.id or user.is_admin:
            return True
        perm = PasswordVaultPermission.query.filter_by(
            vault_id=self.id, user_id=user.id
        ).first()
        return perm and perm.can_read

    def can_edit(self, user):
        """Проверка прав на редактирование"""
        if self.owner_id == user.id or user.is_admin:
            return True
        perm = PasswordVaultPermission.query.filter_by(
            vault_id=self.id, user_id=user.id
        ).first()
        return perm and perm.can_edit

    def can_delete(self, user):
        """Проверка прав на удаление"""
        if self.owner_id == user.id or user.is_admin:
            return True
        perm = PasswordVaultPermission.query.filter_by(
            vault_id=self.id, user_id=user.id
        ).first()
        return perm and perm.can_delete


class PasswordVaultPermission(db.Model):
    """Права доступа к записи в хранилище"""
    __tablename__ = 'password_vault_permissions'

    id = db.Column(db.Integer, primary_key=True)
    vault_id = db.Column(db.Integer, db.ForeignKey(
        'password_vault.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    can_read = db.Column(db.Boolean, default=True)
    can_edit = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    can_share = db.Column(db.Boolean, default=False)

    granted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[
                           user_id], backref='vault_permissions')
    granted_by = db.relationship('User', foreign_keys=[granted_by_id])


class PasswordVaultLog(db.Model):
    """Лог доступа к хранилищу паролей"""
    __tablename__ = 'password_vault_logs'

    id = db.Column(db.Integer, primary_key=True)
    vault_id = db.Column(db.Integer, db.ForeignKey(
        'password_vault.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # view, edit, delete, share
    action = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='vault_logs')


# === Сервисы тестирования ===

class TestingService(db.Model):
    """Сервисы для тестирования (dev, staging, prod и т.д.)"""
    __tablename__ = 'testing_services'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)  # Markdown описание
    url = db.Column(db.String(500))
    environment = db.Column(db.String(50))  # dev, staging, prod, test
    icon = db.Column(db.String(50), default='server')  # FontAwesome иконка

    # Статус
    is_active = db.Column(db.Boolean, default=True)
    is_available = db.Column(db.Boolean, default=True)

    # Кастомные поля (JSON)
    custom_fields = db.Column(db.Text, default='[]')

    # Метаданные
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship('User', backref='testing_services')
    access_logs = db.relationship('TestingServiceLog', backref='service',
                                  cascade='all, delete-orphan')

    def get_custom_fields(self):
        """Получить кастомные поля как список"""
        if not self.custom_fields:
            return []
        try:
            return json.loads(self.custom_fields)
        except:
            return []

    def set_custom_fields(self, fields):
        """Установить кастомные поля"""
        self.custom_fields = json.dumps(fields, ensure_ascii=False)


class TestingServiceLog(db.Model):
    """Лог использования сервисов тестирования"""
    __tablename__ = 'testing_service_logs'

    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey(
        'testing_services.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # access, edit, toggle
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='service_logs')


# === Внешний вид сайта ===

class SiteAppearance(db.Model):
    """Настройки внешнего вида сайта"""
    __tablename__ = 'site_appearance'

    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(255), default='Корпоративный портал')
    primary_color = db.Column(db.String(7), default='#0078D7')
    secondary_color = db.Column(db.String(7), default='#005a9e')
    timezone = db.Column(db.String(50), default='Europe/Moscow')
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_settings():
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
    name = db.Column(db.String(100), nullable=False)
    decoration_type = db.Column(db.String(50), nullable=False)
    # above = над меню, overlay = поверх меню
    position = db.Column(db.String(20), default='above')
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_always_active = db.Column(db.Boolean, default=False)
    is_enabled = db.Column(db.Boolean, default=True)
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
        if not self.is_enabled:
            return False
        if self.is_always_active:
            return True
        today = datetime.now().date()
        if self.start_date and self.end_date:
            return self.start_date <= today <= self.end_date
        return False

    DECORATION_TYPES = {
        'garland': {'name': 'Гирлянда (мигающая)', 'description': 'Классическая мигающая гирлянда', 'icon': 'lightbulb'},
        'newyear_balls': {'name': 'Новогодние шары', 'description': 'Интерактивные новогодние шары', 'icon': 'circle'},
        'snow': {'name': 'Падающий снег', 'description': 'Анимация падающего снега', 'icon': 'snowflake'},
        'hearts': {'name': 'Сердечки', 'description': 'Летающие сердечки', 'icon': 'heart'},
        'confetti': {'name': 'Конфетти', 'description': 'Праздничное конфетти', 'icon': 'gift'},
        'flowers': {'name': 'Цветочки', 'description': 'Падающие цветы и лепестки', 'icon': 'seedling'},
        'leaves': {'name': 'Осенние листья', 'description': 'Падающие осенние листья', 'icon': 'leaf'},
        'stars': {'name': 'Звёздочки', 'description': 'Мерцающие звёзды', 'icon': 'star'}
    }

    CURSOR_TYPES = {
        'default': {'name': 'Стандартный', 'description': 'Обычный курсор'},
        'snowflake': {'name': 'Снежинка', 'description': 'Курсор в виде снежинки ❄'},
        'flower': {'name': 'Цветок', 'description': 'Курсор в виде цветка 🌸'},
        'heart': {'name': 'Сердечко', 'description': 'Курсор в виде сердца ❤'},
        'star': {'name': 'Звезда', 'description': 'Курсор в виде звезды ⭐'},
        'leaf': {'name': 'Листок', 'description': 'Курсор в виде листа 🍂'}
    }


# ==================== ДИАГРАММЫ ====================

class Diagram(db.Model):
    """Диаграмма Draw.io"""
    __tablename__ = 'diagrams'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    # XML данные диаграммы Draw.io
    xml_data = db.Column(db.Text)
    # Превью в base64
    preview_image = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship('User', backref='diagrams')
    shares = db.relationship(
        'DiagramShare', backref='diagram', lazy='dynamic', cascade='all, delete-orphan')

    def can_view(self, user):
        """Проверка права на просмотр"""
        if self.is_public:
            return True
        if self.owner_id == user.id:
            return True
        share = DiagramShare.query.filter_by(
            diagram_id=self.id, user_id=user.id).first()
        return share is not None

    def can_edit(self, user):
        """Проверка права на редактирование"""
        if self.owner_id == user.id:
            return True
        share = DiagramShare.query.filter_by(
            diagram_id=self.id, user_id=user.id).first()
        return share and share.can_edit

    def get_shared_users(self):
        """Получить список пользователей с доступом"""
        return self.shares.all()


class DiagramShare(db.Model):
    """Доступ к диаграмме"""
    __tablename__ = 'diagram_shares'

    id = db.Column(db.Integer, primary_key=True)
    diagram_id = db.Column(db.Integer, db.ForeignKey(
        'diagrams.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # False = только просмотр, True = редактирование
    can_edit = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='shared_diagrams')

    __table_args__ = (
        db.UniqueConstraint('diagram_id', 'user_id',
                            name='unique_diagram_share'),
    )


# ==================== БЛАГОДАРНОСТИ ====================

class Thanks(db.Model):
    """Благодарности сотрудникам"""
    __tablename__ = 'thanks'

    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False)
    to_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    from_user = db.relationship(
        'User', foreign_keys=[from_user_id], backref='thanks_sent')
    to_user = db.relationship('User', foreign_keys=[
                              to_user_id], backref='thanks_received')

    @staticmethod
    def get_count(user_id):
        """Получить количество благодарностей пользователя"""
        return Thanks.query.filter_by(to_user_id=user_id).count()

    @staticmethod
    def get_thanks_for_user(user_id, limit=10):
        """Получить последние благодарности пользователя"""
        return Thanks.query.filter_by(to_user_id=user_id).order_by(Thanks.created_at.desc()).limit(limit).all()
