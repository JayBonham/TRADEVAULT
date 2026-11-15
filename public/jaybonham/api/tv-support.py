"""Whop support chats, answered from the TradeVault admin (page at thetradevault.co/admin/support).
Admin token required. Needs the Whop API key permissions support_chat:read and
support_chat:message:create (and member/membership read, already used elsewhere).

GET  ?list=open|all|resolved[&after=cursor]
       -> {ok, chats:[{id, user:{id,name,username}, last:{text,at,mine,files}, at, needs_reply,
                       resolved}], next}
GET  ?c=<channel id>[&before=<message id>][&since=<message id>][&u=<user id>]
       -> {ok, messages:[{id, text, at, team, author:{id,name,username,avatar}, files:[...],
                          reply_to}] oldest first, more, member}
       member (only when u is given): Whop memberships for that user plus our setup answers, the email on
       their Whop account (whop_email), and purchases found under any email they typed in the chat (typed).
POST {c, text[, reply_to]} -> {ok, message}
POST {c, action: "resolve"|"reopen"} -> {ok, resolved}
POST {c, text?, image: {name, type, data(base64)}} -> uploads the image to Whop and sends it attached
GET  ?snippets=1 -> {ok, snippets:[{id,label,body}]}   (saved replies, shared by every admin)
POST {action: "snippet_save", id?, label, body} / {action: "snippet_delete", id}
Sent replies are recorded with the admin who sent them (tv_support_sent) so the inbox can show
"sent by"; Whop itself posts every reply as the API key's owner.
"""
import datetime
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
import base64
import time

WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
ASSIGNED_TAG = "tv-access-granted"
MAX_IMAGE = 3 * 1024 * 1024
SCHEMA = """
CREATE TABLE IF NOT EXISTS tv_support_snippets (
    id         SERIAL PRIMARY KEY,
    label      TEXT NOT NULL,
    body       TEXT NOT NULL,
    position   INTEGER NOT NULL DEFAULT 0,
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS tv_support_state (
    chat_id  TEXT PRIMARY KEY,
    resolved BOOLEAN NOT NULL,
    by_who   TEXT,
    at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS tv_support_sent (
    message_id TEXT PRIMARY KEY,
    chat_id    TEXT NOT NULL,
    sent_by    TEXT NOT NULL,
    sent_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS tv_support_sent_chat ON tv_support_sent (chat_id);
"""
# Saved replies the table starts with. {first} {email} {setup_link} {tradingview} are filled in per member.
DEFAULT_SNIPPETS = [
    ("Hey 👋", "Hey {first}, thanks for reaching out! "),
    ("Looking into it", "Thanks {first}, I'm looking into this now and will get back to you shortly."),
    ("Access is live", "You're all set {first}! Your TradingView access is live. Refresh TradingView and you'll find the scanner under Indicators → Invite-only scripts."),
    ("Setup page", "To get your scanner access, fill in your setup page here (it takes a minute): {setup_link} Once it's in, we'll get you added."),
    ("Upgrade to Elite", "Use the coupon code: elite_upgrade\nThat will allow you to upgrade to Elite and pay the difference.\n\nYou can pay here: https://whop.com/sniper-academy-603f/sniper-elite-3d/"),
    ("Anything else?", "Anything else I can help with?"),
]
WHOP_COMPANY = "biz_R8QEgfRFt2KfLV"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,80}$")
VIEWS = ("open", "resolved", "all")
# Whop marks a chat resolved by itself once the team replies, so Open/Resolved here follow the Resolve
# button instead (tv_support_state). Chats Whop resolved before this went live keep Whop's state.
WHOP_RESOLVED_BEFORE = 1794700800  # 2026-11-15 00:00 UTC


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


