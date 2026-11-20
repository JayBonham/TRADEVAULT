"""Trade Vault webinar calendar invite.

Adds a registrant as a guest on that night's Google Calendar event (_tv_gcal.py, when GOOGLE_SA_JSON and
GOOGLE_CAL_USER are set), so Google sends the real invite. Otherwise emails a calendar invite (iCalendar
METHOD:REQUEST, sent through Brevo) for their webinar session. Gmail shows it as an invite and adds it to Google Calendar; Apple Mail / iCloud and Outlook show
Accept / Decline. Every session has a stable UID, so sending again for the same night updates the same event.

Used by:
  - api/tv-cal-invite.py  (GHL workflow webhook on the tv-webinar-registered tag, or a manual test)
  - api/jb-webinar.py     (straight after a signup on thetradevault.co/webinar)
Each email + session is only sent once (jb_webinar_invites).
"""
import base64
import http.client
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
FROM_EMAIL = os.environ.get("ADMIN_FROM_EMAIL", "info@jaybonham.com")
FROM_NAME = "Jay Bonham"
ET = ZoneInfo("America/New_York")

# keep in step with public/tradevault/webinar/tv-schedule.js
TITLE = "Trade with 3 Rules: Free Live Training with Jay Bonham"
HOUR, MINUTE, DURATION_MIN, LIVE_WINDOW_MIN, WEEKDAY = 20, 0, 60, 75, 3  # Thursday (Mon=0)
ZOOM = "https://us06web.zoom.us/j/82468528057?pwd=PnVamNOtXbXuQUGooIsnWyKr8pexAD.1"
ZOOM_ID, ZOOM_PASS = "824 6852 8057", "316277"
# a session that was moved: people tagged for the old date get the invite for the new one
MOVED = {"2026-11-19": "2026-11-20"}

TAG_RE = re.compile(r"^tv-webinar-(\d{4}-\d{2}-\d{2})$")


def log(*a):
    print(*a, file=sys.stderr)


def session_start(day):
    """'YYYY-MM-DD' (ET) -> aware UTC datetime of that night's start."""
    y, m, d = map(int, day.split("-"))
    return datetime(y, m, d, HOUR, MINUTE, tzinfo=ET).astimezone(timezone.utc)


def next_session(now=None):
    now = now or datetime.now(timezone.utc)
    d = now.astimezone(ET).date()
    while True:
        if d.weekday() == WEEKDAY:
            s = session_start(d.isoformat())
            if s + timedelta(minutes=LIVE_WINDOW_MIN) > now:
                return d.isoformat()
        d += timedelta(days=1)


def pick_session(tags, now=None):
    """The latest upcoming session from the contact's tv-webinar-YYYY-MM-DD tags (after MOVED), else the next one."""
    now = now or datetime.now(timezone.utc)
    days = []
    for t in tags or []:
        m = TAG_RE.match((t or "").strip().lower())
        if m:
            days.append(MOVED.get(m.group(1), m.group(1)))
    live = [d for d in days if session_start(d) + timedelta(minutes=LIVE_WINDOW_MIN) > now]
    return max(live) if live else next_session(now)


# ── iCalendar ────────────────────────────────────────────────
def _esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    out, b = [], line.encode()
    while len(b) > 74:
        cut = 74
        while (b[cut] & 0xC0) == 0x80:  # don't split a UTF-8 character
            cut -= 1
        out.append(b[:cut].decode())
        b = b" " + b[cut:]
    out.append(b.decode())
    return "\r\n".join(out)


def description():
    return ("Jay Bonham breaks down his 3-rule setup (trend, Point of Control, the signal) on real charts, live.\n\n"
            "Join on Zoom: " + ZOOM + "\nMeeting ID: " + ZOOM_ID + "\nPasscode: " + ZOOM_PASS +
            "\n\nJoin a few minutes early. You may be held in the waiting room for a moment.")


def ics(day, name, email):
    start = session_start(day)
    end = start + timedelta(minutes=DURATION_MIN)
    f = lambda dt: dt.strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "PRODID:-//The Trade Vault//Webinar//EN", "VERSION:2.0", "CALSCALE:GREGORIAN", "METHOD:REQUEST",
        "BEGIN:VEVENT",
        "UID:tv-webinar-" + day + "@thetradevault.co",
        "DTSTAMP:" + f(datetime.now(timezone.utc)),
        "DTSTART:" + f(start), "DTEND:" + f(end),
        "SEQUENCE:0", "STATUS:CONFIRMED", "TRANSP:OPAQUE",
        "SUMMARY:" + _esc(TITLE),
        "LOCATION:" + _esc(ZOOM),
        "URL:" + ZOOM,
        "DESCRIPTION:" + _esc(description()),
        "ORGANIZER;CN=" + _esc(FROM_NAME) + ":mailto:" + FROM_EMAIL,
        "ATTENDEE;CN=" + _esc(name or email) + ";ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:" + email,
        "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:" + _esc(TITLE), "TRIGGER:-PT60M", "END:VALARM",
        "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:" + _esc(TITLE), "TRIGGER:-PT10M", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"


def gcal_link(day):
    import urllib.parse
    start = session_start(day)
    f = lambda dt: dt.strftime("%Y%m%dT%H%M%SZ")
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode({
        "action": "TEMPLATE", "text": TITLE, "dates": f(start) + "/" + f(start + timedelta(minutes=DURATION_MIN)),
        "details": description(), "location": ZOOM})


def when_text(day):
    s = session_start(day).astimezone(ET)
    return s.strftime("%A, %b ") + str(s.day) + " · " + s.strftime("%-I:%M %p").lstrip("0") + " ET"


