"""
Blueprint настройки внешнего вида сайта
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import SiteAppearance, SiteDecoration
from datetime import datetime, date
import pytz

appearance_bp = Blueprint('appearance', __name__)


def admin_required(f):
    """Декоратор проверки прав администратора"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin and not current_user.has_permission('settings_general'):
            flash('Недостаточно прав', 'error')
            return redirect(url_for('admin.index'))
        return f(*args, **kwargs)
    return decorated_function


# === Часовой пояс ===

@appearance_bp.route('/timezone', methods=['GET', 'POST'])
@login_required
@admin_required
def timezone():
    """Настройка часового пояса"""
    settings = SiteAppearance.get_settings()

    if request.method == 'POST':
        settings.timezone = request.form.get('timezone', 'Europe/Moscow')
        db.session.commit()
        flash('Часовой пояс сохранён', 'success')
        return redirect(url_for('appearance.timezone'))

    # Список часовых поясов
    timezones = [
        ('Europe/Moscow', 'Москва (UTC+3)'),
        ('Europe/Kaliningrad', 'Калининград (UTC+2)'),
        ('Europe/Samara', 'Самара (UTC+4)'),
        ('Asia/Yekaterinburg', 'Екатеринбург (UTC+5)'),
        ('Asia/Omsk', 'Омск (UTC+6)'),
        ('Asia/Krasnoyarsk', 'Красноярск (UTC+7)'),
        ('Asia/Irkutsk', 'Иркутск (UTC+8)'),
        ('Asia/Yakutsk', 'Якутск (UTC+9)'),
        ('Asia/Vladivostok', 'Владивосток (UTC+10)'),
        ('Asia/Magadan', 'Магадан (UTC+11)'),
        ('Asia/Kamchatka', 'Камчатка (UTC+12)'),
        ('UTC', 'UTC'),
        ('Europe/London', 'Лондон (UTC+0/+1)'),
        ('Europe/Berlin', 'Берлин (UTC+1/+2)'),
        ('America/New_York', 'Нью-Йорк (UTC-5/-4)'),
        ('Asia/Dubai', 'Дубай (UTC+4)'),
        ('Asia/Shanghai', 'Шанхай (UTC+8)'),
        ('Asia/Tokyo', 'Токио (UTC+9)'),
    ]

    # Текущее время в выбранном часовом поясе
    try:
        tz = pytz.timezone(settings.timezone)
        current_time = datetime.now(tz).strftime('%d.%m.%Y %H:%M:%S')
    except:
        current_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

    return render_template('admin/appearance/timezone.html',
                           settings=settings,
                           timezones=timezones,
                           current_time=current_time)


# === Внешний вид ===

@appearance_bp.route('/design', methods=['GET', 'POST'])
@login_required
@admin_required
def design():
    """Настройка дизайна сайта"""
    settings = SiteAppearance.get_settings()

    if request.method == 'POST':
        settings.site_name = request.form.get(
            'site_name', 'Корпоративный портал')
        settings.primary_color = request.form.get('primary_color', '#0078D7')
        settings.secondary_color = request.form.get(
            'secondary_color', '#005a9e')
        db.session.commit()
        flash('Настройки дизайна сохранены', 'success')
        return redirect(url_for('appearance.design'))

    return render_template('admin/appearance/design.html', settings=settings)


# === Украшения ===

@appearance_bp.route('/decorations')
@login_required
@admin_required
def decorations():
    """Список украшений"""
    decorations = SiteDecoration.query.order_by(SiteDecoration.id.desc()).all()
    decoration_types = SiteDecoration.DECORATION_TYPES
    return render_template('admin/appearance/decorations.html',
                           decorations=decorations,
                           decoration_types=decoration_types)


