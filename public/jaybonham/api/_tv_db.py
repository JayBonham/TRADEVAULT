"""TradeVault member records in Postgres — the board's source for setup answers and purchase dates.
GHL stays the system of record for tags/automations; this is a copy that doesn't depend on
GHL custom-field permissions. Every call is best-effort and never raises.
"""
import os
import sys

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tv_members (
    contact_id   TEXT PRIMARY KEY,
    email        TEXT,
    tier         TEXT,
    product      TEXT,
    purchased_at TIMESTAMPTZ,
    setup_at     TIMESTAMPTZ,
    educator     TEXT,
    scanner      TEXT,
    tradingview  TEXT,
    telegram     TEXT
);
ALTER TABLE tv_members ADD COLUMN IF NOT EXISTS ended_at   TIMESTAMPTZ;
ALTER TABLE tv_members ADD COLUMN IF NOT EXISTS removed_at TIMESTAMPTZ;
"""


_ready = False


def _conn():
    # Schema once per process: ALTER TABLE locks the table even when there's nothing to add.
    global _ready
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    cur = conn.cursor()
    if not _ready:
        cur.execute(_SCHEMA)
        conn.commit()
        _ready = True
    return conn, cur


def record_purchase(contact_id, email, tier, product, paid_at=None):
    if not (DATABASE_URL and contact_id):
        return False
    try:
        conn, cur = _conn()
        cur.execute("""
            INSERT INTO tv_members (contact_id, email, tier, product, purchased_at)
            VALUES (%s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()))
            ON CONFLICT (contact_id) DO UPDATE SET
              email = EXCLUDED.email, tier = EXCLUDED.tier, product = EXCLUDED.product,
              purchased_at = LEAST(tv_members.purchased_at, EXCLUDED.purchased_at),
              ended_at = NULL, removed_at = NULL
        """, (contact_id, email, tier, product, paid_at))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("TV_DB_PURCHASE_ERR:", e, file=sys.stderr)
        return False


def record_setup(contact_id, email, tier, educator, scanner, tradingview, telegram):
    if not (DATABASE_URL and contact_id):
        return False
    try:
        conn, cur = _conn()
        cur.execute("""
            INSERT INTO tv_members (contact_id, email, tier, setup_at, educator, scanner, tradingview, telegram)
            VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s)
            ON CONFLICT (contact_id) DO UPDATE SET
              email = COALESCE(EXCLUDED.email, tv_members.email), tier = EXCLUDED.tier,
              setup_at = EXCLUDED.setup_at, educator = EXCLUDED.educator, scanner = EXCLUDED.scanner,
              tradingview = EXCLUDED.tradingview, telegram = EXCLUDED.telegram
        """, (contact_id, email, tier, educator, scanner, tradingview, telegram))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("TV_DB_SETUP_ERR:", e, file=sys.stderr)
        return False


def remove(contact_id):
    """Drop a member's board record (test purchases); a real payment later records them again."""
    if not (DATABASE_URL and contact_id):
        return False
    try:
        conn, cur = _conn()
        cur.execute("DELETE FROM tv_members WHERE contact_id = %s", (contact_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("TV_DB_REMOVE_ERR:", e, file=sys.stderr)
        return False


def set_ended(contact_id, ended):
    """Whop membership ended (True) or is valid again (False). removed_at resets when it ends."""
    if not (DATABASE_URL and contact_id):
        return False
    try:
        conn, cur = _conn()
        if ended:
            cur.execute("UPDATE tv_members SET ended_at = NOW(), removed_at = NULL WHERE contact_id = %s AND ended_at IS NULL", (contact_id,))
        else:
            cur.execute("UPDATE tv_members SET ended_at = NULL, removed_at = NULL WHERE contact_id = %s", (contact_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("TV_DB_ENDED_ERR:", e, file=sys.stderr)
        return False


def set_removed(contact_id):
    """Admin took the ended member out of the scanners."""
    if not (DATABASE_URL and contact_id):
        return False
    try:
        conn, cur = _conn()
        cur.execute("UPDATE tv_members SET removed_at = NOW() WHERE contact_id = %s", (contact_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("TV_DB_REMOVED_ERR:", e, file=sys.stderr)
        return False


def all_members():
    """{contact_id: {...}} for every row; {} if the DB is unavailable."""
    if not DATABASE_URL:
        return {}
    try:
        conn, cur = _conn()
        cur.execute("""SELECT contact_id, purchased_at, setup_at, educator, scanner, tradingview, telegram,
                              ended_at, removed_at, email, tier
                       FROM tv_members""")
        out = {}
        for cid, bought, setup, edu, scan, tv, tg, ended, removed, email, tier in cur.fetchall():
            out[cid] = {"purchased_at": bought.isoformat() if bought else "",
                        "setup_at": setup.isoformat() if setup else "",
                        "educator": edu or "", "scanner": scan or "",
                        "tradingview": tv or "", "telegram": tg or "",
                        "ended_at": ended.isoformat() if ended else "",
                        "removed_at": removed.isoformat() if removed else "",
                        "email": email or "", "tier": tier or ""}
        conn.commit()
        conn.close()
        return out
    except Exception as e:
        print("TV_DB_READ_ERR:", e, file=sys.stderr)
        return {}
