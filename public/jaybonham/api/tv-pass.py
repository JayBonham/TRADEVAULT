"""Killshot Pass claims from the chart game (thetradevault.co/spot), plus the game's funnel analytics.
POST {name, email, phone?, score, rank, aff?, ref?, utm_*}
 1. Saves a backup row in Postgres (tv_pass_claims) so no claim is ever lost.
 2. Upserts the contact in GHL and ADDS tags (never replaces existing ones):
      tv-pass-claimed, tv-pass-rank-<rank>   (+ tv-pass-aff-<code> from an affiliate link)
    A GHL workflow on tv-pass-claimed sends the "activate your 7 days" emails/texts.

POST ?ev=1 {vid, ev, step, aff?, ref?, utm_*}   (sendBeacon from the game, no personal data)
    One row per visit (vid = random id per browser tab) and step: view, start, round 1-5, finish, claim, again.
GET ?stats=1  (admin token + analytics password, like /api/tv-ads)
    -> {ok, events: [[hour_epoch, ev, step, src, ad, n]], claims: [[ts, src, ad, rank, phone, joined, paid, id, name, email]], since}
    claims are deduped per email; joined = a Trade Vault purchase or trial for that email from a day before the
    claim onwards (tv_members), paid = a real payment over $0 (tv_payments).
POST ?hide=1 {id}  (same lock) hides a test claim from the dashboard (every claim row for that email; kept in the table).
"""
import http.client
import json
import os
import re
import sys
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))

