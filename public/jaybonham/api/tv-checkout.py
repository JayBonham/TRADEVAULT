"""TradeVault checkout with the affiliate attached. Route: /api/tv-checkout?plan=tools|community|elite|elite_trial&ref=CODE
       or ...&src=meta&campaign=..&content=<ad>&fbclid=..&fbc=..&fbp=.. (from an ad, with or without ref)

The pricing buttons on thetradevault.co send visitors who came through an affiliate link here.
We create a Whop checkout session for that plan with metadata {"tv_ref": CODE} and redirect to it;
Whop copies the metadata onto the payment, and whop-hook credits the affiliate from it. That holds
whatever browser or device the buyer pays on, and whether or not they ever reach /setup.

Anything that goes wrong (unknown code, Whop API error) falls back to the plain Whop product page,
so a sale is never blocked by tracking.
"""
import http.client
import json
import time
import os
import re
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
import _tv_aff
from _tv_whop import PRODUCTS, STORE, plan_id

WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
REDIRECT = "https://thetradevault.co/setup"
CODE_RE = re.compile(r"^[a-z0-9_]{3,20}$")
# The 7-day Elite trial is its own Whop product (thetradevault.co/trial). Its plan id comes from env
# TV_PLAN_ELITE_TRIAL, else it's looked up once by the product's store route and remembered.
TRIAL_ROUTE = "tradevault-elite-copy-e7"
TRIAL_ENDS = 1796014800  # 2026-11-30 00:00 ET
TRIAL_PAGE = STORE + TRIAL_ROUTE + "/"


def trial_plan(cur):
    env = os.environ.get("TV_PLAN_ELITE_TRIAL", "").strip()
    if env:
        return env
    cur.execute("CREATE TABLE IF NOT EXISTS tv_whop_plans (tier TEXT PRIMARY KEY, plan_id TEXT NOT NULL)")
    cur.execute("SELECT plan_id FROM tv_whop_plans WHERE tier = 'elite_trial'")
    row = cur.fetchone()
    if row:
        return row[0]
    from _tv_whop import WHOP_COMPANY
    prods = _whop("GET", "/api/v1/products?account_id=%s&first=100" % WHOP_COMPANY).get("data") or []
    prod = next((p for p in prods if isinstance(p, dict) and p.get("route") == TRIAL_ROUTE), None)
    if not prod:
        return None
    plans = _whop("GET", "/api/v1/plans?account_id=%s&product_ids=%s&first=20" % (WHOP_COMPANY, prod["id"])).get("data") or []
    plans = [p for p in plans if isinstance(p, dict) and (p.get("product") or {}).get("id", prod["id"]) == prod["id"]]
    pick = next((p for p in plans if p.get("trial_period_days")), plans[0] if plans else None)
    if not pick:
        return None
    cur.execute("INSERT INTO tv_whop_plans (tier, plan_id) VALUES ('elite_trial', %s) ON CONFLICT (tier) DO NOTHING", (pick["id"],))
    return pick["id"]


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


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        tier = (q.get("plan") or [""])[0].strip().lower()
        code = (q.get("ref") or [""])[0].strip().lower()
        # The Black Friday trial ends with Sun 29 Nov 2026 (ET); after that a trial link checks out as Elite.
        if tier == "elite_trial" and time.time() >= TRIAL_ENDS:
            tier = "elite"
        if tier not in PRODUCTS and tier != "elite_trial":
            return self._go(STORE)
        fallback = TRIAL_PAGE if tier == "elite_trial" else PRODUCTS[tier][1]
        # From an ad (the /trial page passes its utm_* / fbclid): the checkout carries the source too.
        arg = lambda k, n=120: (q.get(k) or [""])[0].strip()[:n]
        ad = {"src": arg("src", 40), "medium": arg("medium", 40), "campaign": arg("campaign", 80),
              "content": arg("content", 80), "fbclid": arg("fbclid", 400), "fbc": arg("fbc", 500), "fbp": arg("fbp", 200)}
        has_ref, has_ad = bool(CODE_RE.match(code)), bool(ad["src"] or ad["fbclid"])
        if not (WHOP_API_KEY and (has_ref or has_ad)):
            return self._go(fallback)
        try:
            c = _tv_aff.conn()
            cur = c.cursor()
            if has_ref:
                cur.execute("SELECT 1 FROM tv_affiliates WHERE code = %s AND status = 'active'", (code,))
                if not cur.fetchone():
                    if not has_ad:
                        c.close()
                        return self._go(fallback, "affiliate not active")
                    code = ""
            else:
                code = ""
            pid = trial_plan(cur) if tier == "elite_trial" else plan_id(cur, tier)
            c.commit()
            if not pid:
                c.close()
                log("TV_CHECKOUT: no plan id for", tier)
                return self._go(fallback, "no plan id for " + tier)
            meta = {"tv_tier": "elite" if tier == "elite_trial" else tier}
            if tier == "elite_trial":
                meta["tv_trial"] = "1"
            if code:
                meta["tv_ref"] = code
            if has_ad:
                import _tv_meta
                src = "meta" if _tv_meta.is_meta(ad["src"], ad["fbclid"]) else _tv_meta.slug(ad["src"]) or "other"
                meta.update(tv_src=src, tv_ad=_tv_meta.slug(ad["content"]), tv_campaign=_tv_meta.slug(ad["campaign"]))
                if ad["fbclid"] and not ad["fbc"]:
                    ad["fbc"] = "fb.1.%d.%s" % (int(time.time() * 1000), ad["fbclid"])
                try:
                    ad.update(src=src, ref=code,
                              ip=(self.headers.get("x-forwarded-for") or self.headers.get("x-real-ip") or "").split(",")[0].strip(),
                              ua=self.headers.get("user-agent") or "")
                    meta["tv_click"] = _tv_meta.save_click(cur, ad)
                    c.commit()
                except Exception as e:
                    log("TV_CHECKOUT_CLICK_ERR:", e)
            c.close()
            cfg = _whop("POST", "/api/v1/checkout_configurations", {
                "mode": "payment", "variant_id": pid, "plan_id": pid, "redirect_url": REDIRECT,
                "metadata": meta})
            url = cfg.get("purchase_url") or ""
            if url.startswith("/"):
                url = "https://whop.com" + url
            if not url.startswith("https://"):
                log("TV_CHECKOUT: no purchase_url", json.dumps(cfg)[:300])
                return self._go(fallback, "no purchase_url: " + json.dumps(cfg)[:300])
            log("TV_CHECKOUT", tier, code, meta.get("tv_src", ""), meta.get("tv_ad", ""), cfg.get("id"))
            return self._go(url)
        except Exception as e:
            log("TV_CHECKOUT_ERR:", e)
            return self._go(fallback, str(e)[:400])

    def _go(self, url, why=""):
        if why:
            log("TV_CHECKOUT_FALLBACK:", why[:300])
        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
