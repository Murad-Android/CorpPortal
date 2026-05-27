"""
Сервис инициализации начальных данных
"""
from app import db
from app.models import User, Role, Settings, LdapSettings, SmtpSettings


def init_default_data():
    """Создание начальных данных при первом запуске"""

    # Создание ролей по умолчанию
    for role_data in Role.get_default_roles():
        if not Role.query.filter_by(name=role_data['name']).first():
            role = Role(
                name=role_data['name'],
                display_name=role_data['display_name']
            )
            role.set_permissions(role_data['permissions'])
            db.session.add(role)
            print(f'✓ Создана роль: {role_data["display_name"]}')

    db.session.commit()

    # Создание администратора по умолчанию
    admin_role = Role.query.filter_by(name='admin').first()
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@portal.local',
            firstname='Администратор',
            lastname='Системы',
            role_id=admin_role.id if admin_role else None,
            is_active=True
        )
        admin.set_password('admin')
        db.session.add(admin)
        print('✓ Создан администратор по умолчанию (admin/admin)')

    # Настройки по умолчанию
    default_settings = [
        ('site_name', 'Корпоративный портал', 'Название сайта'),
        ('site_description', 'Внутренний портал компании', 'Описание сайта'),
        ('auth_enabled', 'true', 'Включена ли авторизация'),
        ('registration_enabled', 'false', 'Разрешена ли регистрация'),
    ]

    for key, value, description in default_settings:
        if not Settings.query.filter_by(key=key).first():
            setting = Settings(key=key, value=value, description=description)
            db.session.add(setting)

    # Настройки LDAP по умолчанию
    if not LdapSettings.query.first():
        ldap = LdapSettings(
            is_enabled=False,
            server='ldap://localhost',
            port=389,
            domain='domain.local'
        )
        db.session.add(ldap)

    # Настройки SMTP по умолчанию
    if not SmtpSettings.query.first():
        smtp = SmtpSettings(
            is_enabled=False,
            server='smtp.mail.ru',
            port=587,
            use_tls=True
        )
        db.session.add(smtp)

    db.session.commit()
