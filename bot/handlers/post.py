# -*- coding: utf-8 -*-
import re

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.keyboards import cancel_kb, confirm_kb, main_menu_kb, skip_cancel_kb
from bot.storage import get_user_language, save_post
from bot.monitoring import record_post_created, record_post_sent, track_chat, record_error
from bot.texts import t

router = Router(name="post")


class PostForm(StatesGroup):
    text = State()
    media = State()
    buttons = State()
    target = State()
    confirm = State()
    save_name = State()


# ---------- helpers ----------

def _preserve_custom_emoji(message: Message) -> str:
    """
    Return Telegram HTML while preserving Premium/Custom Emoji.

    aiogram versions with the custom_emoji HTML bug may produce
    emoji_id="..." instead of the Telegram-required emoji-id="...".
    Normalize it before sending.
    """
    html = message.html_text or message.text or message.caption or ""

    # aiogram bug/compatibility: emoji_id -> emoji-id
    html = re.sub(
        r'<tg-emoji\s+emoji_id=(["\'])(\d+)\1>',
        r'<tg-emoji emoji-id="\\2">',
        html,
        flags=re.IGNORECASE,
    )

    return html


def normalize_chat_target(raw: str):
    """
    Accepts https://t.me/name, t.me/name, @name, bare name, or a numeric chat id
    (e.g. -1001234567890) and returns either '@name' or an int.
    """
    s = (raw or "").strip()

    m = re.search(r"(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]+)", s)
    if m:
        return "@" + m.group(1)

    if s.startswith("@"):
        name = re.sub(r"[^A-Za-z0-9_]", "", s[1:])
        return "@" + name if name else None

    if re.fullmatch(r"-?\d+", s):
        return int(s)

    name = re.sub(r"[^A-Za-z0-9_]", "", s)
    return "@" + name if name else None


# Telegram's Bot API has no real color for inline buttons — this dot is a
# purely visual stand-in, prepended to the button's own label text.
_BUTTON_COLOR_EMOJI = {
    "blue": "🔵",
    "green": "🟢",
    "red": "🔴",
}


def parse_buttons(raw: str):
    """
    Button syntax:

        Купить - https://site.com | Подробнее - https://site.com/info | Канал - https://t.me/test

    "|" separates buttons in the same row.
    A newline starts a new row.

    Optional color suffix is accepted:
        Купить - https://site.com - green
        Подробнее - https://site.com - blue
        Канал - https://site.com - red

    Telegram does not support actual inline-button colors, so the color
    value is accepted for future/custom handling but is not displayed
    inside the button text.
    """
    rows = []

    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue

        row = []

        for item in line.split("|"):
            item = item.strip()
            if not item or " - " not in item:
                continue

            parts = [p.strip() for p in item.split(" - ")]

            color = None
            if len(parts) >= 3 and parts[-1].lower() in {"green", "blue", "red"}:
                color = parts[-1].lower()
                url_part = parts[-2]
                text_part = " - ".join(parts[:-2]).strip()
            else:
                url_part = parts[-1]
                text_part = " - ".join(parts[:-1]).strip()

            if not text_part:
                continue

            if not url_part.startswith(("http://", "https://", "tg://")):
                continue

            row.append(
                InlineKeyboardButton(
                    text=text_part,
                    url=url_part,
                )
            )

        if row:
            rows.append(row)

    return rows or None


def _explain_error(lang: str, exc: Exception) -> str:
    if isinstance(exc, TelegramForbiddenError):
        return t(lang, "error_forbidden")
    if isinstance(exc, TelegramBadRequest):
        desc = str(exc)
        low = desc.lower()
        if "chat not found" in low:
            return t(lang, "error_chat_not_found")
        if "file is too big" in low:
            return t(lang, "error_file_too_big")
        return t(lang, "error_generic", description=desc)
    return t(lang, "error_generic", description=str(exc))


async def _send_by_media(send_photo, send_animation, send_document, send_text, media, caption, markup):
    """Dispatches to the right Bot API method based on stored media type."""
    if media and media["type"] == "photo":
        return await send_photo(media["file_id"], caption=caption, parse_mode="HTML", reply_markup=markup)
    if media and media["type"] == "animation":
        return await send_animation(media["file_id"], caption=caption, parse_mode="HTML", reply_markup=markup)
    if media and media["type"] == "document":
        return await send_document(media["file_id"], caption=caption, parse_mode="HTML", reply_markup=markup)
    return await send_text(caption or "-", parse_mode="HTML", reply_markup=markup)


# ---------- flow ----------

@router.callback_query(F.data == "menu:create")
async def start_post(call: CallbackQuery, state: FSMContext):
    lang = get_user_language(call.from_user.id, "en")
    await state.clear()
    await state.update_data(lang=lang)
    await state.set_state(PostForm.text)
    await call.message.edit_text(t(lang, "post_ask_text"), reply_markup=cancel_kb(lang))
    await call.answer()


