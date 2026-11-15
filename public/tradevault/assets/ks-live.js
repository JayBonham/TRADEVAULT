/* Killshot live replay for the sales pages: real gold 3-minute charts with the Killshot overlay
   (same data and look as /spot). Usage: <canvas data-ks-live></canvas> plus optional
   [data-ks-row="signal|trend|poc"] elements inside the same [data-ks-panel] to show live readouts. */
(function () {
  'use strict';
  var SRC = '/spot/setups.json';
  var RM = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var C = { up: '#EAF0FA', dn: '#2F6BFF', wick: 'rgba(234,240,250,.55)', wickDn: 'rgba(47,107,255,.8)', fast: '#FF4D63', slow: '#3D7BFF', e200: '#FF9800',
    bull: 'rgba(30,80,210,.17)', bear: 'rgba(120,24,46,.24)', yel: '#FFE14D', blue: '#3D7BFF', buy: '#22D39A', sell: '#FF4D63', grid: 'rgba(255,255,255,.05)', axis: '#76849B' };

  function star(x, cx, cy, r, col, pts) {
    pts = pts || 16; x.save(); x.shadowColor = col; x.shadowBlur = r > 5 ? 12 : 3; x.fillStyle = col; x.beginPath();
    for (var i = 0; i < pts; i++) { var a = i * Math.PI * 2 / pts - Math.PI / 2, rr = i % 2 ? r * .45 : r; x.lineTo(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr); }
    x.closePath(); x.fill(); x.restore();
  }
  function tri(x, cx, cy, r, dir, col) {
    x.fillStyle = col; x.beginPath();
    if (dir === 1) { x.moveTo(cx, cy - r); x.lineTo(cx + r, cy + r * .8); x.lineTo(cx - r, cy + r * .8); } else { x.moveTo(cx, cy + r); x.lineTo(cx + r, cy - r * .8); x.lineTo(cx - r, cy - r * .8); }
    x.closePath(); x.fill();
  }
  function fmt(v) { return v.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }); }

  function Live(cv, panel, pool) {
    this.cv = cv; this.x = cv.getContext('2d'); this.panel = panel; this.pool = pool; this.k = Math.floor(Math.random() * pool.length);
    this.resize(); this.next();
    var self = this;
    window.addEventListener('resize', function () { self.resize(); });
  }
  Live.prototype.resize = function () {
    var r = this.cv.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2);
    this.w = Math.max(1, r.width); this.h = Math.max(1, r.height);
    this.cv.width = Math.round(this.w * d); this.cv.height = Math.round(this.h * d); this.x.setTransform(d, 0, 0, d, 0, 0);
  };
  Live.prototype.next = function () {
    this.k = (this.k + 1 + Math.floor(Math.random() * 3)) % this.pool.length;
    this.s = this.pool[this.k]; this.n = this.s.at - 55; this.p = 0; this.trade = null; this.wait = 0; this.lo = null;
  };
  Live.prototype.row = function (key, html, st, cls) {
    var el = this.panel && this.panel.querySelector('[data-ks-row="' + key + '"]');
    if (!el) return;
    var sp = el.querySelector('span'), i = el.querySelector('i');
    if (sp && sp.innerHTML !== html) sp.innerHTML = html;
    if (i) { i.textContent = st; i.className = 'st' + (cls ? ' ' + cls : ''); }
  };
  Live.prototype.step = function (dt) {
    var s = this.s, per = this.n <= s.at ? 110 : 150;
    if (RM) per = 1;
    if (this.wait > 0) { this.wait -= dt; if (this.wait <= 0) this.next(); return; }
    this.p += dt / per;
    while (this.p >= 1) {
      this.p -= 1; this.n++;
      var k = this.n - 1;
      if (k === s.at && !this.trade) {
        var r = Math.abs(s.entry - s.stop);
        this.trade = { d: s.d, at: s.at, entry: s.entry, stop: s.entry - s.d * r, target: s.entry + s.d * s.rr * r, res: null, exit: null };
      } else if (this.trade && !this.trade.res && k > s.at) {
        var c = s.c[k], t = this.trade;
        if (t.d === 1 ? c[2] <= t.stop : c[1] >= t.stop) { t.res = 'loss'; t.exit = k; }
        else if (t.d === 1 ? c[1] >= t.target : c[2] <= t.target) { t.res = 'win'; t.exit = k; }
      }
      if ((this.trade && this.trade.res && this.n > this.trade.exit + 4) || this.n >= s.c.length) { this.p = 0; this.wait = 2200; break; }
    }
  };
  Live.prototype.draw = function () {
    var x = this.x, s = this.s, W = this.w, H = this.h, axis = 52, right = 34, plotW = W - axis - right;
    x.clearRect(0, 0, W, H);
    var cw = plotW / Math.max(46, Math.min(90, plotW / 7)), last = this.n, first = Math.max(0, last - Math.ceil(plotW / cw) - 1), nn = last - 1;
    var X = function (k) { return W - axis - right - (last - 1 - k) * cw - cw / 2; };
    var lo = Infinity, hi = -Infinity, k, c;
    for (k = first; k < last; k++) { c = s.c[k]; lo = Math.min(lo, c[2]); hi = Math.max(hi, c[1]); }
    if (this.trade) { lo = Math.min(lo, this.trade.stop, this.trade.target); hi = Math.max(hi, this.trade.stop, this.trade.target); }
    var pad = (hi - lo) * .12 || 1; lo -= pad; hi += pad;
    if (this.lo === null || RM) { this.lo = lo; this.hi = hi; } else { this.lo += (lo - this.lo) * .1; this.hi += (hi - this.hi) * .1; }
    var top = 8, ph = H - top - 18, L = this.lo, Hh = this.hi, Y = function (v) { return top + (Hh - v) / (Hh - L) * ph; };
    // trend shading
    for (k = first; k < last;) {
      var b = s.e[k][0] > s.e[k][1], k2 = k;
      while (k2 + 1 < last && (s.e[k2 + 1][0] > s.e[k2 + 1][1]) === b) k2++;
      x.fillStyle = b ? C.bull : C.bear; var xa = Math.floor(X(k) - cw / 2); x.fillRect(xa, top, Math.ceil(X(k2) + cw / 2) - xa, ph); k = k2 + 1;
    }
    // grid + axis
    var step = Math.pow(10, Math.floor(Math.log10((Hh - L) / 4))), m = (Hh - L) / 4 / step; step *= m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10;
    x.font = '500 10px "JetBrains Mono", monospace'; x.textBaseline = 'middle'; x.textAlign = 'left';
    for (var g = Math.ceil(L / step) * step; g < Hh; g += step) { var gy = Y(g); x.strokeStyle = C.grid; x.lineWidth = 1; x.beginPath(); x.moveTo(0, gy); x.lineTo(W - axis, gy); x.stroke(); x.fillStyle = C.axis; x.fillText(fmt(g), W - axis + 6, gy); }
    // S/R lines + POC
    (s.ln || []).forEach(function (l) {
      if (l[0] + 8 > nn || l[2] < first) return; var e2 = Math.min(l[2], nn); if (e2 <= l[0]) return;
      x.strokeStyle = l[3] === 1 ? 'rgba(34,211,154,.6)' : 'rgba(255,77,99,.65)'; x.lineWidth = 1.1;
      x.beginPath(); x.moveTo(X(Math.max(l[0], first)), Y(l[1])); x.lineTo(X(e2), Y(l[1])); x.stroke();
    });
    if (s.p && nn >= 0) { var py = Y(s.p[nn]); x.strokeStyle = C.e200; x.lineWidth = 1.4; x.beginPath(); x.moveTo(X(Math.max(first, last - 60)), py); x.lineTo(W - axis, py); x.stroke(); }
    // EMAs
    [[2, C.e200, 2], [1, C.slow, 1.5], [0, C.fast, 1.4]].forEach(function (mm) {
      x.strokeStyle = mm[1]; x.lineWidth = mm[2]; x.beginPath();
      for (var j = first, st = false; j < last; j++) { var yy = Y(s.e[j][mm[0]]); if (!st) { x.moveTo(X(j), yy); st = true; } else x.lineTo(X(j), yy); }
      x.stroke();
    });
    // trade box
    var t = this.trade;
    if (t) {
      var x0 = X(t.at) - cw / 2, x1 = t.exit != null ? X(t.exit) + cw / 2 : W - axis - 4, ye = Y(t.entry), yt = Y(t.target), ys = Y(t.stop);
      x.fillStyle = 'rgba(34,211,154,.16)'; x.fillRect(x0, Math.min(ye, yt), x1 - x0, Math.abs(yt - ye));
      x.fillStyle = 'rgba(255,77,99,.16)'; x.fillRect(x0, Math.min(ye, ys), x1 - x0, Math.abs(ys - ye));
      x.setLineDash([4, 3]); x.strokeStyle = 'rgba(234,240,250,.6)'; x.beginPath(); x.moveTo(x0, ye); x.lineTo(x1, ye); x.stroke(); x.setLineDash([]);
    }
    // candles
    var bw = Math.max(2, cw * .6);
    for (k = first; k < last; k++) {
      c = s.c[k]; var up = c[3] >= c[0], cx = X(k);
      x.strokeStyle = up ? C.wick : C.wickDn; x.lineWidth = 1; x.beginPath(); x.moveTo(Math.round(cx) + .5, Y(c[1])); x.lineTo(Math.round(cx) + .5, Y(c[2])); x.stroke();
      x.fillStyle = up ? C.up : C.dn; var yo = Y(c[0]), yc = Y(c[3]); x.fillRect(cx - bw / 2, Math.min(yo, yc), bw, Math.max(1.2, Math.abs(yc - yo)));
    }
    // markers
    (s.mk || []).forEach(function (mk) {
      if (mk[2] > nn || mk[0] < first) return; var cc = s.c[mk[0]], mx = X(mk[0]);
      switch (mk[1]) {
        case 1: star(x, mx, Y(cc[1]) - 7, 2.6, C.yel, 6); break; case 2: star(x, mx, Y(cc[2]) + 7, 2.6, C.yel, 6); break;
        case 3: star(x, mx, Y(cc[1]) - 9, 4, C.blue, 8); break; case 4: star(x, mx, Y(cc[2]) + 9, 4, C.blue, 8); break;
        case 5: tri(x, mx, Y(cc[2]) + 10, 5, 1, C.blue); break; case 6: tri(x, mx, Y(cc[1]) - 10, 5, -1, C.sell); break;
        case 7: star(x, mx, Y(cc[1]) - 12, 6, C.sell); break; case 8: star(x, mx, Y(cc[2]) + 12, 6, C.buy); break;
      }
    });
    if (t) { var sc = s.c[t.at]; star(x, X(t.at), t.d === 1 ? Y(sc[2]) + 13 : Y(sc[1]) - 13, 7.5, t.d === 1 ? C.buy : C.sell); }
    // last price
    var lp = s.c[nn][3], ly = Y(lp);
    x.fillStyle = s.c[nn][3] >= s.c[nn][0] ? C.up : C.dn; x.fillRect(W - axis, ly - 9, axis - 2, 18);
    x.fillStyle = s.c[nn][3] >= s.c[nn][0] ? '#03060D' : '#fff'; x.font = '700 10px "JetBrains Mono", monospace'; x.fillText(fmt(lp), W - axis + 4, ly);
    // readouts
    var fl = s.f[nn], tr = function (b) { return (fl >> b & 1) ? '<b class="ks-up">Up</b>' : '<b class="ks-dn">Down</b>'; };
    if (t) this.row('signal', (t.d === 1 ? 'Buy' : 'Sell') + ' star printed at ' + fmt(t.entry), t.res === 'win' ? 'Target hit' : t.res === 'loss' ? 'Stopped' : 'Setup', t.res === 'loss' ? 'stop' : 'go');
    else this.row('signal', 'Watching for a stretched extreme', 'Scanning', 'wait');
    this.row('trend', 'M3 ' + tr(0) + ' · M15 ' + tr(1) + ' · H1 ' + tr(3) + ' · H4 ' + tr(4), (fl & 1) ? 'Bullish' : 'Bearish', (fl & 1) ? 'go' : 'stop');
    this.row('poc', 'Point of Control ' + fmt(s.p[nn]), lp > s.p[nn] ? 'Above' : 'Below', '');
  };

  function boot(pool) {
    document.querySelectorAll('canvas[data-ks-live]').forEach(function (cv) {
      var lv = new Live(cv, cv.closest('[data-ks-panel]'), pool), last = 0, vis = true;
      if ('IntersectionObserver' in window) new IntersectionObserver(function (e) { vis = e[0].isIntersecting; }).observe(cv);
      (function f(tm) { var dt = Math.min(64, tm - (last || tm)); last = tm; if (vis) { lv.step(dt); lv.draw(); } requestAnimationFrame(f); })(0);
    });
  }
  function start() {
    if (!document.querySelector('canvas[data-ks-live]')) return;
    fetch(SRC).then(function (r) { return r.json(); }).then(boot).catch(function () {});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
