"""TradeVault plan upgrades. Route: /api/tv-upgrade?action=<action>  (logic in _tv_upgrade.py)

  start  POST  {email}        emails a 48-hour upgrade link through GHL (always says ok)
  quote  POST  {t}            the member's plan and what each higher tier costs today / monthly
  go     POST  {t, tier}      -> {url}: Whop checkout for the upgrade
  info   GET   (Bearer admin) tier plans and promo codes, to check coupons work on upgrades
  link   POST  (Bearer admin) {email} -> {link, quote}: an upgrade link for support to send by hand
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
import _tv_aff as A
import _tv_upgrade as U
from _auth import verify_token

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


class handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(200, None)

    def do_GET(self):
        if self._action() == "info":
            return self._info()
        self._json(404, {"error": "unknown action"})

    def do_POST(self):
        a = self._action()
        if a in ("start", "quote", "go", "link"):
            return getattr(self, "_" + a)()
        self._json(404, {"error": "unknown action"})

    def _start(self):
        email = (self._body().get("email") or "").strip().lower()
        if not EMAIL_RE.match(email):
            return self._json(400, {"error": "Enter the email you joined with."})
        try:
            c = A.conn()
            cur = c.cursor()
            # A member: a payment on record, or on the members board (a $0 signup has no payment).
            cur.execute("""SELECT name FROM tv_payments WHERE lower(email) = %s AND NOT refunded
                           ORDER BY paid_at DESC LIMIT 1""", (email,))
            row = cur.fetchone()
            if not row:
                cur.execute("SELECT '' FROM tv_members WHERE lower(email) = %s AND removed_at IS NULL LIMIT 1", (email,))
                row = cur.fetchone()
            c.close()
        except Exception as e:
            A.log("TV_UPGRADE_START_ERR:", e)
            return self._json(500, {"error": "Upgrades are unavailable right now. Email support@thetradevault.co."})
        # Same answer whether or not the email is a member.
        if row:
            A.ghl_tag(email, row[0] or "", ["tv-upgrade-link"], again=True, fields={"tv_upgrade_link": U.link(email)})
            A.log("TV_UPGRADE_LINK_SENT", email)
        self._json(200, {"ok": True})

    def _quote(self):
        email = U.verify(self._body().get("t"))
        if not email:
            return self._json(400, {"error": "This upgrade link has expired. Ask for a new one below.", "expired": True})
        return self._run(lambda cur: dict(U.public(U.quote(cur, email)), ok=True, email=email))

    def _go(self):
        b = self._body()
        email = U.verify(b.get("t"))
        if not email:
            return self._json(400, {"error": "This upgrade link has expired. Ask for a new one below.", "expired": True})
        return self._run(lambda cur: {"ok": True, "url": U.checkout(cur, email, str(b.get("tier") or ""))})

    def _link(self):
        if not self._admin():
            return
        email = (self._body().get("email") or "").strip().lower()
        if not EMAIL_RE.match(email):
            return self._json(400, {"error": "email required"})

        def run(cur):
            out = {"ok": True, "link": U.link(email)}
            try:
                out["quote"] = U.public(U.quote(cur, email))
            except U.UpgradeError as e:
                out["quote_error"] = str(e)
            return out
        return self._run(run)

    def _info(self):
        if not self._admin():
            return
        return self._run(lambda cur: {"ok": True, "plans": U.tier_plans(cur), "promo_codes": U.promo_codes()})

    # ---------- helpers ----------
    def _run(self, fn):
        try:
            c = A.conn()
            cur = c.cursor()
            out = fn(cur)
            c.commit()
            c.close()
            return self._json(200, out)
        except U.UpgradeError as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:
            A.log("TV_UPGRADE_ERR:", e)
            return self._json(500, {"error": "Something went wrong. Please try again, or email support@thetradevault.co."})

    def _action(self):
        return (parse_qs(urlparse(self.path).query).get("action") or [""])[0].strip().lower()

    def _body(self):
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 4000)
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _admin(self):
        h = self.headers.get("Authorization", "")
        if not verify_token(h[7:].strip() if h.startswith("Bearer ") else ""):
            self._json(401, {"error": "unauthorized"})
            return False
        return True

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body, default=str).encode())
