"""
Blueprint мессенджера с групповыми чатами, каналами и редактированием
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import User, Chat, Message, Notification, ChatGroup, ChatGroupMember
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid
import html
import shutil
import secrets

messenger_bp = Blueprint('messenger', __name__)

UPLOAD_FOLDER = 'app/static/messenger'
STICKER_FOLDER = 'app/static/messenger/stickers'
VOICE_FOLDER = 'app/static/messenger/voice'
GROUP_AVATAR_FOLDER = 'app/static/messenger/avatars'
MAX_MESSAGE_LENGTH = 5000

for folder in [UPLOAD_FOLDER, STICKER_FOLDER, VOICE_FOLDER, GROUP_AVATAR_FOLDER,
               os.path.join(STICKER_FOLDER, 'common')]:
    os.makedirs(folder, exist_ok=True)


def sanitize_message(content):
    if not content:
        return ''
    return html.escape(content.strip())[:MAX_MESSAGE_LENGTH]


def get_user_sticker_folder(user_id):
    folder = os.path.join(STICKER_FOLDER, str(user_id))
    os.makedirs(folder, exist_ok=True)
    return folder


def get_photo_path(photo):
    """Возвращает путь к фото пользователя для API"""
    if photo and photo != 'image/static_avatar.png':
        return f'staff_photo/{photo}'
    return 'image/static_avatar.png'


@messenger_bp.route('/')
@login_required
def index():
    return render_template('messenger/index.html')


# === Личные чаты ===

@messenger_bp.route('/chats')
@login_required
def get_chats():
    """Получить список всех чатов (личных и групповых)"""
    favorites_chat = Chat.get_favorites(current_user.id)

    # Личные чаты
    chats_1 = Chat.query.filter_by(user1_id=current_user.id).all()
    chats_2 = Chat.query.filter_by(user2_id=current_user.id).all()
    all_chats = list(set(chats_1 + chats_2))

    chat_data = []
    favorites_data = None

    for chat in all_chats:
        if not chat.is_visible_for_user(current_user.id):
            continue

        other_user = chat.get_other_user(current_user.id)
        last_msg = chat.get_last_message(current_user.id)
        unread = chat.get_unread_count(current_user.id)

        last_msg_text = ''
        if last_msg:
            if last_msg.is_deleted:
                last_msg_text = 'Сообщение удалено'
            elif last_msg.is_sticker:
                last_msg_text = '🎨 Стикер'
            elif last_msg.message_type == 'voice':
                last_msg_text = '🎤 Голосовое'
            elif last_msg.file_path and last_msg.message_type == 'file':
                last_msg_text = '📎 Файл'
            elif last_msg.forwarded_from_id:
                last_msg_text = '↪️ ' + \
                    (last_msg.content[:40]
                     if last_msg.content else 'Пересланное')
            elif last_msg.content:
                last_msg_text = last_msg.content[:50]

        item = {
            'id': chat.id,
            'type': 'favorites' if chat.is_favorites else 'private',
            'user_id': other_user.id,
            'name': '⭐ Избранное' if chat.is_favorites else other_user.short_name,
            'full_name': 'Избранное' if chat.is_favorites else other_user.full_name,
            'photo': get_photo_path(other_user.photo),
            'subtitle': '' if chat.is_favorites else (other_user.position or ''),
            'is_favorites': chat.is_favorites,
            'last_message': last_msg_text,
            'last_message_time': last_msg.created_at.strftime('%H:%M') if last_msg else '',
            'unread_count': unread,
            'updated_at': chat.updated_at.isoformat() if chat.updated_at else ''
        }

        if chat.is_favorites:
            favorites_data = item
        else:
            chat_data.append(item)

    # Групповые чаты и каналы
    memberships = ChatGroupMember.query.filter_by(
        user_id=current_user.id).all()
    for membership in memberships:
        group = membership.group
        group_dict = group.to_dict(current_user.id)
        chat_data.append({
            'id': group.id,
            'type': group.type,  # 'group' или 'channel'
            'name': group.name,
            'full_name': group.name,
            'photo': group.avatar or 'group_default.png',
            'subtitle': f'{group_dict["member_count"]} участников',
            'is_favorites': False,
            'last_message': group_dict['last_message'],
            'last_message_time': group_dict['last_message_time'],
            'unread_count': group_dict['unread_count'],
            'updated_at': group_dict['updated_at'],
            'my_role': group_dict['my_role']
        })

    chat_data.sort(key=lambda x: x['updated_at'], reverse=True)
    if favorites_data:
        chat_data.insert(0, favorites_data)

    return jsonify({'chats': chat_data})


@messenger_bp.route('/chat/<int:user_id>')
@login_required
def chat(user_id):
    """Получить или создать личный чат"""
    other_user = User.query.get_or_404(user_id)
    chat = Chat.get_or_create(current_user.id, user_id)

    if chat.user1_id == current_user.id:
        chat.is_deleted_for_user1 = False
    else:
        chat.is_deleted_for_user2 = False
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'chat_id': chat.id,
            'type': 'favorites' if chat.is_favorites else 'private',
            'user_id': other_user.id,
            'name': '⭐ Избранное' if chat.is_favorites else other_user.short_name,
            'full_name': 'Избранное' if chat.is_favorites else other_user.full_name,
            'photo': get_photo_path(other_user.photo),
            'subtitle': '' if chat.is_favorites else (other_user.position or ''),
            'is_favorites': chat.is_favorites
        })

    return redirect(url_for('messenger.index') + f'?chat={chat.id}')


@messenger_bp.route('/chat/<int:chat_id>/messages')
@login_required
def get_messages(chat_id):
    """Получить сообщения личного чата"""
    chat = Chat.query.get_or_404(chat_id)

    if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    last_id = request.args.get('last_id', 0, type=int)

    if chat.user1_id == current_user.id:
        deleted_filter = Message.is_deleted_for_user1 == False
    else:
        deleted_filter = Message.is_deleted_for_user2 == False

    query = chat.messages.filter(Message.is_deleted == False, deleted_filter)

    if last_id > 0:
        messages = query.filter(Message.id > last_id).order_by(
            Message.created_at.asc()).all()
    else:
        messages = query.order_by(Message.created_at.asc()).limit(100).all()

    # Отмечаем как прочитанные (используем прямой запрос, чтобы избежать конфликта с order_by)
    Message.query.filter(
        Message.chat_id == chat_id,
        Message.sender_id != current_user.id,
        Message.is_read == False
    ).update({'is_read': True}, synchronize_session=False)
    db.session.commit()

    return jsonify({
        'messages': [msg.to_dict(current_user.id, chat) for msg in messages],
        'last_id': messages[-1].id if messages else last_id
    })


@messenger_bp.route('/chat/<int:chat_id>/send', methods=['POST'])
@login_required
def send_message(chat_id):
    """Отправить сообщение в личный чат"""
    chat = Chat.query.get_or_404(chat_id)

    if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    data = request.get_json()
    content = sanitize_message(data.get('content', ''))
    reply_to_id = data.get('reply_to_id')

    if not content:
        return jsonify({'error': 'Сообщение пустое'}), 400

    message = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        content=content,
        message_type='text',
        reply_to_id=reply_to_id
    )
    db.session.add(message)
    chat.updated_at = datetime.utcnow()
    db.session.commit()

    if not chat.is_favorites:
        other_user_id = chat.user2_id if chat.user1_id == current_user.id else chat.user1_id
        Notification.create(other_user_id, f'Сообщение от {current_user.short_name}',
                            content[:100], f'/messenger?chat={chat_id}', 'comment', 'info')

    return jsonify({'message': message.to_dict(current_user.id, chat)})


# === Редактирование сообщений ===

@messenger_bp.route('/message/<int:message_id>/edit', methods=['POST'])
@login_required
def edit_message(message_id):
    """Редактировать сообщение"""
    message = Message.query.get_or_404(message_id)

    if message.sender_id != current_user.id:
        return jsonify({'error': 'Можно редактировать только свои сообщения'}), 403

    if message.is_deleted:
        return jsonify({'error': 'Сообщение удалено'}), 400

    if message.message_type != 'text':
        return jsonify({'error': 'Можно редактировать только текстовые сообщения'}), 400

    data = request.get_json()
    content = sanitize_message(data.get('content', ''))

    if not content:
        return jsonify({'error': 'Сообщение пустое'}), 400

    message.content = content
    message.is_edited = True
    message.edited_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'message': message.to_dict(current_user.id, message.chat)})


# === Групповые чаты и каналы ===

@messenger_bp.route('/groups/create', methods=['POST'])
@login_required
def create_group():
    """Создать групповой чат или канал"""
    data = request.get_json()
    name = data.get('name', '').strip()
    group_type = data.get('type', 'group')  # 'group' или 'channel'
    description = data.get('description', '').strip()

    if not name:
        return jsonify({'error': 'Укажите название'}), 400

    if group_type not in ('group', 'channel'):
        group_type = 'group'

    group = ChatGroup(
        name=name,
        description=description,
        type=group_type,
        owner_id=current_user.id,
        only_admins_can_post=(group_type == 'channel')
    )
    db.session.add(group)
    db.session.flush()

    # Добавляем создателя как владельца
    owner_member = ChatGroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role='owner',
        can_edit_info=True,
        can_delete_messages=True,
        can_add_members=True,
        can_remove_members=True,
        can_manage_admins=True,
        can_pin_messages=True
    )
    db.session.add(owner_member)
    db.session.commit()

    return jsonify({'success': True, 'group': group.to_dict(current_user.id)})


@messenger_bp.route('/group/<int:group_id>')
@login_required
def get_group(group_id):
    """Получить информацию о группе"""
    group = ChatGroup.query.get_or_404(group_id)

    if not group.is_member(current_user.id):
        return jsonify({'error': 'Вы не участник'}), 403

    return jsonify({'group': group.to_dict(current_user.id)})


@messenger_bp.route('/group/<int:group_id>/messages')
@login_required
def get_group_messages(group_id):
    """Получить сообщения группы"""
    group = ChatGroup.query.get_or_404(group_id)
    member = group.get_member(current_user.id)

    if not member:
        return jsonify({'error': 'Вы не участник'}), 403

    last_id = request.args.get('last_id', 0, type=int)

    query = group.messages.filter(Message.is_deleted == False)

    if last_id > 0:
        messages = query.filter(Message.id > last_id).order_by(
            Message.created_at.asc()).all()
    else:
        messages = query.order_by(Message.created_at.asc()).limit(100).all()

    # Обновляем время последнего прочтения
    member.last_read_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'messages': [msg.to_dict(current_user.id) for msg in messages],
        'last_id': messages[-1].id if messages else last_id
    })


@messenger_bp.route('/group/<int:group_id>/send', methods=['POST'])
@login_required
def send_group_message(group_id):
    """Отправить сообщение в группу"""
    group = ChatGroup.query.get_or_404(group_id)

    if not group.can_post(current_user.id):
        return jsonify({'error': 'Нет прав на отправку сообщений'}), 403

    data = request.get_json()
    content = sanitize_message(data.get('content', ''))
    reply_to_id = data.get('reply_to_id')

    if not content:
        return jsonify({'error': 'Сообщение пустое'}), 400

    message = Message(
        group_id=group_id,
        sender_id=current_user.id,
        content=content,
        message_type='text',
        reply_to_id=reply_to_id
    )
    db.session.add(message)
    group.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': message.to_dict(current_user.id)})


@messenger_bp.route('/group/<int:group_id>/edit', methods=['POST'])
@login_required
def edit_group(group_id):
    """Редактировать группу"""
    group = ChatGroup.query.get_or_404(group_id)
    member = group.get_member(current_user.id)

    if not member or (member.role != 'owner' and not member.can_edit_info):
        return jsonify({'error': 'Нет прав'}), 403

    data = request.get_json()

    if 'name' in data:
        group.name = data['name'].strip()[:255]
    if 'description' in data:
        group.description = data['description'].strip()
    if 'only_admins_can_post' in data and member.role == 'owner':
        group.only_admins_can_post = bool(data['only_admins_can_post'])
    if 'is_public' in data and member.role == 'owner':
        group.is_public = bool(data['is_public'])

    db.session.commit()
    return jsonify({'success': True, 'group': group.to_dict(current_user.id)})


# === Участники группы ===

@messenger_bp.route('/group/<int:group_id>/members')
@login_required
def get_group_members(group_id):
    """Получить список участников"""
    group = ChatGroup.query.get_or_404(group_id)

    if not group.is_member(current_user.id):
        return jsonify({'error': 'Вы не участник'}), 403

    members = group.members.all()
    return jsonify({
        'members': [m.to_dict() for m in members],
        'can_manage': group.can_manage_members(current_user.id)
    })


@messenger_bp.route('/group/<int:group_id>/members/add', methods=['POST'])
@login_required
def add_group_member(group_id):
    """Добавить участника"""
    group = ChatGroup.query.get_or_404(group_id)
    member = group.get_member(current_user.id)

    if not member or (member.role not in ('owner', 'admin') and not member.can_add_members):
        return jsonify({'error': 'Нет прав'}), 403

    data = request.get_json()
    user_ids = data.get('user_ids', [])

    added = []
    for user_id in user_ids:
        if group.is_member(user_id):
            continue
        user = User.query.get(user_id)
        if not user:
            continue

        new_member = ChatGroupMember(
            group_id=group_id, user_id=user_id, role='member')
        db.session.add(new_member)
        added.append(user.short_name)

        # Уведомление
        type_name = 'канал' if group.type == 'channel' else 'чат'
        Notification.create(user_id, f'Вас добавили в {type_name}',
                            f'Вы добавлены в "{group.name}"', f'/messenger?group={group_id}', 'users', 'info')

    db.session.commit()
    return jsonify({'success': True, 'added': added})


@messenger_bp.route('/group/<int:group_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_group_member(group_id, user_id):
    """Удалить участника"""
    group = ChatGroup.query.get_or_404(group_id)
    my_member = group.get_member(current_user.id)
    target_member = group.get_member(user_id)

    if not target_member:
        return jsonify({'error': 'Участник не найден'}), 404

    # Владельца нельзя удалить
    if target_member.role == 'owner':
        return jsonify({'error': 'Нельзя удалить владельца'}), 403

    # Проверка прав
    can_remove = False
    if my_member.role == 'owner':
        can_remove = True
    elif my_member.role == 'admin' and my_member.can_remove_members:
        # Админ не может удалить другого админа
        can_remove = target_member.role == 'member'
    elif user_id == current_user.id:
        # Можно выйти самому
        can_remove = True

    if not can_remove:
        return jsonify({'error': 'Нет прав'}), 403

    db.session.delete(target_member)
    db.session.commit()

    return jsonify({'success': True})


@messenger_bp.route('/group/<int:group_id>/members/<int:user_id>/role', methods=['POST'])
@login_required
def change_member_role(group_id, user_id):
    """Изменить роль участника"""
    group = ChatGroup.query.get_or_404(group_id)
    my_member = group.get_member(current_user.id)
    target_member = group.get_member(user_id)

    if not target_member:
        return jsonify({'error': 'Участник не найден'}), 404

    # Только владелец или админ с правами может менять роли
    can_manage = False
    if my_member.role == 'owner':
        can_manage = True
    elif my_member.role == 'admin' and my_member.can_manage_admins:
        # Админ может только повышать обычных
        can_manage = target_member.role == 'member'

    if not can_manage:
        return jsonify({'error': 'Нет прав'}), 403

    data = request.get_json()
    new_role = data.get('role', 'member')

    if new_role == 'owner':
        # Передача владения
        if my_member.role != 'owner':
            return jsonify({'error': 'Только владелец может передать владение'}), 403
        my_member.role = 'admin'
        target_member.role = 'owner'
        group.owner_id = user_id
    elif new_role == 'admin':
        target_member.role = 'admin'
        # Права по умолчанию для админа
        target_member.can_add_members = data.get('can_add_members', True)
        target_member.can_remove_members = data.get(
            'can_remove_members', False)
        target_member.can_edit_info = data.get('can_edit_info', False)
        target_member.can_delete_messages = data.get(
            'can_delete_messages', False)
        target_member.can_manage_admins = data.get('can_manage_admins', False)
        target_member.can_pin_messages = data.get('can_pin_messages', False)
    else:
        target_member.role = 'member'
        # Сбрасываем права
        target_member.can_add_members = False
        target_member.can_remove_members = False
        target_member.can_edit_info = False
        target_member.can_delete_messages = False
        target_member.can_manage_admins = False
        target_member.can_pin_messages = False

    db.session.commit()
    return jsonify({'success': True, 'member': target_member.to_dict()})


@messenger_bp.route('/group/<int:group_id>/members/<int:user_id>/permissions', methods=['POST'])
@login_required
def update_member_permissions(group_id, user_id):
    """Обновить права админа"""
    group = ChatGroup.query.get_or_404(group_id)
    my_member = group.get_member(current_user.id)
    target_member = group.get_member(user_id)

    if not target_member or target_member.role != 'admin':
        return jsonify({'error': 'Участник не админ'}), 400

    if my_member.role != 'owner':
        return jsonify({'error': 'Только владелец может менять права админов'}), 403

    data = request.get_json()
    target_member.can_add_members = data.get(
        'can_add_members', target_member.can_add_members)
    target_member.can_remove_members = data.get(
        'can_remove_members', target_member.can_remove_members)
    target_member.can_edit_info = data.get(
        'can_edit_info', target_member.can_edit_info)
    target_member.can_delete_messages = data.get(
        'can_delete_messages', target_member.can_delete_messages)
    target_member.can_manage_admins = data.get(
        'can_manage_admins', target_member.can_manage_admins)
    target_member.can_pin_messages = data.get(
        'can_pin_messages', target_member.can_pin_messages)

    db.session.commit()
    return jsonify({'success': True, 'member': target_member.to_dict()})


# === Приглашения ===

@messenger_bp.route('/group/<int:group_id>/invite-link')
@login_required
def get_invite_link(group_id):
    """Получить ссылку-приглашение"""
    group = ChatGroup.query.get_or_404(group_id)

    if not group.is_admin(current_user.id):
        return jsonify({'error': 'Нет прав'}), 403

    return jsonify({
        'invite_link': group.invite_link,
        'enabled': group.invite_link_enabled,
        'full_url': f'/messenger/join/{group.invite_link}'
    })


@messenger_bp.route('/group/<int:group_id>/invite-link/regenerate', methods=['POST'])
@login_required
def regenerate_invite_link(group_id):
    """Сгенерировать новую ссылку"""
    group = ChatGroup.query.get_or_404(group_id)

    if not group.is_admin(current_user.id):
        return jsonify({'error': 'Нет прав'}), 403

    new_link = group.regenerate_invite_link()
    return jsonify({'invite_link': new_link, 'full_url': f'/messenger/join/{new_link}'})


@messenger_bp.route('/group/<int:group_id>/invite-link/toggle', methods=['POST'])
@login_required
def toggle_invite_link(group_id):
    """Включить/выключить ссылку"""
    group = ChatGroup.query.get_or_404(group_id)

    if not group.is_admin(current_user.id):
        return jsonify({'error': 'Нет прав'}), 403

    group.invite_link_enabled = not group.invite_link_enabled
    db.session.commit()
    return jsonify({'enabled': group.invite_link_enabled})


@messenger_bp.route('/join/<invite_link>')
@login_required
def join_by_link(invite_link):
    """Присоединиться по ссылке"""
    group = ChatGroup.query.filter_by(invite_link=invite_link).first()

    if not group:
        return jsonify({'error': 'Ссылка недействительна'}), 404

    if not group.invite_link_enabled:
        return jsonify({'error': 'Ссылка отключена'}), 403

    if group.is_member(current_user.id):
        return redirect(url_for('messenger.index') + f'?group={group.id}')

    member = ChatGroupMember(
        group_id=group.id, user_id=current_user.id, role='member')
    db.session.add(member)
    db.session.commit()

    return redirect(url_for('messenger.index') + f'?group={group.id}')


# === Остальные функции (файлы, голосовые, стикеры, удаление) ===

@messenger_bp.route('/chat/<int:chat_id>/forward', methods=['POST'])
@login_required
def forward_message(chat_id):
    """Переслать сообщение в личный чат"""
    chat = Chat.query.get_or_404(chat_id)
    if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    data = request.get_json()
    original = Message.query.get_or_404(data.get('message_id'))

    message = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        content=original.content,
        message_type=original.message_type,
        file_path=original.file_path,
        file_name=original.file_name,
        is_sticker=original.is_sticker,
        duration=original.duration,
        forwarded_from_id=original.sender_id,
        forwarded_message_id=original.id
    )
    db.session.add(message)
    chat.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': message.to_dict(current_user.id, chat)})


@messenger_bp.route('/chat/<int:chat_id>/voice', methods=['POST'])
@login_required
def send_voice(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    if 'audio' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    audio = request.files['audio']
    duration = request.form.get('duration', 0, type=int)
    filename = f'voice_{current_user.id}_{uuid.uuid4().hex}.webm'
    audio.save(os.path.join(VOICE_FOLDER, filename))

    message = Message(chat_id=chat_id, sender_id=current_user.id, message_type='voice',
                      file_path=f'messenger/voice/{filename}', duration=duration)
    db.session.add(message)
    chat.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': message.to_dict(current_user.id, chat)})


@messenger_bp.route('/chat/<int:chat_id>/file', methods=['POST'])
@login_required
def send_file(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    file = request.files['file']
    caption = request.form.get('caption', '').strip()
    original_name = secure_filename(file.filename)
    filename = f'{uuid.uuid4().hex}_{original_name}'
    files_folder = os.path.join(UPLOAD_FOLDER, 'files')
    os.makedirs(files_folder, exist_ok=True)
    file.save(os.path.join(files_folder, filename))

    message = Message(chat_id=chat_id, sender_id=current_user.id, message_type='file',
                      file_path=f'messenger/files/{filename}', file_name=original_name,
                      content=caption if caption else None)
    db.session.add(message)
    chat.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': message.to_dict(current_user.id, chat)})


@messenger_bp.route('/chat/<int:chat_id>/sticker', methods=['POST'])
@login_required
def send_sticker(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    data = request.get_json()
    sticker_path = data.get('sticker_path', '')
    if not sticker_path:
        return jsonify({'error': 'Стикер не указан'}), 400

    message = Message(chat_id=chat_id, sender_id=current_user.id, message_type='sticker',
                      file_path=sticker_path, is_sticker=True)
    db.session.add(message)
    chat.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': message.to_dict(current_user.id, chat)})


# === Удаление сообщений ===

@messenger_bp.route('/message/<int:message_id>/delete', methods=['POST'])
@login_required
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)

    # Для групповых сообщений
    if message.group_id:
        group = ChatGroup.query.get(message.group_id)
        member = group.get_member(current_user.id) if group else None
        if not member:
            return jsonify({'error': 'Доступ запрещен'}), 403
        # В группах удаление только у себя не имеет смысла - удаляем полностью если свое
        if message.sender_id == current_user.id:
            message.is_deleted = True
            message.content = None
        elif member.can_delete_messages or member.role == 'owner':
            message.is_deleted = True
            message.content = None
        else:
            return jsonify({'error': 'Нет прав'}), 403
    else:
        # Личный чат
        chat = message.chat
        if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
            return jsonify({'error': 'Доступ запрещен'}), 403
        if chat.user1_id == current_user.id:
            message.is_deleted_for_user1 = True
        else:
            message.is_deleted_for_user2 = True

    db.session.commit()
    return jsonify({'success': True})


@messenger_bp.route('/message/<int:message_id>/delete-all', methods=['POST'])
@login_required
def delete_message_for_all(message_id):
    message = Message.query.get_or_404(message_id)

    if message.sender_id != current_user.id:
        return jsonify({'error': 'Можно удалить только свои сообщения'}), 403

    message.is_deleted = True
    message.content = None
    db.session.commit()

    return jsonify({'success': True})


# === Избранное ===

@messenger_bp.route('/message/<int:message_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(message_id):
    message = Message.query.get_or_404(message_id)
    chat = message.chat

    if not chat or (chat.user1_id != current_user.id and chat.user2_id != current_user.id):
        return jsonify({'error': 'Доступ запрещен'}), 403

    if chat.user1_id == current_user.id:
        message.is_favorite_user1 = not message.is_favorite_user1
        is_fav = message.is_favorite_user1
    else:
        message.is_favorite_user2 = not message.is_favorite_user2
        is_fav = message.is_favorite_user2

    if is_fav:
        fav_chat = Chat.get_favorites(current_user.id)
        fav_message = Message(
            chat_id=fav_chat.id,
            sender_id=current_user.id,
            content=message.content,
            message_type=message.message_type,
            file_path=message.file_path,
            file_name=message.file_name,
            is_sticker=message.is_sticker,
            duration=message.duration,
            forwarded_from_id=message.sender_id,
            forwarded_message_id=message.id
        )
        db.session.add(fav_message)
        fav_chat.updated_at = datetime.utcnow()

    db.session.commit()
    return jsonify({'success': True, 'is_favorite': is_fav})


# === Удаление чатов ===

@messenger_bp.route('/chat/<int:chat_id>/delete', methods=['POST'])
@login_required
def delete_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)

    if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    if chat.is_favorites:
        return jsonify({'error': 'Нельзя удалить Избранное'}), 400

    if chat.user1_id == current_user.id:
        chat.is_deleted_for_user1 = True
        chat.messages.update({Message.is_deleted_for_user1: True})
    else:
        chat.is_deleted_for_user2 = True
        chat.messages.update({Message.is_deleted_for_user2: True})

    db.session.commit()
    return jsonify({'success': True})


@messenger_bp.route('/chat/<int:chat_id>/delete-all', methods=['POST'])
@login_required
def delete_chat_for_all(chat_id):
    chat = Chat.query.get_or_404(chat_id)

    if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403

    if chat.is_favorites:
        return jsonify({'error': 'Нельзя удалить Избранное'}), 400

    chat.messages.update({Message.is_deleted: True, Message.content: None})
    chat.is_deleted_for_user1 = True
    chat.is_deleted_for_user2 = True

    db.session.commit()
    return jsonify({'success': True})


@messenger_bp.route('/group/<int:group_id>/leave', methods=['POST'])
@login_required
def leave_group(group_id):
    """Покинуть группу"""
    group = ChatGroup.query.get_or_404(group_id)
    member = group.get_member(current_user.id)

    if not member:
        return jsonify({'error': 'Вы не участник'}), 400

    if member.role == 'owner':
        # Владелец должен передать права или удалить группу
        return jsonify({'error': 'Владелец не может покинуть группу. Передайте права или удалите группу.'}), 400

    db.session.delete(member)
    db.session.commit()
    return jsonify({'success': True})


@messenger_bp.route('/group/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_group(group_id):
    """Удалить группу (только владелец)"""
    group = ChatGroup.query.get_or_404(group_id)

    if group.owner_id != current_user.id:
        return jsonify({'error': 'Только владелец может удалить группу'}), 403

    db.session.delete(group)
    db.session.commit()
    return jsonify({'success': True})


# === Поиск и прочее ===

@messenger_bp.route('/users/search')
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'users': []})

    users = User.query.filter(
        User.id != current_user.id,
        User.is_active == True,
        db.or_(
            User.firstname.ilike(f'%{query}%'),
            User.lastname.ilike(f'%{query}%'),
            User.username.ilike(f'%{query}%')
        )
    ).limit(10).all()

    return jsonify({
        'users': [{
            'id': u.id,
            'name': u.short_name,
            'full_name': u.full_name,
            'photo': get_photo_path(u.photo),
            'position': u.position or ''
        } for u in users]
    })


@messenger_bp.route('/unread-count')
@login_required
def unread_count():
    # Личные чаты
    chats_1 = Chat.query.filter_by(user1_id=current_user.id).all()
    chats_2 = Chat.query.filter_by(user2_id=current_user.id).all()
    all_chats = list(set(chats_1 + chats_2))
    total = sum(chat.get_unread_count(current_user.id)
                for chat in all_chats if chat.is_visible_for_user(current_user.id))

    # Групповые
    memberships = ChatGroupMember.query.filter_by(
        user_id=current_user.id).all()
    for m in memberships:
        total += m.group.get_unread_count(current_user.id)

    return jsonify({'count': total})


# === Стикеры ===

@messenger_bp.route('/stickers')
@login_required
def get_stickers():
    user_folder = get_user_sticker_folder(current_user.id)
    common_folder = os.path.join(STICKER_FOLDER, 'common')

    user_stickers = []
    if os.path.exists(user_folder):
        for f in os.listdir(user_folder):
            if os.path.isfile(os.path.join(user_folder, f)):
                user_stickers.append(
                    {'path': f'messenger/stickers/{current_user.id}/{f}', 'filename': f})

    common_stickers = []
    if os.path.exists(common_folder):
        for f in os.listdir(common_folder):
            if os.path.isfile(os.path.join(common_folder, f)):
                common_stickers.append(
                    {'path': f'messenger/stickers/common/{f}', 'filename': f})

    return jsonify({'user_stickers': user_stickers, 'common_stickers': common_stickers})


@messenger_bp.route('/stickers/upload', methods=['POST'])
@login_required
def upload_sticker():
    if 'sticker' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['sticker']
    ext = file.filename.rsplit('.', 1)[1].lower(
    ) if '.' in file.filename else 'png'
    if ext not in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
        return jsonify({'error': 'Недопустимый формат'}), 400
    filename = f'{uuid.uuid4().hex}.{ext}'
    file.save(os.path.join(get_user_sticker_folder(current_user.id), filename))
    return jsonify({'success': True, 'sticker_path': f'messenger/stickers/{current_user.id}/{filename}'})


@messenger_bp.route('/stickers/copy', methods=['POST'])
@login_required
def copy_sticker():
    data = request.get_json()
    sticker_path = data.get('sticker_path', '')
    if not sticker_path or 'messenger/stickers/' not in sticker_path:
        return jsonify({'error': 'Неверный путь'}), 400
    source_path = os.path.join('app/static', sticker_path)
    if not os.path.exists(source_path):
        return jsonify({'error': 'Стикер не найден'}), 404
    ext = sticker_path.rsplit('.', 1)[1] if '.' in sticker_path else 'png'
    filename = f'{uuid.uuid4().hex}.{ext}'
    shutil.copy2(source_path, os.path.join(
        get_user_sticker_folder(current_user.id), filename))
    return jsonify({'success': True, 'sticker_path': f'messenger/stickers/{current_user.id}/{filename}'})


# === Групповые файлы/голосовые/стикеры ===

@messenger_bp.route('/group/<int:group_id>/voice', methods=['POST'])
@login_required
def send_group_voice(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if not group.can_post(current_user.id):
        return jsonify({'error': 'Нет прав'}), 403

    if 'audio' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    audio = request.files['audio']
    duration = request.form.get('duration', 0, type=int)
    filename = f'voice_{current_user.id}_{uuid.uuid4().hex}.webm'
    audio.save(os.path.join(VOICE_FOLDER, filename))

    message = Message(group_id=group_id, sender_id=current_user.id, message_type='voice',
                      file_path=f'messenger/voice/{filename}', duration=duration)
    db.session.add(message)
    group.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': message.to_dict(current_user.id)})


@messenger_bp.route('/group/<int:group_id>/file', methods=['POST'])
@login_required
def send_group_file(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if not group.can_post(current_user.id):
        return jsonify({'error': 'Нет прав'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    file = request.files['file']
    caption = request.form.get('caption', '').strip()
    original_name = secure_filename(file.filename)
    filename = f'{uuid.uuid4().hex}_{original_name}'
    files_folder = os.path.join(UPLOAD_FOLDER, 'files')
    os.makedirs(files_folder, exist_ok=True)
    file.save(os.path.join(files_folder, filename))

    message = Message(group_id=group_id, sender_id=current_user.id, message_type='file',
                      file_path=f'messenger/files/{filename}', file_name=original_name,
                      content=caption if caption else None)
    db.session.add(message)
    group.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': message.to_dict(current_user.id)})


@messenger_bp.route('/group/<int:group_id>/sticker', methods=['POST'])
@login_required
def send_group_sticker(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if not group.can_post(current_user.id):
        return jsonify({'error': 'Нет прав'}), 403

    data = request.get_json()
    sticker_path = data.get('sticker_path', '')
    if not sticker_path:
        return jsonify({'error': 'Стикер не указан'}), 400

    message = Message(group_id=group_id, sender_id=current_user.id, message_type='sticker',
                      file_path=sticker_path, is_sticker=True)
    db.session.add(message)
    group.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': message.to_dict(current_user.id)})


EMOJI_LIST = ['😊', '😂', '😍', '🥰', '😘', '😎', '🤔', '😢', '😭', '😡', '👍', '👎', '👏', '🙌', '🤝', '💪', '✌️', '🤞', '👀',
              '🙈', '❤️', '💔', '💕', '💖', '💗', '💙', '💚', '💛', '🧡', '💜', '🔥', '⭐', '✨', '🎉', '🎊', '🎁', '🏆', '🥇', '🎯', '💯']


@messenger_bp.route('/emojis')
@login_required
def get_emojis():
    return jsonify({'emojis': EMOJI_LIST})
