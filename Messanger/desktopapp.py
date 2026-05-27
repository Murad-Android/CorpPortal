import flet as ft
import uuid
import json
import os
import asyncio
import base64
from datetime import datetime
import httpx
import socketio
from typing import List, Dict, Any, Optional

# Constants
UPLOAD_FOLDER = "Uploads"
AVATAR_FOLDER = f"{UPLOAD_FOLDER}/avatars"
STICKER_FOLDER = "stickers"
SERVER_URL = "http://192.168.19.135"
WEBSOCKET_URL = "ws://192.168.19.135"
CURRENT_USER = None

# Global state
current_recipient = None
current_group_id = None
message_to_forward = None
selected_forward_users = []
selected_group_members = []
reply_to_message = None
last_chat_list = []
current_sticker_tab = "user"
is_loading_messages = False
sio = socketio.AsyncClient()
client = httpx.AsyncClient(timeout=30.0)

# UI Components
messages = ft.ListView(expand=True, spacing=10, padding=20, auto_scroll=True)
chat_list = ft.ListView(expand=True, spacing=5, padding=10)
forward_user_list = ft.ListView(expand=True, spacing=5, padding=10)
group_user_list = ft.ListView(expand=True, spacing=5, padding=10)
add_participant_list = ft.ListView(expand=True, spacing=5, padding=10)
participants_list = ft.ListView(expand=True, spacing=5, padding=10)
emoji_grid = ft.GridView(
    runs_count=6, spacing=5, run_spacing=5, padding=10,
    child_aspect_ratio=1.0, expand=True
)
sticker_grid = ft.GridView(
    runs_count=4, spacing=5, run_spacing=5, padding=10,
    child_aspect_ratio=1.0, expand=True
)

# ChatListItem control


