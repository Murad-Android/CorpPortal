# -*- coding: utf-8 -*-
"""
Скрипт сборки релиза корпоративного портала
Компилирует Python код в байткод и упаковывает для распространения
"""
import os
import sys
import shutil
import py_compile
import compileall
import zipfile
from datetime import datetime

# Конфигурация
RELEASE_DIR = 'release_build'
PROJECT_NAME = 'corporate_portal'

# Файлы и папки для копирования (без компиляции)
COPY_AS_IS = [
    'app/templates',
    'app/static',
    'static',
    'instance',
    'migrations',
    'requirements.txt',
    'config.py',
]

# Папки с Python кодом для компиляции
COMPILE_DIRS = [
    'app',
    'app/blueprints',
    'app/models',
    'app/services',
]

# Файлы для компиляции в корне
COMPILE_FILES = [
    'run.py',
    'config.py',
]

# Исключить из сборки
EXCLUDE = [
    '__pycache__',
    '.git',
    '.vscode',
    '.kiro',
    'venv',
    'release_build',
    '*.pyc',
    '*.pyo',
    '.env',
    '*.db',
    'build_release.py',
    'update_*.py',
    'test_*.py',
    'simulate_*.py',
    'reset_*.py',
    'init_*.py',
]


def clean_release_dir():
    """Очистка папки релиза"""
    if os.path.exists(RELEASE_DIR):
        shutil.rmtree(RELEASE_DIR)
    os.makedirs(RELEASE_DIR)
    print(f"✓ Создана папка {RELEASE_DIR}")


def should_exclude(path):
    """Проверка, нужно ли исключить файл/папку"""
    name = os.path.basename(path)
    for pattern in EXCLUDE:
        if pattern.startswith('*'):
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern:
            return True
    return False


def compile_python_file(src_path, dest_dir):
    """Компиляция одного Python файла в .pyc"""
    if not src_path.endswith('.py'):
        return False

    filename = os.path.basename(src_path)

    # Создаём директорию назначения
    os.makedirs(dest_dir, exist_ok=True)

    # Компилируем в .pyc
    try:
        # Путь к .pyc файлу
        pyc_name = filename[:-3] + '.pyc'
        pyc_path = os.path.join(dest_dir, pyc_name)

        # Компилируем
        py_compile.compile(src_path, cfile=pyc_path, doraise=True, optimize=2)
        return True
    except py_compile.PyCompileError as e:
        print(f"  ✗ Ошибка компиляции {src_path}: {e}")
        return False


def copy_directory(src, dest, compile_py=False):
    """Копирование директории с опциональной компиляцией Python"""
    if not os.path.exists(src):
        return

    for item in os.listdir(src):
        src_path = os.path.join(src, item)
        dest_path = os.path.join(dest, item)

        if should_exclude(src_path):
            continue

        if os.path.isdir(src_path):
            if item == '__pycache__':
                continue
            copy_directory(src_path, dest_path, compile_py)
        else:
            os.makedirs(dest, exist_ok=True)

            if compile_py and item.endswith('.py'):
                # Компилируем Python файлы
                compile_python_file(src_path, dest)
            else:
                # Копируем как есть
                shutil.copy2(src_path, dest_path)


