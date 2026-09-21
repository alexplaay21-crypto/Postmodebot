import os

# Token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Your numeric Telegram user ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "122"))

# Telegram Stars donation amounts
DONATE_STAR_AMOUNTS = [50, 100, 250, 500, 1000, 2500]