class ChatListItem(ft.Container):
    def __init__(self, chat: Dict[str, Any], on_select: callable, page: ft.Page):
        super().__init__()
        self.chat = chat
        self.on_select = on_select
        self.page = page
        self.padding = 10
        self.border_radius = 10
        self.semantics_label = f"Chat with {chat['group_name'] if chat['is_group'] else chat['username']}"
        self.build()

    def build(self):
        avatar = ft.Image(
            src="/static/images/default-avatar.png",
            width=40,
            height=40,
            border_radius=20
        ) if not self.chat["is_group"] else ft.Container(
            content=ft.Icon(ft.Icons.GROUP, color=ft.Colors.GREY_600),
            width=40,
            height=40,
            bgcolor=ft.Colors.GREY_300,
            border_radius=20,
            alignment=ft.alignment.center
        )
        name = self.chat["group_name"] if self.chat["is_group"] else self.chat["username"]
        status_indicator = ft.Container(
            width=12,
            height=12,
            bgcolor=ft.Colors.GREY_500,
            border_radius=6,
            border=ft.border.all(2, ft.Colors.WHITE)
        )
        unread_badge = ft.Text(
            str(self.chat["unread_count"]),
            bgcolor=ft.Colors.RED_500,
            color=ft.Colors.WHITE,
            size=12,
            padding=ft.padding.symmetric(2, 4),
            border_radius=12,
            visible=self.chat["unread_count"] > 0
        )
        self.content = ft.Row(
            [
                avatar,
                ft.Text(name, weight=ft.FontWeight.BOLD),
                status_indicator,
                unread_badge
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )
        self.on_click = lambda e: self.on_select(
            None if self.chat["is_group"] else self.chat["username"],
            self.chat["group_id"] if self.chat["is_group"] else None,
            self.chat["group_name"] if self.chat["is_group"] else None,
            self.page
        )

    async def update_status(self):
        if not self.chat["is_group"]:
            status = await fetch_user_status(self.chat["username"])
            profile = await fetch_profile(self.chat["username"])
            avatar_url = profile["profile"]["avatar_path"] if profile["success"] and profile[
                "profile"]["avatar_path"] else "/static/images/default-avatar.png"
            self.content.controls[0].src = avatar_url
            self.content.controls[2].bgcolor = ft.Colors.GREEN_500 if status.get(
                "online", False) else ft.Colors.GREY_500
            self.update()

# Helper to generate UUID


def generate_uuid():
    return str(uuid.uuid4())

# WebSocket handler


async def websocket_connect(page: ft.Page):
    global sio
    if sio.connected:
        print("WebSocket already connected, skipping")
        return

    @sio.event
    async def connect():
        print("WebSocket connected")
        await sio.emit("get_chats")  # Emit without data
        try:
            page.client_storage.set("ws_connected", True)
        except Exception as e:
            print(f"Failed to set ws_connected: {e}")
        page.update()

    @sio.event
    async def disconnect():
        print("WebSocket disconnected")
        try:
            page.client_storage.set("ws_connected", False)
        except Exception as e:
            print(f"Failed to set ws_connected: {e}")
        page.update()
        for attempt in range(10):
            try:
                await asyncio.sleep(min(2 ** attempt, 16))
                await sio.connect(WEBSOCKET_URL, wait_timeout=10)
                print(f"Reconnected on attempt {attempt + 1}")
                break
            except Exception as e:
                print(f"Reconnection attempt {attempt + 1} failed: {e}")
        else:
            print("Max reconnection attempts reached")
            page.snack_bar = ft.SnackBar(content=ft.Text(
                "Failed to reconnect to WebSocket"))
            page.snack_bar.open = True
            page.update()

    @sio.on("connect")
    async def on_connect():
        await sio.emit("get_chats")  # Emit without data

    @sio.on("group_created")
    async def on_group_created(data):
        await refresh_chats(page)
        await select_chat(None, data["group_id"], data["group_name"], page)

    @sio.on("members_loaded")
    async def on_members_loaded(data):
        await show_group_participants(data, page)

    @sio.on("members_updated")
    async def on_members_updated(data):
        if data["group_id"] == current_group_id:
            await sio.emit("get_group_members", {"group_id": data["group_id"]})
        await refresh_chats(page)

    @sio.on("error")
    async def on_error(data):
        if data["message"] == "Unauthorized":
            page.go("/")
        else:
            page.snack_bar = ft.SnackBar(content=ft.Text(data["message"]))
            page.snack_bar.open = True
            page.update()

    @sio.on("chats_loaded")
    async def on_chats_loaded(data):
        await update_chat_list(data, page)

    @sio.on("update_chats")
    async def on_update_chats(data):
        if data.get("recipient") == CURRENT_USER or (data.get("group_id") and current_group_id == data["group_id"]):
            await refresh_chats(page)

    @sio.on("messages_loaded")
    async def on_messages_loaded(data):
        global is_loading_messages
        print("Messages loaded:", [
              {"id": m["id"], "timestamp": m["timestamp"]} for m in data])
        messages.controls.clear()
        data.sort(key=lambda x: x["timestamp"])
        for msg in data:
            await add_message(
                msg["id"], msg["sender"], msg["message"], msg["timestamp"], msg["is_read"],
                msg.get("file"), msg.get("forwarded_from"), msg.get(
                    "group_id"), msg.get("reply_to_id"),
                msg.get("sticker", False), page
            )
        is_loading_messages = False
        page.update()

    @sio.on("receive_message")
    async def on_receive_message(data):
        print("Received message:", {
              "id": data["id"], "timestamp": data["timestamp"]})
        if (data["recipient"] == current_recipient and not data["group_id"]) or data["group_id"] == current_group_id:
            placeholder = next(
                (c for c in messages.controls if c.data == "placeholder"), None)
            if placeholder:
                messages.controls.remove(placeholder)
            await add_message(
                data["id"], data["sender"], data["message"], data["timestamp"], data["is_read"],
                data.get("file"), data.get(
                    "forwarded_from"), data["group_id"], data["reply_to_id"],
                data.get("sticker", False), page
            )
            await sio.emit("mark_as_read", {"recipient": data["sender"], "group_id": data["group_id"]})
        if (data["recipient"] != current_recipient and not data["group_id"]) or (data["group_id"] and data["group_id"] != current_group_id):
            await refresh_chats(page)
        page.update()

    @sio.on("update_read_status")
    async def on_update_read_status(data):
        if (data["recipient"] == CURRENT_USER and data["sender"] == current_recipient and not data["group_id"]) or data["group_id"] == current_group_id:
            for msg in messages.controls:
                if msg.data.get("sender") == CURRENT_USER and msg.data.get("is_read") == 0:
                    msg.data["is_read"] = 1
                    status = msg.controls[0].controls[-1].controls[-1]
                    status.content = ft.Icon(
                        ft.Icons.DONE_ALL, color=ft.Colors.INDIGO_200)
            page.update()

    @sio.on("message_deleted")
    async def on_message_deleted(data):
        msg = next((m for m in messages.controls if m.data.get(
            "message_id") == data["message_id"]), None)
        if msg:
            messages.controls.remove(msg)
            page.update()

    try:
        await sio.connect(WEBSOCKET_URL, wait_timeout=10)
        print("Initial WebSocket connection successful")
    except Exception as e:
        print(f"Initial WebSocket connection failed: {e}")
        page.snack_bar = ft.SnackBar(content=ft.Text(
            f"WebSocket connection failed: {str(e)}"))
        page.snack_bar.open = True
        page.update()


async def ws_send(data: Dict[str, Any]):
    if sio.connected:
        # Special handling for get_chats to avoid sending data
        if data["type"] == "get_chats":
            await sio.emit("get_chats")
        else:
            await sio.emit(data["type"], data)
    else:
        print("WebSocket not connected, skipping send")

# API calls


async def fetch_profile(username: str) -> Dict[str, Any]:
    try:
        resp = await client.get(f"{SERVER_URL}/profile/{username}")
        return resp.json()
    except Exception as e:
        print("Profile fetch error:", e)
        return {"success": False}


async def update_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        form_data = {k: v for k, v in data.items() if k != "avatar"}
        if "avatar" in data:
            files = {"avatar": (
                data["avatar"]["name"], data["avatar"]["data"], data["avatar"]["type"])}
            resp = await client.post(f"{SERVER_URL}/upload_avatar", files=files)
            avatar_data = resp.json()
            if avatar_data["success"]:
                form_data["avatar_path"] = avatar_data["avatarPath"]
        resp = await client.post(f"{SERVER_URL}/profile", data=form_data)
        return resp.json()
    except Exception as e:
        print("Profile update error:", e)
        return {"success": False}


async def upload_file(file: Dict[str, Any], recipient: Optional[str], group_id: Optional[int]) -> Dict[str, Any]:
    try:
        files = {"file": (file["name"], file["data"], file["type"])}
        data = {"recipient": recipient or "",
                "group_id": str(group_id) if group_id else ""}
        resp = await client.post(f"{SERVER_URL}/upload", files=files, data=data)
        return resp.json()
    except Exception as e:
        print("File upload error:", e)
        return {"success": False}


async def upload_sticker(file: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = await client.post(f"{SERVER_URL}/upload_sticker", files={"sticker": (file["name"], file["data"], file["type"])})
        return resp.json()
    except Exception as e:
        print("Sticker upload error:", e)
        return {"success": False}


async def copy_sticker(sticker_path: str) -> Dict[str, Any]:
    try:
        resp = await client.post(f"{SERVER_URL}/copy_sticker", json={"stickerPath": sticker_path})
        return resp.json()
    except Exception as e:
        print("Copy sticker error:", e)
        return {"success": False}


async def fetch_stickers() -> Dict[str, Any]:
    try:
        resp = await client.get(f"{SERVER_URL}/stickers")
        return resp.json()
    except Exception as e:
        print("Fetch stickers error:", e)
        return {"user_stickers": [], "common_stickers": []}


async def search_users(query: str) -> List[str]:
    try:
        resp = await client.get(f"{SERVER_URL}/search?query={query}")
        return resp.json()
    except Exception as e:
        print("Search error:", e)
        return []


async def fetch_user_status(username: Optional[str] = None) -> Dict[str, Any]:
    try:
        url = f"{SERVER_URL}/user_status"
        if username:
            url += f"?username={username}"
        resp = await client.get(url)
        data = resp.json()
        # Ensure consistent return type: dict for single user, list for multiple
        if username:
            return data[0] if data else {"username": username, "online": False, "last_seen": None}
        return data
    except Exception as e:
        print("User status error:", e)
        return {"username": username, "online": False, "last_seen": None} if username else []

# UI Component Functions


def create_login_page(page: ft.Page) -> ft.Control:
    username_field = ft.TextField(
        label="Имя пользователя",
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=ft.Colors.INDIGO_500
    )
    password_field = ft.TextField(
        label="Пароль",
        password=True,
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=ft.Colors.INDIGO_500
    )
    error_text = ft.Text(color=ft.Colors.RED_500, visible=False)

    async def handle_login(e):
        username = username_field.value.strip()
        password = password_field.value.strip()
        if not username or not password:
            error_text.value = "Введите имя пользователя и пароль"
            error_text.visible = True
            page.update()
            return
        try:
            resp = await client.post(
                f"{SERVER_URL}/login",
                json={"username": username, "password": password}
            )
            data = resp.json()
            if data.get("success"):
                global CURRENT_USER
                CURRENT_USER = username
                try:
                    page.client_storage.set("username", username)
                except Exception as e:
                    print(f"Failed to set username in clientStorage: {e}")
                    page.snack_bar = ft.SnackBar(content=ft.Text(
                        "Warning: Could not save session, login may not persist"))
                    page.snack_bar.open = True
                page.go("/chat")
            else:
                error_text.value = data.get("message", "Ошибка входа")
                error_text.visible = True
                page.update()
        except Exception as e:
            print("Login error:", e)
            error_text.value = "Не удалось подключиться к серверу"
            error_text.visible = True
            page.update()

    async def handle_register(e):
        username = username_field.value.strip()
        password = password_field.value.strip()
        if not username or not password:
            error_text.value = "Введите имя пользователя и пароль"
            error_text.visible = True
            page.update()
            return
        try:
            resp = await client.post(
                f"{SERVER_URL}/register",
                json={"username": username, "password": password}
            )
            data = resp.json()
            if data.get("success"):
                global CURRENT_USER
                CURRENT_USER = username
                try:
                    page.client_storage.set("username", username)
                except Exception as e:
                    print(f"Failed to set username in clientStorage: {e}")
                    page.snack_bar = ft.SnackBar(content=ft.Text(
                        "Warning: Could not save session, login may not persist"))
                    page.snack_bar.open = True
                page.go("/chat")
            else:
                error_text.value = data.get("message", "Ошибка регистрации")
                error_text.visible = True
                page.update()
        except Exception as e:
            print("Register error:", e)
            error_text.value = "Не удалось подключиться к серверу"
            error_text.visible = True
            page.update()

    return ft.Container(
        content=ft.Column(
            [
                ft.Text("Катюша мессенджер", size=24,
                        weight=ft.FontWeight.BOLD),
                username_field,
                password_field,
                error_text,
                ft.ElevatedButton(
                    "Войти",
                    bgcolor=ft.Colors.INDIGO_600,
                    color=ft.Colors.WHITE,
                    on_click=handle_login
                ),
                ft.ElevatedButton(
                    "Регистрация",
                    bgcolor=ft.Colors.GREY_600,
                    color=ft.Colors.WHITE,
                    on_click=handle_register
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        ),
        padding=40,
        alignment=ft.alignment.center,
        expand=True
    )


def create_message_input(page: ft.Page) -> ft.Control:
    message_input = ft.TextField(
        hint_text="Введите сообщение...",
        expand=True,
        border_radius=25,
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=ft.Colors.INDIGO_500
    )
    file_input = ft.FilePicker(
        on_result=lambda e: handle_file_pick(e, page)
    )
    sticker_input = ft.FilePicker(
        on_result=lambda e: page.run_task(handle_sticker_pick, e, page)
    )
    file_preview = ft.Row(
        [
            ft.Image(width=100, height=100, border_radius=10, visible=False),
            ft.Text(color=ft.Colors.GREY_600, size=12),
            ft.IconButton(
                ft.Icons.CLOSE,
                icon_color=ft.Colors.RED_500,
                on_click=lambda e: clear_file(page)
            )
        ],
        visible=False
    )
    reply_preview = ft.Container(
        content=ft.Row(
            [
                ft.Text(color=ft.Colors.GREY_600, size=12, expand=True),
                ft.IconButton(
                    ft.Icons.CLOSE,
                    icon_color=ft.Colors.RED_500,
                    on_click=lambda e: clear_reply(page)
                )
            ],
            visible=False
        ),
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
        padding=10,
        border_radius=10
    )

    async def handle_submit(e):
        if not (current_recipient or current_group_id):
            return
        placeholder = ft.Row(
            [ft.Container(
                content=ft.Text("Sending...", italic=True, size=12),
                bgcolor=ft.Colors.INDIGO_300,
                padding=15,
                border_radius=10,
                width=200
            )],
            alignment=ft.MainAxisAlignment.END,
            data="placeholder"
        )
        messages.controls.append(placeholder)
        messages.scroll_to(offset=-1, duration=0)
        page.update()

        if file_preview.visible:
            file_data = file_preview.controls[0].src_base64
            file_name = file_preview.controls[1].value
            file_type = "image/png" if file_name.lower().endswith((".png", ".jpg", ".jpeg",
                                                                   ".gif")) else "application/octet-stream"
            result = await upload_file(
                {"name": file_name, "data": base64.b64decode(
                    file_data.split(",")[1]), "type": file_type},
                current_recipient, current_group_id
            )
            if result["success"]:
                await ws_send({
                    "type": "send_message",
                    "recipient": current_recipient,
                    "group_id": current_group_id,
                    "message": file_name,
                    "file": result["filePath"],
                    "reply_to_id": reply_to_message["id"] if reply_to_message else None,
                    "sticker": False,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
                clear_reply(page)
                clear_file(page)
            else:
                messages.controls.remove(placeholder)
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Failed to upload file"))
                page.snack_bar.open = True
        elif message_input.value.strip():
            await ws_send({
                "type": "send_message",
                "recipient": current_recipient,
                "group_id": current_group_id,
                "message": message_input.value,
                "reply_to_id": reply_to_message["id"] if reply_to_message else None,
                "sticker": False,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
            message_input.value = ""
            clear_reply(page)
        page.update()

    return ft.Column(
        [
            reply_preview,
            ft.Row(
                [
                    ft.IconButton(
                        ft.Icons.ATTACH_FILE,
                        icon_color=ft.Colors.GREY_500,
                        on_click=lambda e: file_input.pick_files(
                            allow_multiple=False,
                            allowed_extensions=[
                                "png", ".jpg", "jpeg", "gif", "pdf"]
                        )
                    ),
                    message_input,
                    ft.IconButton(
                        ft.Icons.STICKY_NOTE_2,
                        icon_color=ft.Colors.GREY_500,
                        on_click=lambda e: open_sticker_modal(page)
                    ),
                    ft.IconButton(
                        ft.Icons.EMOJI_EMOTIONS,
                        icon_color=ft.Colors.GREY_500,
                        on_click=lambda e: open_emoji_modal(page)
                    ),
                    ft.IconButton(
                        ft.Icons.SEND,
                        bgcolor=ft.Colors.INDIGO_600,
                        icon_color=ft.Colors.WHITE,
                        on_click=handle_submit
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            ),
            file_preview,
            file_input,
            sticker_input
        ],
        spacing=10
    )


def handle_file_pick(e: ft.FilePickerResultEvent, page: ft.Page):
    if e.files:
        file = e.files[0]
        print(f"Selected file: {file.name}, path: {file.path}")
        # Access file_preview from global message_input
        global message_input_container
        if hasattr(message_input_container, 'controls') and len(message_input_container.controls) > 2:
            file_preview = message_input_container.controls[2]
            file_preview.visible = True
            file_preview.controls[1].value = file.name
            if file.name.lower().endswith((".png", ".jpg", "jpeg", "gif")):
                with open(file.path, "rb") as f:
                    file_preview.controls[0].src_base64 = base64.b64encode(
                        f.read()).decode()
                file_preview.controls[0].visible = True
            else:
                file_preview.controls[0].visible = False
            page.update()


async def handle_sticker_pick(e: ft.FilePickerResultEvent, page: ft.Page):
    if e.files:
        file = e.files[0]
        print(f"Selected sticker: {file.name}, path: {file.path}")
        if not file.name.lower().endswith((".png", ".jpg", "jpeg", "gif")):
            page.snack_bar = ft.SnackBar(content=ft.Text(
                "Only image files are allowed for stickers"))
            page.snack_bar.open = True
            page.update()
            return
        with open(file.path, "rb") as f:
            result = await upload_sticker({"name": file.name, "data": f.read(), "type": "image/png"})
        if result["success"]:
            await load_stickers("user", page)
        else:
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Failed to upload sticker"))
            page.snack_bar.open = True
        page.update()


def clear_file(page: ft.Page):
    global message_input_container
    if hasattr(message_input_container, 'controls') and len(message_input_container.controls) > 2:
        file_preview = message_input_container.controls[2]
        file_preview.visible = False
        file_preview.controls[0].visible = False
        file_preview.controls[1].value = ""
        page.update()


def clear_reply(page: ft.Page):
    global reply_to_message, message_input_container
    reply_to_message = None
    if hasattr(message_input_container, 'controls') and len(message_input_container.controls) > 0:
        reply_preview = message_input_container.controls[0]
        reply_preview.content.visible = False
        reply_preview.content.controls[0].value = ""
        print("Cleared reply preview")
        page.update()


def create_chat_header(page: ft.Page) -> ft.Control:
    chat_title = ft.Text("Выбрать чат", weight=ft.FontWeight.BOLD, size=16)
    chat_subtitle = ft.Text(
        "Начать разговор", color=ft.Colors.GREY_500, size=12)
    row = ft.Row(
        [
            ft.Container(
                content=ft.Icon(ft.Icons.GROUP, color=ft.Colors.GREY_600),
                width=48, height=48, bgcolor=ft.Colors.GREY_300, border_radius=24,
                alignment=ft.alignment.center
            ),
            ft.Column([chat_title, chat_subtitle], spacing=5)
        ],
        alignment=ft.MainAxisAlignment.START
    )
    return ft.Container(
        content=row,
        padding=10
    )


def create_emoji_modal(page: ft.Page) -> ft.AlertDialog:
    emojis = ["😊", "😂", "😍", "😢", "😎", "😡", "👍", "👎",
              "🙌", "🎉", "❤️", "🔥", "🌟", "💪", "👀", "🤓", "😴", "🥳"]
    emoji_grid.controls = [
        ft.Container(
            content=ft.Text(emoji, size=24),
            alignment=ft.alignment.center,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
            border_radius=10,
            on_click=lambda e, em=emoji: (
                setattr(message_input_container.controls[1].controls[1], "value",
                        message_input_container.controls[1].controls[1].value + em),
                page.update()
            )
        ) for emoji in emojis
    ]
    return ft.AlertDialog(
        title=ft.Text("Выберите эмодзи"),
        content=emoji_grid,
        actions=[ft.TextButton(
            "Закрыть", on_click=lambda e: close_dialog(page, "emoji"))],
        modal=True
    )


def create_sticker_modal(page: ft.Page) -> ft.AlertDialog:
    user_tab = ft.TextButton(
        "Мои стикеры",
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.INDIGO_500 if current_sticker_tab == "user" else ft.Colors.GREY_200),
        on_click=lambda e: switch_sticker_tab("user", page)
    )
    common_tab = ft.TextButton(
        "Общие стикеры",
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.INDIGO_500 if current_sticker_tab == "common" else ft.Colors.GREY_200),
        on_click=lambda e: switch_sticker_tab("common", page)
    )
    upload_button = ft.ElevatedButton(
        "Загрузить стикер",
        bgcolor=ft.Colors.INDIGO_500,
        color=ft.Colors.WHITE,
        on_click=lambda e: message_input_container.controls[4].pick_files(
            allow_multiple=False,
            allowed_extensions=["png", ".jpg", "jpeg", "gif"]
        )
    )
    return ft.AlertDialog(
        title=ft.Text("Выберите стикер"),
        content=ft.Column([ft.Row([user_tab, common_tab], alignment=ft.MainAxisAlignment.CENTER),
                          upload_button, sticker_grid], height=300),
        actions=[ft.TextButton(
            "Закрыть", on_click=lambda e: close_dialog(page, "sticker"))],
        modal=True
    )


def switch_sticker_tab(tab: str, page: ft.Page):
    global current_sticker_tab
    current_sticker_tab = tab
    page.run_task(load_stickers, tab, page)
    if page.dialog and hasattr(page.dialog, 'content'):
        page.dialog.content.controls[0].controls[0].style.bgcolor = ft.Colors.INDIGO_500 if tab == "user" else ft.Colors.GREY_200
        page.dialog.content.controls[0].controls[1].style.bgcolor = ft.Colors.INDIGO_500 if tab == "common" else ft.Colors.GREY_200
    page.update()


async def load_stickers(tab: str, page: ft.Page):
    data = await fetch_stickers()
    stickers = data["user_stickers"] if tab == "user" else data["common_stickers"]
    sticker_grid.controls = [
        ft.Container(
            content=ft.Image(
                src=sticker["path"],
                width=100,
                height=100,
                border_radius=10,
                fit=ft.ImageFit.CONTAIN,
                tooltip=sticker["filename"]
            ),
            on_click=lambda e, path=sticker["path"]: send_sticker(path, page)
        ) for sticker in stickers
    ]
    page.update()


def send_sticker(sticker_path: str, page: ft.Page):
    if not (current_recipient or current_group_id):
        return
    page.run_task(ws_send, {
        "type": "send_message",
        "recipient": current_recipient,
        "group_id": current_group_id,
        "message": "",
        "file": sticker_path,
        "sticker": True,
        "reply_to_id": reply_to_message["id"] if reply_to_message else None,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })
    close_dialog(page, "sticker")
    clear_reply(page)


def create_forward_modal(page: ft.Page) -> ft.AlertDialog:
    forward_search = ft.TextField(
        hint_text="Поиск пользователей или групп...",
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
        on_change=lambda e: page.run_task(
            search_forward_users, e.control.value, page)
    )
    return ft.AlertDialog(
        title=ft.Text("Переслано от:"),
        content=ft.Column([forward_search, forward_user_list], height=300),
        actions=[
            ft.TextButton(
                "Отмена", on_click=lambda e: close_forward_modal(page)),
            ft.ElevatedButton("Отправить", bgcolor=ft.Colors.INDIGO_600,
                              color=ft.Colors.WHITE, on_click=lambda e: send_forward(page))
        ],
        modal=True
    )


async def search_forward_users(query: str, page: ft.Page):
    users = await search_users(query)
    chats = (await client.get(f"{SERVER_URL}/chats")).json()
    statuses = await fetch_user_status()
    forward_user_list.controls = []
    for user in users:
        if user != current_recipient:
            status = next((s for s in statuses if s["username"] == user), {
                          "online": False})
            profile = await fetch_profile(user)
            avatar = profile["profile"]["avatar_path"] if profile["success"] and profile[
                "profile"]["avatar_path"] else "/static/images/default-avatar.png"
            forward_user_list.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Image(src=avatar, width=32,
                                     height=32, border_radius=16),
                            ft.Text(user, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                width=12, height=12, bgcolor=ft.Colors.GREEN_500 if status["online"] else ft.Colors.GREY_500,
                                border_radius=6, border=ft.border.all(2, ft.Colors.WHITE)
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    padding=10,
                    bgcolor=ft.Colors.INDIGO_100 if user in selected_forward_users else None,
                    border_radius=10,
                    on_click=lambda e, u=user: toggle_forward_user(u, page)
                )
            )
    for chat in [c for c in chats if c["is_group"] and c["group_id"] != current_group_id]:
        group_id = f"group_{chat['group_id']}"
        forward_user_list.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.GROUP, size=16, color=ft.Colors.GREY_600),
                            width=32, height=32, bgcolor=ft.Colors.GREY_300, border_radius=16
                        ),
                        ft.Text(chat["group_name"], weight=ft.FontWeight.BOLD)
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=10,
                bgcolor=ft.Colors.INDIGO_100 if group_id in selected_forward_users else None,
                border_radius=10,
                on_click=lambda e, g=group_id: toggle_forward_user(g, page)
            )
        )
    page.update()


def toggle_forward_user(user: str, page: ft.Page):
    global selected_forward_users
    if user in selected_forward_users:
        selected_forward_users.remove(user)
    else:
        selected_forward_users.append(user)
    page.run_task(search_forward_users,
                  page.dialog.content.controls[0].value, page)


def send_forward(page: ft.Page):
    global selected_forward_users, message_to_forward
    if selected_forward_users and message_to_forward:
        page.run_task(ws_send, {
            "type": "forward_message",
            "new_recipients": selected_forward_users,
            "message": message_to_forward["message"],
            "file": message_to_forward["file"],
            "forwarded_from": message_to_forward["sender"],
            "sticker": message_to_forward.get("sticker", False)
        })
        close_forward_modal(page)


def close_forward_modal(page: ft.Page):
    global selected_forward_users, message_to_forward
    selected_forward_users = []
    message_to_forward = None
    forward_user_list.controls.clear()
    page.dialog.content.controls[0].value = ""
    close_dialog(page, "forward")


def create_group_modal(page: ft.Page) -> ft.AlertDialog:
    group_name = ft.TextField(hint_text="Название группы...", border_radius=10,
                              bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY))
    group_search = ft.TextField(
        hint_text="Поиск пользователей...",
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
        on_change=lambda e: page.run_task(
            search_group_users, e.control.value, page)
    )
    return ft.AlertDialog(
        title=ft.Text("Создать групповой чат"),
        content=ft.Column(
            [group_name, group_search, group_user_list], height=300),
        actions=[
            ft.TextButton(
                "Отмена", on_click=lambda e: close_group_modal(page)),
            ft.ElevatedButton("Создать", bgcolor=ft.Colors.INDIGO_600, color=ft.Colors.WHITE,
                              on_click=lambda e: create_group(group_name.value, page))
        ],
        modal=True
    )


async def search_group_users(query: str, page: ft.Page):
    users = await search_users(query)
    group_user_list.controls = []
    for user in users:
        profile = await fetch_profile(user)
        avatar = profile["profile"]["avatar_path"] if profile["success"] and profile[
            "profile"]["avatar_path"] else "/static/images/default-avatar.png"
        group_user_list.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Checkbox(value=user in selected_group_members,
                                    on_change=lambda e, u=user: toggle_group_member(u, page)),
                        ft.Image(src=avatar, width=32,
                                 height=32, border_radius=16),
                        ft.Text(user, weight=ft.FontWeight.BOLD)
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=10,
                border_radius=10
            )
        )
    page.update()


