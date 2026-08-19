import http.client
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
APPLY_LIST_ID  = int(os.environ.get("BREVO_JB_APPLY_LIST_ID", "5"))
BOOKED_LIST_ID = int(os.environ.get("BREVO_JB_LIST_ID", "3"))


def _brevo_get(path):
    conn = http.client.HTTPSConnection("api.brevo.com")
    conn.request("GET", path, headers={
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
    })
    res = conn.getresponse()
    return json.loads(res.read().decode())


def _get_list_contacts(list_id, limit=100):
    data = _brevo_get(f"/v3/contacts/lists/{list_id}/contacts?limit={limit}&sort=desc")
    contacts = data.get("contacts", [])
    for c in contacts:
        c.setdefault("_list", list_id)
    return contacts


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        if not verify_token(auth.replace("Bearer ", "").strip()):
            self._json(401, {"ok": False, "error": "Unauthorized"})
            return

        query = parse_qs(urlparse(self.path).query)
        stage_filter = query.get("stage", [""])[0]
        search = (query.get("q", [""])[0]).lower()

        # Pull both lists, merge (contacts in list 3 were removed from list 5)
        applicants = _get_list_contacts(APPLY_LIST_ID)
        booked     = _get_list_contacts(BOOKED_LIST_ID)

        # Deduplicate by email (shouldn't overlap, but safety net)
        seen, contacts = set(), []
        for c in booked + applicants:
            email = (c.get("email") or "").lower()
            if email not in seen:
                seen.add(email)
                contacts.append(c)

        # Derive stage from attributes or list
        for c in contacts:
            attrs = c.get("attributes") or {}
            stage = (attrs.get("PIPELINE_STAGE") or "").strip()
            if not stage:
                stage = "Call Booked" if c.get("_list") == BOOKED_LIST_ID else "New Application"
            c["_stage"] = stage

        # Filter
        if stage_filter:
            contacts = [c for c in contacts if c["_stage"] == stage_filter]
        if search:
            contacts = [c for c in contacts if
                search in (c.get("email") or "").lower() or
                search in ((c.get("attributes") or {}).get("FIRSTNAME", "") + " " +
                           (c.get("attributes") or {}).get("LASTNAME", "")).lower()]

        # Sort newest first
        contacts.sort(key=lambda c: c.get("createdAt", ""), reverse=True)

        self._json(200, {"ok": True, "contacts": contacts, "total": len(contacts)})

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
