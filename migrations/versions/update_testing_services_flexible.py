"""
Обновление таблицы testing_services для гибкого конструктора

- Удаление фиксированных полей (version, tech_stack, documentation_url, responsible_person, contact_email)
- Добавление custom_fields (JSON) для хранения кастомных полей
- Добавление icon для иконки сервиса
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


def upgrade():
    """Обновление структуры таблицы"""
    conn = op.get_bind()

    # Проверяем существование колонок и добавляем новые
    inspector = sa.inspect(conn)
    columns = [col['name']
               for col in inspector.get_columns('testing_services')]

    # Добавляем custom_fields если не существует
    if 'custom_fields' not in columns:
        op.add_column('testing_services',
                      sa.Column('custom_fields', sa.Text(), nullable=True, server_default='[]'))

    # Добавляем icon если не существует
    if 'icon' not in columns:
        op.add_column('testing_services',
                      sa.Column('icon', sa.String(50), nullable=True, server_default='server'))

    # Миграция данных из старых полей в custom_fields
    # Получаем все сервисы со старыми полями
    result = conn.execute(text("""
        SELECT id, version, tech_stack, documentation_url, responsible_person, contact_email 
        FROM testing_services
    """))

    import json

    for row in result:
        custom_fields = []

        if row[1]:  # version
            custom_fields.append({
                'name': 'Версия',
                'value': row[1],
                'type': 'text',
                'icon': ''
            })

        if row[2]:  # tech_stack
            custom_fields.append({
                'name': 'Технологии',
                'value': row[2],
                'type': 'text',
                'icon': ''
            })

        if row[3]:  # documentation_url
            custom_fields.append({
                'name': 'Документация',
                'value': row[3],
                'type': 'link',
                'icon': ''
            })

        if row[4]:  # responsible_person
            custom_fields.append({
                'name': 'Ответственный',
                'value': row[4],
                'type': 'text',
                'icon': ''
            })

        if row[5]:  # contact_email
            custom_fields.append({
                'name': 'Email',
                'value': row[5],
                'type': 'email',
                'icon': ''
            })

        if custom_fields:
            conn.execute(
                text("UPDATE testing_services SET custom_fields = :fields WHERE id = :id"),
                {'fields': json.dumps(
                    custom_fields, ensure_ascii=False), 'id': row[0]}
            )

    # Удаляем старые колонки (SQLite не поддерживает DROP COLUMN напрямую)
    # Для SQLite пропускаем удаление, данные уже мигрированы
    # Для других БД можно раскомментировать:
    # op.drop_column('testing_services', 'version')
    # op.drop_column('testing_services', 'tech_stack')
    # op.drop_column('testing_services', 'documentation_url')
    # op.drop_column('testing_services', 'responsible_person')
    # op.drop_column('testing_services', 'contact_email')


def downgrade():
    """Откат изменений"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name']
               for col in inspector.get_columns('testing_services')]

    # Восстанавливаем старые колонки если их нет
    if 'version' not in columns:
        op.add_column('testing_services', sa.Column('version', sa.String(50)))
    if 'tech_stack' not in columns:
        op.add_column('testing_services', sa.Column(
            'tech_stack', sa.String(500)))
    if 'documentation_url' not in columns:
        op.add_column('testing_services', sa.Column(
            'documentation_url', sa.String(500)))
    if 'responsible_person' not in columns:
        op.add_column('testing_services', sa.Column(
            'responsible_person', sa.String(255)))
    if 'contact_email' not in columns:
        op.add_column('testing_services', sa.Column(
            'contact_email', sa.String(255)))

    # Удаляем новые колонки
    if 'custom_fields' in columns:
        op.drop_column('testing_services', 'custom_fields')
    if 'icon' in columns:
        op.drop_column('testing_services', 'icon')
