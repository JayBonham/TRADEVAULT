"""TradeVault members board (page lives at thetradevault.co/admin). Admin token required.
GET  -> {ok, members:[{id, name, email, tier, setup, assigned, educator, scanner,
                       tradingview, telegram, joined}]}
        everyone tagged tradevault-purchased (set by the Whop webhook), read live from GHL.
POST {action: "assign"|"unassign"|"revoked"|"hide", c}
   hide: takes a test or junk contact off the board (GHL tag tv-hidden; remove the tag in GHL to bring it back)
        assign adds tv-access-granted; the GHL "Access Granted" workflow triggers on that tag,
        moves the card and emails the member. unassign removes the tag (no email is unsent).
        revoked: their Whop membership ended (ended=true, set by whop-hook) and they've been taken
        out of the scanners; removes the tag and records it, so they leave "Remove access".
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
from _tv_groups import groups_for

GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"
GHL_HOST = "services.leadconnectorhq.com"

MEMBER_TAG = "tradevault-purchased"
ASSIGNED_TAG = "tv-access-granted"
DONE_TAG = "tv-setup-complete"
PARTNER_TAG = "tradevault-partner"
HIDDEN_TAG = "tv-hidden"
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
    setup = DONE_TAG in tags or "tv-setup-trial" in tags
    educator = (row.get("educator") or vals.get("tv_educator") or
                next((n for k, n in EDUCATORS.items() if "tv-educator-" + k in tags), ""))
    scanner = (row.get("scanner") or vals.get("tv_scanner") or
               ", ".join(n for k, n in SCANNERS.items() if "tv-scanner-" + k in tags))
    # Elite and Tools include every scanner (Elite every educator too), so an upgrade from Community
    # shows that straight away instead of the one they picked before.
    if setup and tier == "elite":
        educator, scanner = "All educators", "All scanners"
    elif setup and tier == "tools":
        scanner = "All scanners"
    name = (c.get("contactName") or " ".join(filter(None, [c.get("firstName"), c.get("lastName")])) or "").strip()
    return {
        "id": c.get("id"), "name": name.title() if name.islower() else name, "email": c.get("email") or "",
        "tier": tier, "partner": PARTNER_TAG in tags, "upgraded": "tv-upgraded" in tags, "setup": setup, "assigned": ASSIGNED_TAG in tags,
        "educator": educator, "scanner": scanner,
        "tradingview": row.get("tradingview") or vals.get("tradingview_username", ""),
        "telegram": row.get("telegram") or vals.get("telegram_username", ""),
        "joined": row.get("purchased_at") or c.get("dateAdded") or "",
        "ended": bool(row.get("ended_at")), "ended_at": row.get("ended_at") or "",
        "nudged": max([int(t[15:]) for t in tags if t.startswith("tv-setup-nudge-") and t[15:].isdigit()] or [0]),
        "groups": [g["name"] for g in groups_for(tier, next((k for k in EDUCATORS if "tv-educator-" + k in tags), ""))],
    }


import _tv_trial  # noqa: E402
from _tv_trace import classify  # noqa: E402


def _sources():
    """{email: (src, detail)} for how each person first came in, from our own records (one query per table):
    affiliate referral > checkout / ad tracking (tv_signup_src) > Killshot game or webinar sign-up links.
    Contacts with none of these fall back to their GHL tags / attribution in _source()."""
    out = {}
    if not _tv_db.DATABASE_URL:
        return out
    try:
        conn, cur = _tv_db._conn()
    except Exception as e:
        log("TV_MEMBERS_SRC_DB:", e)
        return out

    def q(sql):
        try:
            cur.execute("SAVEPOINT s")
            cur.execute(sql)
            rows = cur.fetchall()
            cur.execute("RELEASE SAVEPOINT s")
            return rows
        except Exception as e:  # table not there yet
            cur.execute("ROLLBACK TO SAVEPOINT s")
            log("TV_MEMBERS_SRC_Q:", e)
            return []

    def put(email, src, detail, weak=False):
        e = (email or "").strip().lower()
        if e and src and (e not in out or (out[e][2] and not weak)):
            out[e] = (src, detail, weak)

    for email, name, code in q("SELECT r.email, a.name, a.code FROM tv_aff_referrals r JOIN tv_affiliates a ON a.id = r.affiliate_id"):
        put(email, "affiliate", name or code or "")
    for email, src, ad, camp in q("SELECT email, src, ad, campaign FROM tv_signup_src WHERE coalesce(src, '') <> ''"):
        put(email, src, ad or camp or "")
    for table, label in (("tv_pass_claims", "Killshot game"), ("jb_webinar_regs", "webinar")):
        for email, utm, ref, aff in q("SELECT email, utm, ref, to_jsonb(t)->>'aff' FROM %s t ORDER BY created_at ASC" % table):
            if isinstance(utm, str):
                try:
                    utm = json.loads(utm)
                except ValueError:
                    utm = {}
            c = classify(utm, ref or "", "", "")
            if aff:
                put(email, "affiliate", aff)
            elif c[0]:
                put(email, c[0], label + (" · " + c[2] if c[2] else ""))
            elif table == "jb_webinar_regs":
                put(email, "webinar", "", weak=True)  # a webinar sign-up with no link source: better than nothing
    try:
        conn.commit()
        conn.close()
    except Exception:
        pass
    return out


def _source(c, tags, srcs):
    e = (c.get("email") or "").lower()
    if e in srcs:
        return srcs[e][0], srcs[e][1]
    if "tv-src-meta-ads" in tags:
        ad = next((t[6:] for t in tags if t.startswith("tv-ad-")), "")
        return "meta", ad
    t = next((t[7:] for t in tags if t.startswith("tv-src-")), "")
    if t:
        return t, ""
    for k in ("attributionSource", "lastAttributionSource"):
        a = c.get(k)
        if isinstance(a, dict) and a:
            got = classify(a, a.get("referrer") or a.get("url") or "", "", a.get("sessionSource") or "")
            if got[0]:
                return got[0], "GHL"
    return "", ""


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
            # GHL's search index lags a few minutes behind new tags: fetch recorded buyers it hasn't caught up on.
            seen = {c.get("id") for c in contacts}
            for cid in [k for k in db if k not in seen][:40]:
                status, data, _ = _ghl("GET", "/contacts/" + cid)
                c = data.get("contact") if status < 300 else None
                if c and MEMBER_TAG in [t.lower() for t in c.get("tags") or []]:
                    contacts.append(c)
            contacts = [c for c in contacts if HIDDEN_TAG not in [t.lower() for t in c.get("tags") or []]]
            members = [_member(c, ids, db) for c in contacts]
            try:
                srcs = _sources()
                for c, m in zip(contacts, members):
                    m["src"], m["src_detail"] = _source(c, [t.lower() for t in c.get("tags") or []], srcs)
            except Exception as e:  # never let attribution break the board
                log("TV_MEMBERS_SRC_ERR:", e)
            trials = _tv_trial.trials_by_email()
            for m in members:
                t = trials.get((m["email"] or "").lower()) or trials.get((db.get(m["id"]) or {}).get("email", ""))
                if t:
                    m["trial"] = t
                    # scanners and signals wait for the first payment: only the community group during the trial
                    m["groups"] = [g["name"] for g in groups_for(m["tier"], "", trial=True)]
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
        if not CID_RE.match(cid) or action not in ("assign", "unassign", "revoked", "hide"):
            return self._json(400, {"ok": False, "error": "Invalid request"})
        method = "POST" if action in ("assign", "hide") else "DELETE"
        tag = HIDDEN_TAG if action == "hide" else ASSIGNED_TAG
        status, _, raw = _ghl(method, "/contacts/" + cid + "/tags", {"tags": [tag]})
        if status >= 300:
            return self._json(502, {"ok": False, "error": "GHL %s: %s" % (status, raw[:200].decode(errors="replace"))})
        if action == "revoked":
            _tv_db.set_removed(cid)
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
