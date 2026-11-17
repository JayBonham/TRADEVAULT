"""Educator pages: /educators and /educators/<slug>. Bios from the homepage; weekly sessions from the
portal schedule (read 17 Nov 2026, times in ET, valid until the clocks change in March)."""

EDUCATORS = [
    {
        "slug": "jay-bonham", "name": "Jay Bonham", "role": "Founder · US30 Sniper", "scanner": "killshot",
        "photo": "/assets/jay-bonham-cut.webp", "card": "/assets/jay-bonham-card.webp", "pos": "center 10%",
        "markets": ["US30", "Gold", "Killshot"], "creds": ["UKNF regulated", "Liquidity Provider", "500+ mentorship clients"],
        "bio": ["Jay Bonham is the founder of The Trade Vault and the creator of the Killshot methodology. He’s a UKNF-regulated trader and Liquidity Provider who built Killshot from years of active trading on US30: a rules-based system that takes emotion out of every decision.",
                "He has mentored 500+ traders worldwide. Inside the Vault he trades the New York open live three mornings a week, runs a Monday mindset session and closes the week with a backtest-and-review session, so members watch the same rules applied in real markets."],
        "style": [("Market", "US30 and gold"), ("Scanner", "Killshot"), ("Style", "Rules-based intraday, New York open")],
        "sessions": [("Scalp the New York Open!", "Tue · Wed · Thu", "9:00 AM ET"), ("Monday Mindset", "Mon", "12:00 PM ET"), ("Friday Backtest & Rant", "Fri", "12:00 PM ET")],
        "desc": "Jay Bonham is the founder of The Trade Vault and creator of the Killshot method: a UKNF-regulated trader and Liquidity Provider who trades the US30 New York open live with members.",
    },
    {
        "slug": "tyler-collins", "name": "Tyler “Tyco” Collins", "short": "Tyler Collins", "role": "Gold & NQ Specialist", "scanner": "smartshot",
        "photo": "/assets/tyler-collins-cut.webp", "card": "/assets/tyler-collins-card.webp", "pos": "center 8%",
        "markets": ["Gold", "NQ", "Smartshot"], "creds": ["9 years trading", "Smart Money Concepts", "Author"],
        "bio": ["Tyler “Tyco” Collins is the founder of Smart Shot Daily and the author of “Zen and the Art of Not Blowing Your Trading Account.” He has 9 years of experience trading futures, forex, crypto and commodities.",
                "Today he focuses on gold and NQ with his own Smart Money Concepts entry model, which became the Smartshot scanner. He trades gold live in the Vault three days a week."],
        "style": [("Market", "Gold and NQ"), ("Scanner", "Smartshot"), ("Style", "Smart Money Concepts, intraday")],
        "sessions": [("Smartshot Gold Scalping", "Tue · Wed · Thu", "10:30 AM ET")],
        "desc": "Tyler “Tyco” Collins trades gold and NQ with Smart Money Concepts: founder of Smart Shot Daily, author, and creator of the Smartshot scanner. Live gold sessions in The Trade Vault.",
    },
    {
        "slug": "andrew-bridges", "name": "Andrew Bridges", "role": "Technical Specialist", "scanner": "spectrum",
        "photo": "/assets/andrew-bridges.jpg", "card": "/assets/andrew-bridges-card.webp", "pos": "center 18%",
        "markets": ["US30", "ES", "NQ", "Spectrum"], "creds": ["15 years in markets", "6 years educating", "Institutional background"],
        "bio": ["Andrew Bridges has 15 years in financial markets, 6 of them as an educator. He brings institutional methodology from two bespoke fund Risk Management and Strategy Development departments, plus live trading desk experience on the DAX, gold and ES.",
                "His Spectrum scanner applies initial market auction theory and session volume analysis to the index markets. He runs Spectrum ORB sessions live in the Vault four days a week."],
        "style": [("Market", "US30, ES and NQ"), ("Scanner", "Spectrum"), ("Style", "Auction theory, session volume")],
        "sessions": [("Spectrum ORB: London Session", "Sun · Tue · Wed · Thu", "1:00 PM ET")],
        "desc": "Andrew Bridges brings 15 years of institutional market experience to The Trade Vault. Creator of the Spectrum scanner for US30, ES and NQ, with live Spectrum sessions four days a week.",
    },
    {
        "slug": "adam-haase", "name": "Adam Haase", "role": "Killshot Specialist · Polish Community", "scanner": "killshot",
        "photo": "/assets/adam-haase.webp", "card": "/assets/adam-haase-card.webp", "pos": "center 12%",
        "markets": ["US30", "NAS100", "Gold", "Killshot"], "creds": ["Trading since 2019", "Fund collaboration", "Polish community lead"],
        "bio": ["Adam Haase has been trading since 2019. He combines the Killshot methodology with price action across US30, NAS100 and gold, and collaborates with an investment fund.",
                "He leads one of Europe’s fastest-growing Polish-speaking trading communities, and runs his live Killshot sessions in Polish four days a week."],
        "style": [("Market", "US30, NAS100 and gold"), ("Scanner", "Killshot"), ("Style", "Killshot with price action"), ("Language", "Polish")],
        "sessions": [("Sesja Killshot (Polish)", "Mon · Tue · Wed · Thu", "11:00 AM ET"), ("Mindset + Analiza (Polish)", "Fri", "4:00 AM ET")],
        "desc": "Adam Haase trades US30, NAS100 and gold with Killshot and price action, and leads The Trade Vault's Polish-speaking community with live Killshot sessions in Polish.",
    },
]


