"""Whop support chats, answered from the TradeVault admin (page at thetradevault.co/admin/support).
Admin token required. Needs the Whop API key permissions support_chat:read and
support_chat:message:create (and member/membership read, already used elsewhere).

GET  ?list=open|all|resolved[&after=cursor]
       -> {ok, chats:[{id, user:{id,name,username}, last:{text,at,mine,files}, at, needs_reply,
                       resolved}], next}
GET  ?c=<channel id>[&before=<message id>][&since=<message id>][&u=<user id>]
       -> {ok, messages:[{id, text, at, team, author:{id,name,username,avatar}, files:[...],
                          reply_to}] oldest first, more, member}
       member (only when u is given): Whop memberships for that user plus our setup answers.
POST {c, text[, reply_to]} -> {ok, message}
POST {c, action: "resolve"|"reopen"} -> {ok, resolved}
"""
import http.client
import json
import os
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote, urlparse

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token

WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
WHOP_COMPANY = "biz_R8QEgfRFt2KfLV"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,80}$")
VIEWS = {"open": "true", "resolved": "false", "all": None}


def log(*a):
    print(*a, file=sys.stderr)


class WhopError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status


def whop(method, path, body=None, extra=None):
    c = http.client.HTTPSConnection("api.whop.com", timeout=12)
    h = {"Authorization": "Bearer " + WHOP_API_KEY, "Accept": "application/json", "Content-Type": "application/json"}
    h.update(extra or {})
    c.request(method, "/api/v1" + path, json.dumps(body) if body is not None else None, h)
    r = c.getresponse()
    raw = r.read()
    if r.status >= 300:
        try:
            msg = json.loads(raw).get("error", {}).get("message") or ""
        except Exception:
            msg = raw[:200].decode("utf-8", "replace")
        if r.status in (401, 403):
            msg = ("Whop refused (%s). The Whop API key needs the support_chat:read and "
                   "support_chat:message:create permissions (and permission to resolve support chats). %s" % (r.status, msg)).strip()
        raise WhopError(r.status, msg or "Whop error %s" % r.status)
    return json.loads(raw or b"{}")


def _pic(u):
    p = u.get("profile_picture")
    if isinstance(p, dict):
        p = p.get("url") or p.get("source_url") or ""
    return p or u.get("profile_pic_url") or u.get("profile_picture_url") or u.get("avatar_url") or ""


def _user(u):
    u = u if isinstance(u, dict) else {}
    return {"id": u.get("id") or "", "name": u.get("name") or "", "username": u.get("username") or "",
            "avatar": _pic(u)}


_PICS = {}  # user id -> profile picture url ("" when none); lives as long as the warm function


def fill_avatars(users):
    """Whop leaves the picture off chat authors, so look each user up once and remember it."""
    want = list({u["id"] for u in users if u.get("id") and not u.get("avatar") and u["id"] not in _PICS})[:30]

    def one(uid):
        try:
            _PICS[uid] = _pic(whop("GET", "/users/" + quote(uid)))
        except Exception as e:
            log("TV_SUPPORT_PIC:", uid, e)
            _PICS[uid] = ""
    if want:
        with ThreadPoolExecutor(min(10, len(want))) as ex:
            list(ex.map(one, want))
    for u in users:
        if u.get("id") and not u.get("avatar"):
            u["avatar"] = _PICS.get(u["id"], "")


def _files(lst):
    out = []
    for f in lst or []:
        if not isinstance(f, dict):
            continue
        out.append({"name": f.get("filename") or "file", "type": f.get("content_type") or "",
                    "url": f.get("url") or "", "w": f.get("width"), "h": f.get("height")})
    return out


def list_chats(view, after):
    q = "/support_channels?account_id=%s&first=50&include_last_message=true&order=last_post_sent_at&direction=desc" % WHOP_COMPANY
    if VIEWS.get(view):
        q += "&open=" + VIEWS[view]
    if after:
        q += "&after=" + quote(after)
    d = whop("GET", q)
    chats = []
    for ch in d.get("data") or []:
        cu = ch.get("customer_user") if isinstance(ch.get("customer_user"), dict) else {}
        lm = ch.get("last_message") if isinstance(ch.get("last_message"), dict) else None
        last = None
        if lm:
            last = {"text": lm.get("content") or "", "at": lm.get("created_at") or "",
                    "mine": bool(cu.get("id")) and lm.get("user_id") != cu.get("id"),
                    "files": len(lm.get("attachments") or [])}
        if view == "resolved" and not ch.get("resolved_at"):
            continue
        chats.append({"id": ch.get("id"), "user": _user(cu), "name": ch.get("custom_name") or "",
                      "last": last, "at": ch.get("last_message_at") or (last or {}).get("at") or "",
                      "needs_reply": bool(ch.get("needs_reply")), "resolved": bool(ch.get("resolved_at"))})
    fill_avatars([c["user"] for c in chats])
    pi = d.get("page_info") or {}
    return chats, (pi.get("end_cursor") if pi.get("has_next_page") else None)


