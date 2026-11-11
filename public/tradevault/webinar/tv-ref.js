/* Affiliate links for the webinar pages: same as the homepage. ?ref=CODE is remembered for 60 days (last click wins),
   counted once per session, and read back by the signup form and the homepage checkout buttons. */
(function () {
  try {
    var r = new URLSearchParams(location.search).get('ref');
    if (!r || !/^[a-z0-9_]{3,20}$/i.test(r)) return;
    r = r.toLowerCase();
    try { localStorage.setItem('tv_ref', JSON.stringify({ c: r, t: Date.now() })); } catch (e) {}
    document.cookie = 'tv_ref=' + r + '; path=/; max-age=5184000; SameSite=Lax';
    var k = 'tv_ref_seen_' + r;
    try { if (sessionStorage.getItem(k)) return; sessionStorage.setItem(k, '1'); } catch (e) {}
    fetch('https://jaybonham.com/api/tv-aff?action=click', { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify({ code: r }), keepalive: true }).catch(function () {});
  } catch (e) {}
})();
window.tvRef = function () {
  try { var s = JSON.parse(localStorage.getItem('tv_ref') || 'null'); if (s && Date.now() - s.t < 60 * 864e5) return s.c; } catch (e) {}
  var m = document.cookie.match(/(?:^|; )tv_ref=([a-z0-9_]{3,20})/);
  return m ? m[1] : '';
};