def _ts(v):
    """Whop timestamps come as ISO strings or unix seconds."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v:
        if v.isdigit():
            return float(v)
        try:
            return datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def chat_states(ids):
    """chat id -> (resolved, at epoch) from the Resolve/Reopen button."""
    if not (DATABASE_URL and ids):
        return {}
    try:
        conn = db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT chat_id, resolved, EXTRACT(EPOCH FROM at) FROM tv_support_state WHERE chat_id = ANY(%s)", (list(ids),))
            return {r[0]: (bool(r[1]), float(r[2])) for r in cur.fetchall()}
        finally:
            conn.close()
    except Exception as e:
        log("TV_SUPPORT_STATE_DB:", e)
        return {}


def set_state(cid, resolved, who):
    if not DATABASE_URL:
        return
    conn = db()
    try:
        cur = conn.cursor()
        cur.execute("""INSERT INTO tv_support_state (chat_id, resolved, by_who, at) VALUES (%s, %s, %s, NOW())
                       ON CONFLICT (chat_id) DO UPDATE SET resolved = EXCLUDED.resolved, by_who = EXCLUDED.by_who, at = NOW()""",
                    (cid, resolved, who))
        conn.commit()
    finally:
        conn.close()


def _is_resolved(ch, last, state):
    """Resolved only when someone pressed Resolve, and the customer hasn't written since."""
    cust_at = _ts(last["at"]) if last and not last["mine"] else 0.0
    if state is not None:
        resolved, at = state
        return resolved and cust_at <= at
    w = _ts(ch.get("resolved_at"))
    return bool(w) and w < WHOP_RESOLVED_BEFORE and cust_at <= w


def list_chats(view, after):
    """Whop's own open/resolved filter can't be used (it drops a chat as soon as we reply), so pages are
    read unfiltered and sorted into Open/Resolved here."""
    want = 25 if view != "all" else 1
    chats, cursor, pages = [], after, 0
    while True:
        q = "/support_channels?account_id=%s&first=50&include_last_message=true&order=last_post_sent_at&direction=desc" % WHOP_COMPANY
        if cursor:
            q += "&after=" + quote(cursor)
        d = whop("GET", q)
        page = []
        for ch in d.get("data") or []:
            if not isinstance(ch, dict):
                continue
            cu = ch.get("customer_user") if isinstance(ch.get("customer_user"), dict) else {}
            lm = ch.get("last_message") if isinstance(ch.get("last_message"), dict) else None
            last = None
            if lm:
                last = {"text": lm.get("content") or "", "at": lm.get("created_at") or "",
                        "mine": bool(cu.get("id")) and lm.get("user_id") != cu.get("id"),
                        "files": len(lm.get("attachments") or [])}
            page.append((ch, cu, last))
        states = chat_states([ch.get("id") for ch, _, _ in page if ch.get("id")])
        for ch, cu, last in page:
            resolved = _is_resolved(ch, last, states.get(ch.get("id")))
            if (view == "open" and resolved) or (view == "resolved" and not resolved):
                continue
            chats.append({"id": ch.get("id"), "user": _user(cu), "name": ch.get("custom_name") or "",
                          "last": last, "at": ch.get("last_message_at") or (last or {}).get("at") or "",
                          "needs_reply": bool(ch.get("needs_reply")) and not resolved, "resolved": resolved})
        pages += 1
        pi = d.get("page_info") or {}
        cursor = pi.get("end_cursor") if pi.get("has_next_page") else None
        if not cursor or len(chats) >= want or pages >= 4:
            break
    fill_avatars([c["user"] for c in chats])
    return chats, cursor


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
    by = senders([m["id"] for m in msgs if m.get("id")])
    for m in msgs:
        if m["id"] in by:
            m["sent_by"] = by[m["id"]]
    msgs.sort(key=lambda m: m["at"])
    more = bool((d.get("page_info") or {}).get("has_next_page")) if not since else False
    return msgs, more


_schema_ready = False


def db():
    global _schema_ready
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    if not _schema_ready:
        cur = conn.cursor()
        cur.execute(SCHEMA)
        conn.commit()
        _schema_ready = True
    return conn


