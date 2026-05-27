# -*- coding: utf-8 -*-
"""
Скрипт для добавления поля employment_status и исправления меню
"""
import sqlite3
import os


def update_database():
    db_path = 'instance/portal.db'

    if not os.path.exists(db_path):
        print(f"База данных не найдена: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Проверяем, есть ли колонка employment_status
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'employment_status' not in columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN employment_status VARCHAR(20) DEFAULT 'working'")
        conn.commit()
        print("✓ Добавлена колонка employment_status")
    else:
        print("✓ Колонка employment_status уже существует")

    # Исправляем название пункта меню "Отпуска"
    cursor.execute(
        "UPDATE menu_items SET title = 'Отпуска' WHERE name = 'vacations'")
    conn.commit()
    print("✓ Исправлено название меню 'Отпуска'")

    conn.close()
    print("\n✓ Обновление завершено!")


if __name__ == '__main__':
    update_database()
