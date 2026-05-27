# -*- coding: utf-8 -*-
"""
Обновление сервера: загрузка ZIP, проверка, применение, перезапуск.
Целевая платформа: Windows.
"""
import os
import sys
import json
import shutil
import hashlib
import zipfile
import subprocess
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import db

server_update_bp = Blueprint('server_update', __name__)

SERVER_DIR = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
UPDATES_DIR = os.path.join(SERVER_DIR, 'updates')
BACKUP_DIR = os.path.join(SERVER_DIR, 'backups')

SKIP_PREFIXES = ('instance/', 'data/', 'logs/',
                 'backups/', 'updates/', 'venv/')
SKIP_EXTENSIONS = ('.db', '.log')


def _is_admin():
    return current_user.is_authenticated and current_user.role and current_user.role.name == 'admin'


def _file_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _should_skip(rel_path):
    """Файлы которые нельзя перезаписывать"""
    for prefix in SKIP_PREFIXES:
        if rel_path.startswith(prefix):
            return True
    for ext in SKIP_EXTENSIONS:
        if rel_path.endswith(ext):
            return True
    return False


class UpdateLog(db.Model):
    """Лог обновлений"""
    __tablename__ = 'update_logs'

    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(50))
    files_updated = db.Column(db.Integer, default=0)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    applied_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='success')
    details = db.Column(db.Text)


@server_update_bp.route('/')
@login_required
def index():
    if not _is_admin():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('main.index'))

    logs = UpdateLog.query.order_by(
        UpdateLog.applied_at.desc()).limit(20).all()

    # Проверяем есть ли pending обновление с результатами проверки
    pending = None
    pending_path = os.path.join(UPDATES_DIR, 'pending_update.zip')
    analysis_path = os.path.join(UPDATES_DIR, 'pending_analysis.json')
    if os.path.exists(pending_path) and os.path.exists(analysis_path):
        with open(analysis_path, 'r', encoding='utf-8') as f:
            pending = json.load(f)

    return render_template('admin/updates/index.html', logs=logs, pending=pending)


@server_update_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    """Загрузка ZIP — только проверка, без применения"""
    if not _is_admin():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('server_update.index'))

    file = request.files.get('update_file')
    if not file or not file.filename.endswith('.zip'):
        flash('Загрузите ZIP-файл', 'error')
        return redirect(url_for('server_update.index'))

    os.makedirs(UPDATES_DIR, exist_ok=True)
    zip_path = os.path.join(UPDATES_DIR, 'pending_update.zip')
    file.save(zip_path)

    # Анализ содержимого (только проверка, ничего не применяем)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            has_manifest = '_manifest.json' in names

            # Определяем общий корневой каталог (если все файлы в одной папке)
            root_prefix = ''
            non_dir_names = [n for n in names if not n.endswith('/')]
            if non_dir_names:
                first_parts = [n.split('/')[0] for n in non_dir_names]
                if len(set(first_parts)) == 1 and first_parts[0] + '/' in names:
                    root_prefix = first_parts[0] + '/'

            if has_manifest:
                manifest_key = root_prefix + \
                    '_manifest.json' if root_prefix and '_manifest.json' not in names else '_manifest.json'
                manifest = json.loads(zf.read(manifest_key))
            else:
                manifest = {}
                for n in names:
                    if not n.endswith('/'):
                        rel = n[len(root_prefix):] if root_prefix and n.startswith(
                            root_prefix) else n
                        if rel:
                            manifest[rel] = ''

        # Сравнение с текущими файлами
        new_files = []
        modified_files = []
        unchanged = 0
        skipped = []

        for rel_path, expected_hash in manifest.items():
            if rel_path == '_manifest.json':
                continue
            if _should_skip(rel_path):
                skipped.append(rel_path)
                continue

            local_path = os.path.join(
                SERVER_DIR, rel_path.replace('/', os.sep))
            if not os.path.exists(local_path):
                new_files.append(rel_path)
            elif expected_hash:
                current_hash = _file_hash(local_path)
                if current_hash != expected_hash:
                    modified_files.append(rel_path)
                else:
                    unchanged += 1
            else:
                modified_files.append(rel_path)

        # Сохраняем результат анализа
        analysis = {
            'filename': file.filename,
            'total_files': len(manifest) - (1 if has_manifest else 0),
            'new_files': new_files,
            'modified_files': modified_files,
            'unchanged': unchanged,
            'skipped': skipped,
            'root_prefix': root_prefix,
            'checked_at': datetime.now().strftime('%d.%m.%Y %H:%M'),
        }
        analysis_path = os.path.join(UPDATES_DIR, 'pending_analysis.json')
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

        flash(
            f'Проверка завершена: {len(new_files)} новых, {len(modified_files)} изменённых, {unchanged} без изменений', 'success')

    except zipfile.BadZipFile:
        os.remove(zip_path)
        flash('Некорректный ZIP-файл', 'error')
    except Exception as e:
        os.remove(zip_path)
        flash(f'Ошибка при проверке: {e}', 'error')

    return redirect(url_for('server_update.index'))


