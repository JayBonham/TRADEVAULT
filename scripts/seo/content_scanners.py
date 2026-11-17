"""Scanner pages: /scanners, /scanners/killshot, /scanners/smartshot, /scanners/spectrum.
Facts come from the homepage, the webinar page and the curriculum (bootcamp lessons)."""

SCANNERS = [
    {
        "slug": "killshot", "name": "Killshot", "markets": ["US30", "Gold", "Bitcoin"], "by": ["jay-bonham", "adam-haase"],
        "title": "Killshot Scanner: Rules-Based US30, Gold & Bitcoin Setups | The Trade Vault",
        "desc": "Killshot is The Trade Vault's original rules-based scanner for US30, gold and Bitcoin. EMA trend structure, Point of Control levels and signal stars flag setups with defined risk.",
        "h1": 'Killshot: <span class="hl">rules, not hunches.</span>',
        "lede": "The original Trade Vault scanner, built by Jay Bonham from years of trading US30. Killshot combines EMA trend structure, Point of Control levels and its own signal stars to flag setups with the stop and target defined before you enter.",
        "image": "/assets/killshot-graphic.webp", "live": True,
        "how": [
            ("Trend", "Trade with the trend", "Killshot reads EMA structure across four timeframes (M3, M15, H1, H4) so you know whether you should only be buying or only be selling."),
            ("Location", "Wait for the Point of Control", "It marks the Point of Control, the price where the most volume traded. Entries near it have a reason to hold. Entries in the middle of nowhere don’t."),
            ("Trigger", "No star, no trade", "A signal star prints when price is stretched to an extreme in the direction of the trend. That’s the trigger. Your stop and target are set before you click."),
        ],
        "points": ["Flags setups on US30, gold and Bitcoin", "Trend read across M3, M15, H1 and H4", "Point of Control levels on the chart", "Signal stars for the entry trigger",
                   "Entry, stop and target defined up front", "Taught step by step in the Killshot Bootcamp"],
        "course": ("Killshot Bootcamp", ["What is Killshot?", "How does it work?", "What are the EMAs?", "What is the POC?", "What are the stars and how to use them", "How to use and backtest Killshot"]),
        "advanced": ["The open strategy", "The inverse risk reward", "The 3-minute gold strategy", "The PB & J"],
        "faq": [
            ("What is the Killshot scanner?", "Killshot is a rules-based scanner built by Jay Bonham. It combines EMA trend structure, Point of Control levels and signal stars to flag setups on US30, gold and Bitcoin, with the stop and target defined before entry."),
            ("Does Killshot place trades for me?", "No. Killshot finds and flags setups that match its rules. You decide whether to take the trade, and you place it. The Trade Vault teaches you to read every signal in the Killshot Bootcamp."),
            ("Which markets does Killshot work on?", "Killshot is used on US30 (the Dow Jones), gold (XAU/USD) and Bitcoin. Jay and Adam trade it live on US30 and gold."),
            ("How do I get Killshot?", "Killshot is included in every Trade Vault plan: Tools ($49.99/month, all three scanners), Community (pick one educator and one scanner) and Elite (everything)."),
            ("Can I backtest Killshot?", "Yes. The last lesson of the Killshot Bootcamp, “How to use and backtest Killshot”, walks through testing it on past charts before you trade it."),
        ],
    },
    {
        "slug": "smartshot", "name": "Smartshot", "markets": ["Gold", "NQ"], "by": ["tyler-collins"],
        "title": "Smartshot Scanner: Smart Money Concepts for Gold & NQ | The Trade Vault",
        "desc": "Smartshot is a Smart Money Concepts scanner for gold and NQ, built by Tyler Collins. It maps liquidity and structure on higher timeframes, then signals A+ and B+ entries on lower timeframes.",
        "h1": 'Smartshot: <span class="hl">smart money, mapped.</span>',
        "lede": "Built by Tyler “Tyco” Collins on Smart Money Concepts. Smartshot maps liquidity and market structure on the higher timeframes, then signals entries on the lower timeframes with order-flow confirmation. A+ and B+ setups only.",
        "image": "/assets/smartshot-graphic.webp",
        "how": [
            ("Map", "Higher-timeframe structure", "Smartshot maps liquidity and structure on the higher timeframes first, so you know where the market is likely to be drawn."),
            ("Confirm", "Order-flow confirmation", "It waits for confirmation in the order flow before anything fires, instead of guessing a reversal."),
            ("Filter", "A+ and B+ only", "Only the higher-quality setups are signalled, graded A+ or B+. Fewer trades, clearer reasons."),
        ],
        "points": ["Built for gold (XAU/USD) and NQ", "Smart Money Concepts entry model", "Liquidity and structure mapped on higher timeframes",
                   "Entries signalled on lower timeframes", "Order-flow confirmation", "A+ and B+ setups only"],
        "course": ("Smartshot Bootcamp", ["Smartshot overview"]),
        "faq": [
            ("What is the Smartshot scanner?", "Smartshot is a Smart Money Concepts scanner for gold and NQ, built by Tyler Collins. It maps liquidity and structure on higher timeframes and signals entries on lower timeframes with order-flow confirmation."),
            ("What does A+ and B+ mean?", "Smartshot grades its setups and only signals the higher-quality ones, A+ and B+. It’s designed to give you fewer, clearer trades rather than constant alerts."),
            ("Who trades Smartshot live?", "Tyler “Tyco” Collins runs Smartshot Gold Scalping sessions live in The Trade Vault, Tuesday to Thursday."),
            ("How do I get Smartshot?", "Smartshot is included in every Trade Vault plan: Tools ($49.99/month, all three scanners), Community (pick one educator and one scanner) and Elite (everything)."),
        ],
    },
    {
        "slug": "spectrum", "name": "Spectrum", "markets": ["US30", "ES", "NQ"], "by": ["andrew-bridges"],
        "title": "Spectrum Scanner: Auction Theory & Session Volume for Indices | The Trade Vault",
        "desc": "Spectrum is an index scanner for US30, ES and NQ built by Andrew Bridges. It uses initial market auction theory, session volume analysis and liquidity inducement to find entries.",
        "h1": 'Spectrum: <span class="hl">institutional method, retail precision.</span>',
        "lede": "Built by Andrew Bridges from 15 years in financial markets. Spectrum uses initial market auction theory and session volume analysis, then looks for liquidity inducement to find entries across the index markets.",
        "image": "/assets/spectrum-graphic.webp",
        "how": [
            ("Auction", "Initial market auction", "Spectrum reads how the session opens, the initial auction, to frame the range the market is working in."),
            ("Volume", "Session volume analysis", "It weighs where volume traded in the session to find the levels that matter."),
            ("Inducement", "Liquidity inducement", "Entries come when the market induces traders the wrong way, then shows its hand."),
        ],
        "points": ["Built for US30, ES (S&P 500 futures) and NQ", "Initial market auction theory", "Session volume analysis",
                   "Liquidity inducement entries", "Set files for US30 and XAU/USD", "Taught in the Spectrum Bootcamp"],
        "course": ("Spectrum Bootcamp", ["What is Spectrum?", "How does it work? Strategy overview", "The rules in the signals", "US30 set file", "XAU/USD set file", "Conclusion"]),
        "faq": [
            ("What is the Spectrum scanner?", "Spectrum is an index scanner built by Andrew Bridges. It uses initial market auction theory, session volume analysis and liquidity inducement to find entries on US30, ES and NQ."),
            ("What markets does Spectrum cover?", "Spectrum is built for the index markets: US30 (Dow Jones), ES (S&amp;P 500 futures) and NQ (Nasdaq). The bootcamp also includes a set file for XAU/USD."),
            ("Who trades Spectrum live?", "Andrew Bridges runs Spectrum ORB sessions live in The Trade Vault around the London afternoon, four days a week."),
            ("How do I get Spectrum?", "Spectrum is included in every Trade Vault plan: Tools ($49.99/month, all three scanners), Community (pick one educator and one scanner) and Elite (everything)."),
        ],
    },
]