def toggle_group_member(user: str, page: ft.Page):
    global selected_group_members
    if user in selected_group_members:
        selected_group_members.remove(user)
    else:
        selected_group_members.append(user)
    page.run_task(search_group_users,
                  page.dialog.content.controls[1].value, page)


def create_group(group_name: str, page: ft.Page):
    global selected_group_members
    if group_name.strip() and selected_group_members:
        page.run_task(ws_send, {
                      "type": "create_group", "group_name": group_name, "members": selected_group_members})
        close_group_modal(page)
    else:
        page.snack_bar = ft.SnackBar(content=ft.Text(
            "Please enter a group name and select at least one member"))
        page.snack_bar.open = True
        page.update()


def close_group_modal(page: ft.Page):
    global selected_group_members
    selected_group_members = []
    group_user_list.controls.clear()
    if page.dialog and hasattr(page.dialog, 'content'):
        page.dialog.content.controls[0].value = ""
        page.dialog.content.controls[1].value = ""
    close_dialog(page, "group")


def create_participants_modal(page: ft.Page) -> ft.AlertDialog:
    add_participant_search = ft.TextField(
        hint_text="Поиск пользователей...",
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY),
        on_change=lambda e: page.run_task(
            search_add_participant, e.control.value, page),
        visible=False
    )
    admin_only_toggle = ft.Checkbox(
        label="Разрешить отправлять сообщения только админам", visible=False)
    add_participant_btn = ft.ElevatedButton(
        "Добавить участника",
        bgcolor=ft.Colors.INDIGO_500,
        color=ft.Colors.WHITE,
        on_click=lambda e: toggle_add_participant(page)
    )
    return ft.AlertDialog(
        title=ft.Text("Участники группы"),
        content=ft.Column([admin_only_toggle, add_participant_btn, add_participant_search,
                          add_participant_list, participants_list], height=300),
        actions=[ft.TextButton(
            "Отмена", on_click=lambda e: close_participants_modal(page))],
        modal=True
    )


def toggle_add_participant(page: ft.Page):
    if page.dialog and hasattr(page.dialog, 'content'):
        dialog = page.dialog
        dialog.content.controls[2].visible = not dialog.content.controls[2].visible
        dialog.content.controls[3].visible = not dialog.content.controls[3].visible
        page.update()


async def search_add_participant(query: str, page: ft.Page):
    users = await search_users(query)
    await ws_send({"type": "get_group_members", "group_id": current_group_id})

    async def handle_members(data: Dict[str, Any]):
        current_members = [m["username"] for m in data["members"]]
        add_participant_list.controls = []
        for user in users:
            if user not in current_members:
                profile = await fetch_profile(user)
                avatar = profile["profile"]["avatar_path"] if profile["success"] and profile[
                    "profile"]["avatar_path"] else "/static/images/default-avatar.png"
                add_participant_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Image(src=avatar, width=32,
                                         height=32, border_radius=16),
                                ft.Text(user, weight=ft.FontWeight.BOLD)
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        padding=10,
                        border_radius=10,
                        on_click=lambda e, u=user: add_group_member(u, page)
                    )
                )
        page.update()
    sio.on("members_loaded", handle_members)
    page.update()


def add_group_member(username: str, page: ft.Page):
    page.run_task(ws_send, {"type": "add_group_member",
                  "group_id": current_group_id, "username": username})
    if page.dialog and hasattr(page.dialog, 'content'):
        page.dialog.content.controls[2].visible = False
        page.dialog.content.controls[3].visible = False
        page.dialog.content.controls[2].value = ""
    add_participant_list.controls.clear()
    page.update()


