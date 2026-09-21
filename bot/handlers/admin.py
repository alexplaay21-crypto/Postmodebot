# -*- coding: utf-8 -*-

import asyncio
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import ADMIN_ID
from bot.database import (
    get_counts,
    get_user,
    get_users,
    get_all_user_ids,
    get_posts,
    get_chats,
    get_events,
    get_errors,
    get_blocked_users,
    get_language_stats,
    get_broadcasts,
    search_users,
    get_setting,
    set_setting,
    is_blocked,
    set_blocked,
    add_broadcast,
    get_database_size,
)
from bot.monitoring import uptime_text

router = Router(name="admin")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"


class AdminForm(StatesGroup):
    search_user = State()
    broadcast_message = State()


def _admin(message: Message) -> bool:
    return message.from_user.id == ADMIN_ID


def _callback_admin(call: CallbackQuery) -> bool:
    return call.from_user.id == ADMIN_ID


def _fmt_time(value) -> str:
    if not value:
        return "—"

    if isinstance(value, str):
        return value.replace("T", " ")[:19]

    return str(value)


def _main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="admin:dashboard",
                ),
                InlineKeyboardButton(
                    text="👥 Пользователи",
                    callback_data="admin:users",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Посты",
                    callback_data="admin:posts",
                ),
                InlineKeyboardButton(
                    text="💬 Чаты",
                    callback_data="admin:chats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Языки",
                    callback_data="admin:languages",
                ),
                InlineKeyboardButton(
                    text="📈 Аналитика",
                    callback_data="admin:analytics",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Заблокированные",
                    callback_data="admin:blocked",
                ),
                InlineKeyboardButton(
                    text="⚙️ Настройки",
                    callback_data="admin:settings",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📣 Рассылка",
                    callback_data="admin:broadcast",
                ),
                InlineKeyboardButton(
                    text="💾 Экспорт",
                    callback_data="admin:backup",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Ошибки",
                    callback_data="admin:errors",
                ),
                InlineKeyboardButton(
                    text="📜 События",
                    callback_data="admin:logs",
                ),
            ],
        ]
    )


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin:dashboard",
                )
            ]
        ]
    )


def _dashboard_text() -> str:
    counts = get_counts()
    blocked = len(get_blocked_users())
    db_size = get_database_size()

    maintenance = get_setting("maintenance_mode", False)

    return (
        "🛠 <b>Админ-панель</b>\n\n"
        f"👥 Пользователей: <b>{counts.get('users', 0)}</b>\n"
        f"📢 Сохранённых постов: <b>{counts.get('posts', 0)}</b>\n"
        f"💬 Чатов: <b>{counts.get('chats', 0)}</b>\n"
        f"📜 Событий: <b>{counts.get('events', 0)}</b>\n"
        f"❌ Ошибок: <b>{counts.get('errors', 0)}</b>\n"
        f"🚫 Заблокировано: <b>{blocked}</b>\n"
        f"💾 База данных: <b>{db_size / 1024:.1f} KB</b>\n"
        f"⚙️ Техработы: <b>{'ВКЛ' if maintenance else 'ВЫКЛ'}</b>\n"
        f"⏱ Аптайм: <b>{uptime_text()}</b>"
    )


@router.message(Command("admin"))
async def admin_command(message: Message):
    if not _admin(message):
        return

    await message.answer(
        _dashboard_text(),
        reply_markup=_main_kb(),
    )


