"""Shared affiliate DB helper — imported by all aff-*.py handlers."""
import base64
import hashlib
import hmac
import os
import secrets
from http.cookies import SimpleCookie

DATABASE_URL = os.environ.get("DATABASE_URL", "")
AFF_SECRET   = os.environ.get("AFF_SESSION_SECRET", "changeme-aff-secret")

PLAN_AMOUNTS = {
    "sniper-basic-ed":    999.0,
    "sniper-accelerator": 5999.0,
    "sniper-elite-72":    9999.0,
}


def get_conn():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def ensure_tables():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jb_affiliates (
            id                   BIGSERIAL PRIMARY KEY,
            name                 TEXT NOT NULL,
            email                TEXT UNIQUE NOT NULL,
            phone                TEXT,
            code                 TEXT UNIQUE NOT NULL,
            password_hash        TEXT NOT NULL,
            password_salt        TEXT NOT NULL,
            commission_pct       INTEGER NOT NULL DEFAULT 15,
            status               TEXT NOT NULL DEFAULT 'active',
            payout_info          TEXT,
            total_clicks         INTEGER NOT NULL DEFAULT 0,
            payout_status        TEXT NOT NULL DEFAULT 'none',
            payout_requested_at  TIMESTAMPTZ,
            payout_requested_amt NUMERIC(10,2),
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jb_aff_events (
            id                BIGSERIAL PRIMARY KEY,
            affiliate_id      BIGINT REFERENCES jb_affiliates(id),
            event_type        TEXT NOT NULL,
            visitor_email     TEXT,
            visitor_name      TEXT,
            plan              TEXT,
            amount_usd        NUMERIC(10,2),
            commission_usd    NUMERIC(10,2),
            commission_status TEXT DEFAULT 'pending',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


# ---------------------------------------------------------------------------
# Password hashing  (PBKDF2-SHA256, 120 000 iterations — same as Voxflow)
# ---------------------------------------------------------------------------

def hash_password(password, salt=None):
    if salt is None:
        salt = base64.b64encode(os.urandom(16)).decode()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return base64.b64encode(dk).decode(), salt


def check_password(password, stored_hash, salt):
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return hmac.compare_digest(base64.b64encode(dk).decode(), stored_hash)


# ---------------------------------------------------------------------------
# Session cookie  (HMAC-SHA256 signed, no expiry in token — cookie Max-Age handles TTL)
# ---------------------------------------------------------------------------

def sign_session(aff_id: int) -> str:
    payload = base64.urlsafe_b64encode(str(aff_id).encode()).decode().rstrip("=")
    sig = hmac.new(AFF_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session(token: str):
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(AFF_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        pad = (4 - len(payload) % 4) % 4
        return int(base64.urlsafe_b64decode(payload + "=" * pad).decode())
    except Exception:
        return None


def get_aff_id_from_request(headers):
    raw    = headers.get("Cookie", "")
    cookie = SimpleCookie()
    cookie.load(raw)
    morsel = cookie.get("jb_aff_session")
    if not morsel:
        return None
    return verify_session(morsel.value)


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

def generate_code():
    return "jb_" + secrets.token_hex(4)


# ---------------------------------------------------------------------------
# Run table creation at import time (idempotent)
# ---------------------------------------------------------------------------

try:
    ensure_tables()
except Exception:
    pass  # Will surface on first real DB call if DATABASE_URL is missing