def _gifs(lst):
    return [{"name": g.get("title") or "GIF", "type": "image/gif", "url": g.get("preview_url") or g.get("url") or "",
             "w": g.get("width"), "h": g.get("height")} for g in lst or [] if isinstance(g, dict)]


def _msg(m):
    # Whop returns either the documented shape (author / author_user_id) or the older one (user / user_id)
    au = m.get("author") if isinstance(m.get("author"), dict) else m.get("user") if isinstance(m.get("user"), dict) else {}
    aid = m.get("author_user_id") or m.get("user_id") or au.get("id") or ""
    if not isinstance(aid, str):
        aid = ""
    if aid and not au.get("id"):
        au = dict(au, id=aid)
    team = m.get("author_is_team_member")
    if team is None:
        team = m.get("is_team_member")
    return {"id": m.get("id"), "text": m.get("content") if m.get("content") is not None else (m.get("plain_content") or m.get("text") or ""),
            "at": m.get("created_at") or "",
            "team": team, "kind": m.get("message_type") or "regular",
            "author": _user(au), "author_id": aid,
            "custom": ((m.get("custom_author") or {}).get("display_name") or "") if isinstance(m.get("custom_author"), dict) else "",
            "files": _files(m.get("attachments")) + _gifs(m.get("gifs")), "reply_to": m.get("replying_to_message_id"),
            "extra": bool(m.get("embeds") or m.get("poll") or m.get("link_previews")),
            "deleted": bool(m.get("deleted_at"))}


def messages(cid, before, since):
    q = "/messages?channel_id=%s&first=50" % quote(cid)
    if since:
        q += "&after_message_id=%s&direction=asc" % quote(since)
    else:
        q += "&direction=desc" + ("&before_message_id=" + quote(before) if before else "")
    d = whop("GET", q)
    raw = [m for m in d.get("data") or [] if isinstance(m, dict)]
    msgs = [_msg(m) for m in d.get("data") or [] if isinstance(m, dict) and not m.get("deleted_at")]
    fill_avatars([m["author"] for m in msgs])
    msgs.sort(key=lambda m: m["at"])
    more = bool((d.get("page_info") or {}).get("has_next_page")) if not since else False
    return msgs, more


def _db_member(membership_ids):
    """Email and setup answers from our own tables, via the membership ids on tv_payments."""
    if not (DATABASE_URL and membership_ids):
        return {}
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        try:
            cur = conn.cursor()
            cur.execute("SELECT email, name FROM tv_payments WHERE membership_id = ANY(%s) ORDER BY paid_at DESC LIMIT 1",
                        (list(membership_ids),))
            row = cur.fetchone()
            if not row:
                return {}
            out = {"email": row[0] or "", "name": row[1] or ""}
            cur.execute("""SELECT tier, setup_at, educator, scanner, tradingview, telegram, purchased_at
                           FROM tv_members WHERE lower(email) = lower(%s)
                           ORDER BY purchased_at DESC NULLS LAST LIMIT 1""", (out["email"],))
            r = cur.fetchone()
            if r:
                out.update({"tier": r[0] or "", "setup": bool(r[1]), "educator": r[2] or "", "scanner": r[3] or "",
                            "tradingview": r[4] or "", "telegram": r[5] or ""})
            return out
        finally:
            conn.close()
    except Exception as e:
        log("TV_SUPPORT_DB:", e)
        return {}


