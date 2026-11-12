"""Sniper Academy admin: every Sniper member and each one's full profile, for Jay and the team
(signed in at jaybonham.com/academy with an admin email). Used by jb-academy.py.

Sources: Whop (memberships, the members' emails), GHL (the Trader Profile Form and Killshot
Application answers, contact, tags, custom fields), Brevo (older jaybonham.com/apply answers) and our own academy tables (progress, comments)."""
import http.client
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(__file__))
import _jb_academy as J
import _tv_aff as A
import _tv_whop as W

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
OK_STATUS = {"active", "trialing", "past_due", "completed"}
LIST_CACHE = 120
APPLY_FIELDS = (("EXPERIENCE_LEVEL", "Experience"), ("CURRENT_TRADING", "Trading now"), ("TRADING_CAPITAL", "Trading capital"),
                ("BIGGEST_BLOCKER", "Biggest blocker"), ("GOAL_12_MONTHS", "12-month goal"), ("APPLICATION_DATE", "Applied"),
                ("PIPELINE_STAGE", "Application stage"))

_list = {"at": 0, "data": None}
_wprog = {"at": 0, "data": None}
COURSE = "cors_ubqXl5GzVJpMN"


def whop_progress(fresh=False):
    """Lessons each Whop user has completed in the Sniper Academy course on Whop itself:
    {user id: {"done": set of lesson ids, "last": iso of their latest lesson}}."""
    if _wprog["data"] is not None and not fresh and time.time() - _wprog["at"] < LIST_CACHE:
        return _wprog["data"]
    out, after = {}, ""
    for _ in range(60):
        page = W.whop("GET", "/api/v1/course_lesson_interactions?course_id=%s&first=100%s" % (COURSE, "&after=" + after if after else ""))
        for i in page.get("data") or []:
            u = i.get("user") if isinstance(i.get("user"), dict) else {}
            l = i.get("lesson") if isinstance(i.get("lesson"), dict) else {}
            if not (u.get("id") and l.get("id")):
                continue
            rec = out.setdefault(u["id"], {"done": set(), "last": None})
            if i.get("completed"):
                rec["done"].add(l["id"])
            at = i.get("updated_at") or i.get("created_at")
            if at and (not rec["last"] or str(at) > rec["last"]):
                rec["last"] = str(at)
        info = page.get("page_info") or {}
        after = info.get("end_cursor") or ""
        if not (info.get("has_next_page") and after):
            break
    try:  # Whop's own "last active" per student also counts rewatching, which adds no new completion
        after = ""
        for _ in range(20):
            page = W.whop("GET", "/api/v1/course_students?course_id=%s&first=100%s" % (COURSE, "&after=" + after if after else ""))
            for st in page.get("data") or []:
                u = st.get("user") if isinstance(st.get("user"), dict) else {}
                at = st.get("last_interaction_at")
                if u.get("id") and at:
                    rec = out.setdefault(u["id"], {"done": set(), "last": None})
                    rec["last"] = max(filter(None, [rec["last"], str(at)]))
            info = page.get("page_info") or {}
            after = info.get("end_cursor") or ""
            if not (info.get("has_next_page") and after):
                break
    except Exception as e:
        log("JB_ADMIN_STUDENTS_ERR", e)
    _wprog.update(at=time.time(), data=out)
    return out


def uid(m):
    u = m.get("user") if isinstance(m.get("user"), dict) else {}
    return u.get("id") or m.get("user_id")


def whop_done(uids):
    """(completed lesson ids, latest Whop activity) across a member's Whop user ids."""
    try:
        wp = whop_progress()
    except Exception as e:
        log("JB_ADMIN_WHOP_PROGRESS_ERR", e)
        return set(), None
    done, last = set(), None
    for u in uids:
        r = wp.get(u)
        if r:
            done |= r["done"]
            last = max(filter(None, [last, r["last"]]), default=None)
    return done, last