DATABASE_URL = os.environ.get("DATABASE_URL", "")
GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"
ORIGINS = {"https://thetradevault.co", "https://www.thetradevault.co", "https://start.thetradevault.co"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
AFF_RE = re.compile(r"^[a-z0-9_]{3,20}$")
RANKS = {"rookie", "apprentice", "trader", "sharpshooter", "sniper"}
EVENTS = {"view", "start", "round", "finish", "claim", "again"}
VID_RE = re.compile(r"^[a-z0-9]{6,32}$")
# Same lock as analytics / tv-ads (salted hash only; env TV_ANALYTICS_PASSWORD replaces it when set).
PASS_SALT = "1cd0c4abafd232acb8a6124e4e3ba085"
PASS_HASH = "a784bb07a38b075cb9d8d316dcf961c49448e6d3c3bc4686703477a07d31f129"
_EV_TABLE = """
    CREATE TABLE IF NOT EXISTS tv_game_events (
        vid TEXT NOT NULL, ev TEXT NOT NULL, step SMALLINT NOT NULL DEFAULT 0,
        src TEXT, ad TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (vid, ev, step));
    CREATE INDEX IF NOT EXISTS tv_game_events_at ON tv_game_events (created_at);
"""
_ev_ready = False


def pass_ok(given):
    given = (given or "").strip()
    env = os.environ.get("TV_ANALYTICS_PASSWORD", "")
    if env:
        return hmac.compare_digest(given.encode(), env.encode())
    h = hashlib.pbkdf2_hmac("sha256", given.encode(), bytes.fromhex(PASS_SALT), 300000).hex()
    return hmac.compare_digest(h, PASS_HASH)


def source_of(utm, ref, aff):
    """(src, ad): meta + ad name, affiliate + code, or the classified source ('' = direct)."""
    try:
        from _tv_trace import classify
        src, _, ad, _ = classify(utm, ref, aff)
    except Exception as e:
        log("TV_PASS_CLASSIFY:", e)
        src, ad = ("affiliate", "") if aff else ("", "")
    if src == "affiliate":
        ad = aff
    return (src or "")[:20], (ad or "")[:80]


def log(*a):
    print(*a, file=sys.stderr)


def _clip(v, n):
    return v.strip()[:n] if isinstance(v, str) else ""


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def _admin(self):
        """None when the caller is an unlocked admin, else the error response already sent."""
        from _auth import verify_token
        auth = self.headers.get("Authorization", "")
        if not (auth.startswith("Bearer ") and verify_token(auth[7:])):
            return self._json(401, {"ok": False, "error": "Unauthorized"}) or True
        if not pass_ok(self.headers.get("X-Analytics-Pass")):
            return self._json(403, {"ok": False, "locked": True, "error": "Wrong password"}) or True
        return None

    def _hide(self):
        if self._admin():
            return
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 2000)
            cid = int(json.loads(self.rfile.read(length) or b"{}").get("id"))
        except Exception:
            return self._json(400, {"ok": False, "error": "Invalid request"})
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
            cur = conn.cursor()
            cur.execute("ALTER TABLE tv_pass_claims ADD COLUMN IF NOT EXISTS hidden BOOLEAN NOT NULL DEFAULT FALSE")
            cur.execute("UPDATE tv_pass_claims SET hidden = TRUE WHERE lower(email) = (SELECT lower(email) FROM tv_pass_claims WHERE id = %s)", (cid,))
            n = cur.rowcount
            conn.commit()
            conn.close()
        except Exception as e:
            log("TV_PASS_HIDE_ERR:", e)
            return self._json(502, {"ok": False, "error": str(e)[:200]})
        log("TV_PASS_HIDE", cid, n)
        self._json(200, {"ok": True, "hidden": n})

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        if qs.get("stats") != ["1"]:
            return self._json(404, {"ok": False, "error": "Not found"})
        if self._admin():
            return
        if not DATABASE_URL:
            return self._json(500, {"ok": False, "error": "DATABASE_URL is not set"})
        out = {"ok": True, "events": [], "claims": [], "since": None}
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
            cur = conn.cursor()
            cur.execute(_EV_TABLE)
            cur.execute("ALTER TABLE tv_pass_claims ADD COLUMN IF NOT EXISTS hidden BOOLEAN NOT NULL DEFAULT FALSE")
            conn.commit()
            cur.execute("""SELECT EXTRACT(EPOCH FROM date_trunc('hour', created_at))::BIGINT, ev, step, COALESCE(src, ''), COALESCE(ad, ''), COUNT(*)
                           FROM tv_game_events WHERE created_at > NOW() - INTERVAL '400 days' GROUP BY 1, 2, 3, 4, 5""")
            out["events"] = [list(r) for r in cur.fetchall()]
            cur.execute("SELECT EXTRACT(EPOCH FROM MIN(created_at))::BIGINT FROM tv_game_events")
            out["since"] = cur.fetchone()[0]
            # one row per person who claimed (their first claim), and whether they went on to join / pay
            joined = paid = "FALSE"
            for table, expr in (("tv_members", "EXISTS (SELECT 1 FROM tv_members m WHERE lower(m.email) = c.em AND m.purchased_at >= c.created_at - INTERVAL '1 day')"),
                                ("tv_payments", "EXISTS (SELECT 1 FROM tv_payments p WHERE lower(p.email) = c.em AND p.amount_usd > 0 AND NOT p.refunded AND p.paid_at >= c.created_at - INTERVAL '1 day')")):
                cur.execute("SELECT to_regclass(%s)", (table,))
                if cur.fetchone()[0]:
                    if table == "tv_members":
                        joined = expr
                    else:
                        paid = expr
            cur.execute("""SELECT EXTRACT(EPOCH FROM c.created_at)::BIGINT, c.utm, c.ref, c.aff, c.rank, c.phone IS NOT NULL AND c.phone <> '', %s, %s, c.id, c.name, c.em
                           FROM (SELECT DISTINCT ON (lower(email)) lower(email) AS em, * FROM tv_pass_claims WHERE NOT hidden ORDER BY lower(email), created_at) c""" % (joined, paid))
            for ts, utm, ref, aff, rank, phone, j, pd, cid, name, em in cur.fetchall():
                src, ad = source_of(utm if isinstance(utm, dict) else {}, ref or "", aff or "")
                out["claims"].append([ts, src, ad, rank or "", bool(phone), bool(j or pd), bool(pd), cid, name or "", em or ""])
            conn.close()
        except Exception as e:
            log("TV_PASS_STATS_ERR:", e)
            return self._json(502, {"ok": False, "error": str(e)[:200]})
        self._json(200, out)

    def _event(self):
        global _ev_ready
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 4000)
            b = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, None)
        vid, ev = _clip(b.get("vid"), 32).lower(), _clip(b.get("ev"), 12)
        try:
            step = int(b.get("step") or 0)
        except (TypeError, ValueError):
            step = 0
        if not VID_RE.match(vid) or ev not in EVENTS or not (0 <= step <= 5) or (ev == "round") != (step > 0):
            return self._json(400, None)
        aff = _clip(b.get("aff"), 20).lower()
        utm = {k: _clip(b.get(k), 120) for k in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "fbclid")}
        src, ad = source_of(utm, _clip(b.get("ref"), 300), aff if AFF_RE.match(aff) else "")
        if DATABASE_URL:
            try:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
                cur = conn.cursor()
                if not _ev_ready:
                    cur.execute(_EV_TABLE)
                    _ev_ready = True
                cur.execute("INSERT INTO tv_game_events (vid, ev, step, src, ad) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            (vid, ev, step, src, ad))
                conn.commit()
                conn.close()
            except Exception as e:
                log("TV_PASS_EV_ERR:", e)
        self._json(204, None)

    def do_POST(self):
        q = parse_qs(urlparse(self.path).query)
        if q.get("ev") == ["1"]:
            return self._event()
        if q.get("hide") == ["1"]:
            return self._hide()
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
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Analytics-Pass")
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())
