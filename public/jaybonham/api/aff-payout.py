import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _aff_db import get_conn, get_aff_id_from_request
from _auth import verify_token


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        """Affiliate requests a payout."""
        try:
            aff_id = get_aff_id_from_request(self.headers)
            if not aff_id:
                self._json(401, {"error": "not logged in"})
                return

            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")
            payout_info = (body.get("payout_info") or "").strip()

            conn = get_conn()
            cur  = conn.cursor()

            # Check current payout status
            cur.execute(
                "SELECT payout_status FROM jb_affiliates WHERE id = %s", (aff_id,)
            )
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                self._json(404, {"error": "affiliate not found"})
                return
            if row[0] != "none":
                cur.close(); conn.close()
                self._json(409, {"error": "payout already requested or processed"})
                return

            # Check payable amount (30-day hold)
            cur.execute("""
                SELECT COALESCE(SUM(commission_usd), 0)
                FROM jb_aff_events
                WHERE affiliate_id      = %s
                  AND commission_status = 'pending'
                  AND created_at        < NOW() - INTERVAL '30 days'
            """, (aff_id,))
            amount = float(cur.fetchone()[0])

            if amount <= 0:
                cur.close(); conn.close()
                self._json(400, {"error": "no commissions available yet (30-day hold applies)"})
                return

            # Update payout_info if provided, then set status
            if payout_info:
                cur.execute(
                    "UPDATE jb_affiliates SET payout_info = %s WHERE id = %s",
                    (payout_info, aff_id)
                )
            cur.execute("""
                UPDATE jb_affiliates
                SET payout_status = 'requested',
                    payout_requested_at  = NOW(),
                    payout_requested_amt = %s
                WHERE id = %s
            """, (amount, aff_id))
            conn.commit()
            cur.close()
            conn.close()

            self._json(200, {"ok": True, "amount": amount})

        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_PATCH(self):
        """Admin: approve or reject a payout request."""
        token = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
        if not verify_token(token):
            self._json(401, {"error": "unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")
            aff_id = body.get("id")
            action = body.get("action")  # "approve" | "reject"

            if not aff_id or action not in ("approve", "reject"):
                self._json(400, {"error": "id and action (approve|reject) required"})
                return

            conn = get_conn()
            cur  = conn.cursor()

            if action == "approve":
                # Mark all pending commissions as paid
                cur.execute("""
                    UPDATE jb_aff_events
                    SET commission_status = 'paid'
                    WHERE affiliate_id      = %s
                      AND commission_status = 'pending'
                """, (aff_id,))
                cur.execute(
                    "UPDATE jb_affiliates SET payout_status = 'paid' WHERE id = %s",
                    (aff_id,)
                )
            else:
                # Reject: reset so they can request again
                cur.execute("""
                    UPDATE jb_affiliates
                    SET payout_status = 'none',
                        payout_requested_at  = NULL,
                        payout_requested_amt = NULL
                    WHERE id = %s
                """, (aff_id,))

            conn.commit()
            cur.close()
            conn.close()
            self._json(200, {"ok": True})

        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
