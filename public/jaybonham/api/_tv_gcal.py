"""Google Calendar invites for the Trade Vault webinar (Workspace service account, domain-wide delegation).

Each session is one event on GOOGLE_CAL_USER's primary calendar with a fixed id (tvsessionYYYYMMDD).
Adding a registrant = adding them as a guest with sendUpdates=all, so Google sends the real invite:
Gmail puts it straight into their calendar, Apple / Outlook get Accept / Decline. Only new guests are emailed.
Guests can't see each other.

Env:
  GOOGLE_SA_JSON   the service account's JSON key (whole file contents)
  GOOGLE_CAL_USER  the Workspace user whose calendar holds the events, e.g. jay@thetradevault.co
"""
import base64
import http.client
import json
import os
import time
import urllib.parse
from datetime import timedelta

SA_JSON = os.environ.get("GOOGLE_SA_JSON", "")
CAL_USER = os.environ.get("GOOGLE_CAL_USER", "")
SCOPE = "https://www.googleapis.com/auth/calendar.events"


def enabled():
    return bool(SA_JSON and CAL_USER)


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _token():
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    sa = json.loads(SA_JSON)
    now = int(time.time())
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claim = _b64(json.dumps({"iss": sa["client_email"], "sub": CAL_USER, "scope": SCOPE,
                             "aud": "https://oauth2.googleapis.com/token", "iat": now, "exp": now + 3600}).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = _b64(key.sign((head + "." + claim).encode(), padding.PKCS1v15(), hashes.SHA256()))
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": head + "." + claim + "." + sig})
    c = http.client.HTTPSConnection("oauth2.googleapis.com", timeout=10)
    c.request("POST", "/token", body, {"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    data = json.loads(r.read() or b"{}")
    if r.status >= 300:
        raise RuntimeError("google token %s %s" % (r.status, str(data)[:200]))
    return data["access_token"]


def _api(tok, method, path, body=None, headers=None):
    h = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
    h.update(headers or {})
    c = http.client.HTTPSConnection("www.googleapis.com", timeout=10)
    c.request(method, "/calendar/v3/calendars/primary/events" + path, json.dumps(body) if body is not None else None, h)
    r = c.getresponse()
    raw = r.read()
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        data = {}
    return r.status, data


def add_guest(inv, day, email, name=""):
    """Add email as a guest on that night's event (creating the event if needed). Returns (ok, info)."""
    tok = _token()
    eid = "tvsession" + day.replace("-", "")
    start = inv.session_start(day)
    end = start + timedelta(minutes=inv.DURATION_MIN)
    guest = {"email": email}
    if name:
        guest["displayName"] = name[:80]
    for _ in range(4):
        st, ev = _api(tok, "GET", "/" + eid)
        if st == 404:
            event = {
                "id": eid, "summary": inv.TITLE, "description": inv.description(day), "location": inv.zoom(day)[0],
                "start": {"dateTime": start.isoformat().replace("+00:00", "Z"), "timeZone": "America/New_York"},
                "end": {"dateTime": end.isoformat().replace("+00:00", "Z"), "timeZone": "America/New_York"},
                "attendees": [guest], "guestsCanSeeOtherGuests": False, "guestsCanInviteOthers": False,
                "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 60}, {"method": "popup", "minutes": 10}]},
            }
            st, ev = _api(tok, "POST", "?sendUpdates=all", event)
            if st == 409:  # created by a parallel request; add to it instead
                continue
            return st < 300, "google created event %s (%s)" % (eid, st)
        if st >= 300:
            return False, "google get %s %s" % (st, str(ev)[:200])
        if ev.get("status") == "cancelled":
            return False, "event %s is cancelled" % eid
        guests = ev.get("attendees") or []
        if any((g.get("email") or "").lower() == email for g in guests):
            return True, "already a guest"
        st, res = _api(tok, "PATCH", "/" + eid + "?sendUpdates=all", {"attendees": guests + [guest]},
                       {"If-Match": ev.get("etag", "*")})
        if st == 412:  # someone else was added at the same moment; reload and retry
            continue
        return st < 300, "google added guest (%s)%s" % (st, "" if st < 300 else " " + str(res)[:200])
    return False, "google busy, try again"
