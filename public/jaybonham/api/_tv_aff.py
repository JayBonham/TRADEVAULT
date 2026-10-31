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

Programme rules (numbers live in tv_aff_settings, editable from /admin/affiliates):
  - Joining is an application: new affiliates are 'pending' until approved; their link
    does nothing until then.
  - A "personal" is a referred member with at least one non-refunded payment.
  - Commission builds from the first personal but can't be paid out until UNLOCK personals.
  - From TIER personals on, new payments earn TIER_PCT instead of BASE_PCT
    (a custom rate set by admin overrides both).
  - An affiliate's own purchases are never credited to another affiliate (no one sits under
    another affiliate); _credit and claim enforce it.
  - Bonuses (e.g. the quarterly profit share) are added by admin and skip the hold.
  - Payouts go by PayPal or crypto; each request reserves the commission it covers.
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
SETTINGS = {"base_pct": 20, "tier_pct": 30, "tier_count": 25, "unlock_count": 5}
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
            ALTER TABLE tv_affiliates ADD COLUMN IF NOT EXISTS application   TEXT;
            ALTER TABLE tv_affiliates ADD COLUMN IF NOT EXISTS payout_method TEXT;
            ALTER TABLE tv_affiliates ADD COLUMN IF NOT EXISTS custom_pct    INTEGER;
            ALTER TABLE tv_affiliates ADD COLUMN IF NOT EXISTS reviewed_at   TIMESTAMPTZ;
            ALTER TABLE tv_aff_commissions ADD COLUMN IF NOT EXISTS kind      TEXT NOT NULL DEFAULT 'commission';
            ALTER TABLE tv_aff_commissions ADD COLUMN IF NOT EXISTS pct       INTEGER;
            ALTER TABLE tv_aff_commissions ADD COLUMN IF NOT EXISTS payout_id BIGINT;
            ALTER TABLE tv_payments ADD COLUMN IF NOT EXISTS membership_id TEXT;
            CREATE TABLE IF NOT EXISTS tv_aff_payouts (
                id           BIGSERIAL PRIMARY KEY,
                affiliate_id BIGINT NOT NULL REFERENCES tv_affiliates(id),
                amount_usd   NUMERIC(10,2) NOT NULL,
                method       TEXT,
                details      TEXT,
                status       TEXT NOT NULL DEFAULT 'requested',
                reference    TEXT,
                requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                decided_at   TIMESTAMPTZ
            );
            CREATE TABLE IF NOT EXISTS tv_aff_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
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

# Commission that has cleared the hold (bonuses never wait).
def ready_sql(hold_days=None):
    return f"(kind = 'bonus' OR paid_at < NOW() - INTERVAL '{int(hold_days or HOLD_DAYS)} days')"


def settings(cur):
    out = dict(SETTINGS)
    cur.execute("SELECT key, value FROM tv_aff_settings")
    for k, v in cur.fetchall():
        if k in out:
            try:
                out[k] = int(v)
            except ValueError:
                pass
    return out


def personals(cur, aff_id):
    cur.execute("""SELECT COUNT(*) FROM tv_aff_referrals r WHERE r.affiliate_id = %s
                     AND EXISTS (SELECT 1 FROM tv_payments p WHERE p.email = r.email AND NOT p.refunded)""", (aff_id,))
    return int(cur.fetchone()[0])


def rate(cur, aff_id, cfg=None, count=None):
    """The % a new payment earns this affiliate right now."""
    cfg = cfg or settings(cur)
    cur.execute("SELECT custom_pct FROM tv_affiliates WHERE id = %s", (aff_id,))
    row = cur.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    count = personals(cur, aff_id) if count is None else count
    return cfg["tier_pct"] if count >= cfg["tier_count"] else cfg["base_pct"]


def is_affiliate(cur, email):
    """True if this email belongs to an affiliate (anyone not rejected)."""
    cur.execute("SELECT 1 FROM tv_affiliates WHERE lower(email) = %s AND status <> 'rejected'", ((email or "").lower(),))
    return cur.fetchone() is not None


