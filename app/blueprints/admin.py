"""
Blueprint админ-панели с поддержкой ролей
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import (
    User, Role, News, Vacancy, SecurityArticle,
    PassRequest, OrderRequest, Table, Notification,
    Settings, LdapSettings, LdapGroup, LdapCustomAttribute,
    SmtpSettings, AuditLog, UserCardField, UserCustomField, Referral,
    Survey, SurveyQuestion, SurveyOption, SurveyResponse, SurveyAnswer,
    Test, TestQuestion, TestOption, TestAttempt, TestAnswer, MenuItem,
    VacationRequest, VacationConflictRule,
    PasswordVault, PasswordVaultPermission, PasswordVaultLog,
    TestingService, TestingServiceLog
)
from app.services.email_service import send_email
from app.services.auth_service import notify_user
from datetime import datetime
from werkzeug.utils import secure_filename
import os

admin_bp = Blueprint('admin', __name__)

UPLOAD_FOLDER = 'app/static/uploads'
STAFF_PHOTO_FOLDER = 'app/static/staff_photo'
REFERRAL_UPLOAD_FOLDER = 'app/static/uploads/referrals'
NEWS_COVER_FOLDER = 'app/static/uploads/news'
NEWS_CONTENT_FOLDER = 'app/static/uploads/news/content'

# Создаем папки если их нет
os.makedirs(NEWS_COVER_FOLDER, exist_ok=True)
os.makedirs(NEWS_CONTENT_FOLDER, exist_ok=True)


def save_news_cover(file):
    """Сохранение обложки новости"""
    if file and file.filename:
        filename = secure_filename(file.filename)
        # Добавляем timestamp для уникальности
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        filename = f"{timestamp}_{name}{ext}"
        filepath = os.path.join(NEWS_COVER_FOLDER, filename)
        file.save(filepath)
        return filename
    return None


def delete_news_cover(filename):
    """Удаление обложки новости"""
    if filename:
        filepath = os.path.join(NEWS_COVER_FOLDER, filename)
        if os.path.exists(filepath):
            os.remove(filepath)


def save_news_content_image(file):
    """Сохранение изображения для контента новости"""
    if file and file.filename:
        filename = secure_filename(file.filename)
        # Добавляем timestamp для уникальности
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        filename = f"{timestamp}_{name}{ext}"
        filepath = os.path.join(NEWS_CONTENT_FOLDER, filename)
        file.save(filepath)
        return filename
    return None


def permission_required(*permissions):
    """Декоратор проверки прав доступа"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if not current_user.can_access_admin():
                flash('Доступ запрещен', 'error')
                return redirect(url_for('main.index'))
            # Проверяем конкретные права
            if permissions:
                has_perm = any(current_user.has_permission(p)
                               for p in permissions)
                if not has_perm:
                    flash('Недостаточно прав', 'error')
                    return redirect(url_for('admin.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Декоратор проверки прав администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещен', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


# === Главная страница админки ===

@admin_bp.route('/')
@login_required
@permission_required()
def index():
    stats = {
        'users': User.query.count(),
        'news': News.query.count(),
        'vacancies': Vacancy.query.filter_by(is_active=True).count(),
        'pending_passes': PassRequest.query.filter_by(status='pending').count(),
        'pending_orders': OrderRequest.query.filter_by(status='pending').count(),
    }

    recent_logs = AuditLog.query.order_by(
        AuditLog.created_at.desc()).limit(10).all()
    recent_passes = PassRequest.query.order_by(
        PassRequest.created_at.desc()).limit(5).all()
    recent_orders = OrderRequest.query.order_by(
        OrderRequest.created_at.desc()).limit(5).all()

    return render_template('admin/index.html',
                           stats=stats,
                           recent_logs=recent_logs,
                           recent_passes=recent_passes,
                           recent_orders=recent_orders)


# === Пользователи ===

@admin_bp.route('/users')
@login_required
@permission_required('all', 'users_view', 'users_create', 'users_edit')
def users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')

    query = User.query
    if search:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.lastname.ilike(f'%{search}%')
            )
        )

    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20)
    return render_template('admin/users/index.html', users=users, search=search)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'users_create')
