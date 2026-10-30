"""TradeVault affiliate API (pages live on thetradevault.co). Route: /api/tv-aff?action=<action>

  register  POST   name, email, password, code?, payout_info?  -> {token, code}
  login     POST   email, password                               -> {token, code}
  me        GET    (Bearer affiliate token)  profile, stats, referrals, commissions
  click     POST   code                      count a visit from an affiliate link
  payout    POST   (Bearer affiliate token)  request payout of commissions past the 30-day hold
  profile   POST   (Bearer affiliate token)  {payout_info} save where to be paid
  admin     GET    (Bearer admin token)      every affiliate with stats
            PATCH  (Bearer admin token)      {id, commission_pct?, status?}
  paid      PATCH  (Bearer admin token)      {id, action: approve|reject} on a payout request

Commission logic and storage are in _tv_aff.py.
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
import _tv_aff as A
from _auth import verify_token

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
HOLD = f"INTERVAL '{A.HOLD_DAYS} days'"


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def do_GET(self):
        a = self._action()
        if a == "me":
            return self._me()
        if a == "admin":
            return self._admin_get()
        self._json(404, {"error": "unknown action"})

    def do_POST(self):
        a = self._action()
        if a == "register":
            return self._register()
        if a == "login":
            return self._login()
        if a == "click":
            return self._click()
        if a == "payout":
            return self._payout()
        if a == "profile":
            return self._profile()
        self._json(404, {"error": "unknown action"})

    def do_PATCH(self):
        a = self._action()
        if a == "admin":
            return self._admin_patch()
        if a == "paid":
            return self._admin_paid()
        self._json(404, {"error": "unknown action"})

    # ---------- affiliate ----------
    def _register(self):
        b = self._body()
        name = (b.get("name") or "").strip()[:80]
        email = (b.get("email") or "").strip().lower()[:160]
        phone = (b.get("phone") or "").strip()[:40]
        password = b.get("password") or ""
        code = (b.get("code") or "").strip().lower()
        payout = (b.get("payout_info") or "").strip()[:300]
        if not name or not EMAIL_RE.match(email):
            return self._json(400, {"error": "Please enter your name and a valid email."})
        if len(password) < 8:
            return self._json(400, {"error": "Your password needs at least 8 characters."})
        if code and not A.CODE_RE.match(code):
            return self._json(400, {"error": "Your link name can use 3 to 20 lowercase letters, numbers or underscores."})
        if not b.get("agree"):
            return self._json(400, {"error": "Please accept the affiliate terms."})
        ph, salt = A.hash_password(password)
        try:
            c = A.conn()
            cur = c.cursor()
            for attempt in range(3):
                try:
                    cur.execute("""
                        INSERT INTO tv_affiliates (name, email, phone, code, password_hash, password_salt, payout_info, commission_pct)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, code
                    """, (name, email, phone or None, code or A.new_code(), ph, salt, payout or None, A.DEFAULT_PCT))
                    row = cur.fetchone()
                    c.commit()
                    c.close()
                    return self._json(200, {"ok": True, "token": A.sign(row[0]), "code": row[1], "name": name})
                except Exception as e:
                    c.rollback()
                    msg = str(e)
                    if "tv_affiliates_email_key" in msg:
                        c.close()
                        return self._json(409, {"error": "That email already has an affiliate account. Log in instead."})
                    if "tv_affiliates_code_key" in msg and code:
                        c.close()
                        return self._json(409, {"error": "That link name is taken. Try another."})
                    if "tv_affiliates_code_key" not in msg:
                        raise
            c.close()
            self._json(500, {"error": "Could not create your account. Please try again."})
        except Exception as e:
            A.log("TV_AFF_REGISTER_ERR:", e)
            self._json(500, {"error": "Could not create your account. Please try again."})

    def _login(self):
        b = self._body()
        email = (b.get("email") or "").strip().lower()
        password = b.get("password") or ""
        try:
            c = A.conn()
            cur = c.cursor()
            cur.execute("SELECT id, name, code, password_hash, password_salt, status FROM tv_affiliates WHERE email = %s", (email,))
            row = cur.fetchone()
            c.close()
        except Exception as e:
            A.log("TV_AFF_LOGIN_ERR:", e)
            return self._json(500, {"error": "Login is unavailable right now."})
        if not row or not A.check_password(password, row[3], row[4]):
            return self._json(401, {"error": "Wrong email or password."})
        if row[5] != "active":
            return self._json(403, {"error": "This affiliate account is paused. Email hello@thetradevault.co."})
        self._json(200, {"ok": True, "token": A.sign(row[0]), "code": row[2], "name": row[1]})

    def _me(self):
        aff = self._aff()
        if not aff:
            return
        try:
            c = A.conn()
            cur = c.cursor()
            cur.execute("""SELECT id, name, email, code, commission_pct, status, payout_info, clicks, payout_status,
                                  payout_requested_amt, created_at FROM tv_affiliates WHERE id = %s""", (aff,))
            p = cur.fetchone()
            if not p:
                c.close()
                return self._json(401, {"error": "not logged in"})
            cur.execute(f"""
                SELECT COALESCE(SUM(commission_usd) FILTER (WHERE status = 'pending'), 0),
                       COALESCE(SUM(commission_usd) FILTER (WHERE status = 'pending' AND paid_at < NOW() - {HOLD}), 0),
                       COALESCE(SUM(commission_usd) FILTER (WHERE status = 'paid'), 0),
                       COALESCE(SUM(amount_usd) FILTER (WHERE status <> 'void'), 0)
                  FROM tv_aff_commissions WHERE affiliate_id = %s
            """, (aff,))
            s = cur.fetchone()
            cur.execute("""
                SELECT r.email, r.tier, r.created_at,
                       (SELECT COUNT(*) FROM tv_payments p WHERE p.email = r.email AND NOT p.refunded AND p.paid_at > NOW() - INTERVAL '35 days') > 0
                  FROM tv_aff_referrals r WHERE r.affiliate_id = %s ORDER BY r.created_at DESC LIMIT 200
            """, (aff,))
            refs = [{"member": A.mask(r[0]), "tier": r[1], "joined": r[2].isoformat(), "active": bool(r[3])} for r in cur.fetchall()]
            cur.execute(f"""
                SELECT email, product, amount_usd, commission_usd, status, paid_at, paid_at < NOW() - {HOLD}
                  FROM tv_aff_commissions WHERE affiliate_id = %s ORDER BY paid_at DESC LIMIT 200
            """, (aff,))
            coms = [{"member": A.mask(r[0]), "product": r[1], "amount": float(r[2]), "commission": float(r[3]),
                     "status": r[4] if r[4] != "pending" else ("payable" if r[6] else "pending"), "at": r[5].isoformat()}
                    for r in cur.fetchall()]
            c.close()
            self._json(200, {
                "ok": True, "name": p[1], "email": p[2], "code": p[3], "pct": p[4], "status": p[5],
                "payout_info": p[6] or "", "payout_status": p[8], "payout_requested": float(p[9] or 0),
                "hold_days": A.HOLD_DAYS,
                "stats": {"clicks": p[7], "referrals": len(refs), "active": sum(1 for r in refs if r["active"]),
                          "pending": float(s[0]), "payable": float(s[1]), "paid": float(s[2]), "sales": float(s[3])},
                "referrals": refs, "commissions": coms,
            })
        except Exception as e:
            A.log("TV_AFF_ME_ERR:", e)
            self._json(500, {"error": "Could not load your dashboard."})

    def _click(self):
        code = (self._body().get("code") or "").strip().lower()
        if A.CODE_RE.match(code):
            try:
                c = A.conn()
                cur = c.cursor()
                cur.execute("UPDATE tv_affiliates SET clicks = clicks + 1 WHERE code = %s AND status = 'active'", (code,))
                c.commit()
                c.close()
            except Exception as e:
                A.log("TV_AFF_CLICK_ERR:", e)
        self._json(200, {"ok": True})

    def _payout(self):
        aff = self._aff()
        if not aff:
            return
        info = (self._body().get("payout_info") or "").strip()[:300]
        try:
            c = A.conn()
            cur = c.cursor()
            cur.execute("SELECT payout_status, payout_info FROM tv_affiliates WHERE id = %s", (aff,))
            st, saved = cur.fetchone()
            if st == "requested":
                c.close()
                return self._json(409, {"error": "You already have a payout request in progress."})
            if not (info or saved):
                c.close()
                return self._json(400, {"error": "Add your payout details (PayPal email or bank details) first."})
            cur.execute(f"SELECT COALESCE(SUM(commission_usd), 0) FROM tv_aff_commissions WHERE affiliate_id = %s AND status = 'pending' AND paid_at < NOW() - {HOLD}", (aff,))
            amount = float(cur.fetchone()[0])
            if amount <= 0:
                c.close()
                return self._json(400, {"error": f"Nothing is ready to pay out yet. Commission becomes payable {A.HOLD_DAYS} days after each payment."})
            cur.execute("""UPDATE tv_affiliates SET payout_status = 'requested', payout_requested_at = NOW(), payout_requested_amt = %s,
                                  payout_info = COALESCE(NULLIF(%s, ''), payout_info) WHERE id = %s""", (amount, info, aff))
            c.commit()
            c.close()
            self._json(200, {"ok": True, "amount": amount})
        except Exception as e:
            A.log("TV_AFF_PAYOUT_ERR:", e)
            self._json(500, {"error": "Could not request your payout. Please try again."})

    def _profile(self):
        aff = self._aff()
        if not aff:
            return
        info = (self._body().get("payout_info") or "").strip()[:300]
        if not info:
            return self._json(400, {"error": "Enter your PayPal email or bank details."})
        c = A.conn()
        cur = c.cursor()
        cur.execute("UPDATE tv_affiliates SET payout_info = %s WHERE id = %s", (info, aff))
        c.commit()
        c.close()
        self._json(200, {"ok": True})

    # ---------- admin ----------
    def _admin_get(self):
        if not self._admin():
            return
        try:
            c = A.conn()
            cur = c.cursor()
            cur.execute(f"""
                SELECT a.id, a.name, a.email, a.phone, a.code, a.commission_pct, a.status, a.payout_info, a.clicks,
                       a.payout_status, a.payout_requested_amt, a.payout_requested_at, a.created_at,
                       (SELECT COUNT(*) FROM tv_aff_referrals r WHERE r.affiliate_id = a.id),
                       COALESCE((SELECT SUM(amount_usd) FROM tv_aff_commissions m WHERE m.affiliate_id = a.id AND m.status <> 'void'), 0),
                       COALESCE((SELECT SUM(commission_usd) FROM tv_aff_commissions m WHERE m.affiliate_id = a.id AND m.status = 'pending'), 0),
                       COALESCE((SELECT SUM(commission_usd) FROM tv_aff_commissions m WHERE m.affiliate_id = a.id AND m.status = 'pending' AND m.paid_at < NOW() - {HOLD}), 0),
                       COALESCE((SELECT SUM(commission_usd) FROM tv_aff_commissions m WHERE m.affiliate_id = a.id AND m.status = 'paid'), 0)
                  FROM tv_affiliates a ORDER BY a.created_at DESC
            """)
            rows = cur.fetchall()
            c.close()
            out = [{"id": r[0], "name": r[1], "email": r[2], "phone": r[3], "code": r[4], "pct": r[5], "status": r[6],
                    "payout_info": r[7] or "", "clicks": r[8], "payout_status": r[9], "payout_requested": float(r[10] or 0),
                    "payout_requested_at": r[11].isoformat() if r[11] else None, "created_at": r[12].isoformat(),
                    "referrals": r[13], "sales": float(r[14]), "pending": float(r[15]), "payable": float(r[16]), "paid": float(r[17])}
                   for r in rows]
            self._json(200, {"ok": True, "affiliates": out})
        except Exception as e:
            A.log("TV_AFF_ADMIN_ERR:", e)
            self._json(500, {"error": str(e)})

    def _admin_patch(self):
        if not self._admin():
            return
        b = self._body()
        sets, vals = [], []
        if "pct" in b:
            pct = int(b["pct"])
            if not 0 <= pct <= 100:
                return self._json(400, {"error": "Commission must be 0 to 100%."})
            sets.append("commission_pct = %s")
            vals.append(pct)
        if b.get("status") in ("active", "paused"):
            sets.append("status = %s")
            vals.append(b["status"])
        if not sets or not b.get("id"):
            return self._json(400, {"error": "Nothing to update."})
        c = A.conn()
        cur = c.cursor()
        cur.execute(f"UPDATE tv_affiliates SET {', '.join(sets)} WHERE id = %s", vals + [int(b["id"])])
        c.commit()
        c.close()
        self._json(200, {"ok": True})

    def _admin_paid(self):
        if not self._admin():
            return
        b = self._body()
        aff, act = int(b.get("id") or 0), b.get("action")
        if not aff or act not in ("approve", "reject"):
            return self._json(400, {"error": "id and action required"})
        c = A.conn()
        cur = c.cursor()
        if act == "approve":
            # Pays what was requested: commission past the hold at request time.
            cur.execute("SELECT payout_requested_at FROM tv_affiliates WHERE id = %s", (aff,))
            at = cur.fetchone()[0]
            cur.execute(f"""UPDATE tv_aff_commissions SET status = 'paid'
                             WHERE affiliate_id = %s AND status = 'pending' AND paid_at < COALESCE(%s, NOW()) - {HOLD}""", (aff, at))
        cur.execute("UPDATE tv_affiliates SET payout_status = 'none', payout_requested_amt = NULL, payout_requested_at = NULL WHERE id = %s", (aff,))
        c.commit()
        c.close()
        self._json(200, {"ok": True})

    # ---------- helpers ----------
    def _action(self):
        return (parse_qs(urlparse(self.path).query).get("action") or [""])[0].strip().lower()

    def _body(self):
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 8000)
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _bearer(self):
        h = self.headers.get("Authorization", "")
        return h[7:].strip() if h.startswith("Bearer ") else ""

    def _aff(self):
        aff = A.verify(self._bearer())
        if not aff:
            self._json(401, {"error": "not logged in"})
        return aff

    def _admin(self):
        if not verify_token(self._bearer()):
            self._json(401, {"error": "unauthorized"})
            return False
        return True

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())
