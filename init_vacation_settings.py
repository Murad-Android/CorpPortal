#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для инициализации настроек отпусков
"""
from app.models import VacationSettings
from app import create_app, db
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def init_vacation_settings():
    """Инициализация настроек отпусков"""
    app = create_app()

    with app.app_context():
        # Создаем таблицы если их нет
        db.create_all()

        # Проверяем, существуют ли настройки
        settings = VacationSettings.query.first()

        if settings:
            print("OK Настройки отпусков уже существуют")
            print(f"  - Ежегодный отпуск: {settings.annual_days_default} дней")
            print(
                f"  - Day Off: {'включен' if settings.dayoff_enabled else 'выключен'}")
            if settings.dayoff_enabled:
                print(f"  - Дней Day Off: {settings.dayoff_days_limit}")
        else:
            # Создаем настройки по умолчанию
            settings = VacationSettings(
                annual_days_default=28,
                dayoff_enabled=False,
                dayoff_days_limit=0
            )
            db.session.add(settings)
            db.session.commit()
            print("OK Настройки отпусков созданы")
            print("  - Ежегодный отпуск: 28 дней (по умолчанию)")
            print("  - Day Off: выключен")
            print("")
            print("Для изменения настроек перейдите в админ-панель:")
            print("  Система -> Отпуска")


if __name__ == '__main__':
    init_vacation_settings()
