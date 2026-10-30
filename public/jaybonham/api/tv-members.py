"""TradeVault members board (page lives at thetradevault.co/admin). Admin token required.
GET  -> {ok, members:[{id, name, email, tier, setup, assigned, educator, scanner,
                       tradingview, telegram, joined}]}
        everyone tagged tradevault-purchased (set by the Whop webhook), read live from GHL.
POST {action: "assign"|"unassign", c}
        assign adds tv-access-granted; the GHL "Access Granted" workflow triggers on that tag,
        moves the card and emails the member. unassign removes the tag (no email is unsent).
"""
import http.client
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token
import _tv_db

GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"
GHL_HOST = "services.leadconnectorhq.com"

MEMBER_TAG = "tradevault-purchased"
ASSIGNED_TAG = "tv-access-granted"
DONE_TAG = "tv-setup-complete"
TIERS = (("tradevault-elite", "elite"), ("tradevault-community", "community"), ("tradevault-tools", "tools"))
EDUCATORS = {"jay": "Jay Bonham", "adam": "Adam Haase", "tyler": "Tyler Collins", "andrew": "Andrew Bridges"}
SCANNERS = {"killshot": "Killshot", "smartshot": "Smartshot", "spectrum": "Spectrum"}
FIELD_KEYS = ("tv_educator", "tv_scanner", "tradingview_username", "telegram_username")
CID_RE = re.compile(r"^[A-Za-z0-9]{10,40}$")
PAGE = 100


def log(*a):
    print(*a, file=sys.stderr)


def _ghl(method, path, body=None):
    headers = {"Authorization": "Bearer " + GHL_API_KEY, "Version": "2021-07-28",
               "Content-Type": "application/json", "Accept": "application/json"}
    c = http.client.HTTPSConnection(GHL_HOST, timeout=12)
    c.request(method, path, json.dumps(body) if body is not None else None, headers)
    r = c.getresponse()
    raw = r.read()
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        data = {}
    if r.status >= 300:
        log("TV_MEMBERS_GHL:", method, path.split("?")[0], r.status, raw[:300])
    return r.status, data, raw


# GHL's search accepts a few filter shapes depending on API version; try each until one works.
FILTERS = (
    [{"field": "tags", "operator": "contains", "value": [MEMBER_TAG]}],
    [{"field": "tags", "operator": "eq", "value": MEMBER_TAG}],
    [{"field": "tags", "operator": "contains", "value": MEMBER_TAG}],
)


def _search():
    last_err = ""
    for flt in FILTERS:
        out, page = [], 1
        while page <= 20:
            status, data, raw = _ghl("POST", "/contacts/search", {
                "locationId": GHL_LOCATION, "page": page, "pageLimit": PAGE, "filters": flt})
            if status >= 300:
                last_err = "GHL %s: %s" % (status, raw[:200].decode(errors="replace"))
                out = None
                break
            batch = data.get("contacts") or []
            out += batch
            if len(batch) < PAGE or len(out) >= (data.get("total") or 0):
                break
            page += 1
        if out is not None:
            # guard against a filter shape GHL accepted but ignored
            return [c for c in out if MEMBER_TAG in [t.lower() for t in c.get("tags") or []]], ""
    return None, last_err


def _field_ids():
    status, data, _ = _ghl("GET", "/locations/" + GHL_LOCATION + "/customFields?model=contact")
    ids = {}
    for f in data.get("customFields") or []:
        key = (f.get("fieldKey") or "").split(".")[-1].lower()
        if key in FIELD_KEYS:
            ids[f.get("id")] = key
    return ids


NOTE_KEYS = {"educator": "educator", "scanner": "scanner", "tradingview": "tradingview", "telegram": "telegram"}