def snippets():
    conn = db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tv_support_snippets")
        if cur.fetchone()[0] == 0:
            for i, (label, body) in enumerate(DEFAULT_SNIPPETS):
                cur.execute("INSERT INTO tv_support_snippets (label, body, position, updated_by) VALUES (%s, %s, %s, 'default')",
                            (label, body, i))
            conn.commit()
        cur.execute("SELECT id, label, body FROM tv_support_snippets ORDER BY position, id")
        return [{"id": r[0], "label": r[1], "body": r[2]} for r in cur.fetchall()]
    finally:
        conn.close()


def snippet_save(sid, label, body, who):
    conn = db()
    try:
        cur = conn.cursor()
        if sid:
            cur.execute("UPDATE tv_support_snippets SET label=%s, body=%s, updated_by=%s, updated_at=NOW() WHERE id=%s",
                        (label, body, who, sid))
        else:
            cur.execute("""INSERT INTO tv_support_snippets (label, body, position, updated_by)
                           VALUES (%s, %s, COALESCE((SELECT MAX(position) + 1 FROM tv_support_snippets), 0), %s)""",
                        (label, body, who))
        conn.commit()
    finally:
        conn.close()


def snippet_delete(sid):
    conn = db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tv_support_snippets WHERE id=%s", (sid,))
        conn.commit()
    finally:
        conn.close()


def record_sent(mid, cid, who):
    if not (DATABASE_URL and mid and who):
        return
    try:
        conn = db()
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO tv_support_sent (message_id, chat_id, sent_by) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                        (mid, cid, who))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        log("TV_SUPPORT_SENT_DB:", e)


def senders(ids):
    if not (DATABASE_URL and ids):
        return {}
    try:
        conn = db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT message_id, sent_by FROM tv_support_sent WHERE message_id = ANY(%s)", (list(ids),))
            return dict(cur.fetchall())
        finally:
            conn.close()
    except Exception as e:
        log("TV_SUPPORT_SENT_DB:", e)
        return {}


def ghl_assigned(contact_id):
    """True/False from the member's GHL tags, None when GHL can't say."""
    if not (GHL_API_KEY and contact_id):
        return None
    try:
        c = http.client.HTTPSConnection("services.leadconnectorhq.com", timeout=8)
        c.request("GET", "/contacts/" + quote(contact_id), None,
                  {"Authorization": "Bearer " + GHL_API_KEY, "Version": "2021-07-28", "Accept": "application/json"})
        r = c.getresponse()
        d = json.loads(r.read() or b"{}")
        if r.status >= 300:
            return None
        return ASSIGNED_TAG in [str(t).lower() for t in (d.get("contact") or {}).get("tags") or []]
    except Exception as e:
        log("TV_SUPPORT_GHL:", e)
        return None