def build_release():
    """Основная функция сборки"""
    print("=" * 50)
    print("  СБОРКА РЕЛИЗА КОРПОРАТИВНОГО ПОРТАЛА")
    print("=" * 50)
    print()

    # 1. Очистка
    clean_release_dir()

    # 2. Копируем структуру app с компиляцией Python
    print("\n📦 Компиляция Python кода...")

    app_src = 'app'
    app_dest = os.path.join(RELEASE_DIR, 'app')

    # Компилируем app/__init__.py
    if os.path.exists(os.path.join(app_src, '__init__.py')):
        compile_python_file(os.path.join(app_src, '__init__.py'), app_dest)
        print(f"  ✓ app/__init__.py")

    # Компилируем blueprints
    blueprints_src = os.path.join(app_src, 'blueprints')
    blueprints_dest = os.path.join(app_dest, 'blueprints')
    if os.path.exists(blueprints_src):
        for f in os.listdir(blueprints_src):
            if f.endswith('.py') and not should_exclude(f):
                if compile_python_file(os.path.join(blueprints_src, f), blueprints_dest):
                    print(f"  ✓ app/blueprints/{f}")

    # Компилируем models
    models_src = os.path.join(app_src, 'models')
    models_dest = os.path.join(app_dest, 'models')
    if os.path.exists(models_src):
        for f in os.listdir(models_src):
            if f.endswith('.py') and not should_exclude(f):
                if compile_python_file(os.path.join(models_src, f), models_dest):
                    print(f"  ✓ app/models/{f}")

    # Компилируем services
    services_src = os.path.join(app_src, 'services')
    services_dest = os.path.join(app_dest, 'services')
    if os.path.exists(services_src):
        for f in os.listdir(services_src):
            if f.endswith('.py') and not should_exclude(f):
                if compile_python_file(os.path.join(services_src, f), services_dest):
                    print(f"  ✓ app/services/{f}")

    # 3. Копируем templates и static
    print("\n📁 Копирование шаблонов и статики...")

    templates_src = os.path.join(app_src, 'templates')
    templates_dest = os.path.join(app_dest, 'templates')
    if os.path.exists(templates_src):
        shutil.copytree(templates_src, templates_dest)
        print(f"  ✓ app/templates/")

    static_src = os.path.join(app_src, 'static')
    static_dest = os.path.join(app_dest, 'static')
    if os.path.exists(static_src):
        shutil.copytree(static_src, static_dest,
                        ignore=shutil.ignore_patterns(
                            '*.db', '__pycache__',
                            'messenger/avatars/*', 'messenger/files/*',
                            'messenger/voice/*', 'staff_photo/*',
                            'uploads/news/content/*', 'uploads/referrals/*',
                            'uploads/services/*'))
        print(f"  ✓ app/static/")

    # 4. Копируем корневую статику
    if os.path.exists('static'):
        shutil.copytree('static', os.path.join(RELEASE_DIR, 'static'),
                        ignore=shutil.ignore_patterns('*.db', '__pycache__'))
        print(f"  ✓ static/")

    # 5. Копируем migrations
    if os.path.exists('migrations'):
        shutil.copytree('migrations', os.path.join(RELEASE_DIR, 'migrations'),
                        ignore=shutil.ignore_patterns('__pycache__'))
        print(f"  ✓ migrations/")

    # 6. Компилируем корневые файлы
    print("\n📦 Компиляция корневых файлов...")

    for f in COMPILE_FILES:
        if os.path.exists(f):
            if compile_python_file(f, RELEASE_DIR):
                print(f"  ✓ {f}")

    # 7. Копируем requirements.txt
    if os.path.exists('requirements.txt'):
        shutil.copy2('requirements.txt', os.path.join(
            RELEASE_DIR, 'requirements.txt'))
        print(f"  ✓ requirements.txt")

    # 7.1. Копируем server_config.ini
    if os.path.exists('server_config.ini'):
        shutil.copy2('server_config.ini', os.path.join(
            RELEASE_DIR, 'server_config.ini'))
        print(f"  ✓ server_config.ini")

    # 8. Создаём пустую папку instance
    os.makedirs(os.path.join(RELEASE_DIR, 'instance'), exist_ok=True)
    print(f"  ✓ instance/ (пустая)")

    # 9. Создаём загрузчик
    create_loader()

    # 10. Создаём README для релиза
    create_readme()

    # 11. Создаём ZIP архив
    create_zip()

    print("\n" + "=" * 50)
    print("  ✓ СБОРКА ЗАВЕРШЕНА!")
    print("=" * 50)
    print(f"\nРелиз находится в папке: {RELEASE_DIR}/")
    print(f"ZIP архив: {RELEASE_DIR}.zip")


