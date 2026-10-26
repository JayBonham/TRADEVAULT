import base64
import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler

JWT_SECRET = os.environ.get("ADMIN_JWT_SECRET", "changeme-set-in-vercel")

# Credentials stored as env vars: ADMIN_USER_1 / ADMIN_PASS_1 … ADMIN_USER_6 / ADMIN_PASS_6
USERS = {}
for i in range(1, 7):
    u = os.environ.get(f"ADMIN_USER_{i}", "")
    p = os.environ.get(f"ADMIN_PASS_{i}", "")
    if u and p:
        USERS[u.strip()] = p.strip()  # stored as plaintext in env var (Vercel encrypts at rest)

# Built-in accounts: PBKDF2-SHA256 (salt, hash), 600k iterations. No plaintext in the repo.
HASHED_USERS = {
    "Admin": ("de0778fb5c3215935b3040ab666bb680",
              "53a9ea63aa01fc185c49be490e5513b12ac02ab8de8df184bacda62c023eee27"),
}


def _check(username, password):
    stored = USERS.get(username)
    if stored and hmac.compare_digest(stored, password):
        return True
    h = HASHED_USERS.get(username)
    if h:
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(h[0]), 600000).hex()
        return hmac.compare_digest(calc, h[1])
    return False


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

        if not _check(username, password):
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