def upload_image(img):
    """Browser sends the image base64; Whop wants it PUT to a presigned URL, then ready."""
    name = re.sub(r"[^A-Za-z0-9._-]", "_", str(img.get("name") or "image.jpg"))[:80] or "image.jpg"
    ctype = str(img.get("type") or "image/jpeg")
    if not ctype.startswith("image/"):
        raise WhopError(400, "Only images can be sent")
    data = base64.b64decode(str(img.get("data") or ""), validate=False)
    if not data or len(data) > MAX_IMAGE:
        raise WhopError(400, "Image is empty or too big (3MB max)")
    f = whop("POST", "/files", {"filename": name})
    url = f.get("upload_url")
    if not url:
        raise WhopError(502, "Whop didn't return an upload URL")
    u = urlparse(url)
    h = {"Content-Type": ctype}
    h.update({k: v for k, v in (f.get("upload_headers") or {}).items() if isinstance(v, str)})
    c = http.client.HTTPSConnection(u.netloc, timeout=20)
    c.request("PUT", u.path + ("?" + u.query if u.query else ""), data, h)
    r = c.getresponse()
    r.read()
    if r.status >= 300:
        raise WhopError(502, "Image upload failed (%s)" % r.status)
    for _ in range(12):
        st = whop("GET", "/files/" + quote(f["id"]))
        if st.get("upload_status") == "ready":
            break
        if st.get("upload_status") == "failed":
            raise WhopError(502, "Whop couldn't process the image")
        time.sleep(0.5)
    return f["id"]


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
            cur.execute("""SELECT tier, setup_at, educator, scanner, tradingview, telegram, purchased_at, contact_id, removed_at, ended_at
                           FROM tv_members WHERE lower(email) = lower(%s)
                           ORDER BY purchased_at DESC NULLS LAST LIMIT 1""", (out["email"],))
            r = cur.fetchone()
            if r:
                out.update({"tier": r[0] or "", "setup": bool(r[1]), "educator": r[2] or "", "scanner": r[3] or "",
                            "tradingview": r[4] or "", "telegram": r[5] or "", "contact_id": r[7] or "",
                            "ended": bool(r[9])})
            return out
        finally:
            conn.close()
    except Exception as e:
        log("TV_SUPPORT_DB:", e)
        return {}


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _fmt_memberships(raw):
    """Whop memberships -> panel rows (best first) plus any tv_* metadata on them."""
    ms, meta = [], {}
    for m in raw:
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
    return ms, meta


def _with_db(ms, meta):
    out = {"memberships": ms}
    out.update(_db_member([m["id"] for m in ms if m["id"]]))
    if out.get("contact_id"):
        out["assigned"] = ghl_assigned(out["contact_id"])
    # Whop metadata fills anything our DB doesn't have
    for k, mk in (("tier", "tv_tier"), ("tradingview", "tv_tradingview"), ("telegram", "tv_telegram"),
                  ("educator", "tv_educator"), ("scanner", "tv_scanners")):
        if not out.get(k) and meta.get(mk):
            out[k] = meta[mk]
    return out


def _member_email(mb):
    u = mb.get("user") if isinstance(mb.get("user"), dict) else {}
    return (mb.get("email") or u.get("email") or "").strip()


def whop_account(uid):
    """(email, name) on the Whop account that's chatting. Checked against the user id, so an ignored filter
    can't hand back someone else's."""
    email = name = ""
    try:
        d = whop("GET", "/members?account_id=%s&user_ids=%s&first=10" % (WHOP_COMPANY, quote(uid)))
        for mb in d.get("data") or []:
            u = mb.get("user") if isinstance(mb, dict) and isinstance(mb.get("user"), dict) else {}
            if (u.get("id") or mb.get("user_id")) == uid:
                email = _member_email(mb)
                name = (u.get("name") or mb.get("name") or "").strip()
                break
    except Exception as e:
        log("TV_SUPPORT_WHOP_EMAIL:", e)
    if not name:
        try:
            name = (whop("GET", "/users/" + quote(uid)).get("name") or "").strip()
        except Exception as e:
            log("TV_SUPPORT_WHOP_NAME:", e)
    return email, name


def _full_name(n):
    """Only a real-looking full name is worth matching on: two or more words, letters only."""
    n = " ".join((n or "").split())
    parts = n.split(" ")
    return n if len(parts) >= 2 and all(re.fullmatch(r"[^\W\d_](?:[^\W\d_]|['.-])*", p) for p in parts) and len(n) >= 5 else ""


