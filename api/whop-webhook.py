import hashlib
import hmac
import http.client
import json
import os
from http.server import BaseHTTPRequestHandler

WHOP_SECRET  = os.environ.get("WHOP_WEBHOOK_SECRET", "")
GHL_API_KEY  = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"

# Map Whop plan slugs → GHL tags
PLAN_TAGS = {
    "sniper-basic-ed":   ["purchased", "purchased-standard"],
    "sniper-accelerator": ["purchased", "purchased-accelerator"],
    "sniper-elite-72":   ["purchased", "purchased-elite"],
}


def verify_signature(secret: str, body: bytes, header: str) -> bool:
    """Whop signs with HMAC-SHA256. Header value is the hex digest."""
    if not secret or not header:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    # Header may be bare hex or prefixed "sha256=..."
    raw = header.split("=")[-1]
    return hmac.compare_digest(expected, raw)


def ghl_upsert_contact(email: str, first: str, last: str, phone: str, tags: list):
    """Create or update contact in GHL, then add tags."""
    conn = http.client.HTTPSConnection("rest.gohighlevel.com")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GHL_API_KEY}",
    }

    # Search for existing contact by email
    conn.request("GET", f"/v1/contacts/search?email={email}&locationId={GHL_LOCATION}", headers=headers)
    res = conn.getresponse()
    data = json.loads(res.read())
    contacts = data.get("contacts", [])

    payload = {
        "locationId": GHL_LOCATION,
        "email": email,
        "firstName": first,
        "lastName": last,
        "tags": tags,
    }
    if phone:
        payload["phone"] = phone

    if contacts:
        # Update existing
        cid = contacts[0]["id"]
        conn2 = http.client.HTTPSConnection("rest.gohighlevel.com")
        conn2.request("PUT", f"/v1/contacts/{cid}", json.dumps(payload), headers)
        conn2.getresponse().read()
    else:
        # Create new
        conn3 = http.client.HTTPSConnection("rest.gohighlevel.com")
        conn3.request("POST", "/v1/contacts/", json.dumps(payload), headers)
        conn3.getresponse().read()


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass  # suppress default access log noise

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)

            # ── Verify Whop signature ──────────────────────────────────────
            sig_header = (
                self.headers.get("whop-signature") or
                self.headers.get("Whop-Signature") or
                ""
            )
            if WHOP_SECRET and not verify_signature(WHOP_SECRET, raw_body, sig_header):
                self._respond(401, {"error": "invalid signature"})
                return

            event = json.loads(raw_body)
            event_type = event.get("event", "")

            # Only care about completed payments
            if event_type not in ("payment.succeeded", "membership.went_valid"):
                self._respond(200, {"ok": True, "skipped": event_type})
                return

            # ── Extract contact details ────────────────────────────────────
            data   = event.get("data", {})
            user   = data.get("user", {}) or data.get("customer", {})
            plan   = data.get("plan", {}) or {}

            email  = (user.get("email") or data.get("email") or "").strip().lower()
            name   = (user.get("name") or user.get("username") or "").strip()
            phone  = (user.get("phone_number") or "").strip()
            slug   = (plan.get("slug") or data.get("plan_id") or "").strip()

            if not email:
                self._respond(400, {"error": "no email in payload"})
                return

            # Split name into first/last
            parts = name.split(" ", 1)
            first = parts[0] if parts else ""
            last  = parts[1] if len(parts) > 1 else ""

            # Resolve tags — fall back to generic "purchased" if slug unknown
            tags = PLAN_TAGS.get(slug, ["purchased"])

            # ── Push to GHL ───────────────────────────────────────────────
            ghl_upsert_contact(email, first, last, phone, tags)

            self._respond(200, {"ok": True, "email": email, "tags": tags})

        except Exception as exc:
            self._respond(500, {"error": str(exc)})

    def do_GET(self):
        # Health check
        self._respond(200, {"ok": True, "service": "whop-webhook"})

    def _respond(self, code: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
