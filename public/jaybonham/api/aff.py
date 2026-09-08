"""
Unified affiliate API — all endpoints in one function to stay within Vercel's 12-function limit.
Route by query param: /api/aff?action=<action>

Actions:
  register   POST   — create affiliate account
  login      POST   — set session cookie  |  DELETE — clear cookie
  me         GET    — profile + stats + events (affiliate session)
  click      POST   — increment click counter
  event      POST   — record optin / call_booked
  admin      GET    — list all affiliates (admin JWT)
             PATCH  — update affiliate (admin JWT)
  payout     POST   — affiliate requests payout
             PATCH  — admin approves or rejects (admin JWT)
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))
from _aff_db import (
    get_conn, hash_password, check_password,
    generate_code, sign_session, get_aff_id_from_request,
)
from _auth import verify_token

COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
VALID_EVENT_TYPES = {"optin", "call_booked"}


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    # ------------------------------------------------------------------
    # HTTP method dispatch
    # ------------------------------------------------------------------
    def do_OPTIONS(self):
        self._cors(200)

    def do_GET(self):
        action = self._action()
        if action == "me":
            self._me()
        elif action == "admin":
            self._admin_get()
        else:
            self._json(404, {"error": "unknown action"})

    def do_POST(self):
        action = self._action()
        if action == "register":
            self._register()
        elif action == "login":
            self._login()
        elif action == "click":
            self._click()
        elif action == "event":
            self._event()
        elif action == "payout":
            self._payout_request()
        else:
            self._json(404, {"error": "unknown action"})

    def do_DELETE(self):
        action = self._action()
        if action == "login":
            self._logout()
        else:
            self._json(404, {"error": "unknown action"})

    def do_PATCH(self):
        action = self._action()
        if action == "admin":
            self._admin_patch()
        elif action == "payout":
            self._payout_admin()
        else:
            self._json(404, {"error": "unknown action"})

    # ------------------------------------------------------------------
    # Affiliate: register
    # ------------------------------------------------------------------
    def _register(self):
        try:
            body     = self._body()
            name     = (body.get("name") or "").strip()
            email    = (body.get("email") or "").strip().lower()
            phone    = (body.get("phone") or "").strip()
            password = (body.get("password") or "").strip()
            code_req    = (body.get("code") or "").strip().lower()
            payout_info = (body.get("payout_info") or "").strip()

            if not name or not email or not password:
                return self._json(400, {"error": "name, email and password are required"})
            if len(password) < 8:
                return self._json(400, {"error": "password must be at least 8 characters"})
            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
                return self._json(400, {"error": "invalid email"})
            if code_req and not re.match(r"^[a-z0-9_]{3,20}$", code_req):
                return self._json(400, {"error": "code must be 3-20 lowercase letters/numbers/underscores"})

            code = code_req or generate_code()
            password_hash, password_salt = hash_password(password)

            conn = get_conn()
            cur  = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO jb_affiliates (name, email, phone, code, password_hash, password_salt, payout_info)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, code
                """, (name, email, phone or None, code, password_hash, password_salt, payout_info or None))
                row = cur.fetchone()
                conn.commit()
                # Auto-login after register
                token  = sign_session(row[0])
                cookie = f"jb_aff_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={COOKIE_MAX_AGE}"
                self._json(200, {"ok": True, "id": row[0], "code": row[1]},
                           extra=[("Set-Cookie", cookie)])
            except Exception as e:
                conn.rollback()
                err = str(e)
                if "jb_affiliates_email_key" in err:
                    self._json(409, {"error": "email already registered"})
                elif "jb_affiliates_code_key" in err:
                    code = generate_code()
                    try:
                        cur.execute("""
                            INSERT INTO jb_affiliates (name, email, phone, code, password_hash, password_salt, payout_info)
                            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, code
                        """, (name, email, phone or None, code, password_hash, password_salt, payout_info or None))
                        row = cur.fetchone()
                        conn.commit()
                        token  = sign_session(row[0])
                        cookie = f"jb_aff_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={COOKIE_MAX_AGE}"
                        self._json(200, {"ok": True, "id": row[0], "code": row[1]},
                                   extra=[("Set-Cookie", cookie)])
                    except Exception:
                        conn.rollback()
                        self._json(409, {"error": "code already taken, try a different one"})
                else:
                    self._json(500, {"error": "registration failed"})
            finally:
                cur.close(); conn.close()
        except Exception as e:
            self._json(500, {"error": str(e)})

    # ------------------------------------------------------------------
    # Affiliate: login / logout
    # ------------------------------------------------------------------
    def _login(self):
        try:
            body     = self._body()
            email    = (body.get("email") or "").strip().lower()
            password = (body.get("password") or "").strip()

            if not email or not password:
                return self._json(400, {"error": "email and password required"})

            conn = get_conn()
            cur  = conn.cursor()
            cur.execute(
                "SELECT id, name, code, password_hash, password_salt, status "
                "FROM jb_affiliates WHERE email = %s", (email,)
            )
            row = cur.fetchone()
            cur.close(); conn.close()

            if not row or not check_password(password, row[3], row[4]):
                return self._json(401, {"error": "invalid email or password"})
            if row[5] == "suspended":
                return self._json(403, {"error": "account suspended"})

            token  = sign_session(row[0])
            cookie = f"jb_aff_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={COOKIE_MAX_AGE}"
            self._json(200, {"ok": True, "name": row[1], "code": row[2]},
                       extra=[("Set-Cookie", cookie)])
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _logout(self):
        clear = "jb_aff_session=; Path=/; HttpOnly; Max-Age=0"
        self._json(200, {"ok": True}, extra=[("Set-Cookie", clear)])

    # ------------------------------------------------------------------
    # Affiliate: profile + stats + events
    # ------------------------------------------------------------------
    def _me(self):
        try:
            aff_id = get_aff_id_from_request(self.headers)
            if not aff_id:
                return self._json(401, {"error": "not logged in"})

            conn = get_conn()
            cur  = conn.cursor()

            cur.execute(
                "SELECT id, name, email, phone, code, commission_pct, status, "
                "payout_info, total_clicks, payout_status, payout_requested_amt "
                "FROM jb_affiliates WHERE id = %s", (aff_id,)
            )
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                return self._json(401, {"error": "affiliate not found"})

            cur.execute("""
                SELECT
                    COALESCE(SUM(CASE WHEN event_type='optin'       THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN event_type='call_booked' THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN event_type='purchased'   THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN commission_status='pending' THEN commission_usd ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN commission_status='paid'    THEN commission_usd ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN commission_status='pending'
                                      AND created_at < NOW() - INTERVAL '30 days'
                                 THEN commission_usd ELSE 0 END), 0)
                FROM jb_aff_events WHERE affiliate_id = %s
            """, (aff_id,))
            s = cur.fetchone()

            cur.execute("""
                SELECT id, event_type, visitor_email, visitor_name, plan,
                       amount_usd, commission_usd, commission_status, created_at
                FROM jb_aff_events
                WHERE affiliate_id = %s
                ORDER BY created_at DESC LIMIT 100
            """, (aff_id,))
            events = []
            for r in cur.fetchall():
                events.append({
                    "id": r[0], "event_type": r[1],
                    "visitor_email": r[2], "visitor_name": r[3],
                    "plan": r[4],
                    "amount_usd":      float(r[5]) if r[5] else None,
                    "commission_usd":  float(r[6]) if r[6] else None,
                    "commission_status": r[7],
                    "created_at": r[8].isoformat() if r[8] else None,
                })

            cur.close(); conn.close()

            self._json(200, {
                "ok": True,
                # Profile fields flat at top level (matches dashboard JS)
                "id": row[0], "name": row[1], "email": row[2], "phone": row[3],
                "code": row[4], "commission_pct": row[5], "status": row[6],
                "payout_info": row[7], "total_clicks": row[8],
                "payout_status": row[9],
                "payout_requested_amt": float(row[10]) if row[10] else 0,
                "stats": {
                    "clicks":          row[8],
                    "optins":          int(s[0]),
                    "calls":           int(s[1]),
                    "purchases":       int(s[2]),
                    "pending_usd":     float(s[3]),
                    "paid_usd":        float(s[4]),
                    "payable_now_usd": float(s[5]),
                },
                "events": events,
            })
        except Exception as e:
            self._json(500, {"error": str(e)})

    # ------------------------------------------------------------------
    # Tracking: click counter
    # ------------------------------------------------------------------
    def _click(self):
        try:
            body = self._body()
            code = (body.get("code") or "").strip().lower()
            if not code:
                return self._json(200, {"ok": True})
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute(
                "UPDATE jb_affiliates SET total_clicks = total_clicks + 1 "
                "WHERE code = %s AND status = 'active' RETURNING name", (code,)
            )
            row = cur.fetchone()
            conn.commit(); cur.close(); conn.close()
            self._json(200, {"ok": True, "name": row[0] if row else None})
        except Exception:
            self._json(200, {"ok": True})

    # ------------------------------------------------------------------
    # Tracking: optin / call_booked event
    # ------------------------------------------------------------------
    def _event(self):
        try:
            body = self._body()

            # GHL sends custom field data as top-level keys with label names,
            # not via our configured custom-data mappings. Read defensively:
            # 1. type: from body, OR from URL query param (?type=call_booked)
            # 2. ref_code: from body["ref_code"] OR body["jb_ref"] (GHL custom field label)
            # 3. email: from body["email"] (standard GHL contact field, always present)
            qs = parse_qs(urlparse(self.path).query)
            type_from_qs = (qs.get("type") or [""])[0].strip().lower()

            event_type = (body.get("type") or type_from_qs or "").strip().lower()
            email      = (body.get("email") or "").strip().lower()
            ref_code   = (body.get("ref_code") or body.get("jb_ref") or "").strip().lower()
            name       = (body.get("name") or body.get("full_name") or "").strip()

            if event_type not in VALID_EVENT_TYPES or not ref_code:
                return self._json(200, {"ok": True, "skipped": "no_ref",
                                        "received": {"type": event_type, "ref_code": ref_code,
                                                     "email": email, "keys": list(body.keys())}})

            conn = get_conn()
            cur  = conn.cursor()
            cur.execute(
                "SELECT id FROM jb_affiliates WHERE code = %s AND status = 'active'",
                (ref_code,)
            )
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                return self._json(200, {"ok": True, "skipped": "no_affiliate", "ref_code": ref_code})

            aff_id = row[0]
            if email:
                cur.execute("""
                    SELECT id FROM jb_aff_events
                    WHERE affiliate_id = %s AND event_type = %s
                      AND visitor_email = %s AND created_at > NOW() - INTERVAL '24 hours'
                    LIMIT 1
                """, (aff_id, event_type, email))
                if cur.fetchone():
                    cur.close(); conn.close()
                    return self._json(200, {"ok": True, "skipped": "duplicate"})

            cur.execute("""
                INSERT INTO jb_aff_events (affiliate_id, event_type, visitor_email, visitor_name)
                VALUES (%s, %s, %s, %s)
            """, (aff_id, event_type, email or None, name or None))
            conn.commit(); cur.close(); conn.close()
            self._json(200, {"ok": True})
        except Exception:
            self._json(200, {"ok": True})

    # ------------------------------------------------------------------
    # Admin: list affiliates
    # ------------------------------------------------------------------
    def _admin_get(self):
        if not self._is_admin():
            return
        try:
            conn = get_conn()
            cur  = conn.cursor()
            # Main affiliate rows with aggregated stats
            cur.execute("""
                SELECT
                    a.id, a.name, a.email, a.phone, a.code,
                    a.commission_pct, a.status, a.payout_info,
                    a.total_clicks, a.payout_status,
                    a.payout_requested_at, a.payout_requested_amt, a.created_at,
                    COALESCE(SUM(CASE WHEN e.event_type='optin'       THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN e.event_type='call_booked' THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN e.event_type='purchased'   THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN e.commission_status='pending' THEN e.commission_usd ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN e.commission_status='paid'    THEN e.commission_usd ELSE 0 END), 0)
                FROM jb_affiliates a
                LEFT JOIN jb_aff_events e ON e.affiliate_id = a.id
                GROUP BY a.id ORDER BY a.created_at DESC
            """)
            aff_rows = cur.fetchall()

            # Per-affiliate events (last 50 each)
            aff_ids = [r[0] for r in aff_rows]
            events_by_aff = {i: [] for i in aff_ids}
            if aff_ids:
                placeholders = ",".join(["%s"] * len(aff_ids))
                cur.execute(f"""
                    SELECT affiliate_id, id, event_type, visitor_email, visitor_name,
                           plan, amount_usd, commission_usd, commission_status, created_at
                    FROM (
                        SELECT *, ROW_NUMBER() OVER (PARTITION BY affiliate_id ORDER BY created_at DESC) AS rn
                        FROM jb_aff_events WHERE affiliate_id IN ({placeholders})
                    ) sub WHERE rn <= 50
                """, aff_ids)
                for r in cur.fetchall():
                    events_by_aff[r[0]].append({
                        "id": r[1], "event_type": r[2],
                        "visitor_email": r[3], "visitor_name": r[4], "plan": r[5],
                        "amount_usd":    float(r[6]) if r[6] else None,
                        "commission_usd": float(r[7]) if r[7] else None,
                        "commission_status": r[8],
                        "created_at": r[9].isoformat() if r[9] else None,
                    })

            cur.close(); conn.close()

            affiliates = []
            totals = {"clicks": 0, "optins": 0, "calls": 0, "purchases": 0, "pending_usd": 0.0}
            for r in aff_rows:
                affiliates.append({
                    "id": r[0], "name": r[1], "email": r[2], "phone": r[3],
                    "code": r[4], "commission_pct": r[5], "status": r[6],
                    "payout_info": r[7], "total_clicks": r[8],
                    "payout_status": r[9],
                    "payout_requested_at":  r[10].isoformat() if r[10] else None,
                    "payout_requested_amt": float(r[11]) if r[11] else 0,
                    "created_at": r[12].isoformat() if r[12] else None,
                    # stats_ prefix to match admin HTML
                    "stats_optins":    int(r[13]),
                    "stats_calls":     int(r[14]),
                    "stats_purchases": int(r[15]),
                    "stats_pending_usd": float(r[16]),
                    "stats_paid_usd":    float(r[17]),
                    "events": events_by_aff.get(r[0], []),
                })
                totals["clicks"]      += r[8]
                totals["optins"]      += int(r[13])
                totals["calls"]       += int(r[14])
                totals["purchases"]   += int(r[15])
                totals["pending_usd"] += float(r[16])

            totals["pending_usd"] = round(totals["pending_usd"], 2)
            self._json(200, {"ok": True, "affiliates": affiliates, "totals": totals})
        except Exception as e:
            self._json(500, {"error": str(e)})

    # ------------------------------------------------------------------
    # Admin: update affiliate
    # ------------------------------------------------------------------
    def _admin_patch(self):
        if not self._is_admin():
            return
        try:
            body   = self._body()
            aff_id = body.get("id")
            if not aff_id:
                return self._json(400, {"error": "id required"})

            updates = {}
            if "commission_pct" in body:
                pct = int(body["commission_pct"])
                if not (0 <= pct <= 100):
                    return self._json(400, {"error": "commission_pct must be 0-100"})
                updates["commission_pct"] = pct
            if "status" in body:
                if body["status"] not in ("active", "suspended"):
                    return self._json(400, {"error": "status must be active or suspended"})
                updates["status"] = body["status"]
            if "payout_info" in body:
                updates["payout_info"] = body["payout_info"]
            if not updates:
                return self._json(400, {"error": "nothing to update"})

            set_clause = ", ".join(f"{k} = %s" for k in updates)
            vals = list(updates.values()) + [aff_id]
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute(f"UPDATE jb_affiliates SET {set_clause} WHERE id = %s", vals)
            conn.commit(); cur.close(); conn.close()
            self._json(200, {"ok": True})
        except Exception as e:
            self._json(500, {"error": str(e)})

    # ------------------------------------------------------------------
    # Payout: affiliate requests
    # ------------------------------------------------------------------
    def _payout_request(self):
        try:
            aff_id = get_aff_id_from_request(self.headers)
            if not aff_id:
                return self._json(401, {"error": "not logged in"})

            body        = self._body()
            payout_info = (body.get("payout_info") or "").strip()

            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("SELECT payout_status FROM jb_affiliates WHERE id = %s", (aff_id,))
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                return self._json(404, {"error": "affiliate not found"})
            if row[0] != "none":
                cur.close(); conn.close()
                return self._json(409, {"error": "payout already requested or processed"})

            cur.execute("""
                SELECT COALESCE(SUM(commission_usd), 0)
                FROM jb_aff_events
                WHERE affiliate_id = %s AND commission_status = 'pending'
                  AND created_at < NOW() - INTERVAL '30 days'
            """, (aff_id,))
            amount = float(cur.fetchone()[0])
            if amount <= 0:
                cur.close(); conn.close()
                return self._json(400, {"error": "no commissions available yet (30-day hold applies)"})

            if payout_info:
                cur.execute("UPDATE jb_affiliates SET payout_info = %s WHERE id = %s",
                            (payout_info, aff_id))
            cur.execute("""
                UPDATE jb_affiliates
                SET payout_status = 'requested',
                    payout_requested_at  = NOW(),
                    payout_requested_amt = %s
                WHERE id = %s
            """, (amount, aff_id))
            conn.commit(); cur.close(); conn.close()
            self._json(200, {"ok": True, "amount": amount})
        except Exception as e:
            self._json(500, {"error": str(e)})

    # ------------------------------------------------------------------
    # Payout: admin approves / rejects
    # ------------------------------------------------------------------
    def _payout_admin(self):
        if not self._is_admin():
            return
        try:
            body       = self._body()
            aff_id     = body.get("affiliate_id") or body.get("id")
            action     = body.get("action")

            if not aff_id or action not in ("approve", "reject"):
                return self._json(400, {"error": "affiliate_id and action (approve|reject) required"})

            conn = get_conn()
            cur  = conn.cursor()
            if action == "approve":
                cur.execute("""
                    UPDATE jb_aff_events
                    SET commission_status = 'paid'
                    WHERE affiliate_id = %s AND commission_status = 'pending'
                """, (aff_id,))
                cur.execute(
                    "UPDATE jb_affiliates SET payout_status = 'paid' WHERE id = %s",
                    (aff_id,)
                )
            else:
                cur.execute("""
                    UPDATE jb_affiliates
                    SET payout_status = 'none',
                        payout_requested_at  = NULL,
                        payout_requested_amt = NULL
                    WHERE id = %s
                """, (aff_id,))
            conn.commit(); cur.close(); conn.close()
            self._json(200, {"ok": True})
        except Exception as e:
            self._json(500, {"error": str(e)})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _action(self):
        qs = parse_qs(urlparse(self.path).query)
        return (qs.get("action") or [""])[0].strip().lower()

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length) or b"{}")

    def _is_admin(self):
        token = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
        if not verify_token(token):
            self._json(401, {"error": "unauthorized"})
            return False
        return True

    def _json(self, status, body, extra=None):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if extra:
            for k, v in extra:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
