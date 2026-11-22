"""Where did a trial signup come from, when the checkout itself didn't record it?

Looks the email up in places that saved the visitor's source when they signed up for something earlier:
  1. tv_pass_claims   - Killshot game pass (utm_*, fbclid, referrer, affiliate code)
  2. jb_webinar_regs  - webinar registrations (same fields)
  3. GHL contact      - GHL's own first/last attribution (utm, fbclid, referrer, session source)
The earliest record that names a real source wins. Returns (src, detail, ad, campaign) or None.

src: meta (paid Meta ad) | social (Facebook/Instagram/TikTok/X, not tagged as an ad) | youtube | seo (Google etc.
or the /learn articles) | email | affiliate | direct (a record exists but it names no source).
"""
import http.client
import json
import os
import re
import sys

GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = os.environ.get("GHL_LOCATION_ID", "") or os.environ.get("GHL_LOCATION", "")


def log(*a):
    print(*a, file=sys.stderr)


def classify(utm=None, ref="", aff="", session_source=""):
    """(src, detail, ad, campaign) for one record's fields; src '' when nothing usable."""
    u = utm if isinstance(utm, dict) else {}
    s = (u.get("utm_source") or u.get("utmSource") or "").strip().lower()
    m = (u.get("utm_medium") or u.get("utmMedium") or u.get("medium") or "").strip().lower()
    camp = (u.get("utm_campaign") or u.get("utmCampaign") or u.get("campaign") or "").strip()
    content = (u.get("utm_content") or u.get("utmContent") or "").strip()
    fb = u.get("fbclid") or u.get("fbclid") or ""
    r = (ref or u.get("referrer") or "").strip().lower()
    host = re.sub(r"^www\.|^m\.|^l\.|^lm\.", "", re.sub(r"^https?://", "", r).split("/")[0])
    ss = (session_source or "").strip().lower()
    if aff:
        return "affiliate", "affiliate link ?ref=" + aff, "", camp
    if s in ("meta", "facebook", "fb", "instagram", "ig") and (m in ("paid", "cpc", "paid_social", "paidsocial", "ads") or s == "meta"):
        return "meta", "Meta ad" + (" · " + content if content else ""), content, camp
    if s in ("ghl", "email") or m == "email":
        return "email", "email" + (" · " + camp if camp else ""), "", camp
    if s in ("youtube", "yt") or "youtube" in host or host == "youtu.be":
        return "youtube", "YouTube" + (" · " + (camp or content) if (camp or content) else ""), "", camp
    if fb or s in ("facebook", "fb", "instagram", "ig", "tiktok", "twitter", "x") or \
            any(h in host for h in ("facebook.com", "instagram.com", "tiktok.com", "t.co", "twitter.com", "x.com", "threads.net")) or \
            "paid social" in ss or "social" in ss:
        if "paid" in ss:
            return "meta", "Meta ad (from GHL)", "", camp
        return "social", "social" + (" · " + (s or host) if (s or host) else ""), "", camp
    if any(h in host for h in ("google.", "bing.com", "duckduckgo.com", "yahoo.", "ecosia.org", "brave.com")) or "organic search" in ss:
        return "seo", "search · " + (host or "organic"), "", camp
    if "thetradevault.co/learn" in r:
        return "seo", "blog article · " + r.split("thetradevault.co")[-1][:60], "", camp
    if s:
        return s[:20], "utm_source=" + s, content, camp
    return "", "", "", ""


def _ghl(path):
    c = http.client.HTTPSConnection("services.leadconnectorhq.com", timeout=6)
    c.request("GET", path, headers={"Authorization": "Bearer " + GHL_API_KEY, "Version": "2021-07-28", "Accept": "application/json"})
    r = c.getresponse()
    body = r.read()
    return json.loads(body or b"{}") if r.status < 300 else {}


def ghl_attribution(email):
    """[(fields, referrer, session_source)] from the GHL contact's first + last attribution."""
    if not (GHL_API_KEY and GHL_LOCATION and email):
        return []
    try:
        from urllib.parse import quote
        d = _ghl("/contacts/search/duplicate?locationId=%s&email=%s" % (GHL_LOCATION, quote(email)))
        cid = (d.get("contact") or {}).get("id")
        if not cid:
            return []
        ct = _ghl("/contacts/" + cid).get("contact") or {}
        out = []
        for k in ("attributionSource", "lastAttributionSource"):
            a = ct.get(k)
            if isinstance(a, dict) and a:
                out.append((a, a.get("referrer") or a.get("url") or "", a.get("sessionSource") or ""))
        for a in ct.get("attributions") or []:
            if isinstance(a, dict):
                out.append((a, a.get("referrer") or a.get("url") or "", a.get("sessionSource") or ""))
        return out
    except Exception as e:
        log("TV_TRACE_GHL_ERR", e)
        return []


def trace(cur, email):
    found = []  # (src, detail, ad, campaign)
    for table, label in (("tv_pass_claims", "Killshot game"), ("jb_webinar_regs", "webinar sign-up")):
        try:
            cur.execute("SAVEPOINT tr")
            cur.execute("SELECT t.utm, t.ref, to_jsonb(t)->>'aff' FROM %s t WHERE lower(t.email) = %%s ORDER BY t.created_at ASC LIMIT 5" % table, (email,))
            for utm, ref, aff in cur.fetchall():
                if isinstance(utm, str):
                    try:
                        utm = json.loads(utm)
                    except Exception:
                        utm = {}
                c = classify(utm, ref or "", aff or "")
                if c[0]:
                    found.append((c[0], label + " · " + c[1], c[2], c[3]))
                else:
                    found.append(("direct", label + " · no source on the link", "", ""))
            cur.execute("RELEASE SAVEPOINT tr")
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT tr")
            log("TV_TRACE_DB_ERR", table, e)
    real = [f for f in found if f[0] != "direct"]
    if real:
        return real[0]
    for fields, ref, ss in ghl_attribution(email):
        c = classify(fields, ref, "", ss)
        if c[0]:
            return (c[0], "GHL first touch · " + c[1], c[2], c[3])
    return found[0] if found else None
