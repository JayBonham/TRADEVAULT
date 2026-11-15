"""Public: published Whop reviews for the TradeVault products, for the sales pages.
GET -> {ok, avg, count, reviews:[{stars, title, text, name, date}]}
Names are shortened to first name + last initial. Cached for 30 minutes per warm instance.
Falls back to the whole store's reviews if the TradeVault products have none yet.
"""
import http.client
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import quote

WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
WHOP_COMPANY = "biz_R8QEgfRFt2KfLV"
ORIGINS = {"https://thetradevault.co", "https://www.thetradevault.co", "https://start.thetradevault.co"}
TTL = 1800
_CACHE = {"at": 0, "body": None}


def log(*a):
    print(*a, file=sys.stderr)


def whop(path):
    c = http.client.HTTPSConnection("api.whop.com", timeout=10)
    c.request("GET", "/api/v1" + path, None, {"Authorization": "Bearer " + WHOP_API_KEY, "Accept": "application/json"})
    r = c.getresponse()
    raw = r.read()
    if r.status >= 300:
        raise RuntimeError("Whop %s: %s" % (r.status, raw[:200].decode("utf-8", "replace")))
    return json.loads(raw or b"{}")


def short_name(u):
    u = u if isinstance(u, dict) else {}
    n = " ".join(str(u.get("name") or "").split())
    if n:
        parts = n.split(" ")
        return parts[0][:20] + (" " + parts[-1][0].upper() + "." if len(parts) > 1 and parts[-1] else "")
    return "Verified member"


def reviews_for(query):
    out, after = [], ""
    for _ in range(4):
        d = whop("/reviews?%s&first=50&order=created_at&direction=desc%s" % (query, "&after=" + quote(after) if after else ""))
        out += [r for r in d.get("data") or [] if isinstance(r, dict)]
        pi = d.get("page_info") or {}
        if not pi.get("has_next_page"):
            break
        after = pi.get("end_cursor") or ""
    return out


def load():
    prods = whop("/products?account_id=%s&first=100" % WHOP_COMPANY).get("data") or []
    tv = [p["id"] for p in prods if isinstance(p, dict) and p.get("id") and "tradevault" in str(p.get("title") or "").lower().replace(" ", "")]
    rows, seen = [], set()
    for pid in tv:
        for r in reviews_for("product_id=" + quote(pid)):
            if r.get("id") not in seen:
                seen.add(r.get("id")); rows.append(r)
    if not rows:
        rows = reviews_for("account_id=" + WHOP_COMPANY)
    stars = [int(r.get("stars") or 0) for r in rows if r.get("stars")]
    good = [r for r in rows if int(r.get("stars") or 0) >= 4 and len(str(r.get("description") or "").strip()) >= 25]
    good.sort(key=lambda r: (int(r.get("stars") or 0), str(r.get("created_at") or "")), reverse=True)
    return {"ok": True, "count": len(stars), "avg": round(sum(stars) / len(stars), 1) if stars else None,
            "reviews": [{"stars": int(r.get("stars") or 5), "title": str(r.get("title") or "")[:120],
                         "text": " ".join(str(r.get("description") or "").split())[:600], "name": short_name(r.get("user")),
                         "date": str(r.get("created_at") or "")[:10]} for r in good[:24]]}


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def do_GET(self):
        if not WHOP_API_KEY:
            return self._json(500, {"ok": False, "error": "not configured"})
        if _CACHE["body"] and time.time() - _CACHE["at"] < TTL:
            return self._json(200, _CACHE["body"])
        try:
            body = load()
            _CACHE.update(at=time.time(), body=body)
            self._json(200, body)
        except Exception as e:
            log("TV_REVIEWS_ERR:", e)
            if _CACHE["body"]:
                return self._json(200, _CACHE["body"])
            self._json(502, {"ok": False, "error": "unavailable"})

    def _json(self, status, body):
        self.send_response(status)
        origin = self.headers.get("Origin", "")
        if origin in ORIGINS or origin.startswith("http://localhost"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=600" if status == 200 else "no-store")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())
