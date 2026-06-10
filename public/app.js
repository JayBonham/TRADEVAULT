/* ============================================================================
   Free Signals Pro — interactions
   Everything you might need to swap is in CONFIG at the top.
   ============================================================================ */

const CONFIG = {
  // CTA destination. Currently the Telegram link; swap for the broker
  // signup/deposit URL once the broker flow is ready.
  ctaUrl: 'https://t.me/+HBFbbw4_Qc9hYjdh',

  // Trust-strip numbers. PLACEHOLDERS — replace with verified figures only.
  // [value, suffix]. Set to null to hide a stat's number.
  stats: [
    [1200, '+'],   // signals sent
    [84,   '%'],   // recent win rate
    [5000, '+'],   // telegram members
    [4,    '']     // markets covered (real: forex, gold, crypto, indices)
  ],
};

/* ── Wire CTA links ─────────────────────────────────────────────────────── */
document.querySelectorAll('[data-cta]').forEach(a => {
  a.href = CONFIG.ctaUrl;
  a.target = '_blank';
  a.rel = 'noopener';
});

document.getElementById('year').textContent = new Date().getFullYear();

/* ── Nav shadow on scroll ───────────────────────────────────────────────── */
const nav = document.getElementById('nav');
const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 12);
onScroll();
window.addEventListener('scroll', onScroll, { passive: true });

/* ── Proof wall ─────────────────────────────────────────────────────────── */
const MKT = {
  gold:   { cls: 'mkt-gold',   tag: 'XAU' },
  forex:  { cls: 'mkt-fx',     tag: 'FX'  },
  crypto: { cls: 'mkt-crypto', tag: 'BTC' },
};
// label, market(s), height(px for placeholder), caption, status, rr
const PROOFS = [
  { m: ['gold','wins'],          h: 200, cap: 'XAUUSD · TP2 hit',         st: 'win',  rr: '+38 pips' },
  { m: ['forex','active'],       h: 250, cap: 'GBPUSD · running',         st: 'live', rr: 'R:R 1:2' },
  { m: ['crypto','wins'],        h: 175, cap: 'BTCUSD · TP1 hit',         st: 'win',  rr: '+2.4%' },
  { m: ['members'],              h: 230, cap: 'Member result · approved', st: 'win',  rr: '' },
  { m: ['forex','wins'],         h: 190, cap: 'EURUSD · closed in profit',st: 'win',  rr: '+22 pips' },
  { m: ['gold','active'],        h: 260, cap: 'XAUUSD · setup forming',   st: 'live', rr: 'pending' },
  { m: ['crypto','active'],      h: 210, cap: 'ETHUSD · running',         st: 'live', rr: 'R:R 1:3' },
  { m: ['members'],              h: 185, cap: 'Member screenshot',        st: 'win',  rr: '' },
  { m: ['forex'],                h: 240, cap: 'USDJPY · trade recap',     st: 'info', rr: 'closed' },
  { m: ['gold','wins'],          h: 200, cap: 'XAUUSD · partial + runner',st: 'win',  rr: '+51 pips' },
  { m: ['crypto'],               h: 220, cap: 'SOLUSD · setup breakdown', st: 'info', rr: 'analysis' },
  { m: ['forex','active'],       h: 180, cap: 'AUDUSD · live alert',      st: 'live', rr: 'R:R 1:2' },
];

const STATUS_MAP = {
  win:  { cls: 'win',  label: 'TP Hit',  ic: 'check' },
  live: { cls: 'live', label: 'Running', ic: null },
  info: { cls: 'info', label: 'Closed',  ic: 'circle' },
};

function primaryMarket(tags) {
  if (tags.includes('gold')) return 'gold';
  if (tags.includes('forex')) return 'forex';
  if (tags.includes('crypto')) return 'crypto';
  return 'forex';
}

const wall = document.getElementById('proofWall');
PROOFS.forEach(p => {
  const pm = primaryMarket(p.m);
  const mk = MKT[pm];
  const stt = STATUS_MAP[p.st];
  const statusInner = stt.cls === 'live'
    ? `<span class="pill live"><span class="dot"></span> Running</span>`
    : `<span class="pill ${stt.cls}">${stt.ic ? `<i data-lucide="${stt.ic}"></i>` : ''} ${stt.label}</span>`;

  const el = document.createElement('div');
  el.className = 'proof';
  el.dataset.markets = p.m.join(' ');
  el.innerHTML = `
    <div class="proof-img">
      <div class="proof-badges">
        <span class="badge-mkt ${mk.cls}" style="width:30px;height:30px;font-size:11px;">${mk.tag}</span>
        ${statusInner}
      </div>
      <div class="proof-ph" style="height:${p.h}px;">
        <div style="display:flex;flex-direction:column;align-items:center;">
          <i data-lucide="image" class="ico"></i>
          <span class="txt">Replace with trade screenshot</span>
        </div>
      </div>
    </div>
    <div class="proof-meta">
      <span class="cap">${p.cap}</span>
      ${p.rr ? `<span class="rr">${p.rr}</span>` : ''}
    </div>`;
  wall.appendChild(el);
});

