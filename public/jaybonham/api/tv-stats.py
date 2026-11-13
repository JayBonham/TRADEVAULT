"""TradeVault analytics for the admin dashboard (thetradevault.co/admin/analytics). Admin token required.

GET [?fresh=1] -> {ok, at, products:{id: tier}, memberships:[...], payments:[...], disputes:[...], partial}
Every TradeVault membership, payment and dispute from Whop, trimmed to what the dashboard needs;
the page computes members, MRR, revenue, renewals, churn and chargebacks from these rows.
Only TradeVault products count (title contains "TradeVault", or one of its store routes). Results are
cached per instance for two minutes; ?fresh=1 reloads. Needs the Whop key's payment:dispute:read
permission for disputes (without it, disputes come from the payments' own dispute fields).
"""
import http.client
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token

WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
WHOP_COMPANY = "biz_R8QEgfRFt2KfLV"
TV_ROUTES = {"sniper-tools", "sniper-community-3c", "sniper-elite-3d", "tradevault-tools-partner-killshot",
             "tradevault-tools-partner-smartshot", "tradevault-tools-partner-killshot-smartshot",
             "tradevault-tools-jay-live"}
CACHE_TTL = 120
BUDGET = 45  # seconds of Whop paging before returning what we have (maxDuration is 60)
_CACHE = {"at": 0, "body": None}


def log(*a):
    print(*a, file=sys.stderr)


def money(v):
    if isinstance(v, dict):
        v = v.get("amount")
    try:
        return round(float(v), 2) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def tier_of(title, route=""):
    t = " ".join(str(title or "").lower().split())
    if "tradevault" not in t.replace(" ", "") and route not in TV_ROUTES:
        return None
    if "partner" in t or route.startswith("tradevault-"):
        return "partner"
    for k in ("elite", "community", "tools"):
        if k in t or k in route:
            return k
    return "partner"


def whop_get(path):
    c = http.client.HTTPSConnection("api.whop.com", timeout=15)
    c.request("GET", "/api/v1" + path, None, {"Authorization": "Bearer " + WHOP_API_KEY, "Accept": "application/json"})
    r = c.getresponse()
    raw = r.read()
    if r.status >= 300:
        raise RuntimeError("Whop %s %s: %s" % (path.split("?")[0], r.status, raw[:200].decode("utf-8", "replace")))
    return json.loads(raw or b"{}")


def pages(path, deadline, limit=60):
    """Every row of a Whop list endpoint, newest first. Returns (rows, complete)."""
    rows, after = [], ""
    for _ in range(limit):
        if time.time() > deadline:
            return rows, False
        page = whop_get(path + ("&after=" + after if after else ""))
        rows += page.get("data") or []
        info = page.get("page_info") or {}
        after = info.get("end_cursor") or ""
        if not (info.get("has_next_page") and after):
            return rows, True
    return rows, False


def products():
    out = {}
    rows, _ = pages("/products?account_id=%s&first=100" % WHOP_COMPANY, time.time() + 10, 10)
    for p in rows:
        t = tier_of(p.get("title") or p.get("name"), str(p.get("route") or ""))
        if t and p.get("id"):
            out[p["id"]] = {"tier": t, "title": str(p.get("title") or "")}
    return out


def pay_title(p):
    prod = p.get("product") if isinstance(p.get("product"), dict) else {}
    items = [li for li in (p.get("line_items") or []) if isinstance(li, dict)]
    title = str(prod.get("title") or prod.get("name") or "") or next(
        (str(li.get("product_title") or li.get("label") or "") for li in items if li.get("product_title") or li.get("label")), "")
    return title, str(prod.get("route") or "")


def db_names():
    """membership_id -> (name, email) from our own payment records, for rows Whop leaves nameless."""
    if not DATABASE_URL:
        return {}
    try:
        import psycopg2
        c = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        cur = c.cursor()
        cur.execute("SELECT membership_id, name, email FROM tv_payments WHERE membership_id IS NOT NULL ORDER BY paid_at")
        out = {r[0]: (r[1] or "", r[2] or "") for r in cur.fetchall()}
        c.close()
        return out
    except Exception as e:
        log("TV_STATS_DB_ERR:", e)
        return {}