def close_participants_modal(page: ft.Page):
    participants_list.controls.clear()
    add_participant_list.controls.clear()
    if page.dialog and hasattr(page.dialog, 'content'):
        page.dialog.content.controls[2].visible = False
        page.dialog.content.controls[3].visible = False
        page.dialog.content.controls[0].visible = False
    close_dialog(page, "participants")


def create_profile_edit_modal(page: ft.Page) -> ft.AlertDialog:
    full_name = ft.TextField(hint_text="Введите полное имя", border_radius=10)
    position = ft.TextField(hint_text="Введите должность", border_radius=10)
    department = ft.TextField(hint_text="Введите отдел", border_radius=10)
    email = ft.TextField(hint_text="Введите почту", border_radius=10)
    phone = ft.TextField(hint_text="Введите номер телефона", border_radius=10)
    avatar_preview = ft.Image(width=100, height=100,
                              border_radius=10, visible=False)
    avatar_picker = ft.FilePicker(
        on_result=lambda e: handle_avatar_pick(e, avatar_preview, page)
    )

    async def save_profile(e):
        data = {
            "full_name": full_name.value,
            "position": position.value,
            "department": department.value,
            "email": email.value,
            "phone_number": phone.value
        }
        if avatar_picker.result and avatar_picker.result.files:
            file = avatar_picker.result.files[0]
            with open(file.path, "rb") as f:
                data["avatar"] = {"name": file.name,
                                  "data": f.read(), "type": "image/png"}
        result = await update_profile(data)
        if result["success"]:
            close_dialog(page, "profile_edit")
            await refresh_chats(page)
        else:
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Failed to update profile"))
            page.snack_bar.open = True
        page.update()

    return ft.AlertDialog(
        title=ft.Text("Редактировать профиль"),
        content=ft.Column(
            [full_name, position, department, email, phone,
             ft.ElevatedButton("Выбрать аватар", on_click=lambda e: avatar_picker.pick_files(
                 allow_multiple=False,
                 allowed_extensions=["png", ".jpg", "jpeg"]
             )),
             avatar_preview, avatar_picker],
            height=400
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda e: close_dialog(
                page, "profile_edit")),
            ft.ElevatedButton("Сохранить", bgcolor=ft.Colors.INDIGO_600,
                              color=ft.Colors.WHITE, on_click=lambda e: page.run_task(save_profile))
        ],
        modal=True
    )


