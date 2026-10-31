"""TradeVault checkout with the affiliate attached. Route: /api/tv-checkout?plan=tools|community|elite&ref=CODE

The pricing buttons on thetradevault.co send visitors who came through an affiliate link here.
We create a Whop checkout session for that plan with metadata {"tv_ref": CODE} and redirect to it;
Whop copies the metadata onto the payment, and whop-hook credits the affiliate from it. That holds
whatever browser or device the buyer pays on, and whether or not they ever reach /setup.

Anything that goes wrong (unknown code, Whop API error) falls back to the plain Whop product page,
so a sale is never blocked by tracking.
"""
import http.client
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
import _tv_aff

WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
WHOP_COMPANY = "biz_R8QEgfRFt2KfLV"
STORE = "https://whop.com/sniper-academy-603f/"
PRODUCTS = {  # tier -> (Whop product title, store page)
    "tools":     ("tradevault tools",     STORE + "sniper-tools/"),
    "community": ("tradevault community", STORE + "sniper-community-3c/"),
    "elite":     ("tradevault elite",     STORE + "sniper-elite-3d/"),
}
REDIRECT = "https://thetradevault.co/setup"
PLAN_TABLE = "CREATE TABLE IF NOT EXISTS tv_whop_plans (tier TEXT PRIMARY KEY, plan_id TEXT NOT NULL)"
CODE_RE = re.compile(r"^[a-z0-9_]{3,20}$")


def log(*a):
    print(*a, file=sys.stderr)


def _whop(method, path, body=None):
    c = http.client.HTTPSConnection("api.whop.com", timeout=8)
    c.request(method, path, json.dumps(body) if body is not None else None,
              {"Authorization": "Bearer " + WHOP_API_KEY, "Accept": "application/json",
               "Content-Type": "application/json"})
    r = c.getresponse()
    raw = r.read()
    if r.status >= 300:
        raise RuntimeError("Whop %s %s: %s" % (method, r.status, raw[:300].decode("utf-8", "replace")))
    return json.loads(raw or b"{}")


def _title(p):
    prod = p.get("product") if isinstance(p.get("product"), dict) else {}
    t = prod.get("title") or next((li.get("product_title") for li in p.get("line_items") or []
                                   if isinstance(li, dict) and li.get("product_title")), "")
    return " ".join(str(t or "").lower().split())


def plan_id(cur, tier):
    """The plan new buyers check out on, per tier. Env TV_PLAN_<TIER> wins; otherwise it's learned
    from the most recent first payment for that product and remembered in tv_whop_plans."""
    env = os.environ.get("TV_PLAN_" + tier.upper(), "").strip()
    if env:
        return env
    cur.execute(PLAN_TABLE)
    cur.execute("SELECT plan_id FROM tv_whop_plans WHERE tier = %s", (tier,))
    row = cur.fetchone()
    if row:
        return row[0]
    page = _whop("GET", "/api/v1/payments?account_id=" + WHOP_COMPANY + "&first=100")
    found = {}
    for p in page.get("data") or []:  # newest first
        if p.get("status") != "paid" or p.get("billing_reason") not in ("subscription_create", "one_time", None):
            continue
        plan = p.get("variant_id") or (p["plan"].get("id") if isinstance(p.get("plan"), dict) else None)
        for t, (title, _) in PRODUCTS.items():
            if plan and t not in found and _title(p) == title:
                found[t] = plan
    for t, pid in found.items():
        cur.execute("INSERT INTO tv_whop_plans (tier, plan_id) VALUES (%s, %s) ON CONFLICT (tier) DO NOTHING", (t, pid))
    return found.get(tier)


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        tier = (q.get("plan") or [""])[0].strip().lower()
        code = (q.get("ref") or [""])[0].strip().lower()
        if tier not in PRODUCTS:
            return self._go(STORE)
        fallback = PRODUCTS[tier][1]
        if not (WHOP_API_KEY and CODE_RE.match(code)):
            return self._go(fallback)
        try:
            c = _tv_aff.conn()
            cur = c.cursor()
            cur.execute("SELECT 1 FROM tv_affiliates WHERE code = %s AND status = 'active'", (code,))
            if not cur.fetchone():
                c.close()
                return self._go(fallback)
            pid = plan_id(cur, tier)
            c.commit()
            c.close()
            if not pid:
                log("TV_CHECKOUT: no plan id for", tier)
                return self._go(fallback)
            cfg = _whop("POST", "/api/v1/checkout_configurations", {
                "mode": "payment", "plan_id": pid, "redirect_url": REDIRECT,
                "metadata": {"tv_ref": code, "tv_tier": tier}})
            url = cfg.get("purchase_url") or ""
            if url.startswith("/"):
                url = "https://whop.com" + url
            if not url.startswith("https://"):
                log("TV_CHECKOUT: no purchase_url", json.dumps(cfg)[:300])
                return self._go(fallback)
            log("TV_CHECKOUT", tier, code, cfg.get("id"))
            return self._go(url)
        except Exception as e:
            log("TV_CHECKOUT_ERR:", e)
            return self._go(fallback)

    def _go(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
