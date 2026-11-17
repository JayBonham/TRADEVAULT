/* Content pages (scanners, educators, learn) are ours: anyone who lands on one from outside the site (Google, social,
   a shared link, ?ref or not) is credited to the house code, 60 days, last click wins.
   Only someone already on the site who clicks through from another page keeps the affiliate they arrived with. */
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
    if (navigator.webdriver || /bot|crawl|spider|headless|lighthouse|preview/i.test(navigator.userAgent)) return;
    var k = 'tv_ref_seen_' + r;
    try { if (sessionStorage.getItem(k)) return; sessionStorage.setItem(k, '1'); } catch (e) {}
    fetch('https://jaybonham.com/api/tv-aff?action=click', { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify({ code: r }), keepalive: true }).catch(function () {});
  }
  try {
    var internal = false;
    try { internal = !!document.referrer && new URL(document.referrer).hostname.replace(/^www\./, '') === location.hostname.replace(/^www\./, ''); } catch (e) {}
    if (!internal || !stored()) set(HOUSE);
  } catch (e) {}
})();
