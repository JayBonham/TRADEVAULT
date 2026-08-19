"""
GET  /api/admin-inbox            → list conversations from Brevo Team Inbox
GET  /api/admin-inbox?id=...     → single conversation with full messages
"""
import http.client
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token

BREVO_API_KEY  = os.environ.get("BREVO_API_KEY", "")
# Brevo Conversations uses a SEPARATE API key — generate it in:
# Brevo → Conversations → Settings → Integrations → API
BREVO_CONV_KEY = os.environ.get("BREVO_CONVERSATIONS_KEY", BREVO_API_KEY)


def _brevo(method, path, body=None):
    conn = http.client.HTTPSConnection("api.brevo.com")
    headers = {"accept": "application/json", "api-key": BREVO_CONV_KEY}
    if body:
        headers["content-type"] = "application/json"
    conn.request(method, path, body, headers)
    res = conn.getresponse()
    raw = res.read().decode()
    print(f"[admin-inbox] Brevo {method} {path} → {res.status}: {raw[:300]}")
    try:
        data = json.loads(raw)
    except Exception:
        data = {"_raw": raw[:300]}
    return res.status, data


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_GET(self):
        if not self._authed():
            return

        query = parse_qs(urlparse(self.path).query)
        conv_id = (query.get("id", [""])[0]).strip()

        if conv_id:
            # Single conversation with messages
            status, data = _brevo("GET", f"/v1/conversations/{conv_id}")
            if status != 200:
                self._json(status, {"ok": False, "error": "Conversation not found", "detail": data})
                return
            self._json(200, {"ok": True, "conversation": data})
        else:
            # List conversations
            page   = (query.get("page", ["1"])[0])
            filter_status = (query.get("status", ["all"])[0])  # open | closed | all
            status, data = _brevo("GET", f"/v1/conversations?status={filter_status}&page={page}&limit=30")
            if status != 200:
                self._json(status, {"ok": False, "error": "Failed to fetch conversations", "detail": data})
                return
            self._json(200, {"ok": True, "conversations": data.get("conversations", []), "total": data.get("total", 0)})

    def _authed(self):
        auth = self.headers.get("Authorization", "")
        if not verify_token(auth.replace("Bearer ", "").strip()):
            self._json(401, {"ok": False, "error": "Unauthorized"})
            return False
        return True

    def _json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(data)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, *args):
        pass
