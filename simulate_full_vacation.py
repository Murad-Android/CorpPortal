#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для симуляции использования всех дней отпуска (для тестирования)
"""
from app.models import User, UserVacationBalance
from app import create_app, db
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def simulate_full_vacation(username=None):
    """Установить использованные дни = всем доступным дням"""
    app = create_app()

    with app.app_context():
        if username:
            user = User.query.filter_by(username=username).first()
            if not user:
                print(f"Ошибка: Пользователь {username} не найден")
                return
        else:
            user = User.query.first()
            if not user:
                print("Ошибка: Нет пользователей в системе")
                return

        print(
            f"Симуляция использования всех дней отпуска для: {user.full_name}")

        # Получаем баланс
        balance = UserVacationBalance.get_or_create(user.id)

        print(f"\nДо симуляции:")
        print(
            f"  Ежегодный: {balance.annual_days_used}/{balance.annual_days_total}")
        print(
            f"  Day Off: {balance.dayoff_days_used}/{balance.dayoff_days_total}")

        # Устанавливаем использованные дни = всем доступным
        balance.annual_days_used = balance.annual_days_total
        balance.dayoff_days_used = balance.dayoff_days_total

        db.session.commit()

        print(f"\nПосле симуляции:")
        print(
            f"  Ежегодный: {balance.annual_days_used}/{balance.annual_days_total} (осталось: {balance.annual_days_remaining})")
        print(
            f"  Day Off: {balance.dayoff_days_used}/{balance.dayoff_days_total} (осталось: {balance.dayoff_days_remaining})")

        print("\nТеперь при создании заявки:")
        print("  - Ежегодный оплачиваемый будет ЗАБЛОКИРОВАН (серым)")
        print("  - Day Off будет ЗАБЛОКИРОВАН (серым)")
        print("  - Доступен только 'За свой счёт'")


if __name__ == '__main__':
    username = sys.argv[1] if len(sys.argv) > 1 else None
    simulate_full_vacation(username)
