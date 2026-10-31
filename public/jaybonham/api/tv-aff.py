"""TradeVault affiliate API (pages live on thetradevault.co). Route: /api/tv-aff?action=<action>

  register   POST   application: name, email, password, code?, socials, audience, promote,
                    payout_method, payout {..}           -> {token} (status 'pending')
  login      POST   email, password                       -> {token}
  me         GET    (Bearer affiliate token)  status, progress, stats, referrals, commissions, payouts
  click      POST   code                      count a visit from an affiliate link
  payout     POST   (Bearer affiliate token)  request payout of everything ready
  profile    POST   (Bearer affiliate token)  {payout_method, payout} save where to be paid
  admin      GET    (Bearer admin token)      affiliates, payouts, settings
             PATCH  (Bearer admin token)      {id, status?, custom_pct?}   status: active|paused|rejected
  detail     GET    (Bearer admin token)      ?id= one affiliate's members and commission
  payouts    PATCH  (Bearer admin token)      {id, action: paid|reject, reference?}
  bonus      POST   (Bearer admin token)      {id, amount, note}  e.g. quarterly profit share
  assign     POST   (Bearer admin token)      {id, email}  credit a buyer the link didn't catch
  settings   PATCH  (Bearer admin token)      {base_pct, tier_pct, tier_count, unlock_count}

GHL tags (for automations): tv-affiliate-applied, tv-affiliate-approved, tv-affiliate-rejected,
tv-affiliate-paid and tv-affiliate-sale (the last two re-added each time). Commission logic and storage are in _tv_aff.py.
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
READY = A.ready_sql()


def _iso(v):
    return v.isoformat() if v else None


def _details(raw):
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {"text": raw}


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
        if a == "detail":
            return self._admin_detail()
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
        if a == "bonus":
            return self._admin_bonus()
        if a == "assign":
            return self._admin_assign()
        self._json(404, {"error": "unknown action"})

    def do_PATCH(self):
        a = self._action()
        if a == "admin":
            return self._admin_patch()
        if a == "payouts":
            return self._admin_payout()
        if a == "settings":
            return self._admin_settings()
        self._json(404, {"error": "unknown action"})

    # ---------- affiliate ----------
    def _register(self):
        b = self._body()
        name = (b.get("name") or "").strip()[:80]
        email = (b.get("email") or "").strip().lower()[:160]
        phone = (b.get("phone") or "").strip()[:40]
        password = b.get("password") or ""
        code = (b.get("code") or "").strip().lower()
        app = {k: (str(b.get(k) or "").strip()[:600]) for k in ("socials", "audience", "promote")}
        if not name or not EMAIL_RE.match(email):
            return self._json(400, {"error": "Please enter your name and a valid email."})
        if len(password) < 8:
            return self._json(400, {"error": "Your password needs at least 8 characters."})
        if code and not A.CODE_RE.match(code):
            return self._json(400, {"error": "Your link name can use 3 to 20 lowercase letters, numbers or underscores."})
        if not app["socials"] or not app["promote"]:
            return self._json(400, {"error": "Tell us where you'll share your link and how you'll promote it."})
        try:
            method, details = A.clean_payout(b.get("payout_method"), b.get("payout"))
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        if not b.get("agree"):
            return self._json(400, {"error": "Please accept the affiliate terms."})
        ph, salt = A.hash_password(password)
        try:
            c = A.conn()
            cur = c.cursor()
            cfg = A.settings(cur)
            for attempt in range(3):
                try:
                    cur.execute("""
                        INSERT INTO tv_affiliates (name, email, phone, code, password_hash, password_salt, payout_method, payout_info,
                                                   commission_pct, status, application)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s) RETURNING id, code
                    """, (name, email, phone or None, code or A.new_code(), ph, salt, method, details, cfg["base_pct"], json.dumps(app)))
                    row = cur.fetchone()
                    c.commit()
                    c.close()
                    A.ghl_tag(email, name, ["tv-affiliate-applied"])
                    return self._json(200, {"ok": True, "token": A.sign(row[0]), "code": row[1], "name": name})
                except Exception as e:
                    c.rollback()
                    msg = str(e)
                    if "tv_affiliates_email_key" in msg:
                        c.close()
                        return self._json(409, {"error": "That email has already applied. Log in instead."})
                    if "tv_affiliates_code_key" in msg and code:
                        c.close()
                        return self._json(409, {"error": "That link name is taken. Try another."})
                    if "tv_affiliates_code_key" not in msg:
                        raise
            c.close()
            self._json(500, {"error": "Could not send your application. Please try again."})
        except Exception as e:
            A.log("TV_AFF_REGISTER_ERR:", e)
            self._json(500, {"error": "Could not send your application. Please try again."})

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
        if row[5] == "paused":
            return self._json(403, {"error": "This affiliate account is paused. Email hello@thetradevault.co."})
        if row[5] == "rejected":
            return self._json(403, {"error": "Your application wasn't approved this time. Questions: hello@thetradevault.co."})
        self._json(200, {"ok": True, "token": A.sign(row[0]), "code": row[2], "name": row[1]})

    def _me(self):
        aff = self._aff()
        if not aff:
            return
        try:
            c = A.conn()
            cur = c.cursor()
            cur.execute("""SELECT id, name, email, code, status, payout_method, payout_info, clicks, created_at
                             FROM tv_affiliates WHERE id = %s""", (aff,))
            p = cur.fetchone()
            if not p or p[4] in ("paused", "rejected"):
                c.close()
                return self._json(401, {"error": "not logged in"})
            cfg = A.settings(cur)
            count = A.personals(cur, aff)
            pct = A.rate(cur, aff, cfg, count)
            qualified = count >= cfg["unlock_count"]
            cur.execute(f"""
                SELECT COALESCE(SUM(commission_usd) FILTER (WHERE status = 'pending'), 0),
                       COALESCE(SUM(commission_usd) FILTER (WHERE status = 'pending' AND payout_id IS NULL AND {READY}), 0),
                       COALESCE(SUM(commission_usd) FILTER (WHERE status = 'paid'), 0),
                       COALESCE(SUM(amount_usd) FILTER (WHERE status <> 'void'), 0),
                       COALESCE(SUM(commission_usd) FILTER (WHERE status = 'pending' AND payout_id IS NOT NULL), 0)
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
                SELECT email, product, amount_usd, commission_usd, status, paid_at, {READY}, kind, pct, payout_id
                  FROM tv_aff_commissions WHERE affiliate_id = %s ORDER BY paid_at DESC LIMIT 200
            """, (aff,))
            coms = []
            for r in cur.fetchall():
                st = r[4]
                if st == "pending":
                    st = "requested" if r[9] else ("held" if not r[6] else ("payable" if qualified else "locked"))
                coms.append({"member": A.mask(r[0]) if r[7] != "bonus" else "Bonus", "product": r[1], "amount": float(r[2]),
                             "commission": float(r[3]), "status": st, "at": r[5].isoformat(), "kind": r[7], "pct": r[8]})
            cur.execute("""SELECT id, amount_usd, method, details, status, reference, requested_at, decided_at
                             FROM tv_aff_payouts WHERE affiliate_id = %s ORDER BY requested_at DESC LIMIT 50""", (aff,))
            pays = [{"id": r[0], "amount": float(r[1]), "method": r[2], "to": A.payout_label(r[2], r[3]), "status": r[4],
                     "reference": r[5] or "", "requested_at": _iso(r[6]), "decided_at": _iso(r[7])} for r in cur.fetchall()]
            c.close()
            self._json(200, {
                "ok": True, "name": p[1], "email": p[2], "code": p[3], "status": p[4], "pct": pct,
                "payout_method": p[5] or "", "payout": _details(p[6]), "hold_days": A.HOLD_DAYS,
                "program": {"personals": count, "unlock_count": cfg["unlock_count"], "qualified": qualified,
                            "base_pct": cfg["base_pct"], "tier_pct": cfg["tier_pct"], "tier_count": cfg["tier_count"]},
                "stats": {"clicks": p[7], "referrals": len(refs), "active": sum(1 for r in refs if r["active"]),
                          "pending": float(s[0]), "ready": float(s[1]), "paid": float(s[2]), "sales": float(s[3]),
                          "requested": float(s[4])},
                "referrals": refs, "commissions": coms, "payouts": pays,
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
        try:
            c = A.conn()
            cur = c.cursor()
            cur.execute("SELECT status, payout_method, payout_info FROM tv_affiliates WHERE id = %s", (aff,))
            st, method, details = cur.fetchone()
            if st != "active":
                c.close()
                return self._json(403, {"error": "Payouts open once your application is approved."})
            cfg = A.settings(cur)
            if A.personals(cur, aff) < cfg["unlock_count"]:
                c.close()
                return self._json(400, {"error": f"Payouts unlock once you've referred {cfg['unlock_count']} paying members."})
            if method not in ("paypal", "crypto"):
                c.close()
                return self._json(400, {"error": "Add your PayPal or crypto details first."})
            cur.execute("SELECT 1 FROM tv_aff_payouts WHERE affiliate_id = %s AND status = 'requested'", (aff,))
            if cur.fetchone():
                c.close()
                return self._json(409, {"error": "You already have a payout on its way."})
            cur.execute(f"""SELECT COALESCE(SUM(commission_usd), 0) FROM tv_aff_commissions
                             WHERE affiliate_id = %s AND status = 'pending' AND payout_id IS NULL AND {READY}""", (aff,))
            amount = float(cur.fetchone()[0])
            if amount <= 0:
                c.close()
                return self._json(400, {"error": f"Nothing is ready yet. Commission clears {A.HOLD_DAYS} days after each payment."})
            cur.execute("""INSERT INTO tv_aff_payouts (affiliate_id, amount_usd, method, details) VALUES (%s, %s, %s, %s) RETURNING id""",
                        (aff, amount, method, details))
            pid = cur.fetchone()[0]
            cur.execute(f"""UPDATE tv_aff_commissions SET payout_id = %s
                             WHERE affiliate_id = %s AND status = 'pending' AND payout_id IS NULL AND {READY}""", (pid, aff))
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
        b = self._body()
        try:
            method, details = A.clean_payout(b.get("payout_method"), b.get("payout"))
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        c = A.conn()
        cur = c.cursor()
        cur.execute("UPDATE tv_affiliates SET payout_method = %s, payout_info = %s WHERE id = %s", (method, details, aff))
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
            cfg = A.settings(cur)
            cur.execute(f"""
                SELECT a.id, a.name, a.email, a.phone, a.code, a.custom_pct, a.status, a.payout_method, a.payout_info, a.clicks,
                       a.created_at, a.application, a.reviewed_at,
                       (SELECT COUNT(*) FROM tv_aff_referrals r WHERE r.affiliate_id = a.id),
                       (SELECT COUNT(*) FROM tv_aff_referrals r WHERE r.affiliate_id = a.id
                           AND EXISTS (SELECT 1 FROM tv_payments p WHERE p.email = r.email AND NOT p.refunded)),
                       COALESCE((SELECT SUM(amount_usd) FROM tv_aff_commissions m WHERE m.affiliate_id = a.id AND m.status <> 'void' AND m.kind = 'commission'), 0),
                       COALESCE((SELECT SUM(commission_usd) FROM tv_aff_commissions m WHERE m.affiliate_id = a.id AND m.status = 'pending'), 0),
                       COALESCE((SELECT SUM(commission_usd) FROM tv_aff_commissions m WHERE m.affiliate_id = a.id AND m.status = 'pending' AND m.payout_id IS NULL AND {READY}), 0),
                       COALESCE((SELECT SUM(commission_usd) FROM tv_aff_commissions m WHERE m.affiliate_id = a.id AND m.status = 'paid'), 0)
                  FROM tv_affiliates a ORDER BY a.created_at DESC
            """)
            affs = []
            for r in cur.fetchall():
                count = r[14]
                pct = r[5] if r[5] is not None else (cfg["tier_pct"] if count >= cfg["tier_count"] else cfg["base_pct"])
                affs.append({"id": r[0], "name": r[1], "email": r[2], "phone": r[3], "code": r[4], "custom_pct": r[5], "pct": pct,
                             "status": r[6], "payout_method": r[7] or "", "payout_to": A.payout_label(r[7], r[8]), "clicks": r[9],
                             "created_at": _iso(r[10]), "application": _details(r[11]), "reviewed_at": _iso(r[12]),
                             "referrals": r[13], "personals": count, "qualified": count >= cfg["unlock_count"],
                             "sales": float(r[15]), "pending": float(r[16]), "ready": float(r[17]), "paid": float(r[18])})
            cur.execute("""SELECT p.id, p.affiliate_id, a.name, a.email, p.amount_usd, p.method, p.details, p.status, p.reference,
                                  p.requested_at, p.decided_at
                             FROM tv_aff_payouts p JOIN tv_affiliates a ON a.id = p.affiliate_id
                            ORDER BY (p.status = 'requested') DESC, p.requested_at DESC LIMIT 300""")
            pays = [{"id": r[0], "affiliate_id": r[1], "name": r[2], "email": r[3], "amount": float(r[4]), "method": r[5],
                     "details": _details(r[6]), "to": A.payout_label(r[5], r[6]), "status": r[7], "reference": r[8] or "",
                     "requested_at": _iso(r[9]), "decided_at": _iso(r[10])} for r in cur.fetchall()]
            c.close()
            self._json(200, {"ok": True, "affiliates": affs, "payouts": pays, "settings": cfg, "hold_days": A.HOLD_DAYS})
        except Exception as e:
            A.log("TV_AFF_ADMIN_ERR:", e)
            self._json(500, {"error": str(e)})

    def _admin_detail(self):
        if not self._admin():
            return
        try:
            aff = int((parse_qs(urlparse(self.path).query).get("id") or ["0"])[0])
            c = A.conn()
            cur = c.cursor()
            cur.execute("""
                SELECT r.email, r.tier, r.created_at,
                       COALESCE((SELECT SUM(amount_usd) FROM tv_payments p WHERE p.email = r.email AND NOT p.refunded), 0)
                  FROM tv_aff_referrals r WHERE r.affiliate_id = %s ORDER BY r.created_at DESC
            """, (aff,))
            refs = [{"email": r[0], "tier": r[1], "joined": _iso(r[2]), "paid": float(r[3])} for r in cur.fetchall()]
            cur.execute(f"""SELECT email, product, amount_usd, commission_usd, status, paid_at, {READY}, kind, pct, payout_id
                              FROM tv_aff_commissions WHERE affiliate_id = %s ORDER BY paid_at DESC""", (aff,))
            coms = [{"email": r[0], "product": r[1], "amount": float(r[2]), "commission": float(r[3]), "at": _iso(r[5]),
                     "status": r[4] if r[4] != "pending" else ("requested" if r[9] else ("ready" if r[6] else "held")),
                     "kind": r[7], "pct": r[8]} for r in cur.fetchall()]
            c.close()
            self._json(200, {"ok": True, "referrals": refs, "commissions": coms})
        except Exception as e:
            A.log("TV_AFF_DETAIL_ERR:", e)
            self._json(500, {"error": str(e)})

    def _admin_patch(self):
        if not self._admin():
            return
        b = self._body()
        aff = int(b.get("id") or 0)
        sets, vals = [], []
        if "custom_pct" in b:
            v = b["custom_pct"]
            if v in (None, ""):
                sets.append("custom_pct = NULL")
            else:
                v = int(v)
                if not 0 <= v <= 100:
                    return self._json(400, {"error": "Commission must be 0 to 100%."})
                sets.append("custom_pct = %s")
                vals.append(v)
        status = b.get("status")
        if status in ("active", "paused", "rejected"):
            sets.append("status = %s")
            vals.append(status)
        if not sets or not aff:
            return self._json(400, {"error": "Nothing to update."})
        c = A.conn()
        cur = c.cursor()
        cur.execute("SELECT status, email, name FROM tv_affiliates WHERE id = %s", (aff,))
        before = cur.fetchone()
        if not before:
            c.close()
            return self._json(404, {"error": "No such affiliate."})
        if status in ("active", "rejected") and before[0] == "pending":
            sets.append("reviewed_at = NOW()")
        cur.execute(f"UPDATE tv_affiliates SET {', '.join(sets)} WHERE id = %s", vals + [aff])
        c.commit()
        c.close()
        if before[0] == "pending" and status == "active":
            A.ghl_tag(before[1], before[2], ["tv-affiliate-approved"])
        elif before[0] == "pending" and status == "rejected":
            A.ghl_tag(before[1], before[2], ["tv-affiliate-rejected"])
        self._json(200, {"ok": True})

    def _admin_payout(self):
        if not self._admin():
            return
        b = self._body()
        pid, act = int(b.get("id") or 0), b.get("action")
        ref = (b.get("reference") or "").strip()[:200]
        if not pid or act not in ("paid", "reject"):
            return self._json(400, {"error": "id and action required"})
        c = A.conn()
        cur = c.cursor()
        cur.execute("""SELECT p.affiliate_id, a.email, a.name FROM tv_aff_payouts p JOIN tv_affiliates a ON a.id = p.affiliate_id
                        WHERE p.id = %s AND p.status = 'requested'""", (pid,))
        row = cur.fetchone()
        if not row:
            c.close()
            return self._json(409, {"error": "That payout was already handled."})
        if act == "paid":
            # Pays what's still reserved: anything refunded since the request dropped out.
            cur.execute("SELECT COALESCE(SUM(commission_usd), 0) FROM tv_aff_commissions WHERE payout_id = %s AND status = 'pending'", (pid,))
            amount = float(cur.fetchone()[0])
            cur.execute("UPDATE tv_aff_commissions SET status = 'paid' WHERE payout_id = %s AND status = 'pending'", (pid,))
            cur.execute("UPDATE tv_aff_payouts SET status = 'paid', amount_usd = %s, reference = %s, decided_at = NOW() WHERE id = %s",
                        (amount, ref or None, pid))
        else:
            cur.execute("UPDATE tv_aff_commissions SET payout_id = NULL WHERE payout_id = %s AND status = 'pending'", (pid,))
            cur.execute("UPDATE tv_aff_payouts SET status = 'rejected', reference = %s, decided_at = NOW() WHERE id = %s", (ref or None, pid))
        c.commit()
        c.close()
        if act == "paid":
            A.ghl_tag(row[1], row[2], ["tv-affiliate-paid"], again=True)
        self._json(200, {"ok": True})

    def _admin_bonus(self):
        if not self._admin():
            return
        b = self._body()
        aff = int(b.get("id") or 0)
        note = (b.get("note") or "Bonus").strip()[:80]
        try:
            amount = round(float(b.get("amount") or 0), 2)
        except ValueError:
            amount = 0
        if not aff or not 0 < amount <= 100000:
            return self._json(400, {"error": "Pick an affiliate and an amount."})
        import secrets
        c = A.conn()
        cur = c.cursor()
        cur.execute("""INSERT INTO tv_aff_commissions (affiliate_id, whop_id, email, product, amount_usd, commission_usd, paid_at, kind)
                       SELECT id, %s, '', %s, 0, %s, NOW(), 'bonus' FROM tv_affiliates WHERE id = %s""",
                    ("bonus-" + secrets.token_hex(6), note, amount, aff))
        c.commit()
        c.close()
        self._json(200, {"ok": True})

    def _admin_assign(self):
        if not self._admin():
            return
        b = self._body()
        aff = int(b.get("id") or 0)
        email = (b.get("email") or "").strip().lower()[:160]
        if not aff or not EMAIL_RE.match(email):
            return self._json(400, {"error": "Enter the buyer's checkout email."})
        c = A.conn()
        cur = c.cursor()
        cur.execute("SELECT code, email, status FROM tv_affiliates WHERE id = %s", (aff,))
        row = cur.fetchone()
        if not row:
            c.close()
            return self._json(404, {"error": "Affiliate not found."})
        if row[2] != "active":
            c.close()
            return self._json(400, {"error": "Activate this affiliate first."})
        if row[1] == email:
            c.close()
            return self._json(400, {"error": "That's the affiliate's own email: self-purchases don't count."})
        cur.execute("""SELECT a.id, a.name FROM tv_aff_referrals r JOIN tv_affiliates a ON a.id = r.affiliate_id
                        WHERE r.email = %s""", (email,))
        other = cur.fetchone()
        if other and other[0] != aff:
            c.close()
            return self._json(409, {"error": "Already credited to " + other[1] + "."})
        cur.execute("SELECT tier FROM tv_payments WHERE email = %s ORDER BY paid_at DESC LIMIT 1", (email,))
        tier = (cur.fetchone() or [None])[0]
        c.close()
        A.claim(email, row[0], tier)
        c = A.conn()
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM tv_aff_commissions WHERE affiliate_id = %s AND email = %s", (aff, email))
        n = cur.fetchone()[0]
        c.close()
        self._json(200, {"ok": True, "payments": n})

    def _admin_settings(self):
        if not self._admin():
            return
        b = self._body()
        limits = {"base_pct": (0, 100), "tier_pct": (0, 100), "tier_count": (1, 10000), "unlock_count": (0, 10000)}
        c = A.conn()
        cur = c.cursor()
        for k, (lo, hi) in limits.items():
            if k in b:
                v = int(b[k])
                if not lo <= v <= hi:
                    c.close()
                    return self._json(400, {"error": f"{k} must be {lo} to {hi}."})
                cur.execute("""INSERT INTO tv_aff_settings (key, value) VALUES (%s, %s)
                               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""", (k, str(v)))
        c.commit()
        c.close()
        self._json(200, {"ok": True})

    # ---------- helpers ----------
    def _action(self):
        return (parse_qs(urlparse(self.path).query).get("action") or [""])[0].strip().lower()

    def _body(self):
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 12000)
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
