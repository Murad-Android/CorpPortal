import logging
from flask import Flask, request, jsonify, session, send_from_directory, render_template
from flask_socketio import SocketIO, emit
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid
from database import (init_db, register_user, login_user, update_last_active, get_user_status, search_users,
                      get_chats, save_message, get_messages, mark_messages_as_read, create_group, add_group_member,
                      remove_group_member, get_group_members, set_admin_only_messages, appoint_admin, revoke_admin,
                      delete_message, is_user_admin_or_creator, update_user_profile, get_user_profile)
from flask_cors import CORS

# Configure logging
logging.basicConfig(filename='app.log', level=logging.DEBUG)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['AVATAR_FOLDER'] = os.path.join('Uploads', 'avatars')
app.config['STICKER_FOLDER'] = 'stickers'
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

# Initialize database
init_db()

# Ensure upload, avatar, and sticker directories exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['AVATAR_FOLDER']):
    os.makedirs(app.config['AVATAR_FOLDER'])
if not os.path.exists(app.config['STICKER_FOLDER']):
    os.makedirs(app.config['STICKER_FOLDER'])
if not os.path.exists(os.path.join(app.config['STICKER_FOLDER'], 'common')):
    os.makedirs(os.path.join(app.config['STICKER_FOLDER'], 'common'))


def update_user_activity(username):
    if username:
        update_last_active(username)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/chat.html')
def chat():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    return render_template('chat.html', username=session['username'])


@app.route('/chat_mobile.html')
def chat_mobile():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    return render_template('/chat_mobile.html', username=session['username'])


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if register_user(username, password):
        session['username'] = username
        update_user_activity(username)
        # Create user-specific sticker folder
        user_sticker_path = os.path.join(
            app.config['STICKER_FOLDER'], username)
        if not os.path.exists(user_sticker_path):
            os.makedirs(user_sticker_path)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Username already exists'}), 400


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if login_user(username, password):
        session['username'] = username
        update_user_activity(username)
        # Create user-specific sticker folder if it doesn't exist
        user_sticker_path = os.path.join(
            app.config['STICKER_FOLDER'], username)
        if not os.path.exists(user_sticker_path):
            os.makedirs(user_sticker_path)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return jsonify({'success': True})


@app.route('/search')
def search():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    query = request.args.get('query', '')
    update_user_activity(session['username'])
    users = search_users(query, session['username'])
    return jsonify(users)


