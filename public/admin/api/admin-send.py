"""
POST /api/admin-send
{ type: "email"|"sms", to_email, to_name, subject, message, to_phone? }
Sends via Brevo transactional email or SMS.
"""
import http.client
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token

BREVO_API_KEY  = os.environ.get("BREVO_API_KEY", "")
FROM_EMAIL     = os.environ.get("ADMIN_FROM_EMAIL", "info@jaybonham.com")
FROM_NAME      = os.environ.get("ADMIN_FROM_NAME", "Jay Bonham")
SMS_SENDER     = os.environ.get("ADMIN_SMS_SENDER", "JayBonham")  # max 11 chars


def _brevo_post(path, payload):
    conn = http.client.HTTPSConnection("api.brevo.com")
    conn.request("POST", path, payload, {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": BREVO_API_KEY,
    })
    res = conn.getresponse()
    return res.status, res.read().decode()


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        auth = self.headers.get("Authorization", "")
        user = verify_token(auth.replace("Bearer ", "").strip())
        if not user:
            self._json(401, {"ok": False, "error": "Unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json(400, {"ok": False, "error": "Invalid JSON"})
            return

        msg_type   = (body.get("type") or "").strip()
        to_email   = (body.get("to_email") or "").strip()
        to_name    = (body.get("to_name") or "Friend").strip()
        to_phone   = (body.get("to_phone") or "").strip()
        subject    = (body.get("subject") or "").strip()
        message    = (body.get("message") or "").strip()
        sent_by    = user  # log who sent it

        if not message:
            self._json(400, {"ok": False, "error": "message required"})
            return

        if msg_type == "email":
            if not to_email or not subject:
                self._json(400, {"ok": False, "error": "to_email and subject required"})
                return
            # Wrap in minimal HTML so it renders nicely
            html_body = message.replace("\n", "<br>")
            payload = json.dumps({
                "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
                "to": [{"email": to_email, "name": to_name}],
                "replyTo": {"email": FROM_EMAIL, "name": FROM_NAME},
                "subject": subject,
                "htmlContent": f"""<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;line-height:1.6;max-width:600px">
{html_body}
<br><br>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0">
<p style="font-size:13px;color:#888">Sent via Jay Bonham Sales Portal · {sent_by}</p>
</div>""",
                "tags": ["admin-portal"],
            }).encode()
            status, resp = _brevo_post("/v3/smtp/email", payload)
            if status not in (200, 201):
                self._json(500, {"ok": False, "error": f"Email failed ({status})", "detail": resp[:300]})
                return
            print(f"[admin-send] email → {to_email} by {sent_by} — Brevo {status}")
            self._json(200, {"ok": True, "sent": "email"})

        elif msg_type == "sms":
            phone = to_phone or to_email  # fallback, won't work but keeps API clean
            # Strip everything except + and digits
            phone_clean = "+" + "".join(c for c in phone if c.isdigit()) if phone else ""
            if not phone_clean or len(phone_clean) < 8:
                self._json(400, {"ok": False, "error": "Valid phone number required for SMS"})
                return
            payload = json.dumps({
                "sender": SMS_SENDER,
                "recipient": phone_clean,
                "content": message[:160],  # standard SMS limit
                "type": "transactional",
            }).encode()
            status, resp = _brevo_post("/v3/transactionalSMS/sms", payload)
            if status not in (200, 201):
                self._json(500, {"ok": False, "error": f"SMS failed ({status})", "detail": resp[:300]})
                return
            print(f"[admin-send] SMS → {phone_clean} by {sent_by} — Brevo {status}")
            self._json(200, {"ok": True, "sent": "sms"})

        else:
            self._json(400, {"ok": False, "error": "type must be 'email' or 'sms'"})

    def _json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(data)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, *args):
        pass
