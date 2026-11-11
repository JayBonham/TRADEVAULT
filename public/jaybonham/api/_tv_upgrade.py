"""TradeVault plan upgrades (Tools -> Community -> Elite) without double billing.

Whop can't move a membership to another plan, so an upgrade is a new membership on the higher
tier that starts where the old one leaves off:
  - Today the member pays the flat difference between what they pay now and the new tier's price
    (whatever day of the month it is).
  - The new membership's first renewal lands on the old billing date, at the new tier's price:
    the checkout uses a one-off hidden Whop plan with initial_price = difference and a "trial" that
    runs until that date (Whop charges only initial_price at checkout while a trial applies).
  - When the payment comes in (whop-hook), the old membership is cancelled straight away, so it
    never renews. Its tv_* metadata (setup answers, affiliate tv_ref) is carried onto the new one.
  - From Tools the member has new choices to make (educator, scanner, Telegram), so their
    "setup complete" tag comes off and /setup asks again.

The upgrade page proves the member owns the email with a link sent through GHL
(tag tv-upgrade-link, field {{contact.tv_upgrade_link}}).
"""
import base64
import datetime
import hashlib
import hmac
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import _tv_whop as W

SECRET = os.environ.get("AFF_SESSION_SECRET", "changeme-aff-secret") + ":tv:upgrade"
LINK_TTL = 60 * 60 * 48
SITE = "https://thetradevault.co"
NAMES = {"tools": "Tools", "community": "Community", "elite": "Elite"}
OK_STATUS = {"active", "trialing"}
TABLE = """CREATE TABLE IF NOT EXISTS tv_upgrades (
    payment_id TEXT PRIMARY KEY, email TEXT NOT NULL, old_membership TEXT, from_tier TEXT,
    to_tier TEXT, amount_usd NUMERIC, status TEXT, created_at TIMESTAMPTZ DEFAULT NOW())"""


def log(*a):
    print(*a, file=sys.stderr)


class UpgradeError(Exception):
    """A reason to show the member as is."""


# ---------- the emailed link ----------

def sign(email):
    payload = base64.urlsafe_b64encode(json.dumps({"m": email, "e": int(time.time()) + LINK_TTL}).encode()).decode().rstrip("=")
    return payload + "." + hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify(token):
    try:
        payload, sig = (token or "").rsplit(".", 1)
        if not hmac.compare_digest(sig, hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()):
            return None
        d = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return d["m"] if d.get("e", 0) > time.time() else None
    except Exception:
        return None


def link(email):
    return SITE + "/upgrade?t=" + sign(email)


# ---------- prices ----------

def _ts(iso):
    try:
        return datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tier_plans(cur):
    """{tier: {plan, product, price, period}} for the plans new buyers get, from Whop."""
    out = {}
    for tier in W.PRODUCTS:
        pid = W.plan_id(cur, tier)
        if not pid:
            continue
        p = W.whop("GET", "/api/v1/plans/" + pid)
        prod = p.get("product") if isinstance(p.get("product"), dict) else {}
        out[tier] = {"plan": pid, "product": prod.get("id") or p.get("product_id"),
                     "price": _num(p.get("renewal_price")), "period": p.get("billing_period"),
                     "title": p.get("title") or ""}
    return out


def current(cur, email, plans):
    """The member's highest active TradeVault membership: (membership dict, tier)."""
    by_product = {v["product"]: t for t, v in plans.items() if v.get("product")}
    best = None
    for mid in W.membership_ids(cur, email):
        m = W.whop("GET", "/api/v1/memberships/" + mid)
        prod = m.get("product_id") or (m["product"].get("id") if isinstance(m.get("product"), dict) else None)
        tier = by_product.get(prod)
        if tier and str(m.get("status")) in OK_STATUS and (best is None or W.RANK[tier] > W.RANK[best[1]]):
            best = (m, tier)
    return best


def quote(cur, email):
    """What this member can upgrade to and what it costs. Raises UpgradeError with a reason."""
    plans = tier_plans(cur)
    found = current(cur, email, plans)
    if not found:
        raise UpgradeError("We couldn't find an active Trade Vault plan on this email. If you joined with a different email, use that one, or email support@thetradevault.co.")
    m, tier = found
    paying = _num(m.get("renewal_price"))
    if paying is None:
        paying = _num(m.get("initial_price"))
    renews = _ts(m.get("current_period_end"))
    period = m.get("billing_period_days")
    now = datetime.datetime.now(datetime.timezone.utc)
    if paying is None or not renews or renews <= now or not period or not 27 <= int(period) <= 31:
        raise UpgradeError("Your plan can't be upgraded online. Email support@thetradevault.co and we'll sort it for you.")
    days = max(1, math.ceil((renews - now).total_seconds() / 86400))
    options = []
    for t, p in plans.items():
        if W.RANK[t] <= W.RANK[tier] or not p.get("price") or not p.get("product"):
            continue
        if not p.get("period") or not 27 <= int(p["period"]) <= 31:
            continue
        options.append({"tier": t, "name": NAMES[t], "today": round(max(1.0, p["price"] - paying), 2),
                        "monthly": round(p["price"], 2), "plan": p})
    return {"membership": m, "tier": tier, "name": NAMES[tier], "paying": round(paying, 2),
            "renews": renews.isoformat(), "days": days, "options": options}


def public(q):
    """The quote as the upgrade page shows it."""
    return {"current": {"tier": q["tier"], "name": q["name"], "paying": q["paying"], "renews": q["renews"]},
            "options": [{k: o[k] for k in ("tier", "name", "today", "monthly")} for o in q["options"]]}


