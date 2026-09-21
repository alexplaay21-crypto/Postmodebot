# -*- coding: utf-8 -*-

import asyncio
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
)

from config import ADMIN_ID
from bot.monitoring import (
    get_data,
    is_blocked,
    set_blocked,
    get_setting,
    set_setting,
    uptime_text,
)

router = Router(name="admin")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"
POSTS_FILE = DATA_DIR / "posts.json"
BACKUPS_DIR = DATA_DIR / "backups"


class AdminForm(StatesGroup):
    search_user = State()
    broadcast_message = State()


def _load(path, default):
    try:
        if not path.exists():
            return default

        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return default


def _users():
    data = _load(USERS_FILE, {})
    return data if isinstance(data, dict) else {}


def _posts():
    data = _load(POSTS_FILE, {})
    return data if isinstance(data, dict) else {}


def _user_ids():
    result = []

    for key in _users():
        try:
            result.append(int(key))
        except (TypeError, ValueError):
            pass

    return sorted(set(result))


def _language_stats():
    result = {}

    for value in _users().values():
        lang = value if isinstance(value, str) else "unknown"
        result[lang] = result.get(lang, 0) + 1

    return sorted(
        result.items(),
        key=lambda x: x[1],
        reverse=True
    )


def _active_chats():
    data = get_data()
    result = []

    for chat in data.get("chats", {}).values():
        status = chat.get("status")

        if status not in ("left", "kicked"):
            result.append(chat)

    return result


def _chat_stats():
    chats = _active_chats()

    channels = sum(
        1 for x in chats
        if x.get("type") == "channel"
    )

    groups = sum(
        1 for x in chats
        if x.get("type") in ("group", "supergroup")
    )

    return channels, groups, len(chats)


def _fmt_time(value):
    if not value:
        return "—"

    try:
        dt = datetime.fromisoformat(value)
        return dt.astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    except Exception:
        return str(value)


def _main_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Dashboard",
                    callback_data="admin:dashboard"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Пользователи",
                    callback_data="admin:users"
                ),
                InlineKeyboardButton(
                    text="🌍 Языки",
                    callback_data="admin:languages"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📡 Каналы / группы",
                    callback_data="admin:chats"
                ),
                InlineKeyboardButton(
                    text="📝 Посты",
                    callback_data="admin:posts"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Рассылка",
                    callback_data="admin:broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📈 Аналитика",
                    callback_data="admin:analytics"
                ),
                InlineKeyboardButton(
                    text="🖥 Мониторинг",
                    callback_data="admin:monitor"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚨 Ошибки",
                    callback_data="admin:errors"
                ),
                InlineKeyboardButton(
                    text="📋 Логи",
                    callback_data="admin:logs"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Блокировки",
                    callback_data="admin:blocked"
                ),
                InlineKeyboardButton(
                    text="💾 Backup",
                    callback_data="admin:backup"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Настройки",
                    callback_data="admin:settings"
                )
            ]
        ]
    )


def _back_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin:dashboard"
                )
            ]
        ]
    )


def _dashboard_text():
    users = _users()
    posts = _posts()
    data = get_data()

    channels, groups, chats = _chat_stats()

    blocked = len(data.get("blocked_users", []))
    errors = len(data.get("errors", []))

    return (
        "<b>🔐 ADMIN DASHBOARD</b>\n\n"
        f"👥 Пользователей: <b>{len(users)}</b>\n"
        f"📝 Сохранённых постов: <b>{len(posts)}</b>\n"
        f"📡 Каналов: <b>{channels}</b>\n"
        f"👥 Групп: <b>{groups}</b>\n"
        f"🤖 Чатов с ботом: <b>{chats}</b>\n"
        f"🚫 Заблокировано: <b>{blocked}</b>\n"
        f"🚨 Ошибок: <b>{errors}</b>\n"
        f"⏱ Uptime: <b>{uptime_text()}</b>"
    )


def _check(user_id):
    return user_id == ADMIN_ID


@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    if not _check(message.from_user.id):
        return

    await state.clear()

    await message.answer(
        _dashboard_text(),
        reply_markup=_main_kb()
    )