_member_emails = {}   # Whop member id -> (email, name, username)
_products = {}        # product id -> title (lowercase)
_fields = {"at": 0, "map": {}, "err": None}


def log(*a):
    print(*a, file=sys.stderr)


def _pid(m):
    p = m.get("product") if isinstance(m.get("product"), dict) else {}
    pid = p.get("id") or m.get("product_id")
    if p.get("title") and pid:
        _products[pid] = " ".join(p["title"].lower().split())
    return pid


def _ptitle(pid):
    if pid and pid not in _products:
        try:
            _products[pid] = " ".join(str(W.whop("GET", "/api/v1/products/" + pid).get("title") or "").lower().split())
        except Exception as e:
            log("JB_ADMIN_PRODUCT_ERR", pid, e)
            _products[pid] = ""
    return _products.get(pid, "")


def _money(v):
    if isinstance(v, dict):
        v = v.get("amount")
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _nice(title):
    return " ".join(w.capitalize() for w in (title or "").split())


def _mid(m):
    mb = m.get("member") if isinstance(m.get("member"), dict) else {}
    return mb.get("id") or m.get("member_id")


def _who(m):
    """(email, name, username) for a membership: from the membership when Whop includes it, else the member."""
    u = m.get("user") if isinstance(m.get("user"), dict) else {}
    mb = m.get("member") if isinstance(m.get("member"), dict) else {}
    email = (u.get("email") or mb.get("email") or m.get("email") or "").strip().lower()
    name, username = (u.get("name") or mb.get("name") or "").strip(), (u.get("username") or mb.get("username") or "").strip()
    mid = _mid(m)
    if not email and mid:
        if mid not in _member_emails:
            try:
                d = W.whop("GET", "/api/v1/members/" + mid)
                du = d.get("user") if isinstance(d.get("user"), dict) else {}
                _member_emails[mid] = ((d.get("email") or du.get("email") or "").strip().lower(),
                                       (d.get("name") or du.get("name") or "").strip(), (d.get("username") or du.get("username") or "").strip())
            except Exception as e:
                log("JB_ADMIN_MEMBER_ERR", mid, e)
                _member_emails[mid] = ("", "", "")
        email, n2, u2 = _member_emails[mid]
        name, username = name or n2, username or u2
    return email, name, username


def _ts(m, *keys):
    for k in keys:
        if m.get(k):
            return m[k]
    return None


def sniper_memberships():
    """Every membership on a Sniper Fast Start / Accelerator / Elite product."""
    out, after = [], ""
    for _ in range(30):
        page = W.whop("GET", "/api/v1/memberships?account_id=%s&first=100%s" % (W.WHOP_COMPANY, "&after=" + after if after else ""))
        for m in page.get("data") or []:
            if J.is_course_product(_ptitle(_pid(m))):
                out.append(m)
        info = page.get("page_info") or {}
        after = info.get("end_cursor") or ""
        if not (info.get("has_next_page") and after):
            break
    return out