def _from_note(cid):
    """Setup answers from the note tv-setup leaves on the contact (for rows the DB doesn't have)."""
    status, data, _ = _ghl("GET", "/contacts/" + cid + "/notes")
    for n in data.get("notes") or []:
        body = n.get("body") or ""
        if not body.startswith("TradeVault setup"):
            continue
        out = {}
        for line in body.splitlines()[1:]:
            k, _, v = line.partition(":")
            k = NOTE_KEYS.get(k.strip().lower())
            if k:
                out[k] = v.strip().lstrip("@")
        return out
    return {}


def _member(c, ids, db):
    tags = [t.lower() for t in c.get("tags") or []]
    vals = {}
    for f in c.get("customFields") or []:
        key = ids.get(f.get("id"))
        if key:
            v = f.get("value", f.get("field_value"))
            vals[key] = v if isinstance(v, str) else ("" if v is None else str(v))
    row = db.get(c.get("id")) or {}
    tier = next((t for tag, t in TIERS if tag in tags), "")
    setup = DONE_TAG in tags
    educator = (row.get("educator") or vals.get("tv_educator") or
                next((n for k, n in EDUCATORS.items() if "tv-educator-" + k in tags), ""))
    scanner = (row.get("scanner") or vals.get("tv_scanner") or
               next((n for k, n in SCANNERS.items() if "tv-scanner-" + k in tags), ""))
    if setup and tier == "elite":
        educator, scanner = educator or "All educators", scanner or "All scanners"
    elif setup and tier == "tools":
        scanner = scanner or "All scanners"
    name = (c.get("contactName") or " ".join(filter(None, [c.get("firstName"), c.get("lastName")])) or "").strip()
    return {
        "id": c.get("id"), "name": name.title() if name.islower() else name, "email": c.get("email") or "",
        "tier": tier, "setup": setup, "assigned": ASSIGNED_TAG in tags,
        "educator": educator, "scanner": scanner,
        "tradingview": row.get("tradingview") or vals.get("tradingview_username", ""),
        "telegram": row.get("telegram") or vals.get("telegram_username", ""),
        "joined": row.get("purchased_at") or c.get("dateAdded") or "",
    }


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
        if not GHL_API_KEY:
            self._json(500, {"ok": False, "error": "GHL_API_KEY is not set"})
            return False
        return True

    def do_GET(self):
        if not self._authed():
            return
        try:
            contacts, err = _search()
            if contacts is None:
                return self._json(502, {"ok": False, "error": err or "GHL search failed"})
            ids = _field_ids()
            db = _tv_db.all_members()
            members = [_member(c, ids, db) for c in contacts]
            # set up before the DB copy existed: read their note once, then keep it in the DB
            for m in [m for m in members if m["setup"] and not m["tradingview"]][:25]:
                got = _from_note(m["id"])
                if got.get("tradingview"):
                    for k in ("tradingview", "telegram"):
                        m[k] = got.get(k, "")
                    if m["tier"] == "community":
                        m["educator"] = got.get("educator") or m["educator"]
                        m["scanner"] = got.get("scanner") or m["scanner"]
                    _tv_db.record_setup(m["id"], m["email"].lower(), m["tier"], m["educator"],
                                        m["scanner"], m["tradingview"], m["telegram"])
            members.sort(key=lambda m: m["joined"], reverse=True)
            self._json(200, {"ok": True, "members": members})
        except Exception as e:
            log("TV_MEMBERS_ERR:", e)
            self._json(502, {"ok": False, "error": str(e)})

    def do_POST(self):
        if not self._authed():
            return
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 2000)
            b = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"ok": False, "error": "Invalid request"})
        cid = str(b.get("c") or "")
        action = b.get("action")
        if not CID_RE.match(cid) or action not in ("assign", "unassign"):
            return self._json(400, {"ok": False, "error": "Invalid request"})
        method = "POST" if action == "assign" else "DELETE"
        status, _, raw = _ghl(method, "/contacts/" + cid + "/tags", {"tags": [ASSIGNED_TAG]})
        if status >= 300:
            return self._json(502, {"ok": False, "error": "GHL %s: %s" % (status, raw[:200].decode(errors="replace"))})
        log("TV_MEMBERS", action, cid)
        self._json(200, {"ok": True})

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
