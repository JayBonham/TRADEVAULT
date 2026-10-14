import http.client
import json
import os
from http.server import BaseHTTPRequestHandler

SLACK_WEBHOOK_JB = os.environ.get("SLACK_WEBHOOK_JB", "")


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            # Contact basics
            first = body.get("first_name") or body.get("firstName") or ""
            last = body.get("last_name") or body.get("lastName") or ""
            name = (first + " " + last).strip() or body.get("full_name") or body.get("name") or "Unknown"
            email = body.get("email") or "—"
            phone = body.get("phone") or body.get("phone_raw") or "—"

            # Appointment time
            appt = body.get("appointment") or {}
            start = appt.get("startTime") or appt.get("start_time") or body.get("start_time") or "—"

            # Questionnaire fields — mapped via GHL Custom Data key-value pairs
            experience     = body.get("trading_experience") or "—"
            capital        = body.get("trading_capital") or "—"
            biggest_issue  = body.get("biggest_challenge") or "—"
            goal           = body.get("main_goal") or "—"
            heard          = body.get("heard_from") or "—"

            if SLACK_WEBHOOK_JB:
                lines = [
                    "*📅 New strategy call booked*",
                    f"*Name:* {name}",
                    f"*Email:* {email}",
                    f"*Phone:* {phone}",
                    f"*Time:* {start}",
                    "",
                    "*— Application Answers —*",
                    f"*Trading experience:* {experience}",
                    f"*Capital available:* {capital}",
                    f"*Biggest challenge:* {biggest_issue}",
                    f"*Main goal:* {goal}",
                    f"*How they heard:* {heard}",
                ]
                payload = json.dumps({"text": "\n".join(lines)}).encode()
                conn = http.client.HTTPSConnection("hooks.slack.com")
                conn.request(
                    "POST",
                    SLACK_WEBHOOK_JB.replace("https://hooks.slack.com", ""),
                    payload,
                    {"Content-Type": "application/json"},
                )
                conn.getresponse()

            self._respond(200, {"ok": True})

        except Exception as e:
            self._respond(500, {"error": str(e)})

    def do_OPTIONS(self):
        self._respond(200, {})

    def _respond(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass
