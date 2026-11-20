"""Whop memberships still in their 7-day free trial.

During the trial a member gets live sessions, Academies and the community Telegram group; scanners,
signals and the educator/scanner groups unlock after the first payment (Whop status trialing -> active).
Used by tv-members (board) and tv-setup (setup page).
"""
import sys


def log(*a):
    print(*a, file=sys.stderr)


_trials = {"at": 0, "data": {}}


def trials_by_email():
    """{email: {"ends": iso, "cancelling": bool}} for every Whop membership still in its free trial.
    One list call (cached for 2 minutes); emails come from the membership, else its member record."""
    import time
    if time.time() - _trials["at"] < 120:
        return _trials["data"]
    out = {}
    try:
        import _tv_whop as W
        import _jb_admin
        after = ""
        for _ in range(5):
            page = W.whop("GET", "/api/v1/memberships?account_id=%s&statuses=trialing&first=100%s"
                          % (W.WHOP_COMPANY, "&after=" + after if after else ""))
            for m in page.get("data") or []:
                if str(m.get("status") or "") != "trialing":
                    continue
                email = _jb_admin._who(m)[0]
                if email:
                    out[email] = {"ends": m.get("renewal_period_end") or m.get("current_period_end") or "",
                                  "cancelling": bool(m.get("cancel_at_period_end"))}
            info = page.get("page_info") or {}
            after = info.get("end_cursor") or ""
            if not (info.get("has_next_page") and after):
                break
        _trials.update(at=time.time(), data=out)
    except Exception as e:
        log("TV_MEMBERS_TRIALS_ERR:", e)
        return _trials["data"]
    return out



def trial_for(email):
    """{"ends", "cancelling"} if this email has a membership in its free trial, else None."""
    return trials_by_email().get((email or "").strip().lower())
