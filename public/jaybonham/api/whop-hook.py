import hashlib
import hmac
import http.client
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler

sys_path = os.path.dirname(__file__)

WHOP_SECRET  = os.environ.get("WHOP_WEBHOOK_SECRET", "")
GHL_API_KEY  = os.environ.get("GHL_API_KEY", "")
GHL_LOCATION = "gjD9eQ5iWb8X6zNbltKP"
SLACK_WEBHOOK_PAYMENTS = os.environ.get("SLACK_WEBHOOK_PAYMENTS", "")
WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
WHOP_COMPANY = "biz_R8QEgfRFt2KfLV"
# Store routes of the TradeVault products, for payments that arrive without a product title.
TV_ROUTES = {"sniper-tools": "Tradevault Tools", "sniper-community-3c": "Tradevault Community",
             "sniper-elite-3d": "Tradevault Elite"}

# Signatures are checked and logged on every event; rejecting bad ones is switched on
# once a real Whop event has been seen to pass (GET /api/whop-hook?sig=1).
ENFORCE_SIG = False
SIG_TABLE = """CREATE TABLE IF NOT EXISTS whop_sig_log (
    id BIGSERIAL PRIMARY KEY, at TIMESTAMPTZ NOT NULL DEFAULT now(),
    event TEXT, scheme TEXT, headers TEXT)"""
# Raw payment/membership events, kept so a handler bug can be fixed and the events replayed.
EVENT_TABLE = """CREATE TABLE IF NOT EXISTS whop_events (
    id BIGSERIAL PRIMARY KEY, at TIMESTAMPTZ NOT NULL DEFAULT now(),
    event TEXT, body TEXT)"""

PLAN_PRICES = {
    "sniper-basic-ed":    999.0,
    "sniper-accelerator": 5999.0,
    "sniper-elite-72":    9999.0,
}

SLACK_EVENTS = {
    "payment.succeeded": ("\U0001F4B0", "Payment received"),
    "payment.failed":    ("\u26A0\uFE0F", "Payment FAILED"),
    "payment.refunded":  ("\U0001F501", "Refund issued"),
    "refund.created":    ("\U0001F501", "Refund issued"),
    "refund.updated":    ("\U0001F501", "Refund updated"),
    "dispute.created":   ("\U0001F6A8", "Dispute / chargeback opened"),
}

PLAN_TAGS = {
    "sniper-basic-ed":    ["purchased", "purchased-standard"],
    "sniper-accelerator": ["purchased", "purchased-accelerator"],
    "sniper-elite-72":    ["purchased", "purchased-elite"],
}


def money(v):
    """Whop amounts: a number, a numeric string, or (API 2026-10-27+) {"amount": "174.99", ...}."""
    if isinstance(v, dict):
        v = v.get("amount")
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def find_email(obj, depth=0):
    if depth > 4:
        return ""
    if isinstance(obj, dict):
        e = obj.get("email")
        if isinstance(e, str) and "@" in e:
            return e
        for v in obj.values():
            e = find_email(v, depth + 1)
            if e:
                return e
    elif isinstance(obj, list):
        for v in obj:
            e = find_email(v, depth + 1)
            if e:
                return e
    return ""


