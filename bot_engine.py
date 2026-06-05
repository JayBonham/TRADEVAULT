"""
Flow engine. Accepts a Bot instance, per-user state dict, and the live flow list.
flow_config.py is the fallback seed; the live flow is read from Neon at runtime.
"""

import asyncio
import logging
import re

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction

log = logging.getLogger("flowbot")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def render(text: str, data: dict) -> str:
    class _Safe(dict):
        def __missing__(self, key):
            return "{" + key + "}"
    return text.format_map(_Safe(data))


async def _pause(bot: Bot, chat_id: int, delay: float) -> None:
    if delay and delay > 0:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(delay)


async def run_flow(bot: Bot, chat_id: int, state: dict, flow: list) -> None:
    """Advance through flow steps until the user must act (input / buttons)."""
    step_index = {s["id"]: i for i, s in enumerate(flow)}

    while state["pos"] < len(flow):
        step = flow[state["pos"]]
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
            state["awaiting"] = {"mode": "buttons", "step_id": step["id"]}
            return

        elif kind == "goto":
            state["pos"] = step_index[step["target"]]

        elif kind in ("photo", "video_note"):
            log.info("Skipping media step %r (not configured yet)", step.get("id"))
            state["pos"] += 1

        else:
            log.warning("Unknown step type %r at id=%s", kind, step.get("id"))
            state["pos"] += 1

    if not state.get("done"):
        state["done"] = True
        log.info("Flow complete for chat %s | data=%s", chat_id, state["data"])