def email_html(day, first):
    w = when_text(day)
    hi = ("Hey " + first + ",") if first else "Hey,"
    font = "font-family:Inter,Helvetica,Arial,sans-serif;"
    btn = lambda href, label, bg, fg: (
        '<a href="%s" style="display:inline-block;padding:14px 26px;%sfont-size:16px;font-weight:700;color:%s;'
        'background:%s;text-decoration:none;border-radius:10px;margin:0 6px 10px 0;">%s</a>' % (href, font, fg, bg, label))
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#060B16;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#060B16;"><tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;">
<tr><td align="center" style="padding:6px 0 22px;"><img src="https://thetradevault.co/assets/tv-logo.png" width="190" alt="The Trade Vault" style="display:block;width:190px;height:auto;border:0;"></td></tr>
<tr><td style="background:#0C1424;border:1px solid #1C2940;border-radius:16px;padding:30px 30px 26px;{font}">
  <div style="color:#4B9EFF;font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">Your calendar invite</div>
  <h1 style="margin:10px 0 0;color:#EAF0FA;font-size:26px;line-height:1.25;font-weight:700;">You're in. It's in your calendar.</h1>
  <p style="margin:16px 0 0;color:#B3C0D4;font-size:16px;line-height:1.6;">{hi} this email is your calendar invite for the free live training. Tap <b style="color:#EAF0FA;">Yes / Accept</b> on the invite (if your email app doesn't add it automatically) and you'll get a reminder before we start.</p>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:22px;background:#0F1B30;border:1px solid #23406B;border-radius:12px;"><tr><td style="padding:20px 22px;{font}">
    <div style="color:#EAF0FA;font-size:18px;font-weight:700;">{TITLE}</div>
    <div style="color:#EAF0FA;font-size:15px;font-weight:600;margin-top:10px;">{w}</div>
    <div style="color:#7F8DA3;font-size:13px;margin-top:6px;">Zoom · Meeting ID {ZOOM_ID} · Passcode {ZOOM_PASS}</div>
  </td></tr></table>
  <div style="margin-top:22px;">{btn(ZOOM, "Join on Zoom &rarr;", "#4B9EFF", "#06101F")}{btn(gcal_link(day).replace("&", "&amp;"), "Add to Google Calendar", "#16233A", "#EAF0FA")}</div>
  <p style="margin:8px 0 0;color:#7F8DA3;font-size:13px;line-height:1.6;">On iPhone or Outlook, open the attached invite.ics to add it.</p>
  <p style="margin:22px 0 0;color:#EAF0FA;font-size:16px;">See you there,<br><b>Jay</b></p>
</td></tr>
<tr><td style="padding:22px 20px 8px;{font}color:#5D6B82;font-size:11px;line-height:1.6;text-align:center;">Trading carries a substantial risk of loss. Educational content only, not financial advice.<br>&copy; 2026 The Trade Vault &middot; <a href="https://thetradevault.co" style="color:#7F8DA3;">thetradevault.co</a></td></tr>
</table></td></tr></table></body></html>'''


# ── once per email + session ────────────────────────────────
def _db():
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS jb_webinar_invites (
        email TEXT NOT NULL, session_day DATE NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (email, session_day))""")
    return conn, cur


def already_sent(email, day):
    if not DATABASE_URL:
        return False
    try:
        conn, cur = _db()
        cur.execute("SELECT 1 FROM jb_webinar_invites WHERE email=%s AND session_day=%s", (email, day))
        hit = cur.fetchone() is not None
        conn.commit(); conn.close()
        return hit
    except Exception as e:
        log("TV_INVITE_DB:", e)
        return False


def mark_sent(email, day):
    if not DATABASE_URL:
        return
    try:
        conn, cur = _db()
        cur.execute("INSERT INTO jb_webinar_invites (email, session_day) VALUES (%s,%s) ON CONFLICT DO NOTHING", (email, day))
        conn.commit(); conn.close()
    except Exception as e:
        log("TV_INVITE_DB:", e)


def send(email, name="", day=None, force=False):
    """Send the invite. Returns (ok, info)."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return False, "no email"
    day = day or next_session()
    if not force and already_sent(email, day):
        return True, "already sent for " + day
    # Google Calendar first (the real invite, auto-added in Gmail); the emailed .ics is the fallback
    try:
        import _tv_gcal as gcal
        if gcal.enabled():
            ok, info = gcal.add_guest(sys.modules[__name__], day, email, name)
            log("TV_INVITE_GCAL", day, info)
            if ok:
                mark_sent(email, day)
                return True, info + " for " + day
    except Exception as e:
        log("TV_INVITE_GCAL_ERR:", e)
    if not BREVO_API_KEY:
        return False, "BREVO_API_KEY not set"
    first = (name or "").strip().split(" ")[0][:40]
    payload = {
        "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
        "to": [{"email": email, "name": (name or email)[:80]}],
        "subject": "Invitation: " + TITLE.split(":")[0] + " · " + when_text(day),
        "htmlContent": email_html(day, first),
        "attachment": [{"name": "invite.ics", "content": base64.b64encode(ics(day, name, email).encode()).decode()}],
        "tags": ["tv-webinar-invite"],
    }
    try:
        c = http.client.HTTPSConnection("api.brevo.com", timeout=10)
        c.request("POST", "/v3/smtp/email", json.dumps(payload),
                  {"accept": "application/json", "content-type": "application/json", "api-key": BREVO_API_KEY})
        r = c.getresponse()
        body = r.read().decode()[:300]
        if r.status >= 300:
            log("TV_INVITE_BREVO:", r.status, body)
            return False, "brevo %s" % r.status
    except Exception as e:
        log("TV_INVITE_ERR:", e)
        return False, "send failed"
    mark_sent(email, day)
    log("TV_INVITE_SENT", day)
    return True, "sent for " + day
