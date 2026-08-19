import hashlib
import http.client
import json
import os
from http.server import BaseHTTPRequestHandler

CAL_API_KEY             = os.environ.get("CAL_API_KEY", "")
BREVO_API_KEY           = os.environ.get("BREVO_API_KEY", "")
BREVO_JB_LIST_ID        = int(os.environ.get("BREVO_JB_LIST_ID", "3"))
BREVO_JB_APPLY_LIST_ID  = int(os.environ.get("BREVO_JB_APPLY_LIST_ID", "5"))
EVENT_TYPE_ID           = 6066137
META_PIXEL_ID           = "3566618163494760"
META_CAPI_TOKEN         = os.environ.get("META_CAPI_TOKEN", "")
META_CAPI_URL_BASE      = "https://jaybonham.com/book"


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            name     = body.get("name", "").strip()
            email    = body.get("email", "").strip()
            start    = body.get("start", "").strip()
            tz       = body.get("timezone", "UTC")
            event_id = body.get("event_id", "").strip()

            if not all([name, email, start]):
                self._json(400, {"error": "name, email and start are required"})
                return

            payload = json.dumps({
                "eventTypeId": EVENT_TYPE_ID,
                "start": start,
                "attendee": {
                    "name": name,
                    "email": email,
                    "timeZone": tz,
                    "language": "en",
                },
            }).encode()

            conn = http.client.HTTPSConnection("api.cal.com")
            conn.request("POST", "/v2/bookings", payload, {
                "Authorization": f"Bearer {CAL_API_KEY}",
                "cal-api-version": "2024-08-13",
                "Content-Type": "application/json",
                "accept": "application/json",
            })
            res = conn.getresponse()
            data = json.loads(res.read().decode())

            if res.status in (200, 201):
                self._add_to_brevo(name, email)
                self._remove_from_apply_list(email)
                self._send_capi("Schedule", email, name, event_id)
                self._json(200, {"ok": True, "booking": data.get("data", {})})
            else:
                self._json(res.status, {"error": "Booking failed", "detail": data})

        except Exception as e:
            self._json(500, {"error": str(e)})

    def _add_to_brevo(self, name, email):
        try:
            payload = json.dumps({
                "email": email,
                "attributes": {"FIRSTNAME": name.split()[0], "LASTNAME": " ".join(name.split()[1:])},
                "listIds": [BREVO_JB_LIST_ID],
                "updateEnabled": True,
            }).encode()
            conn = http.client.HTTPSConnection("api.brevo.com")
            conn.request("POST", "/v3/contacts", payload, {
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": BREVO_API_KEY,
            })
            conn.getresponse()
        except Exception:
            pass  # don't fail the booking if Brevo is down

    def _remove_from_apply_list(self, email):
        """Remove contact from applicants list (List #5) once they've booked."""
        try:
            payload = json.dumps({"emails": [email]}).encode()
            conn = http.client.HTTPSConnection("api.brevo.com")
            conn.request(
                "POST",
                f"/v3/contacts/lists/{BREVO_JB_APPLY_LIST_ID}/contacts/remove",
                payload,
                {
                    "accept": "application/json",
                    "content-type": "application/json",
                    "api-key": BREVO_API_KEY,
                },
            )
            conn.getresponse()
        except Exception:
            pass  # non-critical — booking already confirmed

    def _sha256(self, value):
        return hashlib.sha256(value.lower().strip().encode()).hexdigest() if value else None

    def _send_capi(self, event_name, email, name, event_id):
        if not META_CAPI_TOKEN:
            return
        try:
            import time
            parts = name.split(" ", 1)
            first = parts[0]; last = parts[1] if len(parts) > 1 else ""
            user_data = {}
            em = self._sha256(email); em and user_data.__setitem__("em", [em])
            fn = self._sha256(first); fn and user_data.__setitem__("fn", [fn])
            ln = self._sha256(last);  ln and user_data.__setitem__("ln", [ln])
            event = {
                "event_name": event_name,
                "event_time": int(time.time()),
                "action_source": "website",
                "event_source_url": META_CAPI_URL_BASE,
                "user_data": user_data,
            }
            if event_id:
                event["event_id"] = event_id
            payload = json.dumps({
                "data": [event],
                "access_token": META_CAPI_TOKEN,
            }).encode()
            conn = http.client.HTTPSConnection("graph.facebook.com")
            conn.request("POST", f"/v21.0/{META_PIXEL_ID}/events", payload, {
                "Content-Type": "application/json",
            })
            resp = conn.getresponse()
            print(f"[jb-book] CAPI {event_name} → {resp.status}: {resp.read().decode()[:200]}")
        except Exception as ex:
            print(f"[jb-book] CAPI error: {ex}")

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *args):
        pass