def members(cur, fresh=False):
    if _list["data"] is not None and not fresh and time.time() - _list["at"] < LIST_CACHE:
        rows = _list["data"]
    else:
        ms = sniper_memberships()
        with ThreadPoolExecutor(8) as ex:
            who = list(ex.map(_who, ms))
        people = {}
        for m, (email, name, username) in zip(ms, who):
            if not email:
                continue
            p = people.setdefault(email, {"email": email, "name": name, "username": username, "plans": [], "active": False,
                                          "joined": None, "memberships": 0, "uids": []})
            if uid(m) and uid(m) not in p["uids"]:
                p["uids"].append(uid(m))
            p["name"] = p["name"] or name
            p["username"] = p["username"] or username
            status = str(m.get("status") or "")
            live = status in OK_STATUS
            p["plans"].append({"plan": _nice(_ptitle(_pid(m))), "status": status, "live": live})
            p["active"] = p["active"] or live
            joined = _ts(m, "created_at", "joined_at")
            if joined and (not p["joined"] or str(joined) < str(p["joined"])):
                p["joined"] = joined
            p["memberships"] += 1
            p["paid"] = round(p.get("paid", 0) + _money(m.get("initial_price")), 2)
        rows = list(people.values())
        _list.update(at=time.time(), data=rows)
    emails = [r["email"] for r in rows]
    prog, comm = {}, {}
    if emails:
        cur.execute("""SELECT email, array_agg(lesson_id) FILTER (WHERE done), max(updated_at) FROM jb_academy_progress
                       WHERE email = ANY(%s) GROUP BY email""", (emails,))
        prog = {r[0]: (set(r[1] or []), r[2]) for r in cur.fetchall()}
        cur.execute("SELECT email, count(*) FROM jb_academy_comments WHERE deleted_at IS NULL AND email = ANY(%s) GROUP BY email", (emails,))
        comm = dict(cur.fetchall())
    out = []
    for r in rows:
        ours, seen = prog.get(r["email"], (set(), None))
        wdone, wlast = whop_done(r["uids"])
        last = max(filter(None, [seen.isoformat() if seen else None, wlast]), default=None)
        out.append(dict(r, done=len(ours | wdone), last_active=last, whop_last=wlast, comments=comm.get(r["email"], 0)))
    out.sort(key=lambda r: (not r["active"], str(r["joined"] or "")), reverse=False)
    out.sort(key=lambda r: str(r["joined"] or ""), reverse=True)
    out.sort(key=lambda r: not r["active"])
    return out


# ---------- one member ----------

def _brevo(email):
    if not BREVO_API_KEY:
        return {}
    try:
        c = http.client.HTTPSConnection("api.brevo.com", timeout=6)
        c.request("GET", "/v3/contacts/" + quote(email, safe=""), headers={"accept": "application/json", "api-key": BREVO_API_KEY})
        r = c.getresponse()
        d = json.loads(r.read() or b"{}")
        c.close()
        return d.get("attributes") or {} if r.status < 300 else {}
    except Exception as e:
        log("JB_ADMIN_BREVO_ERR", e)
        return {}


def _field_names():
    if time.time() - _fields["at"] > 600:
        try:
            status, d = A._ghl("GET", "/locations/%s/customFields?model=contact" % A.GHL_LOCATION)
            if status < 300:
                _fields["map"] = {f.get("id"): f.get("name") for f in d.get("customFields") or []}
                _fields["at"] = time.time()
                _fields["err"] = None
            else:
                _fields["err"] = status
        except Exception as e:
            log("JB_ADMIN_FIELDS_ERR", e)
    return _fields["map"]


SKIP_FIELDS = ("link", "tv_sale", "tv sale", "commission")


def _ghl(email):
    try:
        cid = A._ghl_contact(email)
        if not cid:
            return {}
        status, d = A._ghl("GET", "/contacts/" + cid)
        c = d.get("contact") or {}
        names = _field_names()
        fields = []
        for f in c.get("customFields") or c.get("customField") or []:
            v = f.get("value") if "value" in f else f.get("field_value")
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v)
            n = names.get(f.get("id")) or f.get("key") or ""
            if v in (None, "") or not n or any(s in n.lower() for s in SKIP_FIELDS):
                continue
            fields.append({"name": n, "value": str(v)[:500]})
        return {"id": cid, "url": "https://app.gohighlevel.com/v2/location/%s/contacts/detail/%s" % (A.GHL_LOCATION, cid),
                "name": " ".join(filter(None, [c.get("firstName"), c.get("lastName")])) or c.get("contactName") or "",
                "phone": c.get("phone") or "", "country": c.get("country") or "", "timezone": c.get("timezone") or "",
                "added": c.get("dateAdded"), "source": c.get("source") or "", "tags": c.get("tags") or [], "fields": fields}
    except Exception as e:
        log("JB_ADMIN_GHL_ERR", e)
        return {}