def member(uid):
    try:
        d = whop("GET", "/memberships?account_id=%s&user_id=%s&first=25" % (WHOP_COMPANY, quote(uid)))
    except WhopError as e:
        log("TV_SUPPORT_MEMBERSHIPS:", e)
        return {"memberships": [], "error": str(e)}
    ms, meta = [], {}
    for m in d.get("data") or []:
        if not isinstance(m, dict):
            continue
        prod = m.get("product") if isinstance(m.get("product"), dict) else {}
        ms.append({"id": m.get("id"), "product": prod.get("title") or "", "status": m.get("status") or "",
                   "since": m.get("created_at") or "", "renews": m.get("current_period_end") or m.get("expires_at") or "",
                   "cancelling": bool(m.get("cancel_at_period_end"))})
        md = m.get("metadata") if isinstance(m.get("metadata"), dict) else {}
        for k, v in md.items():
            if k.startswith("tv_") and v and k not in meta:
                meta[k] = v
    rank = {"active": 0, "trialing": 0, "past_due": 1, "canceling": 1, "expiring": 1}
    ms.sort(key=lambda m: m["since"], reverse=True)
    ms.sort(key=lambda m: rank.get(m["status"], 2))
    out = {"memberships": ms}
    out.update(_db_member([m["id"] for m in ms if m["id"]]))
    # Whop metadata fills anything our DB doesn't have
    for k, mk in (("tier", "tv_tier"), ("tradingview", "tv_tradingview"), ("telegram", "tv_telegram"),
                  ("educator", "tv_educator"), ("scanner", "tv_scanners")):
        if not out.get(k) and meta.get(mk):
            out[k] = meta[mk]
    return out


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def _authed(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not verify_token(auth[7:]):
            self._json(401, {"ok": False, "error": "Unauthorized"})
            return False
        if not WHOP_API_KEY:
            self._json(500, {"ok": False, "error": "WHOP_API_KEY is not set"})
            return False
        return True

    def do_GET(self):
        if not self._authed():
            return
        qs = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        try:
            cid = qs.get("c", "")
            if cid:
                if not ID_RE.match(cid):
                    return self._json(400, {"ok": False, "error": "Invalid chat"})
                before, since, uid = qs.get("before", ""), qs.get("since", ""), qs.get("u", "")
                for v in (before, since, uid):
                    if v and not ID_RE.match(v):
                        return self._json(400, {"ok": False, "error": "Invalid request"})
                with ThreadPoolExecutor(2) as ex:
                    fm = ex.submit(messages, cid, before, since)
                    fu = ex.submit(member, uid) if uid else None
                    msgs, more = fm.result()
                    body = {"ok": True, "messages": msgs, "more": more}
                    if fu:
                        body["member"] = fu.result()
                return self._json(200, body)
            view = qs.get("list", "open")
            if view not in VIEWS:
                view = "open"
            after = qs.get("after", "")
            if after and len(after) > 400:
                return self._json(400, {"ok": False, "error": "Invalid request"})
            chats, nxt = list_chats(view, after)
            self._json(200, {"ok": True, "chats": chats, "next": nxt})
        except WhopError as e:
            log("TV_SUPPORT_ERR:", e.status, e)
            self._json(502, {"ok": False, "error": str(e)})
        except Exception as e:
            log("TV_SUPPORT_ERR:", e)
            self._json(502, {"ok": False, "error": str(e)})

    def do_POST(self):
        if not self._authed():
            return
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 20000)
            b = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"ok": False, "error": "Invalid request"})
        cid = str(b.get("c") or "")
        action = b.get("action")
        if action in ("resolve", "reopen"):
            if not ID_RE.match(cid):
                return self._json(400, {"ok": False, "error": "Invalid chat"})
            try:
                whop("POST", "/channels/%s/%s" % (quote(cid), action), {})
            except WhopError as e:
                if e.status != 409:  # 409: already in that state
                    log("TV_SUPPORT_%s_ERR:" % action.upper(), e.status, e)
                    return self._json(502, {"ok": False, "error": str(e)})
            log("TV_SUPPORT", action, cid)
            return self._json(200, {"ok": True, "resolved": action == "resolve"})
        text = str(b.get("text") or "").strip()
        reply = str(b.get("reply_to") or "")
        if not ID_RE.match(cid) or not text or len(text) > 5000 or (reply and not ID_RE.match(reply)):
            return self._json(400, {"ok": False, "error": "Invalid message"})
        body = {"channel_id": cid, "content": text, "auto_detect_links": True}
        if reply:
            body["replying_to_message_id"] = reply
        key = str(b.get("key") or "")[:100] or str(uuid.uuid4())
        try:
            m = whop("POST", "/messages", body, {"Idempotency-Key": key})
        except WhopError as e:
            log("TV_SUPPORT_SEND_ERR:", e.status, e)
            return self._json(502, {"ok": False, "error": str(e)})
        except Exception as e:
            log("TV_SUPPORT_SEND_ERR:", e)
            return self._json(502, {"ok": False, "error": str(e)})
        log("TV_SUPPORT_SENT", cid)
        self._json(200, {"ok": True, "message": _msg(m)})

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())