def checkout(cur, email, tier):
    """A Whop checkout for the upgrade -> purchase URL."""
    q = quote(cur, email)
    opt = next((o for o in q["options"] if o["tier"] == tier), None)
    if not opt:
        raise UpgradeError("That upgrade isn't available on your plan.")
    m = q["membership"]
    meta = {k: str(v) for k, v in (m.get("metadata") or {}).items()} if isinstance(m.get("metadata"), dict) else {}
    meta.update({"tv_tier": tier, "tv_upgrade_from": m["id"], "tv_upgrade_old_tier": q["tier"]})
    if tier == "elite":
        meta.update({"tv_scanners": W.ALL_SCANNERS, "tv_educator": "all"})
    renews = _ts(q["renews"]).strftime("%-d %b")
    cfg = W.whop("POST", "/api/v1/checkout_configurations", {
        "mode": "payment",
        "redirect_url": SITE + "/setup",
        "metadata": meta,
        "variant": {
            "product_id": opt["plan"]["product"],
            "billing_type": "renewal",
            "billing_period": int(opt["plan"]["period"]),
            "currency": "usd",
            "initial_price": opt["today"],
            "renewal_price": opt["monthly"],
            "trial_period_days": q["days"],
            "title": ("Upgrade to " + NAMES[tier])[:30],
            "description": ("Upgrade from %s: $%s today (the difference), then $%s/month from %s, your usual billing date. "
                            "Your %s plan is cancelled automatically, so you're never billed twice.")
                           % (q["name"], _money(opt["today"]), _money(opt["monthly"]), renews, q["name"]),
            "visibility": "hidden",
            "release_method": "buy_now",
            "stock": 1,
            "unlimited_stock": False,
            "force_create_new_plan": True,
        },
    })
    url = cfg.get("purchase_url") or ""
    if url.startswith("/"):
        url = "https://whop.com" + url
    if not url.startswith("https://"):
        log("TV_UPGRADE_NO_URL", json.dumps(cfg)[:300])
        raise UpgradeError("Couldn't open checkout. Please try again in a minute.")
    log("TV_UPGRADE_CHECKOUT", email, q["tier"], "->", tier, opt["today"], cfg.get("id"))
    return url


def _money(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


# ---------- after payment (whop-hook) ----------

def finish(cur, payment, email):
    """The upgrade was paid: cancel the old membership now. Safe to run twice."""
    meta = payment.get("metadata") if isinstance(payment.get("metadata"), dict) else {}
    old, to_tier, from_tier = meta.get("tv_upgrade_from"), meta.get("tv_upgrade_tier") or meta.get("tv_tier"), meta.get("tv_upgrade_old_tier")
    pay_id = str(payment.get("id") or "")
    if not (old and pay_id):
        return
    cur.execute(TABLE)
    cur.execute("SELECT status FROM tv_upgrades WHERE payment_id = %s", (pay_id,))
    row = cur.fetchone()
    if row and row[0] == "done":
        return
    # Only the member who owns the old plan can cancel it by upgrading.
    cur.execute("SELECT email FROM tv_payments WHERE membership_id = %s LIMIT 1", (old,))
    owner = cur.fetchone()
    status = "done"
    try:
        m = W.whop("GET", "/api/v1/memberships/" + old)
        user = payment.get("user") if isinstance(payment.get("user"), dict) else {}
        same_user = bool(m.get("user_id") and m.get("user_id") == (user.get("id") or payment.get("user_id")))
        if not (same_user or (owner and owner[0].lower() == email.lower())):
            status = "owner_mismatch"
            log("TV_UPGRADE_MISMATCH", pay_id, email, old)
        elif str(m.get("status")) in W.VALID:
            W.whop("POST", "/api/v1/memberships/%s/cancel" % old,
                   {"cancel_at_period_end": False, "reason": "Upgraded to %s (payment %s)" % (to_tier, pay_id)})
    except Exception as e:
        status = "cancel_failed"
        log("TV_UPGRADE_CANCEL_ERR", pay_id, old, e)
    if status == "done" and from_tier == "tools":
        _redo_setup(email)
    cur.execute("""INSERT INTO tv_upgrades (payment_id, email, old_membership, from_tier, to_tier, amount_usd, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (payment_id) DO UPDATE SET status = EXCLUDED.status""",
                (pay_id, email, old, from_tier, to_tier, _num(payment.get("usd_total") or payment.get("total")), status))
    log("TV_UPGRADE", pay_id, email, from_tier, "->", to_tier, status)


def _redo_setup(email):
    """Take off the setup-complete tag so /setup asks for the new tier's choices."""
    import _tv_aff as A
    if not A.GHL_API_KEY:
        return
    try:
        cid = A._ghl_contact(email)
        if cid:
            A._ghl("DELETE", "/contacts/%s/tags" % cid, {"tags": ["tv-setup-complete"]})
    except Exception as e:
        log("TV_UPGRADE_SETUP_TAG_ERR", e)


def promo_codes():
    """The account's promo codes, for the admin check that coupons work on upgrades."""
    out, after = [], None
    for _ in range(5):
        page = W.whop("GET", "/api/v1/promo_codes?account_id=%s&first=50%s" % (W.WHOP_COMPANY, "&after=" + after if after else ""))
        for p in page.get("data") or []:
            prod = p.get("product") if isinstance(p.get("product"), dict) else {}
            out.append({k: p.get(k) for k in ("code", "status", "promo_type", "amount_off", "new_users_only",
                                              "existing_memberships_only", "churned_users_only", "one_per_customer",
                                              "expires_at", "duration", "promo_duration_months")}
                       | {"product": prod.get("title") or prod.get("id")})
        info = page.get("page_info") or {}
        after = info.get("end_cursor")
        if not (info.get("has_next_page") and after):
            break
    return out