def handle_avatar_pick(e: ft.FilePickerResultEvent, avatar_preview: ft.Image, page: ft.Page):
    if e.files:
        file = e.files[0]
        print(f"Selected avatar: {file.name}, path: {file.path}")
        if not file.name.lower().endswith((".png", ".jpg", "jpeg")):
            page.snack_bar = ft.SnackBar(content=ft.Text(
                "Only PNG and JPEG files are allowed for avatars"))
            page.snack_bar.open = True
            page.update()
            return
        with open(file.path, "rb") as f:
            avatar_preview.src_base64 = base64.b64encode(f.read()).decode()
        avatar_preview.visible = True
        page.update()


def create_profile_view_modal(page: ft.Page) -> ft.AlertDialog:
    avatar = ft.Image(width=96, height=96, border_radius=48)
    username = ft.Text()
    full_name = ft.Text()
    position = ft.Text()
    department = ft.Text()
    email = ft.Text()
    phone = ft.Text()
    return ft.AlertDialog(
        title=ft.Text("Профиль пользователя"),
        content=ft.Column(
            [avatar, ft.Text("Имя пользователя: "), username, ft.Text("Полное имя: "), full_name,
             ft.Text("Должность: "), position, ft.Text("Отдел: "), department, ft.Text("Почта: "), email, ft.Text("Телефон: "), phone],
            alignment=ft.MainAxisAlignment.CENTER
        ),
        actions=[ft.TextButton(
            "Закрыть", on_click=lambda e: close_dialog(page, "profile_view"))],
        modal=True
    )


async def show_profile_view(username: str, page: ft.Page):
    profile = await fetch_profile(username)
    if profile["success"]:
        dialog = page.dialog
        dialog.content.controls[0].src = profile["profile"]["avatar_path"] or "/static/images/default-avatar.png"
        dialog.content.controls[2].value = username
        dialog.content.controls[4].value = profile["profile"]["full_name"] or "N/A"
        dialog.content.controls[6].value = profile["profile"]["position"] or "N/A"
        dialog.content.controls[8].value = profile["profile"]["department"] or "N/A"
        dialog.content.controls[10].value = profile["profile"]["email"] or "N/A"
        dialog.content.controls[12].value = profile["profile"]["phone_number"] or "N/A"
        dialog.open = True
        page.update()
    else:
        page.snack_bar = ft.SnackBar(content=ft.Text("Profile not found"))
        page.snack_bar.open = True
        page.update()