def user_create():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        lastname = request.form.get('lastname', '').strip()
        firstname = request.form.get('firstname', '').strip()
        middlename = request.form.get('middlename', '').strip()
        position = request.form.get('position', '').strip()
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()
        role_id = request.form.get('role_id', type=int)

        # Пароль
        password = request.form.get('password', '')
        generate_pwd = request.form.get('generate_password') == 'on'
        send_pwd = request.form.get('send_password') == 'on'

        if generate_pwd:
            password = User.generate_password()

        if not username or not email or not lastname or not firstname:
            flash('Заполните обязательные поля', 'error')
            return redirect(url_for('admin.user_create'))

        if not password:
            flash('Укажите пароль или выберите генерацию', 'error')
            return redirect(url_for('admin.user_create'))

        if len(password) < 8:
            flash('Пароль должен быть не менее 8 символов', 'error')
            return redirect(url_for('admin.user_create'))

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует', 'error')
            return redirect(url_for('admin.user_create'))

        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'error')
            return redirect(url_for('admin.user_create'))

        user = User(
            username=username,
            email=email,
            lastname=lastname,
            firstname=firstname,
            middlename=middlename,
            position=position,
            department=department,
            phone=phone,
            internal_phone=request.form.get('internal_phone', '').strip(),
            location=request.form.get('location', '').strip(),
            role_id=role_id,
            is_active=True
        )

        # Даты
        birthday_str = request.form.get('birthday', '')
        if birthday_str:
            try:
                user.birthday = datetime.strptime(
                    birthday_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        hire_date_str = request.form.get('hire_date', '')
        if hire_date_str:
            try:
                user.hire_date = datetime.strptime(
                    hire_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        user.set_password(password)

        # Руководитель
        manager_id = request.form.get('manager_id', type=int)
        if manager_id:
            user.manager_id = manager_id

        # Фото
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                filename = secure_filename(f'{username}_{file.filename}')
                os.makedirs(STAFF_PHOTO_FOLDER, exist_ok=True)
                file.save(os.path.join(STAFF_PHOTO_FOLDER, filename))
                user.photo = filename

        db.session.add(user)
        db.session.commit()

        # Отправка пароля на почту
        if send_pwd and email:
            send_email(
                email,
                'Ваш аккаунт на корпоративном портале',
                f'Здравствуйте, {firstname}!\n\n'
                f'Для вас создан аккаунт на корпоративном портале.\n\n'
                f'Логин: {username}\n'
                f'Пароль: {password}\n\n'
                f'Рекомендуем сменить пароль после первого входа.'
            )
            flash('Пользователь создан, пароль отправлен на почту', 'success')
        else:
            flash(f'Пользователь создан. Пароль: {password}', 'success')

        return redirect(url_for('admin.users'))

    roles = Role.query.all()
    all_users = User.query.filter_by(is_active=True).order_by(
        User.lastname, User.firstname).all()
    return render_template('admin/users/form.html', user=None, roles=roles, all_users=all_users)


@admin_bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'users_edit')
def user_edit(id):
    user = User.query.get_or_404(id)

    if request.method == 'POST':
        user.username = request.form.get('username', user.username).strip()
        user.email = request.form.get('email', user.email).strip()
        user.lastname = request.form.get('lastname', '').strip()
        user.firstname = request.form.get('firstname', '').strip()
        user.middlename = request.form.get('middlename', '').strip()
        user.position = request.form.get('position', '').strip()
        user.department = request.form.get('department', '').strip()
        user.phone = request.form.get('phone', '').strip()
        user.internal_phone = request.form.get('internal_phone', '').strip()
        user.location = request.form.get('location', '').strip()
        user.role_id = request.form.get('role_id', type=int)
        user.is_active = request.form.get('is_active') == 'on'

        # Статус сотрудника
        employment_status = request.form.get('employment_status', 'working')
        if employment_status in ['working', 'vacation', 'fired']:
            user.employment_status = employment_status

        # Даты
        birthday_str = request.form.get('birthday', '')
        if birthday_str:
            try:
                user.birthday = datetime.strptime(
                    birthday_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            user.birthday = None

        hire_date_str = request.form.get('hire_date', '')
        if hire_date_str:
            try:
                user.hire_date = datetime.strptime(
                    hire_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            user.hire_date = None

        password = request.form.get('password', '')
        if password:
            if len(password) < 8:
                flash('Пароль должен быть не менее 8 символов', 'error')
                return redirect(url_for('admin.user_edit', id=id))
            user.set_password(password)

        # Руководитель
        manager_id = request.form.get('manager_id', type=int)
        if manager_id and manager_id != user.id:
            user.manager_id = manager_id
        elif not manager_id:
            user.manager_id = None

        # Фото
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                filename = secure_filename(f'{user.id}_{file.filename}')
                os.makedirs(STAFF_PHOTO_FOLDER, exist_ok=True)
                file.save(os.path.join(STAFF_PHOTO_FOLDER, filename))
                user.photo = filename

        db.session.commit()
        flash('Пользователь обновлен', 'success')
        return redirect(url_for('admin.users'))

    roles = Role.query.all()
    all_users = User.query.filter_by(is_active=True).order_by(
        User.lastname, User.firstname).all()
    return render_template('admin/users/form.html', user=user, roles=roles, all_users=all_users)


@admin_bp.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('all', 'users_delete')
def user_delete(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Нельзя удалить самого себя', 'error')
        return redirect(url_for('admin.users'))

    # Удаляем связанные чаты (user1_id и user2_id NOT NULL)
    from app.models import Chat, Message
    chats = Chat.query.filter(
        db.or_(Chat.user1_id == user.id, Chat.user2_id == user.id)
    ).all()
    for chat in chats:
        # Удаляем сообщения чата
        Message.query.filter_by(chat_id=chat.id).delete()
        db.session.delete(chat)

    # Удаляем доступ к баг-трекеру
    from app.blueprints.bugtracker import BugTrackerAccess
    BugTrackerAccess.query.filter_by(user_id=user.id).delete()

    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удален', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/generate-password')
@login_required
@permission_required('all', 'users_create', 'users_edit')
def generate_password():
    return jsonify({'password': User.generate_password()})


# === Новости (HR) ===

@admin_bp.route('/news')
@login_required
@permission_required('all', 'news')
def news():
    page = request.args.get('page', 1, type=int)
    news = News.query.order_by(
        News.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/news/index.html', news=news)


@admin_bp.route('/news/create', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'news')
def news_create():
    if request.method == 'POST':
        # Обработка обложки
        cover_image = None
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and file.filename:
                cover_image = save_news_cover(file)

        article = News(
            title=request.form.get('title', '').strip(),
            short_description=request.form.get(
                'short_description', '').strip(),
            content=request.form.get('content', ''),
            image=cover_image,
            is_published=request.form.get('is_published') == 'on',
            is_pinned=request.form.get('is_pinned') == 'on',
            comments_enabled=request.form.get('comments_enabled') == 'on',
            author_id=current_user.id
        )
        db.session.add(article)
        db.session.commit()

        # Уведомление всем активным пользователям о новой новости
        if article.is_published:
            all_users = User.query.filter(
                User.is_active == True, User.id != current_user.id).all()
            for u in all_users:
                Notification.create(
                    u.id,
                    f'Новая новость: {article.title[:80]}',
                    article.short_description[:100] if article.short_description else None,
                    f'/news/{article.id}',
                    'newspaper', 'info'
                )

        flash('Новость создана', 'success')
        return redirect(url_for('admin.news'))

    return render_template('admin/news/form.html', article=None)


@admin_bp.route('/news/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'news')
def news_edit(id):
    article = News.query.get_or_404(id)

    if request.method == 'POST':
        article.title = request.form.get('title', '').strip()
        article.short_description = request.form.get(
            'short_description', '').strip()
        article.content = request.form.get('content', '')
        article.is_published = request.form.get('is_published') == 'on'
        article.is_pinned = request.form.get('is_pinned') == 'on'
        article.comments_enabled = request.form.get('comments_enabled') == 'on'

        # Обработка обложки
        if request.form.get('remove_image') == 'on':
            # Удаляем старое изображение
            if article.image:
                delete_news_cover(article.image)
                article.image = None

        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and file.filename:
                # Удаляем старое изображение
                if article.image:
                    delete_news_cover(article.image)
                # Сохраняем новое
                article.image = save_news_cover(file)

        db.session.commit()
        flash('Новость обновлена', 'success')
        return redirect(url_for('admin.news'))

    return render_template('admin/news/form.html', article=article)


@admin_bp.route('/news/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('all', 'news')
def news_delete(id):
    article = News.query.get_or_404(id)
    # Удаляем обложку если есть
    if article.image:
        delete_news_cover(article.image)
    db.session.delete(article)
    db.session.commit()
    flash('Новость удалена', 'success')
    return redirect(url_for('admin.news'))


@admin_bp.route('/news/upload-image', methods=['POST'])
@login_required
@permission_required('all', 'news')
def upload_news_image():
    """Загрузка изображения для контента новости"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'Файл не найден'}), 400

    file = request.files['image']
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'Файл не выбран'}), 400

    # Проверка типа файла
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if '.' not in file.filename or \
       file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return jsonify({'success': False, 'error': 'Недопустимый формат файла'}), 400

    try:
        filename = save_news_content_image(file)
        url = url_for('static', filename=f'uploads/news/content/{filename}')
        return jsonify({'success': True, 'url': url, 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# === Вакансии (HR) ===

@admin_bp.route('/vacancies')
@login_required
@permission_required('all', 'vacancies')
def vacancies():
    page = request.args.get('page', 1, type=int)
    vacancies = Vacancy.query.order_by(
        Vacancy.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/vacancies/index.html', vacancies=vacancies)


@admin_bp.route('/vacancies/create', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'vacancies')
def vacancy_create():
    if request.method == 'POST':
        vacancy = Vacancy(
            title=request.form.get('title', '').strip(),
            department=request.form.get('department', '').strip(),
            description=request.form.get('description', ''),
            requirements=request.form.get('requirements', ''),
            conditions=request.form.get('conditions', ''),
            salary_from=request.form.get('salary_from', type=int),
            salary_to=request.form.get('salary_to', type=int),
            employment_type=request.form.get('employment_type', 'full-time'),
            contact_email=request.form.get('contact_email', '').strip(),
            contact_phone=request.form.get('contact_phone', '').strip(),
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(vacancy)
        db.session.commit()
        flash('Вакансия создана', 'success')
        return redirect(url_for('admin.vacancies'))

    # Получаем список отделов
    departments = db.session.query(User.department).filter(
        User.is_active == True,
        User.department != None,
        User.department != ''
    ).distinct().order_by(User.department).all()
    departments = [d[0] for d in departments if d[0]]

    return render_template('admin/vacancies/form.html', vacancy=None, departments=departments)


@admin_bp.route('/vacancies/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'vacancies')
def vacancy_edit(id):
    vacancy = Vacancy.query.get_or_404(id)

    if request.method == 'POST':
        vacancy.title = request.form.get('title', '').strip()
        vacancy.department = request.form.get('department', '').strip()
        vacancy.description = request.form.get('description', '')
        vacancy.requirements = request.form.get('requirements', '')
        vacancy.conditions = request.form.get('conditions', '')
        vacancy.salary_from = request.form.get('salary_from', type=int)
        vacancy.salary_to = request.form.get('salary_to', type=int)
        vacancy.employment_type = request.form.get(
            'employment_type', 'full-time')
        vacancy.contact_email = request.form.get('contact_email', '').strip()
        vacancy.contact_phone = request.form.get('contact_phone', '').strip()
        vacancy.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        flash('Вакансия обновлена', 'success')
        return redirect(url_for('admin.vacancies'))

    # Получаем список отделов
    departments = db.session.query(User.department).filter(
        User.is_active == True,
        User.department != None,
        User.department != ''
    ).distinct().order_by(User.department).all()
    departments = [d[0] for d in departments if d[0]]

    return render_template('admin/vacancies/form.html', vacancy=vacancy, departments=departments)


@admin_bp.route('/vacancies/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('all', 'vacancies')
def vacancy_delete(id):
    vacancy = Vacancy.query.get_or_404(id)
    db.session.delete(vacancy)
    db.session.commit()
    flash('Вакансия удалена', 'success')
    return redirect(url_for('admin.vacancies'))


# === Заявки на пропуск (Секретарь) ===

@admin_bp.route('/passes')
@login_required
@permission_required('all', 'passes')
def passes():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')

    query = PassRequest.query
    if status:
        query = query.filter_by(status=status)

    passes = query.order_by(PassRequest.created_at.desc()
                            ).paginate(page=page, per_page=20)
    return render_template('admin/passes/index.html', passes=passes, current_status=status)


@admin_bp.route('/passes/<int:id>/process', methods=['POST'])
@login_required
@permission_required('all', 'passes')
def pass_process(id):
    pass_req = PassRequest.query.get_or_404(id)
    action = request.form.get('action')
    comment = request.form.get('comment', '')

    if action == 'approve':
        pass_req.status = 'approved'
        # Уведомление создателю заявки
        if pass_req.created_by_id:
            notify_user(pass_req.created_by_id, 'Заявка на пропуск одобрена',
                        f'Ваша заявка на пропуск для {pass_req.visitor_name} одобрена',
                        icon='check-circle', type='success')
    elif action == 'reject':
        pass_req.status = 'rejected'
        if pass_req.created_by_id:
            notify_user(pass_req.created_by_id, 'Заявка на пропуск отклонена',
                        f'Ваша заявка на пропуск для {pass_req.visitor_name} отклонена',
                        icon='times-circle', type='error')

    pass_req.processed_at = datetime.utcnow()
    pass_req.processed_by_id = current_user.id
    pass_req.comment = comment

    db.session.commit()
    flash(
        f'Заявка {"одобрена" if action == "approve" else "отклонена"}', 'success')
    return redirect(url_for('admin.passes'))


# === Заявки на заказ (Секретарь) ===

@admin_bp.route('/orders')
@login_required
@permission_required('all', 'orders')
def orders():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')

    query = OrderRequest.query
    if status:
        query = query.filter_by(status=status)

    orders = query.order_by(OrderRequest.created_at.desc()
                            ).paginate(page=page, per_page=20)
    return render_template('admin/orders/index.html', orders=orders, current_status=status)


@admin_bp.route('/orders/<int:id>/process', methods=['POST'])
@login_required
@permission_required('all', 'orders')
def order_process(id):
    order = OrderRequest.query.get_or_404(id)
    status = request.form.get('status')

    status_messages = {
        'approved': ('Заявка одобрена', 'success'),
        'ordered': ('Товар заказан', 'info'),
        'delivered': ('Товар доставлен', 'success'),
        'rejected': ('Заявка отклонена', 'error'),
    }

    if status in status_messages:
        order.status = status
        order.processed_at = datetime.utcnow()
        order.processed_by_id = current_user.id
        db.session.commit()

        # Уведомление
        if order.created_by_id:
            msg, type = status_messages[status]
            notify_user(order.created_by_id, f'Заказ: {msg}',
                        f'Статус заявки на "{order.item_name}" изменен',
                        icon='shopping-cart', type=type)

        flash('Статус заявки обновлен', 'success')

    return redirect(url_for('admin.orders'))


# === Центр безопасности (Админ) ===

@admin_bp.route('/security')
@login_required
@permission_required('all', 'security_articles')
def security():
    page = request.args.get('page', 1, type=int)
    articles = SecurityArticle.query.order_by(
        SecurityArticle.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/security/index.html', articles=articles)


@admin_bp.route('/security/create', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'security_articles')
def security_create():
    if request.method == 'POST':
        article = SecurityArticle(
            title=request.form.get('title', '').strip(),
            short_description=request.form.get(
                'short_description', '').strip(),
            content=request.form.get('content', ''),
            priority=request.form.get('priority', 'info'),
            icon=request.form.get('icon', 'shield-alt'),
            is_published=request.form.get('is_published') == 'on'
        )
        db.session.add(article)
        db.session.commit()
        flash('Статья создана', 'success')
        return redirect(url_for('admin.security'))

    return render_template('admin/security/form.html', article=None)


@admin_bp.route('/security/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'security_articles')
def security_edit(id):
    article = SecurityArticle.query.get_or_404(id)

    if request.method == 'POST':
        article.title = request.form.get('title', '').strip()
        article.short_description = request.form.get(
            'short_description', '').strip()
        article.content = request.form.get('content', '')
        article.priority = request.form.get('priority', 'info')
        article.icon = request.form.get('icon', 'shield-alt')
        article.is_published = request.form.get('is_published') == 'on'
        db.session.commit()
        flash('Статья обновлена', 'success')
        return redirect(url_for('admin.security'))

    return render_template('admin/security/form.html', article=article)


@admin_bp.route('/security/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('all', 'security_articles')
def security_delete(id):
    article = SecurityArticle.query.get_or_404(id)
    db.session.delete(article)
    db.session.commit()
    flash('Статья удалена', 'success')
    return redirect(url_for('admin.security'))


# === Настройки (Админ) ===

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'settings_general')
def settings():
    if request.method == 'POST':
        Settings.set('site_name', request.form.get('site_name', ''))
        Settings.set('site_description',
                     request.form.get('site_description', ''))
        Settings.set('auth_enabled', 'true' if request.form.get(
            'auth_enabled') else 'false')
        Settings.set('registration_enabled', 'true' if request.form.get(
            'registration_enabled') else 'false')
        flash('Настройки сохранены', 'success')
        return redirect(url_for('admin.settings'))

    settings_dict = {
        'site_name': Settings.get('site_name', 'Корпоративный портал'),
        'site_description': Settings.get('site_description', ''),
        'auth_enabled': Settings.get('auth_enabled', 'true') == 'true',
        'registration_enabled': Settings.get('registration_enabled', 'false') == 'true',
    }
    return render_template('admin/settings/general.html', settings=settings_dict)


@admin_bp.route('/settings/greetings', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'settings_general')
def settings_greetings():
    """Настройки приветственных анимаций"""
    if request.method == 'POST':
        Settings.set('greeting_morning_enabled',
                     'true' if request.form.get('morning_enabled') else 'false')
        Settings.set('greeting_afternoon_enabled',
                     'true' if request.form.get('afternoon_enabled') else 'false')
        Settings.set('greeting_evening_enabled',
                     'true' if request.form.get('evening_enabled') else 'false')

        Settings.set('greeting_morning_start',
                     request.form.get('morning_start', '6'))
        Settings.set('greeting_morning_end',
                     request.form.get('morning_end', '12'))
        Settings.set('greeting_afternoon_start',
                     request.form.get('afternoon_start', '12'))
        Settings.set('greeting_afternoon_end',
                     request.form.get('afternoon_end', '18'))
        Settings.set('greeting_evening_start',
                     request.form.get('evening_start', '18'))
        Settings.set('greeting_evening_end',
                     request.form.get('evening_end', '6'))

        flash('Настройки приветствий сохранены', 'success')
        return redirect(url_for('admin.settings_greetings'))

    settings_dict = {
        'morning_enabled': Settings.get('greeting_morning_enabled', 'true') == 'true',
        'afternoon_enabled': Settings.get('greeting_afternoon_enabled', 'true') == 'true',
        'evening_enabled': Settings.get('greeting_evening_enabled', 'true') == 'true',
        'morning_start': Settings.get('greeting_morning_start', '6'),
        'morning_end': Settings.get('greeting_morning_end', '12'),
        'afternoon_start': Settings.get('greeting_afternoon_start', '12'),
        'afternoon_end': Settings.get('greeting_afternoon_end', '18'),
        'evening_start': Settings.get('greeting_evening_start', '18'),
        'evening_end': Settings.get('greeting_evening_end', '6'),
    }
    return render_template('admin/settings/greetings.html', settings=settings_dict)


@admin_bp.route('/settings/ldap', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'settings_ldap')
def settings_ldap():
    ldap = LdapSettings.query.first()
    if not ldap:
        ldap = LdapSettings()
        db.session.add(ldap)
        db.session.commit()

    roles = Role.query.all()

    if request.method == 'POST':
        ldap.is_enabled = request.form.get('is_enabled') == 'on'
        ldap.server = request.form.get('server', '').strip()
        ldap.port = request.form.get('port', 389, type=int)
        ldap.use_ssl = request.form.get('use_ssl') == 'on'
        ldap.domain = request.form.get('domain', '').strip()
        ldap.base_dn = request.form.get('base_dn', '').strip()
        ldap.bind_user = request.form.get('bind_user', '').strip()

        password = request.form.get('bind_password', '')
        if password:
            ldap.bind_password = password

        ldap.user_filter = request.form.get('user_filter', '').strip()
        ldap.sync_group_dn = request.form.get(
            'sync_group_dn', '').strip() or None
        ldap.attr_firstname = request.form.get(
            'attr_firstname', 'givenName').strip()
        ldap.attr_lastname = request.form.get('attr_lastname', 'sn').strip()
        ldap.attr_email = request.form.get('attr_email', 'mail').strip()
        ldap.attr_phone = request.form.get(
            'attr_phone', 'telephoneNumber').strip()
        ldap.attr_department = request.form.get(
            'attr_department', 'department').strip()
        ldap.attr_position = request.form.get('attr_position', 'title').strip()
        ldap.attr_manager = request.form.get('attr_manager', 'manager').strip()

        db.session.commit()
        flash('Настройки LDAP сохранены', 'success')
        return redirect(url_for('admin.settings_ldap'))

    return render_template('admin/settings/ldap.html', ldap=ldap, roles=roles)


@admin_bp.route('/settings/ldap/groups', methods=['POST'])
@login_required
@permission_required('all', 'settings_ldap')
def settings_ldap_groups():
    ldap = LdapSettings.query.first()
    if not ldap:
        flash('Сначала сохраните настройки LDAP', 'error')
        return redirect(url_for('admin.settings_ldap'))

    action = request.form.get('action')

    if action == 'add':
        group_dn = request.form.get('group_dn', '').strip()
        group_name = request.form.get('group_name', '').strip()
        role_id = request.form.get('role_id', type=int)

        if group_dn:
            group = LdapGroup(
                ldap_settings_id=ldap.id,
                group_dn=group_dn,
                group_name=group_name,
                role_id=role_id
            )
            db.session.add(group)
            db.session.commit()
            flash('Группа добавлена', 'success')

    elif action == 'delete':
        group_id = request.form.get('group_id', type=int)
        group = LdapGroup.query.get(group_id)
        if group:
            db.session.delete(group)
            db.session.commit()
            flash('Группа удалена', 'success')

    return redirect(url_for('admin.settings_ldap'))


@admin_bp.route('/settings/ldap/sync', methods=['POST'])
@login_required
@permission_required('all', 'settings_ldap')
def settings_ldap_sync():
    """Принудительная синхронизация всех пользователей LDAP"""
    from app.services.auth_service import sync_all_ldap_users

    result = sync_all_ldap_users()

    if result['success']:
        flash(
            f'Синхронизация завершена: создано {result["created"]}, обновлено {result["updated"]}, пропущено {result["skipped"]}', 'success')
    else:
        flash(f'Ошибка синхронизации: {result["error"]}', 'error')

    return redirect(url_for('admin.settings_ldap'))


@admin_bp.route('/settings/ldap/attributes', methods=['POST'])
@login_required
@permission_required('all', 'settings_ldap')
def settings_ldap_attributes():
    """Управление кастомными атрибутами LDAP"""
    ldap = LdapSettings.query.first()
    if not ldap:
        flash('Сначала сохраните настройки LDAP', 'error')
        return redirect(url_for('admin.settings_ldap'))

    action = request.form.get('action')

    if action == 'add':
        ldap_attr = request.form.get('ldap_attr', '').strip()
        portal_field = request.form.get('portal_field', '').strip()
        display_name = request.form.get('display_name', '').strip()

        if ldap_attr and portal_field:
            attr = LdapCustomAttribute(
                ldap_settings_id=ldap.id,
                ldap_attr=ldap_attr,
                portal_field=portal_field,
                display_name=display_name or portal_field,
                is_active=True
            )
            db.session.add(attr)
            db.session.commit()
            flash('Атрибут добавлен', 'success')

    elif action == 'delete':
        attr_id = request.form.get('attr_id', type=int)
        attr = LdapCustomAttribute.query.get(attr_id)
        if attr:
            db.session.delete(attr)
            db.session.commit()
            flash('Атрибут удалён', 'success')

    elif action == 'toggle':
        attr_id = request.form.get('attr_id', type=int)
        attr = LdapCustomAttribute.query.get(attr_id)
        if attr:
            attr.is_active = not attr.is_active
            db.session.commit()

    return redirect(url_for('admin.settings_ldap'))


@admin_bp.route('/settings/user-card', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_user_card():
    """Конструктор карточки пользователя"""
    fields = UserCardField.query.order_by(UserCardField.position).all()

    # Инициализация полей по умолчанию
    if not fields:
        for field_data in UserCardField.get_default_fields():
            field = UserCardField(**field_data)
            db.session.add(field)
        db.session.commit()
        fields = UserCardField.query.order_by(UserCardField.position).all()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            field = UserCardField(
                field_name=request.form.get('field_name', '').strip(),
                display_name=request.form.get('display_name', '').strip(),
                icon_type=request.form.get('icon_type', 'fontawesome'),
                icon_value=request.form.get('icon_value', '').strip(),
                icon_color=request.form.get('icon_color', 'blue'),
                section=request.form.get('section', 'contact'),
                is_link=request.form.get('is_link') == 'on',
                link_prefix=request.form.get('link_prefix', '').strip(),
                position=UserCardField.query.count() + 1
            )
            db.session.add(field)
            db.session.commit()
            flash('Поле добавлено', 'success')

        elif action == 'update':
            field_id = request.form.get('field_id', type=int)
            field = UserCardField.query.get(field_id)
            if field:
                field.display_name = request.form.get(
                    'display_name', '').strip()
                field.icon_type = request.form.get('icon_type', 'fontawesome')
                field.icon_value = request.form.get('icon_value', '').strip()
                field.icon_color = request.form.get('icon_color', 'blue')
                field.section = request.form.get('section', 'contact')
                field.is_link = request.form.get('is_link') == 'on'
                field.link_prefix = request.form.get('link_prefix', '').strip()
                field.is_visible = request.form.get('is_visible') == 'on'
                db.session.commit()
                flash('Поле обновлено', 'success')

        elif action == 'delete':
            field_id = request.form.get('field_id', type=int)
            field = UserCardField.query.get(field_id)
            if field:
                db.session.delete(field)
                db.session.commit()
                flash('Поле удалено', 'success')

        elif action == 'reorder':
            order = request.form.getlist('order[]')
            for i, field_id in enumerate(order):
                field = UserCardField.query.get(int(field_id))
                if field:
                    field.position = i + 1
            db.session.commit()

        elif action == 'toggle':
            field_id = request.form.get('field_id', type=int)
            field = UserCardField.query.get(field_id)
            if field:
                field.is_visible = not field.is_visible
                db.session.commit()

        return redirect(url_for('admin.settings_user_card'))

    # Список доступных полей пользователя
    user_fields = [
        {'name': 'email', 'label': 'Email'},
        {'name': 'phone', 'label': 'Телефон'},
        {'name': 'internal_phone', 'label': 'Внутренний телефон'},
        {'name': 'location', 'label': 'Местоположение'},
        {'name': 'department', 'label': 'Отдел'},
        {'name': 'position', 'label': 'Должность'},
        {'name': 'birthday', 'label': 'День рождения'},
        {'name': 'hire_date', 'label': 'Дата приёма'},
    ]

    # Добавляем кастомные поля из LDAP
    ldap = LdapSettings.query.first()
    if ldap:
        for attr in ldap.custom_attributes:
            if attr.is_active and attr.portal_field not in [f['name'] for f in user_fields]:
                user_fields.append(
                    {'name': attr.portal_field, 'label': attr.display_name or attr.portal_field})

    # Список цветов
    colors = ['blue', 'green', 'purple', 'amber', 'pink',
              'red', 'indigo', 'teal', 'orange', 'gray']

    # Популярные иконки FontAwesome
    icons = [
        'fa-envelope', 'fa-phone', 'fa-mobile-alt', 'fa-map-marker-alt', 'fa-building',
        'fa-birthday-cake', 'fa-calendar-check', 'fa-user', 'fa-briefcase', 'fa-id-card',
        'fa-globe', 'fa-link', 'fa-at', 'fa-fax', 'fa-home', 'fa-car', 'fa-plane',
        'fa-graduation-cap', 'fa-certificate', 'fa-star', 'fa-heart', 'fa-comment'
    ]

    return render_template('admin/settings/user_card.html',
                           fields=fields, user_fields=user_fields,
                           colors=colors, icons=icons)


@admin_bp.route('/settings/user-card/upload-icon', methods=['POST'])
@login_required
@admin_required
def upload_card_icon():
    """Загрузка кастомной иконки"""
    if 'icon' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    file = request.files['icon']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    # Проверяем расширение
    allowed = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}
    ext = file.filename.rsplit(
        '.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed:
        return jsonify({'error': 'Недопустимый формат файла'}), 400

    # Сохраняем
    import uuid
    filename = f'icon_{uuid.uuid4().hex}.{ext}'
    icons_folder = os.path.join('app/static/icons')
    os.makedirs(icons_folder, exist_ok=True)
    file.save(os.path.join(icons_folder, filename))

    return jsonify({'success': True, 'path': f'icons/{filename}'})


@admin_bp.route('/settings/fix-avatars', methods=['POST'])
@login_required
@admin_required
def fix_avatars():
    """Исправление аватарок для существующих пользователей"""
    # Обновляем всех пользователей с photo = 'default.png' или NULL
    count = User.query.filter(
        db.or_(
            User.photo == 'default.png',
            User.photo == None,
            User.photo == ''
        )
    ).update({'photo': 'image/static_avatar.png'}, synchronize_session=False)
    db.session.commit()

    flash(f'Обновлено аватарок: {count}', 'success')
    return redirect(url_for('admin.settings_ldap'))


@admin_bp.route('/settings/smtp', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'settings_smtp')
def settings_smtp():
    smtp = SmtpSettings.query.first()
    if not smtp:
        smtp = SmtpSettings()
        db.session.add(smtp)
        db.session.commit()

    if request.method == 'POST':
        smtp.is_enabled = request.form.get('is_enabled') == 'on'
        smtp.server = request.form.get('server', '').strip()
        smtp.port = request.form.get('port', 587, type=int)
        smtp.use_tls = request.form.get('use_tls') == 'on'
        smtp.use_ssl = request.form.get('use_ssl') == 'on'
        smtp.username = request.form.get('username', '').strip()

        password = request.form.get('password', '')
        if password:
            smtp.password = password

        smtp.sender_email = request.form.get('sender_email', '').strip()
        smtp.sender_name = request.form.get('sender_name', '').strip()

        db.session.commit()
        flash('Настройки SMTP сохранены', 'success')
        return redirect(url_for('admin.settings_smtp'))

    return render_template('admin/settings/smtp.html', smtp=smtp)


@admin_bp.route('/settings/smtp/test', methods=['POST'])
@login_required
@permission_required('all', 'settings_smtp')
def settings_smtp_test():
    test_email = request.form.get('test_email', current_user.email)
    result = send_email(
        test_email,
        'Тестовое письмо',
        'Это тестовое письмо от корпоративного портала.'
    )

    if result:
        flash(f'Тестовое письмо отправлено на {test_email}', 'success')
    else:
        flash('Ошибка отправки письма', 'error')

    return redirect(url_for('admin.settings_smtp'))


# === Логи (Админ) ===

@admin_bp.route('/logs')
@login_required
@permission_required('all', 'logs_view')
def logs():
    page = request.args.get('page', 1, type=int)
    action = request.args.get('action', '')

    query = AuditLog.query
    if action:
        query = query.filter_by(action=action)

    logs = query.order_by(AuditLog.created_at.desc()
                          ).paginate(page=page, per_page=50)
    actions = db.session.query(AuditLog.action).distinct().all()
    actions = [a[0] for a in actions]

    return render_template('admin/logs/index.html', logs=logs, actions=actions, current_action=action)


# === Рекомендации кандидатов (HR) ===

@admin_bp.route('/referrals')
@login_required
@permission_required('all', 'vacancies')
def referrals():
    """Список рекомендаций кандидатов"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    vacancy_id = request.args.get('vacancy_id', type=int)

    query = Referral.query
    if status:
        query = query.filter_by(status=status)
    if vacancy_id:
        query = query.filter_by(vacancy_id=vacancy_id)

    referrals = query.order_by(
        Referral.created_at.desc()).paginate(page=page, per_page=20)
    vacancies = Vacancy.query.order_by(Vacancy.title).all()

    # Статистика
    stats = {
        'total': Referral.query.count(),
        'new': Referral.query.filter_by(status='new').count(),
        'hired': Referral.query.filter_by(status='hired').count(),
    }

    return render_template('admin/referrals/index.html',
                           referrals=referrals,
                           vacancies=vacancies,
                           stats=stats,
                           current_status=status,
                           current_vacancy=vacancy_id)


@admin_bp.route('/referrals/<int:id>')
@login_required
@permission_required('all', 'vacancies')
def referral_detail(id):
    """Детали рекомендации"""
    referral = Referral.query.get_or_404(id)

    # Отмечаем как просмотренное
    if referral.status == 'new':
        referral.status = 'reviewed'
        referral.reviewed_at = datetime.utcnow()
        referral.reviewed_by_id = current_user.id
        db.session.commit()

    return render_template('admin/referrals/detail.html', referral=referral)


@admin_bp.route('/referrals/<int:id>/status', methods=['POST'])
@login_required
@permission_required('all', 'vacancies')
def referral_status(id):
    """Изменение статуса рекомендации"""
    referral = Referral.query.get_or_404(id)
    new_status = request.form.get('status')
    hr_comment = request.form.get('hr_comment', '').strip()

    if new_status in ['new', 'reviewed', 'contacted', 'hired', 'rejected']:
        referral.status = new_status
        if hr_comment:
            referral.hr_comment = hr_comment
        referral.reviewed_at = datetime.utcnow()
        referral.reviewed_by_id = current_user.id
        db.session.commit()

        # Уведомляем того, кто рекомендовал
        if new_status == 'hired':
            notify_user(referral.referrer_id,
                        '🍬 Ваш кандидат принят!',
                        f'Кандидат {referral.candidate_name} принят на работу! Спасибо за рекомендацию!',
                        icon='gift', type='success')

        flash('Статус обновлён', 'success')

    return redirect(url_for('admin.referral_detail', id=id))


@admin_bp.route('/referrals/<int:id>/download')
@login_required
@permission_required('all', 'vacancies')
def referral_download(id):
    """Скачивание резюме"""
    referral = Referral.query.get_or_404(id)

    if not referral.resume_file:
        flash('Файл не найден', 'error')
        return redirect(url_for('admin.referral_detail', id=id))

    file_path = os.path.join(REFERRAL_UPLOAD_FOLDER, referral.resume_file)
    if not os.path.exists(file_path):
        flash('Файл не найден на сервере', 'error')
        return redirect(url_for('admin.referral_detail', id=id))

    return send_file(file_path,
                     download_name=referral.resume_filename,
                     as_attachment=True)


# === Опросы (HR, Admin) ===

@admin_bp.route('/surveys')
@login_required
@permission_required('all', 'news')
def surveys():
    """Список опросов"""
    from app.models import Survey

    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')

    query = Survey.query

    surveys = query.order_by(Survey.created_at.desc()
                             ).paginate(page=page, per_page=20)

    # Статистика
    stats = {
        'total': Survey.query.count(),
        'active': Survey.query.filter_by(is_active=True).count(),
    }

    return render_template('admin/surveys/index.html',
                           surveys=surveys,
                           stats=stats,
                           current_status=status)


@admin_bp.route('/surveys/create', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'news')
def survey_create():
    """Создание опроса"""
    from app.models import Survey, SurveyQuestion, SurveyOption

    if request.method == 'POST':
        survey = Survey(
            title=request.form.get('title', '').strip(),
            description=request.form.get('description', '').strip(),
            is_active=request.form.get('is_active') == 'on',
            is_anonymous=request.form.get('is_anonymous') == 'on',
            allow_multiple_answers=request.form.get(
                'allow_multiple_answers') == 'on',
            show_results=request.form.get('show_results') == 'on',
            is_public=request.form.get('is_public') == 'on',
            publish_in_news=request.form.get('publish_in_news') == 'on',
            created_by_id=current_user.id
        )

        # Даты
        start_date = request.form.get('start_date', '')
        if start_date:
            try:
                survey.start_date = datetime.strptime(
                    start_date, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass

        end_date = request.form.get('end_date', '')
        if end_date:
            try:
                survey.end_date = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass

        # Отделы
        departments = request.form.getlist('departments')
        if departments:
            survey.set_departments(departments)

        db.session.add(survey)
        db.session.flush()

        # Добавляем вопросы
        question_texts = request.form.getlist('question_text[]')
        question_types = request.form.getlist('question_type[]')

        for i, (text, qtype) in enumerate(zip(question_texts, question_types)):
            if not text.strip():
                continue

            question = SurveyQuestion(
                survey_id=survey.id,
                text=text.strip(),
                question_type=qtype,
                position=i
            )
            db.session.add(question)
            db.session.flush()

            # Варианты ответов
            options = request.form.getlist(f'options_{i}[]')
            for j, opt_text in enumerate(options):
                if opt_text.strip():
                    option = SurveyOption(
                        question_id=question.id,
                        text=opt_text.strip(),
                        position=j
                    )
                    db.session.add(option)

        db.session.commit()

        # Публикация в новостях
        if survey.publish_in_news:
            news = News(
                title=f'📊 Новый опрос: {survey.title}',
                short_description=survey.description[:
                                                     200] if survey.description else 'Примите участие в опросе!',
                content=f'<p>{survey.description}</p><p><a href="/surveys/{survey.id}" class="text-blue-500">Пройти опрос →</a></p>',
                is_published=True,
                author_id=current_user.id
            )
            db.session.add(news)
            db.session.commit()

        flash('Опрос создан', 'success')
        return redirect(url_for('admin.surveys'))

    # Получаем список отделов
    departments = db.session.query(User.department).filter(
        User.is_active == True,
        User.department != None,
        User.department != ''
    ).distinct().order_by(User.department).all()
    departments = [d[0] for d in departments if d[0]]

    return render_template('admin/surveys/form.html', survey=None, departments=departments)


@admin_bp.route('/surveys/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'news')
def survey_edit(id):
    """Редактирование опроса"""
    from app.models import Survey, SurveyQuestion, SurveyOption

    survey = Survey.query.get_or_404(id)

    if request.method == 'POST':
        survey.title = request.form.get('title', '').strip()
        survey.description = request.form.get('description', '').strip()
        survey.is_active = request.form.get('is_active') == 'on'
        survey.is_anonymous = request.form.get('is_anonymous') == 'on'
        survey.show_results = request.form.get('show_results') == 'on'
        survey.is_public = request.form.get('is_public') == 'on'

        # Даты
        start_date = request.form.get('start_date', '')
        if start_date:
            try:
                survey.start_date = datetime.strptime(
                    start_date, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        else:
            survey.start_date = None

        end_date = request.form.get('end_date', '')
        if end_date:
            try:
                survey.end_date = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        else:
            survey.end_date = None

        # Отделы
        departments = request.form.getlist('departments')
        survey.set_departments(departments if departments else [])

        db.session.commit()
        flash('Опрос обновлён', 'success')
        return redirect(url_for('admin.surveys'))

    # Получаем список отделов
    departments = db.session.query(User.department).filter(
        User.is_active == True,
        User.department != None,
        User.department != ''
    ).distinct().order_by(User.department).all()
    departments = [d[0] for d in departments if d[0]]

    return render_template('admin/surveys/form.html', survey=survey, departments=departments)


@admin_bp.route('/surveys/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('all', 'news')
def survey_delete(id):
    """Удаление опроса"""
    from app.models import Survey

    survey = Survey.query.get_or_404(id)
    db.session.delete(survey)
    db.session.commit()
    flash('Опрос удалён', 'success')
    return redirect(url_for('admin.surveys'))


@admin_bp.route('/surveys/<int:id>/results')
@login_required
@permission_required('all', 'news')
def survey_results(id):
    """Результаты опроса"""
    from app.models import Survey, SurveyQuestion

    survey = Survey.query.get_or_404(id)
    questions = survey.questions.order_by(SurveyQuestion.position).all()
    total_responses = survey.get_total_responses()

    return render_template('admin/surveys/results.html',
                           survey=survey,
                           questions=questions,
                           total_responses=total_responses)


@admin_bp.route('/surveys/<int:id>/regenerate-token', methods=['POST'])
@login_required
@permission_required('all', 'news')
def survey_regenerate_token(id):
    """Перегенерация публичной ссылки"""
    from app.models import Survey

    survey = Survey.query.get_or_404(id)
    survey.regenerate_token()
    flash('Ссылка обновлена', 'success')
    return redirect(url_for('admin.survey_edit', id=id))


@admin_bp.route('/surveys/<int:id>/questions', methods=['POST'])
@login_required
@permission_required('all', 'news')
def survey_add_question(id):
    """Добавление вопроса к существующему опросу"""
    from app.models import Survey, SurveyQuestion, SurveyOption

    survey = Survey.query.get_or_404(id)

    text = request.form.get('text', '').strip()
    qtype = request.form.get('question_type', 'single')

    if not text:
        flash('Введите текст вопроса', 'error')
        return redirect(url_for('admin.survey_edit', id=id))

    position = survey.questions.count()
    question = SurveyQuestion(
        survey_id=survey.id,
        text=text,
        question_type=qtype,
        position=position
    )
    db.session.add(question)
    db.session.flush()

    # Варианты ответов
    options = request.form.getlist('options[]')
    for i, opt_text in enumerate(options):
        if opt_text.strip():
            option = SurveyOption(
                question_id=question.id,
                text=opt_text.strip(),
                position=i
            )
            db.session.add(option)

    db.session.commit()
    flash('Вопрос добавлен', 'success')
    return redirect(url_for('admin.survey_edit', id=id))


@admin_bp.route('/surveys/questions/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('all', 'news')
def survey_delete_question(id):
    """Удаление вопроса"""
    from app.models import SurveyQuestion

    question = SurveyQuestion.query.get_or_404(id)
    survey_id = question.survey_id
    db.session.delete(question)
    db.session.commit()
    flash('Вопрос удалён', 'success')
    return redirect(url_for('admin.survey_edit', id=survey_id))


# === Тесты (HR, Admin) ===

@admin_bp.route('/tests')
@login_required
@permission_required('all', 'news')
def tests():
    """Список тестов"""
    from app.models import Test

    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')

    query = Test.query
    if category:
        query = query.filter_by(category=category)

    tests = query.order_by(Test.created_at.desc()).paginate(
        page=page, per_page=20)

    stats = {
        'total': Test.query.count(),
        'active': Test.query.filter_by(is_active=True).count(),
        'security': Test.query.filter_by(category='security').count(),
    }

    return render_template('admin/tests/index.html',
                           tests=tests,
                           stats=stats,
                           current_category=category)


@admin_bp.route('/tests/create', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'news')
def test_create():
    """Создание теста"""
    from app.models import Test, TestQuestion, TestOption

    if request.method == 'POST':
        test = Test(
            title=request.form.get('title', '').strip(),
            description=request.form.get('description', '').strip(),
            category=request.form.get('category', 'general'),
            is_active=request.form.get('is_active') == 'on',
            time_limit=request.form.get('time_limit', type=int) or None,
            passing_score=request.form.get('passing_score', 60, type=int),
            show_correct_answers=request.form.get(
                'show_correct_answers') == 'on',
            allow_retake=request.form.get('allow_retake') == 'on',
            shuffle_questions=request.form.get('shuffle_questions') == 'on',
            shuffle_options=request.form.get('shuffle_options') == 'on',
            is_mandatory=request.form.get('is_mandatory') == 'on',
            created_by_id=current_user.id
        )

        # Срок
        deadline = request.form.get('deadline', '')
        if deadline:
            try:
                test.deadline = datetime.strptime(deadline, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass

        # Отделы
        departments = request.form.getlist('departments')
        if departments:
            test.set_departments(departments)

        db.session.add(test)
        db.session.flush()

        # Добавляем вопросы
        question_texts = request.form.getlist('question_text[]')
        question_types = request.form.getlist('question_type[]')
        question_points = request.form.getlist('question_points[]')
        question_explanations = request.form.getlist('question_explanation[]')

        for i, text in enumerate(question_texts):
            if not text.strip():
                continue

            qtype = question_types[i] if i < len(question_types) else 'single'
            points = int(question_points[i]) if i < len(
                question_points) and question_points[i] else 1
            explanation = question_explanations[i] if i < len(
                question_explanations) else ''

            question = TestQuestion(
                test_id=test.id,
                text=text.strip(),
                question_type=qtype,
                points=points,
                explanation=explanation.strip(),
                position=i
            )
            db.session.add(question)
            db.session.flush()

            # Варианты ответов
            options = request.form.getlist(f'options_{i}[]')
            correct = request.form.getlist(f'correct_{i}[]')

            for j, opt_text in enumerate(options):
                if opt_text.strip():
                    option = TestOption(
                        question_id=question.id,
                        text=opt_text.strip(),
                        is_correct=str(j) in correct,
                        position=j
                    )
                    db.session.add(option)

        db.session.commit()
        flash('Тест создан', 'success')
        return redirect(url_for('admin.tests'))

    # Получаем список отделов
    departments = db.session.query(User.department).filter(
        User.is_active == True,
        User.department != None,
        User.department != ''
    ).distinct().order_by(User.department).all()
    departments = [d[0] for d in departments if d[0]]

    return render_template('admin/tests/form.html', test=None, departments=departments)


@admin_bp.route('/tests/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'news')
def test_edit(id):
    """Редактирование теста"""
    from app.models import Test, TestQuestion, TestOption

    test = Test.query.get_or_404(id)

    if request.method == 'POST':
        test.title = request.form.get('title', '').strip()
        test.description = request.form.get('description', '').strip()
        test.category = request.form.get('category', 'general')
        test.is_active = request.form.get('is_active') == 'on'
        test.time_limit = request.form.get('time_limit', type=int) or None
        test.passing_score = request.form.get('passing_score', 60, type=int)
        test.show_correct_answers = request.form.get(
            'show_correct_answers') == 'on'
        test.allow_retake = request.form.get('allow_retake') == 'on'
        test.shuffle_questions = request.form.get('shuffle_questions') == 'on'
        test.shuffle_options = request.form.get('shuffle_options') == 'on'
        test.is_mandatory = request.form.get('is_mandatory') == 'on'

        deadline = request.form.get('deadline', '')
        if deadline:
            try:
                test.deadline = datetime.strptime(deadline, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        else:
            test.deadline = None

        departments = request.form.getlist('departments')
        test.set_departments(departments if departments else [])

        db.session.commit()
        flash('Тест обновлён', 'success')
        return redirect(url_for('admin.tests'))

    departments = db.session.query(User.department).filter(
        User.is_active == True,
        User.department != None,
        User.department != ''
    ).distinct().order_by(User.department).all()
    departments = [d[0] for d in departments if d[0]]

    return render_template('admin/tests/form.html', test=test, departments=departments)


@admin_bp.route('/tests/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('all', 'news')
def test_delete(id):
    """Удаление теста"""
    from app.models import Test

    test = Test.query.get_or_404(id)
    db.session.delete(test)
    db.session.commit()
    flash('Тест удалён', 'success')
    return redirect(url_for('admin.tests'))


@admin_bp.route('/tests/<int:id>/results')
@login_required
@permission_required('all', 'news')
def test_results(id):
    """Результаты теста"""
    from app.models import Test, TestAttempt

    test = Test.query.get_or_404(id)

    page = request.args.get('page', 1, type=int)
    attempts = TestAttempt.query.filter_by(
        test_id=test.id,
        is_completed=True
    ).order_by(TestAttempt.finished_at.desc()).paginate(page=page, per_page=30)

    # Статистика
    all_attempts = TestAttempt.query.filter_by(
        test_id=test.id, is_completed=True).all()
    stats = {
        'total_attempts': len(all_attempts),
        'passed': sum(1 for a in all_attempts if a.passed),
        'failed': sum(1 for a in all_attempts if not a.passed),
        'avg_score': round(sum(a.percentage for a in all_attempts) / len(all_attempts), 1) if all_attempts else 0,
        'unique_users': len(set(a.user_id for a in all_attempts))
    }

    return render_template('admin/tests/results.html',
                           test=test,
                           attempts=attempts,
                           stats=stats)


@admin_bp.route('/tests/<int:id>/questions', methods=['POST'])
@login_required
@permission_required('all', 'news')
def test_add_question(id):
    """Добавление вопроса к тесту"""
    from app.models import Test, TestQuestion, TestOption

    test = Test.query.get_or_404(id)

    text = request.form.get('text', '').strip()
    qtype = request.form.get('question_type', 'single')
    points = request.form.get('points', 1, type=int)
    explanation = request.form.get('explanation', '').strip()

    if not text:
        flash('Введите текст вопроса', 'error')
        return redirect(url_for('admin.test_edit', id=id))

    position = test.questions.count()
    question = TestQuestion(
        test_id=test.id,
        text=text,
        question_type=qtype,
        points=points,
        explanation=explanation,
        position=position
    )
    db.session.add(question)
    db.session.flush()

    # Варианты ответов
    options = request.form.getlist('options[]')
    correct = request.form.getlist('correct[]')

    for i, opt_text in enumerate(options):
        if opt_text.strip():
            option = TestOption(
                question_id=question.id,
                text=opt_text.strip(),
                is_correct=str(i) in correct,
                position=i
            )
            db.session.add(option)

    db.session.commit()
    flash('Вопрос добавлен', 'success')
    return redirect(url_for('admin.test_edit', id=id))


@admin_bp.route('/tests/questions/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('all', 'news')
def test_delete_question(id):
    """Удаление вопроса"""
    from app.models import TestQuestion

    question = TestQuestion.query.get_or_404(id)
    test_id = question.test_id
    db.session.delete(question)
    db.session.commit()
    flash('Вопрос удалён', 'success')
    return redirect(url_for('admin.test_edit', id=test_id))


# === Настройки меню ===

@admin_bp.route('/settings/menu', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'settings_menu')
def settings_menu():
    """Настройка пунктов меню"""
    from app.models import MenuItem

    # Инициализация если пусто
    MenuItem.init_default()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update':
            # Сначала скрываем все
            MenuItem.query.update({'is_visible': False})

            # Показываем выбранные (макс 4)
            visible_ids = request.form.getlist('visible[]')[:4]
            for item_id in visible_ids:
                item = MenuItem.query.get(int(item_id))
                if item:
                    item.is_visible = True

            db.session.commit()
            flash('Меню обновлено', 'success')

        elif action == 'reorder':
            order = request.form.getlist('order[]')
            for i, item_id in enumerate(order):
                item = MenuItem.query.get(int(item_id))
                if item:
                    item.position = i + 1
            db.session.commit()

        return redirect(url_for('admin.settings_menu'))

    items = MenuItem.query.order_by(MenuItem.position).all()
    return render_template('admin/settings/menu.html', items=items)


# === Настройки отпусков ===

@admin_bp.route('/settings/vacations', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'vacations')
def settings_vacations():
    """Настройки системы отпусков"""
    from app.models import VacationSettings

    settings = VacationSettings.get_settings()

    if request.method == 'POST':
        settings.annual_days_default = request.form.get(
            'annual_days_default', type=int) or 28
        settings.dayoff_enabled = request.form.get('dayoff_enabled') == 'on'
        settings.dayoff_days_limit = request.form.get(
            'dayoff_days_limit', type=int) or 0

        db.session.commit()
        flash('Настройки отпусков сохранены', 'success')
        return redirect(url_for('admin.settings_vacations'))

    return render_template('admin/settings/vacations.html', settings=settings)


# === Документация ===

@admin_bp.route('/documentation')
@login_required
@admin_required
def documentation():
    """Страница документации для администраторов"""
    section = request.args.get('section', 'overview')
    search_query = request.args.get('q', '')

    return render_template('admin/documentation.html',
                           section=section,
                           search_query=search_query)


# === Отпуска (HR) ===

@admin_bp.route('/vacations')
@login_required
@permission_required('all', 'vacancies')
def vacations_hr():
    """Панель HR для управления отпусками"""
    from app.models import VacationRequest, VacationConflictRule

    tab = request.args.get('tab', 'pending')

    # Ожидающие HR
    pending = VacationRequest.query.filter_by(status='pending_hr').order_by(
        VacationRequest.created_at.desc()
    ).all()
    pending_count = len(pending)

    # Все заявки
    all_requests = []
    if tab == 'all':
        query = VacationRequest.query
        status_filter = request.args.get('status')
        dept_filter = request.args.get('department')

        if status_filter:
            query = query.filter_by(status=status_filter)
        if dept_filter:
            query = query.join(User).filter(User.department == dept_filter)

        all_requests = query.order_by(
            VacationRequest.created_at.desc()).limit(100).all()

    # Правила конфликтов
    rules = []
    users = []
    if tab == 'rules':
        rules = VacationConflictRule.query.all()
        users = User.query.filter_by(is_active=True).order_by(
            User.lastname, User.firstname).all()

    # Список отделов
    departments = db.session.query(User.department).filter(
        User.is_active == True,
        User.department != None,
        User.department != ''
    ).distinct().order_by(User.department).all()
    departments = [d[0] for d in departments if d[0]]

    return render_template('admin/vacations/index.html',
                           tab=tab,
                           pending=pending,
                           pending_count=pending_count,
                           all_requests=all_requests,
                           rules=rules,
                           users=users,
                           departments=departments)


@admin_bp.route('/vacations/<int:id>/approve', methods=['POST'])
@login_required
@permission_required('all', 'vacancies')
def vacation_hr_approve(id):
    """Одобрение HR"""
    from app.models import VacationRequest, UserVacationBalance

    vacation = VacationRequest.query.get_or_404(id)

    if vacation.status != 'pending_hr':
        flash('Заявка уже обработана', 'warning')
        return redirect(url_for('admin.vacations_hr'))

    comment = request.form.get('comment', '').strip()

    vacation.status = 'approved'
    vacation.hr_id = current_user.id
    vacation.hr_approved_at = datetime.utcnow()
    vacation.hr_comment = comment

    # Обновляем баланс дней отпуска
    days_count = vacation.days_count
    balance = UserVacationBalance.get_or_create(vacation.user_id)

    if vacation.vacation_type == 'annual':
        balance.annual_days_used += days_count
    elif vacation.vacation_type == 'dayoff':
        balance.dayoff_days_used += days_count

    db.session.commit()

    # Уведомление сотруднику
    Notification.create(
        vacation.user_id,
        '✅ Отпуск одобрен',
        f'Ваш отпуск с {vacation.start_date.strftime("%d.%m.%Y")} по {vacation.end_date.strftime("%d.%m.%Y")} одобрен',
        link=url_for('vacations.my_requests'),
        icon='check-circle',
        type='success'
    )

    flash('Заявка одобрена', 'success')
    return redirect(url_for('admin.vacations_hr'))


@admin_bp.route('/vacations/<int:id>/reject', methods=['POST'])
@login_required
@permission_required('all', 'vacancies')
def vacation_hr_reject(id):
    """Отклонение HR"""
    from app.models import VacationRequest

    vacation = VacationRequest.query.get_or_404(id)

    if vacation.status != 'pending_hr':
        flash('Заявка уже обработана', 'warning')
        return redirect(url_for('admin.vacations_hr'))

    comment = request.form.get('comment', '').strip()
    if not comment:
        flash('Укажите причину отклонения', 'error')
        return redirect(url_for('admin.vacations_hr'))

    vacation.status = 'rejected_hr'
    vacation.hr_id = current_user.id
    vacation.hr_approved_at = datetime.utcnow()
    vacation.hr_comment = comment
    db.session.commit()

    # Уведомление сотруднику
    Notification.create(
        vacation.user_id,
        '❌ Отпуск отклонён HR',
        f'Причина: {comment}',
        link=url_for('vacations.my_requests'),
        icon='times-circle',
        type='error'
    )

    flash('Заявка отклонена', 'success')
    return redirect(url_for('admin.vacations_hr'))


@admin_bp.route('/vacations/rules/add', methods=['POST'])
@login_required
@permission_required('all', 'vacancies')
def vacation_rule_add():
    """Добавление правила конфликта"""
    from app.models import VacationConflictRule

    user1_id = request.form.get('user1_id', type=int)
    user2_id = request.form.get('user2_id', type=int)
    reason = request.form.get('reason', '').strip()

    if not user1_id or not user2_id:
        flash('Выберите обоих сотрудников', 'error')
        return redirect(url_for('admin.vacations_hr', tab='rules'))

    if user1_id == user2_id:
        flash('Нельзя создать правило для одного сотрудника', 'error')
        return redirect(url_for('admin.vacations_hr', tab='rules'))

    # Проверка существования
    if VacationConflictRule.check_conflict(user1_id, user2_id):
        flash('Такое правило уже существует', 'warning')
        return redirect(url_for('admin.vacations_hr', tab='rules'))

    # Нормализуем порядок ID
    if user1_id > user2_id:
        user1_id, user2_id = user2_id, user1_id

    rule = VacationConflictRule(
        user1_id=user1_id,
        user2_id=user2_id,
        reason=reason
    )
    db.session.add(rule)
    db.session.commit()

    flash('Правило добавлено', 'success')
    return redirect(url_for('admin.vacations_hr', tab='rules'))


@admin_bp.route('/vacations/rules/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('all', 'vacancies')
def vacation_rule_delete(id):
    """Удаление правила конфликта"""
    from app.models import VacationConflictRule

    rule = VacationConflictRule.query.get_or_404(id)
    db.session.delete(rule)
    db.session.commit()

    flash('Правило удалено', 'success')
    return redirect(url_for('admin.vacations_hr', tab='rules'))


# === Управление ролями ===

@admin_bp.route('/roles')
@login_required
@permission_required('all', 'roles_manage')
def roles():
    """Список ролей"""
    roles = Role.query.order_by(Role.is_system.desc(), Role.display_name).all()
    available_permissions = {k: v for k,
                             v in Role.AVAILABLE_PERMISSIONS.items()}
    return render_template('admin/roles/index.html',
                           roles=roles,
                           available_permissions=available_permissions)


@admin_bp.route('/roles/create', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'roles_manage')
def role_create():
    """Создание роли"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip().lower()
        display_name = request.form.get('display_name', '').strip()
        description = request.form.get('description', '').strip()
        permissions_list = request.form.getlist('permissions')

        if not name or not display_name:
            flash('Заполните обязательные поля', 'error')
            return redirect(url_for('admin.role_create'))

        # Проверка уникальности
        if Role.query.filter_by(name=name).first():
            flash('Роль с таким именем уже существует', 'error')
            return redirect(url_for('admin.role_create'))

        # Формируем права
        permissions = {perm: True for perm in permissions_list}

        role = Role(
            name=name,
            display_name=display_name,
            description=description,
            is_system=False
        )
        role.set_permissions(permissions)

        db.session.add(role)
        db.session.commit()

        flash(f'Роль "{display_name}" создана', 'success')
        return redirect(url_for('admin.roles'))

    permissions_grouped = Role.get_permissions_grouped()
    return render_template('admin/roles/form.html',
                           role=None,
                           permissions_grouped=permissions_grouped)


@admin_bp.route('/roles/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('all', 'roles_manage')
def role_edit(id):
    """Редактирование роли"""
    role = Role.query.get_or_404(id)

    if request.method == 'POST':
        # Системное имя можно менять только для несистемных ролей
        if not role.is_system:
            new_name = request.form.get('name', '').strip().lower()
            if new_name and new_name != role.name:
                if Role.query.filter_by(name=new_name).first():
                    flash('Роль с таким именем уже существует', 'error')
                    return redirect(url_for('admin.role_edit', id=id))
                role.name = new_name

        role.display_name = request.form.get(
            'display_name', role.display_name).strip()
        role.description = request.form.get('description', '').strip()

        # Обновляем права
        permissions_list = request.form.getlist('permissions')
        permissions = {perm: True for perm in permissions_list}
        role.set_permissions(permissions)

        db.session.commit()
        flash('Роль обновлена', 'success')
        return redirect(url_for('admin.roles'))

    permissions_grouped = Role.get_permissions_grouped()
    return render_template('admin/roles/form.html',
                           role=role,
                           permissions_grouped=permissions_grouped)


@admin_bp.route('/roles/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('all', 'roles_manage')
def role_delete(id):
    """Удаление роли"""
    role = Role.query.get_or_404(id)

    if role.is_system:
        flash('Нельзя удалить системную роль', 'error')
        return redirect(url_for('admin.roles'))

    if role.users.count() > 0:
        flash('Нельзя удалить роль с пользователями', 'error')
        return redirect(url_for('admin.roles'))

    db.session.delete(role)
    db.session.commit()
    flash('Роль удалена', 'success')
    return redirect(url_for('admin.roles'))


# === Настройки баг-трекера ===

@admin_bp.route('/bugtracker-settings')
@login_required
@admin_required
def bugtracker_settings():
    """Управление доступом к баг-трекеру"""
    from app.blueprints.bugtracker import BugTrackerAccess
    users = User.query.filter_by(is_active=True).order_by(User.lastname).all()
    access_list = BugTrackerAccess.query.all()
    access_user_ids = {a.user_id for a in access_list}
    return render_template('admin/bugtracker_settings.html',
                           users=users, access_list=access_list,
                           access_user_ids=access_user_ids)


@admin_bp.route('/bugtracker-settings/toggle', methods=['POST'])
@login_required
@admin_required
def bugtracker_toggle_access():
    """Включить/выключить доступ пользователя к баг-трекеру"""
    from app.blueprints.bugtracker import BugTrackerAccess
    user_id = request.form.get('user_id', type=int)
    if not user_id:
        flash('Пользователь не указан', 'error')
        return redirect(url_for('admin.bugtracker_settings'))

    access = BugTrackerAccess.query.filter_by(user_id=user_id).first()
    if access:
        db.session.delete(access)
        flash('Доступ закрыт', 'success')
    else:
        access = BugTrackerAccess(
            user_id=user_id,
            can_create=True,
            can_assign='can_assign' in request.form,
            can_close='can_close' in request.form
        )
        db.session.add(access)
        flash('Доступ открыт', 'success')

    db.session.commit()
    return redirect(url_for('admin.bugtracker_settings'))
