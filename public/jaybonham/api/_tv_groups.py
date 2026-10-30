"""TradeVault Telegram groups, shared by tv-setup (links for the member) and tv-members (board)."""

EDUCATORS = ("jay", "tyler", "andrew", "adam")

# Telegram groups (join requests are approved by admins, so a shared link can't let non-members in)
GROUPS = {
    "community": ("Trade Vault Community", "https://t.me/+b0C6zFxaasUxOTgx"),
    "jay": ("US30 Sniper · Killshot", "https://t.me/+6Hv6dR_h0bk1OGNh"),
    "tyler": ("Tyco · Smartshot", "https://t.me/+sMhy2Ta_22I0MjRh"),
    "andrew": ("Andrew · Spectrum", "https://t.me/+4mi43xBr37NjZjk5"),
    "adam": ("Adam · Poland", "https://t.me/+sNS6FEE6AANmNmRh"),
}


def groups_for(tier, educator):
    """Community: the community group + their educator's; Elite: every group; Tools: none."""
    if tier == "elite":
        keys = ["community", "jay", "tyler", "andrew", "adam"]
    elif tier == "community":
        keys = ["community"] + ([educator] if educator in EDUCATORS else [])
    else:
        keys = []
    return [{"name": GROUPS[k][0], "url": GROUPS[k][1]} for k in keys]
