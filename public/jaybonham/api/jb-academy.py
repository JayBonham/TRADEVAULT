"""Sniper Academy members area (page lives at jaybonham.com/academy). Route: /api/jb-academy?action=<action>

Members sign in with an emailed link: we check Whop for an active Sniper Fast Start / Accelerator /
Elite membership on that email, GHL emails the link (tag sniper-academy-login, field
sniper_academy_link), and the link swaps for a 30-day session. Videos stream from Whop's own
hosting (the Sniper Academy course), so Jay keeps uploading in Whop and the page follows.
Progress and lesson comments are ours (Postgres), keyed by Whop's lesson id.

  start      POST {email}             emails a login link if the email is a member (always says ok)
  login      POST {l}                 -> {session, email}: swaps an emailed link for a session
  course     GET  (Bearer session)    modules, lessons (with thumbnails), progress, comment counts
  lesson     GET  ?id= (Bearer)       one lesson: video stream, poster, notes, attachments
  progress   POST {id, pos?, done?, undo?}  (Bearer) where they are / lesson complete
  comments   GET  ?id= (Bearer)       a lesson's discussion
  comment    POST {id, body, parent?} (Bearer) post a comment or a reply
  uncomment  POST {cid}               (Bearer) take down your own comment (a coach: any)
  check      GET  ?email= (Bearer admin)  whether an email has access, and why
  members    GET  (Bearer admin session)  every Sniper member with progress and last seen
  profile    GET  ?email= (Bearer admin session)  one member: Whop plans, trader profile, GHL, progress
  allcomments GET (Bearer admin session)  every comment, newest first, for the admin Comments tab
  onboard    POST {item} (Bearer)      a setup step done: "cal:<call id>", "discord"
  profile_save POST {answers} (Bearer) the trader profile from the setup page: written to the member's
                                       GHL contact fields (the Trader Profile Form's own) + tag trader-profile-complete
  calls      GET  (Bearer admin)       every live call, for the admin Calls tab
  call_save  POST {call} (Bearer admin)  add / change a live call;  call_delete POST {id}
Live calls (Zoom links, passcodes) live in jb_academy_calls, never in this public repo, and only
go to signed-in members whose package the call is for, for that package's length (CALL_DAYS).
Progress counts lessons finished here or on Whop's own course page.

Admins (ADMINS below, plus env JB_ACADEMY_COACHES) always have access, see the Members area and
post with a Coach / Team badge. The jaybonham.com admin token also opens members/profile.
"""
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
import _jb_academy as J
import _tv_aff as A
import _tv_whop as W
import _jb_admin
from _auth import verify_token

COURSE = "cors_ubqXl5GzVJpMN"  # Whop course "Sniper Academy"
OK_STATUS = {"active", "trialing", "past_due", "completed"}
ADMINS = {"jay@jaybonham.com": ("Jay Bonham", "coach"), "alex@alexktaylor.com": ("Alex Taylor", "team")}
for _e in os.environ.get("JB_ACADEMY_COACHES", "").split(","):
    if _e.strip():
        ADMINS.setdefault(_e.strip().lower(), ("", "coach"))
COACHES = set(ADMINS)
MEMBER_CACHE = 600  # re-check Whop at most every 10 minutes per member (per warm instance)
COURSE_CACHE = 300
POSTS_PER_HOUR = 20
DISCORD = "https://discord.gg/vFBQacDYQ"
PROFILE_TAG = "trader-profile-complete"
# The Trader Profile Form's questions = its GHL contact fields (names exactly as in GHL). key, field, required
PROFILE_Q = (("how_long", "How long you've been trading?", True),
             ("markets", "What markets are you currently trading?", True),
             ("live_demo", "Are you currently trading live or demo?", True),
             ("tradingview", "What is your TradingView Username? (For Indicator Access)", True),
             ("accomplish", "What do you want to accomplish through Sniper Academy?", True),
             ("goals", "What are your short-term and long-term trading goals?", False),
             ("struggling", "Where do you feel like you're struggling?", True),
             ("frustrations", "What are your biggest frustrations and challenges?", False),
             ("style", "Describe your current trading style and strategies", False))
ONB_RE = re.compile(r"^(cal:\d{1,9}|discord)$")
# Live calls per package, in days from joining that package (the length of each programme).
CALL_DAYS = {"fast start": 30, "accelerator": 90, "elite": 180}
PLANS = tuple(CALL_DAYS)
CALL_FIELDS = ("title", "coach", "blurb", "weekday", "start_time", "tz", "minutes", "zoom_url", "meeting_id", "passcode", "ics_url",
               "active", "plans")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
