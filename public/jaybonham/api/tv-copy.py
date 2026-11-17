"""Copy Trader setup for Elite members. Route: /api/tv-copy?action=<action>   (page: thetradevault.co/copy)

  start  POST  {email, us}         if it's an active Elite member, GHL emails them a 30-day link
                                   (tag tv-copy-link, field {{contact.tv_copy_link}}, plus tv-copy-us or
                                   tv-copy-global); always says ok
  guide  POST  {t}                 the join link and setup guide for the member's region only
  link   POST  (Bearer admin) {email, us} -> {link, elite, region}: a link support can send by hand

Region: US when the member ticks "I live in the United States" OR the request comes from a US IP
(Vercel's x-vercel-ip-country). It's sealed into the link, so the page only ever shows that one.

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


def sign(email, region):
    p = base64.urlsafe_b64encode(json.dumps({"m": email, "r": region, "e": int(time.time()) + TTL}).encode()).decode().rstrip("=")
    return p + "." + hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()


def verify(token):
    try:
        p, sig = (token or "").rsplit(".", 1)
        if not hmac.compare_digest(sig, hmac.new(SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()):
            return None
        d = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
        return (d["m"], d.get("r") or "us") if d.get("e", 0) > time.time() else None
    except Exception:
        return None


def link(email, region):
    return "https://thetradevault.co/copy?t=" + sign(email, region)


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

    def _region(self, ticked):
        ip = (self.headers.get("x-vercel-ip-country") or "").upper()
        return ("us" if ticked or ip == "US" else "global"), ip

    def _start(self):
        b = self._body()
        email = (b.get("email") or "").strip().lower()
        region, ip = self._region(bool(b.get("us")))
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
            A.ghl_tag(email, name, ["tv-copy-link", "tv-copy-" + region], again=True, fields={"tv_copy_link": link(email, region)})
            A.log("TV_COPY_LINK_SENT", email, region, "ip=" + ip, "ticked=" + str(bool(b.get("us"))))
        self._json(200, {"ok": True})

    def _guide(self):
        v = verify(self._body().get("t"))
        if not v:
            return self._json(400, {"error": "This link has expired. Ask for a new one below.", "expired": True})
        email, region = v
        try:
            c = A.conn()
            cur = c.cursor()
            ok = elite(cur, email)
            c.close()
        except Exception as e:
            A.log("TV_COPY_GUIDE_ERR:", e)
            return self._json(500, {"error": "This is unavailable right now. Please try again in a minute."})
        if not ok:
            return self._json(403, {"error": "The Tradevault Copy Software is part of Elite, and we can't find an active Elite membership on " + email + ".", "not_elite": True})
        g = G.GUIDES[region]
        steps = [dict(s, img=("data:image/webp;base64," + G.US_IMG[s["img"]]) if region == "us" and s.get("img") else None) for s in g["steps"]]
        A.log("TV_COPY_GUIDE", email, region)
        self._json(200, {"ok": True, "email": email, "region": region, "guide": dict(g, steps=steps, url=URLS.get(region) or None)})

    def _link(self):
        h = self.headers.get("Authorization", "")
        if not verify_token(h[7:].strip() if h.startswith("Bearer ") else ""):
            return self._json(401, {"error": "unauthorized"})
        b = self._body()
        email = (b.get("email") or "").strip().lower()
        region = "us" if b.get("us") else "global"
        if not EMAIL_RE.match(email):
            return self._json(400, {"error": "email required"})
        try:
            c = A.conn()
            cur = c.cursor()
            ok = elite(cur, email)
            c.close()
        except Exception as e:
            return self._json(500, {"error": str(e)[:200]})
        self._json(200, {"ok": True, "link": link(email, region), "elite": ok, "region": region})

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