@server_update_bp.route('/apply', methods=['POST'])
@login_required
def apply():
    """Применить обновление и автоматически перезапустить сервер"""
    if not _is_admin():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('server_update.index'))

    zip_path = os.path.join(UPDATES_DIR, 'pending_update.zip')
    if not os.path.exists(zip_path):
        flash('Нет загруженного обновления. Сначала загрузите ZIP.', 'error')
        return redirect(url_for('server_update.index'))

    # Бэкап текущих файлов
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_name = f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    applied_files = []
    try:
        # Читаем root_prefix из анализа
        root_prefix = ''
        analysis_path = os.path.join(UPDATES_DIR, 'pending_analysis.json')
        if os.path.exists(analysis_path):
            with open(analysis_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
                root_prefix = analysis_data.get('root_prefix', '')

        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = [n for n in zf.namelist() if not n.endswith('/')]

            # Бэкап затрагиваемых файлов
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zf:
                for name in names:
                    # Убираем root_prefix для получения реального пути
                    rel_path = name[len(root_prefix):] if root_prefix and name.startswith(
                        root_prefix) else name
                    if not rel_path or rel_path == '_manifest.json':
                        continue
                    if _should_skip(rel_path):
                        continue
                    local_path = os.path.join(
                        SERVER_DIR, rel_path.replace('/', os.sep))
                    if os.path.exists(local_path):
                        backup_zf.write(local_path, rel_path)

            # Применяем обновление
            for name in names:
                rel_path = name[len(root_prefix):] if root_prefix and name.startswith(
                    root_prefix) else name
                if not rel_path or rel_path == '_manifest.json':
                    continue
                if _should_skip(rel_path):
                    continue
                local_path = os.path.join(
                    SERVER_DIR, rel_path.replace('/', os.sep))
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with zf.open(name) as src, open(local_path, 'wb') as dst:
                    dst.write(src.read())
                applied_files.append(rel_path)

        # Логируем
        version = request.form.get('version', 'unknown')
        log = UpdateLog(
            version=version,
            files_updated=len(applied_files),
            applied_by=current_user.id,
            status='success',
            details=json.dumps(applied_files[:100], ensure_ascii=False)
        )
        db.session.add(log)
        db.session.commit()

        # Удаляем pending файлы
        os.remove(zip_path)
        analysis_path = os.path.join(UPDATES_DIR, 'pending_analysis.json')
        if os.path.exists(analysis_path):
            os.remove(analysis_path)

        # Автоматический перезапуск сервера
        _restart_server()

        flash(
            f'Обновление применено: {len(applied_files)} файлов. Сервер перезапускается...', 'success')

    except Exception as e:
        log = UpdateLog(
            version=request.form.get('version', 'unknown'),
            files_updated=0,
            applied_by=current_user.id,
            status='failed',
            details=str(e)
        )
        db.session.add(log)
        db.session.commit()
        flash(f'Ошибка обновления: {e}', 'error')

    return redirect(url_for('server_update.index'))


@server_update_bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    """Отменить загруженное обновление"""
    if not _is_admin():
        flash('Доступ запрещен', 'error')
        return redirect(url_for('server_update.index'))

    zip_path = os.path.join(UPDATES_DIR, 'pending_update.zip')
    analysis_path = os.path.join(UPDATES_DIR, 'pending_analysis.json')
    if os.path.exists(zip_path):
        os.remove(zip_path)
    if os.path.exists(analysis_path):
        os.remove(analysis_path)

    flash('Обновление отменено', 'success')
    return redirect(url_for('server_update.index'))


@server_update_bp.route('/restart', methods=['POST'])
@login_required
def restart():
    """Ручной перезапуск сервера"""
    if not _is_admin():
        return jsonify({'error': 'Доступ запрещен'}), 403

    _restart_server()
    return jsonify({'status': 'restarting', 'message': 'Сервер перезапускается...'})


def _restart_server():
    """
    Перезапуск сервера на Windows.
    Стратегия: убиваем дерево процессов текущего uvicorn parent,
    затем запускаем сервер заново в том же окне консоли.
    """
    restart_script = os.path.join(SERVER_DIR, '_restart.bat')

    # Определяем entry point
    start_script = os.path.join(SERVER_DIR, 'start.py')
    run_script = os.path.join(SERVER_DIR, 'run.py')
    entry = start_script if os.path.exists(start_script) else run_script

    # Читаем порт из конфига
    port = 80
    try:
        import configparser
        cfg = configparser.ConfigParser()
        cfg_path = os.path.join(SERVER_DIR, 'server_config.ini')
        if os.path.exists(cfg_path):
            cfg.read(cfg_path, encoding='utf-8')
            port = cfg.getint('server', 'port', fallback=80)
    except Exception:
        pass

    # Получаем PID parent-процесса uvicorn (тот, что запустил воркеры)
    # os.getpid() — текущий воркер, но нам нужен parent
    parent_pid = os.getppid()

    with open(restart_script, 'w', encoding='utf-8') as f:
        f.write('@echo off\n')
        f.write('chcp 65001 >nul\n')
        f.write(f'cd /d "{SERVER_DIR}"\n')
        f.write('echo [RESTART] Остановка сервера...\n')
        # Убиваем дерево процессов parent uvicorn (parent + все воркеры)
        f.write(f'taskkill /F /T /PID {parent_pid} >nul 2>&1\n')
        # Дополнительно: убиваем всё что слушает наш порт (на случай если PID не сработал)
        f.write(
            f'for /f "tokens=5" %%a in (\'netstat -aon ^| findstr ":{port}" ^| findstr "LISTENING"\') do taskkill /F /PID %%a >nul 2>&1\n')
        f.write('timeout /t 2 /nobreak >nul\n')
        f.write('echo [RESTART] Запуск сервера...\n')
        # Запускаем сервер БЕЗ нового окна — в текущей консоли
        f.write(f'python "{entry}"\n')
        f.write('del "%~f0"\n')

    # Запускаем bat отдельным процессом, который переживёт смерть текущего
    subprocess.Popen(
        ['cmd', '/c', restart_script],
        cwd=SERVER_DIR,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True
    )
