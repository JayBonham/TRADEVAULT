import http.client
import json
import os
from http.server import BaseHTTPRequestHandler

CAL_API_KEY = os.environ.get("CAL_API_KEY", "")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_JB_LIST_ID = int(os.environ.get("BREVO_JB_LIST_ID", "0"))
EVENT_TYPE_ID = 6066137


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            name = body.get("name", "").strip()
            email = body.get("email", "").strip()
            start = body.get("start", "").strip()
            tz = body.get("timezone", "UTC")

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
