# -*- coding: utf-8 -*-
import html
import logging
import re
from functools import partial

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards import buttons_markup, cancel_kb, confirm_kb, main_menu_kb, skip_cancel_kb
from bot.storage import get_user_language, save_post
from bot.monitoring import record_post_created, record_post_sent, record_error
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

_HTML_TAG_RE = re.compile(
    r"</?(?:b|strong|i|em|u|ins|s|strike|del|code|pre|a|tg-spoiler|blockquote|tg-emoji)\b",
    re.IGNORECASE,
)


def _preserve_custom_emoji(message: Message) -> str:
    """
    Returns the post text as Telegram HTML.

    * Text formatted with Telegram's own tools (bold, italic, spoiler, quote,
      Premium/custom emoji, ...) is converted from entities to HTML.
    * Text where the user typed HTML tags by hand (and used no native
      formatting) is passed through as is - otherwise the tags would be
      escaped and shown literally.
    """
    raw = message.text or message.caption or ""
    entities = message.entities or message.caption_entities

    if not entities and _HTML_TAG_RE.search(raw):
        return raw

    html_text = message.html_text or raw

    # aiogram bug/compatibility: emoji_id -> emoji-id
    html_text = re.sub(
        r'<tg-emoji\s+emoji_id=(["\'])(\d+)\1>',
        r'<tg-emoji emoji-id="\2">',
        html_text,
        flags=re.IGNORECASE,
    )

    return html_text


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


# Real button colors (Bot API 9.4+): style = primary (blue) / success (green) / danger (red).
_STYLE_ALIASES = {
    "blue": "primary", "primary": "primary",
    "green": "success", "success": "success",
    "red": "danger", "danger": "danger",
}


def _normalize_url(raw: str):
    url = raw.strip()
    if url.startswith(("http://", "https://", "tg://")):
        return url
    if url.startswith("@") and len(url) > 1:
        return "https://t.me/" + url[1:]
    if re.match(r"^(?:t\.me|telegram\.me)/", url, re.IGNORECASE):
        return "https://" + url
    if re.match(r"^[\w-]+(?:\.[\w-]+)+(?:[/?#].*)?$", url):
        return "https://" + url
    return None


