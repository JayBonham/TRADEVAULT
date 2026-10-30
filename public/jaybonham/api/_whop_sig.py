"""Whop webhook signature check.

Whop's v1 webhooks follow the Standard Webhooks spec (webhook-id / webhook-timestamp /
webhook-signature headers, "v1,<base64 HMAC-SHA256 of id.timestamp.body>"). Older
webhooks sent x-whop-signature "t=..,v1=<hex HMAC of t.body>". Both are accepted, and
the key is tried as the raw secret and as the base64 secret Standard Webhooks expects.
"""
import base64
import hashlib
import hmac
import time

MAX_SKEW = 60 * 10


def _keys(secret):
    keys = [secret.encode()]
    bare = secret.split("_", 1)[1] if secret.startswith("whsec_") else secret
    try:
        keys.append(base64.b64decode(bare + "=" * (-len(bare) % 4), validate=True))
    except Exception:
        pass
    return keys


def check(headers, body, secret):
    """Returns the scheme that matched ("standard", "legacy", "plain") or None."""
    if not secret:
        return None
    h = {k.lower(): v for k, v in headers.items()}

    wid, ts, sig = h.get("webhook-id"), h.get("webhook-timestamp"), h.get("webhook-signature")
    if wid and ts and sig:
        try:
            if abs(time.time() - int(ts)) > MAX_SKEW:
                return None
        except ValueError:
            return None
        msg = f"{wid}.{ts}.".encode() + body
        given = [p.split(",", 1)[1] for p in sig.split() if p.startswith("v1,")]
        for key in _keys(secret):
            want = base64.b64encode(hmac.new(key, msg, hashlib.sha256).digest()).decode()
            if any(hmac.compare_digest(want, g) for g in given):
                return "standard"

    sig = h.get("x-whop-signature") or h.get("whop-signature")
    if sig:
        parts = dict(p.split("=", 1) for p in sig.split(",") if "=" in p)
        for key in _keys(secret):
            if parts.get("t") and parts.get("v1"):
                want = hmac.new(key, parts["t"].encode() + b"." + body, hashlib.sha256).hexdigest()
                if hmac.compare_digest(want, parts["v1"]):
                    return "legacy"
            want = hmac.new(key, body, hashlib.sha256).hexdigest()
            if hmac.compare_digest(want, sig.split("=")[-1]):
                return "plain"
    return None
