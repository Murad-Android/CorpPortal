"""
Blueprint для работы с Draw.io диаграммами
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app import db, csrf
from app.models import Diagram, DiagramShare, User
from datetime import datetime

diagrams_bp = Blueprint('diagrams', __name__)


@diagrams_bp.route('/')
@login_required
def index():
    """Список диаграмм пользователя"""
    # Собственные диаграммы
    my_diagrams = Diagram.query.filter_by(
        owner_id=current_user.id).order_by(Diagram.updated_at.desc()).all()

    # Диаграммы, к которым есть доступ
    shared_with_me = db.session.query(Diagram).join(DiagramShare).filter(
        DiagramShare.user_id == current_user.id
    ).order_by(Diagram.updated_at.desc()).all()

    return render_template('diagrams/index.html',
                           my_diagrams=my_diagrams,
                           shared_with_me=shared_with_me)


@diagrams_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Создание новой диаграммы"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            title = f'Диаграмма {datetime.now().strftime("%d.%m.%Y %H:%M")}'

        diagram = Diagram(
            title=title,
            description=request.form.get('description', '').strip(),
            owner_id=current_user.id,
            xml_data='',  # Пустая диаграмма
            is_public=request.form.get('is_public') == 'on'
        )
        db.session.add(diagram)
        db.session.commit()

        return redirect(url_for('diagrams.edit', id=diagram.id))

    return render_template('diagrams/create.html')


@diagrams_bp.route('/<int:id>')
@login_required
def view(id):
    """Просмотр диаграммы"""
    diagram = Diagram.query.get_or_404(id)

    if not diagram.can_view(current_user):
        flash('У вас нет доступа к этой диаграмме', 'error')
        return redirect(url_for('diagrams.index'))

    can_edit = diagram.can_edit(current_user)

    return render_template('diagrams/view.html', diagram=diagram, can_edit=can_edit)


@diagrams_bp.route('/<int:id>/edit')
@login_required
def edit(id):
    """Редактирование диаграммы в Draw.io"""
    diagram = Diagram.query.get_or_404(id)

    if not diagram.can_edit(current_user):
        flash('У вас нет прав на редактирование этой диаграммы', 'error')
        return redirect(url_for('diagrams.view', id=id))

    return render_template('diagrams/edit.html', diagram=diagram)


@diagrams_bp.route('/<int:id>/save', methods=['POST'])
@login_required
@csrf.exempt
def save(id):
    """Сохранение диаграммы (AJAX)"""
    diagram = Diagram.query.get_or_404(id)

    if not diagram.can_edit(current_user):
        return jsonify({'success': False, 'error': 'Нет прав на редактирование'}), 403

    data = request.get_json()
    if data:
        xml = data.get('xml', '')
        # Сохраняем XML только если он не пустой
        if xml and len(xml) > 10:
            diagram.xml_data = xml
            diagram.updated_at = datetime.utcnow()
        # Превью сохраняем всегда если есть
        if data.get('preview'):
            diagram.preview_image = data.get('preview')
        db.session.commit()
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Нет данных'}), 400


@diagrams_bp.route('/<int:id>/settings', methods=['GET', 'POST'])
@login_required
def settings(id):
    """Настройки диаграммы"""
    import json
    diagram = Diagram.query.get_or_404(id)

    if diagram.owner_id != current_user.id:
        flash('Только владелец может изменять настройки', 'error')
        return redirect(url_for('diagrams.view', id=id))

    if request.method == 'POST':
        diagram.title = request.form.get('title', '').strip() or diagram.title
        diagram.description = request.form.get('description', '').strip()
        diagram.is_public = request.form.get('is_public') == 'on'
        db.session.commit()
        flash('Настройки сохранены', 'success')
        return redirect(url_for('diagrams.settings', id=id))

    # Получаем всех пользователей для выбора
    users = User.query.filter(User.id != current_user.id,
                              User.is_active == True).order_by(User.lastname).all()
    shared_users = diagram.get_shared_users()

    # Подготавливаем JSON для JavaScript
    users_json = json.dumps([{
        'id': u.id,
        'name': u.full_name,
        'position': u.position or '',
        'department': u.department or '',
        'photo': url_for('static', filename=u.photo if u.photo and u.photo != 'image/static_avatar.png' else 'image/static_avatar.png')
    } for u in users], ensure_ascii=False)

    shared_ids_json = json.dumps([s.user.id for s in shared_users])

    return render_template('diagrams/settings.html', diagram=diagram, users=users,
                           shared_users=shared_users, users_json=users_json, shared_ids_json=shared_ids_json)


@diagrams_bp.route('/<int:id>/share', methods=['POST'])
@login_required
def share(id):
    """Добавление доступа к диаграмме"""
    diagram = Diagram.query.get_or_404(id)

    if diagram.owner_id != current_user.id:
        return jsonify({'success': False, 'error': 'Только владелец может управлять доступом'}), 403

    data = request.get_json()
    user_id = data.get('user_id')
    can_edit = data.get('can_edit', False)

    if not user_id:
        return jsonify({'success': False, 'error': 'Не указан пользователь'}), 400

    # Проверяем, что пользователь существует
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404

    # Проверяем, нет ли уже доступа
    existing = DiagramShare.query.filter_by(
        diagram_id=id, user_id=user_id).first()
    if existing:
        existing.can_edit = can_edit
    else:
        share = DiagramShare(diagram_id=id, user_id=user_id, can_edit=can_edit)
        db.session.add(share)

    db.session.commit()

    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'name': user.full_name,
            'can_edit': can_edit
        }
    })


@diagrams_bp.route('/<int:id>/unshare', methods=['POST'])
@login_required
def unshare(id):
    """Удаление доступа к диаграмме"""
    diagram = Diagram.query.get_or_404(id)

    if diagram.owner_id != current_user.id:
        return jsonify({'success': False, 'error': 'Только владелец может управлять доступом'}), 403

    data = request.get_json()
    user_id = data.get('user_id')

    share = DiagramShare.query.filter_by(
        diagram_id=id, user_id=user_id).first()
    if share:
        db.session.delete(share)
        db.session.commit()

    return jsonify({'success': True})


@diagrams_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Удаление диаграммы"""
    diagram = Diagram.query.get_or_404(id)

    if diagram.owner_id != current_user.id:
        flash('Только владелец может удалить диаграмму', 'error')
        return redirect(url_for('diagrams.index'))

    db.session.delete(diagram)
    db.session.commit()
    flash('Диаграмма удалена', 'success')

    return redirect(url_for('diagrams.index'))


@diagrams_bp.route('/<int:id>/duplicate', methods=['POST'])
@login_required
def duplicate(id):
    """Дублирование диаграммы"""
    diagram = Diagram.query.get_or_404(id)

    if not diagram.can_view(current_user):
        flash('У вас нет доступа к этой диаграмме', 'error')
        return redirect(url_for('diagrams.index'))

    new_diagram = Diagram(
        title=f'{diagram.title} (копия)',
        description=diagram.description,
        xml_data=diagram.xml_data,
        preview_image=diagram.preview_image,
        owner_id=current_user.id,
        is_public=False
    )
    db.session.add(new_diagram)
    db.session.commit()

    flash('Диаграмма скопирована', 'success')
    return redirect(url_for('diagrams.edit', id=new_diagram.id))
