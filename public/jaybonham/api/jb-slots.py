import http.client
import json
import os
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler

CAL_API_KEY = os.environ.get("CAL_API_KEY", "")
EVENT_TYPE_ID = "6066137"


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        try:
            now = datetime.now(timezone.utc)
            start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            end = (now + timedelta(days=42)).strftime("%Y-%m-%dT%H:%M:%SZ")

            path = (
                f"/v2/slots/available"
                f"?startTime={start}&endTime={end}&eventTypeId={EVENT_TYPE_ID}"
            )
            conn = http.client.HTTPSConnection("api.cal.com")
            conn.request("GET", path, headers={
                "Authorization": f"Bearer {CAL_API_KEY}",
                "cal-api-version": "2024-09-04",
            })
            res = conn.getresponse()
            data = json.loads(res.read().decode())
            self._json(res.status if res.status != 200 else 200, data)

        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass
