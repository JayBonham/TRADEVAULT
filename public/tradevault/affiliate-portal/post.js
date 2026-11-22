/* Affiliate post builder: on-brand results graphics from the affiliate's own stats + chart screenshot.
   Everything is drawn on a <canvas> in the browser (nothing is uploaded). TVPost.render(el, {code, trial, main}) */
(function () {
  var A = '/assets/';
  var SIZES = { post: [1080, 1350, 'Post 4:5'], story: [1080, 1920, 'Story 9:16'], square: [1080, 1080, 'Square 1:1'] };
  var TEMPLATES = [['score', 'Scoreboard'], ['chart', 'Chart first'], ['ring', 'Win rate'], ['receipt', 'Receipt']];
  var HEADS = { backtest: 'Backtest result', week: 'This week’s results', live: 'Live session recap', trade: 'Today’s trade', custom: 'Your own' };
  var SCANNERS = ['Killshot', 'Smartshot', 'Spectrum'];
  var MARKETS = { gold: ['Gold', 'XAUUSD'], us30: ['US30', 'US30'], nas: ['NAS100', 'NAS100'], btc: ['Bitcoin', 'BTCUSD'], other: ['', ''] };
  var UNITS = ['pips', 'points', 'R', '%'];
  var C = { bg: '#03060C', ink: '#EAF0FA', dim: '#9AA8BE', mute: '#5D6B82', blue: '#2F7BFF', blue2: '#4B9EFF', cyan: '#58E9FF', hair: 'rgba(255,255,255,.10)', red: '#FF4D63', win: '#5BE3A0' };
  var DISP = '"Instrument Sans", system-ui, sans-serif', BODY = 'Inter, system-ui, sans-serif', MONO = '"JetBrains Mono", ui-monospace, monospace';

  var S = {
    tpl: 0, size: 'post', head: 'backtest', custom: '', scanner: 'Killshot', market: 'gold', marketOther: '', tf: '',
    trades: '', wins: '', losses: '', total: '', unit: 'pips', pct: '', shot: null, zoom: 1, posX: 50, posY: 50, cta: 'auto'
  };
  var IMGS = {}, ctx0 = null, OPT = {}, PAINTING = null;

  function img(src) {
    if (IMGS[src]) return IMGS[src];
    var i = new Image(); i.src = src; IMGS[src] = i;
    i.onload = function () { draw(); };
    return i;
  }
  function ok(i) { return i && i.complete && i.naturalWidth > 0; }
  function num(v) { var n = parseFloat(String(v).replace(/[^0-9.\-]/g, '')); return isFinite(n) ? n : null; }
  function fmt(n) { return Math.abs(n) >= 1000 ? Math.round(n).toLocaleString('en-US') : String(Math.round(n * 100) / 100); }

  /* ---------- derived numbers ---------- */
  function stats() {
    var w = num(S.wins), l = num(S.losses), t = num(S.trades), tot = num(S.total), p = num(S.pct);
    if (t == null && w != null && l != null) t = w + l;
    if (l == null && t != null && w != null && t >= w) l = t - w;
    var wr = (w != null && t) ? Math.round(w / t * 100) : null;
    var mk = S.market === 'other' ? [S.marketOther.trim(), S.marketOther.trim().toUpperCase()] : MARKETS[S.market];
    return { w: w, l: l, t: t, wr: wr, tot: tot, pct: p, mk: mk[0], sym: mk[1] || 'CHART' };
  }
  function headline() { return S.head === 'custom' ? (S.custom.trim() || 'My results') : HEADS[S.head]; }
  function eyebrow(st) { return [S.scanner, st.mk, S.tf.trim()].filter(Boolean).join(' · ').toUpperCase(); }
  function totalTxt(st) {
    if (st.tot == null) return null;
    var sign = st.tot > 0 ? '+' : st.tot < 0 ? '−' : '';
    return { n: sign + fmt(Math.abs(st.tot)) + (S.unit === '%' ? '%' : S.unit === 'R' ? 'R' : ''), u: S.unit === '%' || S.unit === 'R' ? '' : S.unit };
  }
  function fine() {
    var bt = S.head === 'backtest';
    return (bt ? 'Backtest results are hypothetical and don’t reflect real trades. ' : 'Individual results, not typical. ') +
      'Past performance doesn’t guarantee future results. Trading involves risk. Educational only.';
  }

  /* ---------- canvas helpers ---------- */
  function rr(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
  function font(c, w, s, f) { c.font = w + ' ' + s + 'px ' + f; }
  function fit(c, text, maxW, size, w, f, min) { var s = size; font(c, w, s, f); while (c.measureText(text).width > maxW && s > (min || 10)) { s -= 2; font(c, w, s, f); } return s; }
  function spaced(c, text, x, y, sp, align) {
    var chars = text.split(''), total = chars.reduce(function (a, ch) { return a + c.measureText(ch).width + sp; }, -sp);
    var cx = align === 'right' ? x - total : align === 'center' ? x - total / 2 : x;
    var al = c.textAlign; c.textAlign = 'left';
    chars.forEach(function (ch) { c.fillText(ch, cx, y); cx += c.measureText(ch).width + sp; });
    c.textAlign = al; return total;
  }
  function wrap(c, text, maxW) {
    var words = text.split(/\s+/), lines = [], cur = '';
    words.forEach(function (w) { var t = cur ? cur + ' ' + w : w; if (c.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; });
    if (cur) lines.push(cur); return lines;
  }
  function seeded(seed) { var s = 0; for (var i = 0; i < seed.length; i++) s = (s * 31 + seed.charCodeAt(i)) >>> 0; return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

  // the background: deep black, blue glow, faint grid
  function backdrop(c, W, H) {
    c.fillStyle = C.bg; c.fillRect(0, 0, W, H);
    var g = c.createRadialGradient(W * 0.85, H * 0.12, 0, W * 0.85, H * 0.12, W * 0.9);
    g.addColorStop(0, 'rgba(47,123,255,.28)'); g.addColorStop(1, 'rgba(47,123,255,0)'); c.fillStyle = g; c.fillRect(0, 0, W, H);
    var g2 = c.createRadialGradient(W * 0.05, H, 0, W * 0.05, H, W * 0.8);
    g2.addColorStop(0, 'rgba(28,72,170,.22)'); g2.addColorStop(1, 'rgba(28,72,170,0)'); c.fillStyle = g2; c.fillRect(0, 0, W, H);
    c.strokeStyle = 'rgba(255,255,255,.035)'; c.lineWidth = 1;
    for (var x = 0; x <= W; x += 90) { c.beginPath(); c.moveTo(x + .5, 0); c.lineTo(x + .5, H); c.stroke(); }
    for (var y = 0; y <= H; y += 90) { c.beginPath(); c.moveTo(0, y + .5); c.lineTo(W, y + .5); c.stroke(); }
  }

  // a Killshot-style chart for when there's no screenshot: candles, two EMAs, entry stars
  function fakeChart(c, x, y, w, h, seed) {
    var r = seeded(seed || 'tv'), n = Math.max(28, Math.round(w / 22)), cw = w / n, p = [], v = 100;
    for (var i = 0; i < n; i++) { var o = v; v += (r() - 0.42) * 3.2; var hi = Math.max(o, v) + r() * 1.6, lo = Math.min(o, v) - r() * 1.6; p.push([o, v, hi, lo]); }
    var mx = Math.max.apply(null, p.map(function (q) { return q[2]; })), mn = Math.min.apply(null, p.map(function (q) { return q[3]; }));
    var Y = function (val) { return y + 18 + (h - 36) * (1 - (val - mn) / (mx - mn || 1)); };
    var ema = function (k) { var e = p[0][1], a = 2 / (k + 1); return p.map(function (q) { e = q[1] * a + e * (1 - a); return e; }); };
    [[ema(9), C.red], [ema(21), C.blue2]].forEach(function (L) {
      c.strokeStyle = L[1]; c.lineWidth = 2.5; c.globalAlpha = .9; c.beginPath();
      L[0].forEach(function (e, i) { var X = x + cw * (i + .5); if (i) c.lineTo(X, Y(e)); else c.moveTo(X, Y(e)); }); c.stroke(); c.globalAlpha = 1;
    });
    p.forEach(function (q, i) {
      var X = x + cw * (i + .5), up = q[1] >= q[0];
      c.strokeStyle = up ? 'rgba(234,240,250,.6)' : 'rgba(47,123,255,.9)'; c.lineWidth = 1.5;
      c.beginPath(); c.moveTo(X, Y(q[2])); c.lineTo(X, Y(q[3])); c.stroke();
      c.fillStyle = up ? '#EAF0FA' : C.blue; var t = Y(Math.max(q[0], q[1])), b = Y(Math.min(q[0], q[1]));
      c.fillRect(X - cw * .3, t, cw * .6, Math.max(2, b - t));
      if (i > 3 && i % 7 === 3) { c.fillStyle = C.cyan; c.font = '700 ' + Math.round(cw * .9) + 'px ' + BODY; c.textAlign = 'center'; c.fillText('★', X, Y(q[3]) + cw * 1.1); c.textAlign = 'left'; }
    });
  }

  // a chart window: screenshot (cover, zoom + position) or the drawn chart, with a terminal-style title bar
  function chartWin(c, x, y, w, h, st, opt) {
    opt = opt || {};
    var bar = opt.noBar ? 0 : 46, rad = opt.r == null ? 22 : opt.r;
    c.save();
    if (!opt.bare) { c.shadowColor = 'rgba(47,123,255,.45)'; c.shadowBlur = 50; }
    rr(c, x, y, w, h, rad); c.fillStyle = '#070C16'; c.fill(); c.restore();
    c.save(); rr(c, x, y, w, h, rad); c.clip();
    var iy = y + bar, ih = h - bar;
    if (S.shot && ok(S.shot)) {
      var im = S.shot, sc = Math.max(w / im.naturalWidth, ih / im.naturalHeight) * S.zoom;
      var dw = im.naturalWidth * sc, dh = im.naturalHeight * sc;
      var dx = x + (w - dw) * (S.posX / 100), dy = iy + (ih - dh) * (S.posY / 100);
      if (PAINTING && !opt.bg) PAINTING._geo = { w: w, ih: ih, dw: dw, dh: dh };
      c.drawImage(im, dx, dy, dw, dh);
    } else {
      fakeChart(c, x + 10, iy + 8, w - 20, ih - 16, eyebrow(st) + S.unit);
    }
    if (bar) {
      c.fillStyle = 'rgba(8,14,26,.92)'; c.fillRect(x, y, w, bar);
      c.fillStyle = C.hair; c.fillRect(x, y + bar - 1, w, 1);
      [C.red, '#F5B85C', C.win].forEach(function (col, i) { c.fillStyle = col; c.beginPath(); c.arc(x + 26 + i * 20, y + bar / 2, 5.5, 0, 7); c.fill(); });
      c.fillStyle = C.dim; font(c, 500, 17, MONO); c.textBaseline = 'middle';
      spaced(c, (st.sym + (S.tf.trim() ? ' · ' + S.tf.trim() : '') + (S.scanner ? ' · ' + S.scanner : '')).toUpperCase(), x + 96, y + bar / 2 + 1, 2);
      c.fillStyle = C.cyan; spaced(c, 'THE TRADE VAULT', x + w - 22, y + bar / 2 + 1, 2, 'right');
      c.textBaseline = 'alphabetic';
    }
    c.restore();
    c.save(); rr(c, x + .5, y + .5, w - 1, h - 1, rad); c.strokeStyle = 'rgba(75,158,255,.45)'; c.lineWidth = 1.5; c.stroke(); c.restore();
  }

  function logo(c, x, y, h) {
    var L = img(A + 'tv-logo.png');
    if (ok(L)) c.drawImage(L, x, y, L.naturalWidth * h / L.naturalHeight, h);
    return ok(L) ? L.naturalWidth * h / L.naturalHeight : 0;
  }
  function chip(c, text, x, y, opt) {
    opt = opt || {}; font(c, 500, opt.size || 19, MONO);
    var sp = 3, tw = text.split('').reduce(function (a, ch) { return a + c.measureText(ch).width + sp; }, -sp), pad = 20, h = (opt.size || 19) + 24;
    var w = tw + pad * 2 + (opt.dot ? 18 : 0), X = opt.align === 'right' ? x - w : x;
    rr(c, X, y, w, h, h / 2);
    if (opt.fill) { c.fillStyle = opt.fill; c.fill(); } else { c.fillStyle = 'rgba(47,123,255,.12)'; c.fill(); c.strokeStyle = 'rgba(75,158,255,.55)'; c.lineWidth = 1.5; c.stroke(); }
    if (opt.dot) { c.fillStyle = C.cyan; c.beginPath(); c.arc(X + pad + 4, y + h / 2, 5, 0, 7); c.fill(); }
    c.fillStyle = opt.color || C.ink; c.textBaseline = 'middle'; spaced(c, text, X + pad + (opt.dot ? 18 : 0), y + h / 2 + 1, sp); c.textBaseline = 'alphabetic';
    return { w: w, h: h };
  }
  function header(c, W, pad, y) {
    logo(c, pad, y, 34);
    chip(c, headline().toUpperCase().slice(0, 26), W - pad, y - 8, { align: 'right', dot: true, size: 16 });
    return y + 34;
  }
  function footer(c, W, H, pad) {
    var y = H - pad, fs = 15;
    font(c, 400, fs, BODY); c.fillStyle = C.mute;
    var lines = wrap(c, fine(), W - pad * 2);
    for (var i = lines.length - 1; i >= 0; i--) { c.fillText(lines[i], pad, y); y -= fs * 1.4; }
    y -= 26;
    var h = 74, cta = S.cta === 'auto' ? (S.size === 'story' ? 'link' : 'bio') : S.cta;
    // CTA pill: affiliates share their own trial link (link in bio / story link sticker), so no code here
    var label = 'Start 7 days free →';
    font(c, 700, 30, DISP); var tw = c.measureText(label).width, pw = tw + 64;
    c.save(); c.shadowColor = 'rgba(47,123,255,.6)'; c.shadowBlur = 36; rr(c, pad, y - h, pw, h, h / 2); c.fillStyle = C.blue; c.fill(); c.restore();
    c.fillStyle = '#fff'; c.textBaseline = 'middle'; c.fillText(label, pad + 32, y - h / 2 + 1); c.textBaseline = 'alphabetic';
    var line = cta === 'bio' ? 'Link in bio' : cta === 'link' ? 'Tap the link' : '';
    c.textBaseline = 'middle';
    if (line) {
      font(c, 600, 26, DISP); c.fillStyle = C.ink; c.fillText(line, pad + pw + 28, y - h / 2 - 13);
      font(c, 500, 15, MONO); c.fillStyle = C.dim; spaced(c, 'THETRADEVAULT.CO', pad + pw + 28, y - h / 2 + 18, 2);
    } else {
      font(c, 500, 17, MONO); c.fillStyle = C.dim; spaced(c, 'THETRADEVAULT.CO', pad + pw + 28, y - h / 2 + 1, 2);
    }
    c.textBaseline = 'alphabetic';
    return y - h; // top of the footer block
  }
  function statBox(c, x, y, w, h, label, value, hl) {
    rr(c, x, y, w, h, 18);
    if (hl) { var g = c.createLinearGradient(x, y, x, y + h); g.addColorStop(0, 'rgba(47,123,255,.42)'); g.addColorStop(1, 'rgba(47,123,255,.14)'); c.fillStyle = g; c.fill(); c.strokeStyle = 'rgba(88,233,255,.6)'; }
    else { c.fillStyle = 'rgba(255,255,255,.035)'; c.fill(); c.strokeStyle = C.hair; }
    c.lineWidth = 1.5; c.stroke();
    var vs = fit(c, value, w - 30, Math.min(64, h * .46), 700, DISP, 20);
    c.fillStyle = C.ink; c.fillText(value, x + 22, y + 24 + vs * .82);
    font(c, 500, 15, MONO); c.fillStyle = hl ? C.cyan : C.dim; spaced(c, label.toUpperCase(), x + 22, y + h - 22, 2.5);
  }
  function statItems(st) {
    var out = [];
    if (st.t != null) out.push(['Trades', fmt(st.t)]);
    if (st.w != null) out.push(['Wins', fmt(st.w)]);
    if (st.l != null) out.push(['Losses', fmt(st.l)]);
    if (st.wr != null) out.push(['Win rate', st.wr + '%', 1]);
    return out;
  }
  function statRow(c, x, y, w, h, items) {
    if (!items.length) return 0;
    var gap = 14, bw = (w - gap * (items.length - 1)) / items.length;
    items.forEach(function (it, i) { statBox(c, x + i * (bw + gap), y, bw, h, it[0], it[1], it[2]); });
    return h;
  }
  function heroTotal(c, x, y, maxW, size, st, align) {
    var T = totalTxt(st); if (!T) return 0;
    var s = fit(c, T.n, maxW - (T.u ? 160 : 0), size, 700, DISP, 60);
    var uw = 0;
    if (T.u && align === 'center') { font(c, 600, Math.round(s * .3), DISP); uw = c.measureText(T.u).width + 14; font(c, 700, s, DISP); x -= uw / 2; }
    c.save(); c.textAlign = align || 'left';
    var g = c.createLinearGradient(0, y - s, 0, y); g.addColorStop(0, '#FFFFFF'); g.addColorStop(1, '#9CC6FF');
    c.fillStyle = g; c.shadowColor = 'rgba(75,158,255,.55)'; c.shadowBlur = 40; c.fillText(T.n, x, y); c.restore();
    var w = c.measureText(T.n).width;
    if (T.u) { font(c, 600, Math.round(s * .3), DISP); c.fillStyle = C.blue2; c.save(); c.textAlign = 'left'; c.fillText(T.u, (align === 'center' ? x + w / 2 : x + w) + 14, y); c.restore(); }
    return s;
  }

  /* ---------- templates ---------- */
  function tScore(c, W, H, st) {
    var pad = 72; backdrop(c, W, H);
    var y = header(c, W, pad, pad) + 58;
    var eb = eyebrow(st);
    if (eb) { font(c, 500, 20, MONO); c.fillStyle = C.blue2; spaced(c, eb, pad, y, 4); y += 22; }
    var hs = fit(c, headline(), W - pad * 2, H > 1500 ? 92 : 78, 700, DISP, 40);
    y += hs * .95; c.fillStyle = C.ink; c.fillText(headline(), pad, y);
    var T = totalTxt(st);
    if (T) {
      y += (H > 1500 ? 210 : H > 1200 ? 170 : 150);
      var s = heroTotal(c, pad - 4, y, W - pad * 2, H > 1500 ? 220 : H > 1200 ? 180 : 150, st);
      if (st.pct != null) { var pt = (st.pct > 0 ? '+' : '') + st.pct + '%'; var cw = chip(c, pt, W - pad, y - s * .62, { align: 'right', size: 24, fill: 'rgba(47,123,255,.9)', color: '#fff' }); }
    } else if (st.pct != null) {
      y += 150; heroTotal(c, pad, y, W - pad * 2, 150, { tot: st.pct, }, 'left');
    }
    var items = statItems(st);
    var top = footer(c, W, H, pad);
    if (items.length) { y += 40; statRow(c, pad, y, W - pad * 2, H > 1200 ? 132 : 112, items); y += (H > 1200 ? 132 : 112); }
    var ch = top - 44 - (y + 40);
    if (ch > 180) chartWin(c, pad, y + 40, W - pad * 2, ch, st);
  }

  function tChart(c, W, H, st) {
    var pad = 72; backdrop(c, W, H);
    var top = footer(c, W, H, pad);
    var imgH = Math.round(H * (H > 1500 ? .56 : H > 1200 ? .46 : .4));
    chartWin(c, 0, 0, W, imgH + 40, st, { noBar: true, r: 0, bare: true });
    var g = c.createLinearGradient(0, imgH * .45, 0, imgH + 40); g.addColorStop(0, 'rgba(3,6,12,0)'); g.addColorStop(1, C.bg);
    c.fillStyle = g; c.fillRect(0, 0, W, imgH + 41);
    var g2 = c.createLinearGradient(0, 0, 0, 160); g2.addColorStop(0, 'rgba(3,6,12,.85)'); g2.addColorStop(1, 'rgba(3,6,12,0)'); c.fillStyle = g2; c.fillRect(0, 0, W, 160);
    header(c, W, pad, pad - 16);
    var y = imgH + 10;
    var eb = eyebrow(st);
    if (eb) { font(c, 500, 20, MONO); c.fillStyle = C.cyan; spaced(c, eb, pad, y, 4); y += 18; }
    var hs = fit(c, headline(), W - pad * 2, 72, 700, DISP, 36); y += hs; c.fillStyle = C.ink; c.fillText(headline(), pad, y);
    var avail = top - 40 - y;
    var T = totalTxt(st);
    var ringR = st.wr != null ? Math.min(H > 1500 ? 140 : 110, avail * .36) : 0;
    if (T) {
      var by = y + Math.min(avail * .55, H > 1500 ? 300 : 200);
      heroTotal(c, pad - 4, by, W - pad * 2 - (ringR ? ringR * 2 + 40 : 0), H > 1500 ? 210 : H > 1200 ? 170 : 130, st);
      if (ringR) ring(c, W - pad - ringR, by - ringR * .78, ringR, st.wr, 'WIN RATE', 14);
      y = by;
    } else if (ringR) { ring(c, pad + ringR, y + 40 + ringR, ringR, st.wr, 'WIN RATE', 14); y += 40 + ringR * 2; }
    var parts = [];
    if (st.t != null) parts.push(fmt(st.t) + ' TRADES');
    if (st.w != null) parts.push(fmt(st.w) + ' WINS');
    if (st.l != null) parts.push(fmt(st.l) + ' LOSSES');
    if (st.pct != null && T) parts.push((st.pct > 0 ? '+' : '') + st.pct + '%');
    if (parts.length && y + 60 < top - 20) {
      y += 54; c.fillStyle = C.hair; c.fillRect(pad, y - 34, W - pad * 2, 1);
      font(c, 500, 22, MONO); c.fillStyle = C.dim; spaced(c, parts.join('  ·  '), pad, y + 4, 2.5);
    }
  }

  function ring(c, cx, cy, r, pctv, label, lw) {
    lw = lw || r * .14;
    c.save(); c.lineCap = 'round';
    c.strokeStyle = 'rgba(255,255,255,.08)'; c.lineWidth = lw; c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.stroke();
    var g = c.createLinearGradient(cx - r, cy - r, cx + r, cy + r); g.addColorStop(0, C.cyan); g.addColorStop(1, C.blue);
    c.strokeStyle = g; c.shadowColor = 'rgba(75,158,255,.7)'; c.shadowBlur = r * .3;
    c.beginPath(); c.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.max(0, Math.min(100, pctv)) / 100); c.stroke(); c.restore();
    c.save(); c.textAlign = 'center'; c.fillStyle = C.ink;
    var s = fit(c, pctv + '%', r * 1.35, r * .62, 700, DISP, 20); c.fillText(pctv + '%', cx, cy + s * .3);
    font(c, 600, Math.max(12, Math.round(r * .12)), MONO); c.fillStyle = C.cyan; spaced(c, label, cx, cy + s * .3 + r * .26, 3, 'center');
    c.restore();
  }

  function tRing(c, W, H, st) {
    var pad = 72; backdrop(c, W, H);
    // the screenshot, faint, behind everything
    if (S.shot && ok(S.shot)) {
      c.save(); c.globalAlpha = .16; chartWin(c, 0, 0, W, H, st, { noBar: true, r: 0, bare: true }); c.restore();
      if (PAINTING) { var im0 = S.shot, sc0 = Math.max(W / im0.naturalWidth, H / im0.naturalHeight) * S.zoom; PAINTING._geo = { w: W, ih: H, dw: im0.naturalWidth * sc0, dh: im0.naturalHeight * sc0 }; }
      var g = c.createLinearGradient(0, 0, 0, H); g.addColorStop(0, 'rgba(3,6,12,.4)'); g.addColorStop(.5, 'rgba(3,6,12,.75)'); g.addColorStop(1, C.bg); c.fillStyle = g; c.fillRect(0, 0, W, H);
    }
    var y = header(c, W, pad, pad) + 70;
    var eb = eyebrow(st);
    c.save(); c.textAlign = 'center';
    if (eb) { font(c, 500, 20, MONO); c.fillStyle = C.blue2; spaced(c, eb, W / 2, y, 4, 'center'); y += 22; }
    var hs = fit(c, headline(), W - pad * 2, 80, 700, DISP, 36); y += hs; c.fillStyle = C.ink; c.fillText(headline(), W / 2, y);
    c.restore();
    var top = footer(c, W, H, pad);
    var items = statItems(st).filter(function (it) { return it[0] !== 'Win rate'; });
    var T = totalTxt(st);
    var below = (items.length ? 140 : 0) + (T && st.wr != null ? 120 : 0);
    var space = top - 50 - y - below;
    var r = Math.max(90, Math.min(260, space / 2 - 40));
    var cy = y + 40 + (space - r * 2) / 2 + r;
    if (st.wr != null) ring(c, W / 2, cy, r, st.wr, 'WIN RATE');
    else if (T) { c.save(); c.textAlign = 'center'; heroTotal(c, W / 2, cy + 50, W - pad * 2, 200, st, 'center'); c.restore(); }
    else {
      c.save(); c.lineWidth = r * .14; c.strokeStyle = 'rgba(255,255,255,.08)'; c.beginPath(); c.arc(W / 2, cy, r, 0, Math.PI * 2); c.stroke();
      c.textAlign = 'center'; font(c, 600, Math.round(r * .2), DISP); c.fillStyle = C.dim; c.fillText('Add your numbers', W / 2, cy + r * .07); c.restore();
    }
    y = cy + r + 40;
    if (T && st.wr != null) {
      c.save(); c.textAlign = 'center'; heroTotal(c, W / 2, y + 90, W - pad * 2, 110, st, 'center'); c.restore(); y += 120;
    }
    if (items.length) statRow(c, pad, y + 10, W - pad * 2, 110, items.map(function (it) { return [it[0], it[1]]; }));
  }

  function tReceipt(c, W, H, st) {
    var pad = 72; backdrop(c, W, H);
    var y0 = header(c, W, pad, pad) + 48, top = footer(c, W, H, pad);
    var x = pad + 20, w = W - pad * 2 - 40, h = top - 40 - y0;
    // the ticket
    c.save(); c.shadowColor = 'rgba(47,123,255,.35)'; c.shadowBlur = 60; rr(c, x, y0, w, h, 26); c.fillStyle = '#0A1220'; c.fill(); c.restore();
    c.save(); rr(c, x + .5, y0 + .5, w - 1, h - 1, 26); c.strokeStyle = 'rgba(75,158,255,.35)'; c.lineWidth = 1.5; c.stroke(); c.restore();
    var ix = x + 44, iw = w - 88, y = y0 + 64;
    font(c, 500, 18, MONO); c.fillStyle = C.blue2; spaced(c, 'TRADE VAULT · RESULTS', ix, y, 4);
    c.textAlign = 'right'; c.fillStyle = C.mute; var d = new Date();
    spaced(c, d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase(), ix + iw, y, 2, 'right'); c.textAlign = 'left';
    y += 30; var hs = fit(c, headline(), iw, 64, 700, DISP, 30); y += hs; c.fillStyle = C.ink; c.fillText(headline(), ix, y);
    var dash = function (yy) { c.save(); c.setLineDash([8, 8]); c.strokeStyle = 'rgba(255,255,255,.16)'; c.lineWidth = 2; c.beginPath(); c.moveTo(ix, yy); c.lineTo(ix + iw, yy); c.stroke(); c.restore(); };
    y += 36; dash(y);
    var rows = [];
    if (S.scanner) rows.push(['Scanner', S.scanner]);
    if (st.mk) rows.push(['Market', st.mk]);
    if (S.tf.trim()) rows.push(['Timeframe', S.tf.trim()]);
    if (st.t != null) rows.push(['Trades', fmt(st.t)]);
    if (st.w != null) rows.push(['Wins', fmt(st.w)]);
    if (st.l != null) rows.push(['Losses', fmt(st.l)]);
    if (st.wr != null) rows.push(['Win rate', st.wr + '%']);
    if (st.pct != null && st.tot != null) rows.push(['Return', (st.pct > 0 ? '+' : '') + st.pct + '%']);
    var T = totalTxt(st);
    var totH = T ? (H > 1200 ? 150 : 110) : 0, shotMin = H > 1200 ? 200 : 0;
    var rowH = Math.min(64, Math.max(30, (h - (y - y0) - totH - 60 - (S.shot ? shotMin : 0)) / Math.max(rows.length, 1)));
    rows.forEach(function (r) {
      y += rowH; font(c, 500, Math.round(rowH * .38), MONO); c.fillStyle = C.dim; spaced(c, r[0].toUpperCase(), ix, y - rowH * .32, 2.5);
      font(c, 600, Math.round(rowH * .46), DISP); c.fillStyle = C.ink; c.textAlign = 'right'; c.fillText(r[1], ix + iw, y - rowH * .3); c.textAlign = 'left';
      c.fillStyle = 'rgba(255,255,255,.05)'; c.fillRect(ix, y, iw, 1);
    });
    if (T) {
      y += H > 1200 ? 24 : 14; dash(y); y += H > 1200 ? 34 : 26;
      font(c, 500, 20, MONO); c.fillStyle = C.cyan; spaced(c, 'TOTAL', ix, y + 4, 4);
      c.save(); c.textAlign = 'right'; var s = fit(c, T.n + (T.u ? ' ' + T.u : ''), iw - 160, H > 1200 ? 92 : 64, 700, DISP, 40);
      c.shadowColor = 'rgba(75,158,255,.6)'; c.shadowBlur = 30; c.fillStyle = C.ink; c.fillText(T.n + (T.u ? ' ' + T.u : ''), ix + iw, y + s * .7); c.restore();
      y += s * .7 + 10;
    }
    var left = y0 + h - 44 - (y + 30);
    if (S.shot && left > 160) chartWin(c, ix, y + 30, iw, left, st, { noBar: true, r: 16, bare: true });
    else if (left > 160) { c.save(); rr(c, ix, y + 30, iw, left, 16); c.clip(); c.globalAlpha = .55; fakeChart(c, ix, y + 30, iw, left, eyebrow(st)); c.restore(); }
    // ticket notches
    c.fillStyle = C.bg; [y0 + 170].forEach(function (ny) { c.beginPath(); c.arc(x, ny, 16, 0, 7); c.fill(); c.beginPath(); c.arc(x + w, ny, 16, 0, 7); c.fill(); });
  }

  var DRAW = { score: tScore, chart: tChart, ring: tRing, receipt: tReceipt };

  function paint(cv, key, size) {
    var sz = SIZES[size || S.size]; cv.width = sz[0]; cv.height = sz[1];
    var c = cv.getContext('2d'); c.textBaseline = 'alphabetic'; c.textAlign = 'left';
    PAINTING = cv; cv._geo = null;
    try { DRAW[key || TEMPLATES[S.tpl][0]](c, sz[0], sz[1], stats()); } finally { PAINTING = null; }
  }

  /* ---------- UI ---------- */
  var CSS = '' +
    '.pb{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,420px);gap:24px;align-items:start;margin-top:20px}' +
    '.pb-prev{position:sticky;top:96px;display:flex;flex-direction:column;gap:14px;min-width:0}' +
    '.pb-stage{position:relative;border-radius:18px;overflow:hidden;border:1px solid var(--hair);background:#03060C;display:flex;justify-content:center}' +
    '.pb-stage canvas{display:block;width:100%;height:auto;max-height:72vh;object-fit:contain}' +
    '.pb-nav{position:absolute;top:50%;transform:translateY(-50%);width:44px;height:44px;border-radius:50%;border:1px solid var(--hair-2);background:rgba(5,10,20,.75);display:grid;place-items:center;cursor:pointer;color:var(--tx);backdrop-filter:blur(6px)}' +
    '.pb-nav.l{left:12px}.pb-nav.r{right:12px}' +
    '.pb-thumbs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}' +
    '.pb-thumbs button{border:1px solid var(--hair);border-radius:12px;background:#03060C;padding:0;overflow:hidden;cursor:pointer;opacity:.6;transition:opacity .2s,border-color .2s}' +
    '.pb-thumbs button.on{opacity:1;border-color:var(--acc)}.pb-thumbs canvas{display:block;width:100%;height:auto}' +
    '.pb-thumbs span{display:block;font-size:11.5px;color:var(--tx-dim);padding:6px 4px;text-align:center}' +
    '.pb-acts{display:flex;gap:10px;flex-wrap:wrap}.pb-acts .btn{min-height:48px;padding:12px 24px;font-size:15.5px}' +
    '.pb-form{display:flex;flex-direction:column;gap:18px;min-width:0}' +
    '.pb-g{border:1px solid var(--hair);border-radius:18px;padding:18px;background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,.01)),var(--g1);display:flex;flex-direction:column;gap:14px}' +
    '.pb-g h3{font-family:var(--display);font-size:15px;font-weight:600;display:flex;align-items:center;gap:10px}' +
    '.pb-g h3 i{font-style:normal;font-family:var(--mono);font-size:11px;color:#58E9FF;letter-spacing:.1em}' +
    '.pb-seg{display:flex;flex-wrap:wrap;gap:8px}' +
    '.pb-seg button{border:1px solid var(--hair-2);background:rgba(255,255,255,.03);border-radius:999px;padding:8px 14px;font-size:13.5px;cursor:pointer;color:var(--tx-dim)}' +
    '.pb-seg button.on{background:rgba(var(--acc-rgb),.18);border-color:var(--acc);color:var(--tx)}' +
    '.pb-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.pb-row.two{grid-template-columns:repeat(2,minmax(0,1fr))}' +
    '.pb-f{display:flex;flex-direction:column;gap:6px;min-width:0}.pb-f label{font-size:12px;color:var(--tx-mute)}' +
    '.pb-f input,.pb-f select{width:100%;min-width:0;border:1px solid var(--hair-2);background:rgba(0,0,0,.25);border-radius:12px;padding:10px 12px;font-size:15px;color:var(--tx)}' +
    '.pb-f input:focus,.pb-f select:focus{outline:none;border-color:var(--acc)}' +
    '.pb-drop{border:1.5px dashed var(--hair-2);border-radius:14px;padding:18px;text-align:center;cursor:pointer;color:var(--tx-dim);font-size:14px;transition:border-color .2s,background .2s}' +
    '.pb-drop:hover,.pb-drop.over{border-color:var(--acc);background:rgba(var(--acc-rgb),.06)}' +
    '.pb-drop b{color:var(--tx)}.pb-shot{display:flex;gap:12px;align-items:center}.pb-shot img{width:84px;height:56px;object-fit:cover;border-radius:8px;border:1px solid var(--hair)}' +
    '.pb-f input[type=range]{padding:0;accent-color:var(--acc)}' +
    '.pb-cap{white-space:pre-wrap;font-size:13.5px;color:var(--tx-dim);background:rgba(0,0,0,.25);border:1px solid var(--hair);border-radius:12px;padding:12px;max-height:180px;overflow:auto}' +
    '.pb-note{font-size:12.5px;color:var(--tx-mute)}' +
    '.pb-chk{display:flex;gap:10px;align-items:center;font-size:14px;color:var(--tx-dim)}.pb-chk input{accent-color:var(--acc);width:18px;height:18px}' +
    '.pb-shot .pb-acts{margin-left:auto;flex-wrap:nowrap}.pb-shot .btn-g{min-height:40px}' +
    '.pb-m{position:fixed;inset:0;z-index:1000;background:rgba(2,5,10,.97);display:flex;flex-direction:column;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}' +
    '.pb-m-top{display:flex;align-items:center;gap:10px;padding:12px max(16px,env(safe-area-inset-left,0px)) 10px max(16px,env(safe-area-inset-right,0px))}' +
    '.pb-m-top b{flex:1;font-family:var(--display);font-size:16px;text-align:center}' +
    '.pb-x{width:40px;height:40px;border-radius:50%;border:1px solid var(--hair-2);background:transparent;color:var(--tx);font-size:18px;cursor:pointer}' +
    '.pb-m-stage{flex:1;min-height:0;position:relative;display:flex;align-items:center;justify-content:center;padding:0 16px}' +
    '.pb-m-stage canvas{display:block;max-width:100%;max-height:calc(100dvh - 250px);width:auto;height:auto;border-radius:12px;touch-action:none;box-shadow:0 20px 60px rgba(0,0,0,.6)}' +
    '.pb-m-stage.drag canvas{cursor:grab}.pb-m-stage.drag canvas:active{cursor:grabbing}' +
    '.pb-m .pb-nav{background:rgba(5,10,20,.85)}.pb-m .pb-nav.l{left:4px}.pb-m .pb-nav.r{right:4px}' +
    '.pb-m-ctl{display:flex;flex-direction:column;gap:8px;padding:12px 16px 4px;align-items:center}' +
    '.pb-m-hint{font-size:13px;color:var(--tx-dim);text-align:center}' +
    '.pb-zoom{display:flex;align-items:center;gap:12px;width:100%;max-width:420px}.pb-zoom input{flex:1;accent-color:var(--acc)}' +
    '.pb-zoom button{width:36px;height:36px;border-radius:50%;border:1px solid var(--hair-2);background:transparent;color:var(--tx);font-size:18px;cursor:pointer}' +
    '.pb-dots{display:flex;gap:6px;align-items:center;font-size:12.5px;color:var(--tx-mute)}.pb-dots i{width:6px;height:6px;border-radius:50%;background:var(--hair-2)}.pb-dots i.on{background:var(--acc)}' +
    '.pb-m-acts{display:flex;gap:10px;padding:12px max(16px,env(safe-area-inset-left,0px)) 16px max(16px,env(safe-area-inset-right,0px));justify-content:center}.pb-m-acts .btn{flex:1;max-width:320px;min-height:50px}' +
    '.pb-bar{display:none}' +
    '@media (max-width:1060px){.pb{grid-template-columns:minmax(0,1fr);padding-bottom:110px}.pb-prev{position:static}.pb-stage canvas{max-height:none}' +
      '.pb-bar{position:fixed;left:0;right:0;bottom:0;z-index:60;display:flex;align-items:center;gap:12px;padding:10px max(16px,env(safe-area-inset-right,0px)) calc(10px + env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px));background:rgba(5,10,20,.95);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);border-top:1px solid var(--hair-2)}' +
      '.pb-bar canvas{height:68px;width:auto;border-radius:6px;border:1px solid var(--hair-2);cursor:pointer;flex:none}' +
      '.pb-bar .t{flex:1;min-width:0;display:flex;flex-direction:column;gap:4px}.pb-bar .t b{font-size:14px;font-family:var(--display)}.pb-bar .t .sw{display:flex;gap:6px;align-items:center}' +
      '.pb-bar .ar{width:34px;height:34px;border-radius:50%;border:1px solid var(--hair-2);background:transparent;color:var(--tx);font-size:16px;cursor:pointer}' +
      '.pb-bar .btn{min-height:46px;padding:10px 20px;font-size:15px;flex:none}}' +
    '@media (max-width:520px){.pb-row{grid-template-columns:repeat(2,minmax(0,1fr))}.pb-thumbs{gap:6px}}';

  function seg(key, opts) {
    return '<div class="pb-seg" data-seg="' + key + '">' + opts.map(function (o) { return '<button type="button" data-v="' + o[0] + '"' + (String(S[key]) === String(o[0]) ? ' class="on"' : '') + '>' + o[1] + '</button>'; }).join('') + '</div>';
  }
  function field(key, label, ph, type) {
    return '<div class="pb-f"><label for="pb-' + key + '">' + label + '</label><input id="pb-' + key + '" data-k="' + key + '" ' + (type === 'num' ? 'inputmode="decimal" ' : '') + 'placeholder="' + ph + '" value="' + String(S[key]).replace(/"/g, '&quot;') + '"></div>';
  }
  function caption() {
    var st = stats(), T = totalTxt(st), bits = [];
    if (T) bits.push(T.n + (T.u ? ' ' + T.u : ''));
    if (st.wr != null) bits.push(st.wr + '% win rate');
    if (st.t != null) bits.push(fmt(st.t) + ' trades');
    var what = [S.scanner, st.mk, S.tf.trim()].filter(Boolean).join(' · ');
    var link = OPT.trial || OPT.main || '';
    return headline() + (what ? ' · ' + what : '') + (bits.length ? '\n\n' + bits.join(' · ') : '') +
      '\n\nThis is what trading with rules looks like inside The Trade Vault: the scanners flag the setup, the educators trade it live, and you follow the plan.' +
      '\n\nTry it free for 7 days 👇\n' + link + ((S.cta === 'auto' ? S.size !== 'story' : S.cta === 'bio') ? '\n(On Instagram: tap the link in my bio)' : '') +
      '\n\n' + (S.head === 'backtest' ? 'Backtest results, hypothetical. ' : '') + 'Results not typical. Trading involves risk. (Affiliate link: I earn a commission if you join.)';
  }

  var root, stage, thumbs = [], MODAL = null, saveFn = null;
  function draw() {
    if (!stage) return;
    paint(stage);
    thumbs.forEach(function (t, i) { paint(t, TEMPLATES[i][0]); });
    var mini = root.querySelector('#pbMini');
    if (mini && getComputedStyle(root.querySelector('.pb-bar')).display !== 'none') {
      mini.width = Math.round(stage.width / 8); mini.height = Math.round(stage.height / 8); mini.getContext('2d').drawImage(stage, 0, 0, mini.width, mini.height);
    }
    var bt = root.querySelector('#pbBarT'); if (bt) bt.textContent = TEMPLATES[S.tpl][1] + ' · ' + SIZES[S.size][2];
    if (MODAL && !MODAL.hidden) { paint(MODAL.querySelector('canvas')); syncModal(); }
    var cap = root.querySelector('.pb-cap'); if (cap) cap.textContent = caption();
  }
  var pend = 0;
  function redraw() { if (pend) return; pend = requestAnimationFrame(function () { pend = 0; draw(); }); }

  var PICK = function () {};
  function syncModal() {
    var M = MODAL; if (!M) return;
    var has = !!S.shot;
    M.querySelector('.pb-m-stage').classList.toggle('drag', has);
    M.querySelector('.pb-zoom').hidden = !has;
    M.querySelector('.pb-m-hint').textContent = has ? 'Drag the chart to move it · pinch or slide to zoom' : 'Swipe through the templates with the arrows';
    M.querySelector('#pbMZ').value = S.zoom;
    M.querySelector('.pb-dots').innerHTML = TEMPLATES.map(function (t, i) { return '<i' + (i === S.tpl ? ' class="on"' : '') + '></i>'; }).join('') + '<span style="margin-left:6px">' + TEMPLATES[S.tpl][1] + '</span>';
  }
  function openModal(adjust) {
    if (!MODAL) {
      var M = MODAL = document.createElement('div'); M.className = 'pb-m'; M.hidden = true;
      M.setAttribute('role', 'dialog'); M.setAttribute('aria-modal', 'true'); M.setAttribute('aria-label', 'Post preview');
      M.innerHTML = '<div class="pb-m-top"><button type="button" class="pb-x" data-close aria-label="Close">✕</button><b>Preview</b><span style="width:40px"></span></div>' +
        '<div class="pb-m-stage"><canvas></canvas><button type="button" class="pb-nav l" data-mstep="-1" aria-label="Previous template">‹</button><button type="button" class="pb-nav r" data-mstep="1" aria-label="Next template">›</button></div>' +
        '<div class="pb-m-ctl"><div class="pb-m-hint"></div><div class="pb-zoom"><button type="button" data-z="-1" aria-label="Zoom out">−</button><input type="range" id="pbMZ" min="1" max="3" step="0.02" aria-label="Zoom"><button type="button" data-z="1" aria-label="Zoom in">+</button></div><div class="pb-dots"></div></div>' +
        '<div class="pb-m-acts"><button type="button" class="btn-g" data-close style="min-height:50px;padding:0 22px">Done</button><button type="button" class="btn" data-save>Save image</button></div>';
      document.body.appendChild(M);
      M.addEventListener('click', function (e) {
        var b = e.target.closest('button'); if (!b) return;
        if (b.hasAttribute('data-close')) return closeModal();
        if (b.hasAttribute('data-save')) return saveFn && saveFn(b);
        if (b.hasAttribute('data-mstep')) return PICK((S.tpl + +b.getAttribute('data-mstep') + TEMPLATES.length) % TEMPLATES.length);
        if (b.hasAttribute('data-z')) { S.zoom = Math.max(1, Math.min(3, S.zoom + .15 * +b.getAttribute('data-z'))); redraw(); }
      });
      M.querySelector('#pbMZ').addEventListener('input', function () { S.zoom = +this.value; redraw(); });
      document.addEventListener('keydown', function (e) { if (!M.hidden && e.key === 'Escape') closeModal(); });
      // drag to move, pinch to zoom (pointer events cover mouse, touch and pen)
      var cv = M.querySelector('canvas'), pts = {}, last = null, pinch = null;
      function geo() { return cv._geo; }
      cv.addEventListener('pointerdown', function (e) { if (!S.shot) return; cv.setPointerCapture(e.pointerId); pts[e.pointerId] = [e.clientX, e.clientY]; last = [e.clientX, e.clientY];
        var k = Object.keys(pts); if (k.length === 2) { var a = pts[k[0]], b = pts[k[1]]; pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), z: S.zoom }; } });
      cv.addEventListener('pointermove', function (e) {
        if (!pts[e.pointerId] || !S.shot) return;
        pts[e.pointerId] = [e.clientX, e.clientY];
        var k = Object.keys(pts);
        if (k.length >= 2 && pinch) { var a = pts[k[0]], b = pts[k[1]]; S.zoom = Math.max(1, Math.min(3, pinch.z * Math.hypot(a[0] - b[0], a[1] - b[1]) / (pinch.d || 1))); return redraw(); }
        var g = geo(); if (!g || !last) return;
        var sc = cv.width / cv.getBoundingClientRect().width, dx = (e.clientX - last[0]) * sc, dy = (e.clientY - last[1]) * sc; last = [e.clientX, e.clientY];
        if (g.dw - g.w > 1) S.posX = Math.max(0, Math.min(100, S.posX - dx / (g.dw - g.w) * 100));
        if (g.dh - g.ih > 1) S.posY = Math.max(0, Math.min(100, S.posY - dy / (g.dh - g.ih) * 100));
        redraw();
      });
      function up(e) { delete pts[e.pointerId]; pinch = null; var k = Object.keys(pts); last = k.length ? pts[k[0]] : null; }
      cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
      cv.addEventListener('wheel', function (e) { if (!S.shot) return; e.preventDefault(); S.zoom = Math.max(1, Math.min(3, S.zoom * (e.deltaY < 0 ? 1.06 : 1 / 1.06))); redraw(); }, { passive: false });
    }
    MODAL.querySelector('.pb-m-top b').textContent = adjust && S.shot ? 'Position your chart' : 'Preview';
    MODAL.hidden = false; document.documentElement.style.overflow = 'hidden';
    paint(MODAL.querySelector('canvas')); syncModal();
  }
  function closeModal() { if (MODAL) MODAL.hidden = true; document.documentElement.style.overflow = ''; redraw(); }

  function render(el, opt) {
    OPT = opt || {}; root = el;
    if (!document.getElementById('pb-css')) { var st = document.createElement('style'); st.id = 'pb-css'; st.textContent = CSS; document.head.appendChild(st); }
    el.innerHTML =
      '<div class="kithero card" style="padding:22px 24px"><div><span class="eyebrow" style="font-family:var(--mono);font-size:11px;letter-spacing:.16em;color:#58E9FF">POST BUILDER</span>' +
      '<h2 style="font-family:var(--display);font-size:24px;margin-top:6px">Turn your results into an on-brand post</h2>' +
      '<p class="muted" style="margin-top:6px;max-width:640px">Add your stats, pick the scanner, drop in a chart screenshot if you have one, then flip through the templates. Your code goes on every image. Nothing you add leaves your device.</p></div></div>' +
      '<div class="pb">' +
        '<div class="pb-prev">' +
          '<div class="pb-stage"><canvas id="pbC" aria-label="Post preview"></canvas>' +
            '<button type="button" class="pb-nav l" data-step="-1" aria-label="Previous template">‹</button><button type="button" class="pb-nav r" data-step="1" aria-label="Next template">›</button></div>' +
          '<div class="pb-thumbs">' + TEMPLATES.map(function (t, i) { return '<button type="button" data-tpl="' + i + '"' + (i === S.tpl ? ' class="on"' : '') + '><canvas></canvas><span>' + t[1] + '</span></button>'; }).join('') + '</div>' +
          '<div class="pb-acts"><button type="button" class="btn" id="pbDl">Download image</button><button type="button" class="btn-g" id="pbShare" hidden>Share / save to phone</button></div>' +
          '<div class="pb-note">PNG at full size (' + SIZES[S.size][0] + '×' + SIZES[S.size][1] + '), ready for Instagram, Facebook and X.</div>' +
        '</div>' +
        '<div class="pb-form">' +
          '<div class="pb-g"><h3><i>01</i>Format</h3>' + seg('size', Object.keys(SIZES).map(function (k) { return [k, SIZES[k][2]]; })) + '</div>' +
          '<div class="pb-g"><h3><i>02</i>What is it?</h3>' + seg('head', Object.keys(HEADS).map(function (k) { return [k, HEADS[k]]; })) +
            '<div class="pb-f" id="pbCustomF"' + (S.head === 'custom' ? '' : ' hidden') + '><label for="pb-custom">Headline</label><input id="pb-custom" data-k="custom" maxlength="40" placeholder="e.g. Gold, London session" value=""></div></div>' +
          '<div class="pb-g"><h3><i>03</i>Scanner & market</h3>' + seg('scanner', SCANNERS.map(function (s) { return [s, s]; }).concat([['', 'None']])) +
            seg('market', [['gold', 'Gold'], ['us30', 'US30'], ['nas', 'NAS100'], ['btc', 'Bitcoin'], ['other', 'Other']]) +
            '<div class="pb-row two"><div class="pb-f" id="pbMkF"' + (S.market === 'other' ? '' : ' hidden') + '><label for="pb-marketOther">Market</label><input id="pb-marketOther" data-k="marketOther" maxlength="14" placeholder="e.g. EURUSD"></div>' +
            field('tf', 'Timeframe (optional)', 'e.g. 3 min') + '</div></div>' +
          '<div class="pb-g"><h3><i>04</i>Your numbers <span class="pb-note" style="font-weight:400">(leave any blank to hide it)</span></h3>' +
            '<div class="pb-row">' + field('trades', 'Trades', '24', 'num') + field('wins', 'Wins', '22', 'num') + field('losses', 'Losses', '2', 'num') + '</div>' +
            '<div class="pb-row">' + field('total', 'Total', '17700', 'num') +
              '<div class="pb-f"><label for="pb-unit">Unit</label><select id="pb-unit" data-k="unit">' + UNITS.map(function (u) { return '<option' + (u === S.unit ? ' selected' : '') + '>' + u + '</option>'; }).join('') + '</select></div>' +
              field('pct', 'Return % (optional)', '17.7', 'num') + '</div>' +
            '<div class="pb-note" id="pbWr"></div></div>' +
          '<div class="pb-g"><h3><i>05</i>Chart screenshot <span class="pb-note" style="font-weight:400">(optional)</span></h3>' +
            '<label class="pb-drop" id="pbDrop"><input type="file" accept="image/*" id="pbFile" hidden><b>Upload a screenshot</b> or drop it here<br><span class="pb-note">No screenshot? We draw a clean chart for you.</span></label>' +
            '<div class="pb-shot" id="pbShot" hidden><img alt=""><div class="pb-acts"><button type="button" class="btn-g" id="pbAdj">Adjust</button><button type="button" class="btn-g" id="pbRm">Remove</button></div></div></div>' +
          '<div class="pb-g"><h3><i>06</i>Call to action & caption</h3>' + seg('cta', [['auto', 'Auto'], ['bio', 'Link in bio'], ['link', 'Tap the link (story)'], ['none', 'No line']]) +
            '<div class="pb-note">Auto uses “Link in bio” on posts and “Tap the link” on stories. Put your trial link in your bio or on a story link sticker: <b style="font-family:var(--mono);color:var(--tx);overflow-wrap:anywhere">' + (OPT.trial || '') + '</b></div>' +
            '<div class="pb-cap"></div><div class="pb-acts"><button type="button" class="btn-g" id="pbCopy">Copy caption</button></div></div>' +
        '</div>' +
      '</div>' +
      '<div class="pb-bar"><canvas id="pbMini" aria-label="Open preview"></canvas><div class="t"><b id="pbBarT"></b><div class="sw"><button type="button" class="ar" data-step="-1" aria-label="Previous template">‹</button><button type="button" class="ar" data-step="1" aria-label="Next template">›</button><span class="pb-note">Tap preview to view</span></div></div><button type="button" class="btn" id="pbBarSave">Save</button></div>';
    stage = el.querySelector('#pbC');
    thumbs = Array.prototype.map.call(el.querySelectorAll('.pb-thumbs canvas'), function (x) { return x; });

    el.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b || !el.contains(b)) return;
      var sg = b.parentNode.getAttribute && b.parentNode.getAttribute('data-seg');
      if (sg) {
        S[sg] = b.getAttribute('data-v');
        b.parentNode.querySelectorAll('button').forEach(function (x) { x.classList.toggle('on', x === b); });
        el.querySelector('#pbCustomF').hidden = S.head !== 'custom';
        el.querySelector('#pbMkF').hidden = S.market !== 'other';
        el.querySelector('.pb-prev .pb-note').textContent = 'PNG at full size (' + SIZES[S.size][0] + '×' + SIZES[S.size][1] + '), ready for Instagram, Facebook and X.';
        return redraw();
      }
      if (b.hasAttribute('data-tpl')) return pick(+b.getAttribute('data-tpl'));
      if (b.hasAttribute('data-step')) return pick((S.tpl + +b.getAttribute('data-step') + TEMPLATES.length) % TEMPLATES.length);
    });
    function pick(i) { S.tpl = i; el.querySelectorAll('.pb-thumbs button').forEach(function (x, j) { x.classList.toggle('on', j === i); }); redraw(); }
    PICK = pick;
    el.addEventListener('input', function (e) {
      var k = e.target.getAttribute('data-k'); if (!k) return;
      S[k] = e.target.value;
      var st = stats(); el.querySelector('#pbWr').textContent = st.wr != null ? 'Win rate works out at ' + st.wr + '% (' + fmt(st.w) + ' of ' + fmt(st.t) + ').' : '';
      if (st.w != null && st.t != null && st.w > st.t) el.querySelector('#pbWr').textContent = 'Wins are more than trades: check the numbers.';
      redraw();
    });
    el.querySelector('#pb-unit').addEventListener('change', function () { S.unit = this.value; redraw(); });

    var drop = el.querySelector('#pbDrop'), file = el.querySelector('#pbFile');
    function load(f) {
      if (!f || !/^image\//.test(f.type)) return;
      var url = URL.createObjectURL(f), im = new Image();
      im.onload = function () { S.shot = im; S.zoom = 1; S.posX = 50; S.posY = 50;
        el.querySelector('#pbShot').hidden = false; el.querySelector('#pbShot img').src = url; drop.hidden = true; draw(); openModal(true); };
      im.src = url;
    }
    file.addEventListener('change', function () { load(file.files[0]); file.value = ''; });
    ['dragenter', 'dragover'].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add('over'); }); });
    ['dragleave', 'drop'].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.remove('over'); }); });
    drop.addEventListener('drop', function (e) { load(e.dataTransfer.files[0]); });
    el.addEventListener('paste', function (e) { var it = [].slice.call((e.clipboardData || {}).items || []).filter(function (x) { return /^image\//.test(x.type); })[0]; if (it) load(it.getAsFile()); });
    el.querySelector('#pbRm').addEventListener('click', function () { S.shot = null; el.querySelector('#pbShot').hidden = true; drop.hidden = false; redraw(); });
    el.querySelector('#pbAdj').addEventListener('click', function () { openModal(true); });
    el.querySelector('#pbMini').addEventListener('click', function () { openModal(false); });

    function blob(cb) { var cv = document.createElement('canvas'); paint(cv); cv.toBlob(cb, 'image/png'); }
    function fname() { return 'tradevault-' + TEMPLATES[S.tpl][0] + '-' + S.size + '.png'; }
    function download(b) {
      if (b) b.disabled = true;
      blob(function (bl) {
        if (b) b.disabled = false; if (!bl) return;
        var a = document.createElement('a'); a.href = URL.createObjectURL(bl); a.download = fname(); document.body.appendChild(a); a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
      });
    }
    var canShare = false;
    try { canShare = !!(navigator.canShare && navigator.canShare({ files: [new File([''], 'x.png', { type: 'image/png' })] })); } catch (e) {}
    var touch = matchMedia('(pointer: coarse)').matches;
    // phones: the share sheet ("Save image" puts it in Photos); computers: a normal download
    saveFn = function (b) {
      if (canShare && touch) return blob(function (bl) { if (!bl) return; navigator.share({ files: [new File([bl], fname(), { type: 'image/png' })] }).catch(function () {}); });
      download(b);
    };
    el.querySelector('#pbDl').addEventListener('click', function () { download(this); });
    el.querySelector('#pbBarSave').addEventListener('click', function () { saveFn(this); });
    var sh = el.querySelector('#pbShare');
    sh.hidden = !canShare;
    sh.addEventListener('click', function () {
      blob(function (bl) { if (!bl) return; var f = new File([bl], fname(), { type: 'image/png' }); navigator.share({ files: [f], text: caption() }).catch(function () {}); });
    });
    el.querySelector('#pbCopy').addEventListener('click', function () {
      var b = this, t = caption();
      (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () { b.textContent = 'Copied ✓'; setTimeout(function () { b.textContent = 'Copy caption'; }, 1600); })
        .catch(function () { var r = document.createRange(); r.selectNodeContents(el.querySelector('.pb-cap')); var s = getSelection(); s.removeAllRanges(); s.addRange(r); });
    });

    img(A + 'tv-logo.png');
    var f = document.fonts;
    if (f && f.load) Promise.all([f.load('700 80px "Instrument Sans"'), f.load('600 30px "Instrument Sans"'), f.load('500 20px "JetBrains Mono"'), f.load('400 15px Inter')]).then(draw, draw);
    draw();
  }

  window.TVPost = { render: render, _paint: paint, _state: S };
})();