def parse_buttons(raw: str):
    """
    Button syntax:

        Text - https://site.com | Text 2 - https://site.com/info
        Channel - t.me/test - green

    "|" separates buttons in the same row, a newline starts a new row.
    Optional last field is the color: blue / green / red.

    Returns rows of plain dicts {"text", "url", "style"?} (JSON-serializable,
    so the post can be saved), or None if nothing valid was found.
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

            style = None
            if len(parts) >= 3 and parts[-1].lower() in _STYLE_ALIASES:
                style = _STYLE_ALIASES[parts[-1].lower()]
                url_part = parts[-2]
                text_part = " - ".join(parts[:-2]).strip()
            else:
                url_part = parts[-1]
                text_part = " - ".join(parts[:-1]).strip()

            url = _normalize_url(url_part)
            if not text_part or not url:
                continue

            button = {"text": text_part, "url": url}
            if style:
                button["style"] = style
            row.append(button)

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


async def _send_by_media(senders, media, caption, markup):
    """Dispatches to the right Bot API method based on stored media type."""
    kind = media.get("type") if media else None
    if kind in ("photo", "video", "animation", "document"):
        return await senders[kind](
            media["file_id"], caption=caption or None, parse_mode="HTML", reply_markup=markup,
        )
    return await senders["text"](caption or "-", parse_mode="HTML", reply_markup=markup)


async def _show_preview(message: Message, state: FSMContext):
    """Shows the preview + confirm keyboard. Used after the last step and after any edit."""
    data = await state.get_data()
    lang = data.get("lang", "en")
    target = data.get("target")

    await state.update_data(editing=False)
    await state.set_state(PostForm.confirm)

    await message.answer(t(lang, "post_preview_title"))
    try:
        await _send_by_media(
            {
                "photo": message.answer_photo,
                "video": message.answer_video,
                "animation": message.answer_animation,
                "document": message.answer_document,
                "text": message.answer,
            },
            data.get("media"), data.get("caption", ""), buttons_markup(data.get("buttons")),
        )
    except TelegramBadRequest as e:
        # Bad HTML in the text, bad button, etc. - tell the user instead of hiding it.
        await message.answer(t(lang, "error_generic", description=html.escape(str(e))))

    await message.answer(t(lang, "post_confirm_prompt", target=str(target)), reply_markup=confirm_kb(lang))


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
    if not (message.text or message.caption):
        await message.answer(t(lang, "post_ask_text"), reply_markup=cancel_kb(lang))
        return

    await state.update_data(caption=_preserve_custom_emoji(message))

    if data.get("editing"):
        await _show_preview(message, state)
        return

    record_post_created(message.from_user.id)
    await state.set_state(PostForm.media)
    await message.answer(t(lang, "post_ask_media"), reply_markup=skip_cancel_kb(lang))


@router.message(PostForm.media, F.photo | F.animation | F.video | F.document)
async def receive_media(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    if message.photo:
        media = {"type": "photo", "file_id": message.photo[-1].file_id}
    elif message.animation:
        media = {"type": "animation", "file_id": message.animation.file_id}
    elif message.video:
        media = {"type": "video", "file_id": message.video.file_id}
    else:
        media = {"type": "document", "file_id": message.document.file_id}
    await state.update_data(media=media)

    if data.get("editing"):
        await _show_preview(message, state)
        return

    await state.set_state(PostForm.buttons)
    await message.answer(t(lang, "post_ask_buttons"), reply_markup=skip_cancel_kb(lang))


@router.message(PostForm.media)
async def media_wrong_type(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    await message.answer(t(lang, "post_ask_media"), reply_markup=skip_cancel_kb(lang))


@router.callback_query(PostForm.media, F.data == "post:skip")
async def skip_media(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    if data.get("editing"):
        await call.answer()
        await _show_preview(call.message, state)
        return

    await state.update_data(media=None)
    await state.set_state(PostForm.buttons)
    await call.message.edit_text(t(lang, "post_ask_buttons"), reply_markup=skip_cancel_kb(lang))
    await call.answer()


@router.message(PostForm.buttons)
async def receive_buttons(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    buttons = parse_buttons(message.text)
    if buttons is None:
        await message.answer(t(lang, "post_buttons_invalid"), reply_markup=skip_cancel_kb(lang))
        return

    await state.update_data(buttons=buttons)

    if data.get("editing"):
        await _show_preview(message, state)
        return

    await state.set_state(PostForm.target)
    await message.answer(t(lang, "post_ask_target"), reply_markup=cancel_kb(lang))


@router.callback_query(PostForm.buttons, F.data == "post:skip")
async def skip_buttons(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    if data.get("editing"):
        await call.answer()
        await _show_preview(call.message, state)
        return

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
    await _show_preview(message, state)


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

    try:
        post = save_post(
            user_id=message.from_user.id,
            name=name,
            caption=data.get("caption", ""),
            media=data.get("media"),
            buttons=data.get("buttons"),
            target=data.get("target"),
            entities=data.get("entities"),
        )
    except Exception as e:
        logging.exception("save_post failed")
        await message.answer(
            t(lang, "error_generic", description=html.escape(str(e))),
            reply_markup=cancel_kb(lang),
        )
        return

    await state.clear()

    await message.answer(
        f"{t(lang, 'saved_post_saved')}\n\n"
        f"<b>{html.escape(name)}</b>\n"
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
    markup = buttons_markup(buttons)

    await call.answer()
    await call.message.edit_text(t(lang, "post_sending"))

    try:
        await _send_by_media(
            {
                "photo": partial(bot.send_photo, target),
                "video": partial(bot.send_video, target),
                "animation": partial(bot.send_animation, target),
                "document": partial(bot.send_document, target),
                "text": partial(bot.send_message, target),
            },
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
