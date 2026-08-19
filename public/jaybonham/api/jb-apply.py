import hashlib
import http.client
import json
import os
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone

BREVO_API_KEY           = os.environ.get("BREVO_API_KEY", "")
BREVO_JB_APPLY_LIST_ID  = int(os.environ.get("BREVO_JB_APPLY_LIST_ID", "5"))
META_PIXEL_ID           = "3566618163494760"
META_CAPI_TOKEN         = os.environ.get("META_CAPI_TOKEN", "")
META_CAPI_URL_BASE      = "https://jaybonham.com/apply"

CAPITAL_MAP = {
    "Under $5K":     2500,
    "$5K–25K":  15000,   # $5K–$25K  (en-dash)
    "$5K-$25K":      15000,
    "$25K–$100K": 62500, # $25K–$100K
    "$25K-$100K":    62500,
    "$100K–$500K": 300000,
    "$100K-$500K":   300000,
    "$500K+":        750000,
}


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json(400, {"ok": False, "error": "Invalid JSON"})
            return

        email    = (body.get("email") or "").strip()
        name     = (body.get("name") or "").strip()
        phone    = (body.get("phone") or "").strip()
        exp      = (body.get("experience_level") or "").strip()
        trading  = (body.get("current_trading") or "").strip()
        capital  = (body.get("trading_capital") or "").strip()
        blocker  = (body.get("biggest_blocker") or "").strip()
        goal     = (body.get("goal_12_months") or "").strip()
        event_id = (body.get("event_id") or "").strip()

        if not email or "@" not in email:
            self._json(400, {"ok": False, "error": "Valid email required"})
            return

        parts = name.split(" ", 1)
        first = parts[0]
        last  = parts[1] if len(parts) > 1 else ""
        capital_usd = CAPITAL_MAP.get(capital, 0)
        app_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        payload = json.dumps({
            "email": email,
            "attributes": {
                "FIRSTNAME":           first,
                "LASTNAME":            last,
                "SMS":                 phone,
                "EXPERIENCE_LEVEL":    exp,
                "CURRENT_TRADING":     trading,
                "TRADING_CAPITAL":     capital,
                "TRADING_CAPITAL_USD": capital_usd,
                "BIGGEST_BLOCKER":     blocker,
                "GOAL_12_MONTHS":      goal,
                "APPLICATION_DATE":    app_date,
            },
            "listIds": [BREVO_JB_APPLY_LIST_ID],
            "updateEnabled": True,
        }).encode()

        try:
            conn = http.client.HTTPSConnection("api.brevo.com")
            conn.request("POST", "/v3/contacts", payload, {
                "accept":       "application/json",
                "content-type": "application/json",
                "api-key":      BREVO_API_KEY,
            })
            res = conn.getresponse()
            res_body = res.read().decode()
            print(f"[jb-apply] Brevo {res.status}: {res_body[:200]}")
        except Exception as ex:
            print(f"[jb-apply] Brevo error: {ex}")
            self._json(200, {"ok": False, "error": "Could not save application. Please try again."})
            return

        # Fire CAPI Lead event (non-blocking, errors don't fail the request)
        self._send_capi("Lead", email, first, last, phone, event_id)

        self._json(200, {"ok": True})

    def _sha256(self, value):
        return hashlib.sha256(value.lower().strip().encode()).hexdigest() if value else None

    def _send_capi(self, event_name, email, first, last, phone, event_id):
        if not META_CAPI_TOKEN:
            return
        try:
            import time
            user_data = {}
            em = self._sha256(email);  em and user_data.__setitem__("em", [em])
            ph_clean = "".join(c for c in (phone or "") if c.isdigit())
            ph = self._sha256(ph_clean); ph and user_data.__setitem__("ph", [ph])
            fn = self._sha256(first);   fn and user_data.__setitem__("fn", [fn])
            ln = self._sha256(last);    ln and user_data.__setitem__("ln", [ln])
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
            print(f"[jb-apply] CAPI {event_name} → {resp.status}: {resp.read().decode()[:200]}")
        except Exception as ex:
            print(f"[jb-apply] CAPI error: {ex}")

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
