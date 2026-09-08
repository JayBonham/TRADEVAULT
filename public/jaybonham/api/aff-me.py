import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _aff_db import get_conn, get_aff_id_from_request


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._cors(200)

    def do_GET(self):
        """Return affiliate profile + stats + recent events."""
        try:
            aff_id = get_aff_id_from_request(self.headers)
            if not aff_id:
                self._json(401, {"error": "not logged in"})
                return

            conn = get_conn()
            cur  = conn.cursor()

            # Profile
            cur.execute(
                "SELECT id, name, email, phone, code, commission_pct, status, "
                "payout_info, total_clicks, payout_status, payout_requested_amt "
                "FROM jb_affiliates WHERE id = %s",
                (aff_id,)
            )
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                self._json(401, {"error": "not found"})
                return

            profile = {
                "id": row[0], "name": row[1], "email": row[2],
                "phone": row[3], "code": row[4], "commission_pct": row[5],
                "status": row[6], "payout_info": row[7],
                "total_clicks": row[8], "payout_status": row[9],
                "payout_requested_amt": float(row[10]) if row[10] else 0,
            }

            # Aggregated stats from events
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
            stats = {
                "optins":          int(s[0]),
                "calls":           int(s[1]),
                "purchases":       int(s[2]),
                "pending_usd":     float(s[3]),
                "paid_usd":        float(s[4]),
                "payable_now_usd": float(s[5]),
            }

            # Recent events (last 100)
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
                    "id": r[0], "type": r[1], "email": r[2], "name": r[3],
                    "plan": r[4],
                    "amount_usd":     float(r[5]) if r[5] else None,
                    "commission_usd": float(r[6]) if r[6] else None,
                    "commission_status": r[7],
                    "created_at": r[8].isoformat() if r[8] else None,
                })

            cur.close()
            conn.close()

            ref_link = f"https://jaybonham.com?ref={profile['code']}"
            self._json(200, {
                "ok": True,
                "profile": profile,
                "stats": stats,
                "events": events,
                "ref_link": ref_link,
            })

        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
