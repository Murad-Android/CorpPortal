"""
Сервис авторизации
"""
from app import db, login_manager
from app.models import User, Role, LdapSettings, LdapGroup, LdapCustomAttribute, UserCustomField, AuditLog, Notification
from datetime import datetime
from flask import request


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def authenticate_local(username, password):
    """Локальная авторизация"""
    user = User.query.filter_by(username=username, is_ldap_user=False).first()
    if user and user.check_password(password) and user.is_active:
        user.last_login = datetime.utcnow()
        db.session.commit()
        log_action(user.id, 'login', 'user', user.id, 'Локальная авторизация')
        return user
    return None


def authenticate_ldap(username, password):
    """LDAP авторизация с синхронизацией данных"""
    ldap_settings = LdapSettings.query.first()
    if not ldap_settings or not ldap_settings.is_enabled:
        print('[LDAP] LDAP отключен или не настроен')
        return None

    print('=' * 60)
    print('[LDAP] Начало авторизации')
    print(f'[LDAP] Пользователь: {username}')
    print(f'[LDAP] Сервер: {ldap_settings.server}:{ldap_settings.port}')
    print(f'[LDAP] Домен: {ldap_settings.domain}')
    print(f'[LDAP] Base DN: {ldap_settings.base_dn}')
    print(f'[LDAP] User Filter: {ldap_settings.user_filter}')
    print(f'[LDAP] SSL: {ldap_settings.use_ssl}')

    try:
        from ldap3 import Server, Connection, ALL, NTLM, SUBTREE

        server = Server(
            ldap_settings.server,
            port=ldap_settings.port,
            use_ssl=ldap_settings.use_ssl,
            get_info=ALL
        )
        print(f'[LDAP] Сервер создан: {server}')

        user_dn = f'{ldap_settings.domain}\\{username}'
        print(f'[LDAP] User DN для NTLM: {user_dn}')

        conn = Connection(
            server,
            user=user_dn,
            password=password,
            authentication=NTLM,
            auto_bind=False
        )
        print('[LDAP] Соединение создано, попытка bind...')

        bind_result = conn.bind()
        print(f'[LDAP] Bind результат: {bind_result}')
        print(f'[LDAP] Bind response: {conn.result}')

        if bind_result:
            print('[LDAP] Bind успешен!')

            search_filter = ldap_settings.user_filter.replace(
                '{username}', username)
            print(f'[LDAP] Поиск с фильтром: {search_filter}')
            print(f'[LDAP] В Base DN: {ldap_settings.base_dn}')

            search_result = conn.search(
                ldap_settings.base_dn,
                search_filter,
                search_scope=SUBTREE,
                attributes=['*', 'memberOf']
            )
            print(f'[LDAP] Результат поиска: {search_result}')
            print(f'[LDAP] Найдено записей: {len(conn.entries)}')

            ldap_user_data = {}
            user_groups = []

            if conn.entries:
                entry = conn.entries[0]
                print(f'[LDAP] DN пользователя: {entry.entry_dn}')
                print(f'[LDAP] Атрибуты: {entry.entry_attributes_as_dict}')

                ldap_user_data = {
                    'firstname': get_ldap_attr(entry, ldap_settings.attr_firstname),
                    'lastname': get_ldap_attr(entry, ldap_settings.attr_lastname),
                    'middlename': get_ldap_attr(entry, 'middleName') or get_ldap_attr(entry, 'initials'),
                    'email': get_ldap_attr(entry, ldap_settings.attr_email),
                    'phone': get_ldap_attr(entry, ldap_settings.attr_phone),
                    'department': get_ldap_attr(entry, ldap_settings.attr_department),
                    'position': get_ldap_attr(entry, ldap_settings.attr_position),
                    'manager_dn': get_ldap_attr(entry, ldap_settings.attr_manager) if hasattr(ldap_settings, 'attr_manager') else get_ldap_attr(entry, 'manager'),
                }

                # Загружаем кастомные атрибуты
                custom_attrs = {}
                for custom_attr in ldap_settings.custom_attributes:
                    if custom_attr.is_active:
                        value = get_ldap_attr(entry, custom_attr.ldap_attr)
                        if value:
                            custom_attrs[custom_attr.portal_field] = value
                            print(
                                f'[LDAP] Кастомный атрибут {custom_attr.ldap_attr} -> {custom_attr.portal_field}: {value}')

                ldap_user_data['custom_attrs'] = custom_attrs
                print(f'[LDAP] Данные: {ldap_user_data}')

                if hasattr(entry, 'memberOf') and entry.memberOf:
                    user_groups = [
                        str(g).lower() for g in entry.memberOf.values] if entry.memberOf.values else []
                print(f'[LDAP] Группы пользователя ({len(user_groups)}):')
                for g in user_groups:
                    print(f'  - {g}')

                # Проверка членства в группе синхронизации
                sync_group = ldap_settings.sync_group_dn
                if sync_group:
                    sync_group_lower = sync_group.lower()
                    if sync_group_lower not in user_groups:
                        print(
                            f'[LDAP] ✗ Пользователь не состоит в группе синхронизации: {sync_group}')
                        print('=' * 60)
                        return None
                    print(f'[LDAP] ✓ Пользователь состоит в группе синхронизации')
            else:
                print('[LDAP] Пользователь не найден в поиске!')

            role_id = None
            default_role = Role.query.filter_by(name='user').first()
            role_id = default_role.id if default_role else None
            print(
                f'[LDAP] Роль по умолчанию: {default_role.name if default_role else "нет"} (ID: {role_id})')

            # Приоритет ролей (чем меньше число, тем выше приоритет)
            ROLE_PRIORITY = {'admin': 0, 'hr': 1, 'secretary': 2, 'user': 99}

            print(f'[LDAP] Настроенные группы ({len(ldap_settings.groups)}):')
            matched_roles = []
            for ldap_group in ldap_settings.groups:
                group_dn_lower = ldap_group.group_dn.lower() if ldap_group.group_dn else ''
                role_name = ldap_group.role.name if ldap_group.role else 'нет роли'
                print(f'  - DN: {ldap_group.group_dn}')
                print(f'    Роль: {role_name} (ID: {ldap_group.role_id})')

                if group_dn_lower in user_groups:
                    matched_roles.append(ldap_group)
                    print(f'    ✓ СОВПАДЕНИЕ!')
                else:
                    print(f'    ✗ Не совпадает')

            # Выбираем роль с наивысшим приоритетом из совпавших
            if matched_roles:
                matched_roles.sort(key=lambda g: ROLE_PRIORITY.get(
                    g.role.name if g.role else 'user', 50))
                best = matched_roles[0]
                role_id = best.role_id
                print(
                    f'[LDAP] Выбрана роль: {best.role.name if best.role else "?"} (наивысший приоритет из {len(matched_roles)} совпадений)')

            # Ищем пользователя по username ИЛИ по email
            user = User.query.filter_by(username=username).first()

            # Если не нашли по username, ищем по email
            ldap_email = ldap_user_data.get('email')
            if not user and ldap_email:
                user = User.query.filter_by(email=ldap_email).first()
                if user:
                    print(
                        f'[LDAP] Найден пользователь по email: {ldap_email} (ID: {user.id})')
                    # Обновляем username если нашли по email
                    user.username = username
                    user.is_ldap_user = True

            if not user:
                print(f'[LDAP] Создание пользователя: {username}')
                # Проверяем уникальность email перед созданием
                email_to_use = ldap_email or f'{username}@{ldap_settings.domain}'
                existing_by_email = User.query.filter_by(
                    email=email_to_use).first()
                if existing_by_email:
                    print(
                        f'[LDAP] Email {email_to_use} уже используется пользователем {existing_by_email.username}')
                    # Обновляем существующего пользователя
                    user = existing_by_email
                    user.username = username
                    user.is_ldap_user = True
                else:
                    user = User(
                        username=username,
                        email=email_to_use,
                        is_ldap_user=True,
                        is_active=True
                    )
                    db.session.add(user)
            else:
                print(
                    f'[LDAP] Пользователь существует: {username} (ID: {user.id})')

            if user.is_ldap_user:
                user.firstname = ldap_user_data.get(
                    'firstname') or user.firstname
                user.lastname = ldap_user_data.get('lastname') or user.lastname
                user.middlename = ldap_user_data.get('middlename') or None
                user.email = ldap_user_data.get('email') or user.email
                user.phone = ldap_user_data.get('phone') or user.phone
                user.department = ldap_user_data.get(
                    'department') or user.department
                user.position = ldap_user_data.get('position') or user.position
                user.role_id = role_id

                # Применяем кастомные атрибуты к стандартным полям
                custom_attrs = ldap_user_data.get('custom_attrs', {})
                if 'location' in custom_attrs:
                    user.location = custom_attrs['location']
                if 'internal_phone' in custom_attrs:
                    user.internal_phone = custom_attrs['internal_phone']

                # Сохраняем остальные кастомные атрибуты
                for field_name, field_value in custom_attrs.items():
                    if field_name not in ['location', 'internal_phone']:
                        existing = UserCustomField.query.filter_by(
                            user_id=user.id, field_name=field_name).first()
                        if existing:
                            existing.field_value = field_value
                        else:
                            custom_field = UserCustomField(
                                user_id=user.id, field_name=field_name, field_value=field_value)
                            db.session.add(custom_field)

                # Поиск руководителя по DN
                manager_dn = ldap_user_data.get('manager_dn')
                if manager_dn:
                    print(f'[LDAP] Manager DN: {manager_dn}')
                    import re
                    cn_match = re.search(
                        r'CN=([^,]+)', manager_dn, re.IGNORECASE)
                    if cn_match:
                        manager_cn = cn_match.group(1)
                        print(f'[LDAP] Manager CN: {manager_cn}')
                        # Ищем руководителя в базе
                        manager_user = User.query.filter(
                            db.or_(
                                User.username.ilike(
                                    manager_cn.replace(' ', '')),
                                User.username.ilike(manager_cn.split()[
                                                    0] if ' ' in manager_cn else manager_cn)
                            )
                        ).first()
                        if manager_user and manager_user.id != user.id:
                            user.manager_id = manager_user.id
                            print(
                                f'[LDAP] Руководитель: {manager_user.full_name} (ID: {manager_user.id})')
                        else:
                            print(f'[LDAP] Руководитель не найден в базе')

            user.last_login = datetime.utcnow()
            db.session.commit()

            print(
                f'[LDAP] ✓ Авторизация успешна! User ID: {user.id}, Role: {user.role.name if user.role else "нет"}')
            print('=' * 60)

            log_action(user.id, 'login', 'user', user.id, 'LDAP авторизация')
            return user
        else:
            print(f'[LDAP] ✗ Bind НЕ УДАЛСЯ!')
            print(f'[LDAP] Результат: {conn.result}')
            print('=' * 60)

    except ImportError:
        print('[LDAP] Ошибка: ldap3 не установлен')
    except Exception as e:
        print(f'[LDAP] Ошибка: {e}')
        import traceback
        traceback.print_exc()

    print('=' * 60)
    return None


