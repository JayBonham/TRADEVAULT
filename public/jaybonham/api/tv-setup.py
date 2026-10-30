"""TradeVault member setup (page lives at thetradevault.co/setup).
GET  ?c=<GHL contact id>  or  ?email=<checkout email>
     -> {ok, contact, first, tier, done}   tier from the Whop webhook tags:
        tradevault-elite > tradevault-community > tradevault-tools
POST {c, educator, scanner, tradingview, telegram}
     Community picks 1 educator + 1 scanner; every tier gives a TradingView username.
     Writes to GHL: tags tv-setup-complete (+ tv-educator-<x>, tv-scanner-<x> for Community),
     custom fields tv_educator / tv_scanner / tradingview_username / telegram_username
     (when they exist in GHL), and a note with the full choice. Choices lock once made.
"""
import http.client
import json
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
import _tv_db
from _tv_groups import groups_for

GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"
GHL_HOST = "services.leadconnectorhq.com"

ORIGINS = {"https://thetradevault.co", "https://www.thetradevault.co", "https://start.thetradevault.co"}
EDUCATORS = {"jay": "Jay Bonham", "adam": "Adam Haase", "tyler": "Tyler Collins", "andrew": "Andrew Bridges"}
SCANNERS = {"killshot": "Killshot", "smartshot": "Smartshot", "spectrum": "Spectrum"}
TIERS = (("tradevault-elite", "elite"), ("tradevault-community", "community"), ("tradevault-tools", "tools"))
DONE_TAG = "tv-setup-complete"
def _educator_key(tags):
    return next((k for k in EDUCATORS if "tv-educator-" + k in tags), "")