/* Filter tabs */
const tabs = document.getElementById('proofTabs');
tabs.addEventListener('click', e => {
  const btn = e.target.closest('.tab');
  if (!btn) return;
  tabs.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  const f = btn.dataset.filter;
  wall.querySelectorAll('.proof').forEach(card => {
    const show = f === 'all' || card.dataset.markets.split(' ').includes(f);
    card.style.display = show ? '' : 'none';
  });
});

/* ── FAQ ────────────────────────────────────────────────────────────────── */
const FAQS = [
  ['Do I have to pay for the premium signals?',
   'There is no separate subscription. Premium signal access is unlocked when you open and fund your broker account through the official link on this page.'],
  ['Is my deposit paid to Free Signals Pro?',
   'No. Your deposit funds your own trading account with the broker. You keep control of those funds and trade your own account — it is not a payment to us.'],
  ['Can I withdraw my money?',
   'Withdrawal rules depend on the broker\'s terms and your account status. Always review the broker\'s conditions before depositing so you understand how withdrawals work.'],
  ['Are profits guaranteed?',
   'No. Trading involves risk and no signal provider can guarantee results. We aim to be clear and consistent, but every trade carries risk and you are responsible for your own decisions.'],
  ['What markets do you send signals for?',
   'Forex, gold, crypto and indices, depending on what is active that session. (Replace this with your verified market list before publishing.)'],
  ['How do I get access after depositing?',
   'After signing up and funding your account, follow the access instructions on this page, submit confirmation, or message support — and you\'ll be added to the premium Telegram feed.'],
  ['Can beginners follow the signals?',
   'Signals are structured to be easy to copy, with clear entry, stop loss and take profit. That said, you are responsible for understanding risk and using an appropriate lot size for your account.'],
];

const faqList = document.getElementById('faqList');
FAQS.forEach(([q, a], i) => {
  const item = document.createElement('div');
  item.className = 'faq-item reveal';
  item.innerHTML = `
    <button class="faq-q" aria-expanded="false">
      <span>${q}</span>
      <i data-lucide="plus" class="icon"></i>
    </button>
    <div class="faq-a"><div class="inner">${a}</div></div>`;
  faqList.appendChild(item);

  const btn = item.querySelector('.faq-q');
  const ans = item.querySelector('.faq-a');
  btn.addEventListener('click', () => {
    const open = item.classList.toggle('open');
    btn.setAttribute('aria-expanded', open);
    ans.style.maxHeight = open ? ans.scrollHeight + 'px' : '0';
  });
});

/* ── Live feed (slow auto-scrolling signal room) ────────────────────────── */
const FEED = [
  { ic: 'trending-up', cls: 'win',  txt: 'XAUUSD · TP1 hit',        t: 'now' },
  { ic: 'send',        cls: 'info', txt: 'GBPUSD buy · alert sent', t: '2m' },
  { ic: 'check',       cls: 'win',  txt: 'BTCUSD · closed +2.4%',   t: '9m' },
  { ic: 'activity',    cls: 'info', txt: 'EURUSD · setup forming',  t: '14m' },
  { ic: 'trending-up', cls: 'win',  txt: 'USDJPY · TP2 hit',        t: '22m' },
  { ic: 'send',        cls: 'info', txt: 'ETHUSD · update posted',  t: '31m' },
];
const feedList = document.getElementById('feedList');
const feedTrack = document.createElement('div');
feedTrack.className = 'feed-track';
feedList.appendChild(feedTrack);
function feedRow(f) {
  const colors = {
    win:  ['var(--win-bg)',  'var(--win)'],
    info: ['var(--info-bg)', 'var(--info)'],
    loss: ['var(--loss-bg)', 'var(--loss)'],
  }[f.cls];
  const row = document.createElement('div');
  row.className = 'feed-item';
  row.innerHTML = `
    <span class="ic" style="background:${colors[0]};color:${colors[1]};"><i data-lucide="${f.ic}"></i></span>
    <span>${f.txt}</span>
    <span class="time">${f.t}</span>`;
  return row;
}
// render twice for a seamless loop
[...FEED, ...FEED].forEach(f => feedTrack.appendChild(feedRow(f)));

