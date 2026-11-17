"""Builds the TradeVault content pages (scanners, educators, learn) into public/tradevault/.

  python3 scripts/seo/build.py

Content lives in content_*.py next to this file. Every page gets: title/description, canonical, OG/Twitter,
BreadcrumbList + page-type JSON-LD, the shared nav/footer, a CTA band and the risk warning.
The sitemap is rebuilt from the static pages plus everything built here.
"""
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "public", "tradevault"))
SITE = "https://thetradevault.co"
TODAY = "2026-11-17"
esc = html.escape


def re_tags(s):
    import re
    return re.sub("<[^>]+>", "", s)

RISK = ("Trading futures, contracts for difference and other leveraged products carries a substantial risk of loss and is not "
        "suitable for every investor. You may lose more than your initial deposit. Past performance is not indicative of future "
        "results. The Trade Vault provides educational content and analytical tools only. Nothing on this site is investment, "
        "financial, legal or tax advice, or a recommendation to buy or sell anything. You are solely responsible for your own "
        "trading decisions.")


def nav(active=""):
    links = [("/scanners", "Scanners", "scanners"), ("/educators", "Educators", "educators"), ("/learn", "Learn", "learn"),
             ("/webinar/replay", "Free training", "webinar"), ("/#pricing", "Pricing", "pricing")]
    return ('<header class="nav"><div class="nav-in">'
            '<a href="/" class="brand"><img src="/assets/tv-icon.png" alt="" width="26" height="26"><img src="/assets/tv-logo.png" alt="The Trade Vault" width="166" height="13"></a>'
            '<nav class="nav-links" aria-label="Site">' + "".join(
                '<a href="%s"%s>%s</a>' % (h, ' class="on"' if k == active else "", t) for h, t, k in links) + '</nav>'
            '<a href="/#pricing" class="btn">Join the Vault <span class="arr">→</span></a></div></header>')


def footer():
    import content_learn as L
    import content_scanners as S
    import content_educators as E
    col = lambda title, items: "<div><b>%s</b>%s</div>" % (title, "".join('<a href="%s">%s</a>' % (h, esc(t)) for h, t in items))
    return ('<footer><div class="W"><div class="fgrid">'
            '<div><a href="/" class="brand"><img src="/assets/tv-icon.png" alt="" width="26" height="26"><img src="/assets/tv-logo.png" alt="The Trade Vault" width="166" height="13"></a>'
            '<p style="color:var(--tx-mute);font-size:14px;margin-top:14px;max-width:30ch">Rules-based trading education, live educators and proprietary scanners.</p></div>'
            + col("Scanners", [("/scanners/" + s["slug"], s["name"]) for s in S.SCANNERS] + [("/scanners", "All scanners")])
            + col("Educators", [("/educators/" + e["slug"], e["name"]) for e in E.EDUCATORS])
            + col("Learn", [("/learn/" + a["slug"], a["short"]) for a in L.ARTICLES[:6]] + [("/learn", "All guides"), ("/spot", "Chart game"), ("/webinar/replay", "Free training replay")])
            + '</div><div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:20px" class="mono"><a href="/terms">Terms</a><a href="/privacy">Privacy</a><a href="/pl">Polski</a><a href="/affiliate-signup">Affiliates</a></div>'
            '<p class="risk">' + RISK + '</p><p class="mono" style="margin-top:14px">© 2026 The Trade Vault</p></div></footer>')


def band(title=None, text=None):
    return ('<section class="band"><div><span class="mono" style="color:var(--acc)">Free training · Watch the replay</span>'
            '<h2>' + (title or 'See inside <span class="hl">the Vault.</span>') + '</h2>'
            '<p>' + (text or "Watch Jay Bonham’s full walkthrough of The Trade Vault: the educators, the scanners, the journal and the plans. Free, watch it now.") + '</p></div>'
            '<div class="ctas"><a class="btn" href="/webinar/replay">Watch the free replay <span class="arr">→</span></a>'
            '<a class="btn-g" href="/#pricing">See the plans</a></div></section>')


def crumbs(trail):
    items = [("/", "Home")] + trail
    vis = '<nav class="crumbs" aria-label="Breadcrumb">' + '<span>/</span>'.join(
        ('<a href="%s">%s</a>' % (h, esc(t)) if i < len(items) - 1 else "<b style='font-weight:500;color:var(--tx-dim)'>%s</b>" % esc(t))
        for i, (h, t) in enumerate(items)) + '</nav>'
    ld = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": t, "item": SITE + (h if h != "/" else "/")} for i, (h, t) in enumerate(items)]}
    return vis, ld


def faq_html(faqs):
    if not faqs:
        return "", None
    vis = '<div class="faq">' + "".join("<details><summary>%s</summary><p>%s</p></details>" % (esc(q), a) for q, a in faqs) + "</div>"
    import re
    ld = {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": html.unescape(re.sub("<[^>]+>", "", a))}} for q, a in faqs]}
    return vis, ld


def page(path, title, desc, body, active="", ld=(), image="/assets/og-image.jpg", extra_head="", scripts=""):
    url = SITE + path
    graph = [{"@type": "Organization", "@id": SITE + "/#org", "name": "The Trade Vault", "url": SITE + "/", "logo": SITE + "/assets/tv-icon.png"}] + [x for x in ld if x]
    doc = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Trade Vault">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE + image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{SITE + image}">
<link rel="icon" href="/assets/tv-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/seo.css">
<script>!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','3566618163494760');fbq('track','PageView');</script>
<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("</", "<\\/")}</script>
{extra_head}</head>
<body>
{nav(active)}
<main class="W">
{body}
</main>
{footer()}
<script src="/assets/tv-ref-content.js"></script>
{scripts}</body>
</html>
'''
    out = os.path.join(ROOT, path.strip("/"), "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(doc)
    return path


STATIC = [("/", "1.0", "weekly", True), ("/pl", "0.9", "weekly", True), ("/webinar", "0.8", "weekly", False), ("/spot", "0.7", "monthly", False),
          ("/affiliate-signup", "0.5", "monthly", False), ("/terms", "0.2", "yearly", False), ("/privacy", "0.2", "yearly", False)]


def sitemap(built):
    x = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    alt = "".join('<xhtml:link rel="alternate" hreflang="%s" href="%s"/>' % (h, SITE + p) for h, p in (("en", "/"), ("pl", "/pl"), ("x-default", "/")))
    for u, pr, cf, a in STATIC + [(p, pr, cf, False) for p, pr, cf in built]:
        x.append("  <url><loc>%s%s</loc><lastmod>%s</lastmod><changefreq>%s</changefreq><priority>%s</priority>%s</url>" % (SITE, u, TODAY, cf, pr, alt if a else ""))
    x.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w").write("\n".join(x) + "\n")


if __name__ == "__main__":
    import content_scanners, content_educators, content_learn
    built = []
    for mod in (content_scanners, content_educators, content_learn):
        built += mod.build(sys.modules[__name__])
    sitemap(built)
    print(len(built), "pages built:", " ".join(p for p, _, _ in built))
