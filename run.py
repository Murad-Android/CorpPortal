# -*- coding: utf-8 -*-
"""
Точка входа для запуска приложения
"""
from app import create_app
from asgiref.wsgi import WsgiToAsgi
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Создаём Flask приложение
flask_app = create_app(os.getenv('FLASK_ENV', 'production'))

# Оборачиваем в ASGI для uvicorn
app = WsgiToAsgi(flask_app)
