"""TradeVault <-> Whop memberships.

The trading portal reads only Whop, so each member's setup answers are written onto the metadata
of their Whop membership(s):
  tv_tier        tools | community | elite
  tv_scanners    comma list of killshot, smartshot, spectrum
  tv_educator    jay | adam | tyler | andrew, "all" (Elite) or "none" (Tools)
  tv_tradingview TradingView username
  tv_telegram    Telegram username (when given)
  tv_setup_at    ISO time setup was completed
Whop's PATCH replaces the whole metadata object, so existing keys (e.g. the affiliate's tv_ref from
checkout) are read first and kept. Membership ids come from tv_payments (filled from the Whop
payment when missing). sync() also reports whether any of the member's memberships is still valid,
which drives "Remove access" on the members board.
"""
import http.client
import json
import os
import sys

WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
VALID = {"active", "trialing", "past_due"}
EDU_KEYS = {"jay bonham": "jay", "adam haase": "adam", "tyler collins": "tyler", "andrew bridges": "andrew"}
SCAN_KEYS = {"killshot": "killshot", "smartshot": "smartshot", "spectrum": "spectrum"}
ALL_SCANNERS = "killshot,smartshot,spectrum"


def log(*a):
    print(*a, file=sys.stderr)


def whop(method, path, body=None):
    c = http.client.HTTPSConnection("api.whop.com", timeout=10)
    c.request(method, path, json.dumps(body) if body is not None else None,
              {"Authorization": "Bearer " + WHOP_API_KEY, "Accept": "application/json",
               "Content-Type": "application/json"})
    r = c.getresponse()
    raw = r.read()
    if r.status >= 300:
        raise RuntimeError("Whop %s %s %s: %s" % (method, path.split("?")[0], r.status, raw[:200].decode("utf-8", "replace")))
    return json.loads(raw or b"{}")


def _utc(iso):
    """Setup time as UTC to the second, so re-syncs compare equal whatever the DB session timezone."""
    import datetime
    try:
        return datetime.datetime.fromisoformat(str(iso)).astimezone(datetime.timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return str(iso or "")


def meta_for(row):
    """The metadata the portal reads, from a tv_members row (as _tv_db.all_members returns it)."""
    tier = row.get("tier") or ""
    scanner = (row.get("scanner") or "").strip().lower()
    if tier in ("elite", "tools") or scanner.startswith("all") or not scanner:
        scanners = ALL_SCANNERS
    else:
        scanners = SCAN_KEYS.get(scanner, scanner)
    educator = (row.get("educator") or "").strip().lower()
    educator = "all" if tier == "elite" else "none" if tier == "tools" else EDU_KEYS.get(educator, educator or "none")
    out = {"tv_tier": tier, "tv_scanners": scanners, "tv_educator": educator,
           "tv_tradingview": row.get("tradingview") or "", "tv_telegram": row.get("telegram") or "",
           "tv_setup_at": _utc(row.get("setup_at"))}
    return {k: str(v)[:500] for k, v in out.items() if v}


def membership_ids(cur, email):
    """The member's Whop membership ids, newest first; fills in any tv_payments row missing one."""
    cur.execute("SELECT whop_id FROM tv_payments WHERE email = %s AND membership_id IS NULL", (email,))
    for (wid,) in cur.fetchall():
        try:
            p = whop("GET", "/api/v1/payments/" + wid)
            m = p.get("membership_id") or (p["membership"].get("id") if isinstance(p.get("membership"), dict) else p.get("membership"))
            if m:
                cur.execute("UPDATE tv_payments SET membership_id = %s WHERE whop_id = %s", (str(m), wid))
        except Exception as e:
            log("TV_WHOP_PAYMENT_ERR:", e)
    cur.execute("""SELECT membership_id FROM tv_payments WHERE email = %s AND membership_id IS NOT NULL
                   GROUP BY membership_id ORDER BY MAX(paid_at) DESC""", (email,))
    return [r[0] for r in cur.fetchall()]


def sync(cur, row):
    """Write the setup answers onto every membership of this member (if they've done setup) and
    report {memberships, valid, written}. Raises nothing; errors are logged and counted."""
    out = {"memberships": 0, "valid": None, "written": 0, "errors": 0}
    email = (row.get("email") or "").lower()
    if not (WHOP_API_KEY and email):
        return out
    ids = membership_ids(cur, email)
    out["memberships"] = len(ids)
    want = meta_for(row) if row.get("setup_at") and row.get("tradingview") else None
    for mid in ids:
        try:
            m = whop("GET", "/api/v1/memberships/" + mid)
            ok = str(m.get("status") or "") in VALID
            out["valid"] = bool(out["valid"]) or ok
            if want:
                meta = dict(m.get("metadata") or {}) if isinstance(m.get("metadata"), dict) else {}
                if any(meta.get(k) != v for k, v in want.items()):
                    meta.update(want)
                    whop("PATCH", "/api/v1/memberships/" + mid, {"metadata": meta})
                    out["written"] += 1
        except Exception as e:
            out["errors"] += 1
            log("TV_WHOP_SYNC_ERR:", mid, e)
    return out
