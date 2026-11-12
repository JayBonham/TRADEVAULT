"""Sniper Academy sign-in links, shared by jb-academy.py (the members area) and whop-hook.py
(a buyer's link is written onto their GHL contact at purchase, for the onboarding email)."""
import base64
import hashlib
import hmac
import json
import os
import time

SECRET = os.environ.get("AFF_SESSION_SECRET", "changeme-aff-secret") + ":jb:academy"
SITE = "https://jaybonham.com"
PRODUCT_TITLES = {"sniper fast start", "sniper accelerator", "sniper elite"}  # deposits don't count
LINK_TTL = 24 * 3600            # a link asked for on the sign-in page
WELCOME_TTL = 30 * 24 * 3600    # the link in the onboarding email, which can go out days after purchase
SESSION_TTL = 30 * 24 * 3600


def sign(email, kind, ttl):
    payload = base64.urlsafe_b64encode(json.dumps({"m": email, "k": kind, "e": int(time.time()) + ttl}).encode()).decode().rstrip("=")
    return payload + "." + hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify(token, kind):
    try:
        payload, sig = (token or "").rsplit(".", 1)
        if not hmac.compare_digest(sig, hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()):
            return None
        d = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return d["m"] if d.get("k") == kind and d.get("e", 0) > time.time() else None
    except Exception:
        return None


def link(email, ttl=LINK_TTL):
    return SITE + "/academy?l=" + sign(email, "l", ttl)


def is_course_product(title):
    return " ".join(str(title or "").lower().split()) in PRODUCT_TITLES
