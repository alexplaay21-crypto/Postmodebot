# -*- coding: utf-8 -*-
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from bot.handlers import donate, language, post, start


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if BOT_TOKEN == "YOUR_BOT_TOKEN":
        raise SystemExit("Set BOT_TOKEN in config.py first (get one from @BotFather).")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(language.router)
    dp.include_router(donate.router)
    dp.include_router(post.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
