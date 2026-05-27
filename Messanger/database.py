import sqlite3
from datetime import datetime
import logging

logging.basicConfig(level=logging.DEBUG)


def init_db():
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            username TEXT PRIMARY KEY,
            full_name TEXT,
            position TEXT,
            department TEXT,
            email TEXT,
            phone_number TEXT,
            avatar_path TEXT,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            creator TEXT NOT NULL,
            admin_only_messages INTEGER DEFAULT 0,
            FOREIGN KEY(creator) REFERENCES users(username)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER,
            username TEXT,
            is_admin INTEGER DEFAULT 0,
            PRIMARY KEY (group_id, username),
            FOREIGN KEY(group_id) REFERENCES groups(group_id),
            FOREIGN KEY(username) REFERENCES users(username)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            recipient TEXT,
            group_id INTEGER,
            message TEXT,
            timestamp TEXT,
            is_read INTEGER DEFAULT 0,
            file TEXT,
            is_deleted INTEGER DEFAULT 0,
            forwarded_from TEXT,
            reply_to_id INTEGER,
            FOREIGN KEY(sender) REFERENCES users(username),
            FOREIGN KEY(recipient) REFERENCES users(username),
            FOREIGN KEY(group_id) REFERENCES groups(group_id),
            FOREIGN KEY(reply_to_id) REFERENCES messages(id)
        )
    ''')
    conn.commit()
    conn.close()


def register_user(username, password):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password, last_active) VALUES (?, ?, ?)',
                  (username, password, datetime.utcnow()))
        c.execute('INSERT INTO user_profiles (username) VALUES (?)', (username,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def login_user(username, password):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE username = ?', (username,))
    result = c.fetchone()
    if result and result[0] == password:
        c.execute('UPDATE users SET last_active = ? WHERE username = ?',
                  (datetime.utcnow(), username))
        conn.commit()
    conn.close()
    return result and result[0] == password


def update_last_active(username):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('UPDATE users SET last_active = ? WHERE username = ?',
              (datetime.utcnow(), username))
    conn.commit()
    conn.close()


def get_user_status(username):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('SELECT last_active FROM users WHERE username = ?', (username,))
    result = c.fetchone()
    conn.close()
    if result:
        last_active = datetime.fromisoformat(result[0].replace('Z', '+00:00'))
        return (datetime.utcnow() - last_active).total_seconds() < 60
    return False


def search_users(query, current_user):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('SELECT username FROM users WHERE username LIKE ? AND username != ?',
              (f'%{query}%', current_user))
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users


def update_user_profile(username, full_name, position, department, email, phone_number, avatar_path):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('''
        UPDATE user_profiles
        SET full_name = ?, position = ?, department = ?, email = ?, phone_number = ?, avatar_path = ?
        WHERE username = ?
    ''', (full_name, position, department, email, phone_number, avatar_path, username))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_user_profile(username):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('''
        SELECT full_name, position, department, email, phone_number, avatar_path
        FROM user_profiles
        WHERE username = ?
    ''', (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'full_name': row[0],
            'position': row[1],
            'department': row[2],
            'email': row[3],
            'phone_number': row[4],
            'avatar_path': row[5]
        }
    return None


def create_group(group_name, members, creator):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('INSERT INTO groups (group_name, creator) VALUES (?, ?)',
              (group_name, creator))
    group_id = c.lastrowid
    for member in members:
        is_admin = 1 if member == creator else 0
        c.execute('INSERT INTO group_members (group_id, username, is_admin) VALUES (?, ?, ?)',
                  (group_id, member, is_admin))
    conn.commit()
    conn.close()
    return group_id


def add_group_member(group_id, username):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO group_members (group_id, username, is_admin) VALUES (?, ?, 0)',
                  (group_id, username))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_group_member(group_id, username):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('DELETE FROM group_members WHERE group_id = ? AND username = ?',
              (group_id, username))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_group_members(group_id):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute(
        'SELECT username, is_admin FROM group_members WHERE group_id = ?', (group_id,))
    members = [{'username': row[0], 'is_admin': row[1]}
               for row in c.fetchall()]
    c.execute(
        'SELECT creator, admin_only_messages, group_name FROM groups WHERE group_id = ?', (group_id,))
    group_info = c.fetchone()
    conn.close()
    return {
        'members': members,
        'creator': group_info[0],
        'admin_only_messages': group_info[1],
        'group_name': group_info[2]
    }


def appoint_admin(group_id, username):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('UPDATE group_members SET is_admin = 1 WHERE group_id = ? AND username = ?',
              (group_id, username))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def revoke_admin(group_id, username):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('UPDATE group_members SET is_admin = 0 WHERE group_id = ? AND username = ?',
              (group_id, username))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def set_admin_only_messages(group_id, enabled):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('UPDATE groups SET admin_only_messages = ? WHERE group_id = ?',
              (1 if enabled else 0, group_id))
    conn.commit()
    conn.close()


def is_user_admin_or_creator(group_id, username):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('SELECT is_admin FROM group_members WHERE group_id = ? AND username = ?',
              (group_id, username))
    member = c.fetchone()
    c.execute('SELECT creator FROM groups WHERE group_id = ?', (group_id,))
    creator = c.fetchone()
    conn.close()
    return (member and member[0] == 1) or (creator and creator[0] == username)


def save_message(sender, recipient=None, group_id=None, message=None, file=None, forwarded_from=None, reply_to_id=None, sticker=False):
    conn = sqlite3.connect('messenger.db', timeout=10)
    # Включить WAL-режим для конкурентности
    conn.execute('PRAGMA journal_mode=WAL;')
    try:
        with conn:
            c = conn.cursor()
            if group_id:
                c.execute(
                    'SELECT admin_only_messages FROM groups WHERE group_id = ?', (group_id,))
                admin_only = c.fetchone()
                if admin_only and admin_only[0]:
                    if not is_user_admin_or_creator(group_id, sender):
                        logging.warning(
                            f"User {sender} not allowed to send message to group {group_id}")
                        return False
            timestamp = datetime.utcnow().isoformat()
            logging.debug(f"Saving message from {sender}, sticker={sticker}")
            c.execute('''
                INSERT INTO messages (sender, recipient, group_id, message, timestamp, file, forwarded_from, reply_to_id, sticker, is_read)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (sender, recipient, group_id, message, timestamp, file, forwarded_from, reply_to_id, sticker, 0))
            message_id = c.lastrowid
            return message_id
    except sqlite3.Error as e:
        logging.error(f"Database error while saving message: {e}")
        raise
    finally:
        conn.close()


