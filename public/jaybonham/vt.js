/* JB video tracker — logs impressions, plays, 10% progress milestones and CTA clicks to /api/vt.
   Listens on document in capture phase and re-scans for <video> tags, so frameworks that re-render
   the DOM (x-dc on the homepage) can't detach it. */
(function () {
  if (window.__jbvt) return;
  window.__jbvt = 1;

  var ENDPOINT = '/api/vt';
  // CDN-hosted copies used on the apply page map to the same keys as the self-hosted files
  var CDN = {
    '6ad25a37cd7225ed3792d94a': 'ash',
    '6ad2517b3cacdd91176dcda3': 'jeremy',
    '6ad25188989628c77a2417c6': 'rees',
    '6ad257e25b21f84366801790': 'hifzah',
    '6ad257e2b3c1e3eb19286def': 'gary'
  };

  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
  function sstore(k, v) { try { if (v === undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k, v); } catch (e) { return null; } }
  function rid() { return Math.random().toString(36).slice(2, 10) + Date.now().toString(36); }

  var vid = store('jb_vt_vid') || rid(); store('jb_vt_vid', vid);
  var sid = sstore('jb_vt_sid') || rid(); sstore('jb_vt_sid', sid);

  var qs = new URLSearchParams(location.search);
  var qEmail = (qs.get('email') || qs.get('e') || '').trim().toLowerCase();
  if (qEmail && qEmail.indexOf('@') > 0) store('jb_vt_email', qEmail);
  var email = store('jb_vt_email') || '';

  var page = location.pathname.replace(/\/index\.html$/, '').replace(/\/+$/, '') || '/';

  function send(event, video, pct) {
    var body = JSON.stringify({ sid: sid, vid: vid, page: page, video: video || null, event: event, pct: pct == null ? null : Math.round(pct), email: email || null, ref: document.referrer ? document.referrer.slice(0, 200) : null });
    try {
      if (navigator.sendBeacon && navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'text/plain' }))) return;
    } catch (e) {}
    try { fetch(ENDPOINT, { method: 'POST', body: body, keepalive: true, headers: { 'Content-Type': 'text/plain' } }); } catch (e) {}
  }

  function keyOf(v) {
    var src = v.currentSrc || v.getAttribute('src') || (v.querySelector('source') || {}).src || '';
    var file = src.split('?')[0].split('#')[0].split('/').pop().replace(/\.mp4$/i, '');
    return CDN[file] || file || null;
  }

  var state = {};      // key -> {imp, play, max, sent:{}}
  function st(k) { return state[k] || (state[k] = { imp: 0, play: 0, max: 0, sent: {} }); }

  send('view', null, null);

  // impressions: video at least half on screen
  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting) return;
      var k = keyOf(e.target); if (!k) return;
      var s = st(k); if (s.imp) return;
      s.imp = 1; send('impression', k, null);
    });
  }, { threshold: 0.5 }) : null;
  var seen = typeof WeakSet !== 'undefined' ? new WeakSet() : null;
  function scan() {
    if (!io) return;
    document.querySelectorAll('video').forEach(function (v) {
      if (seen && seen.has(v)) return;
      if (seen) seen.add(v);
      io.observe(v);
    });
  }
  scan();
  document.addEventListener('DOMContentLoaded', scan);
  addEventListener('load', scan);
  setInterval(scan, 2000);

  document.addEventListener('play', function (e) {
    if (e.target.tagName !== 'VIDEO') return;
    var k = keyOf(e.target); if (!k) return;
    var s = st(k);
    if (!s.imp) { s.imp = 1; send('impression', k, null); }
    if (!s.play) { s.play = 1; send('play', k, 0); }
  }, true);

  function progress(v) {
    if (!v.duration || !isFinite(v.duration)) return;
    var k = keyOf(v); if (!k) return;
    var s = st(k);
    var p = Math.min(100, (v.currentTime / v.duration) * 100);
    if (p > s.max) s.max = p;
    for (var m = 10; m <= 100; m += 10) {
      if (s.max >= (m === 100 ? 98 : m) && !s.sent[m]) { s.sent[m] = 1; send('progress', k, m); }
    }
  }
  document.addEventListener('timeupdate', function (e) { if (e.target.tagName === 'VIDEO') progress(e.target); }, true);
  document.addEventListener('ended', function (e) {
    if (e.target.tagName !== 'VIDEO') return;
    var k = keyOf(e.target); if (!k) return;
    var s = st(k); s.max = 100; progress(e.target);
  }, true);

  // CTA clicks — any link/button to /apply (or marked data-vt-cta). Records how far into the most-watched video they were.
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('a,button') : null;
    if (!el) return;
    var href = el.getAttribute('href') || '';
    if (!(el.hasAttribute('data-vt-cta') || /\/apply(\b|\/|$|\?|#)/.test(href))) return;
    var best = null, bestPct = 0;
    Object.keys(state).forEach(function (k) { if (state[k].max >= bestPct) { best = k; bestPct = state[k].max; } });
    send('cta', best, best ? bestPct : null);
  }, true);
})();