ID_RE = re.compile(r"^[A-Za-z0-9_]{4,60}$")
TABLES = """
CREATE TABLE IF NOT EXISTS jb_academy_progress (
    email      TEXT NOT NULL,
    lesson_id  TEXT NOT NULL,
    pos        INTEGER NOT NULL DEFAULT 0,
    done       BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (email, lesson_id));
CREATE TABLE IF NOT EXISTS jb_academy_comments (
    id         BIGSERIAL PRIMARY KEY,
    lesson_id  TEXT NOT NULL,
    email      TEXT NOT NULL,
    parent_id  BIGINT,
    author     TEXT NOT NULL,
    role       TEXT,
    body       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ);
CREATE INDEX IF NOT EXISTS jb_academy_comments_lesson ON jb_academy_comments (lesson_id, created_at);
CREATE TABLE IF NOT EXISTS jb_academy_calls (
    id         BIGSERIAL PRIMARY KEY,
    title      TEXT NOT NULL,
    coach      TEXT NOT NULL DEFAULT '',
    blurb      TEXT NOT NULL DEFAULT '',
    weekday    INTEGER NOT NULL,            -- 0 Monday .. 6 Sunday
    start_time TEXT NOT NULL,               -- HH:MM in tz
    tz         TEXT NOT NULL DEFAULT 'America/Denver',
    minutes    INTEGER NOT NULL DEFAULT 60,
    zoom_url   TEXT NOT NULL DEFAULT '',
    meeting_id TEXT NOT NULL DEFAULT '',
    passcode   TEXT NOT NULL DEFAULT '',
    ics_url    TEXT NOT NULL DEFAULT '',
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
ALTER TABLE jb_academy_calls ADD COLUMN IF NOT EXISTS plans TEXT NOT NULL DEFAULT 'fast start,accelerator,elite';
CREATE TABLE IF NOT EXISTS jb_academy_onboarding (
    email   TEXT NOT NULL,
    item    TEXT NOT NULL,
    data    TEXT,
    done_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (email, item));
CREATE TABLE IF NOT EXISTS jb_academy_seen (
    email      TEXT PRIMARY KEY,
    logins     INTEGER NOT NULL DEFAULT 0,
    last_login TIMESTAMPTZ,
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT now());"""

_members = {}   # email -> (checked_at, ok, name, Whop user ids)
_titles = {}    # product id -> lowercased title
_course = {"at": 0, "data": None}
_ready = False


def log(*a):
    print(*a, file=sys.stderr)


def db():
    global _ready
    c = A.conn()
    if not _ready:
        c.cursor().execute(TABLES)
        c.commit()
        _ready = True
    return c


# ---------- access ----------

def _title(m):
    p = m.get("product") if isinstance(m.get("product"), dict) else {}
    pid = p.get("id") or m.get("product_id")
    if p.get("title"):
        _titles[pid] = " ".join(p["title"].lower().split())
    if pid and pid not in _titles:
        try:
            _titles[pid] = " ".join(str(W.whop("GET", "/api/v1/products/" + pid).get("title") or "").lower().split())
        except Exception as e:
            log("JB_ACADEMY_PRODUCT_ERR", pid, e)
            return ""
    return _titles.get(pid, "")


def sniper_memberships(cur, email):
    import _tv_upgrade as U  # Whop membership search by email (payment log + Whop's member search)
    return [m for m in U.memberships(cur, email) if J.is_course_product(_title(m))]


def _name_from(ms, email):
    for m in ms:
        u = m.get("user") if isinstance(m.get("user"), dict) else {}
        n = (u.get("name") or u.get("username") or "").strip()
        if n:
            return n[:60]
    local = email.split("@")[0].split("+")[0]
    return re.sub(r"[._\-\d]+", " ", local).strip().title()[:60] or "Member"