def get_messages(sender, recipient=None, group_id=None, limit=50, offset=0):
    conn = sqlite3.connect('messenger.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL;')
    try:
        with conn:
            c = conn.cursor()
            if group_id:
                c.execute('''
                    SELECT id, sender, recipient, group_id, message, timestamp, is_read, file, forwarded_from, reply_to_id, sticker
                    FROM messages
                    WHERE group_id = ? AND is_deleted = 0
                    ORDER BY timestamp ASC
                    LIMIT ? OFFSET ?
                ''', (group_id, limit, offset))
            else:
                c.execute('''
                    SELECT id, sender, recipient, group_id, message, timestamp, is_read, file, forwarded_from, reply_to_id, sticker
                    FROM messages
                    WHERE ((sender = ? AND recipient = ?) OR (sender = ? AND recipient = ?))
                    AND group_id IS NULL AND is_deleted = 0
                    ORDER BY timestamp ASC
                    LIMIT ? OFFSET ?
                ''', (sender, recipient, recipient, sender, limit, offset))
            messages = [
                {
                    'id': row[0],
                    'sender': row[1],
                    'recipient': row[2],
                    'group_id': row[3],
                    'message': row[4],
                    'timestamp': row[5],
                    'is_read': row[6],
                    'file': row[7],
                    'forwarded_from': row[8],
                    'reply_to_id': row[9],
                    'sticker': row[10]
                } for row in c.fetchall()
            ]
            logging.debug(
                f"Retrieved {len(messages)} messages for sender={sender}, recipient={recipient}, group_id={group_id}")
            return messages
    except sqlite3.Error as e:
        logging.error(f"Database error in get_messages: {e}")
        raise
    finally:
        conn.close()


def get_chats(username):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT CASE
            WHEN sender = ? THEN recipient
            ELSE sender
        END AS username
        FROM messages
        WHERE (sender = ? OR recipient = ?) AND group_id IS NULL AND is_deleted = 0
    ''', (username, username, username))
    direct_chats = [{'username': row[0], 'is_group': False}
                    for row in c.fetchall()]

    c.execute('''
        SELECT g.group_id, g.group_name
        FROM groups g
        JOIN group_members gm ON g.group_id = gm.group_id
        WHERE gm.username = ?
    ''', (username,))
    group_chats = [{'group_id': row[0], 'group_name': row[1],
                    'is_group': True} for row in c.fetchall()]

    result = []
    for chat in direct_chats:
        c.execute('''
            SELECT COUNT(*) 
            FROM messages 
            WHERE sender = ? AND recipient = ? AND is_read = 0 AND is_deleted = 0 AND group_id IS NULL
        ''', (chat['username'], username))
        unread_count = c.fetchone()[0]
        result.append(
            {'username': chat['username'], 'unread_count': unread_count, 'is_group': False})

    for chat in group_chats:
        c.execute('''
            SELECT COUNT(*) 
            FROM messages m
            JOIN group_members gm ON m.group_id = gm.group_id
            WHERE m.group_id = ? AND gm.username = ? AND m.is_read = 0 AND m.is_deleted = 0
        ''', (chat['group_id'], username))
        unread_count = c.fetchone()[0]
        result.append({
            'group_id': chat['group_id'],
            'group_name': chat['group_name'],
            'unread_count': unread_count,
            'is_group': True
        })

    conn.close()
    # return sorted(result, key=lambda x: x.get('username', x.get('group_name', '')))
    return sorted(result, key=lambda x: str(x.get('username') or x.get('group_name') or ''))


def mark_messages_as_read(sender, recipient=None, group_id=None):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    if group_id:
        c.execute('''
            UPDATE messages
            SET is_read = 1
            WHERE group_id = ? AND is_deleted = 0
        ''', (group_id,))
    else:
        c.execute('''
            UPDATE messages
            SET is_read = 1
            WHERE sender = ? AND recipient = ? AND group_id IS NULL AND is_deleted = 0
        ''', (sender, recipient))
    conn.commit()
    conn.close()


def delete_message(message_id):
    conn = sqlite3.connect('messenger.db')
    c = conn.cursor()
    c.execute('UPDATE messages SET is_deleted = 1 WHERE id = ?', (message_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0
