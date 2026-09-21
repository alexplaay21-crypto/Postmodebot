# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.texts import t, SUPPORTED_LANGUAGES
from config import DONATE_STAR_AMOUNTS


def main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "menu_create_post"), callback_data="menu:create")],
        [InlineKeyboardButton(text=t(lang, "menu_saved_posts"), callback_data="menu:saved")],
        [InlineKeyboardButton(text=t(lang, "menu_language"), callback_data="menu:language")],
        [InlineKeyboardButton(text=t(lang, "menu_donate"), callback_data="menu:donate")],
        [InlineKeyboardButton(text=t(lang, "menu_help"), callback_data="menu:help")],
    ])


def language_kb() -> InlineKeyboardMarkup:
    """Two languages per row, in the fixed order they were introduced."""
    rows, row = [], []
    for code, label in SUPPORTED_LANGUAGES.items():
        row.append(InlineKeyboardButton(text=label, callback_data=f"lang:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="post:cancel")],
    ])


def skip_cancel_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_skip"), callback_data="post:skip")],
        [InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="post:cancel")],
    ])


def confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t(lang, "btn_edit_text"),
                callback_data="post:edit:text",
            )
        ],
        [
            InlineKeyboardButton(
                text=t(lang, "btn_edit_media"),
                callback_data="post:edit:media",
            )
        ],
        [
            InlineKeyboardButton(
                text=t(lang, "btn_edit_buttons"),
                callback_data="post:edit:buttons",
            )
        ],
        [
            InlineKeyboardButton(
                text=t(lang, "btn_edit_target"),
                callback_data="post:edit:target",
            )
        ],
        [
            InlineKeyboardButton(
                text=t(lang, "btn_save_post"),
                callback_data="post:save",
            )
        ],
        [
            InlineKeyboardButton(
                text=t(lang, "btn_confirm_send"),
                callback_data="post:send",
            )
        ],
        [
            InlineKeyboardButton(
                text=t(lang, "btn_cancel"),
                callback_data="post:cancel",
            )
        ],
    ])

def donate_amounts_kb(lang: str) -> InlineKeyboardMarkup:
    """Two amounts per row, e.g. [50⭐ 100⭐] [250⭐ 500⭐] [1000⭐ 2500⭐] + back."""
    rows, row = [], []
    for amount in DONATE_STAR_AMOUNTS:
        row.append(InlineKeyboardButton(text=f"⭐ {amount}", callback_data=f"donate:{amount}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def buttons_markup(buttons) -> InlineKeyboardMarkup | None:
    """
    Builds a keyboard from stored button dicts:
    [[{"text": "...", "url": "...", "style": "primary|success|danger"}, ...], ...]
    Plain dicts (not aiogram objects) so they can be saved to the database as JSON.
    """
    rows = []
    for row in buttons or []:
        built = []
        for b in row:
            if not isinstance(b, dict) or not b.get("text") or not b.get("url"):
                continue
            kwargs = {"text": b["text"], "url": b["url"]}
            if b.get("style"):
                kwargs["style"] = b["style"]
            built.append(InlineKeyboardButton(**kwargs))
        if built:
            rows.append(built)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
