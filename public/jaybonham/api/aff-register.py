import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from _aff_db import get_conn, hash_password, generate_code


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self._cors(200)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")

            name     = (body.get("name") or "").strip()
            email    = (body.get("email") or "").strip().lower()
            phone    = (body.get("phone") or "").strip()
            password = (body.get("password") or "").strip()
            code_req = (body.get("code") or "").strip().lower()

            # Validate required fields
            if not name or not email or not password:
                self._json(400, {"error": "name, email and password are required"})
                return
            if len(password) < 8:
                self._json(400, {"error": "password must be at least 8 characters"})
                return
            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
                self._json(400, {"error": "invalid email"})
                return

            # Validate or generate code
            if code_req:
                if not re.match(r"^[a-z0-9_]{3,20}$", code_req):
                    self._json(400, {"error": "code must be 3-20 lowercase letters/numbers/underscores"})
                    return
                code = code_req
            else:
                code = generate_code()

            password_hash, password_salt = hash_password(password)

            conn = get_conn()
            cur  = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO jb_affiliates (name, email, phone, code, password_hash, password_salt)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, code
                """, (name, email, phone or None, code, password_hash, password_salt))
                row = cur.fetchone()
                conn.commit()
                self._json(200, {"ok": True, "id": row[0], "code": row[1]})
            except Exception as e:
                conn.rollback()
                err = str(e)
                if "jb_affiliates_email_key" in err:
                    self._json(409, {"error": "email already registered"})
                elif "jb_affiliates_code_key" in err:
                    # Auto-generate a fresh code and retry once
                    code = generate_code()
                    try:
                        cur.execute("""
                            INSERT INTO jb_affiliates (name, email, phone, code, password_hash, password_salt)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id, code
                        """, (name, email, phone or None, code, password_hash, password_salt))
                        row = cur.fetchone()
                        conn.commit()
                        self._json(200, {"ok": True, "id": row[0], "code": row[1]})
                    except Exception:
                        conn.rollback()
                        self._json(409, {"error": "code already taken, try a different one"})
                else:
                    self._json(500, {"error": "registration failed"})
            finally:
                cur.close()
                conn.close()

        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
