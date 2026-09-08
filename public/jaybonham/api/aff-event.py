import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _aff_db import get_conn

VALID_TYPES = {"optin", "call_booked"}


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        """Record an optin or call_booked event. Silent on invalid/missing ref codes."""
        try:
            length     = int(self.headers.get("Content-Length", 0))
            body       = json.loads(self.rfile.read(length) or b"{}")
            event_type = (body.get("type") or "").strip().lower()
            email      = (body.get("email") or "").strip().lower()
            ref_code   = (body.get("ref_code") or "").strip().lower()
            name       = (body.get("name") or "").strip()

            if event_type not in VALID_TYPES or not ref_code:
                self._json(200, {"ok": True, "skipped": True})
                return

            conn = get_conn()
            cur  = conn.cursor()

            # Resolve affiliate
            cur.execute(
                "SELECT id FROM jb_affiliates WHERE code = %s AND status = 'active'",
                (ref_code,)
            )
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                self._json(200, {"ok": True, "skipped": True})
                return

            aff_id = row[0]

            # Dedup: skip if same affiliate + type + email within 24 hours
            if email:
                cur.execute("""
                    SELECT id FROM jb_aff_events
                    WHERE affiliate_id = %s
                      AND event_type   = %s
                      AND visitor_email = %s
                      AND created_at   > NOW() - INTERVAL '24 hours'
                    LIMIT 1
                """, (aff_id, event_type, email))
                if cur.fetchone():
                    cur.close(); conn.close()
                    self._json(200, {"ok": True, "skipped": "duplicate"})
                    return

            cur.execute("""
                INSERT INTO jb_aff_events (affiliate_id, event_type, visitor_email, visitor_name)
                VALUES (%s, %s, %s, %s)
            """, (aff_id, event_type, email or None, name or None))
            conn.commit()
            cur.close()
            conn.close()

            self._json(200, {"ok": True})

        except Exception:
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
