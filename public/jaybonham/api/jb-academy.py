"""Sniper Academy members area (page lives at jaybonham.com/academy). Route: /api/jb-academy?action=<action>

Members sign in with an emailed link: we check Whop for an active Sniper Fast Start / Accelerator /
Elite membership on that email, GHL emails the link (tag sniper-academy-login, field
sniper_academy_link), and the link swaps for a 30-day session. Videos stream from Whop's own
hosting (the Sniper Academy course), so Jay keeps uploading in Whop and the page follows.

  start     POST {email}            emails a login link if the email is a member (always says ok)
  login     POST {l}                -> {session, email}: swaps an emailed link for a session
  course    GET  (Bearer session)   chapters, lessons and this member's progress
  lesson    GET  ?id= (Bearer)      one lesson: video stream, poster, notes, attachments
  progress  POST {id, pos?, done?}  (Bearer) saves where they are / marks a lesson complete
  check     GET  ?email= (Bearer admin)  products found, and whether an email has access
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
from _auth import verify_token

COURSE = "cors_ubqXl5GzVJpMN"  # Whop course "Sniper Academy"
OK_STATUS = {"active", "trialing", "past_due", "completed"}
MEMBER_CACHE = 600  # re-check Whop at most every 10 minutes per member (per warm instance)
COURSE_CACHE = 300
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
ID_RE = re.compile(r"^[A-Za-z0-9_]{4,60}$")
TABLE = """CREATE TABLE IF NOT EXISTS jb_academy_progress (
    email      TEXT NOT NULL,
    lesson_id  TEXT NOT NULL,
    pos        INTEGER NOT NULL DEFAULT 0,
    done       BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (email, lesson_id))"""

_members = {}   # email -> (checked_at, ok)
_titles = {}    # product id -> lowercased title
_course = {"at": 0, "data": None}


def log(*a):
    print(*a, file=sys.stderr)


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


def is_member(email, fresh=False):
    hit = _members.get(email)
    if hit and not fresh and time.time() - hit[0] < MEMBER_CACHE:
        return hit[1]
    c = A.conn()
    try:
        ok = any(str(m.get("status")) in OK_STATUS for m in sniper_memberships(c.cursor(), email))
        c.commit()
    finally:
        c.close()
    _members[email] = (time.time(), ok)
    return ok


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
    with ThreadPoolExecutor(8) as ex:  # full lessons, for each video's length
        full = dict(zip(ids, ex.map(lambda i: _lesson_raw(i), ids)))
    data = {"title": "Sniper Academy", "chapters": [
        {"id": ch.get("id"), "title": ch.get("title") or "", "lessons": [
            {"id": l["id"], "title": l.get("title") or "",
             "duration": int(((full.get(l["id"]) or {}).get("video_asset") or {}).get("duration_seconds") or 0)}
            for l in ls]}
        for ch, ls in zip(chapters, per) if ls]}
    _course.update(at=time.time(), data=data)
    return data


def _lesson_raw(lid):
    try:
        return W.whop("GET", "/api/v1/course_lessons/" + lid)
    except Exception as e:
        log("JB_ACADEMY_LESSON_ERR", lid, e)
        return None


def _stream(v):
    if not isinstance(v, dict):
        return "", ""
    if v.get("signed_playback_id") and v.get("signed_video_playback_token"):
        pid = v["signed_playback_id"]
        poster = ("https://image.mux.com/%s/thumbnail.jpg?width=1280&token=%s" % (pid, v["signed_thumbnail_playback_token"])
                  if v.get("signed_thumbnail_playback_token") else "")
        return "https://stream.mux.com/%s.m3u8?token=%s" % (pid, v["signed_video_playback_token"]), poster
    if v.get("playback_id"):
        pid = v["playback_id"]
        return "https://stream.mux.com/%s.m3u8" % pid, "https://image.mux.com/%s/thumbnail.jpg?width=1280" % pid
    return "", ""


def lesson(lid):
    allowed = {l["id"] for ch in course()["chapters"] for l in ch["lessons"]}
    if lid not in allowed:  # only Sniper Academy lessons, never another course's
        return None
    l = _lesson_raw(lid) or {}
    v = l.get("video_asset") if isinstance(l.get("video_asset"), dict) else {}
    stream, poster = _stream(v)
    thumb = l.get("thumbnail") if isinstance(l.get("thumbnail"), dict) else {}
    pdf = l.get("main_pdf") if isinstance(l.get("main_pdf"), dict) else {}
    files = [{"name": a.get("filename") or "File", "url": a.get("url")} for a in (l.get("attachments") or [])
             if isinstance(a, dict) and a.get("url")]
    if pdf.get("url"):
        files.insert(0, {"name": pdf.get("filename") or "Lesson PDF", "url": pdf["url"]})
    return {"id": lid, "title": l.get("title") or "", "content": l.get("content") or "",
            "stream": stream, "poster": poster or thumb.get("url") or "",
            "duration": int(v.get("duration_seconds") or 0), "files": files}


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
        if a not in ("course", "lesson"):
            return self._json(404, {"error": "unknown action"})
        email = self._member()
        if not email:
            return
        try:
            if a == "course":
                data = dict(course())
                c = A.conn()
                cur = c.cursor()
                cur.execute(TABLE)
                cur.execute("SELECT lesson_id, pos, done FROM jb_academy_progress WHERE email = %s ORDER BY updated_at DESC", (email,))
                rows = cur.fetchall()
                c.commit()
                c.close()
                data["progress"] = {r[0]: {"pos": r[1], "done": r[2]} for r in rows}
                data["last"] = rows[0][0] if rows else None
                return self._json(200, dict(data, ok=True, email=email))
            lid = self._q("id")
            out = lesson(lid) if ID_RE.match(lid) else None
            if not out:
                return self._json(404, {"error": "That lesson isn't in Sniper Academy."})
            return self._json(200, dict(out, ok=True))
        except Exception as e:
            log("JB_ACADEMY_ERR:", e)
            return self._json(502, {"error": "We couldn't load the course. Please refresh in a moment."})

    def do_POST(self):
        a = self._action()
        if a == "start":
            return self._start()
        if a == "login":
            return self._login()
        if a == "progress":
            return self._progress()
        self._json(404, {"error": "unknown action"})

    def _start(self):
        email = (self._body().get("email") or "").strip().lower()
        if not EMAIL_RE.match(email):
            return self._json(400, {"error": "Enter the email you joined with."})
        try:
            ok = is_member(email, fresh=True)
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
            ok = is_member(email, fresh=True)
        except Exception as e:
            log("JB_ACADEMY_LOGIN_ERR:", e)
            return self._json(500, {"error": "Sign-in is unavailable right now. Please try again in a minute."})
        if not ok:
            return self._json(403, {"error": "We couldn't find an active Sniper Academy membership on this email.", "expired": True})
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
        done = bool(b.get("done"))
        try:
            c = A.conn()
            cur = c.cursor()
            cur.execute(TABLE)
            cur.execute("""INSERT INTO jb_academy_progress (email, lesson_id, pos, done) VALUES (%s, %s, %s, %s)
                           ON CONFLICT (email, lesson_id) DO UPDATE SET pos = EXCLUDED.pos,
                             done = jb_academy_progress.done OR EXCLUDED.done, updated_at = now()""",
                        (email, lid, pos, done))
            if b.get("undo"):
                cur.execute("UPDATE jb_academy_progress SET done = FALSE WHERE email = %s AND lesson_id = %s", (email, lid))
            c.commit()
            c.close()
        except Exception as e:
            log("JB_ACADEMY_PROGRESS_ERR:", e)
            return self._json(500, {"error": "Couldn't save progress."})
        self._json(200, {"ok": True})

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
            return self._json(200, {"ok": True, "email": email, "access": any(str(m.get("status")) in OK_STATUS for m in ms),
                                    "memberships": [{"id": m.get("id"), "status": m.get("status"), "product": _title(m)} for m in ms],
                                    "lessons": sum(len(ch["lessons"]) for ch in course()["chapters"])})
        except Exception as e:
            log("JB_ACADEMY_CHECK_ERR:", e)
            return self._json(502, {"error": str(e)[:400]})

    # ---------- helpers ----------
    def _member(self):
        h = self.headers.get("Authorization", "")
        email = J.verify(h[7:].strip() if h.startswith("Bearer ") else "", "s")
        if not email:
            self._json(401, {"error": "Please sign in again.", "signin": True})
            return None
        try:
            ok = is_member(email)
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
            n = min(int(self.headers.get("Content-Length", 0)), 4000)
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
