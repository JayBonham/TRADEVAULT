"""Setup reminders: members who bought but haven't filled in thetradevault.co/setup get emailed (from Jay, via Brevo).

GET (Vercel cron, hourly; or an admin token)   ?dry=1 lists who would get what without sending.
  Stage 1: 24h after purchase      "your access is waiting on you"
  Stage 2: 48h after purchase      "still need your TradingView username"
  Stage 3: free-trial members only, 4 days in ("3 days left on your trial")
Each stage once per member (tv_setup_nudges), at least 20h apart, only for purchases in the last 21 days.
Before sending, the GHL contact is read live: anyone with tv-setup-complete / tv-setup-trial, tv-hidden, or no
tradevault-purchased tag is skipped. Each send tags the contact tv-setup-nudge-<n> (visible on the members board).
"""
import datetime
import http.client
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token  # noqa: E402
import _tv_db  # noqa: E402

GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
FROM_EMAIL = os.environ.get("ADMIN_FROM_EMAIL", "info@jaybonham.com")
FROM_NAME = "Jay Bonham"
DONE_TAGS = ("tv-setup-complete", "tv-setup-trial")
H = 3600
STAGES = ((1, 24 * H, False), (2, 48 * H, False), (3, 96 * H, True))  # (stage, after purchase, trial only)
MAX_AGE = 21 * 86400
GAP = 20 * H
PER_RUN = 40

TABLE = """CREATE TABLE IF NOT EXISTS tv_setup_nudges (
    contact_id TEXT NOT NULL, stage INT NOT NULL, email TEXT, sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (contact_id, stage))"""


def log(*a):
    print(*a, file=sys.stderr)


def _ghl(method, path, body=None):
    c = http.client.HTTPSConnection("services.leadconnectorhq.com", timeout=10)
    c.request(method, path, json.dumps(body) if body is not None else None,
              {"Authorization": "Bearer " + GHL_API_KEY, "Version": "2021-07-28",
               "Content-Type": "application/json", "Accept": "application/json"})
    r = c.getresponse()
    raw = r.read()
    try:
        return r.status, json.loads(raw or b"{}")
    except ValueError:
        return r.status, {}


# ── email ────────────────────────────────────────────────────────────────────
def _html(first, link, trial, stage, days_left):
    font = "font-family:Inter,Helvetica,Arial,sans-serif;"
    hi = ("Hey " + first + ",") if first else "Hey,"
    if trial and stage == 3:
        kicker, h1 = "%d days left on your free trial" % days_left, "Your scanners still aren't switched on"
        lead = ("%s you're %d days into your free Elite trial, but we still can't give you your access, because your "
                "setup page isn't filled in yet. Don't let the trial run out before you've used it." % (hi, 7 - days_left))
    elif trial:
        kicker, h1 = "Your 7-day free trial has started", "Your access is waiting on you"
        lead = ("%s your free Elite trial is running, but we can't switch your access on until you fill in your "
                "setup page. The 7 days count from when you joined, so do it now and use every one of them." % hi)
    elif stage == 2:
        kicker, h1 = "One step left", "We still need your TradingView username"
        lead = ("%s you're a Trade Vault member, but your scanners aren't on your charts yet. We add them by your "
                "TradingView username, and you haven't sent it to us yet." % hi)
    else:
        kicker, h1 = "Welcome to The Trade Vault", "Your access is waiting on you"
        lead = ("%s you're in, but we can't switch your access on until you fill in your setup page." % hi)
    gets = ("<li>Killshot, Smartshot and Spectrum on your TradingView charts</li>"
            "<li>5 live sessions a week with Jay, Adam, Tyler and Andrew</li>"
            "<li>The Trade Vault community Telegram</li>") if trial else \
           ("<li>Your scanners added to your TradingView charts</li>"
            "<li>Your Telegram groups</li>")
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#060B16;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#060B16;"><tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;">
<tr><td align="center" style="padding:6px 0 22px;"><img src="https://thetradevault.co/assets/tv-logo.png" width="190" alt="The Trade Vault" style="display:block;width:190px;height:auto;border:0;"></td></tr>
<tr><td style="background:#0C1424;border:1px solid #1C2940;border-radius:16px;padding:30px 30px 26px;{font}">
  <div style="color:#4B9EFF;font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">{kicker}</div>
  <h1 style="margin:10px 0 0;color:#EAF0FA;font-size:26px;line-height:1.25;font-weight:700;">{h1}</h1>
  <p style="margin:16px 0 0;color:#B3C0D4;font-size:16px;line-height:1.6;">{lead}</p>
  <p style="margin:16px 0 0;color:#B3C0D4;font-size:16px;line-height:1.6;">It takes about a minute: your <b style="color:#EAF0FA;">TradingView username</b> and your <b style="color:#EAF0FA;">Telegram username</b>. Once it's in, we get you:</p>
  <ul style="margin:10px 0 0;padding-left:20px;color:#EAF0FA;font-size:15px;line-height:1.8;">{gets}</ul>
  <div style="margin-top:24px;"><a href="{link}" style="display:inline-block;padding:15px 28px;{font}font-size:16px;font-weight:700;color:#06101F;background:#4B9EFF;text-decoration:none;border-radius:10px;">Finish my setup &rarr;</a></div>
  <p style="margin:18px 0 0;color:#7F8DA3;font-size:13px;line-height:1.6;">Stuck, or don't have TradingView yet? Just reply to this email and we'll sort it.</p>
  <p style="margin:22px 0 0;color:#EAF0FA;font-size:16px;">Jay</p>
