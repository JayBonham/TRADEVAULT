import http.client
import json
import os
from http.server import BaseHTTPRequestHandler


BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_JB_LIST_ID = int(os.environ.get("BREVO_JB_LIST_ID", "0"))


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            email = body.get("email", "").strip().lower()
            if not email or "@" not in email:
                self._json(400, {"error": "Valid email required"})
                return

            payload = json.dumps({
                "email": email,
                "listIds": [BREVO_JB_LIST_ID],
                "updateEnabled": True
            }).encode()

            conn = http.client.HTTPSConnection("api.brevo.com")
            conn.request("POST", "/v3/contacts", payload, {
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": BREVO_API_KEY,
            })
            res = conn.getresponse()
            res_body = res.read().decode()

            # 201 = created, 204 = updated, 400 with "already" = already subscribed (fine)
            if res.status in (201, 204):
                self._json(200, {"ok": True})
            elif res.status == 400 and "already" in res_body.lower():
                self._json(200, {"ok": True})
            else:
                self._json(500, {"error": "Brevo error", "detail": res_body})

        except Exception as e:
            self._json(500, {"error": str(e)})

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
