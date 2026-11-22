"""Ad attribution + Meta Conversions API (CAPI) for TradeVault.

- tv-checkout saves an ad click (utm_* / fbclid from the /trial page) in tv_ad_clicks and puts its id
  on the Whop checkout metadata as tv_click (plus tv_src / tv_ad), so whop-hook knows the signup came from an ad.
- whop-hook / tv-ads send StartTrial and Purchase server-side to the Meta dataset (pixel), matched on the
  buyer's hashed email/phone (+ fbc/fbp/ip/ua when the click was saved). Meta then shows trials and
  purchases against each ad in Ads Manager, including people whose browser blocked the pixel.

Every function here is best-effort: it logs and returns, and never raises into a checkout or webhook.
Env: META_CAPI_TOKEN (Events Manager > dataset > Settings > Conversions API > Generate access token),
optional META_PIXEL_ID (defaults to the site pixel). With no token, nothing is sent.
"""
import hashlib
import http.client
import json
import os
import re
import sys
import time
import uuid

PIXEL = os.environ.get("META_PIXEL_ID", "3566618163494760").strip()
TOKEN = os.environ.get("META_CAPI_TOKEN", "").strip()
GRAPH = "/v24.0/"
META_SOURCES = ("meta", "facebook", "fb", "instagram", "ig")


def log(*a):
    print(*a, file=sys.stderr)


def clip(v, n=120):
    return str(v or "").strip()[:n]


def slug(v):
    return re.sub(r"[^a-z0-9]+", "-", str(v or "").lower()).strip("-")[:40]


def is_meta(src, fbclid=""):
    return bool(fbclid) or slug(src) in META_SOURCES


def source_tags(meta):
    """GHL tags for a checkout's metadata: tv-src-meta-ads + tv-ad-<ad> for Meta ads, tv-src-<x> otherwise."""
    if not isinstance(meta, dict):
        return []
    src = slug(meta.get("tv_src"))
    if not src:
        return []
    tags = ["tv-src-meta-ads"] if src == "meta" else ["tv-src-" + src]
    ad = slug(meta.get("tv_ad"))
    if src == "meta" and ad:
        tags.append("tv-ad-" + ad)
    return tags


_trial_plan = {}


def is_trial_plan(pid):
    """Is this Whop plan id the 7-day trial plan (env TV_PLAN_ELITE_TRIAL, else the id tv-checkout remembered)?"""
    pid = str(pid or "").strip()
    if not pid:
        return False
    if "id" not in _trial_plan:
        _trial_plan["id"] = os.environ.get("TV_PLAN_ELITE_TRIAL", "").strip()
        if not _trial_plan["id"]:
            try:
                import _tv_aff
                c = _tv_aff.conn()
                cur = c.cursor()
                cur.execute("SELECT plan_id FROM tv_whop_plans WHERE tier = 'elite_trial'")
                r = cur.fetchone()
                c.close()
                _trial_plan["id"] = r[0] if r else ""
            except Exception as e:
                log("TV_META_TRIAL_PLAN_ERR", e)
                return False
    return pid == _trial_plan["id"]