</td></tr>
<tr><td style="padding:22px 20px 8px;{font}color:#5D6B82;font-size:11px;line-height:1.6;text-align:center;">Trading carries a substantial risk of loss. Educational content only, not financial advice.<br>&copy; 2026 The Trade Vault &middot; <a href="https://thetradevault.co" style="color:#7F8DA3;">thetradevault.co</a></td></tr>
</table></td></tr></table></body></html>'''


def _subject(first, trial, stage, days_left):
    f = (first + ", ") if first else ""
    if trial and stage == 3:
        return "%d days left on your trial (your scanners aren't on yet)" % days_left
    if trial:
        return f + "your free trial is running, finish your setup"
    if stage == 2:
        return f + "we still need your TradingView username"
    return f + "your Trade Vault access is waiting on you"


def _send(email, name, subject, html):
    c = http.client.HTTPSConnection("api.brevo.com", timeout=10)
    c.request("POST", "/v3/smtp/email", json.dumps({
        "sender": {"name": FROM_NAME, "email": FROM_EMAIL}, "replyTo": {"email": FROM_EMAIL, "name": FROM_NAME},
        "to": [{"email": email, "name": (name or email)[:80]}], "subject": subject, "htmlContent": html,
        "tags": ["tv-setup-nudge"]}),
        {"accept": "application/json", "content-type": "application/json", "api-key": BREVO_API_KEY})
    r = c.getresponse()
    body = r.read().decode(errors="replace")[:200]
    return r.status < 300, "brevo %s %s" % (r.status, body) if r.status >= 300 else "sent"


# ── run ──────────────────────────────────────────────────────────────────────
def run(dry):
    now = datetime.datetime.now(datetime.timezone.utc)
    conn, cur = _tv_db._conn()
    cur.execute(TABLE)
    conn.commit()
    cur.execute("""SELECT contact_id, email, purchased_at FROM tv_members
                   WHERE setup_at IS NULL AND ended_at IS NULL AND purchased_at IS NOT NULL
                     AND purchased_at > NOW() - make_interval(secs => %s) AND purchased_at < NOW() - interval '24 hours'
                   ORDER BY purchased_at""", (MAX_AGE,))
    rows = cur.fetchall()
    cur.execute("SELECT contact_id, stage, sent_at FROM tv_setup_nudges")
    sent = {}
    for cid, st, at in cur.fetchall():
        sent.setdefault(cid, {})[st] = at
    out, n, looked = [], 0, 0
    for cid, email, bought in rows:
        age = (now - bought).total_seconds()
        mine = sent.get(cid, {})
        if 0 in mine:  # already found set up in GHL: never look again
            continue
        last = max(mine.values()) if mine else None
        if last and (now - last).total_seconds() < GAP:
            continue
        due = [s for s, after, _t in STAGES if age >= after and s not in mine]
        if not due:
            continue
        if n >= PER_RUN or looked >= 120:
            break
        looked += 1
        status, d = _ghl("GET", "/contacts/" + cid)
        ct = d.get("contact") or {}
        tags = [t.lower() for t in ct.get("tags") or []]
        if status >= 300 or not ct:
            continue
        if any(t in tags for t in DONE_TAGS):
            if not dry:  # set up (before the DB tracked it): stage 0 marks them so they're not looked up again
                cur.execute("INSERT INTO tv_setup_nudges (contact_id, stage, email) VALUES (%s, 0, %s) ON CONFLICT DO NOTHING", (cid, email))
                conn.commit()
            continue
        if "tradevault-purchased" not in tags or "tv-hidden" in tags:
            continue
        trial = "tv-trial" in tags and "tv-trial-converted" not in tags
        due = [s for s in due if trial or not dict((x, t) for x, _a, t in STAGES)[s]]
        if not due:
            continue
        stage = due[-1]  # skip straight to the latest stage they're due (no double email on catch-up)
        to = ct.get("email") or email
        name = (ct.get("firstName") or ct.get("contactName") or "").strip()
        first = name.split(" ")[0].title()[:40] if name else ""
        days_left = max(1, 7 - int(age // 86400))
        link = "https://thetradevault.co/setup?c=" + cid
        item = {"email": to, "stage": stage, "trial": trial, "hours": int(age // 3600)}
        if dry:
            item["subject"] = _subject(first, trial, stage, days_left)
            out.append(item)
            continue
        ok, why = _send(to, name, _subject(first, trial, stage, days_left), _html(first, link, trial, stage, days_left))
        item["result"] = why
        out.append(item)
        if ok:
            n += 1
            for s in [x for x in due if x <= stage]:  # a catch-up send covers the earlier stages too
                cur.execute("INSERT INTO tv_setup_nudges (contact_id, stage, email) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (cid, s, to))
            conn.commit()
            _ghl("POST", "/contacts/" + cid + "/tags", {"tags": ["tv-setup-nudge-%d" % stage]})
            log("TV_NUDGE_SENT", cid, stage)
        else:
            log("TV_NUDGE_FAIL", cid, why)
    conn.close()
    return out


class handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        bearer = auth[7:] if auth.startswith("Bearer ") else ""
        secret = os.environ.get("CRON_SECRET", "")
        ok = (secret and bearer == secret) or (bearer and verify_token(bearer)) \
            or (not secret and "vercel-cron" in (self.headers.get("User-Agent") or ""))
        if not ok:
            return self._json(401, {"ok": False, "error": "unauthorized"})
        if not (GHL_API_KEY and BREVO_API_KEY and _tv_db.DATABASE_URL):
            return self._json(500, {"ok": False, "error": "GHL_API_KEY / BREVO_API_KEY / DATABASE_URL missing"})
        dry = parse_qs(urlparse(self.path).query).get("dry", [""])[0] == "1"
        try:
            res = run(dry)
            self._json(200, {"ok": True, "dry": dry, "count": len(res), "items": res})
        except Exception as e:
            log("TV_NUDGE_ERR:", e)
            self._json(500, {"ok": False, "error": str(e)[:200]})

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())
