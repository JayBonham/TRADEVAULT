"""TradeVault project board + Alex's pay tracker for the admin (thetradevault.co/admin/projects).

Locked twice, like analytics: an admin token (Authorization: Bearer) and the analytics password
(X-Analytics-Pass). Route: /api/tv-pm?action=<action>

  all           GET     -> {tasks, payments, settings}
  task          POST    {id?, title, notes, kind: todo|idea, importance: 1..4, who: jay|alex|both, due?, done}
  task_delete   POST    {id}
  pay           POST    {id?, paid_on: YYYY-MM-DD, amount, credited, note}
  pay_delete    POST    {id}
  settings      POST    {amount, every_days, next_due: YYYY-MM-DD, caught_up_on: YYYY-MM-DD}
"""
import datetime
import hashlib
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
from _auth import verify_token

DATABASE_URL = os.environ.get("DATABASE_URL", "")
# Same second lock as analytics (salted hash only; env TV_ANALYTICS_PASSWORD replaces it when set).
PASS_SALT = "1cd0c4abafd232acb8a6124e4e3ba085"
PASS_HASH = "a784bb07a38b075cb9d8d316dcf961c49448e6d3c3bc4686703477a07d31f129"

DEFAULTS = {"amount": 2500, "every_days": 14, "next_due": "2026-11-29", "caught_up_on": "2026-11-16"}
# Binance USDT deposits from Jay, received net of a few dollars of fees. credited = what it counts as.
SEED = [("2026-03-31", 5000, 5000), ("2026-05-28", 2500, 2500), ("2026-06-22", 2498.5, 2500),
        ("2026-08-05", 2498.01, 2500), ("2026-08-10", 2498.01, 2500), ("2026-09-08", 4421.43, 4421.43),
        ("2026-09-12", 2498.01, 2500), ("2026-09-24", 2498.01, 2500), ("2026-09-30", 1253.15, 1253.15),
        ("2026-10-19", 2498.01, 2500), ("2026-10-31", 2498.01, 2500), ("2026-11-16", 4998.01, 5000)]

_ready = False


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def pass_ok(given):
    given = (given or "").strip()
    env = os.environ.get("TV_ANALYTICS_PASSWORD", "")
    if env:
        return hmac.compare_digest(given.encode(), env.encode())
    h = hashlib.pbkdf2_hmac("sha256", given.encode(), bytes.fromhex(PASS_SALT), 300000).hex()
    return hmac.compare_digest(h, PASS_HASH)