def by_name(name, skip):
    """Purchases under exactly the same full name (another Whop account, same person, usually)."""
    name = _full_name(name)
    if not name:
        return []
    emails = []
    if DATABASE_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
            try:
                cur = conn.cursor()
                cur.execute("""SELECT lower(email) FROM tv_payments WHERE lower(trim(name)) = lower(%s) AND email <> ''
                               GROUP BY lower(email) ORDER BY max(paid_at) DESC LIMIT 3""", (name,))
                emails = [r[0] for r in cur.fetchall()]
            finally:
                conn.close()
        except Exception as e:
            log("TV_SUPPORT_BYNAME_DB:", e)
    try:
        found = whop("GET", "/members?account_id=%s&query=%s&first=10" % (WHOP_COMPANY, quote(name)))
        for mb in found.get("data") or []:
            u = mb.get("user") if isinstance(mb, dict) and isinstance(mb.get("user"), dict) else {}
            nm = " ".join((u.get("name") or mb.get("name") or "").split()).lower()
            e = _member_email(mb).lower()
            if nm == name.lower() and e and e not in emails:
                emails.append(e)
    except Exception as e:
        log("TV_SUPPORT_BYNAME_SEARCH:", e)
    skip = {x.lower() for x in skip if x}
    emails = [e for e in emails if e not in skip][:3]
    if not emails:
        return []
    with ThreadPoolExecutor(len(emails)) as ex:
        hits = [x for x in ex.map(by_email, emails) if x]
    for h in hits:
        h["via"] = "name"
        h["matched_name"] = name
    return hits


def by_email(email):
    """Purchases under an email the customer typed in the chat. Often a different Whop account from the one
    chatting (e.g. Apple Pay checkout with another email)."""
    ids = []
    if DATABASE_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
            try:
                cur = conn.cursor()
                cur.execute("""SELECT membership_id FROM tv_payments WHERE lower(email) = lower(%s) AND membership_id <> ''
                               GROUP BY membership_id ORDER BY max(paid_at) DESC LIMIT 5""", (email,))
                ids = [r[0] for r in cur.fetchall() if r[0]]
            finally:
                conn.close()
        except Exception as e:
            log("TV_SUPPORT_BYEMAIL_DB:", e)
    seen = {}

    def one(mid):
        try:
            return whop("GET", "/memberships/" + quote(mid))
        except Exception as e:
            log("TV_SUPPORT_BYEMAIL_MEM:", mid, e)
    for m in filter(None, [one(mid) for mid in ids]):
        seen[m.get("id")] = m
    try:
        found = whop("GET", "/members?account_id=%s&query=%s&first=10" % (WHOP_COMPANY, quote(email)))
        for mb in found.get("data") or []:
            if not isinstance(mb, dict) or _member_email(mb).lower() != email.lower() or not mb.get("id"):
                continue
            page = whop("GET", "/memberships?account_id=%s&member_id=%s&first=25" % (WHOP_COMPANY, quote(mb["id"])))
            for m in page.get("data") or []:
                if isinstance(m, dict):
                    seen.setdefault(m.get("id"), m)
    except Exception as e:
        log("TV_SUPPORT_BYEMAIL_SEARCH:", e)
    if not seen:
        return None
    out = _with_db(*_fmt_memberships(list(seen.values())))
    out["lookup"] = email
    return out


def member(uid):
    with ThreadPoolExecutor(2) as ex:
        fe = ex.submit(whop_account, uid)
        try:
            d = whop("GET", "/memberships?account_id=%s&user_id=%s&first=25" % (WHOP_COMPANY, quote(uid)))
        except WhopError as e:
            log("TV_SUPPORT_MEMBERSHIPS:", e)
            email, name = fe.result()
            return {"memberships": [], "error": str(e), "whop_email": email, "whop_name": name}
        out = _with_db(*_fmt_memberships(d.get("data") or []))
        out["whop_email"], out["whop_name"] = fe.result()
    return out