@appearance_bp.route('/decorations/create', methods=['GET', 'POST'])
@login_required
@admin_required
def decoration_create():
    """Создание украшения"""
    if request.method == 'POST':
        decoration = SiteDecoration(
            name=request.form.get('name', '').strip(),
            decoration_type=request.form.get('decoration_type'),
            position=request.form.get('position', 'above'),
            is_always_active=request.form.get('is_always_active') == 'on',
            is_enabled=request.form.get('is_enabled') == 'on'
        )

        # Даты
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        if start_date:
            decoration.start_date = datetime.strptime(
                start_date, '%Y-%m-%d').date()
        if end_date:
            decoration.end_date = datetime.strptime(
                end_date, '%Y-%m-%d').date()

        # Дополнительные настройки
        settings = {
            'speed': request.form.get('speed', '500'),
        }
        # Цвет фона гирлянды
        if request.form.get('use_bg_color') == 'on':
            settings['bg_color'] = request.form.get('bg_color', '#1a1a2e')
        # Кастомный курсор
        cursor_type = request.form.get('cursor_type', 'default')
        if cursor_type != 'default':
            settings['cursor_type'] = cursor_type
        decoration.set_settings(settings)

        db.session.add(decoration)
        db.session.commit()

        flash('Украшение создано', 'success')
        return redirect(url_for('appearance.decorations'))

    decoration_types = SiteDecoration.DECORATION_TYPES
    cursor_types = SiteDecoration.CURSOR_TYPES
    return render_template('admin/appearance/decoration_form.html',
                           decoration=None,
                           decoration_types=decoration_types,
                           cursor_types=cursor_types)


@appearance_bp.route('/decorations/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def decoration_edit(id):
    """Редактирование украшения"""
    decoration = SiteDecoration.query.get_or_404(id)

    if request.method == 'POST':
        decoration.name = request.form.get('name', '').strip()
        decoration.decoration_type = request.form.get('decoration_type')
        decoration.position = request.form.get('position', 'above')
        decoration.is_always_active = request.form.get(
            'is_always_active') == 'on'
        decoration.is_enabled = request.form.get('is_enabled') == 'on'

        # Даты
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        decoration.start_date = datetime.strptime(
            start_date, '%Y-%m-%d').date() if start_date else None
        decoration.end_date = datetime.strptime(
            end_date, '%Y-%m-%d').date() if end_date else None

        # Дополнительные настройки
        settings = {
            'speed': request.form.get('speed', '500'),
        }
        # Цвет фона гирлянды
        if request.form.get('use_bg_color') == 'on':
            settings['bg_color'] = request.form.get('bg_color', '#1a1a2e')
        # Кастомный курсор
        cursor_type = request.form.get('cursor_type', 'default')
        if cursor_type != 'default':
            settings['cursor_type'] = cursor_type
        decoration.set_settings(settings)

        db.session.commit()
        flash('Украшение обновлено', 'success')
        return redirect(url_for('appearance.decorations'))

    decoration_types = SiteDecoration.DECORATION_TYPES
    cursor_types = SiteDecoration.CURSOR_TYPES
    return render_template('admin/appearance/decoration_form.html',
                           decoration=decoration,
                           decoration_types=decoration_types,
                           cursor_types=cursor_types)


@appearance_bp.route('/decorations/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def decoration_delete(id):
    """Удаление украшения"""
    decoration = SiteDecoration.query.get_or_404(id)
    db.session.delete(decoration)
    db.session.commit()
    flash('Украшение удалено', 'success')
    return redirect(url_for('appearance.decorations'))


@appearance_bp.route('/decorations/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def decoration_toggle(id):
    """Включение/выключение украшения"""
    decoration = SiteDecoration.query.get_or_404(id)
    decoration.is_enabled = not decoration.is_enabled
    db.session.commit()
    return jsonify({
        'success': True,
        'is_enabled': decoration.is_enabled
    })


@appearance_bp.route('/decorations/preview/<decoration_type>')
@login_required
@admin_required
def decoration_preview(decoration_type):
    """Предпросмотр украшения"""
    return render_template('admin/appearance/preview.html',
                           decoration_type=decoration_type)


# === API для получения активных украшений ===

@appearance_bp.route('/api/active-decorations')
def api_active_decorations():
    """Получить список активных украшений"""
    decorations = SiteDecoration.query.filter_by(is_enabled=True).all()
    active = []
    for d in decorations:
        if d.is_active_now():
            active.append({
                'type': d.decoration_type,
                'settings': d.get_settings()
            })
    return jsonify(active)
