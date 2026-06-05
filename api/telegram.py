"""
Vercel serverless entry point. One POST per Telegram update.
Loads per-user flow state from Neon, runs the engine, saves state back.
"""

import asyncio
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler

# Vercel adds the project root to sys.path, but insert explicitly to be safe.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot, Update

from bot_engine import EMAIL_RE, FLOW, STEP_INDEX, render, run_flow
from db import load_state, save_lead, save_state

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger("flowbot")

TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
            self.send_response(403)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            asyncio.run(process_update(json.loads(body)))
        except Exception:
            log.exception("Unhandled error processing update")

        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # suppress default request logging


async def process_update(data: dict) -> None:
    bot = Bot(token=TOKEN)
    async with bot:
        update = Update.de_json(data, bot)

        if update.message and update.message.text:
            if update.message.text.startswith("/start"):
                await on_start(bot, update)
            else:
                await on_text(bot, update)
        elif update.callback_query:
            await on_button(bot, update)


async def on_start(bot: Bot, update: Update) -> None:
    chat_id = update.effective_chat.id
    state = {"pos": 0, "data": {}, "awaiting": None, "done": False}
    await run_flow(bot, chat_id, state)
    await save_state(chat_id, state)


async def on_text(bot: Bot, update: Update) -> None:
    chat_id = update.effective_chat.id
    state = await load_state(chat_id)
    awaiting = state.get("awaiting")

    if not awaiting or awaiting.get("mode") != "input":
        return

    step = FLOW[STEP_INDEX[awaiting["step_id"]]]
    value = update.message.text.strip()

    if step.get("validate") == "email" and not EMAIL_RE.match(value):
        await bot.send_message(chat_id, "That doesn't look like a valid email — mind trying again?")
        return

    state["data"][step["save_as"]] = value
    state["awaiting"] = None
    await save_lead(chat_id, update.effective_user.username or "", state["data"])
    await run_flow(bot, chat_id, state)
    await save_state(chat_id, state)


async def on_button(bot: Bot, update: Update) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    state = await load_state(chat_id)

    if not query.data.startswith("goto:"):
        return

    target = query.data.split(":", 1)[1]

    if state.get("awaiting") and state["awaiting"].get("mode") == "buttons":
        state["data"].setdefault("choices", []).append(target)
    state["awaiting"] = None

    if target in STEP_INDEX:
        state["pos"] = STEP_INDEX[target]
        await run_flow(bot, chat_id, state)
    else:
        log.warning("Button points to unknown step id: %s", target)

    await save_state(chat_id, state)