@app.route('/chats')
def get_chats_route():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    update_user_activity(session['username'])
    chats = get_chats(session['username'])
    return jsonify(chats)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    filename = secure_filename(str(uuid.uuid4()) + '_' + file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    update_user_activity(session['username'])
    return jsonify({'success': True, 'filePath': f"/{app.config['UPLOAD_FOLDER']}/{filename}"})


@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'username' not in session:
        logging.error("Unauthorized access to /upload_avatar")
        return jsonify({'error': 'Unauthorized'}), 401
    if 'avatar' not in request.files:
        logging.error("No avatar file in request.files")
        return jsonify({'success': False, 'message': 'No avatar provided'}), 400
    file = request.files['avatar']
    if file.filename == '':
        logging.error("Empty avatar filename")
        return jsonify({'success': False, 'message': 'No avatar selected'}), 400
    try:
        filename = secure_filename(
            f"{session['username']}_{uuid.uuid4()}_{file.filename}")
        file.save(os.path.join(app.config['AVATAR_FOLDER'], filename))
        update_user_activity(session['username'])
        logging.info(f"Avatar uploaded: {filename}")
        return jsonify({'success': True, 'avatarPath': f"/{app.config['AVATAR_FOLDER']}/{filename}"})
    except Exception as e:
        logging.error(f"Error saving avatar: {e}")
        return jsonify({'success': False, 'message': 'Failed to save avatar'}), 500


@app.route('/upload_sticker', methods=['POST'])
def upload_sticker():
    if 'username' not in session:
        logging.error("Unauthorized access to /upload_sticker")
        return jsonify({'error': 'Unauthorized'}), 401
    if 'sticker' not in request.files:
        logging.error("No sticker file in request.files")
        return jsonify({'success': False, 'message': 'No sticker provided'}), 400
    file = request.files['sticker']
    if file.filename == '':
        logging.error("Empty sticker filename")
        return jsonify({'success': False, 'message': 'No sticker selected'}), 400
    try:
        filename = secure_filename(
            f"{session['username']}_{uuid.uuid4()}_{file.filename}")
        user_sticker_path = os.path.join(
            app.config['STICKER_FOLDER'], session['username'])
        file.save(os.path.join(user_sticker_path, filename))
        update_user_activity(session['username'])
        logging.info(f"Sticker uploaded for {session['username']}: {filename}")
        return jsonify({
            'success': True,
            'stickerPath': f"/{app.config['STICKER_FOLDER']}/{session['username']}/{filename}"
        })
    except Exception as e:
        logging.error(f"Error saving sticker: {e}")
        return jsonify({'success': False, 'message': 'Failed to save sticker'}), 500


@app.route('/stickers', methods=['GET'])
def get_stickers():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        user_sticker_path = os.path.join(
            app.config['STICKER_FOLDER'], session['username'])
        common_sticker_path = os.path.join(
            app.config['STICKER_FOLDER'], 'common')

        user_stickers = []
        if os.path.exists(user_sticker_path):
            for filename in os.listdir(user_sticker_path):
                if os.path.isfile(os.path.join(user_sticker_path, filename)):
                    user_stickers.append({
                        'path': f"/{app.config['STICKER_FOLDER']}/{session['username']}/{filename}",
                        'filename': filename
                    })

        common_stickers = []
        if os.path.exists(common_sticker_path):
            for filename in os.listdir(common_sticker_path):
                if os.path.isfile(os.path.join(common_sticker_path, filename)):
                    common_stickers.append({
                        'path': f"/{app.config['STICKER_FOLDER']}/common/{filename}",
                        'filename': filename
                    })

        update_user_activity(session['username'])
        return jsonify({
            'user_stickers': user_stickers,
            'common_stickers': common_stickers
        })
    except Exception as e:
        logging.error(f"Error retrieving stickers: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve stickers'}), 500


@app.route('/copy_sticker', methods=['POST'])
def copy_sticker():
    if 'username' not in session:
        logging.error("Unauthorized access to /copy_sticker")
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    sticker_path = data.get('stickerPath')
    if not sticker_path or not sticker_path.startswith(f"/{app.config['STICKER_FOLDER']}/"):
        logging.error("Invalid or missing stickerPath")
        return jsonify({'success': False, 'message': 'Invalid sticker path'}), 400
    try:
        # Extract source filename and ensure it's valid
        source_filename = os.path.basename(sticker_path)
        source_path = os.path.join(os.getcwd(), sticker_path.lstrip('/'))
        if not os.path.exists(source_path):
            logging.error(f"Sticker not found: {source_path}")
            return jsonify({'success': False, 'message': 'Sticker not found'}), 404

        # Destination path
        destination_filename = secure_filename(
            f"{session['username']}_{uuid.uuid4()}_{source_filename}")
        destination_path = os.path.join(
            app.config['STICKER_FOLDER'], session['username'], destination_filename)

        # Copy the file
        import shutil
        shutil.copy2(source_path, destination_path)

        update_user_activity(session['username'])
        logging.info(
            f"Sticker copied for {session['username']}: {destination_filename}")
        return jsonify({
            'success': True,
            'stickerPath': f"/{app.config['STICKER_FOLDER']}/{session['username']}/{destination_filename}"
        })
    except Exception as e:
        logging.error(f"Error copying sticker: {e}")
        return jsonify({'success': False, 'message': 'Failed to copy sticker'}), 500


@app.route('/profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        logging.error("Unauthorized access to /profile")
        return jsonify({'error': 'Unauthorized'}), 401
    username = session['username']
    full_name = request.form.get('full_name')
    position = request.form.get('position')
    department = request.form.get('department')
    email = request.form.get('email')
    phone_number = request.form.get('phone_number')
    avatar_path = request.form.get('avatar_path')
    update_user_activity(username)
    logging.debug(
        f"Updating profile for {username}: phone_number={phone_number}")
    if update_user_profile(username, full_name, position, department, email, phone_number, avatar_path):
        logging.info(f"Profile updated for {username}")
        return jsonify({'success': True})
    logging.error(f"Failed to update profile for {username}")
    return jsonify({'success': False, 'message': 'Failed to update profile'}), 400


@app.route('/profile/<username>', methods=['GET'])
def get_profile(username):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    update_user_activity(session['username'])
    profile = get_user_profile(username)
    if profile:
        return jsonify({'success': True, 'profile': profile})
    return jsonify({'success': False, 'message': 'Profile not found'}), 404


@app.route('/Uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/stickers/<path:filename>')
def sticker_file(filename):
    return send_from_directory(app.config['STICKER_FOLDER'], filename)


@app.route('/user_status', methods=['GET'])
def get_user_status_route():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    username = request.args.get('username')
    update_user_activity(session['username'])
    if username:
        status = get_user_status(username)
        return jsonify({'username': username, 'online': status})
    users = search_users('', session['username'])
    statuses = [
        {'username': user, 'online': get_user_status(user)} for user in users]
    return jsonify(statuses)


@socketio.on('get_chats')
def handle_get_chats():
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    update_user_activity(session['username'])
    chats = get_chats(session['username'])
    emit('chats_loaded', chats)


@socketio.on('load_messages')
def handle_load_messages(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    recipient = data.get('recipient')
    group_id = data.get('group_id')
    update_user_activity(session['username'])
    messages = get_messages(session['username'], recipient, group_id)
    emit('messages_loaded', messages)


@socketio.on('send_message')
def handle_send_message(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    sender = session['username']
    recipient = data.get('recipient')
    group_id = data.get('group_id')
    message = data.get('message')
    file = data.get('file')
    forwarded_from = data.get('forwarded_from')
    reply_to_id = data.get('reply_to_id')
    sticker = data.get('sticker', False)
    timestamp = data.get('timestamp')

    if group_id:
        group_info = get_group_members(group_id)
        if group_info['admin_only_messages']:
            if not is_user_admin_or_creator(group_id, sender):
                emit(
                    'error', {'message': 'Только администраторы могут отправлять сообщения'})
                return

    message_id = save_message(
        sender, recipient, group_id, message, file, forwarded_from, reply_to_id, sticker)
    update_user_activity(sender)

    if group_id:
        group_members = get_group_members(group_id)['members']
        for member in group_members:
            if member['username'] != sender:
                socketio.emit('receive_message', {
                    'id': message_id,
                    'sender': sender,
                    'recipient': None,
                    'group_id': group_id,
                    'message': message,
                    'timestamp': timestamp,
                    'is_read': 0,
                    'file': file,
                    'forwarded_from': forwarded_from,
                    'reply_to_id': reply_to_id,
                    'sticker': sticker
                }, room=member['username'])
                socketio.emit('update_chats', {
                    'recipient': member['username'],
                    'group_id': group_id
                }, room=member['username'])
    else:
        socketio.emit('receive_message', {
            'id': message_id,
            'sender': sender,
            'recipient': recipient,
            'group_id': None,
            'message': message,
            'timestamp': timestamp,
            'is_read': 0,
            'file': file,
            'forwarded_from': forwarded_from,
            'reply_to_id': reply_to_id,
            'sticker': sticker
        }, room=recipient)
        socketio.emit('receive_message', {
            'id': message_id,
            'sender': sender,
            'recipient': recipient,
            'group_id': None,
            'message': message,
            'timestamp': timestamp,
            'is_read': 0,
            'file': file,
            'forwarded_from': forwarded_from,
            'reply_to_id': reply_to_id,
            'sticker': sticker
        }, room=sender)
        socketio.emit('update_chats', {'recipient': recipient}, room=recipient)
        socketio.emit('update_chats', {'recipient': sender}, room=sender)


@socketio.on('mark_as_read')
def handle_mark_as_read(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    username = session['username']
    recipient = data.get('recipient')
    group_id = data.get('group_id')
    update_user_activity(username)
    mark_messages_as_read(recipient, username, group_id)
    socketio.emit('update_read_status', {
        'sender': username,
        'recipient': recipient,
        'group_id': group_id
    }, room=recipient if recipient else None)


@socketio.on('create_group')
def handle_create_group(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    group_name = data['group_name']
    members = data['members']
    creator = session['username']
    update_user_activity(creator)
    group_id = create_group(group_name, members + [creator], creator)
    for member in members + [creator]:
        socketio.emit('group_created', {
            'group_id': group_id,
            'group_name': group_name
        }, room=member)
        socketio.emit('update_chats', {
            'recipient': member,
            'group_id': group_id
        }, room=member)


@socketio.on('add_group_member')
def handle_add_group_member(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    group_id = data['group_id']
    username = data['username']
    creator = session['username']
    update_user_activity(creator)
    group_info = get_group_members(group_id)
    if group_info['creator'] != creator and not any(m['username'] == creator and m['is_admin'] for m in group_info['members']):
        emit('error', {'message': 'Only admins or creator can add members'})
        return
    if add_group_member(group_id, username):
        for member in group_info['members']:
            socketio.emit('members_updated', {
                          'group_id': group_id}, room=member['username'])
        socketio.emit('members_updated', {'group_id': group_id}, room=username)
        socketio.emit('group_created', {
            'group_id': group_id,
            'group_name': group_info['group_name']
        }, room=username)


@socketio.on('remove_group_member')
def handle_remove_group_member(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    group_id = data['group_id']
    username = data['username']
    creator = session['username']
    update_user_activity(creator)
    group_info = get_group_members(group_id)
    if group_info['creator'] != creator and not any(m['username'] == creator and m['is_admin'] for m in group_info['members']):
        emit('error', {
             'message': 'Только администраторы или владелец могут удалять пользователей'})
        return
    if remove_group_member(group_id, username):
        for member in group_info['members']:
            socketio.emit('members_updated', {
                          'group_id': group_id}, room=member['username'])
        socketio.emit('members_updated', {'group_id': group_id}, room=username)


@socketio.on('get_group_members')
def handle_get_group_members(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    group_id = data['group_id']
    update_user_activity(session['username'])
    group_info = get_group_members(group_id)
    emit('members_loaded', {
        'group_id': group_id,
        'members': group_info['members'],
        'creator': group_info['creator'],
        'admin_only_messages': group_info['admin_only_messages']
    })


@socketio.on('set_admin_only_messages')
def handle_set_admin_only_messages(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    group_id = data['group_id']
    enabled = data['enabled']
    creator = session['username']
    update_user_activity(creator)
    group_info = get_group_members(group_id)
    if group_info['creator'] != creator and not any(m['username'] == creator and m['is_admin'] for m in group_info['members']):
        emit('error', {'message': 'Only admins or creator can change settings'})
        return
    set_admin_only_messages(group_id, enabled)
    for member in group_info['members']:
        socketio.emit('members_updated', {
                      'group_id': group_id}, room=member['username'])


@socketio.on('appoint_admin')
def handle_appoint_admin(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    group_id = data['group_id']
    username = data['username']
    creator = session['username']
    update_user_activity(creator)
    group_info = get_group_members(group_id)
    if group_info['creator'] != creator:
        emit('error', {'message': 'Only the creator can appoint admins'})
        return
    if appoint_admin(group_id, username):
        for member in group_info['members']:
            socketio.emit('members_updated', {
                          'group_id': group_id}, room=member['username'])


@socketio.on('revoke_admin')
def handle_revoke_admin(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    group_id = data['group_id']
    username = data['username']
    creator = session['username']
    update_user_activity(creator)
    group_info = get_group_members(group_id)
    if group_info['creator'] != creator:
        emit('error', {
             'message': 'Только администраторы или владелец могут удалять администраторов'})
        return
    if revoke_admin(group_id, username):
        for member in group_info['members']:
            socketio.emit('members_updated', {
                          'group_id': group_id}, room=member['username'])


@socketio.on('delete_message')
def handle_delete_message(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    message_id = data['message_id']
    update_user_activity(session['username'])
    if delete_message(message_id):
        socketio.emit('message_deleted', {'message_id': message_id})


@socketio.on('forward_message')
def handle_forward_message(data):
    if 'username' not in session:
        emit('error', {'message': 'Unauthorized'})
        return
    sender = session['username']
    new_recipients = data['new_recipients']
    message = data['message']
    file = data['file']
    forwarded_from = data['forwarded_from']
    sticker = data.get('sticker', False)
    timestamp = datetime.utcnow().isoformat() + 'Z'
    update_user_activity(sender)

    for recipient in new_recipients:
        if recipient.startswith('group_'):
            group_id = int(recipient.split('_')[1])
            group_info = get_group_members(group_id)
            if group_info['admin_only_messages']:
                if not is_user_admin_or_creator(group_id, sender):
                    emit(
                        'error', {'message': f'Only admins can send messages in group {group_id}'})
                    continue
            message_id = save_message(
                sender, None, group_id, message, file, forwarded_from, None, sticker)
            for member in group_info['members']:
                if member['username'] != sender:
                    socketio.emit('receive_message', {
                        'id': message_id,
                        'sender': sender,
                        'recipient': None,
                        'group_id': group_id,
                        'message': message,
                        'timestamp': timestamp,
                        'is_read': 0,
                        'file': file,
                        'forwarded_from': forwarded_from,
                        'reply_to_id': None,
                        'sticker': sticker
                    }, room=member['username'])
                    socketio.emit('update_chats', {
                        'recipient': member['username'],
                        'group_id': group_id
                    }, room=member['username'])
        else:
            message_id = save_message(
                sender, recipient, None, message, file, forwarded_from, None, sticker)
            socketio.emit('receive_message', {
                'id': message_id,
                'sender': sender,
                'recipient': recipient,
                'group_id': None,
                'message': message,
                'timestamp': timestamp,
                'is_read': 0,
                'file': file,
                'forwarded_from': forwarded_from,
                'reply_to_id': None,
                'sticker': sticker
            }, room=recipient)
            socketio.emit('receive_message', {
                'id': message_id,
                'sender': sender,
                'recipient': recipient,
                'group_id': None,
                'message': message,
                'timestamp': timestamp,
                'is_read': 0,
                'file': file,
                'forwarded_from': forwarded_from,
                'reply_to_id': None,
                'sticker': sticker
            }, room=sender)
            socketio.emit('update_chats', {
                          'recipient': recipient}, room=recipient)
            socketio.emit('update_chats', {'recipient': sender}, room=sender)


@socketio.on('connect')
def handle_connect(auth=None):
    from flask_socketio import join_room
    if 'username' in session:
        try:
            join_room(session['username'])
            update_user_activity(session['username'])
            app.logger.debug(
                f"User {session['username']} joined room {session['username']}")
        except Exception as e:
            app.logger.error(
                f"Error joining room for {session['username']}: {e}")
    else:
        app.logger.debug("No username in session during connect")


@socketio.on('heartbeat')
def handle_heartbeat():
    if 'username' in session:
        update_user_activity(session['username'])


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=80,
                 debug=True, use_reloader=False)
