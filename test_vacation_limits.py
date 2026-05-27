#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для тестирования лимитов отпусков
"""
from app.models import User, VacationSettings, UserVacationBalance
from app import create_app, db
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_vacation_limits():
    """Тестирование лимитов отпусков"""
    app = create_app()

    with app.app_context():
        # Получаем настройки
        settings = VacationSettings.get_settings()
        print("=== Настройки отпусков ===")
        print(f"Ежегодный отпуск: {settings.annual_days_default} дней")
        print(
            f"Day Off: {'включен' if settings.dayoff_enabled else 'выключен'}")
        if settings.dayoff_enabled:
            print(f"Дней Day Off: {settings.dayoff_days_limit}")
        print()

        # Получаем первого пользователя для теста
        user = User.query.first()
        if not user:
            print("Ошибка: Нет пользователей в системе")
            return

        print(f"=== Тестирование для пользователя: {user.full_name} ===")

        # Получаем баланс
        balance = UserVacationBalance.get_or_create(user.id)

        print(f"\nБаланс отпускных дней:")
        print(f"  Ежегодный оплачиваемый:")
        print(f"    - Всего: {balance.annual_days_total} дней")
        print(f"    - Использовано: {balance.annual_days_used} дней")
        print(f"    - Осталось: {balance.annual_days_remaining} дней")

        if settings.dayoff_enabled:
            print(f"  Day Off:")
            print(f"    - Всего: {balance.dayoff_days_total} дней")
            print(f"    - Использовано: {balance.dayoff_days_used} дней")
            print(f"    - Осталось: {balance.dayoff_days_remaining} дней")

        print("\n=== Доступные типы отпуска ===")

        # Проверяем доступность типов
        if balance.annual_days_remaining > 0:
            print(
                f"✓ Ежегодный оплачиваемый (доступно {balance.annual_days_remaining} дн.)")
        else:
            print("✗ Ежегодный оплачиваемый (дни закончились)")

        if settings.dayoff_enabled:
            if balance.dayoff_days_remaining > 0:
                print(
                    f"✓ Day Off (доступно {balance.dayoff_days_remaining} дн.)")
            else:
                print("✗ Day Off (дни закончились)")

        print("✓ За свой счёт (всегда доступен)")

        print("\n=== Тест завершен ===")


if __name__ == '__main__':
    test_vacation_limits()