def purchase_tags(slug, title):
    """Tags from the Whop product title, so new products tag themselves.
    e.g. "Sniper Elite - $999 Deposit" -> purchased, purchased-deposit, purchased-elite"""
    t = title.lower()
    if "tradevault" in t:
        tags = ["tradevault-purchased"]
        for key in ("tools", "community", "elite"):
            if key in t:
                tags.append("tradevault-" + key)
        return tags
    tags = list(PLAN_TAGS.get(slug, ["purchased"]))
    if "deposit" in t:
        tags.append("purchased-deposit")
    for key, tag in (("fast start", "purchased-fast-start"), ("accelerator", "purchased-accelerator"),
                     ("elite", "purchased-elite")):
        if key in t and tag not in tags:
            tags.append(tag)
    return tags


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def do_GET(self):
        if "backfill=1" in self.path:
            self._backfill()
            return
        if "sig=1" in self.path:
            # Recent signature results (no secrets) so the check can be confirmed before enforcing.
            rows = []
            try:
                sys.path.insert(0, sys_path)
                import _tv_aff
                c = _tv_aff.conn(); cur = c.cursor()
                cur.execute(SIG_TABLE)
                cur.execute("SELECT at, event, scheme, headers FROM whop_sig_log ORDER BY id DESC LIMIT 10")
                rows = [{"at": r[0].isoformat(), "event": r[1], "scheme": r[2], "headers": r[3]} for r in cur.fetchall()]
                c.commit(); c.close()
            except Exception as e:
                rows = [{"error": str(e)[:200]}]
            self._json(200, {"ok": True, "secret_set": bool(WHOP_SECRET), "enforced": ENFORCE_SIG, "recent": rows})
            return
        self._json(200, {"ok": True, "service": "whop-webhook", "v": "sync-6", "whop_key": bool(WHOP_API_KEY)})

    def _whop_get(self, path):
        conn = http.client.HTTPSConnection("api.whop.com", timeout=15)
        conn.request("GET", path, headers={"Authorization": "Bearer " + WHOP_API_KEY, "Accept": "application/json"})
        res = conn.getresponse()
        body = res.read()
        if res.status >= 300:
            raise RuntimeError("Whop API %s: %s" % (res.status, body[:300].decode("utf-8", "replace")))
        return json.loads(body or b"{}")

    def _email_for(self, p, cache, errs):
        """Payments from API 2026-10-27 carry only member_id / user id: fetch the email."""
        user = p.get("user") if isinstance(p.get("user"), dict) else {}
        tries = []
        if p.get("member_id"):
            tries.append("/api/v1/members/" + str(p["member_id"]))
        if user.get("id"):
            tries.append("/api/v1/users/" + str(user["id"]))
        if p.get("membership_id"):
            tries.append("/api/v1/memberships/" + str(p["membership_id"]))
        for path in tries:
            if path in cache:
                if cache[path]:
                    return cache[path]
                continue
            try:
                got = self._whop_get(path)
                cache[path] = find_email(got)
                if not cache[path]:
                    errs.append(path.split("/")[3] + " no email: " + json.dumps(got)[:300])
            except Exception as e:
                cache[path] = ""
                errs.append(path.split("/")[3] + ": " + str(e)[:160])
            if cache[path]:
                return cache[path]
        return ""

    def _title_for(self, p, cache, errs):
        """Product title for a payment listed without one: payment, then plan, then membership lookups."""
        def title_of(obj):
            obj = obj if isinstance(obj, dict) else {}
            for k in ("product", "access_pass"):
                v = obj.get(k)
                if isinstance(v, dict) and (v.get("title") or v.get("name")):
                    return str(v.get("title") or v.get("name"))
            return ""
        plan = p.get("plan") if isinstance(p.get("plan"), dict) else {}
        memb = p.get("membership") if isinstance(p.get("membership"), dict) else {}
        if plan.get("id") and ("plan:" + plan["id"]) in cache:
            return cache["plan:" + plan["id"]]
        tries = [("/api/v1/payments/" + str(p["id"]), None)] if p.get("id") else []
        if plan.get("id"):
            tries.append(("/api/v1/plans/" + plan["id"], "plan:" + plan["id"]))
        if memb.get("id"):
            tries.append(("/api/v1/memberships/" + memb["id"], None))
        for path, key in tries:
            if key and key in cache:
                return cache[key]
            try:
                t = title_of(self._whop_get(path))
            except Exception as e:
                errs.append(path.split("/")[3] + ": " + str(e)[:160])
                t = ""
            if key:
                cache[key] = t
            if t:
                if plan.get("id"):
                    cache["plan:" + plan["id"]] = t
                return t
        return ""

    def _backfill(self):
        """Admin only: re-run every paid TradeVault payment from the Whop API through _purchase.
        Safe to repeat: GHL tags are added, members upsert, payments are keyed on the Whop payment id."""
        sys.path.insert(0, sys_path)
        from _auth import verify_token
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not verify_token(auth[7:]):
            self._json(401, {"ok": False, "error": "Unauthorized"})
            return
        if not WHOP_API_KEY:
            self._json(500, {"ok": False, "error": "WHOP_API_KEY is not set in Vercel"})
            return
        started = time.time()
        try:
            pays, after, seen, scope, raw, sample, cache, errs = [], "", {}, None, "", "", {}, []
            for _ in range(30):
                q = "first=100" + ("&after=" + after if after else "")
                if scope is None:
                    # A company key may only list its own company's payments: try with and without the filter.
                    for scope in ("account_id=" + WHOP_COMPANY + "&", ""):
                        page = self._whop_get("/api/v1/payments?" + scope + q)
                        if page.get("data"):
                            break
                    raw = json.dumps(page)[:400]
                else:
                    page = self._whop_get("/api/v1/payments?" + scope + q)
                for p in page.get("data") or []:
                    if not sample:
                        sample = json.dumps(p)[:1500]
                    prod = p.get("product") if isinstance(p.get("product"), dict) else {}
                    items = [li for li in (p.get("line_items") or []) if isinstance(li, dict)]
                    title = (str(prod.get("title") or prod.get("name") or "") or
                             next((str(li.get("product_title") or li.get("label") or "") for li in items
                                   if li.get("product_title") or li.get("label")), "")).strip()
                    route = str(prod.get("route") or "")
                    k = "%s | %s" % (title or route or prod.get("id") or "?", p.get("status"))
                    seen[k] = seen.get(k, 0) + 1
                    if "tradevault" not in title.lower().replace(" ", ""):
                        title = TV_ROUTES.get(route, "")
                        if not title:
                            continue
                    p["product"] = dict(prod, title=title)
                    paid = p.get("status") == "paid" or (not p.get("status") and
                                                         (p.get("paid_at") or str(p.get("substatus") or "") == "succeeded"))
                    if paid and p.get("id") and not p.get("refunded_at") and \
                            str(p.get("substatus") or "") not in ("refunded", "auto_refunded"):
                        if not p.get("usd_total"):
                            p["usd_total"] = money(p.get("total")) or money(p.get("subtotal"))
                        pays.append(p)
                info = page.get("page_info") or {}
                after = info.get("end_cursor") or ""
                if not (info.get("has_next_page") and after):
                    break
        except Exception as e:
            self._json(502, {"ok": False, "error": str(e)[:300]})
            return

        # Payments already in tv_payments were handled when they happened; oldest first so the latest tier wins.
        import _tv_aff
        c = _tv_aff.conn(); cur = c.cursor()
        cur.execute("SELECT whop_id FROM tv_payments WHERE whop_id = ANY(%s)", ([str(p["id"]) for p in pays],))
        have = {r[0] for r in cur.fetchall()}
        c.close()
        todo = sorted((p for p in pays if str(p["id"]) not in have), key=lambda p: str(p.get("paid_at") or p.get("created_at") or ""))

        done, failed, no_email = [], [], 0
        for p in todo:
            if time.time() - started > 45:
                break
            try:
                if not find_email(p.get("user")):
                    email = self._email_for(p, cache, errs)
                    if email:
                        p["user"] = dict(p.get("user") if isinstance(p.get("user"), dict) else {}, email=email)
                _, out = self._purchase("payment.succeeded", p)
                if not out.get("email"):
                    no_email += 1
                    continue
                done.append({"email": out["email"], "product": (p.get("product") or {}).get("title"),
                             "paid_at": p.get("paid_at"), "ghl": bool((out.get("ghl") or {}).get("contact"))})
            except Exception as e:
                failed.append({"id": p.get("id"), "error": str(e)[:200]})
        left = len(todo) - len(done) - len(failed) - no_email
        msample = ""
        if not pays:
            for path in ("/api/v1/memberships?account_id=" + WHOP_COMPANY + "&first=2", "/api/v1/memberships?company_id=" + WHOP_COMPANY + "&first=2", "/api/v1/memberships?first=2"):
                try:
                    msample = path.split("?")[1][:12] + " " + json.dumps(self._whop_get(path))[:1200]
                    if '"data": []' not in msample:
                        break
                except Exception as e:
                    msample = path.split("?")[1][:12] + " ERR " + str(e)[:200]
        self._json(200, {"ok": True, "sample": sample, "msample": msample, "lookup_errors": errs[:3], "scope": scope, "raw": "" if seen else raw, "seen": seen, "found": len(pays), "already": len(have), "synced": done,
                         "failed": failed, "no_email": no_email, "remaining": left})

    def _keep(self, event_type, raw_body):
        try:
            sys.path.insert(0, sys_path)
            import _tv_aff
            c = _tv_aff.conn(); cur = c.cursor()
            cur.execute(EVENT_TABLE)
            cur.execute("INSERT INTO whop_events (event, body) VALUES (%s, %s)", (event_type[:60], raw_body.decode("utf-8", "replace")))
            c.commit(); c.close()
        except Exception as e:
            print("event keep failed:", e, file=sys.stderr)

    def _log_sig(self, event_type, scheme):
        try:
            sys.path.insert(0, sys_path)
            import _tv_aff
            c = _tv_aff.conn(); cur = c.cursor()
            cur.execute(SIG_TABLE)
            names = ",".join(sorted(k.lower() for k in self.headers.keys() if "sig" in k.lower() or k.lower().startswith("webhook")))
            cur.execute("INSERT INTO whop_sig_log (event, scheme, headers) VALUES (%s, %s, %s)",
                        (event_type[:60], scheme or "none", names[:300]))
            cur.execute("DELETE FROM whop_sig_log WHERE id < (SELECT MAX(id) - 50 FROM whop_sig_log)")
            c.commit(); c.close()
        except Exception as e:
            print("sig log failed:", e, file=sys.stderr)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)

            sys.path.insert(0, sys_path)
            import _whop_sig
            scheme = _whop_sig.check(dict(self.headers.items()), raw_body, WHOP_SECRET)
            try:
                peek = json.loads(raw_body).get("event", "") or json.loads(raw_body).get("type", "")
            except Exception:
                peek = ""
            self._log_sig(str(peek), scheme)
            if ENFORCE_SIG and not scheme:
                self._json(401, {"error": "invalid signature"})
                return

            event = json.loads(raw_body)
            # Whop v1 webhooks name the event in "type"; older ones used "event".
            event_type = event.get("type") or event.get("event") or ""
            if event_type.startswith(("payment.", "membership.", "member.", "refund.")):
                self._keep(event_type, raw_body)

            # Debug: return full payload so we can inspect it
            print("WHOP EVENT:", event_type, json.dumps(event)[:500], file=sys.stderr)

            if event_type in SLACK_EVENTS:
                self._notify_slack(event_type, event.get("data", {}) or {})

            # A refunded TradeVault payment earns its affiliate nothing.
            if event_type in ("payment.refunded", "refund.created", "refund.updated"):
                d = event.get("data", {}) or {}
                pay = d.get("payment") if isinstance(d.get("payment"), dict) else {}
                pay_id = d.get("payment_id") or pay.get("id") or (d.get("id") if event_type == "payment.refunded" else None)
                if pay_id:
                    sys.path.insert(0, sys_path)
                    import _tv_aff
                    _tv_aff.refund(str(pay_id))

            if event_type not in ("payment.succeeded", "membership.went_valid",
                                   "membership.activated", "member.created"):
                self._json(200, {"ok": True, "skipped": event_type})
                return

            status, out = self._purchase(event_type, event.get("data", {}) or {})
            self._json(status, out)

        except Exception as e:
            self._json(500, {"error": str(e)})

    def _purchase(self, event_type, data):
        """Tag the buyer in GHL and record the purchase (members board + affiliate commission)."""
        # membership.activated nests user under data.user; member.created may use data directly
        user  = data.get("user") or data.get("customer") or {}
        plan  = data.get("plan") or {}
        prod  = data.get("product") or {}
        bill  = data.get("billing_address") or {}
        memb  = data.get("member") or {}
        user, plan, prod, bill, memb = [x if isinstance(x, dict) else {} for x in (user, plan, prod, bill, memb)]

        email = (user.get("email") or memb.get("email") or data.get("email") or data.get("user_email") or "").strip().lower()
        name  = (user.get("name") or bill.get("name") or user.get("username") or
                 user.get("display_name") or "").strip()
        phone = (user.get("phone_number") or memb.get("phone") or data.get("phone") or "").strip()
        slug  = str(plan.get("slug") or plan.get("id") or
                    data.get("plan_id") or data.get("product_slug") or "").strip()
        title = str(prod.get("title") or prod.get("name") or
                    plan.get("title") or plan.get("name") or "").strip()

        if not email:
            # v1 membership events can omit the email; payment.succeeded carries it. 200 so Whop doesn't retry.
            return 200, {"ok": True, "skipped": "no email", "event": event_type}

        parts = name.split(" ", 1)
        first = parts[0] if parts else ""
        last  = parts[1] if len(parts) > 1 else ""
        tags  = purchase_tags(slug, title)
        paid_at = data.get("paid_at") or data.get("created_at") or None
        if isinstance(paid_at, (int, float)):
            import datetime
            paid_at = datetime.datetime.fromtimestamp(paid_at, datetime.timezone.utc).isoformat()

        ghl_result = self._ghl_upsert(email, first, last, phone, tags)
        if "tradevault-purchased" in tags and ghl_result.get("contact"):
            sys.path.insert(0, sys_path)
            import _tv_db
            tier = next((t.split("-", 1)[1] for t in tags if t in ("tradevault-tools", "tradevault-community", "tradevault-elite")), "")
            _tv_db.record_purchase(ghl_result["contact"], email, tier, title, paid_at)
        if "tradevault-purchased" in tags:
            # Every TradeVault payment is logged for the TradeVault affiliate programme.
            amount = None
            for k in ("usd_total", "total", "final_amount", "subtotal", "amount"):
                amount = money(data.get(k))
                if amount:
                    break
            if event_type == "payment.succeeded" and data.get("id") and amount:
                sys.path.insert(0, sys_path)
                import _tv_aff
                tier = next((t.split("-", 1)[1] for t in tags if t in ("tradevault-tools", "tradevault-community", "tradevault-elite")), "")
                _tv_aff.record_payment(str(data["id"]), email, amount, title, tier, paid_at)
        else:
            self._record_affiliate_purchase(email, slug, None)
        return 200, {"ok": True, "email": email, "tags": tags, "ghl": ghl_result}

    def _notify_slack(self, event_type, data):
        """Post a payment line to #payment-confirmations-us30. Never breaks the webhook."""
        if not SLACK_WEBHOOK_PAYMENTS:
            return
        try:
            icon, label = SLACK_EVENTS[event_type]
            user = data.get("user") or data.get("customer") or data.get("member") or {}
            if not isinstance(user, dict):
                user = {}
            plan = data.get("plan") or {}
            prod = data.get("product") or {}
            if not isinstance(plan, dict):
                plan = {}
            if not isinstance(prod, dict):
                prod = {}
            bill  = data.get("billing_address") or {}
            if not isinstance(bill, dict):
                bill = {}
            name  = (user.get("name") or bill.get("name") or user.get("username") or data.get("name") or "").strip()
            email = (user.get("email") or data.get("email") or data.get("user_email") or "").strip()
            slug  = str(plan.get("slug") or plan.get("id") or data.get("plan_id") or "").strip()
            product = (prod.get("title") or prod.get("name") or plan.get("title") or plan.get("name") or slug or "Unknown product")

            amount = None
            for k in ("total", "final_amount", "usd_total", "subtotal", "amount", "amount_after_fees"):
                amount = money(data.get(k))
                if amount is not None:
                    break
            if amount is None:
                amount = PLAN_PRICES.get(slug)
            currency = (data.get("currency") or "usd").upper()
            amt = f"${amount:,.2f} {currency}" if amount is not None else "amount n/a"

            lines = [f"{icon} *{label}: {amt}*",
                     f"*Name:* {name or 'n/a'}",
                     f"*Email:* {email or 'n/a'}",
                     f"*Product:* {product}"]
            pid = data.get("id")
            if pid:
                lines.append(f"*Whop ID:* `{pid}`")
            if event_type == "payment.failed":
                reason = data.get("failure_message") or data.get("failure_reason") or ""
                if reason:
                    lines.append(f"*Reason:* {reason}")

            payload = json.dumps({"text": "\n".join(lines)}).encode()
            conn = http.client.HTTPSConnection("hooks.slack.com", timeout=5)
            conn.request("POST", SLACK_WEBHOOK_PAYMENTS.replace("https://hooks.slack.com", ""),
                         payload, {"Content-Type": "application/json"})
            r = conn.getresponse()
            print("SLACK_PAYMENT:", r.status, file=sys.stderr)
        except Exception as e:
            print("SLACK_PAYMENT_ERR:", e, file=sys.stderr)

    def _ghl_upsert(self, email, first, last, phone, tags):
        """Upsert the contact, then ADD tags (never removes existing ones like pdf-optin)."""
        if not GHL_API_KEY:
            print("GHL_UPSERT: no GHL_API_KEY set", file=sys.stderr)
            return {"error": "no api key"}

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + GHL_API_KEY,
            "Version": "2021-07-28",
        }
        host = "services.leadconnectorhq.com"

        try:
            payload = {"locationId": GHL_LOCATION, "email": email, "source": "Whop purchase"}
            if first:
                payload["firstName"] = first
            if last:
                payload["lastName"] = last
            if phone:
                payload["phone"] = phone

            conn = http.client.HTTPSConnection(host, timeout=10)
            conn.request("POST", "/contacts/upsert", json.dumps(payload), headers)
            res  = conn.getresponse()
            body = res.read()
            print("GHL_UPSERT:", res.status, body[:300], file=sys.stderr)
            cid = ((json.loads(body or b"{}").get("contact") or {}).get("id")) if res.status < 300 else None
            if not cid:
                return {"status": res.status, "body": body.decode()[:300]}

            conn2 = http.client.HTTPSConnection(host, timeout=10)
            conn2.request("POST", "/contacts/" + cid + "/tags", json.dumps({"tags": tags}), headers)
            res2  = conn2.getresponse()
            body2 = res2.read()
            print("GHL_TAGS:", res2.status, body2[:300], file=sys.stderr)
            return {"status": res2.status, "contact": cid}
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
            print("AFF_PURCHASE_ERR:", e, file=sys.stderr)

    def _json(self, status, body):
        payload = json.dumps(body).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(payload)
