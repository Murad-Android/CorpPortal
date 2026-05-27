"""
Blueprint планера отпусков
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import VacationRequest, VacationConflictRule, User, Notification
from datetime import datetime, date, timedelta
import calendar

vacations_bp = Blueprint('vacations', __name__)


@vacations_bp.route('/')
@login_required
def index():
    """Планер отпусков - календарь"""
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', date.today().month, type=int)

    # Границы месяца
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    # Получаем одобренные отпуска в отделе пользователя
    department = current_user.department
    approved_vacations = VacationRequest.get_approved_in_range(
        first_day, last_day, department)

    # Мои заявки
    my_requests = VacationRequest.query.filter_by(user_id=current_user.id).order_by(
        VacationRequest.created_at.desc()
    ).limit(10).all()

    # Конфликтующие пользователи
    conflict_user_ids = VacationConflictRule.get_conflicts_for_user(
        current_user.id)

    # Занятые даты конфликтующих пользователей
    blocked_dates = set()
    if conflict_user_ids:
        conflict_vacations = VacationRequest.query.filter(
            VacationRequest.user_id.in_(conflict_user_ids),
            VacationRequest.status == 'approved',
            VacationRequest.start_date <= last_day,
            VacationRequest.end_date >= first_day
        ).all()

        for v in conflict_vacations:
            current = max(v.start_date, first_day)
            end = min(v.end_date, last_day)
            while current <= end:
                blocked_dates.add(current.isoformat())
                current += timedelta(days=1)

    return render_template('vacations/index.html',
                           year=year,
                           month=month,
                           first_day=first_day,
                           last_day=last_day,
                           approved_vacations=approved_vacations,
                           my_requests=my_requests,
                           blocked_dates=list(blocked_dates),
                           conflict_user_ids=list(conflict_user_ids))


@vacations_bp.route('/request', methods=['GET', 'POST'])
@login_required
def create_request():
    """Создание заявки на отпуск"""
    from app.models import VacationSettings, UserVacationBalance

    # Получаем настройки и баланс пользователя
    settings = VacationSettings.get_settings()
    balance = UserVacationBalance.get_or_create(current_user.id)

    # Подсчитываем дни из ожидающих заявок
    pending_requests = VacationRequest.query.filter(
        VacationRequest.user_id == current_user.id,
        VacationRequest.status.in_(['pending_manager', 'pending_hr'])
    ).all()

    pending_annual_days = sum(
        req.days_count for req in pending_requests if req.vacation_type == 'annual'
    )
    pending_dayoff_days = sum(
        req.days_count for req in pending_requests if req.vacation_type == 'dayoff'
    )

    # Реальный доступный баланс с учетом ожидающих заявок
    real_annual_available = balance.annual_days_remaining - pending_annual_days
    real_dayoff_available = balance.dayoff_days_remaining - pending_dayoff_days

    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        vacation_type = request.form.get('vacation_type', 'annual')
        comment = request.form.get('comment', '').strip()

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Неверный формат даты', 'error')
            return redirect(url_for('vacations.create_request'))

        if start_date > end_date:
            flash('Дата начала не может быть позже даты окончания', 'error')
            return redirect(url_for('vacations.create_request'))

        if start_date < date.today():
            flash('Нельзя подать заявку на прошедшие даты', 'error')
            return redirect(url_for('vacations.create_request'))

        # Подсчет дней
        days_requested = (end_date - start_date).days + 1

        # Проверка лимитов для ежегодного отпуска
        if vacation_type == 'annual':
            if real_annual_available < days_requested:
                flash(
                    f'Недостаточно дней ежегодного отпуска. Доступно: {max(0, real_annual_available)} дней (учтены ожидающие заявки на {pending_annual_days} дн.)', 'error')
                return redirect(url_for('vacations.create_request'))

        # Проверка лимитов для day off
        elif vacation_type == 'dayoff':
            if not settings.dayoff_enabled:
                flash('Day Off отключен в настройках компании', 'error')
                return redirect(url_for('vacations.create_request'))
            if real_dayoff_available < days_requested:
                flash(
                    f'Недостаточно дней Day Off. Доступно: {max(0, real_dayoff_available)} дней (учтены ожидающие заявки на {pending_dayoff_days} дн.)', 'error')
                return redirect(url_for('vacations.create_request'))

        # Проверка конфликтов
        conflict_user_ids = VacationConflictRule.get_conflicts_for_user(
            current_user.id)
        if conflict_user_ids:
            conflict_vacations = VacationRequest.query.filter(
                VacationRequest.user_id.in_(conflict_user_ids),
                VacationRequest.status == 'approved',
                VacationRequest.start_date <= end_date,
                VacationRequest.end_date >= start_date
            ).all()

            if conflict_vacations:
                conflict_names = [v.user.full_name for v in conflict_vacations]
                flash(
                    f'Выбранные даты пересекаются с отпуском: {", ".join(conflict_names)}', 'error')
                return redirect(url_for('vacations.create_request'))

        # Создаём заявку
        vacation = VacationRequest(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            vacation_type=vacation_type,
            comment=comment,
            status='pending_manager'
        )
        db.session.add(vacation)
        db.session.commit()

        # Уведомление руководителю
        if current_user.manager_id:
            Notification.create(
                current_user.manager_id,
                '📅 Новая заявка на отпуск',
                f'{current_user.full_name} подал заявку на отпуск с {start_date.strftime("%d.%m.%Y")} по {end_date.strftime("%d.%m.%Y")}',
                link=url_for('vacations.manager_requests'),
                icon='calendar-alt',
                type='info'
            )

        flash('Заявка на отпуск отправлена руководителю', 'success')
        return redirect(url_for('vacations.index'))

    # Получаем заблокированные даты
    conflict_user_ids = VacationConflictRule.get_conflicts_for_user(
        current_user.id)
    blocked_dates = []

    if conflict_user_ids:
        # Смотрим на 6 месяцев вперёд
        today = date.today()
        end_range = today + timedelta(days=180)

        conflict_vacations = VacationRequest.query.filter(
            VacationRequest.user_id.in_(conflict_user_ids),
            VacationRequest.status == 'approved',
            VacationRequest.end_date >= today
        ).all()

        for v in conflict_vacations:
            current = max(v.start_date, today)
            while current <= v.end_date:
                blocked_dates.append(current.isoformat())
                current += timedelta(days=1)

    return render_template('vacations/request.html',
                           blocked_dates=blocked_dates,
                           balance=balance,
                           settings=settings,
                           real_annual_available=max(0, real_annual_available),
                           real_dayoff_available=max(0, real_dayoff_available),
                           pending_annual_days=pending_annual_days,
                           pending_dayoff_days=pending_dayoff_days)


@vacations_bp.route('/my')
@login_required
def my_requests():
    """Мои заявки на отпуск"""
    from app.models import VacationSettings, UserVacationBalance

    requests = VacationRequest.query.filter_by(user_id=current_user.id).order_by(
        VacationRequest.created_at.desc()
    ).all()

    # Получаем баланс и настройки
    balance = UserVacationBalance.get_or_create(current_user.id)
    settings = VacationSettings.get_settings()

    return render_template('vacations/my_requests.html',
                           requests=requests,
                           balance=balance,
                           settings=settings)


@vacations_bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_request(id):
    """Отмена заявки"""
    vacation = VacationRequest.query.get_or_404(id)

    if vacation.user_id != current_user.id:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('vacations.my_requests'))

    if vacation.status not in ['pending_manager', 'pending_hr']:
        flash('Нельзя отменить эту заявку', 'error')
        return redirect(url_for('vacations.my_requests'))

    db.session.delete(vacation)
    db.session.commit()
    flash('Заявка отменена', 'success')
    return redirect(url_for('vacations.my_requests'))


# === Панель руководителя ===

@vacations_bp.route('/manager')
@login_required
def manager_requests():
    """Заявки подчинённых для руководителя (или все для админа)"""
    is_admin = current_user.is_admin or current_user.has_permission('all')

    if is_admin:
        # Админ видит все заявки на согласовании у руководителя
        pending = VacationRequest.query.filter(
            VacationRequest.status == 'pending_manager'
        ).order_by(VacationRequest.created_at.desc()).all()

        processed = VacationRequest.query.filter(
            VacationRequest.status != 'pending_manager'
        ).order_by(VacationRequest.updated_at.desc()).limit(30).all()
    else:
        # Обычный руководитель — только подчинённые
        subordinates = User.query.filter_by(
            manager_id=current_user.id, is_active=True).all()
        subordinate_ids = [s.id for s in subordinates]

        if not subordinate_ids:
            flash('У вас нет подчинённых', 'warning')
            return redirect(url_for('vacations.index'))

        pending = VacationRequest.query.filter(
            VacationRequest.user_id.in_(subordinate_ids),
            VacationRequest.status == 'pending_manager'
        ).order_by(VacationRequest.created_at.desc()).all()

        processed = VacationRequest.query.filter(
            VacationRequest.user_id.in_(subordinate_ids),
            VacationRequest.status != 'pending_manager'
        ).order_by(VacationRequest.updated_at.desc()).limit(20).all()

    return render_template('vacations/manager.html', pending=pending, processed=processed)


@vacations_bp.route('/manager/<int:id>/approve', methods=['POST'])
@login_required
def manager_approve(id):
    """Одобрение руководителем (или админом)"""
    vacation = VacationRequest.query.get_or_404(id)

    # Проверка прав — руководитель ИЛИ админ с полным доступом
    is_manager = vacation.user.manager_id == current_user.id
    is_admin = current_user.is_admin or current_user.has_permission('all')
    if not is_manager and not is_admin:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('vacations.manager_requests'))

    if vacation.status != 'pending_manager':
        flash('Заявка уже обработана', 'warning')
        return redirect(url_for('vacations.manager_requests'))

    comment = request.form.get('comment', '').strip()

    # Если админ одобряет — сразу approved (пропускаем HR)
    if is_admin:
        vacation.status = 'approved'
        vacation.manager_id = current_user.id
        vacation.manager_approved_at = datetime.utcnow()
        vacation.manager_comment = comment
        vacation.hr_id = current_user.id
        vacation.hr_approved_at = datetime.utcnow()
        db.session.commit()

        Notification.create(
            vacation.user_id,
            '✅ Отпуск одобрен',
            f'Ваша заявка на отпуск полностью одобрена',
            link=url_for('vacations.my_requests'),
            icon='check-circle',
            type='success'
        )

        flash('Заявка полностью одобрена', 'success')
        return redirect(url_for('vacations.manager_requests'))

    vacation.status = 'pending_hr'
    vacation.manager_id = current_user.id
    vacation.manager_approved_at = datetime.utcnow()
    vacation.manager_comment = comment
    db.session.commit()

    # Уведомление сотруднику
    Notification.create(
        vacation.user_id,
        '✅ Руководитель одобрил отпуск',
        f'Ваша заявка на отпуск одобрена руководителем и передана в HR',
        link=url_for('vacations.my_requests'),
        icon='check-circle',
        type='success'
    )

    # Уведомление HR
    hr_users = User.query.join(User.role).filter(
        db.or_(
            User.role.has(name='admin'),
            User.role.has(name='hr')
        ),
        User.is_active == True
    ).all()

    for hr in hr_users:
        Notification.create(
            hr.id,
            '📅 Заявка на отпуск ожидает HR',
            f'{vacation.user.full_name}: {vacation.start_date.strftime("%d.%m.%Y")} - {vacation.end_date.strftime("%d.%m.%Y")}. Руководитель одобрил.',
            link=url_for('admin.vacations_hr'),
            icon='calendar-check',
            type='info'
        )

    flash('Заявка одобрена и передана в HR', 'success')
    return redirect(url_for('vacations.manager_requests'))


@vacations_bp.route('/manager/<int:id>/reject', methods=['POST'])
@login_required
def manager_reject(id):
    """Отклонение руководителем (или админом)"""
    vacation = VacationRequest.query.get_or_404(id)

    is_manager = vacation.user.manager_id == current_user.id
    is_admin = current_user.is_admin or current_user.has_permission('all')
    if not is_manager and not is_admin:
        flash('Доступ запрещён', 'error')
        return redirect(url_for('vacations.manager_requests'))

    if vacation.status != 'pending_manager':
        flash('Заявка уже обработана', 'warning')
        return redirect(url_for('vacations.manager_requests'))

    comment = request.form.get('comment', '').strip()
    if not comment:
        flash('Укажите причину отклонения', 'error')
        return redirect(url_for('vacations.manager_requests'))

    vacation.status = 'rejected_manager'
    vacation.manager_id = current_user.id
    vacation.manager_approved_at = datetime.utcnow()
    vacation.manager_comment = comment
    db.session.commit()

    # Уведомление сотруднику
    Notification.create(
        vacation.user_id,
        '❌ Руководитель отклонил отпуск',
        f'Причина: {comment}',
        link=url_for('vacations.my_requests'),
        icon='times-circle',
        type='error'
    )

    flash('Заявка отклонена', 'success')
    return redirect(url_for('vacations.manager_requests'))


# === API для календаря ===

@vacations_bp.route('/api/calendar')
@login_required
def api_calendar():
    """API для получения данных календаря"""
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', date.today().month, type=int)

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    department = current_user.department
    approved_vacations = VacationRequest.get_approved_in_range(
        first_day, last_day, department)

    events = []
    for v in approved_vacations:
        events.append({
            'id': v.id,
            'user_id': v.user_id,
            'user_name': v.user.full_name,
            'start': v.start_date.isoformat(),
            'end': v.end_date.isoformat(),
            'type': v.vacation_type,
            'is_mine': v.user_id == current_user.id
        })

    # Заблокированные даты
    conflict_user_ids = VacationConflictRule.get_conflicts_for_user(
        current_user.id)
    blocked = []

    if conflict_user_ids:
        conflict_vacations = VacationRequest.query.filter(
            VacationRequest.user_id.in_(conflict_user_ids),
            VacationRequest.status == 'approved',
            VacationRequest.start_date <= last_day,
            VacationRequest.end_date >= first_day
        ).all()

        for v in conflict_vacations:
            blocked.append({
                'user_name': v.user.full_name,
                'start': v.start_date.isoformat(),
                'end': v.end_date.isoformat()
            })

    return jsonify({
        'events': events,
        'blocked': blocked
    })
