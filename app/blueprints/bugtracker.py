# -*- coding: utf-8 -*-
"""
Баг-трекер: создание, назначение и отслеживание задач
"""
import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app import db

bugtracker_bp = Blueprint('bugtracker', __name__)

UPLOAD_DIR = os.path.join('app', 'static', 'uploads', 'bugs')


class BugProject(db.Model):
    """Проект в баг-трекере"""
    __tablename__ = 'bug_projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    # active, paused, closed, archived
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship(
        'BugProjectMember', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    tickets = db.relationship('BugTicket', backref='project', lazy='dynamic')


class BugProjectMember(db.Model):
    """Участник проекта"""
    __tablename__ = 'bug_project_members'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey(
        'bug_projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # designer, tester, developer
    role = db.Column(db.String(20), nullable=False, default='developer')

    user = db.relationship('User')


class BugTicket(db.Model):
    """Задача/баг"""
    __tablename__ = 'bug_tickets'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    steps = db.Column(db.Text)
    expected_result = db.Column(db.Text)
    actual_result = db.Column(db.Text)
    # bug, improvement
    ticket_type = db.Column(db.String(20), default='bug')
    # low, medium, high, critical
    priority = db.Column(db.String(20), default='medium')
    # new, progress, testing, review, resolved, closed
    status = db.Column(db.String(20), default='new')
    environment = db.Column(db.String(255))

    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    project_id = db.Column(db.Integer, db.ForeignKey(
        'bug_projects.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    creator = db.relationship('User', foreign_keys=[
                              creator_id], backref='bugs_created')
    assignee = db.relationship('User', foreign_keys=[
                               assignee_id], backref='bugs_assigned')
    attachments = db.relationship(
        'BugAttachment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')


class BugAttachment(db.Model):
    """Вложение к задаче (скриншоты, файлы)"""
    __tablename__ = 'bug_attachments'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey(
        'bug_tickets.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class BugComment(db.Model):
    """Комментарий к задаче"""
    __tablename__ = 'bug_comments'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey(
        'bug_tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')
    ticket = db.relationship('BugTicket', backref=db.backref(
        'comments', lazy='dynamic', order_by='BugComment.created_at'))


class BugTrackerAccess(db.Model):
    """Доступ пользователей к баг-трекеру"""
    __tablename__ = 'bug_tracker_access'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id'), nullable=False, unique=True)
    can_create = db.Column(db.Boolean, default=True)
    can_assign = db.Column(db.Boolean, default=False)
    can_close = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='bugtracker_access')


def _generate_ticket_id():
    last = BugTicket.query.order_by(BugTicket.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f'BF-{1000 + num}'


def _has_access():
    """Проверяет доступ текущего пользователя к баг-трекеру"""
    if current_user.role and current_user.role.name == 'admin':
        return True
    access = BugTrackerAccess.query.filter_by(user_id=current_user.id).first()
    return access is not None


def _save_attachment(file, ticket_id):
    """Сохраняет вложение"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    filename = f'{uuid.uuid4().hex}{ext}'
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    attachment = BugAttachment(
        ticket_id=ticket_id,
        filename=filename,
        original_name=file.filename,
        uploader_id=current_user.id
    )
    db.session.add(attachment)
    return attachment


@bugtracker_bp.route('/')
@login_required
def index():
    if not _has_access():
        flash('Нет доступа к баг-трекеру', 'error')
        return redirect(url_for('main.index'))

    tab = request.args.get('tab', 'projects')

    if tab == 'my_tasks':
        # Мои задачи — задачи назначенные текущему пользователю из всех проектов
        sort = request.args.get('sort', 'created_at')
        order = request.args.get('order', 'desc')
        status_filter = request.args.get('status', 'all')
        priority_filter = request.args.get('priority', 'all')
        search = request.args.get('q', '')

        query = BugTicket.query.filter_by(assignee_id=current_user.id)

        if status_filter != 'all':
            query = query.filter_by(status=status_filter)
        if priority_filter != 'all':
            query = query.filter_by(priority=priority_filter)
        if search:
            query = query.filter(
                db.or_(
                    BugTicket.title.ilike(f'%{search}%'),
                    BugTicket.ticket_id.ilike(f'%{search}%'),
                    BugTicket.description.ilike(f'%{search}%')
                )
            )

        sort_map = {
            'ticket_id': BugTicket.ticket_id,
            'created_at': BugTicket.created_at,
            'priority': BugTicket.priority,
            'ticket_type': BugTicket.ticket_type,
            'status': BugTicket.status,
        }
        sort_col = sort_map.get(sort, BugTicket.created_at)
        if order == 'asc':
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        tickets = query.all()

        return render_template('bugtracker/index.html',
                               tab=tab, tickets=tickets,
                               sort=sort, order=order,
                               status_filter=status_filter,
                               priority_filter=priority_filter,
                               search=search)
    elif tab == 'all_tasks':
        # Все задачи из всех проектов
        sort = request.args.get('sort', 'created_at')
        order = request.args.get('order', 'desc')
        status_filter = request.args.get('status', 'all')
        priority_filter = request.args.get('priority', 'all')
        search = request.args.get('q', '')

        query = BugTicket.query

        if status_filter != 'all':
            query = query.filter_by(status=status_filter)
        if priority_filter != 'all':
            query = query.filter_by(priority=priority_filter)
        if search:
            query = query.filter(
                db.or_(
                    BugTicket.title.ilike(f'%{search}%'),
                    BugTicket.ticket_id.ilike(f'%{search}%'),
                    BugTicket.description.ilike(f'%{search}%')
                )
            )

        sort_map = {
            'ticket_id': BugTicket.ticket_id,
            'created_at': BugTicket.created_at,
            'priority': BugTicket.priority,
            'ticket_type': BugTicket.ticket_type,
            'status': BugTicket.status,
        }
        sort_col = sort_map.get(sort, BugTicket.created_at)
        if order == 'asc':
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        tickets = query.all()

        return render_template('bugtracker/index.html',
                               tab=tab, tickets=tickets,
                               sort=sort, order=order,
                               status_filter=status_filter,
                               priority_filter=priority_filter,
                               search=search)
    else:
        # Проекты — вкладка по умолчанию
        project_status = request.args.get('project_status', 'active')
        project_list = BugProject.query.filter_by(status=project_status).order_by(
            BugProject.created_at.desc()).all()

        return render_template('bugtracker/index.html',
                               tab=tab, projects=project_list,
                               project_status=project_status)


@bugtracker_bp.route('/projects/<int:project_id>/create', methods=['GET', 'POST'])
@login_required
def create(project_id):
    if not _has_access():
        flash('Нет доступа', 'error')
        return redirect(url_for('main.index'))

    project = BugProject.query.get_or_404(project_id)

    if request.method == 'POST':
        ticket = BugTicket(
            ticket_id=_generate_ticket_id(),
            title=request.form['title'],
            description=request.form.get('description', ''),
            steps=request.form.get('steps', ''),
            expected_result=request.form.get('expected_result', ''),
            actual_result=request.form.get('actual_result', ''),
            ticket_type=request.form.get('ticket_type', 'bug'),
            priority=request.form.get('priority', 'medium'),
            environment=request.form.get('environment', ''),
            creator_id=current_user.id,
            assignee_id=request.form.get('assignee_id') or None,
            project_id=project.id,
        )
        db.session.add(ticket)
        db.session.flush()

        # Вложения
        files = request.files.getlist('attachments')
        for f in files:
            if f and f.filename:
                _save_attachment(f, ticket.id)

        db.session.commit()

        # Уведомление назначенному сотруднику
        if ticket.assignee_id and ticket.assignee_id != current_user.id:
            from app.models import Notification
            Notification.create(
                ticket.assignee_id,
                f'Вам назначена задача {ticket.ticket_id}',
                f'{ticket.title}',
                url_for('bugtracker.detail', ticket_id=ticket.ticket_id),
                'bug', 'info'
            )

        flash(f'Задача {ticket.ticket_id} создана', 'success')
        return redirect(url_for('bugtracker.detail', ticket_id=ticket.ticket_id))

    # Только пользователи с доступом к баг-трекеру
    from app.models import User
    access_ids = [a.user_id for a in BugTrackerAccess.query.all()]
    admin_ids = [u.id for u in User.query.join(
        User.role).filter_by(name='admin').all()]
    allowed_ids = list(set(access_ids + admin_ids))
    users = User.query.filter(User.id.in_(
        allowed_ids), User.is_active == True).all()
    return render_template('bugtracker/create.html', users=users, project=project)


@bugtracker_bp.route('/<ticket_id>')
@login_required
def detail(ticket_id):
    if not _has_access():
        flash('Нет доступа', 'error')
        return redirect(url_for('main.index'))

    ticket = BugTicket.query.filter_by(ticket_id=ticket_id).first_or_404()
    # Только пользователи с доступом
    from app.models import User
    access_ids = [a.user_id for a in BugTrackerAccess.query.all()]
    admin_ids = [u.id for u in User.query.join(
        User.role).filter_by(name='admin').all()]
    allowed_ids = list(set(access_ids + admin_ids))
    users = User.query.filter(User.id.in_(
        allowed_ids), User.is_active == True).all()
    projects = BugProject.query.filter_by(
        status='active').order_by(BugProject.name).all()

    # Check if current user is a tester on the ticket's project
    is_tester = False
    is_developer = False
    if ticket.project_id:
        tester_member = BugProjectMember.query.filter_by(
            project_id=ticket.project_id, user_id=current_user.id, role='tester'
        ).first()
        is_tester = tester_member is not None
        dev_member = BugProjectMember.query.filter_by(
            project_id=ticket.project_id, user_id=current_user.id, role='developer'
        ).first()
        is_developer = dev_member is not None

    return render_template('bugtracker/detail.html', ticket=ticket, users=users,
                           projects=projects, is_tester=is_tester, is_developer=is_developer)


@bugtracker_bp.route('/<ticket_id>/update', methods=['POST'])
@login_required
def update(ticket_id):
    if not _has_access():
        return jsonify({'error': 'Нет доступа'}), 403

    ticket = BugTicket.query.filter_by(ticket_id=ticket_id).first_or_404()
    from app.models import Notification

    old_status = ticket.status
    old_assignee_id = ticket.assignee_id

    if 'status' in request.form:
        ticket.status = request.form['status']
        if ticket.status in ('resolved', 'closed') and old_status not in ('resolved', 'closed'):
            ticket.resolved_at = datetime.utcnow()

    if 'assignee_id' in request.form:
        ticket.assignee_id = request.form['assignee_id'] or None

    if 'priority' in request.form:
        ticket.priority = request.form['priority']

    if 'ticket_type' in request.form:
        ticket.ticket_type = request.form['ticket_type']

    if 'title' in request.form and request.form['title'].strip():
        ticket.title = request.form['title'].strip()

    if 'description' in request.form:
        ticket.description = request.form['description']

    if 'steps' in request.form:
        ticket.steps = request.form['steps']

    if 'expected_result' in request.form:
        ticket.expected_result = request.form['expected_result']

    if 'actual_result' in request.form:
        ticket.actual_result = request.form['actual_result']

    if 'environment' in request.form:
        ticket.environment = request.form['environment']

    if 'project_id' in request.form:
        ticket.project_id = request.form['project_id'] or None

    # Новые вложения
    files = request.files.getlist('attachments')
    for f in files:
        if f and f.filename:
            _save_attachment(f, ticket.id)

    db.session.commit()

    # Уведомления
    STATUS_NAMES = {
        'new': 'Новый', 'progress': 'В работе', 'review': 'На проверке',
        'resolved': 'Решено', 'closed': 'Закрыто'
    }
    link = url_for('bugtracker.detail', ticket_id=ticket.ticket_id)

    # Смена статуса — уведомляем создателя и ответственного
    if 'status' in request.form and ticket.status != old_status:
        notify_ids = set()
        if ticket.creator_id and ticket.creator_id != current_user.id:
            notify_ids.add(ticket.creator_id)
        if ticket.assignee_id and ticket.assignee_id != current_user.id:
            notify_ids.add(ticket.assignee_id)

        for uid in notify_ids:
            Notification.create(
                uid,
                f'{ticket.ticket_id}: статус изменён на "{STATUS_NAMES.get(ticket.status, ticket.status)}"',
                ticket.title,
                link, 'bug', 'info'
            )

    # Смена ответственного — уведомляем нового
    if ticket.assignee_id and ticket.assignee_id != old_assignee_id and ticket.assignee_id != current_user.id:
        Notification.create(
            ticket.assignee_id,
            f'Вам назначена задача {ticket.ticket_id}',
            ticket.title,
            link, 'bug', 'warning'
        )

    flash('Задача обновлена', 'success')
    return redirect(url_for('bugtracker.detail', ticket_id=ticket_id))


@bugtracker_bp.route('/attachment/<int:att_id>/delete', methods=['POST'])
@login_required
def delete_attachment(att_id):
    """Удалить вложение"""
    if not _has_access():
        return jsonify({'error': 'Нет доступа'}), 403

    att = BugAttachment.query.get_or_404(att_id)
    ticket = BugTicket.query.get(att.ticket_id)

    # Удаляем файл с диска
    filepath = os.path.join(UPLOAD_DIR, att.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(att)
    db.session.commit()
    flash('Файл удалён', 'success')
    return redirect(url_for('bugtracker.detail', ticket_id=ticket.ticket_id))


@bugtracker_bp.route('/<ticket_id>/comment', methods=['POST'])
@login_required
def add_comment(ticket_id):
    if not _has_access():
        return jsonify({'error': 'Нет доступа'}), 403

    ticket = BugTicket.query.filter_by(ticket_id=ticket_id).first_or_404()
    text = request.form.get('text', '').strip()
    if text:
        comment = BugComment(ticket_id=ticket.id,
                             user_id=current_user.id, text=text)
        db.session.add(comment)
        db.session.commit()

        # Уведомления создателю и ответственному (кроме автора комментария)
        from app.models import Notification
        notify_ids = set()
        if ticket.creator_id and ticket.creator_id != current_user.id:
            notify_ids.add(ticket.creator_id)
        if ticket.assignee_id and ticket.assignee_id != current_user.id:
            notify_ids.add(ticket.assignee_id)

        for uid in notify_ids:
            Notification.create(
                uid,
                f'{ticket.ticket_id}: новый комментарий',
                f'{current_user.short_name}: {text[:100]}',
                url_for('bugtracker.detail', ticket_id=ticket.ticket_id),
                'comment', 'info'
            )

        flash('Комментарий добавлен', 'success')

    return redirect(url_for('bugtracker.detail', ticket_id=ticket_id))


# ==================== Projects ====================

@bugtracker_bp.route('/projects/create', methods=['GET', 'POST'])
@login_required
def create_project():
    if not _has_access():
        flash('Нет доступа', 'error')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        project = BugProject(
            name=request.form['name'],
            description=request.form.get('description', ''),
        )
        db.session.add(project)
        db.session.flush()

        # Add members
        member_ids = request.form.getlist('member_ids')
        member_roles = request.form.getlist('member_roles')
        for uid, role in zip(member_ids, member_roles):
            if uid:
                member = BugProjectMember(
                    project_id=project.id,
                    user_id=int(uid),
                    role=role
                )
                db.session.add(member)

        db.session.commit()
        flash(f'Проект "{project.name}" создан', 'success')
        return redirect(url_for('bugtracker.project_detail', project_id=project.id))

    from app.models import User
    access_ids = [a.user_id for a in BugTrackerAccess.query.all()]
    admin_ids = [u.id for u in User.query.join(
        User.role).filter_by(name='admin').all()]
    allowed_ids = list(set(access_ids + admin_ids))
    users = User.query.filter(User.id.in_(
        allowed_ids), User.is_active == True).all()
    return render_template('bugtracker/project_create.html', users=users)


@bugtracker_bp.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    if not _has_access():
        flash('Нет доступа', 'error')
        return redirect(url_for('main.index'))

    project = BugProject.query.get_or_404(project_id)

    task_tab = request.args.get('task_tab', 'my')
    sort = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')

    query = BugTicket.query.filter_by(project_id=project.id)

    if task_tab == 'my':
        query = query.filter_by(assignee_id=current_user.id)

    sort_map = {
        'ticket_id': BugTicket.ticket_id,
        'created_at': BugTicket.created_at,
        'priority': BugTicket.priority,
        'ticket_type': BugTicket.ticket_type,
        'status': BugTicket.status,
    }
    sort_col = sort_map.get(sort, BugTicket.created_at)
    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    tickets = query.all()
    members = BugProjectMember.query.filter_by(project_id=project.id).all()

    from app.models import User
    access_ids = [a.user_id for a in BugTrackerAccess.query.all()]
    admin_ids = [u.id for u in User.query.join(
        User.role).filter_by(name='admin').all()]
    allowed_ids = list(set(access_ids + admin_ids))
    users = User.query.filter(User.id.in_(
        allowed_ids), User.is_active == True).all()

    return render_template('bugtracker/project_detail.html',
                           project=project, tickets=tickets, members=members,
                           users=users, sort=sort, order=order, task_tab=task_tab)


@bugtracker_bp.route('/projects/<int:project_id>/update', methods=['POST'])
@login_required
def update_project(project_id):
    if not _has_access():
        return jsonify({'error': 'Нет доступа'}), 403

    project = BugProject.query.get_or_404(project_id)

    if 'status' in request.form:
        project.status = request.form['status']
    if 'name' in request.form and request.form['name'].strip():
        project.name = request.form['name'].strip()
    if 'description' in request.form:
        project.description = request.form['description']

    db.session.commit()
    flash('Проект обновлён', 'success')
    return redirect(url_for('bugtracker.project_detail', project_id=project_id))


@bugtracker_bp.route('/projects/<int:project_id>/add_member', methods=['POST'])
@login_required
def add_project_member(project_id):
    if not _has_access():
        return jsonify({'error': 'Нет доступа'}), 403

    project = BugProject.query.get_or_404(project_id)
    user_id = request.form.get('user_id')
    role = request.form.get('role', 'developer')

    if user_id:
        existing = BugProjectMember.query.filter_by(
            project_id=project.id, user_id=int(user_id)).first()
        if not existing:
            member = BugProjectMember(
                project_id=project.id, user_id=int(user_id), role=role)
            db.session.add(member)
            db.session.commit()
            flash('Участник добавлен', 'success')
        else:
            flash('Пользователь уже в проекте', 'warning')

    return redirect(url_for('bugtracker.project_detail', project_id=project_id))


@bugtracker_bp.route('/projects/<int:project_id>/remove_member/<int:member_id>', methods=['POST'])
@login_required
def remove_project_member(project_id, member_id):
    if not _has_access():
        return jsonify({'error': 'Нет доступа'}), 403

    member = BugProjectMember.query.get_or_404(member_id)
    db.session.delete(member)
    db.session.commit()
    flash('Участник удалён', 'success')
    return redirect(url_for('bugtracker.project_detail', project_id=project_id))


# ==================== Workflow buttons ====================

@bugtracker_bp.route('/<ticket_id>/to_testing', methods=['POST'])
@login_required
def to_testing(ticket_id):
    """В тестирование — доступно разработчику проекта когда статус 'progress'"""
    if not _has_access():
        return jsonify({'error': 'Нет доступа'}), 403

    ticket = BugTicket.query.filter_by(ticket_id=ticket_id).first_or_404()

    # Проверка: assignee ИЛИ разработчик проекта
    is_dev = False
    if ticket.project_id:
        dev_member = BugProjectMember.query.filter_by(
            project_id=ticket.project_id, user_id=current_user.id, role='developer'
        ).first()
        is_dev = dev_member is not None

    if ticket.assignee_id != current_user.id and not is_dev:
        flash('Только разработчик может отправить в тестирование', 'error')
        return redirect(url_for('bugtracker.detail', ticket_id=ticket_id))

    if ticket.status != 'progress':
        flash('Задача должна быть в статусе "В работе"', 'error')
        return redirect(url_for('bugtracker.detail', ticket_id=ticket_id))

    ticket.status = 'testing'

    # Автоматически назначить тестировщика проекта ответственным
    if ticket.project_id:
        tester = BugProjectMember.query.filter_by(
            project_id=ticket.project_id, role='tester'
        ).first()
        if tester:
            ticket.assignee_id = tester.user_id

    db.session.commit()

    # Notify tester in the project
    if ticket.project_id:
        from app.models import Notification
        testers = BugProjectMember.query.filter_by(
            project_id=ticket.project_id, role='tester'
        ).all()
        link = url_for('bugtracker.detail', ticket_id=ticket.ticket_id)
        for tester in testers:
            if tester.user_id != current_user.id:
                Notification.create(
                    tester.user_id,
                    f'{ticket.ticket_id}: отправлено в тестирование',
                    ticket.title,
                    link, 'bug', 'info'
                )

    flash('Задача отправлена в тестирование', 'success')
    return redirect(url_for('bugtracker.detail', ticket_id=ticket_id))


@bugtracker_bp.route('/<ticket_id>/return_to_dev', methods=['POST'])
@login_required
def return_to_dev(ticket_id):
    """Вернуть в разработку — доступно тестировщику когда статус 'testing'"""
    if not _has_access():
        return jsonify({'error': 'Нет доступа'}), 403

    ticket = BugTicket.query.filter_by(ticket_id=ticket_id).first_or_404()

    if ticket.status != 'testing':
        flash('Задача должна быть в статусе "Тестирование"', 'error')
        return redirect(url_for('bugtracker.detail', ticket_id=ticket_id))

    # Check if current user is a tester on the project
    is_tester = False
    if ticket.project_id:
        tester_member = BugProjectMember.query.filter_by(
            project_id=ticket.project_id, user_id=current_user.id, role='tester'
        ).first()
        is_tester = tester_member is not None

    if not is_tester:
        flash('Только тестировщик проекта может вернуть задачу в разработку', 'error')
        return redirect(url_for('bugtracker.detail', ticket_id=ticket_id))

    ticket.status = 'progress'

    # Автоматически назначить разработчика проекта ответственным
    if ticket.project_id:
        developer = BugProjectMember.query.filter_by(
            project_id=ticket.project_id, role='developer'
        ).first()
        if developer:
            ticket.assignee_id = developer.user_id

    db.session.commit()

    # Notify the developer (assignee)
    if ticket.assignee_id and ticket.assignee_id != current_user.id:
        from app.models import Notification
        link = url_for('bugtracker.detail', ticket_id=ticket.ticket_id)
        Notification.create(
            ticket.assignee_id,
            f'{ticket.ticket_id}: возвращено в разработку',
            ticket.title,
            link, 'bug', 'warning'
        )

    flash('Задача возвращена в разработку', 'success')
    return redirect(url_for('bugtracker.detail', ticket_id=ticket_id))
