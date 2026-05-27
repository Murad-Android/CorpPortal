# -*- coding: utf-8 -*-
"""
Миграция: Добавление таблицы благодарностей
"""
import sqlite3
import os


def upgrade():
    """Создание таблицы thanks"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(__file__))), 'instance', 'portal.db')

    if not os.path.exists(db_path):
        print(f"База данных не найдена: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Проверяем, существует ли таблица
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='thanks'")
    if cursor.fetchone():
        print("Таблица thanks уже существует")
        conn.close()
        return

    # Создаём таблицу
    cursor.execute('''
        CREATE TABLE thanks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER NOT NULL,
            to_user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (from_user_id) REFERENCES users(id),
            FOREIGN KEY (to_user_id) REFERENCES users(id)
        )
    ''')

    # Создаём индексы
    cursor.execute('CREATE INDEX idx_thanks_to_user ON thanks(to_user_id)')
    cursor.execute('CREATE INDEX idx_thanks_from_user ON thanks(from_user_id)')

    conn.commit()
    conn.close()

    print("✓ Таблица thanks создана успешно")


if __name__ == '__main__':
    upgrade()