def unlink(cur, email):
    """Take a buyer off their affiliate: the referral goes, and so does commission not yet paid or
    requested. Returns the number of commission rows removed."""
    cur.execute("DELETE FROM tv_aff_referrals WHERE email = %s", (email,))
    cur.execute("""DELETE FROM tv_aff_commissions WHERE email = %s AND kind = 'commission'
                   AND status = 'pending' AND payout_id IS NULL""", (email,))
    return cur.rowcount


def _credit(cur, aff_id, row):
    """row: (whop_id, email, amount_usd, product, paid_at). Idempotent per payment."""
    whop_id, email, amount, product, paid_at = row
    if is_affiliate(cur, email):
        return False
    pct = rate(cur, aff_id)
    commission = round(float(amount) * pct / 100, 2)
    if commission <= 0:
        return
    cur.execute("""
        INSERT INTO tv_aff_commissions (affiliate_id, whop_id, email, product, amount_usd, commission_usd, paid_at, pct)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (whop_id) DO NOTHING
    """, (aff_id, whop_id, email, product, amount, commission, paid_at, pct))
    return cur.rowcount == 1


def _tell_sale(cur, aff_id):
    """GHL email trigger: the affiliate just earned commission."""
    cur.execute("SELECT email, name FROM tv_affiliates WHERE id = %s", (aff_id,))
    row = cur.fetchone()
    if row:
        ghl_tag(row[0], row[1], ["tv-affiliate-sale"], again=True)


def record_payment(whop_id, email, amount_usd, product, tier, paid_at=None, membership_id=None):
    """Log a TradeVault payment; credit its affiliate if the buyer is already a referral."""
    if not (DATABASE_URL and whop_id and email) or not amount_usd or amount_usd <= 0:
        return False
    try:
        c = conn()
        cur = c.cursor()
        cur.execute("""
            INSERT INTO tv_payments (whop_id, email, amount_usd, product, tier, paid_at, membership_id)
            VALUES (%s, %s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()), %s)
            ON CONFLICT (whop_id) DO UPDATE SET membership_id = COALESCE(tv_payments.membership_id, EXCLUDED.membership_id)
        """, (whop_id, email, amount_usd, product, tier, paid_at, membership_id))
        c.commit()
        # Arrived at setup with a ref before this payment reached us: turn that into a referral now.
        cur.execute("DELETE FROM tv_aff_claims WHERE email = %s AND created_at > NOW() - INTERVAL '2 days' RETURNING code", (email,))
        pend = cur.fetchone()
        c.commit()
        if pend:
            claim(email, pend[0], tier)
        cur.execute("""
            SELECT a.id FROM tv_aff_referrals r JOIN tv_affiliates a ON a.id = r.affiliate_id
             WHERE r.email = %s AND a.status = 'active'
        """, (email,))
        ref = cur.fetchone()
        if ref:
            cur.execute("SELECT whop_id, email, amount_usd, product, paid_at FROM tv_payments WHERE whop_id = %s", (whop_id,))
            sold = _credit(cur, ref[0], cur.fetchone())
        c.commit()
        if ref and sold:
            _tell_sale(cur, ref[0])
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
        cur.execute("UPDATE tv_aff_commissions SET status = 'void', payout_id = NULL WHERE whop_id = %s AND status = 'pending'", (whop_id,))
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
        cur.execute("SELECT id, email FROM tv_affiliates WHERE code = %s AND status = 'active'", (code,))
        aff = cur.fetchone()
        if not aff or aff[1] == email or is_affiliate(cur, email):  # unknown code, self, or another affiliate
            c.close()
            return False
        cur.execute("""
            INSERT INTO tv_aff_referrals (email, affiliate_id, tier) VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING RETURNING affiliate_id
        """, (email, aff[0], tier))
        sold = False
        if cur.fetchone():
            cur.execute(f"""
                SELECT whop_id, email, amount_usd, product, paid_at FROM tv_payments
                 WHERE email = %s AND NOT refunded AND paid_at > NOW() - INTERVAL '{CLAIM_WINDOW_DAYS} days'
            """, (email,))
            for row in cur.fetchall():
                sold = _credit(cur, aff[0], row) or sold
            log("TV_AFF_CLAIM", code, "->", email[:3] + "***")
        c.commit()
        if sold:
            _tell_sale(cur, aff[0])
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


