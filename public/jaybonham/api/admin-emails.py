"""
GET /api/admin-emails?email=foo@bar.com  → transactional email history from Brevo
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

        # Fetch transactional email history
        enc = quote(email, safe="")
        conn = http.client.HTTPSConnection("api.brevo.com")
        conn.request(
            "GET",
            f"/v3/smtp/emails?email={enc}&limit=25&sort=desc",
            None,
            {"accept": "application/json", "api-key": BREVO_API_KEY},
        )
        res = conn.getresponse()
        try:
            data = json.loads(res.read().decode())
        except Exception:
            data = {}

        emails = data.get("transactionalEmails", [])

        # Normalise: keep only what the UI needs
        out = []
        for e in emails:
            events = e.get("events", [])
            event_names = [ev.get("name", "") for ev in events]
            # Latest status
            if "clicked" in event_names:
                status = "clicked"
            elif "opened" in event_names:
                status = "opened"
            elif "delivered" in event_names:
                status = "delivered"
            elif "softBounce" in event_names or "hardBounce" in event_names:
                status = "bounced"
            elif "spam" in event_names:
                status = "spam"
            else:
                status = "sent"

            out.append({
                "uuid":    e.get("uuid", ""),
                "date":    e.get("date", ""),
                "subject": e.get("subject", "(no subject)"),
                "from":    e.get("from", ""),
                "status":  status,
                "events":  events,
            })

        self._json(200, {"ok": True, "emails": out})

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
