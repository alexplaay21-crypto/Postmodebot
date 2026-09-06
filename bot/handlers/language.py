# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.texts import t, SUPPORTED_LANGUAGES
from bot.storage import get_user_language, set_user_language
from bot.keyboards import language_kb, main_menu_kb

router = Router(name="language")


@router.message(Command("language"))
async def cmd_language(message: Message):
    lang = get_user_language(message.from_user.id, "en")
    await message.answer(t(lang, "choose_language"), reply_markup=language_kb())


@router.callback_query(F.data == "menu:language")
async def cb_language_menu(call: CallbackQuery):
    lang = get_user_language(call.from_user.id, "en")
    await call.message.edit_text(t(lang, "choose_language"), reply_markup=language_kb())
    await call.answer()


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_language(call: CallbackQuery):
    code = call.data.split(":", 1)[1]
    if code not in SUPPORTED_LANGUAGES:
        await call.answer()
        return
    set_user_language(call.from_user.id, code)
    await call.message.edit_text(t(code, "language_set"), reply_markup=main_menu_kb(code))
    await call.answer()