def get_ldap_attr(entry, attr_name):
    """Безопасное получение атрибута LDAP. Возвращает строку или None (никогда не 'None')."""
    if not attr_name:
        return None
    try:
        # Способ 1: через hasattr/getattr
        if hasattr(entry, attr_name):
            val = getattr(entry, attr_name)
            if val and val.value:
                result = str(val.value)
                # Защита от строки "None"
                return result if result and result != 'None' else None

        # Способ 2: через словарь атрибутов (для нестандартных имён)
        attrs_dict = entry.entry_attributes_as_dict
        if attr_name in attrs_dict and attrs_dict[attr_name]:
            val = attrs_dict[attr_name]
            if isinstance(val, list) and len(val) > 0:
                result = str(val[0])
                return result if result and result != 'None' else None
            result = str(val)
            return result if result and result != 'None' else None
    except Exception as e:
        pass
    return None


def authenticate(username, password):
    """Универсальная авторизация"""
    # Сначала пробуем локальную авторизацию
    user = authenticate_local(username, password)
    if user:
        return user

    # Затем LDAP
    ldap_settings = LdapSettings.query.first()
    if ldap_settings and ldap_settings.is_enabled:
        user = authenticate_ldap(username, password)
        if user:
            return user

    return None


def sync_all_ldap_users():
    """Полная синхронизация всех пользователей из LDAP"""
    ldap_settings = LdapSettings.query.first()
    if not ldap_settings or not ldap_settings.is_enabled:
        return {'success': False, 'error': 'LDAP не настроен или отключен'}

    print('=' * 60)
    print('[LDAP SYNC] Начало полной синхронизации')

    try:
        from ldap3 import Server, Connection, ALL, NTLM, SUBTREE

        server = Server(
            ldap_settings.server,
            port=ldap_settings.port,
            use_ssl=ldap_settings.use_ssl,
            get_info=ALL
        )

        # Подключаемся с bind user
        if ldap_settings.bind_user and ldap_settings.bind_password:
            conn = Connection(
                server,
                user=ldap_settings.bind_user,
                password=ldap_settings.bind_password,
                authentication=NTLM,
                auto_bind=False
            )
        else:
            return {'success': False, 'error': 'Не указаны bind user/password'}

        if not conn.bind():
            return {'success': False, 'error': f'Ошибка подключения: {conn.result}'}

        print(f'[LDAP SYNC] Подключение успешно')

        # Определяем фильтр поиска
        sync_group = ldap_settings.sync_group_dn
        if sync_group:
            # Поиск только членов указанной группы
            search_filter = f'(&(objectClass=user)(objectCategory=person)(!(userAccountControl:1.2.840.113556.1.4.803:=2))(memberOf={sync_group}))'
            print(f'[LDAP SYNC] Фильтр по группе: {sync_group}')
        else:
            # Все активные пользователи
            search_filter = '(&(objectClass=user)(objectCategory=person)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))'
            print('[LDAP SYNC] Синхронизация всех пользователей (группа не указана)')

        # Собираем кастомные атрибуты для запроса
        custom_attr_names = [
            ca.ldap_attr for ca in ldap_settings.custom_attributes if ca.is_active]

        # Запрашиваем все атрибуты чтобы избежать ошибок с несуществующими
        conn.search(
            ldap_settings.base_dn,
            search_filter,
            search_scope=SUBTREE,
            attributes=['*', 'memberOf']
        )

        print(f'[LDAP SYNC] Найдено пользователей в AD: {len(conn.entries)}')

        created = 0
        updated = 0
        skipped = 0

        # Собираем DN -> username маппинг для руководителей
        dn_to_username = {}
        for entry in conn.entries:
            username = str(entry.sAMAccountName) if hasattr(
                entry, 'sAMAccountName') and entry.sAMAccountName else None
            if username:
                dn_to_username[entry.entry_dn.lower()] = username

        for entry in conn.entries:
            try:
                username = str(entry.sAMAccountName) if hasattr(
                    entry, 'sAMAccountName') and entry.sAMAccountName else None
                if not username:
                    skipped += 1
                    continue

                # Получаем группы пользователя
                user_groups = []
                if hasattr(entry, 'memberOf') and entry.memberOf:
                    user_groups = [
                        str(g).lower() for g in entry.memberOf.values] if entry.memberOf.values else []

                # Определяем роль (наивысший приоритет из совпавших групп)
                ROLE_PRIORITY = {'admin': 0, 'hr': 1,
                                 'secretary': 2, 'user': 99}
                role_id = None
                default_role = Role.query.filter_by(name='user').first()
                role_id = default_role.id if default_role else None

                matched_roles = []
                for ldap_group in ldap_settings.groups:
                    group_dn_lower = ldap_group.group_dn.lower() if ldap_group.group_dn else ''
                    if group_dn_lower in user_groups:
                        matched_roles.append(ldap_group)

                if matched_roles:
                    matched_roles.sort(key=lambda g: ROLE_PRIORITY.get(
                        g.role.name if g.role else 'user', 50))
                    role_id = matched_roles[0].role_id

                # Данные пользователя
                ldap_user_data = {
                    'firstname': get_ldap_attr(entry, ldap_settings.attr_firstname),
                    'lastname': get_ldap_attr(entry, ldap_settings.attr_lastname),
                    'middlename': get_ldap_attr(entry, 'middleName') or get_ldap_attr(entry, 'initials'),
                    'email': get_ldap_attr(entry, ldap_settings.attr_email),
                    'phone': get_ldap_attr(entry, ldap_settings.attr_phone),
                    'department': get_ldap_attr(entry, ldap_settings.attr_department),
                    'position': get_ldap_attr(entry, ldap_settings.attr_position),
                    'manager_dn': get_ldap_attr(entry, ldap_settings.attr_manager or 'manager'),
                }

                # Проверяем/создаем пользователя
                user = User.query.filter_by(username=username).first()

                # Если не нашли по username, ищем по email
                ldap_email = ldap_user_data.get('email')
                if not user and ldap_email:
                    user = User.query.filter_by(email=ldap_email).first()
                    if user:
                        user.username = username
                        user.is_ldap_user = True

                is_new = False
                if not user:
                    email_to_use = ldap_email or f'{username}@{ldap_settings.domain}'
                    # Проверяем уникальность email
                    existing_by_email = User.query.filter_by(
                        email=email_to_use).first()
                    if existing_by_email:
                        user = existing_by_email
                        user.username = username
                        user.is_ldap_user = True
                        updated += 1
                    else:
                        user = User(
                            username=username,
                            email=email_to_use,
                            is_ldap_user=True,
                            is_active=True
                        )
                        db.session.add(user)
                        is_new = True
                        created += 1
                else:
                    updated += 1

                # Обновляем данные
                if user.is_ldap_user:
                    user.firstname = ldap_user_data.get(
                        'firstname') or user.firstname
                    user.lastname = ldap_user_data.get(
                        'lastname') or user.lastname
                    user.middlename = ldap_user_data.get('middlename') or None
                    user.email = ldap_user_data.get('email') or user.email
                    user.phone = ldap_user_data.get('phone') or user.phone
                    user.department = ldap_user_data.get(
                        'department') or user.department
                    user.position = ldap_user_data.get(
                        'position') or user.position
                    user.role_id = role_id

                    # Применяем кастомные атрибуты
                    for custom_attr in ldap_settings.custom_attributes:
                        if custom_attr.is_active:
                            value = get_ldap_attr(entry, custom_attr.ldap_attr)
                            print(
                                f'[LDAP SYNC] Кастомный атрибут {custom_attr.ldap_attr} = {value}')
                            if value:
                                # Стандартные поля
                                if custom_attr.portal_field == 'location':
                                    user.location = value
                                    print(
                                        f'[LDAP SYNC] Установлено location = {value} для {username}')
                                elif custom_attr.portal_field == 'internal_phone':
                                    user.internal_phone = value
                                else:
                                    # Кастомные поля
                                    existing = UserCustomField.query.filter_by(
                                        user_id=user.id, field_name=custom_attr.portal_field).first()
                                    if existing:
                                        existing.field_value = value
                                    else:
                                        custom_field = UserCustomField(
                                            user_id=user.id, field_name=custom_attr.portal_field, field_value=value)
                                        db.session.add(custom_field)

            except Exception as e:
                print(f'[LDAP SYNC] Ошибка обработки {username}: {e}')
                skipped += 1

        db.session.commit()

        # Второй проход - обновляем руководителей
        print('[LDAP SYNC] Обновление руководителей...')
        for entry in conn.entries:
            try:
                username = str(entry.sAMAccountName) if hasattr(
                    entry, 'sAMAccountName') and entry.sAMAccountName else None
                if not username:
                    continue

                manager_dn = get_ldap_attr(
                    entry, ldap_settings.attr_manager or 'manager')
                if manager_dn:
                    manager_username = dn_to_username.get(manager_dn.lower())
                    if manager_username:
                        user = User.query.filter_by(username=username).first()
                        manager = User.query.filter_by(
                            username=manager_username).first()
                        if user and manager and user.id != manager.id:
                            user.manager_id = manager.id
            except:
                pass

        db.session.commit()

        # Третий проход - деактивация пользователей, которых нет в LDAP
        print('[LDAP SYNC] Проверка деактивации...')
        ldap_usernames = set()
        for entry in conn.entries:
            username = str(entry.sAMAccountName) if hasattr(
                entry, 'sAMAccountName') and entry.sAMAccountName else None
            if username:
                ldap_usernames.add(username.lower())

        deactivated = 0
        # Все активные LDAP-пользователи на портале
        portal_ldap_users = User.query.filter_by(
            is_ldap_user=True, is_active=True).all()
        for portal_user in portal_ldap_users:
            if portal_user.username.lower() not in ldap_usernames:
                portal_user.is_active = False
                portal_user.employment_status = 'fired'
                deactivated += 1
                print(
                    f'[LDAP SYNC] Деактивирован: {portal_user.username} ({portal_user.full_name})')

        if deactivated:
            db.session.commit()
            print(f'[LDAP SYNC] Деактивировано: {deactivated}')

        result = {
            'success': True,
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'deactivated': deactivated,
            'total': len(conn.entries)
        }
        print(
            f'[LDAP SYNC] Завершено: создано {created}, обновлено {updated}, деактивировано {deactivated}, пропущено {skipped}')
        print('=' * 60)
        return result

    except ImportError:
        return {'success': False, 'error': 'ldap3 не установлен'}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def log_action(user_id, action, entity_type=None, entity_id=None, details=None):
    """Логирование действия"""
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=request.remote_addr if request else None
    )
    db.session.add(log)
    db.session.commit()


def notify_user(user_id, title, message=None, link=None, icon='bell', type='info'):
    """Создание уведомления для пользователя"""
    return Notification.create(user_id, title, message, link, icon, type)


def notify_role(role_name, title, message=None, link=None, icon='bell', type='info'):
    """Создание уведомления для всех пользователей с определенной ролью"""
    role = Role.query.filter_by(name=role_name).first()
    if role:
        for user in role.users:
            Notification.create(user.id, title, message, link, icon, type)