@router.callback_query(F.data == "admin:dashboard")
async def admin_dashboard(call: CallbackQuery, state: FSMContext):
    if not _check(call.from_user.id):
        return

    await state.clear()

    await call.message.edit_text(
        _dashboard_text(),
        reply_markup=_main_kb()
    )

    await call.answer()


@router.callback_query(F.data == "admin:users")
async def admin_users(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    data = get_data()
    users = _users()

    active = 0
    now = datetime.now(timezone.utc)

    for item in data.get("users", {}).values():
        try:
            last = datetime.fromisoformat(item["last_seen"])
            if (now - last).total_seconds() <= 86400:
                active += 1
        except Exception:
            pass

    await call.message.edit_text(
        "<b>👥 Пользователи</b>\n\n"
        f"Всего: <b>{len(users)}</b>\n"
        f"Активных за 24ч: <b>{active}</b>\n\n"
        "Для поиска отправь:\n"
        "<code>/find ID</code>\n"
        "или\n"
        "<code>/find @username</code>",
        reply_markup=_back_kb()
    )

    await call.answer()


@router.message(Command("find"))
async def find_user(message: Message):
    if not _check(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "Использование:\n"
            "<code>/find 123456789</code>\n"
            "<code>/find @username</code>"
        )
        return

    query = parts[1].strip().lower()
    data = get_data()

    found = []

    for uid, user in data.get("users", {}).items():
        username = str(user.get("username") or "").lower()
        first_name = str(user.get("first_name") or "").lower()
        last_name = str(user.get("last_name") or "").lower()

        if (
            query == uid.lower()
            or query.lstrip("@") == username.lstrip("@")
            or query in first_name
            or query in last_name
        ):
            found.append((uid, user))

    if not found:
        await message.answer("❌ Пользователь не найден.")
        return

    uid, user = found[0]

    blocked = is_blocked(int(uid))
    chats = user.get("chats", [])

    await message.answer(
        "<b>👤 Пользователь</b>\n\n"
        f"ID: <code>{uid}</code>\n"
        f"Username: @{user.get('username') or '—'}\n"
        f"Имя: {user.get('first_name') or '—'}\n"
        f"Фамилия: {user.get('last_name') or '—'}\n\n"
        f"Первый визит: {_fmt_time(user.get('first_seen'))}\n"
        f"Последний визит: {_fmt_time(user.get('last_seen'))}\n"
        f"Постов создано: {user.get('posts_created', 0)}\n"
        f"Постов отправлено: {user.get('posts_sent', 0)}\n"
        f"Чатов: {len(chats)}\n"
        f"Статус: {'🚫 Заблокирован' if blocked else '✅ Активен'}"
    )


@router.callback_query(F.data == "admin:languages")
async def admin_languages(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    stats = _language_stats()

    lines = ["<b>🌍 Языки пользователей</b>\n"]

    if not stats:
        lines.append("Нет данных.")
    else:
        for lang, count in stats:
            lines.append(
                f"<code>{lang}</code> — <b>{count}</b>"
            )

    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=_back_kb()
    )

    await call.answer()


@router.callback_query(F.data == "admin:chats")
async def admin_chats(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    chats = _active_chats()
    channels, groups, total = _chat_stats()

    lines = [
        "<b>📡 Каналы и группы</b>\n",
        f"Всего: <b>{total}</b>",
        f"📢 Каналов: <b>{channels}</b>",
        f"👥 Групп: <b>{groups}</b>",
        ""
    ]

    for chat in chats[-15:]:
        title = chat.get("title") or chat.get("username") or "Без названия"
        chat_type = chat.get("type", "?")

        lines.append(
            f"• <b>{title}</b> "
            f"<code>{chat.get('chat_id')}</code> "
            f"({chat_type})"
        )

    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=_back_kb()
    )

    await call.answer()


@router.callback_query(F.data == "admin:posts")
async def admin_posts(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    posts = _posts()

    media = {
        "photo": 0,
        "animation": 0,
        "document": 0,
        "text": 0
    }

    for post in posts.values():
        item = post.get("media")

        if not item:
            media["text"] += 1
        else:
            media[item.get("type", "text")] = (
                media.get(item.get("type", "text"), 0) + 1
            )

    await call.message.edit_text(
        "<b>📝 Посты</b>\n\n"
        f"Всего сохранено: <b>{len(posts)}</b>\n\n"
        f"🖼 Фото: {media['photo']}\n"
        f"🎞 GIF: {media['animation']}\n"
        f"📄 Документы: {media['document']}\n"
        f"📝 Только текст: {media['text']}",
        reply_markup=_back_kb()
    )

    await call.answer()


@router.callback_query(F.data == "admin:analytics")
async def admin_analytics(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    data = get_data()

    created = sum(
        int(x.get("posts_created", 0))
        for x in data.get("users", {}).values()
    )

    sent = sum(
        int(x.get("posts_sent", 0))
        for x in data.get("users", {}).values()
    )

    events = len(data.get("events", []))

    await call.message.edit_text(
        "<b>📈 Аналитика</b>\n\n"
        f"👥 Пользователей: <b>{len(_users())}</b>\n"
        f"📝 Создано постов: <b>{created}</b>\n"
        f"📤 Отправлено постов: <b>{sent}</b>\n"
        f"📋 Событий записано: <b>{events}</b>\n"
        f"🚨 Ошибок: <b>{len(data.get('errors', []))}</b>",
        reply_markup=_back_kb()
    )

    await call.answer()


@router.callback_query(F.data == "admin:monitor")
async def admin_monitor(call: CallbackQuery, bot: Bot):
    if not _check(call.from_user.id):
        return

    api_status = "❌ Ошибка"

    try:
        me = await bot.get_me()
        api_status = f"✅ @{me.username}"
    except Exception:
        pass

    data = get_data()

    await call.message.edit_text(
        "<b>🖥 Мониторинг</b>\n\n"
        f"Telegram API: <b>{api_status}</b>\n"
        f"Uptime: <b>{uptime_text()}</b>\n"
        f"Пользователей: <b>{len(_users())}</b>\n"
        f"Чатов: <b>{len(_active_chats())}</b>\n"
        f"Ошибок: <b>{len(data.get('errors', []))}</b>\n"
        f"Событий: <b>{len(data.get('events', []))}</b>",
        reply_markup=_back_kb()
    )

    await call.answer()


@router.callback_query(F.data == "admin:errors")
async def admin_errors(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    errors = get_data().get("errors", [])

    if not errors:
        text = "<b>🚨 Ошибки</b>\n\nОшибок пока нет."
    else:
        lines = ["<b>🚨 Последние ошибки</b>\n"]

        for error in errors[-15:][::-1]:
            lines.append(
                f"• {_fmt_time(error.get('time'))}\n"
                f"<code>{str(error.get('error', ''))[:300]}</code>\n"
            )

        text = "\n".join(lines)

    await call.message.edit_text(
        text,
        reply_markup=_back_kb()
    )

    await call.answer()


@router.callback_query(F.data == "admin:logs")
async def admin_logs(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    events = get_data().get("events", [])

    if not events:
        text = "<b>📋 Логи</b>\n\nЛогов пока нет."
    else:
        lines = ["<b>📋 Последние события</b>\n"]

        for event in events[-20:][::-1]:
            lines.append(
                f"• {_fmt_time(event.get('time'))} "
                f"<b>{event.get('type')}</b>\n"
                f"user=<code>{event.get('user_id') or '-'}</code> "
                f"chat=<code>{event.get('chat_id') or '-'}</code>"
            )

        text = "\n".join(lines)

    await call.message.edit_text(
        text,
        reply_markup=_back_kb()
    )

    await call.answer()


@router.callback_query(F.data == "admin:blocked")
async def admin_blocked(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    blocked = get_data().get("blocked_users", [])

    lines = [
        "<b>🚫 Заблокированные пользователи</b>\n",
        f"Всего: <b>{len(blocked)}</b>",
        ""
    ]

    for uid in blocked[-30:]:
        lines.append(f"• <code>{uid}</code>")

    lines.append("")
    lines.append("Блокировка:")
    lines.append("<code>/block ID</code>")
    lines.append("<code>/unblock ID</code>")

    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=_back_kb()
    )

    await call.answer()


@router.message(Command("block"))
async def block_user(message: Message):
    if not _check(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer("Использование: <code>/block ID</code>")
        return

    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("❌ Некорректный ID.")
        return

    set_blocked(uid, True)

    await message.answer(
        f"🚫 Пользователь <code>{uid}</code> заблокирован."
    )


@router.message(Command("unblock"))
async def unblock_user(message: Message):
    if not _check(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer("Использование: <code>/unblock ID</code>")
        return

    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("❌ Некорректный ID.")
        return

    set_blocked(uid, False)

    await message.answer(
        f"✅ Пользователь <code>{uid}</code> разблокирован."
    )


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if not _check(call.from_user.id):
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Всем",
                    callback_data="admin:broadcast:all"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌍 По языку",
                    callback_data="admin:broadcast:language"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin:dashboard"
                )
            ]
        ]
    )

    await call.message.edit_text(
        "<b>📢 Рассылка</b>\n\n"
        "Выбери аудиторию:",
        reply_markup=kb
    )

    await call.answer()


@router.callback_query(F.data == "admin:broadcast:all")
async def broadcast_all(call: CallbackQuery, state: FSMContext):
    if not _check(call.from_user.id):
        return

    await state.update_data(broadcast_target="all")
    await state.set_state(AdminForm.broadcast_message)

    await call.message.edit_text(
        "<b>📢 Рассылка всем</b>\n\n"
        "Отправь сообщение.\n"
        "Можно текст, фото, видео, GIF или документ.\n\n"
        "Для отмены: /cancel"
    )

    await call.answer()


@router.callback_query(F.data == "admin:broadcast:language")
async def broadcast_language(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    buttons = []

    for lang, count in _language_stats():
        buttons.append([
            InlineKeyboardButton(
                text=f"{lang} — {count}",
                callback_data=f"admin:broadcast:lang:{lang}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin:broadcast"
        )
    ])

    await call.message.edit_text(
        "<b>🌍 Язык рассылки</b>\n\n"
        "Выбери язык:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await call.answer()


@router.callback_query(F.data.startswith("admin:broadcast:lang:"))
async def broadcast_language_selected(
    call: CallbackQuery,
    state: FSMContext
):
    if not _check(call.from_user.id):
        return

    lang = call.data.split(":")[-1]

    await state.update_data(
        broadcast_target=f"lang:{lang}"
    )

    await state.set_state(AdminForm.broadcast_message)

    await call.message.edit_text(
        f"<b>📢 Рассылка: {lang}</b>\n\n"
        "Отправь сообщение.\n\n"
        "Для отмены: /cancel"
    )

    await call.answer()


def _broadcast_users(target):
    users = _users()
    data = get_data()

    blocked = {
        int(x)
        for x in data.get("blocked_users", [])
    }

    result = []

    for uid, value in users.items():
        try:
            user_id = int(uid)
        except ValueError:
            continue

        if user_id in blocked:
            continue

        if target == "all":
            result.append(user_id)

        elif target.startswith("lang:"):
            lang = target.split(":", 1)[1]

            if value == lang:
                result.append(user_id)

    return result


@router.message(AdminForm.broadcast_message, Command("cancel"))
async def broadcast_cancel(message: Message, state: FSMContext):
    if not _check(message.from_user.id):
        return

    await state.clear()

    await message.answer(
        "❌ Рассылка отменена.",
        reply_markup=_main_kb()
    )


@router.message(AdminForm.broadcast_message)
async def broadcast_message(
    message: Message,
    state: FSMContext
):
    if not _check(message.from_user.id):
        return

    data = await state.get_data()
    target = data.get("broadcast_target", "all")

    users = _broadcast_users(target)

    await state.update_data(
        broadcast_chat_id=message.chat.id,
        broadcast_message_id=message.message_id,
        broadcast_count=len(users)
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Отправить",
                    callback_data="admin:broadcast:confirm"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="admin:broadcast:cancel"
                )
            ]
        ]
    )

    await message.answer(
        "<b>📢 Подтверждение</b>\n\n"
        f"Получателей: <b>{len(users)}</b>\n"
        "Заблокированные пользователи исключены.\n\n"
        "Отправить?",
        reply_markup=kb
    )


@router.callback_query(F.data == "admin:broadcast:cancel")
async def broadcast_cancel_button(
    call: CallbackQuery,
    state: FSMContext
):
    if not _check(call.from_user.id):
        return

    await state.clear()

    await call.message.edit_text(
        "❌ Рассылка отменена.",
        reply_markup=_main_kb()
    )

    await call.answer()


@router.callback_query(F.data == "admin:broadcast:confirm")
async def broadcast_confirm(
    call: CallbackQuery,
    state: FSMContext,
    bot: Bot
):
    if not _check(call.from_user.id):
        return

    data = await state.get_data()

    source_chat_id = data.get("broadcast_chat_id")
    source_message_id = data.get("broadcast_message_id")
    target = data.get("broadcast_target", "all")

    if not source_chat_id or not source_message_id:
        await state.clear()
        await call.answer(
            "Сообщение не найдено.",
            show_alert=True
        )
        return

    users = _broadcast_users(target)

    await call.message.edit_text(
        "<b>📢 Рассылка запущена</b>\n\n"
        f"Получателей: <b>{len(users)}</b>"
    )

    success = 0
    failed = 0

    for user_id in users:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=source_chat_id,
                message_id=source_message_id
            )

            success += 1

            await asyncio.sleep(0.05)

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)

            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=source_chat_id,
                    message_id=source_message_id
                )
                success += 1

            except Exception:
                failed += 1

        except Exception:
            failed += 1

    admin_data = get_data()

    admin_data["broadcasts"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "total": len(users),
        "success": success,
        "failed": failed
    })

    admin_data["broadcasts"] = admin_data["broadcasts"][-100:]

    from bot.monitoring import _save

    _save(admin_data)

    await state.clear()

    await call.message.answer(
        "<b>📢 Рассылка завершена</b>\n\n"
        f"👥 Получателей: <b>{len(users)}</b>\n"
        f"✅ Доставлено: <b>{success}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>",
        reply_markup=_main_kb()
    )

    await call.answer()


