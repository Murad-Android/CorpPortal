"""
Скрипт для создания таблиц внешнего вида сайта
"""
import sqlite3
import os

DB_PATH = 'instance/portal.db'


def update_database():
    if not os.path.exists(DB_PATH):
        print(f"База данных не найдена: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Создаём таблицу site_appearance
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_appearance (
            id INTEGER PRIMARY KEY,
            site_name VARCHAR(255) DEFAULT 'Корпоративный портал',
            primary_color VARCHAR(7) DEFAULT '#0078D7',
            secondary_color VARCHAR(7) DEFAULT '#005a9e',
            timezone VARCHAR(50) DEFAULT 'Europe/Moscow',
            updated_at DATETIME
        )
    """)
    print("Таблица site_appearance создана")

    # Создаём таблицу site_decorations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_decorations (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            decoration_type VARCHAR(50) NOT NULL,
            start_date DATE,
            end_date DATE,
            is_always_active BOOLEAN DEFAULT 0,
            is_enabled BOOLEAN DEFAULT 1,
            settings TEXT DEFAULT '{}',
            created_at DATETIME
        )
    """)
    print("Таблица site_decorations создана")

    # Создаём начальные настройки если их нет
    cursor.execute("SELECT COUNT(*) FROM site_appearance")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO site_appearance (site_name, primary_color, secondary_color, timezone)
            VALUES ('Корпоративный портал', '#0078D7', '#005a9e', 'Europe/Moscow')
        """)
        print("Созданы начальные настройки внешнего вида")

    conn.commit()
    conn.close()
    print("\nОбновление завершено!")


if __name__ == '__main__':
    update_database()
