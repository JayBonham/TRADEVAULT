import base64
import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler

JWT_SECRET = os.environ.get("ADMIN_JWT_SECRET", "changeme-set-in-vercel")

# Credentials stored as env vars: ADMIN_USER_1 / ADMIN_PASS_1, ADMIN_USER_2 / ADMIN_PASS_2
USERS = {}
for i in (1, 2, 3):
    u = os.environ.get(f"ADMIN_USER_{i}", "")
    p = os.environ.get(f"ADMIN_PASS_{i}", "")
    if u and p:
        USERS[u] = p  # stored as plaintext in env var (Vercel encrypts at rest)


def _make_token(user):
    payload = base64.urlsafe_b64encode(
        json.dumps({"u": user, "exp": int(time.time()) + 86400}).encode()
    ).decode().rstrip("=")
    sig = hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json(400, {"ok": False, "error": "Invalid JSON"})
            return

        username = (body.get("username") or "").strip()
        password = (body.get("password") or "").strip()

        stored = USERS.get(username)
        if not stored or stored != password:
            self._json(401, {"ok": False, "error": "Invalid credentials"})
            return

        token = _make_token(username)
        self._json(200, {"ok": True, "token": token, "user": username})

    def _json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(data)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, *args):
        pass
