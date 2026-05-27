# -*- coding: utf-8 -*-
"""
Corporate Notify — десктопный клиент уведомлений.
Python + webview (pywebview) + win10toast.
Работает как фоновый процесс, показывает приветствия поверх всех окон.
"""
import os
import sys
import json
import time
import threading
import urllib.request
import urllib.error
from datetime import datetime, date

# === Конфигурация ===
PORTAL_URL = "http://192.168.19.183"
CHECK_INTERVAL = 2  # секунд — проверка новых уведомлений
REMINDER_INTERVAL = 3600  # секунд (1 час) — напоминание о непрочитанных

# === Состояние ===
STATE_FILE = os.path.join(os.environ.get(
    'APPDATA', '.'), 'CorporateNotify', 'state.json')
USERNAME = os.environ.get('USERNAME', 'user')
USER_FIRSTNAME = ''

# Множество ID уведомлений, которые уже показали пользователю
shown_notification_ids = set()
last_reminder_time = 0


def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}


def save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f)
    except:
        pass


def fetch_json(path):
    """GET-запрос к API портала"""
    url = f"{PORTAL_URL}{path}"
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'CorporateNotify/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except:
        return None


def get_user_name():
    """Получить имя пользователя с портала"""
    global USER_FIRSTNAME
    data = fetch_json(f'/api/user-info/{USERNAME}')
    if data and data.get('firstname'):
        USER_FIRSTNAME = data['firstname']


def get_greeting_type():
    """Определить тип приветствия по времени"""
    h = datetime.now().hour
    if h < 12:
        return 'morning'
    elif h < 18:
        return 'afternoon'
    else:
        return 'evening'


def get_greeting_html(greeting_type):
    """Сгенерировать HTML приветствия"""
    name = USER_FIRSTNAME or USERNAME

    if greeting_type == 'morning':
        title = f'Доброе утро, {name}!'
        bg = "linear-gradient(to bottom, #2196F3 0%, #64B5F6 25%, #FFB74D 45%, #1c2541 70%, #0b132b 100%)"
        emoji = '☀️'
        text_shadow = "0 4px 15px rgba(33,150,243,0.6), 0 2px 30px rgba(0,0,0,0.3)"
    elif greeting_type == 'afternoon':
        title = f'Добрый день, {name}!'
        bg = "linear-gradient(to bottom, #1e90ff 0%, #4fa3d9 35%, #87ceeb 65%, #a8d8ea 100%)"
        emoji = '☀️'
        text_shadow = "0 4px 15px rgba(30,144,255,0.7), 0 2px 8px rgba(0,0,0,0.3)"
    else:
        title = f'Хорошего вечера, {name}!'
        bg = "linear-gradient(to bottom, #0b0e23 0%, #1c2541 35%, #3a2d5c 60%, #6b4c7a 80%, #d97a6a 92%, #f0a882 100%)"
        emoji = '🌙'
        text_shadow = "0 4px 15px rgba(10,15,30,0.7), 0 0 25px rgba(100,140,255,0.25)"

    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<script>
