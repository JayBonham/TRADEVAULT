"""
Flow config API — GET returns the live flow, POST replaces it.
Protected by the same DASHBOARD_TOKEN as the leads endpoint.
"""

import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import load_flow, save_flow

DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "")


class handler(BaseHTTPRequestHandler):
    def _authed(self) -> bool:
        parsed = urlparse(self.path)
        token = parse_qs(parsed.query).get("token", [""])[0]
        bearer = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
        if DASHBOARD_TOKEN and token != DASHBOARD_TOKEN and bearer != DASHBOARD_TOKEN:
            self._json(401, {"error": "Unauthorized"})
            return False
        return True

    def do_GET(self):
        if not self._authed():
            return
        try:
            self._json(200, asyncio.run(load_flow()))
        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_POST(self):
        if not self._authed():
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            flow = json.loads(body)
            if not isinstance(flow, list):
                self._json(400, {"error": "Expected a JSON array"})
                return
            asyncio.run(save_flow(flow))
            self._json(200, {"ok": True})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _json(self, status: int, body) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass
