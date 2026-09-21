# -*- coding: utf-8 -*-

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from aiogram import BaseMiddleware, Router
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

from config import ADMIN_ID

router = Router(name="monitoring")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ADMIN_FILE = DATA_DIR / "admin.json"

_lock = Lock()
STARTED_AT = datetime.now(timezone.utc)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _default():
    return {
        "users": {},
        "chats": {},
        "events": [],
        "errors": [],
        "broadcasts": [],
        "blocked_users": [],
        "settings": {
            "maintenance_mode": False
        }
    }


def _load():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not ADMIN_FILE.exists():
        data = _default()
        _save(data)
        return data

    try:
        with ADMIN_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = _default()

    default = _default()

    for key, value in default.items():
        if key not in data:
            data[key] = value

    return data


def _save(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temp = ADMIN_FILE.with_suffix(".tmp")

    with temp.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    temp.replace(ADMIN_FILE)


def set_started():
    global STARTED_AT
    STARTED_AT = datetime.now(timezone.utc)


def uptime_seconds():
    return max(
        0,
        int(
            (
                datetime.now(timezone.utc) - STARTED_AT
            ).total_seconds()
        )
    )


def uptime_text():
    seconds = uptime_seconds()

    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []

    if days:
        parts.append(f"{days}д")

    if hours:
        parts.append(f"{hours}ч")

    if minutes:
        parts.append(f"{minutes}м")

    parts.append(f"{seconds}с")

    return " ".join(parts)


def touch_user(user):
    if not user:
        return

    uid = str(user.id)
    now = _now()

    with _lock:
        data = _load()

        item = data["users"].get(uid)

        if not isinstance(item, dict):
            item = {
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "first_seen": now,
                "last_seen": now,
                "posts_created": 0,
                "posts_sent": 0,
                "chats": []
            }

        item["user_id"] = user.id
        item["username"] = user.username
        item["first_name"] = user.first_name
        item["last_name"] = user.last_name
        item["last_seen"] = now

        data["users"][uid] = item

        _save(data)


def record_event(event_type, user_id=None, chat_id=None, details=None):
    with _lock:
        data = _load()

        data["events"].append({
            "time": _now(),
            "type": event_type,
            "user_id": user_id,
            "chat_id": chat_id,
            "details": details or {}
        })

        data["events"] = data["events"][-500:]

        _save(data)


def record_error(error, user_id=None, details=None):
    with _lock:
        data = _load()

        data["errors"].append({
            "time": _now(),
            "error": str(error),
            "user_id": user_id,
            "details": details or {}
        })

        data["errors"] = data["errors"][-200:]

        _save(data)


def record_post_created(user_id):
    with _lock:
        data = _load()

        uid = str(user_id)

        user = data["users"].setdefault(
            uid,
            {
                "user_id": user_id,
                "posts_created": 0,
                "posts_sent": 0,
                "chats": []
            }
        )

        user["posts_created"] = user.get("posts_created", 0) + 1

        _save(data)

    record_event(
        "post_created",
        user_id=user_id
    )


def record_post_sent(user_id, chat_id=None):
    with _lock:
        data = _load()

        uid = str(user_id)

        user = data["users"].setdefault(
            uid,
            {
                "user_id": user_id,
                "posts_created": 0,
                "posts_sent": 0,
                "chats": []
            }
        )

        user["posts_sent"] = user.get("posts_sent", 0) + 1

        _save(data)

    record_event(
        "post_sent",
        user_id=user_id,
        chat_id=chat_id
    )


def track_chat(chat, user_id=None, status=None):
    if not chat:
        return

    chat_id = str(chat.id)

    with _lock:
        data = _load()

        item = data["chats"].get(chat_id, {})

        item.update({
            "chat_id": chat.id,
            "type": str(chat.type),
            "title": getattr(chat, "title", None),
            "username": getattr(chat, "username", None),
            "last_seen": _now()
        })

        if "first_seen" not in item:
            item["first_seen"] = _now()

        if status is not None:
            item["status"] = status

        if user_id is not None:
            item["last_user_id"] = user_id

            user = data["users"].setdefault(
                str(user_id),
                {
                    "user_id": user_id,
                    "posts_created": 0,
                    "posts_sent": 0,
                    "chats": []
                }
            )

            chats = user.setdefault("chats", [])

            if chat.id not in chats:
                chats.append(chat.id)

        data["chats"][chat_id] = item

        _save(data)

    record_event(
        "chat_updated",
        user_id=user_id,
        chat_id=chat.id,
        details={
            "type": str(chat.type),
            "status": status
        }
    )


def set_blocked(user_id, blocked=True):
    with _lock:
        data = _load()

        blocked_users = set(
            int(x)
            for x in data.get("blocked_users", [])
        )

        if blocked:
            blocked_users.add(int(user_id))
        else:
            blocked_users.discard(int(user_id))

        data["blocked_users"] = sorted(blocked_users)

        _save(data)


def is_blocked(user_id):
    with _lock:
        data = _load()

        return int(user_id) in {
            int(x)
            for x in data.get("blocked_users", [])
        }


def get_setting(name, default=None):
    with _lock:
        data = _load()

        return data.get(
            "settings",
            {}
        ).get(name, default)


def set_setting(name, value):
    with _lock:
        data = _load()

        data.setdefault("settings", {})[name] = value

        _save(data)


def get_data():
    with _lock:
        return _load()


@router.my_chat_member()
async def bot_chat_member_update(update: ChatMemberUpdated):
    status = update.new_chat_member.status

    track_chat(
        update.chat,
        user_id=update.from_user.id if update.from_user else None,
        status=status
    )


class ActivityMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)

        if user:
            touch_user(user)

            if (
                user.id != ADMIN_ID
                and is_blocked(user.id)
                and isinstance(event, (Message, CallbackQuery))
            ):
                return None

            if (
                user.id != ADMIN_ID
                and get_setting("maintenance_mode", False)
                and isinstance(event, (Message, CallbackQuery))
            ):
                return None

        return await handler(event, data)
