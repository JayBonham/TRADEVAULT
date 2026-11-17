"""Copy Trader setup for Elite members. Route: /api/tv-copy?action=<action>   (page: thetradevault.co/copy)

  start  POST  {email}             if it's an active Elite member, GHL emails them a 30-day link
                                   (tag tv-copy-link, field {{contact.tv_copy_link}}); always says ok
  guide  POST  {t}                 the join links and setup guides, only for a valid link + active Elite
  link   POST  (Bearer admin) {email} -> {link, elite}: a link support can send by hand

The join links live in Vercel env vars (TV_COPY_GLOBAL_URL, TV_COPY_US_URL), never in this public repo,
and nothing on the page shows them until the member is verified.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
import _tv_aff as A
import _tv_upgrade as U
import _tv_copy_guide as G
from _auth import verify_token

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
SECRET = os.environ.get("AFF_SESSION_SECRET", "changeme-aff-secret") + ":tv:copy"
TTL = 60 * 60 * 24 * 30
URLS = {"global": os.environ.get("TV_COPY_GLOBAL_URL", "").strip(), "us": os.environ.get("TV_COPY_US_URL", "").strip()}


def sign(email):
    p = base64.urlsafe_b64encode(json.dumps({"m": email, "e": int(time.time()) + TTL}).encode()).decode().rstrip("=")
    return p + "." + hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()


def verify(token):
    try:
        p, sig = (token or "").rsplit(".", 1)
        if not hmac.compare_digest(sig, hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()):
            return None
        d = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
        return d["m"] if d.get("e", 0) > time.time() else None
    except Exception:
        return None


def link(email):
    return "https://thetradevault.co/copy?t=" + sign(email)


def elite(cur, email):
    """True when the email has an active (or trialing) Elite membership on Whop."""
    best = U.current(cur, email, U.tier_plans(cur))
    return bool(best and best[1] == "elite")


class handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(200, None)

    def do_POST(self):
        a = self._action()
        if a in ("start", "guide", "link"):
            return getattr(self, "_" + a)()
        self._json(404, {"error": "unknown action"})

    def _start(self):
        email = (self._body().get("email") or "").strip().lower()
        if not EMAIL_RE.match(email):
            return self._json(400, {"error": "Enter the email you joined with."})
        try:
            c = A.conn()
            cur = c.cursor()
            ok = elite(cur, email)
            name = ""
            if ok:
                cur.execute("SELECT name FROM tv_payments WHERE lower(email) = %s AND name IS NOT NULL ORDER BY paid_at DESC LIMIT 1", (email,))
                r = cur.fetchone()
                name = (r and r[0]) or ""
            c.close()
        except Exception as e:
            A.log("TV_COPY_START_ERR:", e)
            return self._json(500, {"error": "This is unavailable right now. Email support@thetradevault.co."})
        # Same answer for members and non-members.
        if ok:
            A.ghl_tag(email, name, ["tv-copy-link"], again=True, fields={"tv_copy_link": link(email)})
            A.log("TV_COPY_LINK_SENT", email)
        self._json(200, {"ok": True})

    def _guide(self):
        email = verify(self._body().get("t"))
        if not email:
            return self._json(400, {"error": "This link has expired. Ask for a new one below.", "expired": True})
        try:
            c = A.conn()
            cur = c.cursor()
            ok = elite(cur, email)
            c.close()
        except Exception as e:
            A.log("TV_COPY_GUIDE_ERR:", e)
            return self._json(500, {"error": "This is unavailable right now. Please try again in a minute."})
        if not ok:
            return self._json(403, {"error": "Copy Trader is part of TradeVault Elite, and we can't find an active Elite membership on " + email + ".", "not_elite": True})
        regions = {}
        for k, g in G.GUIDES.items():
            steps = [dict(s, img=("data:image/webp;base64," + G.US_IMG[s["img"]]) if k == "us" and s.get("img") else None) for s in g["steps"]]
            regions[k] = dict(g, steps=steps, url=URLS.get(k) or None)
        A.log("TV_COPY_GUIDE", email)
        self._json(200, {"ok": True, "email": email, "regions": regions})

    def _link(self):
        h = self.headers.get("Authorization", "")
        if not verify_token(h[7:].strip() if h.startswith("Bearer ") else ""):
            return self._json(401, {"error": "unauthorized"})
        email = (self._body().get("email") or "").strip().lower()
        if not EMAIL_RE.match(email):
            return self._json(400, {"error": "email required"})
        try:
            c = A.conn()
            cur = c.cursor()
            ok = elite(cur, email)
            c.close()
        except Exception as e:
            return self._json(500, {"error": str(e)[:200]})
        self._json(200, {"ok": True, "link": link(email), "elite": ok})

    def _action(self):
        return (parse_qs(urlparse(self.path).query).get("action") or [""])[0].strip().lower()

    def _body(self):
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 4000)
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body, default=str).encode())
