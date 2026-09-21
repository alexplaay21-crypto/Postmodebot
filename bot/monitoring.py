# -*- coding: utf-8 -*-

from datetime import datetime, timezone

from aiogram import BaseMiddleware, Router
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    Message,
)

from config import ADMIN_ID
from bot.database import (
    ensure_user,
    get_setting,
    is_blocked,
    record_error,
    record_event,
    set_blocked,
    set_setting,
    track_chat as db_track_chat,
    increment_posts_created,
    increment_posts_sent,
)

router = Router(name="monitoring")

STARTED_AT = datetime.now(timezone.utc)


def _now():
    return datetime.now(timezone.utc).isoformat()


def set_started():
    global STARTED_AT
    STARTED_AT = datetime.now(timezone.utc)


def uptime_seconds():
    return max(
        0,
        int(
            (
                datetime.now(timezone.utc)
                - STARTED_AT
            ).total_seconds()
        ),
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

    ensure_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )


def record_post_created(user_id):
    increment_posts_created(user_id)

    record_event(
        "post_created",
        user_id=user_id,
    )


def record_post_sent(user_id, chat_id=None):
    increment_posts_sent(user_id)

    record_event(
        "post_sent",
        user_id=user_id,
        chat_id=chat_id,
    )


def track_chat(chat, user_id=None, status=None):
    if not chat:
        return

    db_track_chat(
        chat,
        user_id=user_id,
        status=status,
    )


def get_data():
    """
    Compatibility helper for code that still expects
    monitoring.get_data().

    Runtime data is no longer stored in JSON.
    """
    counts = get_counts()

    return {
        "users": {},
        "chats": {},
        "events": [],
        "errors": [],
        "broadcasts": [],
        "blocked_users": [],
        "settings": {
            "maintenance_mode": get_setting(
                "maintenance_mode",
                False,
            ),
        },
        "counts": counts,
    }


@router.my_chat_member()
async def bot_chat_member_update(
    update: ChatMemberUpdated,
):
    status = update.new_chat_member.status

    track_chat(
        update.chat,
        user_id=(
            update.from_user.id
            if update.from_user
            else None
        ),
        status=status,
    )


class ActivityMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler,
        event,
        data,
    ):
        user = getattr(
            event,
            "from_user",
            None,
        )

        if user:
            touch_user(user)

            if (
                user.id != ADMIN_ID
                and is_blocked(user.id)
                and isinstance(
                    event,
                    (Message, CallbackQuery),
                )
            ):
                return None

            if (
                user.id != ADMIN_ID
                and get_setting(
                    "maintenance_mode",
                    False,
                )
                and isinstance(
                    event,
                    (Message, CallbackQuery),
                )
            ):
                return None

        return await handler(event, data)
