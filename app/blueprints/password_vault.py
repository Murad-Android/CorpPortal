"""
Blueprint хранилища паролей
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import PasswordVault, PasswordVaultPermission, PasswordVaultLog, User
from app.services.encryption_service import EncryptionService
from datetime import datetime

vault_bp = Blueprint('vault', __name__)


def log_vault_access(vault_id, action, details=None):
    """Логирование доступа к хранилищу"""
    log = PasswordVaultLog(
        vault_id=vault_id,
        user_id=current_user.id,
        action=action,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:500],
        timestamp=datetime.utcnow()
    )
    db.session.add(log)
    db.session.commit()


@vault_bp.route('/')
@login_required
def index():
    """Список паролей"""
    # Проверка прав
    if not (current_user.is_admin or current_user.has_permission('password_vault_view')):
        flash('У вас нет доступа к хранилищу паролей', 'error')
        return redirect(url_for('main.index'))

    # Свои пароли
    my_vaults = PasswordVault.query.filter_by(owner_id=current_user.id).all()

    # Пароли с общим доступом
    shared_vaults = []
    if not current_user.is_admin:
        permissions = PasswordVaultPermission.query.filter_by(
            user_id=current_user.id, can_read=True
        ).all()
        shared_vaults = [p.vault for p in permissions]
    else:
        # Админ видит все
        shared_vaults = PasswordVault.query.filter(
            PasswordVault.owner_id != current_user.id
        ).all()

    return render_template('vault/index.html',
                           my_vaults=my_vaults,
                           shared_vaults=shared_vaults)


@vault_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Создание записи"""
    if not (current_user.is_admin or current_user.has_permission('password_vault_create')):
        flash('У вас нет прав на создание записей', 'error')
        return redirect(url_for('vault.index'))

    if request.method == 'POST':
        password = request.form.get('password', '')

        vault = PasswordVault(
            title=request.form.get('title', '').strip(),
            service_name=request.form.get('service_name', '').strip(),
            url=request.form.get('url', '').strip(),
            username=request.form.get('username', '').strip(),
            encrypted_password=EncryptionService.encrypt(password),
            notes=request.form.get('notes', '').strip(),
            category=request.form.get('category', '').strip(),
            owner_id=current_user.id,
            is_shared=request.form.get('is_shared') == 'on'
        )

        db.session.add(vault)
        db.session.commit()

        log_vault_access(vault.id, 'create')

        flash('Пароль добавлен в хранилище', 'success')
        return redirect(url_for('vault.index'))

    return render_template('vault/form.html', vault=None)


@vault_bp.route('/<int:id>')
@login_required
def view(id):
    """Просмотр записи"""
    vault = PasswordVault.query.get_or_404(id)

    if not vault.can_view(current_user):
        flash('У вас нет доступа к этой записи', 'error')
        return redirect(url_for('vault.index'))

    # Дешифруем пароль
    try:
        decrypted_password = EncryptionService.decrypt(
            vault.encrypted_password)
    except Exception as e:
        flash(f'Ошибка дешифрования: {str(e)}', 'error')
        decrypted_password = None

    # Обновляем время последнего доступа
    vault.last_accessed = datetime.utcnow()
    db.session.commit()

    log_vault_access(vault.id, 'view')

    return render_template('vault/view.html', vault=vault, password=decrypted_password)