_forms = {"at": 0, "list": [], "err": None}
FORM_WORDS = ("trader profile", "application")  # Trader Profile Form, Killshot Application (+ Direct)
META_KEYS = {"formid", "location_id", "locationid", "contactid", "contact_id", "eventdata", "sessionid", "session_id", "fingerprint",
             "submissionid", "signatureHash".lower(), "timezone", "terms_and_conditions", "ip", "pageurl", "page_url",
             "url", "referrer", "spam", "full_name", "first_name", "last_name", "email", "phone", "name", "fieldsoriseverywhere",
             "documenturl", "fieldsorder", "browser"}


def _form_list():
    if time.time() - _forms["at"] > 600:
        try:
            status, d = A._ghl("GET", "/forms/?locationId=%s&limit=50" % A.GHL_LOCATION)
            if status < 300:
                _forms["list"] = [f for f in d.get("forms") or [] if any(w in (f.get("name") or "").lower() for w in FORM_WORDS)]
                _forms["at"] = time.time()
                _forms["err"] = None
            else:
                _forms["err"] = status
                log("JB_ADMIN_FORMS", status, str(d)[:200])
        except Exception as e:
            log("JB_ADMIN_FORMS_ERR", e)
    return _forms["list"]


def _junk_key(k):
    """GHL's own bookkeeping that rides along in a submission (e.g. fieldsOriSequance: the field-id order)."""
    k = (k or "").lower().replace("_", "").replace(" ", "")
    return k in {x.replace("_", "") for x in META_KEYS} or any(w in k for w in ("sequance", "sequence", "fieldsori", "captcha", "signature", "utm", "adsource", "campaign", "medium"))


def _label(label, val):
    """Readable question labels: GHL names unlabelled fields like "checkbox 2msq"."""
    import re
    if re.match(r"^(checkbox|radio|single[ _]?line|multi[ _]?line|dropdown|text|field)[ _]?[a-z0-9]{0,6}$", label.strip().lower()):
        return "Trading capital" if "$" in val else "Other answer"
    return label


def _answer(v):
    if isinstance(v, list):
        return ", ".join(_answer(x) for x in v if x not in (None, ""))
    if isinstance(v, dict):
        return v.get("url") or v.get("value") or v.get("name") or ""
    return str(v).strip()


def forms(email):
    """The member's latest answers to the Trader Profile Form and the Killshot applications, labelled."""
    names = _field_names()
    out = []
    for f in _form_list():
        try:
            status, d = A._ghl("GET", "/forms/submissions?locationId=%s&formId=%s&q=%s&limit=10" % (A.GHL_LOCATION, f["id"], quote(email)))
            if status >= 300:
                log("JB_ADMIN_SUBS", status, str(d)[:200])
                continue
            subs = [x for x in d.get("submissions") or [] if (x.get("email") or "").strip().lower() == email]
            if not subs:
                continue
            sub = sorted(subs, key=lambda x: str(x.get("createdAt") or ""))[-1]
            others = sub.get("others") or {}
            answers = []
            for k, v in others.items():
                label = names.get(k) or k
                val = _answer(v)
                if not val or _junk_key(k) or _junk_key(label) or len(k) > 60 and k not in names:
                    continue
                label = label.replace("_", " ").strip().capitalize() if label == k else label
                answers.append({"name": _label(label, val), "value": val[:1500]})
            if answers:
                out.append({"form": f.get("name") or "Form", "at": sub.get("createdAt"), "answers": answers})
        except Exception as e:
            log("JB_ADMIN_FORM_ERR", f.get("name"), e)
    out.sort(key=lambda x: 0 if "trader profile" in x["form"].lower() else 1)
    return out


