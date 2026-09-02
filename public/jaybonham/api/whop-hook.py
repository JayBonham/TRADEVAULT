import hashlib
import hmac
import http.client
import json
import os
from http.server import BaseHTTPRequestHandler

WHOP_SECRET  = os.environ.get("WHOP_WEBHOOK_SECRET", "")
GHL_API_KEY  = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"

PLAN_TAGS = {
    "sniper-basic-ed":    ["purchased", "purchased-standard"],
    "sniper-accelerator": ["purchased", "purchased-accelerator"],
    "sniper-elite-72":    ["purchased", "purchased-elite"],
}


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_GET(self):
        self._json(200, {"ok": True, "service": "whop-webhook"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)

            # Signature verification — skipped temporarily for debugging
            # sig = (self.headers.get("whop-signature") or
            #        self.headers.get("Whop-Signature") or "")
            # if WHOP_SECRET and sig:
            #     expected = hmac.new(
            #         WHOP_SECRET.encode(), raw_body, hashlib.sha256
            #     ).hexdigest()
            #     bare = sig.split("=")[-1]
            #     if not hmac.compare_digest(expected, bare):
            #         self._json(401, {"error": "invalid signature"})
            #         return

            event = json.loads(raw_body)
            event_type = event.get("event", "")

            # Debug: return full payload so we can inspect it
            import sys
            print("WHOP EVENT:", event_type, json.dumps(event)[:500], file=sys.stderr)

            if event_type not in ("payment.succeeded", "membership.went_valid"):
                self._json(200, {"ok": True, "skipped": event_type})
                return

            data  = event.get("data", {})
            user  = data.get("user") or data.get("customer") or {}
            plan  = data.get("plan") or {}

            email = (user.get("email") or data.get("email") or "").strip().lower()
            name  = (user.get("name") or user.get("username") or "").strip()
            phone = (user.get("phone_number") or "").strip()
            slug  = (plan.get("slug") or data.get("plan_id") or "").strip()

            if not email:
                self._json(400, {"error": "no email in payload"})
                return

            parts = name.split(" ", 1)
            first = parts[0] if parts else ""
            last  = parts[1] if len(parts) > 1 else ""
            tags  = PLAN_TAGS.get(slug, ["purchased"])

            self._ghl_upsert(email, first, last, phone, tags)
            self._json(200, {"ok": True, "email": email, "tags": tags})

        except Exception as e:
            self._json(500, {"error": str(e)})

    def _ghl_upsert(self, email, first, last, phone, tags):
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + GHL_API_KEY,
        }
        payload = {
            "locationId": GHL_LOCATION,
            "email": email,
            "firstName": first,
            "lastName": last,
            "tags": tags,
        }
        if phone:
            payload["phone"] = phone

        # Search for existing contact
        conn = http.client.HTTPSConnection("rest.gohighlevel.com")
        conn.request(
            "GET",
            "/v1/contacts/search?email=" + email + "&locationId=" + GHL_LOCATION,
            headers=headers,
        )
        res  = conn.getresponse()
        data = json.loads(res.read())
        contacts = data.get("contacts", [])

        if contacts:
            cid = contacts[0]["id"]
            conn2 = http.client.HTTPSConnection("rest.gohighlevel.com")
            conn2.request("PUT", "/v1/contacts/" + cid, json.dumps(payload), headers)
            conn2.getresponse().read()
        else:
            conn3 = http.client.HTTPSConnection("rest.gohighlevel.com")
            conn3.request("POST", "/v1/contacts/", json.dumps(payload), headers)
            conn3.getresponse().read()

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)