@vault_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Редактирование записи"""
    vault = PasswordVault.query.get_or_404(id)

    if not vault.can_edit(current_user):
        flash('У вас нет прав на редактирование этой записи', 'error')
        return redirect(url_for('vault.index'))

    if request.method == 'POST':
        vault.title = request.form.get('title', '').strip()
        vault.service_name = request.form.get('service_name', '').strip()
        vault.url = request.form.get('url', '').strip()
        vault.username = request.form.get('username', '').strip()
        vault.notes = request.form.get('notes', '').strip()
        vault.category = request.form.get('category', '').strip()
        vault.is_shared = request.form.get('is_shared') == 'on'

        # Обновляем пароль если указан новый
        new_password = request.form.get('password', '').strip()
        if new_password:
            vault.encrypted_password = EncryptionService.encrypt(new_password)

        db.session.commit()

        log_vault_access(vault.id, 'edit')

        flash('Запись обновлена', 'success')
        return redirect(url_for('vault.view', id=id))

    return render_template('vault/form.html', vault=vault)


@vault_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Удаление записи"""
    vault = PasswordVault.query.get_or_404(id)

    if not vault.can_delete(current_user):
        flash('У вас нет прав на удаление этой записи', 'error')
        return redirect(url_for('vault.index'))

    log_vault_access(vault.id, 'delete')

    db.session.delete(vault)
    db.session.commit()

    flash('Запись удалена', 'success')
    return redirect(url_for('vault.index'))


@vault_bp.route('/<int:id>/share', methods=['GET', 'POST'])
@login_required
def share(id):
    """Предоставление доступа"""
    vault = PasswordVault.query.get_or_404(id)

    if not (vault.owner_id == current_user.id or current_user.is_admin or
            current_user.has_permission('password_vault_share')):
        flash('У вас нет прав на предоставление доступа', 'error')
        return redirect(url_for('vault.index'))

    if request.method == 'POST':
        user_id = request.form.get('user_id', type=int)

        if not user_id:
            flash('Выберите пользователя', 'error')
            return redirect(url_for('vault.share', id=id))

        # Проверяем, нет ли уже прав
        existing = PasswordVaultPermission.query.filter_by(
            vault_id=id, user_id=user_id
        ).first()

        if existing:
            # Обновляем права
            existing.can_read = request.form.get('can_read') == 'on'
            existing.can_edit = request.form.get('can_edit') == 'on'
            existing.can_delete = request.form.get('can_delete') == 'on'
            existing.can_share = request.form.get('can_share') == 'on'
        else:
            # Создаем новые права
            permission = PasswordVaultPermission(
                vault_id=id,
                user_id=user_id,
                can_read=request.form.get('can_read') == 'on',
                can_edit=request.form.get('can_edit') == 'on',
                can_delete=request.form.get('can_delete') == 'on',
                can_share=request.form.get('can_share') == 'on',
                granted_by_id=current_user.id
            )
            db.session.add(permission)

        db.session.commit()

        log_vault_access(vault.id, 'share',
                         f'Доступ предоставлен пользователю {user_id}')

        flash('Доступ предоставлен', 'success')
        return redirect(url_for('vault.view', id=id))

    # Список пользователей для предоставления доступа
    users = User.query.filter(User.id != current_user.id).all()

    # Текущие права доступа
    permissions = PasswordVaultPermission.query.filter_by(vault_id=id).all()

    return render_template('vault/share.html', vault=vault, users=users, permissions=permissions)


@vault_bp.route('/<int:id>/revoke/<int:user_id>', methods=['POST'])
@login_required
def revoke(id, user_id):
    """Отзыв доступа"""
    vault = PasswordVault.query.get_or_404(id)

    if not (vault.owner_id == current_user.id or current_user.is_admin):
        flash('У вас нет прав на отзыв доступа', 'error')
        return redirect(url_for('vault.index'))

    permission = PasswordVaultPermission.query.filter_by(
        vault_id=id, user_id=user_id
    ).first()

    if permission:
        db.session.delete(permission)
        db.session.commit()

        log_vault_access(vault.id, 'revoke',
                         f'Доступ отозван у пользователя {user_id}')

        flash('Доступ отозван', 'success')

    return redirect(url_for('vault.share', id=id))


@vault_bp.route('/<int:id>/copy-password', methods=['POST'])
@login_required
def copy_password(id):
    """API для копирования пароля"""
    vault = PasswordVault.query.get_or_404(id)

    if not vault.can_view(current_user):
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    try:
        password = EncryptionService.decrypt(vault.encrypted_password)
        log_vault_access(vault.id, 'copy')
        return jsonify({'success': True, 'password': password})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
