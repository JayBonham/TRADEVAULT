"""
One-time script: register your Vercel URL as the Telegram webhook.

Usage:
    TELEGRAM_TOKEN=xxx WEBHOOK_SECRET=yyy python scripts/set_webhook.py https://<project>.vercel.app/api/telegram

Or if you have a .env file:
    export $(cat .env | xargs) && python scripts/set_webhook.py https://<project>.vercel.app/api/telegram
"""

import asyncio
import os
import sys

from telegram import Bot


async def main() -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        sys.exit("Error: TELEGRAM_TOKEN not set in environment.")

    if len(sys.argv) < 2:
        sys.exit(
            "Usage: python scripts/set_webhook.py https://<project>.vercel.app/api/telegram"
        )

    url = sys.argv[1]
    secret = os.environ.get("WEBHOOK_SECRET") or None

    bot = Bot(token=token)
    async with bot:
        ok = await bot.set_webhook(
            url=url,
            secret_token=secret,
            allowed_updates=["message", "callback_query"],
        )
        print(f"set_webhook → {ok}")
        info = await bot.get_webhook_info()
        print(f"URL             : {info.url}")
        print(f"Pending updates : {info.pending_update_count}")
        if info.last_error_message:
            print(f"Last error      : {info.last_error_message}")


asyncio.run(main())
