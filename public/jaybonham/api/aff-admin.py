import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _aff_db import get_conn

# Import admin JWT verifier
sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._cors(200)

    def do_GET(self):
        """Admin: list all affiliates with aggregated stats."""
        if not self._check_admin():
            return
        try:
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("""
                SELECT
                    a.id, a.name, a.email, a.phone, a.code,
                    a.commission_pct, a.status, a.payout_info,
                    a.total_clicks, a.payout_status,
                    a.payout_requested_at, a.payout_requested_amt,
                    a.created_at,
                    COALESCE(SUM(CASE WHEN e.event_type='optin'       THEN 1 ELSE 0 END), 0) AS optins,
                    COALESCE(SUM(CASE WHEN e.event_type='call_booked' THEN 1 ELSE 0 END), 0) AS calls,
                    COALESCE(SUM(CASE WHEN e.event_type='purchased'   THEN 1 ELSE 0 END), 0) AS sales,
                    COALESCE(SUM(CASE WHEN e.commission_status='pending' THEN e.commission_usd ELSE 0 END), 0) AS pending_usd,
                    COALESCE(SUM(CASE WHEN e.commission_status='paid'    THEN e.commission_usd ELSE 0 END), 0) AS paid_usd
                FROM jb_affiliates a
                LEFT JOIN jb_aff_events e ON e.affiliate_id = a.id
                GROUP BY a.id
                ORDER BY a.created_at DESC
            """)
            rows = cur.fetchall()

            affiliates = []
            total_clicks = total_optins = total_calls = total_sales = total_pending = 0
            for r in rows:
                affiliates.append({
                    "id": r[0], "name": r[1], "email": r[2], "phone": r[3],
                    "code": r[4], "commission_pct": r[5], "status": r[6],
                    "payout_info": r[7], "total_clicks": r[8],
                    "payout_status": r[9],
                    "payout_requested_at": r[10].isoformat() if r[10] else None,
                    "payout_requested_amt": float(r[11]) if r[11] else 0,
                    "created_at": r[12].isoformat() if r[12] else None,
                    "optins": int(r[13]), "calls": int(r[14]),
                    "sales": int(r[15]),
                    "pending_usd": float(r[16]), "paid_usd": float(r[17]),
                })
                total_clicks  += r[8]
                total_optins  += int(r[13])
                total_calls   += int(r[14])
                total_sales   += int(r[15])
                total_pending += float(r[16])

            cur.close()
            conn.close()

            self._json(200, {
                "ok": True,
                "affiliates": affiliates,
                "totals": {
                    "affiliates": len(affiliates),
                    "clicks": total_clicks,
                    "optins": total_optins,
                    "calls": total_calls,
                    "sales": total_sales,
                    "pending_usd": round(total_pending, 2),
                },
            })
        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_PATCH(self):
        """Admin: update affiliate commission_pct or status."""
        if not self._check_admin():
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")
            aff_id = body.get("id")
            if not aff_id:
                self._json(400, {"error": "id required"})
                return

            updates = {}
            if "commission_pct" in body:
                pct = int(body["commission_pct"])
                if not (0 <= pct <= 100):
                    self._json(400, {"error": "commission_pct must be 0-100"})
                    return
                updates["commission_pct"] = pct
            if "status" in body:
                if body["status"] not in ("active", "suspended"):
                    self._json(400, {"error": "status must be active or suspended"})
                    return
                updates["status"] = body["status"]
            if "payout_info" in body:
                updates["payout_info"] = body["payout_info"]

            if not updates:
                self._json(400, {"error": "nothing to update"})
                return

            set_clause = ", ".join(f"{k} = %s" for k in updates)
            vals = list(updates.values()) + [aff_id]

            conn = get_conn()
            cur  = conn.cursor()
            cur.execute(f"UPDATE jb_affiliates SET {set_clause} WHERE id = %s", vals)
            conn.commit()
            cur.close()
            conn.close()
            self._json(200, {"ok": True})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_GET_events(self):
        pass  # Future: per-affiliate event log endpoint

    def _check_admin(self):
        token = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
        if not verify_token(token):
            self._json(401, {"error": "unauthorized"})
            return False
        return True

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