def create_loader():
    """Создание загрузчика для запуска через uvicorn"""
    loader_content = '''# -*- coding: utf-8 -*-
"""
Корпоративный портал - Загрузчик (uvicorn)
"""
import sys
import os
import configparser

# Добавляем текущую директорию в путь
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

def load_server_config():
    """Загрузка настроек сервера"""
    config = configparser.ConfigParser()
    config_path = os.path.join(base_dir, 'server_config.ini')
    
    settings = {
        'host': '0.0.0.0',
        'port': 5000,
        'workers': 4,
        'debug': False,
        'ssl_enabled': False,
        'ssl_cert': None,
        'ssl_key': None,
    }
    
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        
        if config.has_section('server'):
            settings['host'] = config.get('server', 'host', fallback='0.0.0.0')
            settings['port'] = config.getint('server', 'port', fallback=5000)
            settings['workers'] = config.getint('server', 'workers', fallback=4)
            settings['debug'] = config.getboolean('server', 'debug', fallback=False)
        
        if config.has_section('ssl'):
            settings['ssl_enabled'] = config.getboolean('ssl', 'enabled', fallback=False)
            settings['ssl_cert'] = config.get('ssl', 'cert_file', fallback=None)
            settings['ssl_key'] = config.get('ssl', 'key_file', fallback=None)
        
        print(f"[CONFIG] Загружены настройки из {config_path}")
    
    return settings

if __name__ == '__main__':
    import importlib.util
    
    # Загружаем config
    for ext in ['.py', '.pyc']:
        config_path = os.path.join(base_dir, f'config{ext}')
        if os.path.exists(config_path):
            spec = importlib.util.spec_from_file_location('config', config_path)
            config_module = importlib.util.module_from_spec(spec)
            sys.modules['config'] = config_module
            spec.loader.exec_module(config_module)
            break
    
    # Загружаем run для получения app
    run_found = False
    for ext in ['.py', '.pyc']:
        run_path = os.path.join(base_dir, f'run{ext}')
        if os.path.exists(run_path):
            spec = importlib.util.spec_from_file_location('run', run_path)
            run_module = importlib.util.module_from_spec(spec)
            sys.modules['run'] = run_module
            spec.loader.exec_module(run_module)
            run_found = True
            break
    
    if not run_found:
        print("Ошибка: run.py не найден")
        sys.exit(1)
    
    # Получаем настройки
    server_config = load_server_config()
    
    host = server_config['host']
    port = server_config['port']
    workers = server_config['workers']
    debug = server_config['debug']
    
    print()
    print("=" * 50)
    print("  КОРПОРАТИВНЫЙ ПОРТАЛ")
    print("=" * 50)
    protocol = 'https' if server_config['ssl_enabled'] else 'http'
    print(f"  Адрес: {protocol}://{host}:{port}")
    print(f"  Воркеры: {workers}")
    print(f"  Режим: {'Отладка' if debug else 'Продакшен'}")
    print("=" * 50)
    print()
    
    # Запуск через uvicorn
    import uvicorn
    
    uvicorn_config = {
        'app': 'run:app',
        'host': host,
        'port': port,
        'workers': 1 if debug else workers,
        'reload': debug,
        'access_log': True,
    }
    
    # SSL
    if server_config['ssl_enabled']:
        cert = server_config['ssl_cert']
        key = server_config['ssl_key']
        if cert and key:
            cert_path = os.path.join(base_dir, cert)
            key_path = os.path.join(base_dir, key)
            if os.path.exists(cert_path) and os.path.exists(key_path):
                uvicorn_config['ssl_certfile'] = cert_path
                uvicorn_config['ssl_keyfile'] = key_path
                print("[SSL] HTTPS включён")
    
    uvicorn.run(**uvicorn_config)
'''

    loader_path = os.path.join(RELEASE_DIR, 'start.py')
    with open(loader_path, 'w', encoding='utf-8') as f:
        f.write(loader_content)
    print(f"  ✓ start.py (загрузчик)")


def create_readme():
    """Создание README для релиза"""
    readme_content = f'''# Корпоративный портал

## Установка

1. Установите Python 3.10 или выше
2. Создайте виртуальное окружение:
   ```
   python -m venv venv
   ```
3. Активируйте окружение:
   - Windows: `venv\\Scripts\\activate`
   - Linux/Mac: `source venv/bin/activate`
4. Установите зависимости:
   ```
   pip install -r requirements.txt
   ```

## Настройка

Отредактируйте файл `server_config.ini`:

```ini
[server]
host = 0.0.0.0      # IP-адрес (0.0.0.0 = все интерфейсы)
port = 5000         # Порт
workers = 4         # Количество воркеров
debug = False       # Режим отладки

[ssl]
enabled = False     # Включить HTTPS
cert_file = cert/certificate.crt
key_file = cert/private_key.pem

[app]
secret_key = ваш-секретный-ключ
```

## Запуск

```
python start.py
```

Сервер запустится через uvicorn (высокопроизводительный ASGI сервер).

Портал будет доступен по адресу, указанному в настройках.

## Первый вход

- Логин: admin
- Пароль: admin123

**Обязательно смените пароль после первого входа!**

---
Сборка: {datetime.now().strftime('%d.%m.%Y %H:%M')}
'''

    readme_path = os.path.join(RELEASE_DIR, 'README.md')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"  ✓ README.md")


def create_zip():
    """Создание ZIP архива"""
    print("\n📦 Создание ZIP архива...")

    zip_name = f'{RELEASE_DIR}.zip'

    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(RELEASE_DIR):
            # Исключаем __pycache__
            dirs[:] = [d for d in dirs if d != '__pycache__']

            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, RELEASE_DIR)
                # Без вложенной папки — файлы в корне архива
                zipf.write(file_path, arcname)

    print(f"  ✓ {zip_name}")


if __name__ == '__main__':
    build_release()