def typed_emails(msgs, uid, known):
    """Emails the customer wrote in the chat that aren't already on their record."""
    skip = {e.lower() for e in known if e}
    found = []
    for m in msgs:
        if m.get("team") or (uid and m.get("author_id") and m["author_id"] != uid):
            continue
        for e in EMAIL_RE.findall(m.get("text") or ""):
            e = e.strip(".").lower()
            if e not in skip and e not in found:
                found.append(e)
    return found[-3:]


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def _authed(self):
        auth = self.headers.get("Authorization", "")
        self.who = verify_token(auth[7:]) if auth.startswith("Bearer ") else None
        if not self.who:
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
            if qs.get("snippets") == "1":
                return self._json(200, {"ok": True, "snippets": snippets(), "me": self.who})
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
                        mb = fu.result()
                        emails = typed_emails(msgs, uid, [mb.get("email"), mb.get("whop_email")])
                        if emails:
                            with ThreadPoolExecutor(len(emails)) as ex2:
                                mb["typed"] = [x for x in ex2.map(by_email, emails) if x]
                        # nothing on this account and nothing from a typed email: try the same full name
                        if not (mb.get("tier") or mb.get("typed")):
                            mb["typed"] = by_name(mb.get("whop_name") or mb.get("name"),
                                                  [mb.get("email"), mb.get("whop_email")] + emails)
                        body["member"] = mb
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
            length = min(int(self.headers.get("Content-Length", 0)), 4_500_000)
            b = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"ok": False, "error": "Invalid request"})
        cid = str(b.get("c") or "")
        action = b.get("action")
        if action in ("snippet_save", "snippet_delete"):
            try:
                sid = int(b.get("id") or 0)
                if action == "snippet_delete":
                    if not sid:
                        return self._json(400, {"ok": False, "error": "Invalid reply"})
                    snippet_delete(sid)
                else:
                    label = str(b.get("label") or "").strip()[:40]
                    body = str(b.get("body") or "").strip()[:5000]
                    if not label or not body:
                        return self._json(400, {"ok": False, "error": "Give it a name and a message"})
                    snippet_save(sid, label, body, self.who)
                return self._json(200, {"ok": True, "snippets": snippets()})
            except Exception as e:
                log("TV_SUPPORT_SNIPPET_ERR:", e)
                return self._json(502, {"ok": False, "error": str(e)})
        if action in ("resolve", "reopen"):
            if not ID_RE.match(cid):
                return self._json(400, {"ok": False, "error": "Invalid chat"})
            try:
                whop("POST", "/channels/%s/%s" % (quote(cid), action), {})
            except WhopError as e:
                if e.status != 409:  # 409: already in that state
                    log("TV_SUPPORT_%s_ERR:" % action.upper(), e.status, e)
                    return self._json(502, {"ok": False, "error": str(e)})
            try:
                set_state(cid, action == "resolve", self.who)
            except Exception as e:
                log("TV_SUPPORT_STATE_DB:", e)
                return self._json(502, {"ok": False, "error": "Saved in Whop, but couldn't save it here: %s" % e})
            log("TV_SUPPORT", action, cid)
            return self._json(200, {"ok": True, "resolved": action == "resolve"})
        text = str(b.get("text") or "").strip()
        reply = str(b.get("reply_to") or "")
        img = b.get("image") if isinstance(b.get("image"), dict) else None
        if not ID_RE.match(cid) or not (text or img) or len(text) > 5000 or (reply and not ID_RE.match(reply)):
            return self._json(400, {"ok": False, "error": "Invalid message"})
        body = {"channel_id": cid, "content": text, "auto_detect_links": bool(text)}
        if img:
            try:
                body["attachments"] = [{"id": upload_image(img)}]
            except WhopError as e:
                log("TV_SUPPORT_UPLOAD_ERR:", e.status, e)
                return self._json(502, {"ok": False, "error": str(e)})
            except Exception as e:
                log("TV_SUPPORT_UPLOAD_ERR:", e)
                return self._json(502, {"ok": False, "error": "Image upload failed: %s" % e})
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
        log("TV_SUPPORT_SENT", cid, self.who)
        msg = _msg(m)
        record_sent(msg.get("id"), cid, self.who)
        msg["sent_by"] = self.who
        self._json(200, {"ok": True, "message": msg})

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
