"""
Blueprint электронных таблиц
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Table, TablePermission, User
import uuid
import json

tables_bp = Blueprint('tables', __name__)


@tables_bp.route('/')
@login_required
def index():
    # Таблицы, к которым есть доступ
    owned_tables = Table.query.filter_by(owner_id=current_user.id).all()

    shared_permissions = TablePermission.query.filter_by(
        user_id=current_user.id).all()
    shared_tables = [
        p.table for p in shared_permissions if p.table.owner_id != current_user.id]

    return render_template('tables/index.html',
                           owned_tables=owned_tables,
                           shared_tables=shared_tables)


@tables_bp.route('/create', methods=['POST'])
@login_required
def create():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Введите название таблицы', 'error')
        return redirect(url_for('tables.index'))

    # Создаем пустую таблицу
    table_id = str(uuid.uuid4())
    empty_data = {
        "Sheet1": [["" for _ in range(10)] for _ in range(20)]
    }

    table = Table(
        id=table_id,
        name=name,
        owner_id=current_user.id
    )
    table.set_data(empty_data)

    db.session.add(table)

    # Добавляем пользователей с доступом
    user_ids = request.form.getlist('users')
    for user_id in user_ids:
        if user_id and int(user_id) != current_user.id:
            permission = TablePermission(
                table_id=table_id,
                user_id=int(user_id),
                can_edit=True
            )
            db.session.add(permission)

    db.session.commit()
    flash('Таблица создана', 'success')
    return redirect(url_for('tables.view', table_id=table_id))


@tables_bp.route('/<table_id>')
@login_required
def view(table_id):
    table = Table.query.get_or_404(table_id)

    # Проверка доступа
    has_access = (
        table.owner_id == current_user.id or
        TablePermission.query.filter_by(
            table_id=table_id, user_id=current_user.id).first()
    )

    if not has_access:
        flash('У вас нет доступа к этой таблице', 'error')
        return redirect(url_for('tables.index'))

    # Список пользователей для добавления
    users = User.query.filter_by(is_active=True).all()

    # Текущие пользователи с доступом
    permissions = TablePermission.query.filter_by(table_id=table_id).all()

    return render_template('tables/view.html',
                           table=table,
                           users=users,
                           permissions=permissions)


@tables_bp.route('/<table_id>/save', methods=['POST'])
@login_required
def save(table_id):
    table = Table.query.get_or_404(table_id)

    # Проверка доступа на редактирование
    can_edit = table.owner_id == current_user.id
    if not can_edit:
        permission = TablePermission.query.filter_by(
            table_id=table_id, user_id=current_user.id
        ).first()
        can_edit = permission and permission.can_edit

    if not can_edit:
        return jsonify({'status': 'error', 'message': 'Нет прав на редактирование'}), 403

    data = request.get_json()
    if data:
        table.set_data(data)
        db.session.commit()
        return jsonify({'status': 'success'})

    return jsonify({'status': 'error', 'message': 'Нет данных'}), 400


@tables_bp.route('/<table_id>/permissions', methods=['POST'])
@login_required
def update_permissions(table_id):
    table = Table.query.get_or_404(table_id)

    if table.owner_id != current_user.id:
        flash('Только владелец может управлять доступом', 'error')
        return redirect(url_for('tables.view', table_id=table_id))

    action = request.form.get('action')

    if action == 'add':
        user_ids = request.form.getlist('users')
        for user_id in user_ids:
            if user_id and int(user_id) != current_user.id:
                existing = TablePermission.query.filter_by(
                    table_id=table_id, user_id=int(user_id)
                ).first()
                if not existing:
                    permission = TablePermission(
                        table_id=table_id,
                        user_id=int(user_id),
                        can_edit=True
                    )
                    db.session.add(permission)
        flash('Пользователи добавлены', 'success')

    elif action == 'remove':
        user_ids = request.form.getlist('remove_users')
        for user_id in user_ids:
            permission = TablePermission.query.filter_by(
                table_id=table_id, user_id=int(user_id)
            ).first()
            if permission:
                db.session.delete(permission)
        flash('Пользователи удалены', 'success')

    db.session.commit()
    return redirect(url_for('tables.view', table_id=table_id))


@tables_bp.route('/<table_id>/delete', methods=['POST'])
@login_required
def delete(table_id):
    table = Table.query.get_or_404(table_id)

    if table.owner_id != current_user.id and not current_user.is_admin:
        flash('Только владелец может удалить таблицу', 'error')
        return redirect(url_for('tables.index'))

    db.session.delete(table)
    db.session.commit()
    flash('Таблица удалена', 'success')
    return redirect(url_for('tables.index'))