def _call_access(ms):
    """Live calls by package: {"fast start" | "accelerator" | "elite": access ends (iso)}, from when the
    member joined that package (CALL_DAYS). Admins get every package with no end."""
    import datetime
    out = {}
    for m in ms:
        t = _title(m)
        if str(m.get("status")) not in OK_STATUS or not t.startswith("sniper "):
            continue
        plan = t[len("sniper "):]
        if plan not in CALL_DAYS or not m.get("created_at"):
            continue
        try:
            start = datetime.datetime.fromisoformat(str(m["created_at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        until = (start + datetime.timedelta(days=CALL_DAYS[plan])).isoformat()
        out[plan] = max(out.get(plan, ""), until)
    return out


def _plans(v):
    return [p for p in PLANS if p in {x.strip().lower() for x in str(v or "").split(",")}]


_profile_checked = {}  # email -> when GHL last said "not yet" (don't ask GHL on every page load)


def _profile_in_ghl(email):
    """Filled in the Trader Profile Form (or the setup page) already: the tag, or its answers on the contact."""
    if time.time() - _profile_checked.get(email, 0) < MEMBER_CACHE:
        return False
    _profile_checked[email] = time.time()
    try:
        cid = A._ghl_contact(email)
        if not cid:
            return False
        st, d = A._ghl("GET", "/contacts/" + cid)
        ct = d.get("contact") or {}
        if PROFILE_TAG in [t.lower() for t in ct.get("tags") or []]:
            return True
        names = _jb_admin._field_names()
        want = {q.lower() for _, q, _ in PROFILE_Q}
        filled = [f for f in ct.get("customFields") or [] if (names.get(f.get("id")) or "").strip().lower() in want and f.get("value") not in (None, "")]
        return len(filled) >= 3
    except Exception as e:
        log("JB_ACADEMY_PROFILE_CHECK_ERR:", e)
        return False


def calls(cur, admin=False):
    cur.execute("SELECT id, " + ", ".join(CALL_FIELDS) + " FROM jb_academy_calls" + ("" if admin else " WHERE active") +
                " ORDER BY weekday, start_time")
    return [dict(zip(("id",) + CALL_FIELDS, r)) for r in cur.fetchall()]


def member(email, fresh=False):
    """(has access, display name), from Whop; cached per warm instance."""
    hit = _members.get(email)
    if hit and not fresh and time.time() - hit[0] < MEMBER_CACHE:
        return hit[1], hit[2]
    if email in ADMINS:
        _members[email] = (time.time(), True, ADMINS[email][0] or _name_from([], email), set(), {"admin": True})
        return True, _members[email][2]
    c = A.conn()
    try:
        ms = sniper_memberships(c.cursor(), email)
        c.commit()
    finally:
        c.close()
    ok = any(str(m.get("status")) in OK_STATUS for m in ms)
    _members[email] = (time.time(), ok, _name_from(ms, email), {_jb_admin.uid(m) for m in ms if _jb_admin.uid(m)}, _call_access(ms))
    return ok, _members[email][2]


# ---------- the course ----------

def _all(path):
    out, after = [], ""
    for _ in range(10):
        page = W.whop("GET", path + "&first=100" + ("&after=" + after if after else ""))
        out += page.get("data") or []
        info = page.get("page_info") or {}
        after = info.get("end_cursor") or ""
        if not (info.get("has_next_page") and after):
            break
    return out


def _lesson_raw(lid):
    try:
        return W.whop("GET", "/api/v1/course_lessons/" + lid)
    except Exception as e:
        log("JB_ACADEMY_LESSON_ERR", lid, e)
        return None


def _stream(v):
    """(HLS url, poster url) from a Whop video_asset: signed ids need their token, public ids play as is."""
    if not isinstance(v, dict):
        return "", ""
    if v.get("signed_playback_id") and v.get("signed_video_playback_token"):
        pid = v["signed_playback_id"]
        poster = ("https://image.mux.com/%s/thumbnail.jpg?token=%s" % (pid, v["signed_thumbnail_playback_token"])
                  if v.get("signed_thumbnail_playback_token") else "")
        return "https://stream.mux.com/%s.m3u8?token=%s" % (pid, v["signed_video_playback_token"]), poster
    if v.get("playback_id"):
        pid = v["playback_id"]
        return "https://stream.mux.com/%s.m3u8" % pid, "https://image.mux.com/%s/thumbnail.jpg?width=640" % pid
    return "", ""


def _thumb(l):
    t = l.get("thumbnail") if isinstance(l.get("thumbnail"), dict) else {}
    return t.get("url") or _stream(l.get("video_asset"))[1]


def course():
    if _course["data"] and time.time() - _course["at"] < COURSE_CACHE:
        return _course["data"]
    chapters = sorted(_all("/api/v1/course_chapters?course_id=" + COURSE), key=lambda c: c.get("order") or 0)

    def lessons(ch):
        ls = sorted(_all("/api/v1/course_lessons?chapter_id=" + str(ch.get("id"))), key=lambda l: l.get("order") or 0)
        return [l for l in ls if l.get("visibility", "visible") == "visible"]

    with ThreadPoolExecutor(8) as ex:
        per = list(ex.map(lessons, chapters))
    ids = [l["id"] for ls in per for l in ls]
    with ThreadPoolExecutor(8) as ex:  # full lessons: each video's length and thumbnail
        full = dict(zip(ids, ex.map(_lesson_raw, ids)))
    mods = []
    for ch, ls in zip(chapters, per):
        if not ls:
            continue
        out = []
        for l in ls:
            f = full.get(l["id"]) or {}
            v = f.get("video_asset") if isinstance(f.get("video_asset"), dict) else {}
            out.append({"id": l["id"], "title": l.get("title") or "", "thumb": _thumb(f),
                        "video": bool(v), "duration": int(v.get("duration_seconds") or 0)})
        mods.append({"id": ch.get("id"), "title": ch.get("title") or "", "lessons": out})
    data = {"title": "Sniper Academy", "chapters": mods}
    _course.update(at=time.time(), data=data)
    return data


def allowed(lid):
    return lid in {l["id"] for ch in course()["chapters"] for l in ch["lessons"]}


def lesson(lid):
    if not allowed(lid):  # only Sniper Academy lessons, never another course's
        return None
    l = _lesson_raw(lid) or {}
    v = l.get("video_asset") if isinstance(l.get("video_asset"), dict) else {}
    stream, poster = _stream(v)
    pdf = l.get("main_pdf") if isinstance(l.get("main_pdf"), dict) else {}
    files = [{"name": a.get("filename") or "File", "url": a.get("url")} for a in (l.get("attachments") or [])
             if isinstance(a, dict) and a.get("url")]
    if pdf.get("url"):
        files.insert(0, {"name": pdf.get("filename") or "Lesson PDF", "url": pdf["url"]})
    return {"id": lid, "title": l.get("title") or "", "content": l.get("content") or "",
            "stream": stream, "poster": _thumb(l) or poster,
            "duration": int(v.get("duration_seconds") or 0), "files": files}


# ---------- comments ----------

def thread(cur, lid, email):
    cur.execute("""SELECT id, parent_id, author, role, body, created_at, email FROM jb_academy_comments
                   WHERE lesson_id = %s AND deleted_at IS NULL ORDER BY created_at""", (lid,))
    coach = email in COACHES
    return [{"id": r[0], "parent": r[1], "author": r[2], "role": r[3], "body": r[4], "at": r[5].isoformat(),
             "mine": r[6] == email, "can_delete": r[6] == email or coach} for r in cur.fetchall()]


# ---------- handler ----------

class handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def do_GET(self):
        a = self._action()
        if a == "check":
            return self._check()
        if a in ("members", "profile", "allcomments", "calls", "ghlfields"):
            return self._admin_get(a)
        if a not in ("course", "lesson", "comments"):
            return self._json(404, {"error": "unknown action"})
        email = self._member()
        if not email:
            return
        try:
            if a == "course":
                data = dict(course())
                c = db()
                cur = c.cursor()
                cur.execute("SELECT lesson_id, pos, done FROM jb_academy_progress WHERE email = %s ORDER BY updated_at DESC", (email,))
                rows = cur.fetchall()
                cur.execute("SELECT lesson_id, count(*) FROM jb_academy_comments WHERE deleted_at IS NULL GROUP BY lesson_id")
                counts = dict(cur.fetchall())
                c.commit()
                c.close()
                data["progress"] = {r[0]: {"pos": r[1], "done": r[2]} for r in rows}
                hit = _members.get(email)
                for lid in _jb_admin.whop_done(hit[3] if hit and len(hit) > 3 else set())[0]:  # finished on Whop
                    data["progress"].setdefault(lid, {"pos": 0, "done": True})["done"] = True
                data["last"] = rows[0][0] if rows else None
                data["comments"] = counts
                c = db()
                cur = c.cursor()
                cur.execute("""INSERT INTO jb_academy_seen (email, last_seen) VALUES (%s, now())
                               ON CONFLICT (email) DO UPDATE SET last_seen = now()""", (email,))
                c.commit()
                c.close()
                hit = _members.get(email)
                access = (hit[4] if hit and len(hit) > 4 else None) or {}
                import datetime
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                admin = email in ADMINS
                c = db()
                cl = []
                for x in calls(c.cursor()):
                    mine = [p for p in _plans(x["plans"]) if admin or p in access]
                    if not mine:
                        continue  # a call for a package this member doesn't have
                    x["open"] = admin or any(access[p] > now for p in mine)
                    x["plans"] = _plans(x["plans"])
                    if not x["open"]:  # their package's call time has ended: no join links
                        x = {k: v for k, v in x.items() if k not in ("zoom_url", "meeting_id", "passcode", "ics_url")}
                    cl.append(x)
                c.close()
                best = max(access.items(), key=lambda kv: (PLANS.index(kv[0]), kv[1])) if access and not admin else None
                c = db()
                cur = c.cursor()
                cur.execute("SELECT item FROM jb_academy_onboarding WHERE email = %s", (email,))
                done_items = {r[0] for r in cur.fetchall()}
                if "profile" not in done_items and not admin and _profile_in_ghl(email):
                    cur.execute("INSERT INTO jb_academy_onboarding (email, item, data) VALUES (%s, 'profile', 'ghl') ON CONFLICT DO NOTHING", (email,))
                    c.commit()
                    done_items.add("profile")
                c.close()
                data["onboarding"] = {"done": sorted(done_items), "discord": DISCORD,
                                      "questions": [{"key": k, "q": q, "required": r} for k, q, r in PROFILE_Q]}
                return self._json(200, dict(data, ok=True, email=email, name=member(email)[1], admin=admin,
                                            role=ADMINS.get(email, ("", None))[1], calls=cl,
                                            call_access={"open": admin or any(x["open"] for x in cl), "admin": admin,
                                                         "plan": "Admin" if admin else (best[0].title() if best else None),
                                                         "until": best[1] if best else None}))
            lid = self._q("id")
            if a == "comments":
                if not (ID_RE.match(lid) and allowed(lid)):
                    return self._json(404, {"error": "That lesson isn't in Sniper Academy."})
                c = db()
                out = thread(c.cursor(), lid, email)
                c.close()
                return self._json(200, {"ok": True, "comments": out})
            out = lesson(lid) if ID_RE.match(lid) else None
            if not out:
                return self._json(404, {"error": "That lesson isn't in Sniper Academy."})
            return self._json(200, dict(out, ok=True))
        except Exception as e:
            log("JB_ACADEMY_ERR:", e)
            return self._json(502, {"error": "We couldn't load the course. Please refresh in a moment."})

    def do_POST(self):
        a = self._action()
        if a in ("start", "login", "progress", "comment", "uncomment", "call_save", "call_delete", "onboard", "profile_save"):
            return getattr(self, "_" + a)()
        self._json(404, {"error": "unknown action"})

    def _start(self):
        email = (self._body().get("email") or "").strip().lower()
        if not EMAIL_RE.match(email):
            return self._json(400, {"error": "Enter the email you joined with."})
        try:
            ok = member(email, fresh=True)[0]
        except Exception as e:
            log("JB_ACADEMY_START_ERR:", e)
            return self._json(500, {"error": "Sign-in is unavailable right now. Please try again in a minute."})
        if ok:  # same answer either way, so the form never reveals who's a member
            A.ghl_tag(email, "", ["sniper-academy-login"], again=True,
                      fields={"sniper_academy_link": J.link(email)})
            log("JB_ACADEMY_LINK_SENT", email)
        else:
            log("JB_ACADEMY_NOT_MEMBER", email)
        self._json(200, {"ok": True})

    def _login(self):
        email = J.verify(self._body().get("l"), "l")
        if not email:
            return self._json(400, {"error": "This sign-in link has expired. Enter your email for a new one.", "expired": True})
        try:
            ok = member(email, fresh=True)[0]
        except Exception as e:
            log("JB_ACADEMY_LOGIN_ERR:", e)
            return self._json(500, {"error": "Sign-in is unavailable right now. Please try again in a minute."})
        if not ok:
            return self._json(403, {"error": "We couldn't find an active Sniper Academy membership on this email.", "expired": True})
        try:
            c = db()
            c.cursor().execute("""INSERT INTO jb_academy_seen (email, logins, last_login, last_seen) VALUES (%s, 1, now(), now())
                                  ON CONFLICT (email) DO UPDATE SET logins = jb_academy_seen.logins + 1, last_login = now(), last_seen = now()""", (email,))
            c.commit()
            c.close()
        except Exception as e:
            log("JB_ACADEMY_SEEN_ERR:", e)
        self._json(200, {"ok": True, "email": email, "session": J.sign(email, "s", J.SESSION_TTL)})

    def _progress(self):
        email = self._member()
        if not email:
            return
        b = self._body()
        lid = str(b.get("id") or "")
        if not ID_RE.match(lid):
            return self._json(400, {"error": "bad lesson"})
        try:
            pos = max(0, min(int(float(b.get("pos") or 0)), 86400))
        except Exception:
            pos = 0
        try:
            c = db()
            cur = c.cursor()
            cur.execute("""INSERT INTO jb_academy_progress (email, lesson_id, pos, done) VALUES (%s, %s, %s, %s)
                           ON CONFLICT (email, lesson_id) DO UPDATE SET pos = EXCLUDED.pos,
                             done = jb_academy_progress.done OR EXCLUDED.done, updated_at = now()""",
                        (email, lid, pos, bool(b.get("done"))))
            if b.get("undo"):
                cur.execute("UPDATE jb_academy_progress SET done = FALSE WHERE email = %s AND lesson_id = %s", (email, lid))
            c.commit()
            c.close()
        except Exception as e:
            log("JB_ACADEMY_PROGRESS_ERR:", e)
            return self._json(500, {"error": "Couldn't save progress."})
        self._json(200, {"ok": True})

    def _comment(self):
        email = self._member()
        if not email:
            return
        b = self._body()
        lid = str(b.get("id") or "")
        text = re.sub(r"\n{3,}", "\n\n", str(b.get("body") or "").replace("\r", "")).strip()[:2000]
        if not text:
            return self._json(400, {"error": "Write something first."})
        try:
            if not (ID_RE.match(lid) and allowed(lid)):
                return self._json(404, {"error": "That lesson isn't in Sniper Academy."})
            c = db()
            cur = c.cursor()
            cur.execute("SELECT count(*) FROM jb_academy_comments WHERE email = %s AND created_at > now() - interval '1 hour'", (email,))
            if cur.fetchone()[0] >= POSTS_PER_HOUR and email not in COACHES:
                c.close()
                return self._json(429, {"error": "You've posted a lot in the last hour. Try again a bit later."})
            parent = None
            if b.get("parent"):
                cur.execute("SELECT COALESCE(parent_id, id) FROM jb_academy_comments WHERE id = %s AND lesson_id = %s AND deleted_at IS NULL",
                            (int(b["parent"]), lid))
                row = cur.fetchone()
                if not row:
                    c.close()
                    return self._json(404, {"error": "That comment has been removed."})
                parent = row[0]  # replies stay one level deep
            cur.execute("""INSERT INTO jb_academy_comments (lesson_id, email, parent_id, author, role, body)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (lid, email, parent, member(email)[1], ADMINS.get(email, ("", None))[1], text))
            c.commit()
            out = thread(cur, lid, email)
            c.close()
            log("JB_ACADEMY_COMMENT", email, lid)
            return self._json(200, {"ok": True, "comments": out})
        except Exception as e:
            log("JB_ACADEMY_COMMENT_ERR:", e)
            return self._json(500, {"error": "Couldn't post that. Please try again."})

    def _uncomment(self):
        email = self._member()
        if not email:
            return
        try:
            cid = int(self._body().get("cid") or 0)
            c = db()
            cur = c.cursor()
            cur.execute("SELECT lesson_id, email FROM jb_academy_comments WHERE id = %s AND deleted_at IS NULL", (cid,))
            row = cur.fetchone()
            if not row or (row[1] != email and email not in COACHES):
                c.close()
                return self._json(404, {"error": "That comment can't be removed."})
            cur.execute("UPDATE jb_academy_comments SET deleted_at = now() WHERE id = %s OR parent_id = %s", (cid, cid))
            c.commit()
            out = thread(cur, row[0], email)
            c.close()
            return self._json(200, {"ok": True, "comments": out})
        except Exception as e:
            log("JB_ACADEMY_UNCOMMENT_ERR:", e)
            return self._json(500, {"error": "Couldn't remove that. Please try again."})

    def _check(self):
        h = self.headers.get("Authorization", "")
        if not verify_token(h[7:].strip() if h.startswith("Bearer ") else ""):
            return self._json(401, {"error": "unauthorized"})
        email = self._q("email").strip().lower()
        try:
            c = A.conn()
            ms = sniper_memberships(c.cursor(), email) if email else []
            c.commit()
            c.close()
            return self._json(200, {"ok": True, "email": email, "coach": email in COACHES,
                                    "access": email in COACHES or any(str(m.get("status")) in OK_STATUS for m in ms),
                                    "name": _name_from(ms, email) if email else "",
                                    "memberships": [{"id": m.get("id"), "status": m.get("status"), "product": _title(m)} for m in ms],
                                    "lessons": sum(len(ch["lessons"]) for ch in course()["chapters"])})
        except Exception as e:
            log("JB_ACADEMY_CHECK_ERR:", e)
            return self._json(502, {"error": str(e)[:400]})

    def _onboard(self):
        email = self._member()
        if not email:
            return
        item = str(self._body().get("item") or "")
        if not ONB_RE.match(item):
            return self._json(400, {"error": "bad step"})
        c = db()
        c.cursor().execute("INSERT INTO jb_academy_onboarding (email, item) VALUES (%s, %s) ON CONFLICT DO NOTHING", (email, item))
        c.commit()
        c.close()
        self._json(200, {"ok": True})

    def _profile_save(self):
        email = self._member()
        if not email:
            return
        given = self._body().get("answers") or {}
        answers = {}
        for k, q, req in PROFILE_Q:
            v = re.sub(r"\s+\n", "\n", str(given.get(k) or "")).strip()[:1500]
            if req and not v:
                return self._json(400, {"error": "Please answer: " + q, "field": k})
            if v:
                answers[q] = v
        try:
            cid = A._ghl_contact(email)
            if not cid:  # a member with no GHL contact yet: make one, then fill it
                A.ghl_tag(email, member(email)[1], [])
                cid = A._ghl_contact(email)
            ids = {(n or "").strip().lower(): i for i, n in _jb_admin._field_names().items()}
            fields = [{"id": ids[q.lower()], "field_value": v} for q, v in answers.items() if q.lower() in ids]
            missing = [q for q in answers if q.lower() not in ids]
            if missing:
                log("JB_ACADEMY_PROFILE_FIELDS_MISSING", missing)
            if cid and fields:
                st, d = A._ghl("PUT", "/contacts/" + cid, {"customFields": fields})
                if st >= 300:
                    raise RuntimeError("GHL %s %s" % (st, str(d)[:200]))
                A._ghl("POST", "/contacts/%s/tags" % cid, {"tags": [PROFILE_TAG]})
        except Exception as e:
            log("JB_ACADEMY_PROFILE_GHL_ERR:", e)
            return self._json(502, {"error": "We couldn't save that just now. Please try again."})
        c = db()
        c.cursor().execute("""INSERT INTO jb_academy_onboarding (email, item, data) VALUES (%s, 'profile', %s)
                              ON CONFLICT (email, item) DO UPDATE SET data = EXCLUDED.data, done_at = now()""",
                           (email, json.dumps(answers)))
        c.commit()
        c.close()
        log("JB_ACADEMY_PROFILE_SAVED", email, len(answers))
        self._json(200, {"ok": True})

    def _is_admin(self):
        h = self.headers.get("Authorization", "")
        tok = h[7:].strip() if h.startswith("Bearer ") else ""
        return J.verify(tok, "s") in ADMINS or verify_token(tok)

    def _call_save(self):
        if not self._is_admin():
            return self._json(403, {"error": "Admins only."})
        b = self._body().get("call") or {}
        try:
            v = {"title": str(b.get("title") or "").strip()[:120], "coach": str(b.get("coach") or "").strip()[:120],
                 "blurb": str(b.get("blurb") or "").strip()[:300], "weekday": int(b.get("weekday")),
                 "start_time": str(b.get("start_time") or "").strip(), "tz": str(b.get("tz") or "America/Denver").strip()[:60],
                 "minutes": max(15, min(int(b.get("minutes") or 60), 480)), "zoom_url": str(b.get("zoom_url") or "").strip()[:500],
                 "meeting_id": str(b.get("meeting_id") or "").strip()[:40], "passcode": str(b.get("passcode") or "").strip()[:40],
                 "ics_url": str(b.get("ics_url") or "").strip()[:800], "active": bool(b.get("active", True)),
                 "plans": ",".join(_plans(",".join(b.get("plans") or []) if isinstance(b.get("plans"), list) else b.get("plans")))}
        except (TypeError, ValueError):
            return self._json(400, {"error": "Check the day and length."})
        if not v["plans"]:
            return self._json(400, {"error": "Pick at least one package that sees this call."})
        if not v["title"] or not 0 <= v["weekday"] <= 6 or not TIME_RE.match(v["start_time"]):
            return self._json(400, {"error": "A call needs a title, a day and a time like 11:00."})
        for k in ("zoom_url", "ics_url"):
            if v[k] and not v[k].startswith("https://"):
                return self._json(400, {"error": "Links must start with https://"})
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(v["tz"])
        except Exception:
            return self._json(400, {"error": "Unknown timezone. Use one like America/Denver."})
        c = db()
        cur = c.cursor()
        if b.get("id"):
            cur.execute("UPDATE jb_academy_calls SET " + ", ".join(k + " = %s" for k in CALL_FIELDS) + ", updated_at = now() WHERE id = %s",
                        [v[k] for k in CALL_FIELDS] + [int(b["id"])])
        else:
            cur.execute("INSERT INTO jb_academy_calls (" + ", ".join(CALL_FIELDS) + ") VALUES (" + ", ".join(["%s"] * len(CALL_FIELDS)) + ")",
                        [v[k] for k in CALL_FIELDS])
        c.commit()
        out = calls(cur, admin=True)
        c.close()
        return self._json(200, {"ok": True, "calls": out})

    def _call_delete(self):
        if not self._is_admin():
            return self._json(403, {"error": "Admins only."})
        c = db()
        cur = c.cursor()
        cur.execute("DELETE FROM jb_academy_calls WHERE id = %s", (int(self._body().get("id") or 0),))
        c.commit()
        out = calls(cur, admin=True)
        c.close()
        return self._json(200, {"ok": True, "calls": out})

    def _admin_get(self, a):
        h = self.headers.get("Authorization", "")
        tok = h[7:].strip() if h.startswith("Bearer ") else ""
        who = J.verify(tok, "s")
        if not (who in ADMINS or verify_token(tok)):
            return self._json(403, {"error": "Admins only."})
        try:
            c = db()
            cur = c.cursor()
            if a == "members" and self._q("probe") and verify_token(tok):
                # admin JWT only: read-only look at Whop's course endpoints, to map course progress
                path = self._q("probe")
                if not re.match(r"^/api/v1/course_[a-z_]+(/[A-Za-z0-9_]+)?(\?[A-Za-z0-9_=&%.-]*)?$", path):
                    c.close()
                    return self._json(400, {"error": "course endpoints only"})
                try:
                    out = {"ok": True, "probe": W.whop("GET", path)}
                except Exception as e:
                    out = {"ok": False, "probe_error": str(e)[:500]}
                c.close()
                return self._json(200, out)
            if a == "ghlfields":  # admin: the GHL contact field names, to map the trader profile
                c.close()
                return self._json(200, {"ok": True, "fields": sorted(n for n in _jb_admin._field_names().values() if n)})
            if a == "calls":
                out = {"ok": True, "calls": calls(cur, admin=True)}
                c.close()
                return self._json(200, out)
            if a == "allcomments":
                out = {"ok": True, "comments": _jb_admin.all_comments(cur)}
                c.close()
                return self._json(200, out)
            if a == "members":
                if self._q("fresh") == "1":
                    _jb_admin.whop_progress(fresh=True)
                rows = _jb_admin.members(cur, fresh=self._q("fresh") == "1")
                cur.execute("SELECT email, logins, last_login, last_seen FROM jb_academy_seen")
                seen = {r[0]: r[1:] for r in cur.fetchall()}
                cur.execute("SELECT email, array_agg(item) FROM jb_academy_onboarding GROUP BY email")
                onb = {r[0]: set(r[1] or []) for r in cur.fetchall()}
                for r in rows:
                    s = seen.get(r["email"])
                    r["logins"] = s[0] if s else 0
                    r["last_login"] = s[1].isoformat() if s and s[1] else None
                    r["last_seen"] = s[2].isoformat() if s and s[2] else None
                    o = onb.get(r["email"], set())
                    r["setup"] = {"profile": "profile" in o, "discord": "discord" in o,
                                  "calendar": any(i.startswith("cal:") for i in o)}
                out = {"ok": True, "members": rows, "lessons": sum(len(ch["lessons"]) for ch in course()["chapters"])}
                if self._q("debug") == "1":
                    ms = _jb_admin.sniper_memberships()
                    out["raw"] = ms[:1]
            else:
                email = self._q("email").strip().lower()
                if not EMAIL_RE.match(email):
                    c.close()
                    return self._json(400, {"error": "email required"})
                out = dict(_jb_admin.profile(cur, email, course()), ok=True)
                cur.execute("SELECT logins, last_login, last_seen FROM jb_academy_seen WHERE email = %s", (email,))
                s = cur.fetchone()
                out["logins"] = s[0] if s else 0
                out["last_login"] = s[1].isoformat() if s and s[1] else None
                out["last_seen"] = s[2].isoformat() if s and s[2] else None
                if self._q("debug") == "1":  # admin-only: what GHL returns for its forms
                    from urllib.parse import quote as _q
                    st, fl = A._ghl("GET", "/forms/?locationId=%s&limit=50" % A.GHL_LOCATION)
                    out["debug_forms"] = {"status": st, "forms": [{"id": f.get("id"), "name": f.get("name")} for f in fl.get("forms") or []] or str(fl)[:300]}
                    tp = [f for f in fl.get("forms") or [] if "trader profile" in (f.get("name") or "").lower()]
                    if tp:
                        st2, sb = A._ghl("GET", "/forms/submissions?locationId=%s&formId=%s&limit=3" % (A.GHL_LOCATION, tp[0]["id"]))
                        out["debug_subs"] = {"status": st2, "total": (sb.get("meta") or {}).get("total"),
                                             "sample": [{k: (v if k != "others" else {kk: str(vv)[:60] for kk, vv in (v or {}).items()}) for k, v in x.items()}
                                                        for x in (sb.get("submissions") or [])[:1]] or str(sb)[:300]}
            c.commit()
            c.close()
            return self._json(200, out)
        except Exception as e:
            log("JB_ACADEMY_ADMIN_ERR:", e)
            return self._json(502, {"error": "Couldn't load that from Whop/GHL. Please refresh.", "detail": str(e)[:300]})

    # ---------- helpers ----------
    def _member(self):
        h = self.headers.get("Authorization", "")
        email = J.verify(h[7:].strip() if h.startswith("Bearer ") else "", "s")
        if not email:
            self._json(401, {"error": "Please sign in again.", "signin": True})
            return None
        try:
            ok = member(email)[0]
        except Exception as e:
            log("JB_ACADEMY_MEMBER_ERR:", e)
            ok = True  # Whop hiccup: keep a signed-in member watching rather than locking them out
        if not ok:
            self._json(403, {"error": "Your Sniper Academy membership isn't active any more.", "signin": True})
            return None
        return email

    def _action(self):
        return self._q("action").strip().lower()

    def _q(self, k):
        return (parse_qs(urlparse(self.path).query).get(k) or [""])[0]

    def _body(self):
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 8000)
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body, default=str).encode())
