"""
Meta Conversions API — server-side Lead event
Called by GHL automation webhook on form submission.

GHL webhook body (JSON):
  { "email": "...", "phone": "...", "name": "...", "fn": "...", "ln": "..." }

Required env var:
  META_CAPI_TOKEN   — Meta CAPI access token from Events Manager
"""
import json, hashlib, time, os, re
from http.server import BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError

PIXEL_ID    = '3566618163494760'
CAPI_TOKEN  = os.environ.get('META_CAPI_TOKEN', '')
CAPI_URL    = f'https://graph.facebook.com/v19.0/{PIXEL_ID}/events'
PAGE_URL    = 'https://jaybonham.com/free-download'


def sha256(value: str) -> str:
    """Lowercase, strip, then SHA-256 hash a PII string (Meta requirement)."""
    return hashlib.sha256(value.lower().strip().encode()).hexdigest()


def normalise_phone(phone: str) -> str:
    """Strip everything except digits; add country code if missing."""
    digits = re.sub(r'\D', '', phone)
    if digits and not digits.startswith('1') and len(digits) == 10:
        digits = '1' + digits
    return digits


class handler(BaseHTTPRequestHandler):

    def _json(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(payload))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if not CAPI_TOKEN:
            self._json(500, {'ok': False, 'error': 'META_CAPI_TOKEN not set'})
            return

        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length)) if length else {}
        except Exception:
            self._json(400, {'ok': False, 'error': 'invalid JSON'})
            return

        # ── build user_data with whatever PII GHL sends ──────────────────
        user_data = {}

        email = (body.get('email') or body.get('Email') or '').strip()
        if email:
            user_data['em'] = [sha256(email)]

        phone = (body.get('phone') or body.get('Phone') or '').strip()
        if phone:
            norm = normalise_phone(phone)
            if norm:
                user_data['ph'] = [sha256(norm)]

        fn = (body.get('fn') or body.get('firstName') or body.get('first_name') or '').strip()
        ln = (body.get('ln') or body.get('lastName')  or body.get('last_name')  or '').strip()
        if not fn and not ln:
            # try splitting the 'name' field
            full = (body.get('name') or body.get('Name') or '').strip().split()
            if full:
                fn = full[0]
                ln = full[-1] if len(full) > 1 else ''
        if fn:
            user_data['fn'] = [sha256(fn)]
        if ln:
            user_data['ln'] = [sha256(ln)]

        if not user_data:
            self._json(400, {'ok': False, 'error': 'no usable PII fields'})
            return

        # ── event payload ─────────────────────────────────────────────────
        event = {
            'event_name':        'Lead',
            'event_time':        int(time.time()),
            'action_source':     'website',
            'event_source_url':  PAGE_URL,
            'user_data':         user_data,
        }

        # pass event_id from GHL if present (helps dedup against pixel)
        event_id = body.get('event_id') or body.get('eventId') or ''
        if event_id:
            event['event_id'] = str(event_id)

        capi_payload = json.dumps({
            'data':         [event],
            'access_token': CAPI_TOKEN,
        }).encode()

        # ── POST to Meta ──────────────────────────────────────────────────
        try:
            req  = Request(CAPI_URL, data=capi_payload,
                           headers={'Content-Type': 'application/json'}, method='POST')
            resp = urlopen(req, timeout=8)
            meta_body = json.loads(resp.read())
            self._json(200, {'ok': True, 'meta': meta_body})

        except HTTPError as e:
            err_body = e.read().decode()
            print(f'[meta-capi] Meta error {e.code}: {err_body}')
            self._json(502, {'ok': False, 'meta_error': err_body})

        except Exception as e:
            print(f'[meta-capi] unexpected error: {e}')
            self._json(500, {'ok': False, 'error': str(e)})

    def log_message(self, *_):
        pass
