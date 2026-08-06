import json, os, urllib.request, urllib.error
from datetime import datetime, timezone

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_JB_APPLY_LIST_ID = int(os.environ.get("BREVO_JB_APPLY_LIST_ID", "5"))

# Map capital label → USD midpoint for numeric filtering in Brevo
CAPITAL_MAP = {
    "Under $5K":     2500,
    "$5K–$25K":     15000,
    "$25K–$100K":   62500,
    "$100K–$500K": 300000,
    "$500K+":       750000,
}

def handler(request):
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": "",
        }

    if request.method != "POST":
        return {"statusCode": 405, "body": json.dumps({"ok": False, "error": "Method not allowed"})}

    try:
        body = json.loads(request.body)
    except Exception:
        return {"statusCode": 400, "body": json.dumps({"ok": False, "error": "Invalid JSON"})}

    name      = (body.get("name") or "").strip()
    email     = (body.get("email") or "").strip()
    phone     = (body.get("phone") or "").strip()
    exp       = (body.get("experience_level") or "").strip()
    trading   = (body.get("current_trading") or "").strip()
    capital   = (body.get("trading_capital") or "").strip()
    blocker   = (body.get("biggest_blocker") or "").strip()
    goal      = (body.get("goal_12_months") or "").strip()

    if not email or "@" not in email:
        return {"statusCode": 400, "body": json.dumps({"ok": False, "error": "Valid email required"})}

    # Split name into first/last
    parts = name.split(" ", 1)
    first = parts[0]
    last  = parts[1] if len(parts) > 1 else ""

    # Numeric capital
    capital_usd = CAPITAL_MAP.get(capital, 0)

    # Today's date ISO
    app_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build Brevo payload
    contact_payload = {
        "email": email,
        "attributes": {
            "FIRSTNAME":           first,
            "LASTNAME":            last,
            "SMS":                 phone,
            "EXPERIENCE_LEVEL":    exp,
            "CURRENT_TRADING":     trading,
            "TRADING_CAPITAL":     capital,
            "TRADING_CAPITAL_USD": capital_usd,
            "BIGGEST_BLOCKER":     blocker,
            "GOAL_12_MONTHS":      goal,
            "APPLICATION_DATE":    app_date,
        },
        "listIds": [BREVO_JB_APPLY_LIST_ID],
        "updateEnabled": True,
    }

    brevo_url = "https://api.brevo.com/v3/contacts"
    req = urllib.request.Request(
        brevo_url,
        data=json.dumps(contact_payload).encode("utf-8"),
        headers={
            "api-key":      BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept":       "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode("utf-8")
            print(f"[jb-apply] Brevo OK: {resp.status} {resp_body[:200]}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[jb-apply] Brevo error {e.code}: {err_body}")
        # 204 / duplicate contact is fine; don't fail the user
        if e.code not in (204, 400):
            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
                "body": json.dumps({"ok": False, "error": "Could not save application. Please try again."}),
            }
    except Exception as ex:
        print(f"[jb-apply] Request failed: {ex}")
        return {
            "statusCode": 200,
            "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
            "body": json.dumps({"ok": False, "error": "Something went wrong. Please try again."}),
        }

    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json",
        },
        "body": json.dumps({"ok": True}),
    }
