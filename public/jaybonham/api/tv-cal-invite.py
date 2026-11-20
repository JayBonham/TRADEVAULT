"""Webinar calendar invite, triggered from GHL.

GHL workflow: Trigger "Contact Tag added: tv-webinar-registered" (or any tv-webinar-YYYY-MM-DD tag)
  -> Action "Webhook" POST https://jaybonham.com/api/tv-cal-invite   (default contact data is fine)

Also works as a quick test: GET https://jaybonham.com/api/tv-cal-invite?email=you@example.com
Only contacts that exist in GHL with a tv-webinar tag get an invite, so this can't be used to email strangers.
The session comes from their newest tv-webinar-YYYY-MM-DD tag (see MOVED in _tv_invite.py).
"""
import http.client
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _tv_invite as inv  # noqa: E402

GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"


def ghl_contact(email):
    c = http.client.HTTPSConnection("services.leadconnectorhq.com", timeout=8)
    c.request("GET", "/contacts/search/duplicate?" + urllib.parse.urlencode({"locationId": GHL_LOCATION, "email": email}),
              headers={"Authorization": "Bearer " + GHL_API_KEY, "Version": "2021-07-28", "Accept": "application/json"})
    r = c.getresponse()
    data = json.loads(r.read() or b"{}")
    if r.status >= 300:
        inv.log("TV_INVITE_GHL:", r.status, str(data)[:200])
    return data.get("contact") or None


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self._run((q.get("email") or [""])[0], (q.get("name") or [""])[0])

    def do_POST(self):
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 200000)
            b = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            b = {}
        contact = b.get("contact") if isinstance(b.get("contact"), dict) else {}
        email = b.get("email") or contact.get("email") or ""
        name = b.get("full_name") or b.get("first_name") or contact.get("name") or contact.get("firstName") or ""
        self._run(email, name)

    def _run(self, email, name):
        email = (email or "").strip().lower()
        if not email or "@" not in email:
            return self._json(400, {"ok": False, "error": "email required"})
        try:
            c = ghl_contact(email)
        except Exception as e:
            inv.log("TV_INVITE_GHL_ERR:", e)
            return self._json(502, {"ok": False, "error": "could not reach GHL"})
        tags = [t.lower() for t in ((c or {}).get("tags") or [])]
        if not c or not any(t.startswith("tv-webinar-") for t in tags):
            return self._json(404, {"ok": False, "error": "not a webinar registrant in GHL (needs a tv-webinar tag)"})
        name = name or " ".join(x for x in ((c.get("firstName") or ""), (c.get("lastName") or "")) if x)
        day = inv.pick_session(tags)
        ok, info = inv.send(email, name, day)
        self._json(200 if ok else 502, {"ok": ok, "session": day, "info": info})

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())