async def show_group_participants(data: Dict[str, Any], page: ft.Page):
    is_admin_or_creator = data["creator"] == CURRENT_USER or any(
        m["username"] == CURRENT_USER and m["is_admin"] for m in data["members"])
    dialog = page.dialog
    if hasattr(dialog, 'content'):
        dialog.content.controls[0].visible = is_admin_or_creator
        dialog.content.controls[0].value = data["admin_only_messages"]
        dialog.content.controls[0].on_change = lambda e: page.run_task(ws_send, {
            "type": "set_admin_only_messages",
            "group_id": data["group_id"],
            "enabled": e.control.value
        })
        dialog.content.controls[1].visible = is_admin_or_creator
    participants_list.controls = []
    for member in data["members"]:
        status = await fetch_user_status(member["username"])
        profile = await fetch_profile(member["username"])
        avatar = profile["profile"]["avatar_path"] if profile["success"] and profile[
            "profile"]["avatar_path"] else "/static/images/default-avatar.png"
        label = f"{member['username']}{' (Админ)' if member['is_admin'] else ''}{' (Владелец)' if member['username'] == data['creator'] else ''}"
        menu_items = [
            ft.PopupMenuItem(text="Написать", on_click=lambda e,
                             u=member["username"]: select_chat(u, None, u, page))
        ]
        if is_admin_or_creator and member["username"] != CURRENT_USER:
            menu_items.append(
                ft.PopupMenuItem(
                    text="Удалить",
                    text_style=ft.TextStyle(color=ft.Colors.RED_600),
                    on_click=lambda e, u=member["username"]: page.run_task(
                        ws_send, {"type": "remove_group_member", "group_id": data["group_id"], "username": u})
                )
            )
            if data["creator"] == CURRENT_USER:
                if member["is_admin"]:
                    menu_items.append(
                        ft.PopupMenuItem(
                            text="Удалить админ права",
                            on_click=lambda e, u=member["username"]: page.run_task(
                                ws_send, {"type": "revoke_admin", "group_id": data["group_id"], "username": u})
                        )
                    )
                else:
                    menu_items.append(
                        ft.PopupMenuItem(
                            text="Назначить админом",
                            on_click=lambda e, u=member["username"]: page.run_task(
                                ws_send, {"type": "appoint_admin", "group_id": data["group_id"], "username": u})
                        )
                    )
        participants_list.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Image(src=avatar, width=32,
                                 height=32, border_radius=16),
                        ft.Text(label, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            width=12, height=12, bgcolor=ft.Colors.GREEN_500 if status.get("online") else ft.Colors.GREY_500,
                            border_radius=6, border=ft.border.all(2, ft.Colors.WHITE)
                        ),
                        ft.PopupMenuButton(
                            icon=ft.Icons.MORE_VERT, items=menu_items)
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=10,
                border_radius=10
            )
        )
    dialog.open = True
    page.update()