# ---------- payout details (PayPal or crypto only) ----------

COINS = ("USDT", "USDC")
NETWORKS = {"TRC20": "Tron (TRC20)", "ERC20": "Ethereum (ERC20)", "BEP20": "BNB Smart Chain (BEP20)",
            "SOL": "Solana", "BINANCE": "Binance Pay ID"}
ADDR_RE = re.compile(r"^[A-Za-z0-9]{20,100}$")
PAYID_RE = re.compile(r"^[0-9]{6,12}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


def clean_payout(method, d):
    """Returns (method, details_json) or raises ValueError with a message for the user."""
    d = d if isinstance(d, dict) else {}
    if method == "paypal":
        email = str(d.get("email") or "").strip().lower()[:160]
        if not EMAIL_RE.match(email):
            raise ValueError("Enter the email address on your PayPal account.")
        return "paypal", json.dumps({"email": email})
    if method == "crypto":
        coin = str(d.get("coin") or "USDT").upper()
        net = str(d.get("network") or "").upper()
        addr = str(d.get("address") or "").strip()[:100]
        if coin not in COINS or net not in NETWORKS:
            raise ValueError("Pick a coin and network.")
        if net == "BINANCE" and not PAYID_RE.match(addr):
            raise ValueError("Your Binance Pay ID is the 6 to 12 digit number in Binance under Pay.")
        if net != "BINANCE" and not ADDR_RE.match(addr):
            raise ValueError("That wallet address doesn't look right. Copy it straight from your wallet.")
        return "crypto", json.dumps({"coin": coin, "network": net, "address": addr})
    raise ValueError("Choose PayPal or crypto.")


def payout_label(method, details):
    """One line for admin: where to send the money."""
    try:
        d = json.loads(details or "{}")
    except ValueError:
        return details or ""
    if method == "paypal":
        return "PayPal · " + d.get("email", "")
    if method == "crypto":
        return f"{d.get('coin', '')} · {NETWORKS.get(d.get('network'), d.get('network', ''))} · {d.get('address', '')}"
    return details or ""


# ---------- GoHighLevel tags (for the application / approval emails) ----------

GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"


def ghl_tag(email, name, tags, again=False):
    """Best-effort: upsert the contact and add tags so GHL automations can send emails.
    again=True removes the tags first, so a "tag added" trigger fires every time (each sale, each payout)."""
    if not (GHL_API_KEY and email):
        return
    import http.client
    headers = {"Authorization": "Bearer " + GHL_API_KEY, "Version": "2021-07-28",
               "Content-Type": "application/json", "Accept": "application/json"}
    try:
        first, _, last = (name or "").strip().partition(" ")
        c = http.client.HTTPSConnection("services.leadconnectorhq.com", timeout=6)
        c.request("POST", "/contacts/upsert", json.dumps({"locationId": GHL_LOCATION, "email": email,
                                                          "firstName": first, "lastName": last}), headers)
        r = c.getresponse()
        data = json.loads(r.read() or b"{}")
        cid = (data.get("contact") or {}).get("id")
        if cid:
            if again:
                c.request("DELETE", f"/contacts/{cid}/tags", json.dumps({"tags": tags}), headers)
                c.getresponse().read()
            c.request("POST", f"/contacts/{cid}/tags", json.dumps({"tags": tags}), headers)
            c.getresponse().read()
        else:
            log("TV_AFF_GHL:", r.status, str(data)[:200])
        c.close()
    except Exception as e:
        log("TV_AFF_GHL_ERR:", e)
