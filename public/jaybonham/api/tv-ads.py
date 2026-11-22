"""Black Friday trial: where each signup came from (admin Analytics > Trial signups).

Locked like analytics: admin token (Authorization: Bearer) + analytics password (X-Analytics-Pass).
Route: GET /api/tv-ads

Each call also catches up signups that happened before tracking existed (or that a webhook missed):
every Whop membership in its free trial gets the GHL tag tv-trial once, and a StartTrial event is sent
to Meta (CAPI, when META_CAPI_TOKEN is set) if it started within Meta's 7-day window. That lets Meta
match earlier signups to the people who clicked the ads.

-> {ok, capi: bool, meta_sent: n, rows: [{started, ends, cancelling, status, src, ad, campaign}] (no names/emails), by_ad: {ad: {clicks, trials}},
    caught_up: n, remaining: n}
"""
import datetime
import hashlib
import hmac
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token

# Same second lock as analytics / tv-pm (salted hash only; env TV_ANALYTICS_PASSWORD replaces it when set).
PASS_SALT = "1cd0c4abafd232acb8a6124e4e3ba085"
PASS_HASH = "a784bb07a38b075cb9d8d316dcf961c49448e6d3c3bc4686703477a07d31f129"


def pass_ok(given):
    given = (given or "").strip()
    env = os.environ.get("TV_ANALYTICS_PASSWORD", "")
    if env:
        return hmac.compare_digest(given.encode(), env.encode())
    h = hashlib.pbkdf2_hmac("sha256", given.encode(), bytes.fromhex(PASS_SALT), 300000).hex()
    return hmac.compare_digest(h, PASS_HASH)


