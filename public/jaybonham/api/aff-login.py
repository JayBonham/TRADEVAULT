import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _aff_db import get_conn, check_password, sign_session

COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        """Login: verify credentials, set jb_aff_session cookie."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")

            email    = (body.get("email") or "").strip().lower()
            password = (body.get("password") or "").strip()

            if not email or not password:
                self._json(400, {"error": "email and password required"})
                return

            conn = get_conn()
            cur  = conn.cursor()
            cur.execute(
                "SELECT id, name, code, password_hash, password_salt, status "
                "FROM jb_affiliates WHERE email = %s",
                (email,)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()

            # Use constant-time check to avoid leaking existence
            if not row or not check_password(password, row[3], row[4]):
                self._json(401, {"error": "invalid email or password"})
                return

            if row[5] == "suspended":
                self._json(403, {"error": "account suspended"})
                return

            token = sign_session(row[0])
            cookie = (
                f"jb_aff_session={token}; Path=/; HttpOnly; SameSite=Lax; "
                f"Max-Age={COOKIE_MAX_AGE}"
            )
            self._json(200, {"ok": True, "name": row[1], "code": row[2]},
                       extra_headers=[("Set-Cookie", cookie)])

        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_DELETE(self):
        """Logout: clear the session cookie."""
        clear = "jb_aff_session=; Path=/; HttpOnly; Max-Age=0"
        self._json(200, {"ok": True}, extra_headers=[("Set-Cookie", clear)])

    def _json(self, status, body, extra_headers=None):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
