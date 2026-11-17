"""Whop membership transfers (a member moving their plan to another Whop account / email).

Whop sends a transfer as a brand-new $0 "purchase" on the new account (empty metadata, no pointer to the
old membership) and cancels the old one. Left alone that made a second card on the members board, lost
the affiliate's credit and flagged the original card for "Remove access".

A transfer is recognised by its fingerprint: a cancelled membership of the same product, on another Whop
user, with the exact same current_period_end. When found:
  - tv_membership_links: the new membership counts as the original card's (so ending the old one doesn't
    flag "Remove access", and upgrades see it),
  - tv_email_moves new email -> card email: later webhooks for the new email land on the original card,
    so its setup, access, commission and affiliate credit carry on,
  - the old membership's metadata (tv_ref, setup answers) is copied onto the new one in Whop.
"""
import datetime
import sys

import _tv_whop as W

TABLE = """CREATE TABLE IF NOT EXISTS tv_membership_links (
    membership_id TEXT PRIMARY KEY, email TEXT NOT NULL, from_membership TEXT, created_at TIMESTAMPTZ DEFAULT NOW())"""
DONE_STATUS = "statuses=canceled&statuses=completed&statuses=expired&statuses=canceling"


def log(*a):
    print(*a, file=sys.stderr)


def _ts(v):
    try:
        return datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _prod(m):
    p = m.get("product")
    return m.get("product_id") or (p.get("id") if isinstance(p, dict) else p)


def linked(cur, email):
    """Memberships tied to this card's email by a transfer."""
    cur.execute(TABLE)
    cur.execute("SELECT membership_id FROM tv_membership_links WHERE email = %s", (email,))
    return [r[0] for r in cur.fetchall()]


def detect(cur, new_mid):
    """(old membership id, card email, old metadata) if new_mid is a transfer of a membership we know, else None."""
    m = W.whop("GET", "/api/v1/memberships/" + new_mid)
    end, created, uid, prod = _ts(m.get("current_period_end")), m.get("created_at"), m.get("user_id"), _prod(m)
    if not (end and created and prod):
        return None
    page = W.whop("GET", "/api/v1/memberships?account_id=%s&product_ids=%s&%s&created_before=%s&first=50"
                  % (W.WHOP_COMPANY, prod, DONE_STATUS, str(created).replace("+", "%2B")))
    for o in page.get("data") or []:
        oe = _ts(o.get("current_period_end"))
        if o.get("id") == new_mid or (uid and o.get("user_id") == uid) or not oe:
            continue
        if abs((oe - end).total_seconds()) > 5:
            continue
        cur.execute("SELECT email FROM tv_payments WHERE membership_id = %s ORDER BY paid_at DESC LIMIT 1", (o["id"],))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT email FROM tv_membership_links WHERE membership_id = %s", (o["id"],))
            row = cur.fetchone()
        if row:
            return o["id"], row[0], (o.get("metadata") if isinstance(o.get("metadata"), dict) else {})
    return None


def handle(cur, new_mid, new_email):
    """The card email this membership belongs to when it's a transfer (recording it), else None."""
    if not (W.WHOP_API_KEY and new_mid):
        return None
    cur.execute(TABLE)
    cur.execute("SELECT email FROM tv_membership_links WHERE membership_id = %s", (new_mid,))
    row = cur.fetchone()
    if row:
        return row[0]
    found = detect(cur, new_mid)
    if not found:
        return None
    old_mid, card_email, meta = found
    new_email = (new_email or "").strip().lower()
    cur.execute("""INSERT INTO tv_membership_links (membership_id, email, from_membership) VALUES (%s, %s, %s)
                   ON CONFLICT (membership_id) DO NOTHING""", (new_mid, card_email, old_mid))
    if new_email and new_email != card_email:
        cur.execute("""INSERT INTO tv_email_moves (old_email, new_email) VALUES (%s, %s)
                       ON CONFLICT (old_email) DO UPDATE SET new_email = EXCLUDED.new_email, moved_at = NOW()""",
                    (new_email, card_email))
    if meta:
        try:
            W.whop("PATCH", "/api/v1/memberships/" + new_mid, {"metadata": meta})
        except Exception as e:
            log("TV_TRANSFER_META_ERR:", e)
    log("TV_TRANSFER", old_mid, "->", new_mid, (new_email or "")[:3] + "*** -> card", card_email[:3] + "***")
    return card_email
