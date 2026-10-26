"""Video tracking.
POST (public, from vt.js): log one event.
GET  (admin, Bearer token): aggregated stats per video and per page, plus recent sessions.
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token

DATABASE_URL = os.environ.get("DATABASE_URL", "")
EVENTS = {"view", "impression", "play", "progress", "cta"}
SAFE = re.compile(r"^[A-Za-z0-9_\-./]{1,120}$")
MILESTONES = list(range(10, 101, 10))


def _conn():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def _ensure(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jb_video_events (
            id         BIGSERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            sid        TEXT NOT NULL,
            vid        TEXT,
            page       TEXT NOT NULL,
            video      TEXT,
            event      TEXT NOT NULL,
            pct        INTEGER,
            email      TEXT,
            ref        TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS jb_video_events_ts ON jb_video_events (created_at)")


def _clip(v, n):
    return v[:n] if isinstance(v, str) else None


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._send(204, None)

    # ── ingest ────────────────────────────────────────────────
    def do_POST(self):
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 4000)
            b = json.loads(self.rfile.read(length) or b"{}")
            event = b.get("event")
            sid = _clip(b.get("sid"), 40)
            page = _clip(b.get("page"), 120)
            video = _clip(b.get("video"), 80)
            if event not in EVENTS or not sid or not page:
                return self._send(400, {"ok": False})
            if video and not SAFE.match(video):
                video = None
            pct = b.get("pct")
            pct = max(0, min(100, int(pct))) if isinstance(pct, (int, float)) else None
            email = _clip(b.get("email"), 160)
            if email and "@" not in email:
                email = None
            conn = _conn()
            cur = conn.cursor()
            _ensure(cur)
            cur.execute(
                "INSERT INTO jb_video_events (sid, vid, page, video, event, pct, email, ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (sid, _clip(b.get("vid"), 40), page, video, event, pct, email.lower() if email else None, _clip(b.get("ref"), 200)),
            )
            conn.commit()
            conn.close()
            self._send(204, None)
        except Exception as e:
            print("vt ingest error:", e)
            self._send(500, {"ok": False})

    # ── stats ────────────────────────────────────────────────
    def do_GET(self):
        auth = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
        if not verify_token(auth):
            return self._send(401, {"ok": False, "error": "Unauthorized"})
        q = parse_qs(urlparse(self.path).query)
        try:
            days = max(1, min(365, int(q.get("days", ["30"])[0])))
        except ValueError:
            days = 30
        try:
            conn = _conn()
            cur = conn.cursor()
            _ensure(cur)
            conn.commit()
            # one row per session x page x video x event: max pct and first time
            cur.execute("""
                SELECT sid, page, COALESCE(video, ''), event, MAX(COALESCE(pct, 0)), MIN(created_at), MAX(email)
                FROM jb_video_events
                WHERE created_at >= NOW() - (%s || ' days')::interval
                GROUP BY sid, page, COALESCE(video, ''), event
            """, (str(days),))
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            print("vt stats error:", e)
            return self._send(500, {"ok": False, "error": "Database unavailable: " + str(e)[:160]})

        sessions = {}   # sid -> {page -> {...}}
        for sid, page, video, event, pct, ts, email in rows:
            s = sessions.setdefault(sid, {"email": None, "first": ts, "last": ts, "pages": {}})
            if email:
                s["email"] = email
            s["first"] = min(s["first"], ts)
            s["last"] = max(s["last"], ts)
            pg = s["pages"].setdefault(page, {"view": False, "cta": False, "cta_pct": None, "cta_video": None, "videos": {}})
            if event == "view":
                pg["view"] = True
            elif event == "cta":
                pg["cta"] = True
                pg["cta_pct"] = pct if video else None
                pg["cta_video"] = video or None
            elif video:
                v = pg["videos"].setdefault(video, {"imp": False, "play": False, "max": 0})
                if event == "impression":
                    v["imp"] = True
                elif event == "play":
                    v["play"] = True
                elif event == "progress":
                    v["max"] = max(v["max"], pct)

        videos, pages = {}, {}
        for sid, s in sessions.items():
            for page, pg in s["pages"].items():
                P = pages.setdefault(page, {"page": page, "views": 0, "cta": 0, "played_any": 0, "cta_after_play": 0})
                if pg["view"]:
                    P["views"] += 1
                if pg["cta"]:
                    P["cta"] += 1
                played_here = any(v["play"] for v in pg["videos"].values())
                if played_here:
                    P["played_any"] += 1
                    if pg["cta"]:
                        P["cta_after_play"] += 1
                for key, v in pg["videos"].items():
                    V = videos.setdefault(key, {"video": key, "pages": set(), "impressions": 0, "plays": 0,
                                                "reached": {m: 0 for m in MILESTONES}, "pct_sum": 0,
                                                "cta": 0, "cta_pct": []})
                    V["pages"].add(page)
                    if v["imp"] or v["play"]:
                        V["impressions"] += 1
                    if v["play"]:
                        V["plays"] += 1
                        V["pct_sum"] += v["max"]
                        for m in MILESTONES:
                            if v["max"] >= m:
                                V["reached"][m] += 1
                        if pg["cta"]:
                            V["cta"] += 1
                            if pg["cta_video"] == key and pg["cta_pct"] is not None:
                                V["cta_pct"].append(pg["cta_pct"])

        out_videos = []
        for V in videos.values():
            plays = V["plays"]
            out_videos.append({
                "video": V["video"],
                "pages": sorted(V["pages"]),
                "impressions": V["impressions"],
                "plays": plays,
                "play_rate": round(100 * plays / V["impressions"], 1) if V["impressions"] else None,
                "avg_watched": round(V["pct_sum"] / plays, 1) if plays else None,
                "reached": {str(m): V["reached"][m] for m in MILESTONES},
                "cta_after_play": V["cta"],
                "avg_pct_at_cta": round(sum(V["cta_pct"]) / len(V["cta_pct"]), 1) if V["cta_pct"] else None,
            })

        recent = []
        for sid, s in sorted(sessions.items(), key=lambda kv: kv[1]["last"], reverse=True)[:100]:
            for page, pg in s["pages"].items():
                watched = {k: v["max"] for k, v in pg["videos"].items() if v["play"]}
                recent.append({
                    "when": s["last"].isoformat(),
                    "email": s["email"],
                    "page": page,
                    "watched": watched,
                    "cta": pg["cta"],
                    "cta_pct": pg["cta_pct"],
                })

        self._send(200, {
            "ok": True,
            "days": days,
            "sessions": len(sessions),
            "videos": sorted(out_videos, key=lambda v: -v["plays"]),
            "pages": sorted(pages.values(), key=lambda p: -p["views"]),
            "recent": recent[:150],
        })

    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if body is not None:
            data = json.dumps(body, default=str).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        else:
            self.end_headers()

    def log_message(self, *args):
        pass