async def add_message(id: str, sender: str, message: str, timestamp: str, is_read: int, file: Optional[str],
                      forwarded_from: Optional[str], group_id: Optional[int], reply_to_id: Optional[str],
                      sticker: bool, page: ft.Page):
    if id and any(m.data.get("message_id") == id for m in messages.controls):
        print(f"Message {id} already exists, skipping")
        return
    profile = await fetch_profile(sender)
    avatar = profile["profile"]["avatar_path"] if profile["success"] and profile[
        "profile"]["avatar_path"] else "/static/images/default-avatar.png"
    is_own_message = sender == CURRENT_USER
    content = []
    if sticker and file:
        content.append(ft.Image(src=file, width=150, height=150,
                       border_radius=10, fit=ft.ImageFit.CONTAIN))
    elif file:
        if file.lower().endswith((".jpg", "jpeg", "png", "gif")):
            content.append(ft.Image(src=file, width=300, border_radius=10))
        else:
            content.append(ft.TextButton(
                content=ft.Row(
                    [ft.Icon(ft.Icons.INSERT_DRIVE_FILE), ft.Text(message)]),
                url=file,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE if is_own_message else ft.Colors.INDIGO_500)
            ))
    else:
        content.append(ft.Text(message))
    reply_content = []
    if reply_to_id:
        reply_msg = next((m for m in messages.controls if m.data.get(
            "message_id") == reply_to_id), None)
        if reply_msg:
            reply_content = [
                ft.Text(reply_msg.data["sender"], size=12,
                        weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                ft.Text(reply_msg.data["message"][:50] + ("..." if len(reply_msg.data["message"]) > 50 else ""),
                        size=14, color=ft.Colors.BLACK)
            ]
    sender_label = [ft.Text(sender, size=12, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.INDIGO_100 if is_own_message else ft.Colors.GREY_600)] if group_id and not is_own_message else []
    forwarded_label = [ft.Text(f"Forwarded from {forwarded_from}", size=12, italic=True,
                               color=ft.Colors.INDIGO_100 if is_own_message else ft.Colors.GREY_500)] if forwarded_from else []
    menu_items = [
        ft.PopupMenuItem(text="Переслать", on_click=lambda e: forward_message(
            {"sender": sender, "message": message, "file": file, "sticker": sticker}, page)),
        ft.PopupMenuItem(text="Ответить", on_click=lambda e: reply_to(
            {"id": id, "sender": sender, "message": message}, page))
    ]
    if sticker:
        menu_items.append(
            ft.PopupMenuItem(text="Добавить в свои стикеры",
                             on_click=lambda e: page.run_task(copy_sticker, file))
        )
    if is_own_message:
        menu_items.append(
            ft.PopupMenuItem(
                text="Удалить",
                text_style=ft.TextStyle(color=ft.Colors.RED_600),
                on_click=lambda e: page.run_task(
                    ws_send, {"type": "delete_message", "message_id": id})
            )
        )
    message_container = ft.Container(
        content=ft.Column(
            sender_label + forwarded_label + ([
                ft.Container(
                    content=ft.Column(reply_content),
                    padding=10,
                    bgcolor=ft.Colors.WHITE,
                    border=ft.border.only(
                        left=ft.border.BorderSide(4, ft.Colors.INDIGO_400)),
                    border_radius=10
                )
            ] if reply_content else []) + content + [
                ft.Row(
                    [
                        ft.Text(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%H:%M"),
                                size=12, color=ft.Colors.INDIGO_100 if is_own_message else ft.Colors.GREY_500),
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.DONE_ALL if is_read else ft.Icons.DONE, color=ft.Colors.INDIGO_200),
                            visible=is_own_message
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT,
                    icon_color=ft.Colors.INDIGO_100 if is_own_message else ft.Colors.GREY_500,
                    items=menu_items,
                    offset=ft.transform.Offset(0, -len(menu_items) * 0.5)
                )
            ],
            spacing=5
        ),
        bgcolor=ft.Colors.INDIGO_500 if is_own_message else ft.Colors.WHITE,
        padding=15,
        border_radius=10,
        width=400
    )
    message_row = ft.Row(
        [
            ft.Image(src=avatar, width=32, height=32,
                     border_radius=16, visible=not is_own_message),
            message_container
        ],
        alignment=ft.MainAxisAlignment.END if is_own_message else ft.MainAxisAlignment.START,
        data={"sender": sender, "is_read": is_read,
              "timestamp": timestamp, "message_id": id, "message": message}
    )
    existing_timestamps = [m.data["timestamp"]
                           for m in messages.controls if m.data.get("timestamp")]
    insert_index = 0
    for i, ts in enumerate(existing_timestamps):
        if timestamp < ts:
            insert_index = i
            break
    else:
        insert_index = len(messages.controls)
    messages.controls.insert(insert_index, message_row)
    messages.scroll_to(offset=-1, duration=0)
    print(
        f"Added message {id} with timestamp {timestamp} at position {'inserted' if insert_index < len(messages.controls)-1 else 'appended'}")
    page.update()


def forward_message(msg: Dict[str, Any], page: ft.Page):
    global message_to_forward
    message_to_forward = msg
    page.dialog = create_forward_modal(page)
    page.dialog.open = True
    page.update()


def reply_to(msg: Dict[str, Any], page: ft.Page):
    global reply_to_message, message_input_container
    reply_to_message = msg
    if hasattr(message_input_container, 'controls') and len(message_input_container.controls) > 0:
        reply_preview = message_input_container.controls[0]
        reply_preview.content.visible = True
        reply_preview.content.controls[0].value = f"Replying to {msg['sender']}: {msg['message'][:20]}..."
        print(f"Set reply to message {msg['id']}")
        page.update()


async def select_chat(recipient: Optional[str], group_id: Optional[int], name: Optional[str], page: ft.Page):
    global current_recipient, current_group_id, is_loading_messages
    if is_loading_messages:
        print("Messages are already loading, skipping select_chat")
        return
    is_loading_messages = True
    current_recipient = recipient
    current_group_id = group_id
    chat_header = page.controls[0].content.controls[1].content.controls[0]
    if recipient:
        profile = await fetch_profile(recipient)
        avatar = profile["profile"]["avatar_path"] if profile["success"] and profile[
            "profile"]["avatar_path"] else "/static/images/default-avatar.png"
        status = await fetch_user_status(recipient)
        status_text = "В сети" if status.get("online", False) else "Нет в сети"
        chat_header.content.controls[0].content = ft.Image(
            src=avatar, width=48, height=48, border_radius=24)
        chat_header.content.controls[1].controls[0].value = recipient
        chat_header.content.controls[1].controls[1].value = status_text
        chat_header.content.controls[2].controls = [
            ft.PopupMenuItem(text="Просмотреть профиль",
                             on_click=lambda e: show_profile_view(recipient, page))
        ]
    else:
        chat_header.content.controls[0].content = ft.Icon(
            ft.Icons.GROUP, color=ft.Colors.GREY_600)
        chat_header.content.controls[1].controls[0].value = name
        chat_header.content.controls[1].controls[1].value = "Групповой чат"
        chat_header.content.controls[2].controls = [
            ft.PopupMenuItem(text="Участники", on_click=lambda e: page.run_task(
                ws_send, {"type": "get_group_members", "group_id": group_id}))
        ]
    messages.controls.clear()
    await ws_send({"type": "load_messages", "recipient": recipient, "group_id": group_id})
    page.update()


async def refresh_chats(page: ft.Page):
    await ws_send({"type": "get_chats"})


async def update_chat_list(chats: List[Dict[str, Any]], page: ft.Page):
    global last_chat_list
    last_chat_list = chats
    chat_list.controls.clear()
    for chat in chats:
        item = ChatListItem(chat, select_chat, page)
        chat_list.controls.append(item)
        page.run_task(item.update_status)
    page.update()


def close_dialog(page: ft.Page, dialog_type: str):
    page.dialog.open = False
    if dialog_type == "emoji":
        emoji_grid.controls.clear()
    elif dialog_type == "sticker":
        sticker_grid.controls.clear()
    page.update()


async def cleanup(page: ft.Page):
    try:
        await client.aclose()
        if sio.connected:
            await sio.disconnect()
    except Exception as e:
        print(f"Cleanup error: {e}")


def main(page: ft.Page):
    global CURRENT_USER
    page.title = "Катюша мессенджер"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = ft.Colors.GREY_100
    page.on_close = cleanup
    global message_input_container
    message_input_container = create_message_input(page)

    page.dialog = create_emoji_modal(page)
    page.dialog = create_sticker_modal(page)
    page.dialog = create_forward_modal(page)
    page.dialog = create_group_modal(page)
    page.dialog = create_participants_modal(page)
    page.dialog = create_profile_edit_modal(page)
    page.dialog = create_profile_view_modal(page)

    def route_change(route):
        page.views.clear()
        if page.route == "/":
            page.views.append(
                ft.View(
                    "/",
                    [create_login_page(page)],
                    bgcolor=ft.Colors.GREY_100,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    vertical_alignment=ft.MainAxisAlignment.CENTER
                )
            )
        elif page.route == "/chat":
            if not CURRENT_USER:
                try:
                    username = page.client_storage.get("username")
                    if username:
                        CURRENT_USER = username
                    else:
                        page.go("/")
                        return
                except Exception as e:
                    print(f"Failed to get username from clientStorage: {e}")
                    page.go("/")
                    return
            page.views.append(
                ft.View(
                    "/chat",
                    [
                        ft.AppBar(
                            leading=ft.Image(
                                src="/static/images/logo.png", width=40, height=40),
                            title=ft.Text("Катюша мессенджер",
                                          weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.INDIGO_600,
                            color=ft.Colors.WHITE,
                            actions=[
                                ft.PopupMenuButton(
                                    items=[
                                        ft.PopupMenuItem(text="Редактировать профиль", on_click=lambda e: (
                                            setattr(
                                                page, 'dialog', create_profile_edit_modal(page)),
                                            setattr(page.dialog, 'open', True),
                                            page.update()
                                        )),
                                        ft.PopupMenuItem(text="Выйти", on_click=lambda e: (
                                            page.client_storage.remove(
                                                "username"),
                                            setattr(page, 'route', "/"),
                                            page.update(),
                                            CURRENT_USER=None
                                        ))
                                    ]
                                )
                            ]
                        ),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Container(
                                        content=chat_list,
                                        width=300,
                                        bgcolor=ft.Colors.WHITE,
                                        border_radius=10,
                                        padding=10
                                    ),
                                    ft.Container(
                                        content=ft.Column(
                                            [
                                                create_chat_header(page),
                                                messages,
                                                message_input_container
                                            ],
                                            expand=True,
                                            spacing=10
                                        ),
                                        expand=True,
                                        bgcolor=ft.Colors.WHITE,
                                        border_radius=10,
                                        padding=10
                                    )
                                ],
                                expand=True,
                                spacing=10
                            ),
                            padding=10,
                            expand=True
                        )
                    ],
                    bgcolor=ft.Colors.GREY_100
                )
            )
            page.run_task(websocket_connect, page)
            page.run_task(refresh_chats, page)
        page.update()

    page.on_route_change = route_change
    page.go(page.route)


if __name__ == "__main__":
    ft.app(target=main, assets_dir="static")
