# -*- coding: utf-8 -*-
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from bot.keyboards import donate_amounts_kb, main_menu_kb
from bot.storage import get_user_language
from bot.texts import t
from config import DONATE_STAR_AMOUNTS

router = Router(name="donate")


@router.message(Command("donate"))
async def cmd_donate(message: Message):
    lang = get_user_language(message.from_user.id, "en")
    await message.answer(t(lang, "donate_text"))
    await message.answer(t(lang, "donate_choose_amount"), reply_markup=donate_amounts_kb(lang))


@router.callback_query(F.data == "menu:donate")
async def cb_donate_menu(call: CallbackQuery):
    lang = get_user_language(call.from_user.id, "en")
    await call.message.edit_text(
        t(lang, "donate_text") + "\n\n" + t(lang, "donate_choose_amount"),
        reply_markup=donate_amounts_kb(lang),
    )
    await call.answer()


@router.callback_query(F.data.startswith("donate:"))
async def cb_donate_amount(call: CallbackQuery):
    lang = get_user_language(call.from_user.id, "en")
    try:
        amount = int(call.data.split(":", 1)[1])
    except ValueError:
        await call.answer()
        return
    if amount not in DONATE_STAR_AMOUNTS:
        await call.answer()
        return

    await call.answer()
    await call.message.answer_invoice(
        title=t(lang, "donate_invoice_title"),
        description=t(lang, "donate_invoice_description"),
        payload=f"stars_donate_{amount}",
        provider_token="",  # empty for Telegram Stars (currency XTR)
        currency="XTR",
        prices=[LabeledPrice(label=t(lang, "donate_invoice_label"), amount=amount)],
    )


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_q: PreCheckoutQuery):
    # Nothing to validate — every amount on the picker is a valid donation.
    await pre_checkout_q.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message):
    lang = get_user_language(message.from_user.id, "en")
    amount = message.successful_payment.total_amount
    await message.answer(t(lang, "donate_thanks", amount=amount), reply_markup=main_menu_kb(lang))