// Принудительно сбрасываем zoom WebView2 на 100%
if (window.chrome && window.chrome.webview) {{
    window.chrome.webview.postMessage('setZoom');
}}
document.addEventListener('DOMContentLoaded', function() {{
    document.body.style.zoom = (1 / window.devicePixelRatio);
}});
</script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ overflow:hidden; height:100vh; font-family:'Segoe UI',system-ui,sans-serif; background:{bg}; }}
.message {{
    position:absolute; top:40%; left:50%; transform:translate(-50%,-50%);
    font-size:4.5vw; font-weight:700; color:#fff;
    text-shadow:{text_shadow};
    text-align:center; letter-spacing:2px;
    opacity:0; animation: fadeIn 2s 0.5s forwards;
}}
.emoji {{ font-size:1.2em; margin-right:10px; }}
.close-btn {{
    position:fixed; top:20px; right:20px; z-index:9999;
    width:50px; height:50px; border-radius:50%;
    background:rgba(255,255,255,0.15); border:2px solid rgba(255,255,255,0.4);
    color:white; font-size:24px; cursor:pointer;
    display:flex; align-items:center; justify-content:center;
    backdrop-filter:blur(8px); transition:all 0.2s;
}}
.close-btn:hover {{ background:rgba(255,255,255,0.3); transform:scale(1.1); }}
@keyframes fadeIn {{ to {{ opacity:1; }} }}
</style></head>
<body>
<button class="close-btn" onclick="window.pywebview.api.close()">✕</button>
<div class="message"><span class="emoji">{emoji}</span>{title}</div>
</body></html>'''


class Api:
    """API доступный из JavaScript в webview"""

    def __init__(self, window_ref):
        self._window_ref = window_ref

    def close(self):
        if self._window_ref and self._window_ref[0]:
            self._window_ref[0].destroy()


def show_fullscreen_window(html):
    """Показать HTML окно на полный экран поверх всех окон."""
    import webview
    import ctypes

    # Отключаем DPI-масштабирование — окно будет 100% без увеличения
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    window_ref = [None]
    api = Api(window_ref)

    window = webview.create_window(
        'Corporate Portal',
        html=html,
        fullscreen=True,
        on_top=True,
        frameless=True,
        easy_drag=False,
        js_api=api
    )
    window_ref[0] = window
    webview.start(gui='edgechromium')


def show_toast(title, body):
    """Показать Windows balloon notification через Shell_NotifyIcon"""
    try:
        import ctypes
        import ctypes.wintypes as wintypes

        NIM_ADD = 0x00
        NIM_MODIFY = 0x01
        NIM_DELETE = 0x02
        NIF_INFO = 0x10
        NIF_ICON = 0x02
        NIF_TIP = 0x04
        NIIF_INFO = 0x01

        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32

        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD),
            ]

        hwnd = user32.GetDesktopWindow()

        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = hwnd
        nid.uID = 99
        nid.uFlags = NIF_INFO | NIF_ICON | NIF_TIP
        nid.hIcon = user32.LoadIconW(None, 32516)  # IDI_INFORMATION
        nid.szTip = 'Корпоративный портал'
        nid.szInfo = (body or '')[:255]
        nid.szInfoTitle = (title or '')[:63]
        nid.dwInfoFlags = NIIF_INFO

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

        def cleanup():
            time.sleep(6)
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

        threading.Thread(target=cleanup, daemon=True).start()
        print(f'[TOAST] Показано: {title}')

    except Exception as e:
        print(f'[TOAST] Ошибка: {e}')


def check_and_show_greeting():
    """Показать приветствие при первом запуске за день"""
    state = load_state()
    today = date.today().isoformat()

    if state.get('lastGreetingDate') == today:
        return False

    state['lastGreetingDate'] = today
    save_state(state)

    greeting_type = get_greeting_type()
    html = get_greeting_html(greeting_type)
    show_fullscreen_window(html)
    return True


def check_notifications():
    """Проверить новые уведомления. Показывает только те, что ещё не показывались."""
    global last_reminder_time

    data = fetch_json(f'/api/notifications/{USERNAME}')
    if data is None:
        print(f'[NOTIFY] Ошибка запроса к API')
        return

    notifications = data.get('notifications', [])
    unread_count = len(notifications)

    if unread_count > 0:
        print(f'[NOTIFY] Получено {unread_count} непрочитанных уведомлений')

    new_shown = False

    for notif in notifications:
        nid = notif.get('id', 0)
        if nid not in shown_notification_ids:
            # Новое уведомление — показываем
            shown_notification_ids.add(nid)
            title = notif.get('title', 'Уведомление')
            message = notif.get('message', '')
            print(f'[NOTIFY] Показываю: [{nid}] {title}')
            show_toast(title, message)
            new_shown = True

    # Напоминание каждый час если есть непрочитанные
    now = time.time()
    if unread_count > 0 and not new_shown and (now - last_reminder_time) >= REMINDER_INTERVAL:
        last_reminder_time = now
        print(f'[NOTIFY] Напоминание: {unread_count} непрочитанных')
        show_toast(
            'Корпоративный портал',
            f'У вас {unread_count} непрочитанных уведомлений'
        )


# Флаг для показа приветствия из фонового потока
pending_greeting = [None]  # [None] или ['morning'/'afternoon'/'evening']


def check_scheduled_greetings():
    """Проверить расписание дневных/вечерних приветствий"""
    state = load_state()
    today = date.today().isoformat()
    now = datetime.now()
    h, m = now.hour, now.minute

    if state.get('scheduledDate') != today:
        state['scheduledDate'] = today
        state['shownAfternoon'] = False
        state['shownEvening'] = False
        save_state(state)

    if h == 12 and m == 0 and not state.get('shownAfternoon'):
        state['shownAfternoon'] = True
        save_state(state)
        pending_greeting[0] = 'afternoon'

    if h == 18 and m == 20 and not state.get('shownEvening'):
        state['shownEvening'] = True
        save_state(state)
        pending_greeting[0] = 'evening'


def background_loop():
    """Фоновый цикл — проверка уведомлений каждые 2 сек, расписание каждые 30 сек"""
    schedule_counter = 0
    while True:
        try:
            check_notifications()
            schedule_counter += CHECK_INTERVAL
            if schedule_counter >= 30:
                check_scheduled_greetings()
                schedule_counter = 0
        except Exception as e:
            print(f'[ERROR] {e}')
        time.sleep(CHECK_INTERVAL)


def main():
    print(f'[NOTIFY] Запуск. Пользователь: {USERNAME}')

    # Получаем имя с портала
    get_user_name()
    print(f'[NOTIFY] Имя: {USER_FIRSTNAME or "(не получено)"}')

    # Запускаем фоновый поток проверки уведомлений
    bg_thread = threading.Thread(target=background_loop, daemon=True)
    bg_thread.start()

    # Показываем приветствие при первом запуске за день
    # show_fullscreen_window блокирует до закрытия окна, но фоновый поток продолжает работать
    greeting_shown = check_and_show_greeting()

    # После закрытия приветствия (или если не показывали) — работаем в фоне бесконечно
    print('[NOTIFY] Фоновый режим. Проверка уведомлений каждые 2 сек.')
    try:
        while True:
            # Проверяем, нужно ли показать приветствие по расписанию
            if pending_greeting[0]:
                gtype = pending_greeting[0]
                pending_greeting[0] = None
                html = get_greeting_html(gtype)
                show_fullscreen_window(html)
            time.sleep(1)
    except KeyboardInterrupt:
        print('[NOTIFY] Завершение.')


if __name__ == '__main__':
    main()
