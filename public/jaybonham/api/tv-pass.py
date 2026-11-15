"""Killshot Pass claims from the chart game (thetradevault.co/spot).
POST {name, email, phone?, score, rank, aff?, ref?, utm_*}
 1. Saves a backup row in Postgres (tv_pass_claims) so no claim is ever lost.
 2. Upserts the contact in GHL and ADDS tags (never replaces existing ones):
      tv-pass-claimed, tv-pass-rank-<rank>   (+ tv-pass-aff-<code> from an affiliate link)
    A GHL workflow on tv-pass-claimed sends the "activate your 7 days" emails/texts.
"""
import http.client
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler

DATABASE_URL = os.environ.get("DATABASE_URL", "")
GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"
ORIGINS = {"https://thetradevault.co", "https://www.thetradevault.co", "https://start.thetradevault.co"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
AFF_RE = re.compile(r"^[a-z0-9_]{3,20}$")
RANKS = {"rookie", "apprentice", "trader", "sharpshooter", "sniper"}


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
        if not name or not EMAIL_RE.match(email):
            return self._json(400, {"ok": False, "error": "Please check your name and email."})
        if phone and len(re.sub(r"\D", "", phone)) < 7:
            return self._json(400, {"ok": False, "error": "That mobile number looks too short."})
        try:
            score = max(0, min(100, int(b.get("score") or 0)))
        except (TypeError, ValueError):
            score = 0
        rank = _clip(b.get("rank"), 20).lower()
        if rank not in RANKS:
            rank = ""
        aff = _clip(b.get("aff"), 20).lower()
        if not AFF_RE.match(aff):
            aff = ""
        utm = {k: _clip(b.get(k), 120) for k in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid")}
        utm = {k: v for k, v in utm.items() if v}
        ref = _clip(b.get("ref"), 300)

        first, _, last = name.partition(" ")
        tags = ["tv-pass-claimed"] + (["tv-pass-rank-" + rank] if rank else []) + (["tv-pass-aff-" + aff] if aff else [])
        ghl = self._ghl(first, last, email, phone, tags)
        saved = self._save(name, email, phone, score, rank, aff, utm, ref)
        log("TV_PASS", email, rank, score, "db" if saved else "-", "ghl" if ghl else "-")
        if not (saved or ghl):
            return self._json(502, {"ok": False, "error": "Couldn't save your pass. Please try again."})
        self._json(200, {"ok": True})

    def _save(self, name, email, phone, score, rank, aff, utm, ref):
        if not DATABASE_URL:
            return False
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tv_pass_claims (
                    id         BIGSERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    name TEXT, email TEXT, phone TEXT,
                    score INT, rank TEXT, aff TEXT, utm JSONB, ref TEXT
                )
            """)
            cur.execute("INSERT INTO tv_pass_claims (name, email, phone, score, rank, aff, utm, ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (name, email, phone or None, score, rank or None, aff or None, json.dumps(utm), ref))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log("TV_PASS_DB_ERR:", e)
            return False

    def _ghl(self, first, last, email, phone, tags):
        if not GHL_API_KEY:
            return False
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + GHL_API_KEY, "Version": "2021-07-28"}
        try:
            body = {"locationId": GHL_LOCATION, "firstName": first, "email": email, "source": "Trade Vault chart game (Killshot pass)"}
            if last:
                body["lastName"] = last
            if phone:
                body["phone"] = phone
            c = http.client.HTTPSConnection("services.leadconnectorhq.com", timeout=8)
            c.request("POST", "/contacts/upsert", json.dumps(body), headers)
            r = c.getresponse()
            data = json.loads(r.read() or b"{}")
            cid = (data.get("contact") or {}).get("id")
            if r.status >= 300 or not cid:
                log("TV_PASS_GHL_UPSERT:", r.status, str(data)[:300])
                return False
            c = http.client.HTTPSConnection("services.leadconnectorhq.com", timeout=8)
            c.request("POST", "/contacts/" + cid + "/tags", json.dumps({"tags": tags}), headers)
            r2 = c.getresponse()
            r2.read()
            if r2.status >= 300:
                log("TV_PASS_GHL_TAGS:", r2.status)
            return True
        except Exception as e:
            log("TV_PASS_GHL_ERR:", e)
            return False

    def _json(self, status, body):
        self.send_response(status)
        origin = self.headers.get("Origin", "")
        if origin in ORIGINS or origin.startswith("http://localhost"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())
