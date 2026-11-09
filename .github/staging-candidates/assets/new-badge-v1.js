/* NEW on homepage entrances for the first 7 JST calendar days after public UI release.
   v1.46 and earlier use stable historical dates. From v1.47 onward the approved
   jra-ui-promote-v1 workflow records new_entry_pages automatically in the release
   ledger by diffing homepage portal-card links. No manual registration at release. */
(function () {
  'use strict';
  var NEW_DAYS = 7;
  var LEGACY = [
    { href: 'collection-status.html', since: '2026-11-08' },
    { href: 'baba-bias.html', since: '2026-11-08' },
    { href: 'sire-map.html', since: '2026-11-06' },
    { href: 'operations.html', since: '2026-11-03' },
    { href: 'track-trends.html', since: '2026-11-10' },
    { href: 'people-trends.html', since: '2026-11-10' }
  ];
  function todayJst() {
    var n = new Date(Date.now() + 9 * 3600000);
    return Date.UTC(n.getUTCFullYear(), n.getUTCMonth(), n.getUTCDate());
  }
  function isNew(date, today) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
    var ymd = date.split('-').map(Number);
    var published = Date.UTC(ymd[0], ymd[1] - 1, ymd[2]);
    var days = Math.floor((today - published) / 86400000);
    return days >= 0 && days < NEW_DAYS;
  }
  function addBadges(entries) {
    var today = todayJst();
    Array.prototype.forEach.call(document.querySelectorAll('a.portal-card'), function (a) {
      var href = (a.getAttribute('href') || '').split(/[?#]/)[0].split('/').pop();
      if (a.querySelector('.new-badge')) return;
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].href !== href || !isNew(entries[i].since, today)) continue;
        if (getComputedStyle(a).position === 'static') a.style.position = 'relative';
        var tag = document.createElement('span');
        tag.className = 'new-badge';
        tag.textContent = 'NEW';
        tag.setAttribute('aria-label', '新しく公開');
        a.appendChild(tag);
        break;
      }
    });
  }
  function run() {
    var style = document.createElement('style');
    style.textContent = '.new-badge{position:absolute;top:-7px;right:12px;z-index:2;padding:2px 7px;border-radius:999px;background:#c61d31;color:#fff;font:800 10px/1.3 system-ui,-apple-system,sans-serif;letter-spacing:.06em;box-shadow:0 1px 3px rgba(0,0,0,.3);pointer-events:none}';
    document.head.appendChild(style);
    addBadges(LEGACY);  // Also works if the ledger is temporarily unavailable.
    var fromStaging = /\/staging\//.test(window.location.pathname);
    var ledgerUrl = fromStaging ? '../data/production-releases.json' : 'data/production-releases.json';
    fetch(ledgerUrl, {cache: 'no-store'}).then(function (response) {
      if (!response.ok) throw Error('release ledger HTTP ' + response.status);
      return response.json();
    }).then(function (ledger) {
      var entries = [];
      (ledger.releases || []).forEach(function (release) {
        var date = (release.deployed_at || '').slice(0, 10);
        if (!release.user_approved || !isNew(date, todayJst())) return;
        (release.new_entry_pages || []).forEach(function (href) {
          if (typeof href === 'string') entries.push({href: href, since: date});
        });
      });
      addBadges(entries);
    }).catch(function () { /* Preserve historical badges on transient network errors. */ });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
