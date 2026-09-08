import hashlib
import hmac
import http.client
import json
import os
from http.server import BaseHTTPRequestHandler

WHOP_SECRET  = os.environ.get("WHOP_WEBHOOK_SECRET", "")
GHL_API_KEY  = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"

PLAN_TAGS = {
    "sniper-basic-ed":    ["purchased", "purchased-standard"],
    "sniper-accelerator": ["purchased", "purchased-accelerator"],
    "sniper-elite-72":    ["purchased", "purchased-elite"],
}


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_GET(self):
        self._json(200, {"ok": True, "service": "whop-webhook"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)

            # Signature verification — skipped temporarily for debugging
            # sig = (self.headers.get("whop-signature") or
            #        self.headers.get("Whop-Signature") or "")
            # if WHOP_SECRET and sig:
            #     expected = hmac.new(
            #         WHOP_SECRET.encode(), raw_body, hashlib.sha256
            #     ).hexdigest()
            #     bare = sig.split("=")[-1]
            #     if not hmac.compare_digest(expected, bare):
            #         self._json(401, {"error": "invalid signature"})
            #         return

            event = json.loads(raw_body)
            event_type = event.get("event", "")

            # Debug: return full payload so we can inspect it
            import sys
            print("WHOP EVENT:", event_type, json.dumps(event)[:500], file=sys.stderr)

            if event_type not in ("payment.succeeded", "membership.went_valid",
                                   "membership.activated", "member.created"):
                self._json(200, {"ok": True, "skipped": event_type})
                return

            data  = event.get("data", {})
            # membership.activated nests user under data.user; member.created may use data directly
            user  = data.get("user") or data.get("customer") or {}
            plan  = data.get("plan") or data.get("product") or {}

            email = (user.get("email") or data.get("email") or "").strip().lower()
            name  = (user.get("name") or user.get("username") or
                     user.get("display_name") or "").strip()
            phone = (user.get("phone_number") or "").strip()
            slug  = (plan.get("slug") or plan.get("id") or
                     data.get("plan_id") or data.get("product_slug") or "").strip()

            if not email:
                self._json(400, {"error": "no email in payload"})
                return

            parts = name.split(" ", 1)
            first = parts[0] if parts else ""
            last  = parts[1] if len(parts) > 1 else ""
            tags  = PLAN_TAGS.get(slug, ["purchased"])

            ghl_result = self._ghl_upsert(email, first, last, phone, tags)
            self._record_affiliate_purchase(email, slug, None)
            self._json(200, {"ok": True, "email": email, "tags": tags, "ghl": ghl_result})

        except Exception as e:
            self._json(500, {"error": str(e)})

    def _ghl_upsert(self, email, first, last, phone, tags):
        import sys
        if not GHL_API_KEY:
            print("GHL_UPSERT: no GHL_API_KEY set", file=sys.stderr)
            return {"error": "no api key"}

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + GHL_API_KEY,
        }
        payload = {
            "locationId": GHL_LOCATION,
            "email": email,
            "firstName": first,
            "lastName": last,
            "tags": tags,
        }
        if phone:
            payload["phone"] = phone

        try:
            # Search for existing contact
            conn = http.client.HTTPSConnection("rest.gohighlevel.com")
            conn.request(
                "GET",
                "/v1/contacts/search?email=" + email + "&locationId=" + GHL_LOCATION,
                headers=headers,
            )
            res   = conn.getresponse()
            body  = res.read()
            data  = json.loads(body)
            contacts = data.get("contacts", [])
            print("GHL_SEARCH:", res.status, len(contacts), "contacts", file=sys.stderr)

            if contacts:
                cid = contacts[0]["id"]
                conn2 = http.client.HTTPSConnection("rest.gohighlevel.com")
                conn2.request("PUT", "/v1/contacts/" + cid, json.dumps(payload), headers)
                res2  = conn2.getresponse()
                body2 = res2.read()
                print("GHL_UPDATE:", res2.status, body2[:200], file=sys.stderr)
                return {"status": res2.status, "body": body2.decode()[:200]}
            else:
                conn3 = http.client.HTTPSConnection("rest.gohighlevel.com")
                conn3.request("POST", "/v1/contacts/", json.dumps(payload), headers)
                res3  = conn3.getresponse()
                body3 = res3.read()
                print("GHL_CREATE:", res3.status, body3[:200], file=sys.stderr)
                return {"status": res3.status, "body": body3.decode()[:200]}
        except Exception as e:
            print("GHL_UPSERT_ERR:", e, file=sys.stderr)
            return {"error": str(e)}

    def _record_affiliate_purchase(self, email, slug, amount_usd_override):
        """Attribute a Whop purchase to an affiliate if we have prior tracking events."""
        if not email:
            return
        try:
            import psycopg2
            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                return
            PLAN_AMOUNTS = {
                "sniper-basic-ed":    999.0,
                "sniper-accelerator": 5999.0,
                "sniper-elite-72":    9999.0,
            }
            amount_usd = amount_usd_override or PLAN_AMOUNTS.get(slug, 0)

            conn = psycopg2.connect(db_url)
            cur  = conn.cursor()

            # Idempotency: skip if purchased event already exists for this email
            cur.execute(
                "SELECT id FROM jb_aff_events WHERE visitor_email = %s AND event_type = 'purchased' LIMIT 1",
                (email,)
            )
            if cur.fetchone():
                cur.close(); conn.close()
                return

            # Find affiliate from most recent optin or call_booked event
            cur.execute("""
                SELECT e.affiliate_id, a.commission_pct
                FROM jb_aff_events e
                JOIN jb_affiliates a ON a.id = e.affiliate_id
                WHERE e.visitor_email = %s
                  AND e.event_type IN ('optin', 'call_booked')
                  AND a.status = 'active'
                ORDER BY e.created_at DESC LIMIT 1
            """, (email,))
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                return

            aff_id, commission_pct = row
            commission = round(float(amount_usd) * commission_pct / 100, 2)

            cur.execute("""
                INSERT INTO jb_aff_events
                  (affiliate_id, event_type, visitor_email, plan, amount_usd, commission_usd, commission_status)
                VALUES (%s, 'purchased', %s, %s, %s, %s, 'pending')
            """, (aff_id, email, slug, amount_usd, commission))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            import sys
            print("AFF_PURCHASE_ERR:", e, file=sys.stderr)

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)