def _short(e):
    return e.get("short") or e["name"]


def card(e, B):
    return ('<a class="card ed-card" href="/educators/%s"><div class="thumb"><img src="%s" alt="%s" loading="lazy"></div>'
            '<span class="n">%s</span><h3>%s</h3><p>%s</p><span class="go">Meet %s →</span></a>') % (
        e["slug"], e["card"], B.esc(_short(e)), B.esc(e["role"]).upper(), B.esc(e["name"]), B.esc(e["bio"][0].split(". ")[0]) + ".", B.esc(_short(e).split(" ")[0]))


def _et_to(t, off):
    h, rest = t.split(":"); m, ap = rest.split(" ")[0], rest.split(" ")[1]
    h = int(h) % 12 + (12 if ap == "PM" else 0) + off
    d = "" if 0 <= h < 24 else (" (+1 day)" if h >= 24 else " (−1 day)")
    h %= 24
    return "%d:%s %s%s" % (h % 12 or 12, m, "AM" if h < 12 else "PM", d)


def build(B):
    import content_scanners as S
    scan = {s["slug"]: s for s in S.SCANNERS}
    esc = B.esc
    out = []
    for e in EDUCATORS:
        path = "/educators/" + e["slug"]
        cv, cld = B.crumbs([("/educators", "Educators"), (path, _short(e))])
        s = scan[e["scanner"]]
        sched = "".join('<div class="srow"><div><b>%s</b><div class="days">%s</div></div><div class="t">%s<small>%s UK · %s PT</small></div></div>' % (
            esc(n), d.upper(), t.replace(" ET", " ET"), _et_to(t.replace(" ET", ""), 5), _et_to(t.replace(" ET", ""), -3)) for n, d, t in e["sessions"])
        faqs = [
            ("What does %s trade?" % _short(e), "%s trades %s using the %s scanner." % (_short(e), dict(e["style"])["Market"], s["name"])),
            ("When does %s trade live?" % _short(e).split(" ")[0], "; ".join("%s: %s at %s" % (n, d.replace(" · ", ", "), t) for n, d, t in e["sessions"]) + ". Every session is recorded for members."),
            ("How can I learn from %s?" % _short(e).split(" ")[0], "On the Community plan you choose one educator and their scanner, so you can pick %s and %s. Elite includes all four educators and every live session." % (_short(e), s["name"])),
        ]
        fv, fld = B.faq_html(faqs)
        body = cv + f'''
<section class="hero split"><div>
  <span class="mono eyebrow">Educator · {esc(e["role"])}</span>
  <h1>{esc(e["name"])}</h1>
  <p class="lede">{esc(e["desc"])}</p>
  <div class="chips">{"".join('<span class="chip acc">%s</span>' % esc(c) for c in e["creds"])}{"".join('<span class="chip">%s</span>' % m for m in e["markets"])}</div>
  <div class="ctas"><a class="btn" href="/#pricing">Learn with {esc(_short(e).split(" ")[0])} <span class="arr">→</span></a><a class="btn-g" href="/scanners/{s["slug"]}">The {s["name"]} scanner</a></div>
</div><div class="media portrait"><img src="{e["photo"]}" alt="{esc(_short(e))}, Trade Vault educator" style="object-position:{e["pos"]}"></div></section>

<section class="sec"><div class="split" style="align-items:start"><div><span class="mono eyebrow">About</span><h2>How {esc(_short(e).split(" ")[0])} trades.</h2>
<div class="prose" style="margin-top:18px">{"".join("<p>%s</p>" % esc(p) for p in e["bio"])}</div></div>
<div class="grid2" style="margin-top:0">{"".join('<div class="card"><span class="n">%s</span><h3 style="font-size:20px">%s</h3></div>' % (k.upper(), esc(v)) for k, v in e["style"])}</div></div></section>

<section class="sec"><span class="mono eyebrow">Live sessions</span><h2>Trade live with {esc(_short(e).split(" ")[0])} <span class="hl">every week.</span></h2>
<div class="sched">{sched}</div>
<p class="note">Current weekly schedule, shown in Eastern Time with UK and Pacific times. Members see the live schedule in their own time zone in the portal, and every session is recorded.</p></section>

<section class="sec"><span class="mono eyebrow">The scanner</span><h2>{s["name"]}: {esc(" · ".join(s["markets"]))}</h2>
<p class="sub">{esc(s["lede"])}</p><div class="ctas" style="margin-top:22px;display:flex;gap:12px;flex-wrap:wrap"><a class="btn-g" href="/scanners/{s["slug"]}">How {s["name"]} works →</a></div></section>

<section class="sec"><span class="mono eyebrow">Questions</span><h2>About {esc(_short(e).split(" ")[0])}.</h2>{fv}</section>

<section class="sec"><span class="mono eyebrow">The team</span><h2>The other educators.</h2>
<div class="grid3">{"".join(card(x, B) for x in EDUCATORS if x is not e)}</div></section>
{B.band()}'''
        person = {"@type": "Person", "name": _short(e), "jobTitle": e["role"].split(" · ")[0] + " educator", "description": e["desc"],
                  "image": B.SITE + e["photo"], "url": B.SITE + path, "worksFor": {"@id": B.SITE + "/#org"},
                  "knowsAbout": [m for m in e["markets"]] + ["Trading education"]}
        prof = {"@type": "ProfilePage", "url": B.SITE + path, "mainEntity": person}
        out.append((B.page(path, "%s: %s | The Trade Vault" % (_short(e), e["role"].split(" · ")[0]), e["desc"], body, "educators", (cld, fld, prof),
                           image="/assets/" + e["slug"] + ".jpg"), "0.7", "monthly"))

    cv, cld = B.crumbs([("/educators", "Educators")])
    body = cv + f'''
<section class="hero"><span class="mono eyebrow">The educators</span><h1>Four traders. <span class="hl">All trading live.</span></h1>
<p class="lede">Every educator in the Vault trades live, in the same markets they teach. You learn from people executing the same setups, every session.</p>
<div class="ctas"><a class="btn" href="/#pricing">Pick your educator <span class="arr">→</span></a><a class="btn-g" href="/webinar/replay">Watch the free replay</a></div></section>
<section class="sec" style="border-top:0;padding-top:10px"><div class="grid2">{"".join(card(e, B) for e in EDUCATORS)}</div>
<p class="sub">On Community you pick one educator and their scanner. Elite gets you all four, every live session and every recording.</p></section>
{B.band()}'''
    out.append((B.page("/educators", "Trading Educators: Jay Bonham, Tyler Collins, Andrew Bridges, Adam Haase | The Trade Vault",
                       "Meet The Trade Vault's four live trading educators: Jay Bonham (US30, Killshot), Tyler Collins (gold and NQ, Smartshot), Andrew Bridges (indices, Spectrum) and Adam Haase (Killshot, Polish community).",
                       body, "educators", (cld,)), "0.7", "monthly"))
    return out