let feedOffset = 0;
const rowH = 31; // approx item height + gap
setInterval(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  feedOffset = (feedOffset + 1) % FEED.length;
  feedTrack.style.transition = 'transform .6s ease';
  feedTrack.style.transform = `translateY(-${feedOffset * rowH}px)`;
  if (feedOffset === 0) {
    setTimeout(() => { feedTrack.style.transition = 'none'; feedTrack.style.transform = 'translateY(0)'; }, 650);
  }
}, 2600);

/* ── Render all lucide icons (after dynamic content) ────────────────────── */
if (window.lucide) lucide.createIcons();

/* ── Count-up stats ─────────────────────────────────────────────────────── */
function countUp(el, target, suffix) {
  const dur = 1400, start = performance.now();
  const final = target.toLocaleString('en-US') + suffix;
  function frame(now) {
    const p = Math.min((now - start) / dur, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    const val = Math.round(target * eased);
    el.textContent = val.toLocaleString('en-US') + suffix;
    if (p < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  // Fallback: guarantee the final value even if rAF is throttled/paused.
  setTimeout(() => { el.textContent = final; }, dur + 400);
}
// assign targets from CONFIG to the four stat spans in order
const countEls = [...document.querySelectorAll('[data-count]')];
countEls.forEach((el, i) => {
  const s = CONFIG.stats[i];
  if (s) { el.dataset.target = s[0]; el.dataset.suffix = s[1]; }
});

/* ── Scroll-driven reveal + count-up + chart draw ───────────────────────────
   IntersectionObserver is unreliable inside some embedded preview iframes,
   so we use a getBoundingClientRect scroll check — works everywhere.        */
document.body.classList.add('reveal-ready');

const revealEls = [...document.querySelectorAll('.reveal, .float-card, .step, [data-reveal-stagger]')];
const chartEls  = [...document.querySelectorAll('svg.chart')];

function revealEl(el) {
  if (el.dataset.shown) return;
  el.dataset.shown = '1';
  if (el.dataset.revealStagger !== undefined) {
    el.style.animationDelay = (parseInt(el.dataset.revealStagger) * 90) + 'ms';
  }
  el.classList.add('in');
  if (el.classList.contains('stat')) {
    el.querySelectorAll('[data-count]').forEach(c => {
      if (c.dataset.done) return;
      c.dataset.done = '1';
      countUp(c, parseInt(c.dataset.target || 0), c.dataset.suffix || '');
    });
  }
}

function drawChart(svg) {
  if (svg.dataset.drawn) return;
  svg.dataset.drawn = '1';
  svg.querySelectorAll('.draw-path').forEach(path => {
    const len = path.getTotalLength();
    path.style.strokeDasharray = len;
    path.style.strokeDashoffset = len;
    path.getBoundingClientRect(); // reflow
    path.style.transition = 'stroke-dashoffset 1.8s ease';
    path.style.strokeDashoffset = '0';
    // Fallback: if the transition is throttled/paused, force the drawn state.
    setTimeout(() => { path.style.strokeDashoffset = '0'; }, 2200);
  });
  setTimeout(() => {
    svg.querySelectorAll('.hero-area, .bd-area, .hero-dot').forEach(n => {
      n.style.transition = 'opacity .6s ease';
      n.style.opacity = '1';
    });
  }, 900);
}

function checkReveal() {
  const trigger = window.innerHeight * 0.9;
  for (const el of revealEls) {
    if (!el.dataset.shown && el.getBoundingClientRect().top < trigger) revealEl(el);
  }
  for (const svg of chartEls) {
    if (!svg.dataset.drawn && svg.getBoundingClientRect().top < trigger) drawChart(svg);
  }
}

let ticking = false;
window.addEventListener('scroll', () => {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => { checkReveal(); ticking = false; });
}, { passive: true });
window.addEventListener('resize', checkReveal, { passive: true });
checkReveal();
// Safety net: never leave anything hidden, even if something above fails.
setTimeout(() => { revealEls.forEach(revealEl); chartEls.forEach(drawChart); }, 2600);

/* ── Hero price subtle flicker (cosmetic) ───────────────────────────────── */
const px = document.querySelector('[data-px-target]');
if (px && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const base = parseFloat(px.dataset.pxTarget);
  setInterval(() => {
    const v = base + (Math.random() - 0.4) * 1.6;
    px.textContent = v.toFixed(2);
  }, 2000);
}
