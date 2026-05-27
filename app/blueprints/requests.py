"""
Blueprint заявок (пропуска, заказы)
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import PassRequest, OrderRequest, User
from app.services.email_service import send_pass_request_notification, send_order_request_notification
from app.services.auth_service import notify_role
from datetime import datetime

requests_bp = Blueprint('requests', __name__)


# === Пропуска ===

@requests_bp.route('/pass', methods=['GET', 'POST'])
@login_required
def pass_request():
    if request.method == 'POST':
        visitor_name = request.form.get('visitor_name', '').strip()
        visitor_company = request.form.get('visitor_company', '').strip()
        visitor_document = request.form.get('visitor_document', '').strip()
        visit_date_str = request.form.get('visit_date', '')
        visit_end_date_str = request.form.get('visit_end_date', '')
        purpose = request.form.get('purpose', '').strip()
        host_id = request.form.get('host_id', type=int)

        if not visitor_name or not visit_date_str:
            flash('Заполните обязательные поля', 'error')
            return redirect(url_for('requests.pass_request'))

        try:
            visit_date = datetime.strptime(visit_date_str, '%Y-%m-%d').date()
            visit_end_date = None
            if visit_end_date_str:
                visit_end_date = datetime.strptime(
                    visit_end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Неверный формат даты', 'error')
            return redirect(url_for('requests.pass_request'))

        pass_req = PassRequest(
            visitor_name=visitor_name,
            visitor_company=visitor_company,
            visitor_document=visitor_document,
            visit_date=visit_date,
            visit_end_date=visit_end_date,
            purpose=purpose,
            host_id=host_id,
            created_by_id=current_user.id,
            status='pending'
        )

        db.session.add(pass_req)
        db.session.commit()

        # Уведомление секретарям
        notify_role('secretary', 'Новая заявка на пропуск',
                    f'Посетитель: {visitor_name}',
                    url_for('admin.passes'), 'id-card', 'info')

        # Отправка email
        send_pass_request_notification(pass_req)

        flash('Заявка на пропуск успешно создана', 'success')
        return redirect(url_for('requests.pass_success'))

    # Список пользователей для выбора принимающего
    users = User.query.filter_by(is_active=True).order_by(User.lastname).all()
    return render_template('requests/pass_form.html', users=users)


@requests_bp.route('/pass/success')
@login_required
def pass_success():
    return render_template('requests/pass_success.html')


# === Заказы ===

@requests_bp.route('/order', methods=['GET', 'POST'])
@login_required
def order_request():
    if request.method == 'POST':
        department = request.form.get('department', '').strip()
        item_name = request.form.get('item_name', '').strip()
        article = request.form.get('article', '').strip()
        quantity = request.form.get('quantity', 1, type=int)
        priority = request.form.get('priority', 'normal')
        notes = request.form.get('notes', '').strip()

        if not department or not item_name:
            flash('Заполните обязательные поля', 'error')
            return redirect(url_for('requests.order_request'))

        order = OrderRequest(
            department=department,
            item_name=item_name,
            article=article,
            quantity=max(1, quantity),
            priority=priority,
            notes=notes,
            created_by_id=current_user.id,
            status='pending'
        )

        db.session.add(order)
        db.session.commit()

        # Уведомление секретарям
        notify_role('secretary', 'Новая заявка на заказ товаров',
                    f'{item_name} ({quantity} шт.)',
                    url_for('admin.orders'), 'shopping-cart', 'info')

        # Отправка email
        send_order_request_notification(order)

        flash('Заявка на заказ успешно создана', 'success')
        return redirect(url_for('requests.order_success'))

    return render_template('requests/order_form.html')


@requests_bp.route('/order/success')
@login_required
def order_success():
    return render_template('requests/order_success.html')


# === Мои заявки ===

@requests_bp.route('/my')
@login_required
def my_requests():
    pass_requests = PassRequest.query.filter_by(created_by_id=current_user.id).order_by(
        PassRequest.created_at.desc()
    ).limit(20).all()

    order_requests = OrderRequest.query.filter_by(created_by_id=current_user.id).order_by(
        OrderRequest.created_at.desc()
    ).limit(20).all()

    return render_template('requests/my_requests.html',
                           pass_requests=pass_requests,
                           order_requests=order_requests)