def load():
    deadline = time.time() + BUDGET
    prods = products()
    q = "account_id=%s&first=100" % WHOP_COMPANY
    with ThreadPoolExecutor(4) as ex:
        fm = ex.submit(pages, "/memberships?" + q + "&order=created_at&direction=desc", deadline)
        fp = ex.submit(pages, "/payments?" + q + "&order=created_at&direction=desc", deadline)
        fd = ex.submit(pages, "/disputes?" + q, deadline, 20)
        fn = ex.submit(db_names)
        mems, m_ok = fm.result()
        pays, p_ok = fp.result()
        try:
            disps, d_ok = fd.result()
        except Exception as e:
            log("TV_STATS_DISPUTES:", e)
            disps, d_ok = None, False
        names = fn.result()

    out_p, who = [], {}
    for p in pays:
        pid = p.get("product_id") or (p["product"].get("id") if isinstance(p.get("product"), dict) else None)
        title, route = pay_title(p)
        tier = (prods.get(pid) or {}).get("tier") or tier_of(title, route)
        if not tier:
            continue
        if pid and pid not in prods:
            prods[pid] = {"tier": tier, "title": title}
        user = p.get("user") if isinstance(p.get("user"), dict) else {}
        name = str(user.get("name") or user.get("username") or "")
        email = str(p.get("customer_email") or user.get("email") or "")
        mid = p.get("membership_id") or ((p.get("membership") or {}).get("id") if isinstance(p.get("membership"), dict) else p.get("membership"))
        if mid and mid not in who and (name or email):
            who[mid] = (name, email)  # newest payment first
        out_p.append({
            "id": p.get("id"), "tier": tier, "mid": mid, "uid": user.get("id"),
            "at": p.get("paid_at") or p.get("created_at"), "created": p.get("created_at"),
            "amt": money(p.get("usd_total")) or money(p.get("total")) or money(p.get("subtotal")) or 0,
            "ref": money(p.get("refunded_amount")) or 0, "refunded_at": p.get("refunded_at"),
            "st": p.get("status"), "sub": p.get("substatus"), "br": p.get("billing_reason"),
            "disp": p.get("dispute_created_at"), "name": name, "email": email})

    out_m = []
    for m in mems:
        prod = m.get("product") if isinstance(m.get("product"), dict) else {}
        pid = m.get("product_id") or prod.get("id")
        tier = (prods.get(pid) or {}).get("tier") or tier_of(prod.get("title"), str(prod.get("route") or ""))
        if not tier:
            continue
        name, email = who.get(m.get("id")) or names.get(m.get("id")) or ("", "")
        out_m.append({
            "id": m.get("id"), "tier": tier, "status": m.get("status"), "uid": m.get("user_id"),
            "created": m.get("created_at"), "canceled_at": m.get("canceled_at"),
            "end": m.get("current_period_end") or m.get("expires_at"), "cap": bool(m.get("cancel_at_period_end")),
            "price": money(m.get("renewal_price")), "days": m.get("billing_period_days"),
            "opt": m.get("cancel_option"), "why": (m.get("cancellation_reason") or "")[:200],
            "name": name, "email": email})

    out_d, by_pay = [], {p["id"]: p for p in out_p}
    if disps is not None:
        for d in disps:
            pay = d.get("payment") if isinstance(d.get("payment"), dict) else {}
            pid = d.get("product_id")
            mine = by_pay.get(pay.get("id"))
            tier = (prods.get(pid) or {}).get("tier") or (mine or {}).get("tier")
            if not tier:
                continue
            out_d.append({"id": d.get("id"), "tier": tier, "at": d.get("created_at"), "amt": money(d.get("amount")) or 0,
                          "status": d.get("status"), "reason": d.get("reason"), "pay": pay.get("id"),
                          "name": (mine or {}).get("name") or "", "due": d.get("evidence_due_at")})
    else:
        # No dispute permission: every payment Whop marks as disputed.
        for p in out_p:
            if p["disp"] or str(p["sub"] or "").startswith(("dispute", "resolution")):
                out_d.append({"id": p["id"], "tier": p["tier"], "at": p["disp"] or p["at"], "amt": p["amt"],
                              "status": p["sub"], "reason": None, "pay": p["id"], "name": p["name"], "due": None})

    return {"ok": True, "at": int(time.time()), "products": prods, "memberships": out_m, "payments": out_p,
            "disputes": out_d, "partial": not (m_ok and p_ok), "disputes_source": "whop" if disps is not None else "payments"}


class handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        if not (auth.startswith("Bearer ") and verify_token(auth[7:])):
            return self._json(401, {"ok": False, "error": "Unauthorized"})
        if not WHOP_API_KEY:
            return self._json(500, {"ok": False, "error": "WHOP_API_KEY is not set in Vercel"})
        fresh = parse_qs(urlparse(self.path).query).get("fresh") == ["1"]
        if not fresh and _CACHE["body"] and time.time() - _CACHE["at"] < CACHE_TTL:
            return self._json(200, dict(_CACHE["body"], cached=True))
        try:
            body = load()
        except Exception as e:
            log("TV_STATS_ERR:", e)
            return self._json(502, {"ok": False, "error": str(e)[:300]})
        _CACHE.update(at=time.time(), body=body)
        self._json(200, body)

    def _json(self, status, body):
        raw = json.dumps(body, separators=(",", ":")).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)
