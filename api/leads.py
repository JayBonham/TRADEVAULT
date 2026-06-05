"""
Dashboard API — returns all leads + flow state as JSON.
Requires ?token=DASHBOARD_TOKEN or Authorization: Bearer <token>.
"""

import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]
DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        token = params.get("token", [""])[0]
        bearer = self.headers.get("Authorization", "").replace("Bearer ", "").strip()

        if DASHBOARD_TOKEN and token != DASHBOARD_TOKEN and bearer != DASHBOARD_TOKEN:
            self._json(401, {"error": "Unauthorized"})
            return

        try:
            data = asyncio.run(fetch_leads())
            self._json(200, data)
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, status: int, body) -> None:
        payload = json.dumps(body, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


async def fetch_leads():
    async with await psycopg.AsyncConnection.connect(DATABASE_URL, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    l.chat_id,
                    l.username,
                    l.data        AS lead_data,
                    l.updated_at,
                    fs.done,
                    fs.data       AS state_data
                FROM leads l
                LEFT JOIN flow_state fs ON l.chat_id = fs.chat_id
                ORDER BY l.updated_at DESC
            """)
            rows = await cur.fetchall()

    result = []
    for row in rows:
        lead_data  = row["lead_data"]  or {}
        state_data = row["state_data"] or {}
        merged     = {**state_data, **lead_data}

        result.append({
            "chat_id":    row["chat_id"],
            "username":   row["username"],
            "full_name":  merged.get("full_name", ""),
            "email":      merged.get("email", ""),
            "choices":    merged.get("choices", []),
            "done":       bool(row["done"]),
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        })

    return result
