"""
Blueprint профиля пользователя
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Notification
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import base64

profile_bp = Blueprint('profile', __name__)

STAFF_PHOTO_FOLDER = 'app/static/staff_photo'


@profile_bp.route('/')
@login_required
def index():
    return render_template('profile/index.html')


@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if request.method == 'POST':
        # LDAP пользователи не могут редактировать данные из LDAP
        if not current_user.is_ldap_user:
            current_user.phone = request.form.get('phone', '').strip()
            current_user.internal_phone = request.form.get(
                'internal_phone', '').strip()
            current_user.location = request.form.get('location', '').strip()

        # День рождения может редактировать любой
        birthday_str = request.form.get('birthday', '')
        if birthday_str:
            try:
                current_user.birthday = datetime.strptime(
                    birthday_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            current_user.birthday = None

        # Фото может редактировать любой пользователь
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                filename = secure_filename(
                    f'{current_user.id}_{file.filename}')
                os.makedirs(STAFF_PHOTO_FOLDER, exist_ok=True)
                file.save(os.path.join(STAFF_PHOTO_FOLDER, filename))
                current_user.photo = filename

        # Обработка обрезанного фото (base64)
        cropped_photo = request.form.get('cropped_photo')
        if cropped_photo and cropped_photo.startswith('data:image'):
            try:
                # Извлекаем данные base64
                header, data = cropped_photo.split(',', 1)
                ext = 'png' if 'png' in header else 'jpg'
                filename = f'{current_user.id}_cropped.{ext}'
                filepath = os.path.join(STAFF_PHOTO_FOLDER, filename)

                os.makedirs(STAFF_PHOTO_FOLDER, exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(base64.b64decode(data))

                current_user.photo = filename
            except Exception as e:
                flash(f'Ошибка сохранения фото: {e}', 'error')

        db.session.commit()
        flash('Профиль обновлен', 'success')
        return redirect(url_for('profile.index'))

    return render_template('profile/edit.html')


@profile_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    # LDAP пользователи не могут менять пароль здесь
    if current_user.is_ldap_user:
        flash('Смена пароля недоступна для LDAP пользователей', 'warning')
        return redirect(url_for('profile.index'))

    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash('Неверный текущий пароль', 'error')
            return redirect(url_for('profile.change_password'))

        if len(new_password) < 8:
            flash('Новый пароль должен быть не менее 8 символов', 'error')
            return redirect(url_for('profile.change_password'))

        if new_password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return redirect(url_for('profile.change_password'))

        current_user.set_password(new_password)
        db.session.commit()
        flash('Пароль успешно изменен', 'success')
        return redirect(url_for('profile.index'))

    return render_template('profile/change_password.html')


# === Уведомления ===

@profile_bp.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    notifications = current_user.notifications.order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=20)
    return render_template('profile/notifications.html', notifications=notifications)


@profile_bp.route('/notifications/unread-count')
@login_required
def notifications_unread_count():
    count = current_user.unread_notifications_count()
    return jsonify({'count': count})


@profile_bp.route('/notifications/recent')
@login_required
def notifications_recent():
    notifications = current_user.notifications.order_by(
        Notification.created_at.desc()
    ).limit(10).all()

    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'link': n.link,
            'icon': n.icon,
            'type': n.type,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%d.%m.%Y %H:%M')
        } for n in notifications]
    })


@profile_bp.route('/notifications/<int:id>/read', methods=['POST'])
@login_required
def notification_read(id):
    notification = Notification.query.get_or_404(id)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    return jsonify({'success': True})


@profile_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def notifications_read_all():
    current_user.notifications.filter_by(
        is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


@profile_bp.route('/notifications/<int:id>/delete', methods=['POST'])
@login_required
def notification_delete(id):
    notification = Notification.query.get_or_404(id)
    if notification.user_id == current_user.id:
        db.session.delete(notification)
        db.session.commit()
    return jsonify({'success': True})
