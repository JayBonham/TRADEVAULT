"""Shared JWT verify helper — imported by other admin API handlers."""
import base64
import hashlib
import hmac
import json
import os
import time

JWT_SECRET = os.environ.get("ADMIN_JWT_SECRET", "changeme-set-in-vercel")


def verify_token(token):
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        pad = (4 - len(payload) % 4) % 4
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * pad))
        if data["exp"] < time.time():
            return None
        return data["u"]
    except Exception:
        return None
