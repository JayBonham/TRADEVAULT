/* Affiliate promo kit: graphics slider, ready-made captions and DMs, and the playbook.
   Every caption has the affiliate's own link dropped in. Webinar pieces only show while
   admin has webinar links switched on. TVKit.render(el, {main, webinar, webOn}) */
(function () {
  var IMG = '/assets/promo/';
  var DISCLOSE = '\n\n(Affiliate link: I earn a commission if you join. Trading involves risk.)';

  // caption keys used by graphics below
  var CAP = {
    rules: 'I’ve been trading inside The Trade Vault.\n\n4 educators trading live every week, 3 scanners (Killshot, Smartshot and Spectrum) and a journal that checks whether I actually followed my rules.\n\nIf you’re tired of guessing, have a look 👇\n{link}\n\nPlans from $49.99/month.' + DISCLOSE,
    educators: 'Four traders. All trading live.\n\n• Jay Bonham: Killshot (US30, Gold, BTC)\n• Tyler Collins: Smartshot (Gold & NQ)\n• Adam Haase: Killshot (US30)\n• Andrew Bridges: Spectrum (indices)\n\nPick one on Community, or get all four on Elite.\n{link}' + DISCLOSE,
    alone: 'Trading alone is the hardest way to learn it.\n\nInside The Trade Vault you sit in on live sessions 5 times a week, watch the educators call their trades and ask questions while it happens.\n\nCome trade with us 👇\n{link}' + DISCLOSE,
    scanners: 'Three scanners. One plan.\n\nKillshot, Smartshot and Spectrum flag the setups. You decide what to take, with rules for every entry, stop and target.\n\nAll three are on every plan, from $49.99/month:\n{link}' + DISCLOSE,
    journal: 'The part nobody talks about: did you actually follow your rules?\n\nThe Trade Vault journal connects to MetaTrader and shows you, trade by trade. It’s been a game changer for my discipline.\n\n{link}' + DISCLOSE,
    signals: 'Two ways to trade the Vault:\n\n1️⃣ Semi-automatic: entries, stops and targets sent to you\n2️⃣ Fully automatic: Copy Trader runs it with set risk\n\nBoth come with Elite. Have a look:\n{link}' + DISCLOSE,
    pricing: 'Three ways into The Trade Vault:\n\n• Tools, $49.99/mo: all three scanners\n• Community, $99.99/mo: 1 educator + 1 scanner + the Academy\n• Elite, $124.99/mo: everything, including signals and Copy Trader\n\nPick yours 👇\n{link}' + DISCLOSE,
    everything: 'Everything in one place:\n\n01 — 4 educators trading live\n02 — 3 proprietary scanners\n03 — The full Academy, basic to advanced\n04 — A journal that checks your rules\n05 — Signals & Copy Trader\n\nThis is what I use. Link to join:\n{link}' + DISCLOSE,
    me: 'People keep asking what I use, so here it is.\n\nI trade inside The Trade Vault: live educators, real scanners and a journal that keeps me honest.\n\nIf you want to trade with us, here’s my link 👇\n{link}' + DISCLOSE,
    bell: '09:29. One minute to the open.\n\nDo you have a plan, or are you about to guess?\n\nScanners that flag the setup. Educators trading it live. Rules you actually follow. That’s The Trade Vault.\n\n{link}' + DISCLOSE,
    web1: 'FREE LIVE WEBINAR 🔴\n\nJay Bonham is opening up The Trade Vault, live on Zoom: the educators, the 3 scanners, the journal, signals and Copy Trader. Live Q&A at the end.\n\nIt’s free. Save your seat 👇\n{webinar}\n\n(Educational only, not financial advice.)',
    web2: 'What you’ll see on the free webinar:\n\n01 — 4 educators and how they run their live sessions\n02 — Killshot, Smartshot and Spectrum\n03 — The journal that tracks your rules\n04 — Signals & Copy Trader, plus live Q&A\n\nFree seat here:\n{webinar}'
  };

  var GRAPHICS = [
    { f: '01-trade-with-rules', t: 'Trade with rules', k: 'post', cap: 'rules' },
    { f: '02-four-educators', t: 'Four educators', k: 'post', cap: 'educators' },
    { f: '03-stop-trading-alone', t: 'Stop trading alone', k: 'post', cap: 'alone' },
    { f: '04-three-scanners', t: 'Three scanners', k: 'post', cap: 'scanners' },
    { f: '05-the-journal', t: 'The journal', k: 'post', cap: 'journal' },
    { f: '06-signals-copy-trader', t: 'Signals & Copy Trader', k: 'post', cap: 'signals' },
    { f: '07-three-ways-in', t: 'Pricing', k: 'post', cap: 'pricing' },
    { f: '08-everything-inside', t: 'Everything inside', k: 'post', cap: 'everything' },
    { f: '09-im-in', t: 'I trade inside', k: 'post', cap: 'me' },
    { f: '10-no-more-guessing', t: 'Plan before the bell', k: 'post', cap: 'bell' },
    { f: '11-webinar-opening-the-vault', t: 'Webinar: opening the Vault', k: 'webinar', cap: 'web1' },
    { f: '12-webinar-what-youll-see', t: 'Webinar: what you’ll see', k: 'webinar', cap: 'web2' },
    { f: '13-story-trade-with-rules', t: 'Story: trade with rules', k: 'story' },
    { f: '14-story-educators', t: 'Story: four traders', k: 'story' },
    { f: '15-story-webinar', t: 'Story: webinar', k: 'story', web: true },
    { f: '16-story-three-ways-in', t: 'Story: pricing', k: 'story' }
  ];

  var DMS = [
    { t: 'When someone asks what you use', s: 'I use The Trade Vault. Live educators, 3 scanners and a journal that tracks whether I followed my rules. Here’s my link if you want a look: {link}' },
    { t: 'They’re interested but unsure', s: 'No pressure at all. Tools starts at $49.99/month if you just want the scanners, and you can upgrade any time. Happy to answer anything about how I use it.' },
    { t: 'Follow-up a few days later', s: 'Hey, did you get a chance to look at The Trade Vault? If you’ve got questions about the scanners or the live sessions, ask away. Link again: {link}' },
    { t: 'Missed the webinar? Send the replay', s: 'Jay did a full live walkthrough of The Trade Vault: the educators, the scanners, the journal and every plan. You can watch the whole replay here: {replay}' },
    { t: 'Webinar invite', s: 'Jay’s doing a free live walkthrough of The Trade Vault on Zoom: the scanners, the journal and live Q&A. Grab a free seat here: {webinar}', web: true },
    { t: 'Webinar day reminder', s: 'Reminder: the free Trade Vault webinar is today. If you haven’t saved a seat yet, it takes 10 seconds: {webinar}', web: true }
  ];

  var BIOS = [
    '📈 Trading with rules, not instinct\n🔐 Inside The Trade Vault ↓',
    'Learning to trade live with 4 educators ↓',
    'Scanners + live sessions + a journal that keeps me honest 👇',
    '🔴 Free live webinar: see inside The Trade Vault ↓'
  ];

  var STEPS = [
    { h: 'Put your link in your bio', p: 'Instagram, TikTok, YouTube and X all have a link field. Paste your link there. Using Linktree or similar? Make it the first button and call it “Join The Trade Vault”.' },
    { h: 'Pin a post to your profile', p: 'Post “Trade with rules” or “I trade inside” with its caption below, then pin it (••• → Pin to your profile). New visitors see it first.' },
    { h: 'Post stories with a link sticker', p: 'Use the story graphics. Add a Link sticker with your link and drop it on the dashed “Put your link here” box. Save them to a Highlight called “Trade Vault” so they stay up.' },
    { h: 'Show your own trading', p: 'Your real sessions, your journal, the scanner on your chart. People join people. Show the process, not just wins.' },
    { h: 'Reply to DMs with your link', p: 'When someone asks how you trade, send the DM template below. A personal message beats a post every time.' },
    { h: 'Push the webinar when it’s on', p: 'Post the webinar graphic 2–3 days before, a story the day before and on the day. Every sign-up through your webinar link shows in your Opt-ins, and if they buy you’re credited.', web: true }
  ];

  var RULES = [
    'Never promise profits, income or “guaranteed” results.',
    'Don’t post anyone else’s P&L or screenshots as your own.',
    'Say it’s your affiliate link (the captions already do).',
    'Don’t spam groups or comment sections with your link.'
  ];

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function fill(s, L) { return s.replace(/\{link\}/g, L.main).replace(/\{webinar\}/g, L.webinar).replace(/\{replay\}/g, L.replay); }
  function copyBtn(text, label, cls) {
    var b = el('button', cls || 'btn-g btn-sm', label); b.type = 'button';
    b.addEventListener('click', function () {
      var done = function () { b.textContent = 'Copied ✓'; b.classList.add('done'); setTimeout(function () { b.textContent = label; b.classList.remove('done'); }, 1500); };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () { window.prompt && window.prompt('Copy this', text); });
      else window.prompt && window.prompt('Copy this', text);
    });
    return b;
  }
  function sec(title, sub) {
    var s = el('section', 'sec'), h = el('div', 'sech'); h.appendChild(el('h2', null, title)); if (sub) h.appendChild(el('span', 'mono', sub)); s.appendChild(h); return s;
  }

  function render(root, L) {
    root.innerHTML = '';
    var web = !!L.webOn;

    // hero
    var hero = el('section', 'card kithero');
    var hl = el('div'); hl.appendChild(el('span', 'mono', 'Your promo kit'));
    hl.appendChild(el('h2', null, 'Everything you need to start sharing.'));
    hl.appendChild(el('p', 'help', 'Graphics, captions and DMs, all with your link already in them. Download, copy, post.'));
    hero.appendChild(hl);
    var links = el('div', 'kitlinks');
    [['Direct offer link', L.main, true], ['Webinar link', L.webinar, web], ['Last webinar replay', L.replay, true]].forEach(function (x) {
      if (!x[2]) return;
      var r = el('div', 'kitlink'); r.appendChild(el('span', 'mono', x[0])); var c = el('code', null, x[1]); r.appendChild(c); r.appendChild(copyBtn(x[1], 'Copy')); links.appendChild(r);
    });
    hero.appendChild(links);
    root.appendChild(hero);

    // playbook
    var pb = sec('Start here', 'The basics');
    var grid = el('div', 'kitsteps');
    STEPS.filter(function (s) { return !s.web || web; }).forEach(function (s, i) {
      var c = el('div', 'card kitstep'); c.appendChild(el('span', 'n', (i < 9 ? '0' : '') + (i + 1))); c.appendChild(el('h3', null, s.h)); c.appendChild(el('p', null, s.p)); grid.appendChild(c);
    });
    pb.appendChild(grid);
    var rules = el('div', 'card kitrules'); rules.appendChild(el('b', null, 'Keep it clean'));
    var ul = el('ul'); RULES.forEach(function (r) { ul.appendChild(el('li', null, r)); }); rules.appendChild(ul);
    pb.appendChild(rules);
    root.appendChild(pb);

    // graphics slider
    var gs = sec('Graphics', 'Tap to download');
    var chips = el('div', 'kitchips'), filters = [['all', 'All'], ['post', 'Posts'], ['story', 'Stories']];
    if (web) filters.push(['webinar', 'Webinar']);
    var track = el('div', 'kittrack'), cur = 'all';
    var list = GRAPHICS.filter(function (g) { return (g.k !== 'webinar' && !g.web) || web; });
    function draw() {
      track.innerHTML = '';
      list.filter(function (g) { return cur === 'all' || g.k === cur || (cur === 'webinar' && g.web); }).forEach(function (g) {
        var card = el('figure', 'kitslide' + (g.k === 'story' ? ' story' : ''));
        var a = el('a'); a.href = IMG + g.f + '.jpg'; a.target = '_blank'; a.rel = 'noopener';
        var img = el('img'); img.src = IMG + 'thumb/' + g.f + '.jpg'; img.alt = g.t; img.loading = 'lazy'; a.appendChild(img); card.appendChild(a);
        var cap = el('figcaption'); cap.appendChild(el('b', null, g.t)); cap.appendChild(el('span', 'mono', g.k === 'story' ? '9:16 story' : '4:5 post'));
        var btns = el('div', 'kitbtns');
        var dl = el('a', 'btn btn-sm', 'Download'); dl.href = IMG + g.f + '.jpg'; dl.setAttribute('download', 'TradeVault-' + g.f + '.jpg'); btns.appendChild(dl);
        if (g.cap) btns.appendChild(copyBtn(fill(CAP[g.cap], L), 'Copy caption'));
        cap.appendChild(btns); card.appendChild(cap); track.appendChild(card);
      });
      track.scrollLeft = 0;
    }
    filters.forEach(function (f) {
      var c = el('button', 'kitchip' + (f[0] === cur ? ' on' : ''), f[1]); c.type = 'button';
      c.addEventListener('click', function () { cur = f[0]; [].forEach.call(chips.children, function (x) { x.classList.remove('on'); }); c.classList.add('on'); draw(); });
      chips.appendChild(c);
    });
    var nav = el('div', 'kitnav');
    var prev = el('button', 'kitarrow', '←'), next = el('button', 'kitarrow', '→'); prev.type = next.type = 'button';
    prev.setAttribute('aria-label', 'Previous'); next.setAttribute('aria-label', 'Next');
    prev.addEventListener('click', function () { track.scrollBy({ left: -track.clientWidth * 0.8, behavior: 'smooth' }); });
    next.addEventListener('click', function () { track.scrollBy({ left: track.clientWidth * 0.8, behavior: 'smooth' }); });
    nav.appendChild(prev); nav.appendChild(next);
    var bar = el('div', 'kitbar'); bar.appendChild(chips); bar.appendChild(nav);
    gs.appendChild(bar); gs.appendChild(track);
    gs.appendChild(el('p', 'help kittip', 'On your phone: tap Download, then press and hold the image and choose Save to Photos. Stories have a dashed box: put your Link sticker there.'));
    draw();
    root.appendChild(gs);

    // DMs
    var ds = sec('DM templates', 'Copy and send');
    var dg = el('div', 'kitcopies');
    DMS.filter(function (d) { return !d.web || web; }).forEach(function (d) {
      var c = el('div', 'card kitcopy'); var t = fill(d.s, L);
      c.appendChild(el('b', null, d.t)); c.appendChild(el('p', null, t)); c.appendChild(copyBtn(t, 'Copy message')); dg.appendChild(c);
    });
    ds.appendChild(dg); root.appendChild(ds);

    // bios
    var bs = sec('Bio lines', 'Pair with your link');
    var bg = el('div', 'kitcopies');
    BIOS.filter(function (b, i) { return i < 3 || web; }).forEach(function (b) {
      var c = el('div', 'card kitcopy'); c.appendChild(el('p', 'bio', b)); c.appendChild(copyBtn(b, 'Copy bio')); bg.appendChild(c);
    });
    bs.appendChild(bg); root.appendChild(bs);
  }

  window.TVKit = { render: render };
})();
