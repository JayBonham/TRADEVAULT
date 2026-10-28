"""Webinar registration.
POST {name, email, phone, session (ISO UTC start), page, ref, utm_*}
 1. Saves a backup row in Postgres (jb_webinar_regs) so no signup is ever lost.
 2. Upserts the contact in GHL and ADDS tags (never replaces existing tags):
      webinar-registered, webinar-YYYY-MM-DD
 3. Forwards the payload to a GHL inbound webhook if GHL_WEBINAR_WEBHOOK is set.
"""
import http.client
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler

DATABASE_URL = os.environ.get("DATABASE_URL", "")
GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"
GHL_WEBINAR_WEBHOOK = os.environ.get("GHL_WEBINAR_WEBHOOK", "")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


def log(*a):
    print(*a, file=sys.stderr)


def _clip(v, n):
    return v.strip()[:n] if isinstance(v, str) else ""


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def do_POST(self):
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 8000)
            b = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"ok": False, "error": "Invalid request"})

        name = _clip(b.get("name"), 80)
        email = _clip(b.get("email"), 160).lower()
        phone = _clip(b.get("phone"), 40)
        if not name or not EMAIL_RE.match(email) or len(re.sub(r"\D", "", phone)) < 7:
            return self._json(400, {"ok": False, "error": "Please check your name, email and phone."})

        # session start (ISO) -> date tag; fall back to today
        try:
            session = datetime.fromisoformat(_clip(b.get("session"), 40).replace("Z", "+00:00"))
        except ValueError:
            session = datetime.now(timezone.utc)
        if session.tzinfo is None:
            session = session.replace(tzinfo=timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            local_day = session.astimezone(ZoneInfo("America/New_York"))
        except Exception:
            local_day = session - timedelta(hours=5)
        session_tag = "webinar-" + local_day.strftime("%Y-%m-%d")
        first, _, last = name.partition(" ")
        utm = {k: _clip(b.get(k), 120) for k in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid")}
        ref = _clip(b.get("ref"), 300)

        saved = self._save(name, email, phone, session, utm, ref)
        ghl = self._ghl(first, last, email, phone, ["webinar-registered", session_tag])
        hook = self._webhook({
            "first_name": first, "last_name": last, "full_name": name,
            "email": email, "phone": phone,
            "webinar_start_utc": session.isoformat(),
            "webinar_tag": session_tag,
            "source": "jaybonham.com/webinar", "referrer": ref, **utm,
        })
        log("WEBINAR_REG", email, "db" if saved else "-", "ghl" if ghl else "-", "hook" if hook else "-")

        if not (saved or ghl or hook):
            return self._json(502, {"ok": False, "error": "Something went wrong saving your seat. Please try again."})
        self._json(200, {"ok": True})

    # ── backup copy ──────────────────────────────────────────
    def _save(self, name, email, phone, session, utm, ref):
        if not DATABASE_URL:
            return False
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jb_webinar_regs (
                    id         BIGSERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    session_at TIMESTAMPTZ,
                    name TEXT, email TEXT, phone TEXT,
                    utm JSONB, ref TEXT
                )
            """)
            cur.execute(
                "INSERT INTO jb_webinar_regs (session_at, name, email, phone, utm, ref) VALUES (%s,%s,%s,%s,%s,%s)",
                (session, name, email, phone, json.dumps(utm), ref),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log("WEBINAR_DB_ERR:", e)
            return False

    # ── GHL contact + tags ───────────────────────────────────
    def _ghl(self, first, last, email, phone, tags):
        if not GHL_API_KEY:
            return False
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + GHL_API_KEY,
            "Version": "2021-07-28",
        }
        try:
            body = {"locationId": GHL_LOCATION, "firstName": first, "email": email,
                    "phone": phone, "source": "Webinar registration"}
            if last:
                body["lastName"] = last
            c = http.client.HTTPSConnection("services.leadconnectorhq.com", timeout=8)
            c.request("POST", "/contacts/upsert", json.dumps(body), headers)
            r = c.getresponse()
            data = json.loads(r.read() or b"{}")
            cid = (data.get("contact") or {}).get("id")
            if r.status >= 300 or not cid:
                log("WEBINAR_GHL_UPSERT:", r.status, str(data)[:300])
                return False
            # add tags (POST /tags adds; it never removes existing tags)
            c = http.client.HTTPSConnection("services.leadconnectorhq.com", timeout=8)
            c.request("POST", "/contacts/" + cid + "/tags", json.dumps({"tags": tags}), headers)
            r2 = c.getresponse()
            r2.read()
            if r2.status >= 300:
                log("WEBINAR_GHL_TAGS:", r2.status)
            return True
        except Exception as e:
            log("WEBINAR_GHL_ERR:", e)
            return False

    # ── optional GHL inbound webhook ─────────────────────────
    def _webhook(self, payload):
        if not GHL_WEBINAR_WEBHOOK:
            return False
        try:
            u = urllib.parse.urlparse(GHL_WEBINAR_WEBHOOK)
            c = http.client.HTTPSConnection(u.netloc, timeout=8)
            c.request("POST", u.path + ("?" + u.query if u.query else ""), json.dumps(payload),
                      {"Content-Type": "application/json"})
            r = c.getresponse()
            r.read()
            if r.status >= 300:
                log("WEBINAR_HOOK:", r.status)
                return False
            return True
        except Exception as e:
            log("WEBINAR_HOOK_ERR:", e)
            return False

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())
