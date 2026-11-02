"""Academy test: can our own player stream TradeVault's Whop course videos? Admin token required.
GET               -> {ok, courses:[{id, title, lessons:[{id, title, type, embed_type, embed_id}]}]}
GET ?lesson=ID    -> {ok, lesson:{id, title, type, content, embed_type, embed_id, stream, poster, attachments}, raw}
        stream is the Mux HLS URL built from the lesson's video asset (signed when Whop signs it).
Needs the Whop API key to have courses:read. Test only: the portal's real Academy will live in the portal.
"""
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
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not verify_token(auth[7:]):
            return self._json(401, {"ok": False, "error": "Unauthorized"})
        q = parse_qs(urlparse(self.path).query)
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

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())
