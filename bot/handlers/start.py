# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.texts import t, detect_language
from bot.storage import get_user_language, set_user_language
from bot.keyboards import main_menu_kb

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    # detected = detect_language(message.from_user.language_code)
    lang = get_user_language(message.from_user.id, "en")
    # First time we see this user: remember the auto-detected language.
    set_user_language(message.from_user.id, lang)
    await message.answer(t(lang, "start_welcome"), reply_markup=main_menu_kb(lang))


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    lang = get_user_language(message.from_user.id, "en")
    await message.answer(t(lang, "menu_title"), reply_markup=main_menu_kb(lang))


@router.callback_query(F.data == "menu:back")
async def cb_back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = get_user_language(call.from_user.id, "en")
    await call.message.edit_text(t(lang, "menu_title"), reply_markup=main_menu_kb(lang))
    await call.answer()


@router.callback_query(F.data == "menu:help")
async def cb_help(call: CallbackQuery):
    lang = get_user_language(call.from_user.id, "en")
    await call.message.edit_text(t(lang, "help_text"), reply_markup=main_menu_kb(lang))
    await call.answer()
