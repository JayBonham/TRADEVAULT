"""
GET  /api/admin-lead?email=foo@bar.com  → full contact detail
PATCH /api/admin-lead                   → { email, stage } update pipeline stage
"""
import http.client
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")


def _brevo(method, path, body=None):
    conn = http.client.HTTPSConnection("api.brevo.com")
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY}
    if body:
        headers["content-type"] = "application/json"
    conn.request(method, path, body, headers)
    res = conn.getresponse()
    return res.status, json.loads(res.read().decode())


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_GET(self):
        if not self._authed():
            return
        query = parse_qs(urlparse(self.path).query)
        email = (query.get("email", [""])[0]).strip()
        if not email:
            self._json(400, {"ok": False, "error": "email required"})
            return

        status, data = _brevo("GET", f"/v3/contacts/{quote(email, safe='')}?includeStatistics=true")
        if status != 200:
            self._json(404, {"ok": False, "error": "Contact not found"})
            return

        self._json(200, {"ok": True, "contact": data})

    def do_PATCH(self):
        if not self._authed():
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json(400, {"ok": False, "error": "Invalid JSON"})
            return

        email = (body.get("email") or "").strip()
        stage = (body.get("stage") or "").strip()
        note  = (body.get("note") or "").strip()

        if not email:
            self._json(400, {"ok": False, "error": "email required"})
            return

        attrs = {}
        if stage:
            attrs["PIPELINE_STAGE"] = stage
        if note:
            attrs["NOTES"] = note  # optional notes attribute

        payload = json.dumps({"attributes": attrs, "updateEnabled": True}).encode()
        status, data = _brevo("PUT", f"/v3/contacts/{quote(email, safe='')}", payload)
        if status not in (200, 204):
            self._json(500, {"ok": False, "error": "Failed to update", "detail": data})
            return

        self._json(200, {"ok": True})

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
        self.send_header("Access-Control-Allow-Methods", "GET, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(data)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, *args):
        pass