def _ensure(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tv_ad_clicks (
            id TEXT PRIMARY KEY, src TEXT, medium TEXT, campaign TEXT, content TEXT,
            fbclid TEXT, fbc TEXT, fbp TEXT, ip TEXT, ua TEXT, ref TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
        CREATE TABLE IF NOT EXISTS tv_meta_events (
            event_id TEXT PRIMARY KEY, event_name TEXT, email TEXT, src TEXT, ad TEXT,
            value NUMERIC(10,2), status INT, sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
        CREATE TABLE IF NOT EXISTS tv_signup_src (
            email TEXT PRIMARY KEY, membership_id TEXT, kind TEXT, src TEXT, medium TEXT, campaign TEXT,
            ad TEXT, click_id TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
    """)


def save_click(cur, d):
    """d: src, medium, campaign, content, fbclid, fbc, fbp, ip, ua, ref. Returns the click id."""
    _ensure(cur)
    cid = uuid.uuid4().hex[:16]
    cur.execute("INSERT INTO tv_ad_clicks (id, src, medium, campaign, content, fbclid, fbc, fbp, ip, ua, ref) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (cid, clip(d.get("src"), 40), clip(d.get("medium"), 40), clip(d.get("campaign"), 80),
                 clip(d.get("content"), 80), clip(d.get("fbclid"), 400), clip(d.get("fbc"), 500),
                 clip(d.get("fbp"), 200), clip(d.get("ip"), 60), clip(d.get("ua"), 400), clip(d.get("ref"), 20)))
    return cid


def click(cur, cid):
    if not cid:
        return {}
    _ensure(cur)
    cur.execute("SELECT src, medium, campaign, content, fbc, fbp, ip, ua FROM tv_ad_clicks WHERE id = %s", (str(cid)[:40],))
    r = cur.fetchone()
    return dict(zip(("src", "medium", "campaign", "content", "fbc", "fbp", "ip", "ua"), r)) if r else {}


def remember_signup(cur, email, mem_id, kind, meta, clk):
    """First source wins: a later renewal or webhook retry only fills blanks, never overwrites how they came in."""
    _ensure(cur)
    meta = meta if isinstance(meta, dict) else {}
    cur.execute("INSERT INTO tv_signup_src (email, membership_id, kind, src, medium, campaign, ad, click_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (email) DO UPDATE SET "
                "membership_id = COALESCE(tv_signup_src.membership_id, EXCLUDED.membership_id), "
                "src = COALESCE(NULLIF(tv_signup_src.src, ''), EXCLUDED.src), "
                "campaign = COALESCE(NULLIF(tv_signup_src.campaign, ''), EXCLUDED.campaign), "
                "ad = COALESCE(NULLIF(tv_signup_src.ad, ''), EXCLUDED.ad), "
                "click_id = COALESCE(tv_signup_src.click_id, EXCLUDED.click_id)",
                (email, mem_id or None, kind, clip(meta.get("tv_src") or clk.get("src") or ("affiliate" if meta.get("tv_ref") else ""), 40),
                 clip(clk.get("medium"), 40), clip(meta.get("tv_campaign") or clk.get("campaign"), 80),
                 clip(meta.get("tv_ad") or clk.get("content"), 80), clip(meta.get("tv_click"), 40) or None))


def _h(v):
    v = (v or "").strip().lower()
    return hashlib.sha256(v.encode()).hexdigest() if v else None


def send(cur, event_name, event_id, email, phone="", name="", value=None, event_time=None, clk=None, src="", ad=""):
    """Send one event once (event_id is remembered in tv_meta_events). Returns a short status string."""
    if not (TOKEN and PIXEL and email and event_id):
        return "skipped"
    _ensure(cur)
    cur.execute("INSERT INTO tv_meta_events (event_id, event_name, email, src, ad, value) VALUES (%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (event_id) DO NOTHING RETURNING event_id",
                (event_id, event_name, email, clip(src, 40), clip(ad, 80), value))
    if not cur.fetchone():
        return "already sent"
    clk = clk or {}
    first, _, last = (name or "").strip().partition(" ")
    digits = re.sub(r"\D", "", phone or "")
    ud = {"em": [_h(email)], "external_id": [_h(email)]}
    if digits:
        ud["ph"] = [_h(digits)]
    if first:
        ud["fn"] = [_h(first)]
    if last:
        ud["ln"] = [_h(last.split(" ")[-1])]
    for k in ("fbc", "fbp"):
        if clk.get(k):
            ud[k] = clk[k]
    if clk.get("ip"):
        ud["client_ip_address"] = clk["ip"]
    if clk.get("ua"):
        ud["client_user_agent"] = clk["ua"]
    ev = {"event_name": event_name, "event_time": int(event_time or time.time()), "event_id": event_id,
          "action_source": "website", "event_source_url": "https://thetradevault.co/trial", "user_data": ud,
          "custom_data": {"currency": "USD", "value": float(value or 0), "content_name": "TradeVault Elite"}}
    if event_name == "StartTrial":
        ev["custom_data"]["predicted_ltv"] = 124.99
    status = 0
    try:
        c = http.client.HTTPSConnection("graph.facebook.com", timeout=6)
        c.request("POST", GRAPH + PIXEL + "/events", json.dumps({"data": [ev], "access_token": TOKEN}),
                  {"Content-Type": "application/json"})
        r = c.getresponse()
        status = r.status
        body = r.read()[:300]
        log("TV_META_CAPI", event_name, event_id, status, body)
    except Exception as e:
        log("TV_META_CAPI_ERR", event_name, event_id, e)
    cur.execute("UPDATE tv_meta_events SET status = %s WHERE event_id = %s", (status, event_id))
    if status >= 300 or not status:
        # Not sent: forget it so the next sync (tv-ads) retries.
        cur.execute("DELETE FROM tv_meta_events WHERE event_id = %s", (event_id,))
        return "error %s" % status
    return "sent"