STEP = 8  # catch-up work per call (GHL + Meta requests), so a call stays well inside the time limit


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _ts(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def trial_members():
    import _tv_whop as W
    import _jb_admin
    out, after = [], ""
    for _ in range(5):
        page = W.whop("GET", "/api/v1/memberships?account_id=%s&statuses=trialing&first=100%s"
                      % (W.WHOP_COMPANY, "&after=" + after if after else ""))
        for m in page.get("data") or []:
            if str(m.get("status") or "") != "trialing":
                continue
            email, name, _ = _jb_admin._who(m)
            if email:
                out.append({"id": str(m.get("id") or ""), "email": email, "name": name,
                            "started": _ts(m.get("created_at")),
                            "ends": _ts(m.get("renewal_period_end") or m.get("current_period_end")),
                            "cancelling": bool(m.get("cancel_at_period_end")),
                            "meta": m.get("metadata") if isinstance(m.get("metadata"), dict) else {}})
        info = page.get("page_info") or {}
        after = info.get("end_cursor") or ""
        if not (info.get("has_next_page") and after):
            break
    return out


class handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        if not (auth.startswith("Bearer ") and verify_token(auth[7:])):
            return self._json(401, {"ok": False, "error": "Unauthorized"})
        if not pass_ok(self.headers.get("X-Analytics-Pass")):
            return self._json(403, {"ok": False, "locked": True, "error": "Wrong password"})
        try:
            self._json(200, self._report())
        except Exception as e:
            log("TV_ADS_ERR:", e)
            self._json(500, {"ok": False, "error": str(e)[:300]})

    def _report(self):
        import _tv_aff
        import _tv_meta
        c = _tv_aff.conn()
        cur = c.cursor()
        _tv_meta._ensure(cur)
        c.commit()
        cur.execute("SELECT email FROM tv_signup_src")
        known = {r[0] for r in cur.fetchall()}
        trials = trial_members()
        done = left = 0
        for t in trials:
            if done >= STEP:
                left += 1
                continue
            work = False
            if t["email"] not in known:
                # Signed up before tracking (or the webhook missed it): tag + remember, source from Whop if any.
                _tv_aff.ghl_tag(t["email"], "", ["tv-trial"] + _tv_meta.source_tags(t["meta"]))
                _tv_meta.remember_signup(cur, t["email"], t["id"], "trial", t["meta"], {})
                known.add(t["email"])
                work = True
            if _tv_meta.TOKEN and t["id"] and t["started"] and time.time() - t["started"] < 6.9 * 86400:
                r = _tv_meta.send(cur, "StartTrial", "trial-" + t["id"], t["email"], "", t["name"], 0,
                                  event_time=t["started"], src=t["meta"].get("tv_src") or "", ad=t["meta"].get("tv_ad") or "")
                work = work or r == "sent"
            c.commit()
            done += 1 if work else 0

        # Signups with no source on the checkout: look them up in the game / webinar sign-ups and GHL, once each.
        cur.execute("SELECT r.email FROM tv_aff_referrals r")
        credited = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT email FROM tv_signup_src WHERE COALESCE(src, '') = '' AND traced_at IS NULL")
        traced = 0
        for (em,) in cur.fetchall():
            if em in credited:
                continue
            if done + traced >= STEP * 2:
                left += 1
                continue
            import _tv_trace
            t = _tv_trace.trace(cur, em)
            cur.execute("UPDATE tv_signup_src SET src = %s, ad = COALESCE(NULLIF(ad, ''), %s), campaign = COALESCE(NULLIF(campaign, ''), %s), "
                        "how = %s, traced_at = NOW() WHERE email = %s AND COALESCE(src, '') = ''",
                        ((t[0] if t else "") or "", (t[2] if t else "") or "", (t[3] if t else "") or "", (t[1] if t else "no record found"), em))
            c.commit()
            traced += 1

        cur.execute("SELECT email, kind, src, ad, campaign, created_at, how, traced_at FROM tv_signup_src ORDER BY created_at DESC LIMIT 500")
        src_by = {r[0]: r for r in cur.fetchall()}
        # Credited to an affiliate (checkout code, /setup or webinar link): that's where they came from.
        cur.execute("SELECT r.email, a.code FROM tv_aff_referrals r JOIN tv_affiliates a ON a.id = r.affiliate_id")
        aff_of = dict(cur.fetchall())
        live = {t["email"]: t for t in trials}
        rows = []
        for email in list(live) + [e for e in src_by if e not in live]:
            s = src_by.get(email)
            if not s and email not in live:
                continue
            if s and s[1] != "trial" and email not in live:
                continue
            t = live.get(email, {})
            rows.append({"started": t.get("started") or (s[5].timestamp() if s and s[5] else 0),
                         "ends": t.get("ends") or 0, "cancelling": bool(t.get("cancelling")),
                         "status": "in trial" if t else "ended / converted",
                         "src": (s[2] if s else "") or ("affiliate" if email in aff_of else ""),
                         "aff": aff_of.get(email, ""), "ad": (s[3] if s else "") or "",
                         "how": (s[6] if s else "") or "", "traced": bool(s and s[7]),
                         "campaign": (s[4] if s else "") or ""})
        rows.sort(key=lambda r: -r["started"])

        cur.execute("SELECT COALESCE(content, ''), COUNT(*) FROM tv_ad_clicks WHERE src = 'meta' GROUP BY 1")
        by_ad = {k or "(no ad name)": {"clicks": n, "trials": 0} for k, n in cur.fetchall()}
        for r in rows:
            if r["src"] == "meta":
                by_ad.setdefault(r["ad"] or "(no ad name)", {"clicks": 0, "trials": 0})["trials"] += 1
        cur.execute("SELECT COUNT(*) FROM tv_meta_events WHERE event_name = 'StartTrial' AND status < 300")
        sent = cur.fetchone()[0]
        c.close()
        return {"ok": True, "capi": bool(_tv_meta.TOKEN), "meta_sent": sent, "rows": rows, "by_ad": by_ad,
                "caught_up": done, "remaining": left}

    def _json(self, status, body):
        raw = json.dumps(body, separators=(",", ":"), default=str).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Analytics-Pass")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)