def conn():
    global _ready
    import psycopg2
    c = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    if not _ready:
        cur = c.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tv_pm_tasks (
                id          BIGSERIAL PRIMARY KEY,
                title       TEXT NOT NULL,
                notes       TEXT NOT NULL DEFAULT '',
                kind        TEXT NOT NULL DEFAULT 'todo',
                importance  SMALLINT NOT NULL DEFAULT 2,
                who         TEXT NOT NULL DEFAULT 'alex',
                due         DATE,
                done_at     TIMESTAMPTZ,
                created_by  TEXT NOT NULL DEFAULT '',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS tv_pay_payments (
                id          BIGSERIAL PRIMARY KEY,
                paid_on     DATE NOT NULL,
                amount      NUMERIC(12,2) NOT NULL,
                credited    NUMERIC(12,2) NOT NULL,
                note        TEXT NOT NULL DEFAULT '',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS tv_pay_settings (
                k TEXT PRIMARY KEY,
                v JSONB NOT NULL
            );
        """)
        cur.execute("SELECT 1 FROM tv_pay_settings WHERE k = 'schedule'")
        if not cur.fetchone():
            cur.execute("INSERT INTO tv_pay_settings (k, v) VALUES ('schedule', %s) ON CONFLICT DO NOTHING", (json.dumps(DEFAULTS),))
            cur.execute("SELECT COUNT(*) FROM tv_pay_payments")
            if not cur.fetchone()[0]:
                for d, a, cr in SEED:
                    cur.execute("INSERT INTO tv_pay_payments (paid_on, amount, credited, note) VALUES (%s, %s, %s, 'Binance USDT')", (d, a, cr))
        c.commit()
        _ready = True
    return c


def _date(v, required=False):
    v = (v or "").strip() if isinstance(v, str) else ""
    if not v:
        if required:
            raise ValueError("date required")
        return None
    return datetime.date.fromisoformat(v[:10]).isoformat()


def _money(v):
    x = round(float(v), 2)
    if not (0 <= x <= 1_000_000):
        raise ValueError("bad amount")
    return x


class handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self._json(204, None)

    def _ok(self):
        auth = self.headers.get("Authorization", "")
        user = verify_token(auth[7:]) if auth.startswith("Bearer ") else None
        if not user:
            self._json(401, {"ok": False, "error": "Unauthorized"})
            return None
        if not pass_ok(self.headers.get("X-Analytics-Pass")):
            self._json(403, {"ok": False, "locked": True, "error": "Wrong password"})
            return None
        if not DATABASE_URL:
            self._json(500, {"ok": False, "error": "DATABASE_URL is not set"})
            return None
        return user

    def _action(self):
        return (parse_qs(urlparse(self.path).query).get("action") or [""])[0]

    def do_GET(self):
        if not self._ok():
            return
        if self._action() == "check":
            return self._json(200, {"ok": True})
        try:
            c = conn()
            body = self._all(c.cursor())
            c.close()
            self._json(200, body)
        except Exception as e:
            log("TV_PM_ERR:", e)
            self._json(500, {"ok": False, "error": "Could not load the board."})

    def _all(self, cur):
        cur.execute("""SELECT id, title, notes, kind, importance, who, due, done_at, created_by, created_at
                         FROM tv_pm_tasks ORDER BY created_at""")
        tasks = [{"id": r[0], "title": r[1], "notes": r[2], "kind": r[3], "importance": r[4], "who": r[5],
                  "due": r[6].isoformat() if r[6] else None, "done_at": r[7].isoformat() if r[7] else None,
                  "by": r[8], "at": r[9].isoformat()} for r in cur.fetchall()]
        cur.execute("SELECT id, paid_on, amount, credited, note FROM tv_pay_payments ORDER BY paid_on DESC, id DESC")
        pays = [{"id": r[0], "paid_on": r[1].isoformat(), "amount": float(r[2]), "credited": float(r[3]), "note": r[4]}
                for r in cur.fetchall()]
        cur.execute("SELECT v FROM tv_pay_settings WHERE k = 'schedule'")
        row = cur.fetchone()
        st = dict(DEFAULTS, **(row[0] if row else {}))
        return {"ok": True, "tasks": tasks, "payments": pays, "settings": st}

    def do_POST(self):
        user = self._ok()
        if not user:
            return
        a = self._action()
        try:
            b = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)) or b"{}")
        except Exception:
            return self._json(400, {"ok": False, "error": "Invalid JSON"})
        try:
            c = conn()
            cur = c.cursor()
            if a == "task":
                title = str(b.get("title") or "").strip()[:300]
                if not title:
                    return self._json(400, {"ok": False, "error": "Give it a title."})
                kind = "idea" if b.get("kind") == "idea" else "todo"
                imp = max(1, min(4, int(b.get("importance") or 2)))
                who = b.get("who") if b.get("who") in ("jay", "alex", "both") else "alex"
                notes = str(b.get("notes") or "")[:4000]
                due = _date(b.get("due"))
                done = bool(b.get("done"))
                if b.get("id"):
                    cur.execute("""UPDATE tv_pm_tasks SET title=%s, notes=%s, kind=%s, importance=%s, who=%s, due=%s,
                                   done_at = CASE WHEN %s THEN COALESCE(done_at, NOW()) ELSE NULL END, updated_at=NOW()
                                   WHERE id=%s""", (title, notes, kind, imp, who, due, done, int(b["id"])))
                else:
                    cur.execute("""INSERT INTO tv_pm_tasks (title, notes, kind, importance, who, due, done_at, created_by)
                                   VALUES (%s,%s,%s,%s,%s,%s, CASE WHEN %s THEN NOW() END, %s)""",
                                (title, notes, kind, imp, who, due, done, str(user)[:60]))
            elif a == "task_delete":
                cur.execute("DELETE FROM tv_pm_tasks WHERE id=%s", (int(b.get("id") or 0),))
            elif a == "pay":
                paid_on = _date(b.get("paid_on"), True)
                amount = _money(b.get("amount"))
                credited = _money(b.get("credited") if b.get("credited") not in (None, "") else amount)
                note = str(b.get("note") or "")[:300]
                if b.get("id"):
                    cur.execute("UPDATE tv_pay_payments SET paid_on=%s, amount=%s, credited=%s, note=%s WHERE id=%s",
                                (paid_on, amount, credited, note, int(b["id"])))
                else:
                    cur.execute("INSERT INTO tv_pay_payments (paid_on, amount, credited, note) VALUES (%s,%s,%s,%s)",
                                (paid_on, amount, credited, note))
            elif a == "pay_delete":
                cur.execute("DELETE FROM tv_pay_payments WHERE id=%s", (int(b.get("id") or 0),))
            elif a == "settings":
                st = {"amount": _money(b.get("amount")), "every_days": max(1, min(62, int(b.get("every_days") or 14))),
                      "next_due": _date(b.get("next_due"), True), "caught_up_on": _date(b.get("caught_up_on"), True)}
                cur.execute("""INSERT INTO tv_pay_settings (k, v) VALUES ('schedule', %s)
                               ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v""", (json.dumps(st),))
            else:
                c.close()
                return self._json(404, {"ok": False, "error": "unknown action"})
            c.commit()
            body = self._all(cur)
            c.close()
            self._json(200, body)
        except (ValueError, TypeError) as e:
            self._json(400, {"ok": False, "error": "Check the dates and amounts (" + str(e)[:80] + ")."})
        except Exception as e:
            log("TV_PM_ERR:", a, e)
            self._json(500, {"ok": False, "error": "Couldn't save that. Try again."})

    def _json(self, status, body):
        raw = json.dumps(body, separators=(",", ":")).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Analytics-Pass")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)
