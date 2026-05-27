# Корпоративный портал

Внутренний веб-портал компании на Flask. Включает управление сотрудниками, новости, заявки, опросы, тесты, мессенджер, хранилище паролей, систему отпусков, баг-трекер и диаграммы.

## Требования

- Python 3.10+
- SQLite (встроенная БД)

## Установка и запуск

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
python run.py
```

Портал запустится на `http://localhost:5000`

## Вход по умолчанию

- Логин: `admin`
- Пароль: `admin`

После первого входа смените пароль.

## Конфигурация

Основные параметры сервера задаются в `server_config.ini`:

- Адрес и порт
- Количество воркеров
- SSL-сертификаты
- Секретный ключ приложения

## Продакшен-запуск

```bash
python run.py
```

Запускает через uvicorn с настройками из `server_config.ini`.

## Сборка релиза

```bash
python build_release.py
```

Компилирует Python в .pyc, собирает шаблоны и статику в папку `release_build/`, создает ZIP-архив.

## Пересборка Tailwind CSS

```bash
tailwindcss.exe -i app/static/css/tailwind-input.css -o app/static/css/tailwind.min.css --minify
```

## Структура проекта

```
app/
  blueprints/     — маршруты (admin, auth, news, staff, messenger, vault, ...)
  models/         — модели SQLAlchemy
  services/       — сервисы (auth, email, encryption, scheduler)
  templates/      — Jinja2 шаблоны
  static/         — CSS, шрифты, Font Awesome, загрузки
migrations/       — миграции БД
Messanger/        — отдельное приложение мессенджера (standalone)
NotifyClient/     — клиент уведомлений (Electron)
ControlPanel2/    — панель управления (отдельный проект)
```

## Модули портала

| Путь | Описание |
|------|----------|
| `/` | Главная страница |
| `/admin` | Панель администратора |
| `/staff` | Справочник сотрудников |
| `/news` | Новости компании |
| `/vacancies` | Вакансии |
| `/security` | Центр безопасности |
| `/messenger` | Встроенный мессенджер |
| `/vault` | Хранилище паролей (AES-256) |
| `/requests/pass` | Заявка на пропуск |
| `/requests/order` | Заявка на заказ |
| `/vacations` | Система отпусков |
| `/surveys` | Опросы |
| `/tests` | Тесты и аттестации |
| `/testing` | Сервисы тестирования |
| `/tables` | Электронные таблицы |
| `/diagrams` | Диаграммы |
| `/bugs` | Баг-трекер |

## Ключевые возможности

- Аутентификация через LDAP/Active Directory или локальные учётные записи
- Ролевая система прав доступа с гранулярными разрешениями
- Хранилище паролей с AES-256-GCM шифрованием
- Система отпусков с лимитами, Day Off и согласованием
- Баг-трекер с проектами, ролями и workflow
- Приветственные анимации по времени суток
- Настраиваемый внешний вид (темы, декорации)
- Планировщик задач (синхронизация LDAP, уведомления)
- Встроенная документация для администраторов

## Документация

- [Руководство администратора](docs/admin.md)
- [Управление пользователями](docs/admin_users.md)
- [Управление контентом](docs/admin_content.md)
- [Настройки системы](docs/admin_settings.md)
- [Заявки и отпуска](docs/admin_requests.md)
- [Интеграции (LDAP, SMTP)](docs/admin_integrations.md)
- [Хранилище паролей](docs/password_vault.md)
- [Сервисы тестирования](docs/testing_services.md)
- [Система отпусков](docs/vacations.md)
- [Изображения в новостях](docs/news_images.md)

## Стек технологий

- Flask 3.0, Flask-SQLAlchemy, Flask-Login, Flask-Migrate
- Tailwind CSS (скомпилированный), Font Awesome 6.4
- SQLite, Alembic
- uvicorn (ASGI-сервер)
- PyCryptodome (AES-256 шифрование)
- ldap3 (интеграция с Active Directory)
- APScheduler (планировщик задач)
- Markdown (рендеринг контента)

## Лицензия

MIT License — свободное использование, включая коммерческое.
