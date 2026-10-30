"""TradeVault affiliate programme: storage, auth tokens and commission logic.

How a sale is credited (there's no opt-in before checkout, so the buyer's email is
learned at Whop and joined to the ref afterwards):
  1. thetradevault.co/?ref=CODE stores the code in the visitor's browser (60 days).
  2. The Whop webhook logs every TradeVault payment (email, amount, Whop payment id).
  3. Whop sends the buyer back to thetradevault.co/setup in that same browser, and the
     page passes the stored code with the buyer's email -> claim(). The buyer becomes the
     affiliate's referral and earns commission on payments from the last 14 days.
  4. Every later payment from that member earns commission too (recurring), and a
     refund voids the commission on that payment.
Commission is held 30 days before it can be paid out. Every call here is best-effort.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from _aff_db import hash_password, check_password  # same PBKDF2 scheme as Jay's programme

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SECRET = os.environ.get("AFF_SESSION_SECRET", "changeme-aff-secret") + ":tv"
DEFAULT_PCT = 20
CLAIM_WINDOW_DAYS = 14
HOLD_DAYS = 30
TOKEN_TTL = 60 * 60 * 24 * 30
CODE_RE = re.compile(r"^[a-z0-9_]{3,20}$")


def log(*a):
    print(*a, file=sys.stderr)


_ready = False


def conn():
    global _ready
    import psycopg2
    c = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    if not _ready:
        cur = c.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tv_affiliates (
                id             BIGSERIAL PRIMARY KEY,
                name           TEXT NOT NULL,
                email          TEXT UNIQUE NOT NULL,
                phone          TEXT,
                code           TEXT UNIQUE NOT NULL,
                password_hash  TEXT NOT NULL,
                password_salt  TEXT NOT NULL,
                commission_pct INTEGER NOT NULL DEFAULT 20,
                status         TEXT NOT NULL DEFAULT 'active',
                payout_info    TEXT,
                clicks         INTEGER NOT NULL DEFAULT 0,
                payout_status  TEXT NOT NULL DEFAULT 'none',
                payout_requested_at  TIMESTAMPTZ,
                payout_requested_amt NUMERIC(10,2),
                created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS tv_payments (
                whop_id    TEXT PRIMARY KEY,
                email      TEXT NOT NULL,
                amount_usd NUMERIC(10,2) NOT NULL,
                product    TEXT,
                tier       TEXT,
                refunded   BOOLEAN NOT NULL DEFAULT FALSE,
                paid_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS tv_payments_email ON tv_payments (email);
            CREATE TABLE IF NOT EXISTS tv_aff_referrals (
                email        TEXT PRIMARY KEY,
                affiliate_id BIGINT NOT NULL REFERENCES tv_affiliates(id),
                tier         TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS tv_aff_claims (
                email      TEXT PRIMARY KEY,
                code       TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS tv_aff_commissions (
                id             BIGSERIAL PRIMARY KEY,
                affiliate_id   BIGINT NOT NULL REFERENCES tv_affiliates(id),
                whop_id        TEXT UNIQUE NOT NULL,
                email          TEXT NOT NULL,
                product        TEXT,
                amount_usd     NUMERIC(10,2) NOT NULL,
                commission_usd NUMERIC(10,2) NOT NULL,
                status         TEXT NOT NULL DEFAULT 'pending',
                paid_at        TIMESTAMPTZ NOT NULL,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        c.commit()
        _ready = True
    return c


# ---------- tokens (Bearer, stored by the portal page) ----------

def sign(aff_id: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"a": aff_id, "e": int(time.time()) + TOKEN_TTL}).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify(token: str):
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(sig, hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return int(data["a"]) if data.get("e", 0) > time.time() else None
    except Exception:
        return None


def new_code() -> str:
    return "tv" + secrets.token_hex(3)


# ---------- commission ----------

def _credit(cur, aff_id, pct, row):
    """row: (whop_id, email, amount_usd, product, paid_at). Idempotent per payment."""
    whop_id, email, amount, product, paid_at = row
    commission = round(float(amount) * pct / 100, 2)
    if commission <= 0:
        return
    cur.execute("""
        INSERT INTO tv_aff_commissions (affiliate_id, whop_id, email, product, amount_usd, commission_usd, paid_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (whop_id) DO NOTHING
    """, (aff_id, whop_id, email, product, amount, commission, paid_at))


def record_payment(whop_id, email, amount_usd, product, tier):
    """Log a TradeVault payment; credit its affiliate if the buyer is already a referral."""
    if not (DATABASE_URL and whop_id and email) or not amount_usd or amount_usd <= 0:
        return False
    try:
        c = conn()
        cur = c.cursor()
        cur.execute("""
            INSERT INTO tv_payments (whop_id, email, amount_usd, product, tier)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT (whop_id) DO NOTHING
        """, (whop_id, email, amount_usd, product, tier))
        c.commit()
        # Arrived at setup with a ref before this payment reached us: turn that into a referral now.
        cur.execute("DELETE FROM tv_aff_claims WHERE email = %s AND created_at > NOW() - INTERVAL '2 days' RETURNING code", (email,))
        pend = cur.fetchone()
        c.commit()
        if pend:
            claim(email, pend[0], tier)
        cur.execute("""
            SELECT a.id, a.commission_pct FROM tv_aff_referrals r JOIN tv_affiliates a ON a.id = r.affiliate_id
             WHERE r.email = %s AND a.status = 'active'
        """, (email,))
        ref = cur.fetchone()
        if ref:
            cur.execute("SELECT whop_id, email, amount_usd, product, paid_at FROM tv_payments WHERE whop_id = %s", (whop_id,))
            _credit(cur, ref[0], ref[1], cur.fetchone())
        c.commit()
        c.close()
        return True
    except Exception as e:
        log("TV_AFF_PAYMENT_ERR:", e)
        return False


def refund(whop_id):
    """A refunded payment earns nothing: void its commission (unless already paid out)."""
    if not (DATABASE_URL and whop_id):
        return
    try:
        c = conn()
        cur = c.cursor()
        cur.execute("UPDATE tv_payments SET refunded = TRUE WHERE whop_id = %s", (whop_id,))
        cur.execute("UPDATE tv_aff_commissions SET status = 'void' WHERE whop_id = %s AND status = 'pending'", (whop_id,))
        c.commit()
        c.close()
    except Exception as e:
        log("TV_AFF_REFUND_ERR:", e)


def claim(email, code, tier=None):
    """The buyer arrived at setup carrying an affiliate code: make them that affiliate's referral
    (first claim wins) and credit their recent payments."""
    email = (email or "").strip().lower()
    code = (code or "").strip().lower()
    if not (DATABASE_URL and email and CODE_RE.match(code)):
        return False
    try:
        c = conn()
        cur = c.cursor()
        cur.execute("SELECT id, commission_pct, email FROM tv_affiliates WHERE code = %s AND status = 'active'", (code,))
        aff = cur.fetchone()
        if not aff or aff[2] == email:  # unknown code, or someone referring themselves
            c.close()
            return False
        cur.execute("""
            INSERT INTO tv_aff_referrals (email, affiliate_id, tier) VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING RETURNING affiliate_id
        """, (email, aff[0], tier))
        if cur.fetchone():
            cur.execute(f"""
                SELECT whop_id, email, amount_usd, product, paid_at FROM tv_payments
                 WHERE email = %s AND NOT refunded AND paid_at > NOW() - INTERVAL '{CLAIM_WINDOW_DAYS} days'
            """, (email,))
            for row in cur.fetchall():
                _credit(cur, aff[0], aff[1], row)
            log("TV_AFF_CLAIM", code, "->", email[:3] + "***")
        c.commit()
        c.close()
        return True
    except Exception as e:
        log("TV_AFF_CLAIM_ERR:", e)
        return False


def pending_claim(email, code):
    """The buyer reached setup before Whop told us about their payment: hold the ref for 48 hours."""
    email = (email or "").strip().lower()
    code = (code or "").strip().lower()
    if not (DATABASE_URL and email and CODE_RE.match(code)):
        return
    try:
        c = conn()
        cur = c.cursor()
        cur.execute("""INSERT INTO tv_aff_claims (email, code) VALUES (%s, %s)
                       ON CONFLICT (email) DO UPDATE SET code = EXCLUDED.code, created_at = NOW()""", (email, code))
        c.commit()
        c.close()
    except Exception as e:
        log("TV_AFF_PENDING_ERR:", e)


def mask(email):
    """jo***@gmail.com — affiliates see that a sale happened, not who bought."""
    if not email or "@" not in email:
        return "member"
    user, dom = email.split("@", 1)
    return (user[:2] + "***@" + dom) if len(user) > 2 else ("***@" + dom)