@router.callback_query(F.data == "admin:backup")
async def backup(call: CallbackQuery, bot: Bot):
    if not _check(call.from_user.id):
        return

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    archive = BACKUPS_DIR / f"backup_{stamp}.zip"

    with zipfile.ZipFile(
        archive,
        "w",
        zipfile.ZIP_DEFLATED
    ) as z:
        for path in DATA_DIR.glob("*.json"):
            z.write(
                path,
                arcname=path.name
            )

    await call.message.answer_document(
        FSInputFile(archive),
        caption=(
            "💾 <b>Backup создан</b>\n\n"
            f"<code>{archive.name}</code>"
        )
    )

    await call.answer()


@router.callback_query(F.data == "admin:settings")
async def admin_settings(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    maintenance = get_setting(
        "maintenance_mode",
        False
    )

    status = "🟢 Включен" if maintenance else "🔴 Выключен"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Переключить maintenance",
                    callback_data="admin:maintenance"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin:dashboard"
                )
            ]
        ]
    )

    await call.message.edit_text(
        "<b>⚙️ Настройки</b>\n\n"
        f"Maintenance mode: <b>{status}</b>\n\n"
        "При включении обычные пользователи "
        "не смогут пользоваться ботом.",
        reply_markup=kb
    )

    await call.answer()


@router.callback_query(F.data == "admin:maintenance")
async def maintenance_toggle(call: CallbackQuery):
    if not _check(call.from_user.id):
        return

    current = get_setting(
        "maintenance_mode",
        False
    )

    set_setting(
        "maintenance_mode",
        not current
    )

    await call.answer(
        "Переключено."
    )

    await admin_settings(call)

