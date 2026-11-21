/* Shared second lock for Analytics and Projects (same analytics password).
   Enter it once and it stays unlocked on this browser for 24 hours: refreshes, switching pages
   and closing/reopening don't ask again. Sign out clears it. */
window.TVUnlock = (function () {
  var KEY = 'tv_unlock', TTL = 24 * 60 * 60 * 1000;
  function read() { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } }
  function write(v) { try { if (v) localStorage.setItem(KEY, JSON.stringify(v)); else localStorage.removeItem(KEY); } catch (e) {} }
  function get() {
    var v = read();
    if (!v || !v.p || Date.now() - (v.t || 0) > TTL) { if (v) write(null); return ''; }
    return v.p;
  }
  function set(p) { var v = read(); write(p ? { p: p, t: v && v.p === p && Date.now() - v.t < TTL ? v.t : Date.now() } : null); }
  return { get: get, set: set, clear: function () { write(null); } };
})();
