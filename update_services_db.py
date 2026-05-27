"""
Скрипт для обновления структуры таблицы testing_services
Добавляет поддержку кастомных полей и иконок
"""
import sqlite3
import json
import os

DB_PATH = 'instance/portal.db'


def update_database():
    if not os.path.exists(DB_PATH):
        print(f"База данных не найдена: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получаем текущие колонки
    cursor.execute("PRAGMA table_info(testing_services)")
    columns = [col[1] for col in cursor.fetchall()]

    print(f"Текущие колонки: {columns}")

    # Добавляем custom_fields если не существует
    if 'custom_fields' not in columns:
        print("Добавляем колонку custom_fields...")
        cursor.execute(
            "ALTER TABLE testing_services ADD COLUMN custom_fields TEXT DEFAULT '[]'")

    # Добавляем icon если не существует
    if 'icon' not in columns:
        print("Добавляем колонку icon...")
        cursor.execute(
            "ALTER TABLE testing_services ADD COLUMN icon VARCHAR(50) DEFAULT 'server'")

    # Миграция данных из старых полей
    if 'version' in columns or 'tech_stack' in columns:
        print("Мигрируем данные из старых полей...")
        cursor.execute("""
            SELECT id, version, tech_stack, documentation_url, responsible_person, contact_email 
            FROM testing_services
        """)

        for row in cursor.fetchall():
            service_id = row[0]
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
                cursor.execute(
                    "UPDATE testing_services SET custom_fields = ? WHERE id = ?",
                    (json.dumps(custom_fields, ensure_ascii=False), service_id)
                )
                print(
                    f"  Сервис {service_id}: мигрировано {len(custom_fields)} полей")

    conn.commit()
    conn.close()

    print("\nОбновление завершено!")
    print("Теперь вы можете использовать гибкий конструктор сервисов.")


if __name__ == '__main__':
    update_database()
