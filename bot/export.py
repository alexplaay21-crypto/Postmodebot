# -*- coding: utf-8 -*-

import asyncio
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile

from config import ADMIN_ID
from bot.database import backup_database, get_setting, set_setting


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"

AUTO_EXPORT_INTERVAL = 7 * 24 * 60 * 60


def _create_archive() -> Path:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    db_file = EXPORTS_DIR / f"bot_{stamp}.db"
    archive = EXPORTS_DIR / f"postmodebot_export_{stamp}.zip"

    backup_database(db_file)

    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as z:
        z.write(db_file, arcname="bot.db")

        z.writestr(
            "export_info.txt",
            (
                "Postmodebot SQLite export\n"
                f"Created: {datetime.now(timezone.utc).isoformat()}\n"
                "Automatic weekly export\n"
            ),
        )

    db_file.unlink(missing_ok=True)

    return archive


async def send_export(bot: Bot, automatic: bool = False) -> bool:
    archive = None

    try:
        archive = await asyncio.to_thread(_create_archive)

        caption = (
            "💾 <b>Автоматический экспорт базы</b>"
            if automatic
            else "💾 <b>Экспорт базы данных</b>"
        )

        await bot.send_document(
            chat_id=ADMIN_ID,
            document=FSInputFile(archive),
            caption=caption,
        )

        if automatic:
            set_setting(
                "last_auto_export",
                datetime.now(timezone.utc).isoformat(),
            )

        return True

    except Exception as e:
        print(f"[EXPORT] error: {e}")
        return False

    finally:
        if archive:
            try:
                archive.unlink(missing_ok=True)
            except Exception:
                pass


async def weekly_export_loop(bot: Bot) -> None:
    while True:
        try:
            last = get_setting("last_auto_export", None)

            now = datetime.now(timezone.utc)

            if last:
                try:
                    last_time = datetime.fromisoformat(last)
                    elapsed = (now - last_time).total_seconds()
                except (ValueError, TypeError):
                    elapsed = AUTO_EXPORT_INTERVAL
            else:
                # Первый автоматический экспорт — через 7 дней
                elapsed = 0

            remaining = AUTO_EXPORT_INTERVAL - elapsed

            if remaining <= 0:
                await send_export(bot, automatic=True)
                continue

            # Просыпаемся не чаще раза в час,
            # а перед самым экспортом — точно в нужное время.
            await asyncio.sleep(
                min(3600, max(60, remaining))
            )

        except asyncio.CancelledError:
            raise

        except Exception as e:
            print(f"[EXPORT LOOP] error: {e}")
            await asyncio.sleep(3600)
