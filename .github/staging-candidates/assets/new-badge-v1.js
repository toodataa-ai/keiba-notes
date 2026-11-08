/* 新しく公開した入り口のボタンに「NEW」のワッペンを付ける（公開から7日間）。
   ワッペンは角に重ねて表示するだけで、ボタンの大きさや文字の並びは変えない。
   新しい仕組みを公開したら、下の一覧に「ページ名と公開日」を足す（公開日はリリース台帳の日付）。 */
(function () {
  var NEW_DAYS = 7;
  var ENTRIES = [
    { href: 'collection-status.html', since: '2026-11-08' },
    { href: 'baba-bias.html', since: '2026-11-08' },
    { href: 'sire-map.html', since: '2026-11-06' },
    { href: 'operations.html', since: '2026-11-03' }
  ];
  function jstToday() { var n = new Date(Date.now() + 9 * 3600000); return Date.UTC(n.getUTCFullYear(), n.getUTCMonth(), n.getUTCDate()); }
  function run() {
    var today = jstToday(), css = document.createElement('style');
    css.textContent = '.new-badge{position:absolute;top:-7px;right:12px;z-index:2;padding:2px 7px;border-radius:999px;background:#c61d31;color:#fff;font:800 10px/1.3 system-ui,-apple-system,sans-serif;letter-spacing:.06em;box-shadow:0 1px 3px rgba(0,0,0,.3);pointer-events:none}';
    document.head.appendChild(css);
    ENTRIES.forEach(function (e) {
      var p = e.since.split('-'), days = Math.floor((today - Date.UTC(+p[0], +p[1] - 1, +p[2])) / 86400000);
      if (days < 0 || days >= NEW_DAYS) return;
      Array.prototype.forEach.call(document.querySelectorAll('a.portal-card'), function (a) {
        if ((a.getAttribute('href') || '').split(/[?#]/)[0] !== e.href || a.querySelector('.new-badge')) return;
        if (getComputedStyle(a).position === 'static') a.style.position = 'relative';
        var b = document.createElement('span'); b.className = 'new-badge'; b.textContent = 'NEW'; b.setAttribute('aria-label', '新しく公開');
        a.appendChild(b);
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
})();
