import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _aff_db import get_conn


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        """Increment click counter for a ref code. Silent on invalid codes."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")
            code   = (body.get("code") or "").strip().lower()

            if not code:
                self._json(200, {"ok": True})
                return

            conn = get_conn()
            cur  = conn.cursor()
            cur.execute(
                "UPDATE jb_affiliates SET total_clicks = total_clicks + 1 "
                "WHERE code = %s AND status = 'active' RETURNING name",
                (code,)
            )
            row = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()

            name = row[0] if row else None
            self._json(200, {"ok": True, "name": name})

        except Exception as e:
            self._json(200, {"ok": True})  # Never fail tracking calls

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
