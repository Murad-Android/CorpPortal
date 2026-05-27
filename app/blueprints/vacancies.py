"""
Blueprint вакансий
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import Vacancy, User, Referral
import os
import uuid

vacancies_bp = Blueprint('vacancies', __name__)

REFERRAL_UPLOAD_FOLDER = 'app/static/uploads/referrals'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'rtf', 'txt'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_department_info(department_name):
    """Получить информацию об отделе: руководитель и количество сотрудников"""
    if not department_name:
        return None

    # Находим всех сотрудников отдела
    employees = User.query.filter_by(
        department=department_name, is_active=True).all()
    if not employees:
        return None

    # Ищем руководителя - того, у кого нет руководителя в этом же отделе
    # или у кого больше всего подчинённых в этом отделе
    manager = None
    for emp in employees:
        # Если у сотрудника есть подчинённые в этом отделе - он руководитель
        subordinates_in_dept = [
            s for s in emp.subordinates if s.department == department_name and s.is_active]
        if subordinates_in_dept:
            manager = emp
            break

    # Если не нашли по подчинённым, ищем того, чей руководитель в другом отделе
    if not manager:
        for emp in employees:
            if not emp.manager or emp.manager.department != department_name:
                manager = emp
                break

    # Если всё ещё не нашли, берём первого
    if not manager and employees:
        manager = employees[0]

    return {
        'name': department_name,
        'manager': manager,
        'employee_count': len(employees)
    }


@vacancies_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    department = request.args.get('department', '')

    query = Vacancy.query.filter_by(is_active=True)

    if department:
        query = query.filter_by(department=department)

    vacancies = query.order_by(
        Vacancy.created_at.desc()).paginate(page=page, per_page=12)

    return render_template('vacancies/index.html', vacancies=vacancies)


@vacancies_bp.route('/<int:id>')
@login_required
def detail(id):
    vacancy = Vacancy.query.get_or_404(id)
    department_info = get_department_info(vacancy.department)
    return render_template('vacancies/detail.html', vacancy=vacancy, department_info=department_info)


@vacancies_bp.route('/<int:id>/refer', methods=['POST'])
@login_required
def refer_friend(id):
    """Рекомендовать друга на вакансию"""
    vacancy = Vacancy.query.get_or_404(id)

    candidate_name = request.form.get('candidate_name', '').strip()
    candidate_email = request.form.get('candidate_email', '').strip()
    candidate_phone = request.form.get('candidate_phone', '').strip()
    comment = request.form.get('comment', '').strip()
    consent = request.form.get('consent') == 'on'

    if not candidate_name:
        flash('Укажите ФИО кандидата', 'error')
        return redirect(url_for('vacancies.detail', id=id))

    if not consent:
        flash('Необходимо подтвердить согласие кандидата', 'error')
        return redirect(url_for('vacancies.detail', id=id))

    # Проверяем файл резюме
    if 'resume' not in request.files or request.files['resume'].filename == '':
        flash('Прикрепите файл резюме', 'error')
        return redirect(url_for('vacancies.detail', id=id))

    file = request.files['resume']
    if not allowed_file(file.filename):
        flash('Недопустимый формат файла. Разрешены: PDF, DOC, DOCX, RTF, TXT', 'error')
        return redirect(url_for('vacancies.detail', id=id))

    # Сохраняем файл
    os.makedirs(REFERRAL_UPLOAD_FOLDER, exist_ok=True)
    original_filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
    file_path = os.path.join(REFERRAL_UPLOAD_FOLDER, unique_filename)
    file.save(file_path)

    # Создаём рекомендацию
    referral = Referral(
        vacancy_id=vacancy.id,
        referrer_id=current_user.id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_phone=candidate_phone,
        comment=comment,
        resume_file=unique_filename,
        resume_filename=original_filename,
        consent_given=True
    )
    db.session.add(referral)
    db.session.commit()

    flash('🍬 Спасибо за рекомендацию! Ваша конфетка уже ждёт вас!', 'success')
    return redirect(url_for('vacancies.detail', id=id))
