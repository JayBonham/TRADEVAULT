"""Academy test: can our own player stream TradeVault's Whop course videos? Admin token required.
GET               -> {ok, courses:[{id, title, lessons:[{id, title, type, embed_type, embed_id}]}]}
GET ?lesson=ID    -> {ok, lesson:{id, title, type, content, embed_type, embed_id, stream, poster, attachments}, raw}
        stream is the Mux HLS URL built from the lesson's video asset (signed when Whop signs it).
Needs the Whop API key to have courses:read. Test only: the portal's real Academy will live in the portal.
"""
import hashlib
import hmac
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token
from _tv_whop import whop

WHOP_COMPANY = "biz_R8QEgfRFt2KfLV"
# One-off structure export for building the portal Academy (key held by the developer; only its hash is here).
EXPORT_HASH = "e2a3f8199a7b57cba4f29961ee6142e29d3ab89ea085299c742c418d44f887a2"
ID_RE = re.compile(r"^[A-Za-z0-9_]{4,60}$")


def log(*a):
    print(*a, file=sys.stderr)


def _all(path):
    out, after = [], ""
    for _ in range(10):
        page = whop("GET", path + "&first=100" + ("&after=" + after if after else ""))
        out += page.get("data") or []
        info = page.get("page_info") or {}
        after = info.get("end_cursor") or ""
        if not (info.get("has_next_page") and after):
            break
    return out


def _stream(v):
    """Mux HLS + poster from a Whop video_asset: signed ids need their token, public ids play as is."""
    if not isinstance(v, dict):
        return "", ""
    if v.get("signed_playback_id") and v.get("signed_video_playback_token"):
        pid = v["signed_playback_id"]
        poster = ("https://image.mux.com/%s/thumbnail.jpg?token=%s" % (pid, v["signed_thumbnail_playback_token"])
                  if v.get("signed_thumbnail_playback_token") else "")
        return "https://stream.mux.com/%s.m3u8?token=%s" % (pid, v["signed_video_playback_token"]), poster
    if v.get("playback_id"):
        pid = v["playback_id"]
        return "https://stream.mux.com/%s.m3u8" % pid, "https://image.mux.com/%s/thumbnail.jpg" % pid
    return "", ""


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        key = self.headers.get("X-Export-Key", "")
        if key and hmac.compare_digest(hashlib.sha256(key.encode()).hexdigest(), EXPORT_HASH):
            return self._export(q)
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not verify_token(auth[7:]):
            return self._json(401, {"ok": False, "error": "Unauthorized"})
        try:
            lid = (q.get("lesson") or [""])[0]
            if lid:
                if not ID_RE.match(lid):
                    return self._json(400, {"ok": False, "error": "Invalid lesson"})
                l = whop("GET", "/api/v1/course_lessons/" + lid)
                stream, poster = _stream(l.get("video_asset"))
                thumb = l.get("thumbnail") if isinstance(l.get("thumbnail"), dict) else {}
                return self._json(200, {"ok": True, "raw": l, "lesson": {
                    "id": l.get("id"), "title": l.get("title"), "type": l.get("lesson_type"),
                    "content": l.get("content") or "", "embed_type": l.get("embed_type"), "embed_id": l.get("embed_id"),
                    "stream": stream, "poster": poster or thumb.get("url") or "",
                    "attachments": [{"name": a.get("filename"), "url": a.get("url"), "type": a.get("content_type")}
                                    for a in (l.get("attachments") or []) if isinstance(a, dict)]}})
            courses = _all("/api/v1/courses?account_id=" + WHOP_COMPANY)
            out = []
            for c in courses:
                lessons = _all("/api/v1/course_lessons?course_id=" + str(c.get("id")))
                out.append({"id": c.get("id"), "title": c.get("title"), "visibility": c.get("visibility"),
                            "lessons": [{"id": l.get("id"), "title": l.get("title"), "type": l.get("lesson_type"),
                                         "order": l.get("order"), "embed_type": l.get("embed_type"), "embed_id": l.get("embed_id")}
                                        for l in lessons]})
            self._json(200, {"ok": True, "courses": out})
        except Exception as e:
            log("TV_ACADEMY_ERR:", e)
            self._json(502, {"ok": False, "error": str(e)[:400]})

    def _export(self, q):
        """?course=ID: chapters with their lessons (and each lesson in full when &full=1); else the course list."""
        try:
            cid = (q.get("course") or [""])[0]
            lid = (q.get("lesson") or [""])[0]
            if lid and ID_RE.match(lid):
                return self._json(200, {"ok": True, "lesson": whop("GET", "/api/v1/course_lessons/" + lid)})
            if not cid:
                return self._json(200, {"ok": True, "courses": _all("/api/v1/courses?account_id=" + WHOP_COMPANY)})
            if not ID_RE.match(cid):
                return self._json(400, {"ok": False})
            full = (q.get("full") or [""])[0] == "1"
            chapters = sorted(_all("/api/v1/course_chapters?course_id=" + cid), key=lambda c: c.get("order") or 0)
            for ch in chapters:
                ch["lessons"] = sorted(_all("/api/v1/course_lessons?chapter_id=" + str(ch.get("id"))), key=lambda l: l.get("order") or 0)
                if full:
                    ch["lessons"] = [whop("GET", "/api/v1/course_lessons/" + str(l.get("id"))) for l in ch["lessons"]]
            self._json(200, {"ok": True, "chapters": chapters})
        except Exception as e:
            log("TV_ACADEMY_EXPORT_ERR:", e)
            self._json(502, {"ok": False, "error": str(e)[:400]})

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Export-Key")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())