CID_RE = re.compile(r"^[A-Za-z0-9]{10,40}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
HANDLE_RE = re.compile(r"^[A-Za-z0-9_.\-]{2,40}$")


def log(*a):
    print(*a, file=sys.stderr)


def _clip(v, n):
    return v.strip()[:n] if isinstance(v, str) else ""


def _ghl(method, path, body=None):
    headers = {"Authorization": "Bearer " + GHL_API_KEY, "Version": "2021-07-28",
               "Content-Type": "application/json", "Accept": "application/json"}
    c = http.client.HTTPSConnection(GHL_HOST, timeout=8)
    c.request(method, path, json.dumps(body) if body is not None else None, headers)
    r = c.getresponse()
    raw = r.read()
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        data = {}
    if r.status >= 300:
        log("TV_SETUP_GHL:", method, path.split("?")[0], r.status, raw[:300])
    return r.status, data


def _tier(tags):
    tags = {t.lower() for t in tags or []}
    for tag, tier in TIERS:
        if tag in tags:
            return tier
    return None


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        contact = self._find(_clip((q.get("c") or [""])[0], 40), _clip((q.get("email") or [""])[0], 160).lower())
        if contact is None:
            return
        tier = _tier(contact.get("tags"))
        if not tier:
            return self._json(404, {"ok": False, "error": "not_member"})
        tags = [t.lower() for t in contact.get("tags") or []]
        done = DONE_TAG in tags
        self._json(200, {"ok": True, "contact": contact["id"], "first": contact.get("firstName") or "",
                         "tier": tier, "done": done,
                         "groups": groups_for(tier, _educator_key(tags)) if done else []})

    def do_POST(self):
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 4000)
            b = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"ok": False, "error": "Invalid request"})

        contact = self._find(_clip(b.get("c"), 40), "")
        if contact is None:
            return
        tags = [t.lower() for t in contact.get("tags") or []]
        tier = _tier(tags)
        if not tier:
            return self._json(404, {"ok": False, "error": "not_member"})
        if DONE_TAG in tags:
            return self._json(409, {"ok": False, "error": "already_done"})

        tv = _clip(b.get("tradingview"), 40).lstrip("@")
        tg = _clip(b.get("telegram"), 40).lstrip("@")
        if not HANDLE_RE.match(tv):
            return self._json(400, {"ok": False, "error": "Please enter your TradingView username."})
        if tier != "tools" and not tg:
            return self._json(400, {"ok": False, "error": "Please enter your Telegram username so we can approve you."})
        if tg and not HANDLE_RE.match(tg):
            return self._json(400, {"ok": False, "error": "That Telegram username doesn't look right."})

        educator = scanner = ""
        new_tags = [DONE_TAG]
        if tier == "community":
            educator = _clip(b.get("educator"), 20).lower()
            scanner = _clip(b.get("scanner"), 20).lower()
            if educator not in EDUCATORS or scanner not in SCANNERS:
                return self._json(400, {"ok": False, "error": "Please choose an educator and a scanner."})
            new_tags += ["tv-educator-" + educator, "tv-scanner-" + scanner]

        cid = contact["id"]
        edu_name = EDUCATORS.get(educator, "All educators" if tier == "elite" else "")
        scan_name = SCANNERS.get(scanner, "All scanners")
        self._fields(cid, {"tv_educator": edu_name, "tv_scanner": scan_name,
                           "tradingview_username": tv, "telegram_username": tg})
        _ghl("POST", "/contacts/" + cid + "/notes", {"body": "\n".join(filter(None, [
            "TradeVault setup (" + tier.title() + ")",
            "Educator: " + edu_name if edu_name else "",
            "Scanner: " + scan_name,
            "TradingView: " + tv,
            "Telegram: @" + tg if tg else "",
        ]))})
        _tv_db.record_setup(cid, (contact.get("email") or "").lower(), tier, edu_name, scan_name, tv, tg)
        # tags last: automations fire on them, so fields and note are already in place
        status, _ = _ghl("POST", "/contacts/" + cid + "/tags", {"tags": new_tags})
        if status >= 300:
            return self._json(502, {"ok": False, "error": "We couldn't save that. Please try again."})
        log("TV_SETUP", cid, tier, educator or "-", scanner or "-")
        self._json(200, {"ok": True, "tier": tier, "educator": edu_name, "scanner": scan_name,
                         "groups": groups_for(tier, educator)})

    # ── helpers ──────────────────────────────────────────────
    def _find(self, cid, email):
        """Contact by id, else by email. Writes the error response and returns None on failure."""
        if not GHL_API_KEY:
            self._json(500, {"ok": False, "error": "Setup is unavailable right now."})
            return None
        try:
            if CID_RE.match(cid):
                status, data = _ghl("GET", "/contacts/" + cid)
                if status < 300 and data.get("contact"):
                    return data["contact"]
            elif EMAIL_RE.match(email):
                status, data = _ghl("GET", "/contacts/search/duplicate?locationId=" + GHL_LOCATION +
                                    "&email=" + urllib.parse.quote(email))
                found = (data.get("contact") or {}).get("id") if status < 300 else None
                if found:
                    status, data = _ghl("GET", "/contacts/" + found)
                    if status < 300 and data.get("contact"):
                        return data["contact"]
            else:
                self._json(400, {"ok": False, "error": "missing"})
                return None
        except Exception as e:
            log("TV_SETUP_ERR:", e)
            self._json(502, {"ok": False, "error": "Setup is unavailable right now."})
            return None
        self._json(404, {"ok": False, "error": "not_found"})
        return None

    def _fields(self, cid, values):
        """Fill the GHL custom fields, by id when the field list is readable, else by key."""
        try:
            status, data = _ghl("GET", "/locations/" + GHL_LOCATION + "/customFields?model=contact")
            ids = {}
            for f in data.get("customFields") or []:
                key = (f.get("fieldKey") or "").split(".")[-1].lower()
                if key in values:
                    ids[key] = f.get("id")
            fields = [{"id": ids[k], "field_value": v} if ids.get(k) else {"key": k, "field_value": v}
                      for k, v in values.items() if v]
            if fields:
                status, _ = _ghl("PUT", "/contacts/" + cid, {"customFields": fields})
                log("TV_SETUP_FIELDS:", status, len(ids), "ids")
        except Exception as e:
            log("TV_SETUP_FIELDS_ERR:", e)

    def _json(self, status, body):
        self.send_response(status)
        origin = self.headers.get("Origin", "")
        if origin in ORIGINS or origin.startswith("http://localhost"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())
