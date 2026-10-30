/* =================================================================
   WEBINAR SCHEDULE — single source of truth for /workshop pages.
   Runs weekly. Shows the next session on/after firstDate; a session
   counts as "current" until liveWindowMin after it starts.
   ================================================================= */
var WEBINAR = {
  firstDate: '2026-11-05',          // first session (YYYY-MM-DD)
  weekday: 4,                       // 0=Sun … 4=Thu
  hour: 20, minute: 0,              // 8:00 PM …
  tz: 'America/New_York', tzLabel: 'ET',
  durationMin: 60,
  liveWindowMin: 75,
  title: 'Live Workshop: The Secrets of a Hedge Fund Trader — Jay Bonham'
};

window.JBW = (function () {
  function tzOffset(date, tz) {
    var p = {};
    new Intl.DateTimeFormat('en-US', { timeZone: tz, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
      .formatToParts(date).forEach(function (x) { p[x.type] = x.value; });
    return Date.UTC(+p.year, p.month - 1, +p.day, +p.hour, +p.minute, +p.second) - date.getTime();
  }
  function zoned(y, mo, d, h, mi, tz) {
    var guess = Date.UTC(y, mo, d, h, mi);
    var t = guess - tzOffset(new Date(guess), tz);
    return new Date(guess - tzOffset(new Date(t), tz));
  }
  function nextSession(now) {
    var f = WEBINAR.firstDate.split('-').map(Number);
    var base = new Date(Date.UTC(f[0], f[1] - 1, f[2]));
    while (base.getUTCDay() !== WEBINAR.weekday) base.setUTCDate(base.getUTCDate() + 1);
    for (var i = 0; i < 520; i++) {
      var s = zoned(base.getUTCFullYear(), base.getUTCMonth(), base.getUTCDate(), WEBINAR.hour, WEBINAR.minute, WEBINAR.tz);
      if (s.getTime() + WEBINAR.liveWindowMin * 60000 > now) return s;
      base.setUTCDate(base.getUTCDate() + 7);
    }
  }

  // a registered session can be pinned with ?s=<ISO> (used by the confirmation page)
  var start = null;
  try {
    var q = new URLSearchParams(location.search).get('s');
    if (q && !isNaN(Date.parse(q))) start = new Date(q);
  } catch (e) {}
  if (!start) start = nextSession(Date.now());

  var end = new Date(start.getTime() + WEBINAR.durationMin * 60000);
  var fmt = function (o, tz) { return new Intl.DateTimeFormat('en-US', Object.assign({ timeZone: tz }, o)).format(start); };
  var userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  var local = '';
  if (userTz && tzOffset(start, userTz) !== tzOffset(start, WEBINAR.tz)) {
    local = 'That\'s ' + new Intl.DateTimeFormat('en-US', { weekday: 'short', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }).format(start) + ' your time';
  }

  var z = function (dt) { return dt.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, ''); };
  var details = 'Free live workshop with Jay Bonham. Your join link is in your email and texts.\n\nhttps://jaybonham.com/workshop';
  var gcal = 'https://calendar.google.com/calendar/render?action=TEMPLATE&text=' + encodeURIComponent(WEBINAR.title) +
             '&dates=' + z(start) + '/' + z(end) + '&details=' + encodeURIComponent(details) + '&location=' + encodeURIComponent('Online — link in your email');

  function ics() {
    var body = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Jay Bonham//Workshop//EN', 'BEGIN:VEVENT',
      'UID:' + z(start) + '@jaybonham.com', 'DTSTAMP:' + z(new Date()), 'DTSTART:' + z(start), 'DTEND:' + z(end),
      'SUMMARY:' + WEBINAR.title, 'DESCRIPTION:' + details.replace(/\n/g, '\\n'), 'LOCATION:Online — link in your email',
      'BEGIN:VALARM', 'TRIGGER:-PT15M', 'ACTION:DISPLAY', 'DESCRIPTION:Jay Bonham live workshop starts in 15 minutes', 'END:VALARM',
      'END:VEVENT', 'END:VCALENDAR'].join('\r\n');
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([body], { type: 'text/calendar' }));
    a.download = 'jay-bonham-live-workshop.ics';
    document.body.appendChild(a); a.click(); a.remove();
  }

  function set(sel, txt) { document.querySelectorAll(sel).forEach(function (e) { e.textContent = txt; }); }

  var pad = function (n) { return (n < 10 ? '0' : '') + n; };
  function countdown() {
    function tick() {
      var ms = start.getTime() - Date.now();
      if (ms <= 0) {
        set('[data-cd-mini]', '● Live now');
        document.querySelectorAll('[data-cd] b').forEach(function (b) { b.textContent = '00'; });
        return;
      }
      var s = Math.floor(ms / 1000), d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
      document.querySelectorAll('[data-cd]').forEach(function (c) {
        c.querySelector('[data-d]').textContent = pad(d);
        c.querySelector('[data-h]').textContent = pad(h);
        c.querySelector('[data-m]').textContent = pad(m);
        c.querySelector('[data-s]').textContent = pad(sec);
      });
      set('[data-cd-mini]', 'Starts in ' + (d ? d + 'd ' : '') + pad(h) + 'h ' + pad(m) + 'm ' + pad(sec) + 's');
    }
    tick(); setInterval(tick, 1000);
  }

  var J = {
    config: WEBINAR, start: start, end: end,
    day: fmt({ weekday: 'long' }, WEBINAR.tz),
    date: fmt({ month: 'short', day: 'numeric' }, WEBINAR.tz),
    dateL: fmt({ weekday: 'long', month: 'long', day: 'numeric' }, WEBINAR.tz),
    time: fmt({ hour: 'numeric', minute: '2-digit' }, WEBINAR.tz) + ' ' + WEBINAR.tzLabel,
    local: local, gcal: gcal, ics: ics, set: set, countdown: countdown
  };

  // fill the standard placeholders on whichever page loaded this
  function fill() {
    set('[data-when-short],[data-when-short2],[data-when-short3]', J.day + ', ' + J.date + ' · ' + J.time);
    set('[data-when-date]', J.day + ' ' + J.date);
    set('[data-when-time]', J.time);
    set('[data-when-local]', J.local || 'Live with Jay');
    set('[data-when-ribbon]', 'Live · ' + J.day + ' ' + J.date + ' · ' + J.time);
    set('[data-when-full],[data-when-full2]', J.dateL + ' at ' + J.time);
    set('[data-yr]', new Date().getFullYear());
    document.querySelectorAll('[data-gcal]').forEach(function (a) { a.href = gcal; });
    document.querySelectorAll('[data-ics]').forEach(function (b) { b.addEventListener('click', ics); });
    if (document.querySelector('[data-cd]')) countdown();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fill); else fill();
  return J;
})();
