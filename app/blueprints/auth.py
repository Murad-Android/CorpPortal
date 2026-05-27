"""
Blueprint авторизации
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.services.auth_service import authenticate

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        if not username or not password:
            flash('Введите логин и пароль', 'error')
            return render_template('auth/login.html')

        user = authenticate(username, password)
        if user:
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            # Используем имя сотрудника или логин если имя не заполнено
            display_name = user.firstname or user.username
            flash(f'Добро пожаловать, {display_name}!', 'success')
            # Устанавливаем флаг для показа приветственной анимации
            session['show_greeting'] = True
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Неверный логин или пароль', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('auth.login'))
