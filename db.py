import json
import os

import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]


async def load_flow() -> list:
    from flow_config import FLOW as _default
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT flow FROM flow_config WHERE id = 1")
            row = await cur.fetchone()
    if row is None:
        await save_flow(_default)
        return _default
    return row[0]


async def save_flow(flow: list) -> None:
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO flow_config (id, flow, updated_at)
                VALUES (1, %s::jsonb, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    flow       = EXCLUDED.flow,
                    updated_at = NOW()
                """,
                (json.dumps(flow),),
            )


async def load_state(chat_id: int) -> dict:
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT pos, data, awaiting, done FROM flow_state WHERE chat_id = %s",
                (chat_id,),
            )
            row = await cur.fetchone()
    if row is None:
        return {"pos": 0, "data": {}, "awaiting": None, "done": False}
    pos, data, awaiting, done = row
    return {"pos": pos, "data": data or {}, "awaiting": awaiting, "done": bool(done)}


async def save_state(chat_id: int, state: dict) -> None:
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO flow_state (chat_id, pos, data, awaiting, done, updated_at)
                VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, NOW())
                ON CONFLICT (chat_id) DO UPDATE SET
                    pos        = EXCLUDED.pos,
                    data       = EXCLUDED.data,
                    awaiting   = EXCLUDED.awaiting,
                    done       = EXCLUDED.done,
                    updated_at = NOW()
                """,
                (
                    chat_id,
                    state["pos"],
                    json.dumps(state["data"]),
                    json.dumps(state["awaiting"]) if state["awaiting"] is not None else None,
                    state["done"],
                ),
            )


async def save_lead(chat_id: int, username: str, data: dict) -> None:
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO leads (chat_id, username, data, updated_at)
                VALUES (%s, %s, %s::jsonb, NOW())
                ON CONFLICT (chat_id) DO UPDATE SET
                    username   = EXCLUDED.username,
                    data       = EXCLUDED.data,
                    updated_at = NOW()
                """,
                (chat_id, username, json.dumps(data)),
            )
