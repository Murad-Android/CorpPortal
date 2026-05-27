"""
Blueprint сотрудников
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, UserCardField, UserCustomField, Thanks, Notification
from datetime import datetime, date
from werkzeug.utils import secure_filename
import os

staff_bp = Blueprint('staff', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = 'app/static/staff_photo'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@staff_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    department = request.args.get('department', '')
    search = request.args.get('search', '')
    show_fired = request.args.get('show_fired', '0') == '1'

    query = User.query.filter_by(is_active=True)

    # Скрываем системную учётную запись admin
    query = query.filter(User.username != 'admin')

    # По умолчанию скрываем уволенных
    if not show_fired:
        query = query.filter(db.or_(
            User.employment_status == None,
            User.employment_status != 'fired'
        ))

    if department:
        query = query.filter_by(department=department)

    if search:
        search_term = f'%{search}%'
        query = query.filter(
            db.or_(
                User.firstname.ilike(search_term),
                User.lastname.ilike(search_term),
                User.position.ilike(search_term),
                User.email.ilike(search_term)
            )
        )

    staff = query.order_by(User.lastname).paginate(page=page, per_page=20)

    # Получаем список отделов для фильтра
    departments = db.session.query(User.department).filter(
        User.is_active == True,
        User.department != None
    ).distinct().all()
    departments = [d[0] for d in departments if d[0]]

    return render_template('staff/index.html',
                           staff=staff,
                           departments=departments,
                           current_department=department,
                           search=search,
                           show_fired=show_fired)


@staff_bp.route('/<int:id>')
@login_required
def detail(id):
    employee = User.query.get_or_404(id)
    can_edit = current_user.is_admin or (current_user.id == id)

    # HR и админы видят полную дату рождения
    is_hr = current_user.is_admin or current_user.has_permission('users_view')

    # Получаем настройки полей карточки
    card_fields = UserCardField.query.filter_by(
        is_visible=True).order_by(UserCardField.position).all()

    # Получаем кастомные поля пользователя
    custom_fields = {
        cf.field_name: cf.field_value for cf in employee.custom_fields}

    # Формат даты рождения - без года для обычных пользователей
    birthday_display = None
    if employee.birthday:
        if is_hr:
            birthday_display = employee.birthday.strftime('%d.%m.%Y')
        else:
            birthday_display = employee.birthday.strftime('%d %B').replace(
                'January', 'января').replace('February', 'февраля').replace('March', 'марта').replace(
                'April', 'апреля').replace('May', 'мая').replace('June', 'июня').replace(
                'July', 'июля').replace('August', 'августа').replace('September', 'сентября').replace(
                'October', 'октября').replace('November', 'ноября').replace('December', 'декабря')

    # Собираем значения стандартных полей в словарь для шаблона
    employee_data = {
        'email': employee.email,
        'phone': employee.phone,
        'internal_phone': employee.internal_phone,
        'location': employee.location,
        'department': employee.department,
        'position': employee.position,
        'birthday': birthday_display,
        'hire_date': employee.hire_date.strftime('%d.%m.%Y') if employee.hire_date else None,
    }
    # Добавляем кастомные поля
    employee_data.update(custom_fields)

    # Благодарности
    thanks_count = Thanks.get_count(employee.id)
    thanks_list = Thanks.get_thanks_for_user(employee.id, limit=5)

    return render_template('staff/detail.html',
                           employee=employee,
                           can_edit=can_edit,
                           card_fields=card_fields,
                           employee_data=employee_data,
                           thanks_count=thanks_count,
                           thanks_list=thanks_list)


@staff_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    employee = User.query.get_or_404(id)

    # Проверка прав - только админ может редактировать других
    # Обычный пользователь редактирует через профиль
    if not current_user.is_admin:
        flash('У вас нет прав для редактирования', 'error')
        return redirect(url_for('staff.detail', id=id))

    if request.method == 'POST':
        employee.firstname = request.form.get('firstname', employee.firstname)
        employee.lastname = request.form.get('lastname', employee.lastname)
        employee.middlename = request.form.get(
            'middlename', employee.middlename)
        employee.position = request.form.get('position', employee.position)
        employee.department = request.form.get(
            'department', employee.department)
        employee.email = request.form.get('email', employee.email)
        employee.phone = request.form.get('phone', employee.phone)
        employee.internal_phone = request.form.get(
            'internal_phone', employee.internal_phone)
        employee.location = request.form.get('location', employee.location)

        # Обработка фото
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f'{employee.id}_{file.filename}')
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                employee.photo = filename

        db.session.commit()
        flash('Данные успешно обновлены', 'success')
        return redirect(url_for('staff.detail', id=id))

    return render_template('staff/edit.html', employee=employee)


@staff_bp.route('/birthdays')
@login_required
def birthdays():
    today = date.today()

    # Именинники сегодня
    today_birthdays = User.query.filter(
        User.is_active == True,
        db.extract('month', User.birthday) == today.month,
        db.extract('day', User.birthday) == today.day
    ).all()

    # Ближайшие именинники (следующие 30 дней)
    upcoming = []
    all_users = User.query.filter(
        User.is_active == True, User.birthday != None).all()

    for emp in all_users:
        if emp.birthday:
            this_year_birthday = emp.birthday.replace(year=today.year)
            if this_year_birthday < today:
                this_year_birthday = emp.birthday.replace(year=today.year + 1)

            days_until = (this_year_birthday - today).days
            if 0 < days_until <= 30:
                upcoming.append({
                    'employee': emp,
                    'date': this_year_birthday,
                    'days_until': days_until
                })

    upcoming.sort(key=lambda x: x['days_until'])

    return render_template('staff/birthdays.html',
                           today_birthdays=today_birthdays,
                           upcoming=upcoming)


@staff_bp.route('/<int:id>/thanks', methods=['POST'])
@login_required
def send_thanks(id):
    """Отправить благодарность сотруднику"""
    if id == current_user.id:
        return jsonify({'success': False, 'error': 'Нельзя благодарить себя'}), 400

    employee = User.query.get_or_404(id)
    data = request.get_json()
    message = data.get('message', '').strip()

    if not message:
        return jsonify({'success': False, 'error': 'Введите текст благодарности'}), 400

    if len(message) > 500:
        return jsonify({'success': False, 'error': 'Текст слишком длинный (макс. 500 символов)'}), 400

    thanks = Thanks(
        from_user_id=current_user.id,
        to_user_id=id,
        message=message
    )
    db.session.add(thanks)

    # Уведомление
    Notification.create(
        id,
        'Вам сказали спасибо! ❤️',
        f'{current_user.short_name}: {message[:100]}',
        url_for('staff.detail', id=id),
        'heart',
        'success'
    )

    db.session.commit()

    return jsonify({
        'success': True,
        'thanks_count': Thanks.get_count(id)
    })


@staff_bp.route('/<int:id>/thanks/list')
@login_required
def get_thanks(id):
    """Получить список благодарностей"""
    employee = User.query.get_or_404(id)
    thanks_list = Thanks.get_thanks_for_user(id, limit=20)

    return jsonify({
        'thanks': [{
            'id': t.id,
            'from_user': t.from_user.short_name,
            'from_user_photo': t.from_user.photo if t.from_user.photo else 'image/static_avatar.png',
            'message': t.message,
            'created_at': t.created_at.strftime('%d.%m.%Y %H:%M')
        } for t in thanks_list],
        'total': Thanks.get_count(id)
    })