@router.message(PostForm.text)
async def receive_text(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    caption = _preserve_custom_emoji(message)
    await state.update_data(caption=caption)
    await state.set_state(PostForm.media)
    await message.answer(t(lang, "post_ask_media"), reply_markup=skip_cancel_kb(lang))


@router.message(PostForm.media, F.photo | F.animation | F.document)
async def receive_media(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    if message.photo:
        media = {"type": "photo", "file_id": message.photo[-1].file_id}
    elif message.animation:
        media = {"type": "animation", "file_id": message.animation.file_id}
    else:
        media = {"type": "document", "file_id": message.document.file_id}
    await state.update_data(media=media)
    await state.set_state(PostForm.buttons)
    await message.answer(t(lang, "post_ask_buttons"), reply_markup=skip_cancel_kb(lang))


@router.callback_query(PostForm.media, F.data == "post:skip")
async def skip_media(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    if not data.get("editing"):
        await state.update_data(media=None)

    await state.set_state(PostForm.buttons)
    await call.message.edit_text(t(lang, "post_ask_buttons"), reply_markup=skip_cancel_kb(lang))
    await call.answer()


@router.message(PostForm.buttons)
async def receive_buttons(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    await state.update_data(buttons=parse_buttons(message.text))
    await state.set_state(PostForm.target)
    await message.answer(t(lang, "post_ask_target"), reply_markup=cancel_kb(lang))


@router.callback_query(PostForm.buttons, F.data == "post:skip")
async def skip_buttons(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    if not data.get("editing"):
        await state.update_data(buttons=None)

    await state.set_state(PostForm.target)
    await call.message.edit_text(t(lang, "post_ask_target"), reply_markup=cancel_kb(lang))
    await call.answer()


@router.message(PostForm.target)
async def receive_target(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")

    target = normalize_chat_target(message.text)
    if target is None:
        await message.answer(t(lang, "post_target_invalid"), reply_markup=cancel_kb(lang))
        return

    await state.update_data(target=target)
    await state.set_state(PostForm.confirm)

    caption = data.get("caption", "")
    media = data.get("media")
    buttons = data.get("buttons")
    markup = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    await message.answer(t(lang, "post_preview_title"))
    try:
        await _send_by_media(
            message.answer_photo, message.answer_animation, message.answer_document, message.answer,
            media, caption, markup,
        )
    except TelegramBadRequest:
        # Fall back to plain text if HTML parsing of the caption fails during preview.
        await message.answer(caption or "-", reply_markup=markup)

    await message.answer(t(lang, "post_confirm_prompt", target=str(target)), reply_markup=confirm_kb(lang))


@router.callback_query(PostForm.confirm, F.data == "post:edit:text")
async def edit_post_text(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")

    await state.update_data(editing=True)
    await state.set_state(PostForm.text)
    await call.message.edit_text(
        t(lang, "post_ask_text"),
        reply_markup=cancel_kb(lang),
    )
    await call.answer()


@router.callback_query(PostForm.confirm, F.data == "post:edit:media")
async def edit_post_media(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")

    await state.update_data(editing=True)
    await state.set_state(PostForm.media)
    await call.message.edit_text(
        t(lang, "post_ask_media"),
        reply_markup=skip_cancel_kb(lang),
    )
    await call.answer()


@router.callback_query(PostForm.confirm, F.data == "post:edit:buttons")
async def edit_post_buttons(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")

    await state.update_data(editing=True)
    await state.set_state(PostForm.buttons)
    await call.message.edit_text(
        t(lang, "post_ask_buttons"),
        reply_markup=skip_cancel_kb(lang),
    )
    await call.answer()


@router.callback_query(PostForm.confirm, F.data == "post:edit:target")
async def edit_post_target(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")

    await state.update_data(editing=True)
    await state.set_state(PostForm.target)
    await call.message.edit_text(
        t(lang, "post_ask_target"),
        reply_markup=cancel_kb(lang),
    )
    await call.answer()


@router.callback_query(PostForm.confirm, F.data == "post:save")
async def save_post_start(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")

    await state.set_state(PostForm.save_name)

    await call.message.edit_text(
        t(lang, "saved_post_name_prompt"),
        reply_markup=cancel_kb(lang),
    )
    await call.answer()


@router.message(PostForm.save_name)
async def save_post_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")

    name = (message.text or "").strip()

    if not name:
        await message.answer(
            t(lang, "saved_post_name_empty"),
            reply_markup=cancel_kb(lang),
        )
        return

    post = save_post(
        user_id=message.from_user.id,
        name=name,
        caption=data.get("caption", ""),
        media=data.get("media"),
        buttons=data.get("buttons"),
        target=data.get("target"),
        entities=data.get("entities"),
    )

    await state.clear()

    await message.answer(
        f"{t(lang, 'saved_post_saved')}\n\n"
        f"<b>{name}</b>\n"
        f"<code>{post['code']}</code>",
        reply_markup=main_menu_kb(lang),
    )


@router.callback_query(PostForm.confirm, F.data == "post:send")
async def send_post(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get("lang", "en")
    caption = data.get("caption", "")
    media = data.get("media")
    buttons = data.get("buttons")
    target = data.get("target")
    markup = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    await call.answer()
    await call.message.edit_text(t(lang, "post_sending"))

    try:
        await _send_by_media(
            lambda *a, **kw: bot.send_photo(target, *a, **kw),
            lambda *a, **kw: bot.send_animation(target, *a, **kw),
            lambda *a, **kw: bot.send_document(target, *a, **kw),
            lambda *a, **kw: bot.send_message(target, *a, **kw),
            media, caption, markup,
        )
        record_post_sent(
            call.from_user.id,
            chat_id=target if isinstance(target, int) else None,
        )

        await call.message.answer(
            t(lang, "post_success", target=str(target)),
            reply_markup=main_menu_kb(lang),
        )
    except TelegramAPIError as e:
        record_error(
            e,
            user_id=call.from_user.id,
            details={
                "target": str(target),
            },
        )

        tip = _explain_error(lang, e)
        await call.message.answer(t(lang, "post_failed", error=tip), reply_markup=main_menu_kb(lang))

    await state.clear()


@router.callback_query(F.data == "post:cancel")
async def cancel_post(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang") or get_user_language(call.from_user.id, "en")
    await state.clear()
    await call.message.edit_text(t(lang, "post_cancelled"), reply_markup=main_menu_kb(lang))
    await call.answer()
