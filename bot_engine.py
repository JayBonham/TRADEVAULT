"""
Flow engine. Handlers accept a Bot instance + a plain state dict loaded from DB.
flow_config.py drives all behaviour; this file should rarely need editing.
"""

import asyncio
import logging
import re

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction

from flow_config import FLOW

log = logging.getLogger("flowbot")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STEP_INDEX = {step["id"]: i for i, step in enumerate(FLOW)}


def render(text: str, data: dict) -> str:
    class _Safe(dict):
        def __missing__(self, key):
            return "{" + key + "}"
    return text.format_map(_Safe(data))


async def _pause(bot: Bot, chat_id: int, delay: float) -> None:
    if delay and delay > 0:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(delay)


async def run_flow(bot: Bot, chat_id: int, state: dict) -> None:
    """Advance through FLOW steps until the user must act (input / buttons)."""
    while state["pos"] < len(FLOW):
        step = FLOW[state["pos"]]
        kind = step["type"]

        if kind == "message":
            await _pause(bot, chat_id, step.get("delay", 0.8))
            await bot.send_message(chat_id, render(step["text"], state["data"]))
            state["pos"] += 1

        elif kind == "input":
            await _pause(bot, chat_id, step.get("delay", 0.8))
            await bot.send_message(chat_id, render(step["prompt"], state["data"]))
            state["awaiting"] = {"mode": "input", "step_id": step["id"]}
            state["pos"] += 1
            return

        elif kind == "buttons":
            await _pause(bot, chat_id, step.get("delay", 0.6))
            keyboard = [
                [InlineKeyboardButton(opt["label"], callback_data=f"goto:{opt['goto']}")]
                for opt in step["options"]
            ]
            await bot.send_message(
                chat_id,
                render(step["text"], state["data"]),
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            state["awaiting"] = {"mode": "buttons"}
            return

        elif kind == "goto":
            state["pos"] = STEP_INDEX[step["target"]]

        elif kind in ("photo", "video_note"):
            log.info("Skipping media step %r (not configured yet)", step.get("id"))
            state["pos"] += 1

        else:
            log.warning("Unknown step type %r at id=%s", kind, step.get("id"))
            state["pos"] += 1

    if not state.get("done"):
        state["done"] = True
        log.info("Flow complete for chat %s | data=%s", chat_id, state["data"])