def _live_panel():
    return ('<div class="ui" data-ks-panel aria-label="Killshot replaying past gold 3-minute charts">'
            '<div class="ui-top"><b>Killshot</b><span>XAUUSD · 3m · replay</span><em>Replay</em></div><div class="ui-body">'
            '<div class="ks-chart"><canvas data-ks-live aria-hidden="true"></canvas></div><div class="ui-rows">'
            '<div data-ks-row="trend"><b>Trend</b><span>M3 · M15 · H1 · H4</span><i class="st">–</i></div>'
            '<div data-ks-row="poc"><b>POC</b><span>Point of Control</span><i class="st">–</i></div>'
            '<div data-ks-row="signal"><b>Signal</b><span>Watching for a stretched extreme</span><i class="st wait">Scanning</i></div>'
            '</div></div></div><p class="note">Replays of past gold 3-minute charts with the Killshot overlay. Not live trades.</p>')


def build(B):
    import content_educators as E
    eds = {e["slug"]: e for e in E.EDUCATORS}
    esc = B.esc
    out = []
    for s in SCANNERS:
        path = "/scanners/" + s["slug"]
        cv, cld = B.crumbs([("/scanners", "Scanners"), (path, s["name"])])
        fv, fld = B.faq_html(s["faq"])
        media = _live_panel() if s.get("live") else '<div class="media" style="padding:12px;background:#0B1528"><img src="%s" alt="%s scanner on a trading chart" width="1200" height="810"></div>' % (s["image"], s["name"])
        body = cv + f'''
<section class="hero split"><div>
  <span class="mono eyebrow">Scanner · {" · ".join(s["markets"])}</span>
  <h1>{s["h1"]}</h1>
  <p class="lede">{s["lede"]}</p>
  <div class="ctas"><a class="btn" href="/#pricing">Get {s["name"]} <span class="arr">→</span></a><a class="btn-g" href="/webinar">Free live training</a></div>
  <div class="chips">{"".join('<span class="chip acc">%s</span>' % m for m in s["markets"])}<span class="chip">Included from $49.99/mo</span></div>
</div><div>{media}</div></section>

<section class="sec"><span class="mono eyebrow">How it works</span><h2>Three steps. <span class="hl">Every setup.</span></h2>
<div class="grid3">{"".join('<div class="card"><span class="n">0%d · %s</span><h3>%s</h3><p>%s</p></div>' % (i + 1, k.upper(), t, p) for i, (k, t, p) in enumerate(s["how"]))}</div></section>

<section class="sec"><span class="mono eyebrow">What you get</span><h2>What {s["name"]} <span class="hl">does for you.</span></h2>
<div class="grid3">{"".join('<div class="card"><p style="color:var(--tx)">✓ %s</p></div>' % p for p in s["points"])}</div>
<p class="sub">{s["name"]} flags setups that match its rules. It doesn’t trade for you: you decide what to take, size it and place it. That’s what the bootcamp teaches.</p></section>

<section class="sec"><span class="mono eyebrow">Learn it inside the Vault</span><h2>The {esc(s["course"][0])}.</h2>
<p class="sub">Every lesson is a video with its own slide deck, in the order you need them.</p>
<div class="grid3">{"".join('<div class="card"><span class="n">LESSON %02d</span><h3 style="font-size:19px">%s</h3></div>' % (i + 1, esc(t)) for i, t in enumerate(s["course"][1]))}</div>
{('<p class="sub">Then the Advanced Academy goes further: ' + ", ".join(esc(x) for x in s["advanced"]) + '.</p>') if s.get("advanced") else ""}</section>

<section class="sec"><span class="mono eyebrow">Trade it live</span><h2>Who runs {s["name"]} <span class="hl">live.</span></h2>
<div class="grid{2 if len(s["by"]) > 1 else 2}">{"".join(E.card(eds[x], B) for x in s["by"])}</div></section>

<section class="sec"><span class="mono eyebrow">Questions</span><h2>{s["name"]} FAQ.</h2>{fv}</section>
{B.band()}'''
        app = {"@type": "SoftwareApplication", "name": s["name"] + " scanner", "applicationCategory": "FinanceApplication",
               "operatingSystem": "TradingView", "description": s["desc"], "url": B.SITE + path, "image": B.SITE + s["image"],
               "publisher": {"@id": B.SITE + "/#org"},
               "offers": {"@type": "Offer", "price": "49.99", "priceCurrency": "USD", "url": B.SITE + "/#pricing"}}
        scripts = '<script src="/assets/ks-live.js" defer></script>' if s.get("live") else ""
        out.append((B.page(path, s["title"], s["desc"], body, "scanners", (cld, fld, app), image=s["image"].replace(".webp", ".png") if s["slug"] != "spectrum" else "/assets/og-image.jpg", scripts=scripts), "0.8", "monthly"))

    # hub
    cv, cld = B.crumbs([("/scanners", "Scanners")])
    rows = "".join('<tr><td><b><a href="/scanners/%s">%s</a></b></td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        s["slug"], s["name"], " · ".join(s["markets"]), {"killshot": "EMA trend, Point of Control, signal stars", "smartshot": "Smart Money Concepts, liquidity, order flow", "spectrum": "Auction theory, session volume, inducement"}[s["slug"]],
        ", ".join(eds[x]["name"] for x in s["by"])) for s in SCANNERS)
    body = cv + f'''
<section class="hero"><span class="mono eyebrow">The scanners</span><h1>Three scanners. <span class="hl">One vault.</span></h1>
<p class="lede">These aren’t free indicators. The educators built them, trade them live and teach you to read every signal. Setup identification is automated. Execution is still yours.</p>
<div class="ctas"><a class="btn" href="/#pricing">All three from $49.99/mo <span class="arr">→</span></a><a class="btn-g" href="/spot">Try the chart game</a></div></section>
<section class="sec" style="border-top:0;padding-top:10px"><div class="grid3">{"".join('<a class="card" href="/scanners/%s"><div class="thumb contain"><img src="%s" alt="%s scanner" loading="lazy"></div><span class="n">%s</span><h3>%s</h3><p>%s</p><span class="go">How %s works →</span></a>' % (s["slug"], s["image"], s["name"], " · ".join(s["markets"]).upper(), s["name"], B.esc(s["desc"].split(". ")[0]) + ".", s["name"]) for s in SCANNERS)}</div></section>
<section class="sec"><span class="mono eyebrow">Compare</span><h2>Which scanner <span class="hl">fits you?</span></h2>
<div class="prose" style="max-width:none;margin-top:24px"><div class="tw"><table><thead><tr><th>Scanner</th><th>Markets</th><th>Method</th><th>Traded live by</th></tr></thead><tbody>{rows}</tbody></table></div></div>
<p class="sub">Tools gets you all three for $49.99/month. Community gives you one educator and their scanner with the Basic Academy. Elite is everything.</p></section>
{B.band()}'''
    out.append((B.page("/scanners", "Trading Scanners for US30, Gold & NQ: Killshot, Smartshot, Spectrum | The Trade Vault",
                       "Compare The Trade Vault's three proprietary trading scanners: Killshot (US30, gold, Bitcoin), Smartshot (gold, NQ) and Spectrum (US30, ES, NQ). All three from $49.99/month.",
                       body, "scanners", (cld,)), "0.8", "monthly"))
    return out