@router.callback_query(F.data == "admin:dashboard")
async def admin_dashboard(call: CallbackQuery):
    if not _callback_admin(call):
        return

    await call.message.edit_text(
        _dashboard_text(),
        reply_markup=_main_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:users")
async def admin_users(call: CallbackQuery):
    if not _callback_admin(call):
        return

    users = get_users(limit=20)

    text = "👥 <b>Последние пользователи</b>\n\n"

    if not users:
        text += "Пользователей пока нет."
    else:
        for user in users:
            username = user.get("username") or "без username"
            name = user.get("full_name") or "—"
            uid = user.get("user_id")

            text += (
                f"• <b>{name}</b>\n"
                f"  @{username} | <code>{uid}</code>\n"
                f"  Язык: {user.get('language') or '—'}\n\n"
            )

    await call.message.edit_text(
        text,
        reply_markup=_back_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:languages")
async def admin_languages(call: CallbackQuery):
    if not _callback_admin(call):
        return

    stats = get_language_stats()

    text = "🌐 <b>Языки пользователей</b>\n\n"

    if not stats:
        text += "Данных пока нет."
    else:
        for lang, count in stats.items():
            text += f"• <code>{lang}</code>: {count}\n"

    await call.message.edit_text(
        text,
        reply_markup=_back_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:chats")
async def admin_chats(call: CallbackQuery):
    if not _callback_admin(call):
        return

    chats = get_chats(limit=30)

    text = "💬 <b>Чаты</b>\n\n"

    if not chats:
        text += "Чатов пока нет."
    else:
        for chat in chats:
            title = chat.get("title") or "Без названия"
            chat_id = chat.get("chat_id")

            text += (
                f"• <b>{title}</b>\n"
                f"  <code>{chat_id}</code>\n"
                f"  Тип: {chat.get('chat_type') or '—'}\n\n"
            )

    await call.message.edit_text(
        text,
        reply_markup=_back_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:posts")
async def admin_posts(call: CallbackQuery):
    if not _callback_admin(call):
        return

    posts = get_posts(limit=20)

    text = "📢 <b>Сохранённые посты</b>\n\n"

    if not posts:
        text += "Постов пока нет."
    else:
        for post in posts:
            text += (
                f"• <b>{post.get('name') or 'Без названия'}</b>\n"
                f"  Пользователь: <code>{post.get('user_id')}</code>\n"
                f"  Код: <code>{post.get('code')}</code>\n\n"
            )

    await call.message.edit_text(
        text,
        reply_markup=_back_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:analytics")
async def admin_analytics(call: CallbackQuery):
    if not _callback_admin(call):
        return

    counts = get_counts()
    broadcasts = get_broadcasts(limit=10)

    text = (
        "📈 <b>Аналитика</b>\n\n"
        f"👥 Пользователи: {counts.get('users', 0)}\n"
        f"📢 Посты: {counts.get('posts', 0)}\n"
        f"💬 Чаты: {counts.get('chats', 0)}\n"
        f"📜 События: {counts.get('events', 0)}\n"
        f"❌ Ошибки: {counts.get('errors', 0)}\n\n"
        f"📣 Рассылок: {len(broadcasts)}"
    )

    await call.message.edit_text(
        text,
        reply_markup=_back_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:monitor")
async def admin_monitor(call: CallbackQuery):
    if not _callback_admin(call):
        return

    await call.message.edit_text(
        "🖥 <b>Мониторинг</b>\n\n"
        f"⏱ Аптайм: {uptime_text()}\n"
        f"💾 SQLite: {get_database_size() / 1024:.1f} KB",
        reply_markup=_back_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:errors")
async def admin_errors(call: CallbackQuery):
    if not _callback_admin(call):
        return

    errors = get_errors(limit=20)

    text = "❌ <b>Последние ошибки</b>\n\n"

    if not errors:
        text += "Ошибок нет."
    else:
        for error in errors:
            text += (
                f"• {_fmt_time(error.get('created_at'))}\n"
                f"Пользователь: <code>{error.get('user_id') or '—'}</code>\n"
                f"<code>{str(error.get('error') or '')[:300]}</code>\n\n"
            )

    await call.message.edit_text(
        text,
        reply_markup=_back_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:logs")
async def admin_logs(call: CallbackQuery):
    if not _callback_admin(call):
        return

    events = get_events(limit=30)

    text = "📜 <b>Последние события</b>\n\n"

    if not events:
        text += "Событий нет."
    else:
        for event in events:
            text += (
                f"• {_fmt_time(event.get('created_at'))}\n"
                f"<b>{event.get('event_type') or 'event'}</b>\n"
                f"Пользователь: <code>{event.get('user_id') or '—'}</code>\n\n"
            )

    await call.message.edit_text(
        text,
        reply_markup=_back_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:blocked")
async def admin_blocked(call: CallbackQuery):
    if not _callback_admin(call):
        return

    blocked = get_blocked_users()

    text = "🚫 <b>Заблокированные пользователи</b>\n\n"

    if not blocked:
        text += "Список пуст."
    else:
        for user_id in blocked[:50]:
            text += f"• <code>{user_id}</code>\n"

    await call.message.edit_text(
        text,
        reply_markup=_back_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "admin:settings")
async def admin_settings(call: CallbackQuery):
    if not _callback_admin(call):
        return

    maintenance = get_setting("maintenance_mode", False)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(
                        "🔴 Выключить техработы"
                        if maintenance
                        else "🟢 Включить техработы"
                    ),
                    callback_data="admin:maintenance",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin:dashboard",
                )
            ],
        ]
    )

    await call.message.edit_text(
        "⚙️ <b>Настройки</b>\n\n"
        f"Режим технических работ: "
        f"<b>{'ВКЛ' if maintenance else 'ВЫКЛ'}</b>",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(F.data == "admin:maintenance")
async def admin_maintenance(call: CallbackQuery):
    if not _callback_admin(call):
        return

    current = bool(get_setting("maintenance_mode", False))
    new_value = not current

    set_setting("maintenance_mode", new_value)

    await call.message.edit_text(
        "⚙️ <b>Настройки</b>\n\n"
        f"Режим технических работ: "
        f"<b>{'ВКЛ' if new_value else 'ВЫКЛ'}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=(
                            "🔴 Выключить техработы"
                            if new_value
                            else "🟢 Включить техработы"
                        ),
                        callback_data="admin:maintenance",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="admin:dashboard",
                    )
                ],
            ]
        ),
    )
    await call.answer()


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(call: CallbackQuery, state: FSMContext):
    if not _callback_admin(call):
        return

    await state.set_state(AdminForm.broadcast_message)

    await call.message.answer(
        "📣 <b>Рассылка</b>\n\n"
        "Отправь сообщение, которое нужно разослать всем пользователям.\n\n"
        "Для отмены: /cancel"
    )
    await call.answer()


@router.message(AdminForm.broadcast_message)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if not _admin(message):
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Рассылка отменена.")
        return

    user_ids = get_all_user_ids()

    sent = 0
    failed = 0

    status = await message.answer(
        f"📣 Начинаю рассылку: {len(user_ids)} пользователей..."
    )

    for user_id in user_ids:
        try:
            await message.bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            sent += 1

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)

            try:
                await message.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
                sent += 1
            except Exception:
                failed += 1

        except Exception:
            failed += 1

        await asyncio.sleep(0.04)

    add_broadcast(
        admin_id=message.from_user.id,
        total=len(user_ids),
        sent=sent,
        failed=failed,
    )

    await state.clear()

    await status.edit_text(
        "📣 <b>Рассылка завершена</b>\n\n"
        f"👥 Всего: {len(user_ids)}\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )


@router.callback_query(F.data == "admin:backup")
async def admin_backup(call: CallbackQuery):
    if not _callback_admin(call):
        return

    await call.message.answer(
        "ℹ️ Экспорт SQLite отключён.\n\n"
        "Бот использует PostgreSQL через Railway."
    )
    await call.answer()


@router.message(Command("find"))
async def find_command(message: Message, state: FSMContext):
    if not _admin(message):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "Использование:\n"
            "<code>/find 123456789</code>\n"
            "или\n"
            "<code>/find username</code>"
        )
        return

    query = parts[1].strip()
    users = search_users(query)

    if not users:
        await message.answer("🔎 Пользователь не найден.")
        return

    text = "🔎 <b>Результаты поиска</b>\n\n"

    for user in users[:20]:
        text += (
            f"👤 {user.get('full_name') or '—'}\n"
            f"ID: <code>{user.get('user_id')}</code>\n"
            f"Username: @{user.get('username') or '—'}\n"
            f"Язык: {user.get('language') or '—'}\n\n"
        )

    await message.answer(text)


@router.message(Command("block"))
async def block_command(message: Message):
    if not _admin(message):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2:
        await message.answer("Использование: <code>/block USER_ID</code>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return

    set_blocked(user_id, True)

    await message.answer(
        f"🚫 Пользователь <code>{user_id}</code> заблокирован."
    )


@router.message(Command("unblock"))
async def unblock_command(message: Message):
    if not _admin(message):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2:
        await message.answer("Использование: <code>/unblock USER_ID</code>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return

    set_blocked(user_id, False)

    await message.answer(
        f"✅ Пользователь <code>{user_id}</code> разблокирован."
    )