def profile(cur, email, course):
    import _tv_upgrade as U
    with ThreadPoolExecutor(4) as ex:
        f_whop = ex.submit(U.memberships, cur, email)
        f_brevo = ex.submit(_brevo, email)
        f_ghl = ex.submit(_ghl, email)
        f_forms = ex.submit(forms, email)
        ms, app, ghl, profile_forms = f_whop.result(), f_brevo.result(), f_ghl.result(), f_forms.result()
    name = username = ""
    plans = []
    for m in ms:
        e, n, u = _who(m)
        name, username = name or n, username or u
        title = _ptitle(_pid(m))
        plans.append({"plan": _nice(title) or "Unknown product", "status": str(m.get("status") or ""),
                      "sniper": J.is_course_product(title), "joined": _ts(m, "created_at", "joined_at"),
                      "renews": _ts(m, "renewal_period_end", "current_period_end", "expires_at"),
                      "cancelling": bool(m.get("cancel_at_period_end")), "paid": _money(m.get("initial_price")),
                      "monthly": _money(m.get("renewal_price"))})
    plans.sort(key=lambda p: str(p["joined"] or ""), reverse=True)
    application = [{"name": label, "value": str(app.get(k))} for k, label in APPLY_FIELDS if app.get(k) not in (None, "", 0)]
    # The contact's custom fields mostly repeat the form answers: keep only what the forms don't already show.
    seen = {" ".join(a["value"].lower().split()) for f in profile_forms for a in f["answers"]}
    if ghl:
        ghl = dict(ghl, fields=[dict(f, name=_label(f["name"], f["value"])) for f in ghl.get("fields") or []
                                if " ".join(f["value"].lower().split()) not in seen and not _junk_key(f["name"])])
        ghl.pop("tags", None)
    cur.execute("SELECT lesson_id, pos, done, updated_at FROM jb_academy_progress WHERE email = %s ORDER BY updated_at DESC", (email,))
    prog = {r[0]: {"pos": r[1], "done": r[2], "at": r[3].isoformat()} for r in cur.fetchall()}
    wdone, wlast = whop_done({uid(m) for m in ms if uid(m)})
    for lid in wdone:  # finished on Whop counts as finished here
        prog.setdefault(lid, {"pos": 0, "done": True, "at": None})["done"] = True
    titles = {l["id"]: l["title"] for ch in course["chapters"] for l in ch["lessons"]}
    modules = [{"title": ch["title"], "total": len(ch["lessons"]),
                "done": sum(1 for l in ch["lessons"] if (prog.get(l["id"]) or {}).get("done"))} for ch in course["chapters"]]
    recent = [{"id": lid, "title": titles.get(lid, lid), "done": p["done"], "at": p["at"]} for lid, p in prog.items() if lid in titles and p["at"]][:6]
    cur.execute("""SELECT id, lesson_id, body, created_at FROM jb_academy_comments WHERE email = %s AND deleted_at IS NULL
                   ORDER BY created_at DESC LIMIT 30""", (email,))
    comments = [{"id": r[0], "lesson": r[1], "title": titles.get(r[1], ""), "body": r[2], "at": r[3].isoformat()} for r in cur.fetchall()]
    total = sum(m["total"] for m in modules)
    done = sum(m["done"] for m in modules)
    return {"email": email, "name": name or ghl.get("name") or "", "username": username,
            "missing_access": [x for x, e in (("forms", _forms["err"]), ("custom fields", _fields["err"])) if e in (401, 403)],
            "access": any(p["sniper"] and p["status"] in OK_STATUS for p in plans),
            "plans": plans, "forms": profile_forms, "application": application, "ghl": ghl,
            "progress": {"done": done, "total": total, "modules": modules, "recent": recent,
                         "last_active": max(filter(None, [recent[0]["at"] if recent else None, wlast]), default=None),
                         "whop_last": wlast, "whop_done": len(wdone)},
            "comments": comments}


def all_comments(cur):
    cur.execute("""SELECT c.id, c.lesson_id, c.email, c.parent_id, c.author, c.role, c.body, c.created_at
                   FROM jb_academy_comments c WHERE c.deleted_at IS NULL ORDER BY c.created_at DESC LIMIT 500""")
    return [{"id": r[0], "lesson": r[1], "email": r[2], "parent": r[3], "author": r[4], "role": r[5], "body": r[6],
             "at": r[7].isoformat()} for r in cur.fetchall()]
