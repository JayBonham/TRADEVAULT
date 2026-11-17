/* Content pages (scanners, educators, learn): affiliate links work here too (?ref=CODE, last click wins, 60 days).
   A visitor with no affiliate yet is credited to the house code, so sign-ups from search show in Affiliate HQ.
   It never replaces a real affiliate's code. */
(function () {
  var HOUSE = 'jaybreacts';
  function stored() {
    try { var s = JSON.parse(localStorage.getItem('tv_ref') || 'null'); if (s && Date.now() - s.t < 60 * 864e5) return s.c; } catch (e) {}
    var m = document.cookie.match(/(?:^|; )tv_ref=([a-z0-9_]{3,20})/);
    return m ? m[1] : '';
  }
  function set(r) {
    try { localStorage.setItem('tv_ref', JSON.stringify({ c: r, t: Date.now() })); } catch (e) {}
    document.cookie = 'tv_ref=' + r + '; path=/; max-age=5184000; SameSite=Lax';
    var k = 'tv_ref_seen_' + r;
    try { if (sessionStorage.getItem(k)) return; sessionStorage.setItem(k, '1'); } catch (e) {}
    fetch('https://jaybonham.com/api/tv-aff?action=click', { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify({ code: r }), keepalive: true }).catch(function () {});
  }
  try {
    var q = new URLSearchParams(location.search).get('ref');
    if (q && /^[a-z0-9_]{3,20}$/i.test(q)) set(q.toLowerCase());
    else if (!stored()) set(HOUSE);
  } catch (e) {}
})();
