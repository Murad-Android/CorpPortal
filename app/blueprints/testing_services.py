"""
Blueprint сервисов тестирования с конструктором полей
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import TestingService, TestingServiceLog
from datetime import datetime
import os
import uuid
import json

testing_bp = Blueprint('testing', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def log_service_action(service_id, action, details=None):
    """Логирование действий с сервисами"""
    log = TestingServiceLog(
        service_id=service_id,
        user_id=current_user.id,
        action=action,
        details=details,
        ip_address=request.remote_addr,
        timestamp=datetime.utcnow()
    )
    db.session.add(log)
    db.session.commit()


@testing_bp.route('/')
@login_required
def index():
    """Список сервисов"""
    if not (current_user.is_admin or current_user.has_permission('testing_services_view')):
        flash('У вас нет доступа к сервисам тестирования', 'error')
        return redirect(url_for('main.index'))

    services = TestingService.query.order_by(
        TestingService.is_active.desc(),
        TestingService.environment,
        TestingService.name
    ).all()

    return render_template('testing/index.html', services=services)


@testing_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Создание сервиса"""
    if not (current_user.is_admin or current_user.has_permission('testing_services_create')):
        flash('У вас нет прав на создание сервисов', 'error')
        return redirect(url_for('testing.index'))

    if request.method == 'POST':
        # Собираем кастомные поля
        custom_fields = []
        field_names = request.form.getlist('field_name[]')
        field_values = request.form.getlist('field_value[]')
        field_types = request.form.getlist('field_type[]')
        field_icons = request.form.getlist('field_icon[]')

        for i in range(len(field_names)):
            if field_names[i].strip():
                custom_fields.append({
                    'name': field_names[i].strip(),
                    'value': field_values[i].strip() if i < len(field_values) else '',
                    'type': field_types[i] if i < len(field_types) else 'text',
                    'icon': field_icons[i] if i < len(field_icons) else ''
                })

        service = TestingService(
            name=request.form.get('name', '').strip(),
            description=request.form.get('description', '').strip(),
            url=request.form.get('url', '').strip(),
            environment=request.form.get('environment', '').strip(),
            icon=request.form.get('icon', 'server').strip(),
            is_active=request.form.get('is_active') == 'on',
            is_available=request.form.get('is_available') == 'on',
            created_by_id=current_user.id
        )
        service.set_custom_fields(custom_fields)

        db.session.add(service)
        db.session.commit()

        log_service_action(service.id, 'create',
                           f'Создан сервис: {service.name}')

        flash('Сервис создан', 'success')
        return redirect(url_for('testing.index'))

    return render_template('testing/form.html', service=None)


@testing_bp.route('/<int:id>')
@login_required
def view(id):
    """Просмотр сервиса"""
    if not (current_user.is_admin or current_user.has_permission('testing_services_view')):
        flash('У вас нет доступа', 'error')
        return redirect(url_for('main.index'))

    service = TestingService.query.get_or_404(id)
    log_service_action(service.id, 'view')

    return render_template('testing/view.html', service=service)


@testing_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Редактирование сервиса"""
    if not (current_user.is_admin or current_user.has_permission('testing_services_edit')):
        flash('У вас нет прав на редактирование', 'error')
        return redirect(url_for('testing.index'))

    service = TestingService.query.get_or_404(id)

    if request.method == 'POST':
        # Собираем кастомные поля
        custom_fields = []
        field_names = request.form.getlist('field_name[]')
        field_values = request.form.getlist('field_value[]')
        field_types = request.form.getlist('field_type[]')
        field_icons = request.form.getlist('field_icon[]')

        for i in range(len(field_names)):
            if field_names[i].strip():
                custom_fields.append({
                    'name': field_names[i].strip(),
                    'value': field_values[i].strip() if i < len(field_values) else '',
                    'type': field_types[i] if i < len(field_types) else 'text',
                    'icon': field_icons[i] if i < len(field_icons) else ''
                })

        service.name = request.form.get('name', '').strip()
        service.description = request.form.get('description', '').strip()
        service.url = request.form.get('url', '').strip()
        service.environment = request.form.get('environment', '').strip()
        service.icon = request.form.get('icon', 'server').strip()
        service.is_active = request.form.get('is_active') == 'on'
        service.is_available = request.form.get('is_available') == 'on'
        service.set_custom_fields(custom_fields)

        db.session.commit()

        log_service_action(service.id, 'edit',
                           f'Обновлен сервис: {service.name}')

        flash('Сервис обновлен', 'success')
        return redirect(url_for('testing.view', id=id))

    return render_template('testing/form.html', service=service)


@testing_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Удаление сервиса"""
    if not (current_user.is_admin or current_user.has_permission('testing_services_delete')):
        flash('У вас нет прав на удаление', 'error')
        return redirect(url_for('testing.index'))

    service = TestingService.query.get_or_404(id)

    log_service_action(service.id, 'delete', f'Удален сервис: {service.name}')

    db.session.delete(service)
    db.session.commit()

    flash('Сервис удален', 'success')
    return redirect(url_for('testing.index'))


@testing_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
def toggle(id):
    """Включение/выключение сервиса"""
    if not (current_user.is_admin or current_user.has_permission('testing_services_toggle')):
        return jsonify({'success': False, 'error': 'Нет прав'}), 403

    service = TestingService.query.get_or_404(id)
    service.is_active = not service.is_active
    db.session.commit()

    status = 'включен' if service.is_active else 'выключен'
    log_service_action(service.id, 'toggle', f'Сервис {status}')

    return jsonify({
        'success': True,
        'is_active': service.is_active,
        'message': f'Сервис {status}'
    })


@testing_bp.route('/<int:id>/access', methods=['POST'])
@login_required
def access(id):
    """Логирование доступа к сервису"""
    service = TestingService.query.get_or_404(id)

    if not service.is_active:
        return jsonify({'success': False, 'error': 'Сервис отключен'}), 403

    log_service_action(service.id, 'access', f'Переход на {service.url}')

    return jsonify({'success': True, 'url': service.url})


@testing_bp.route('/upload-image', methods=['POST'])
@login_required
def upload_image():
    """Загрузка изображения для описания сервиса"""
    if not (current_user.is_admin or current_user.has_permission('testing_services_create')
            or current_user.has_permission('testing_services_edit')):
        return jsonify({'success': False, 'error': 'Нет прав'}), 403

    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'Файл не найден'}), 400

    file = request.files['image']
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'Файл не выбран'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Недопустимый формат файла'}), 400

    try:
        # Создаем папку если не существует
        upload_folder = os.path.join(
            current_app.static_folder, 'uploads', 'services')
        os.makedirs(upload_folder, exist_ok=True)

        # Генерируем уникальное имя файла
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(upload_folder, filename)

        file.save(filepath)

        url = url_for('static', filename=f'uploads/services/{filename}')
        return jsonify({'success': True, 'url': url, 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
