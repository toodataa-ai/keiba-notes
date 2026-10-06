(() => {
  'use strict';

  const NAMESPACE = 'toodataa-ai-keiba-notes';
  const ACTION = 'visit';
  const ENDPOINT = 'https://counterapi.com/api';

  // 管理画面自身は来訪者数へ含めない。
  if (/\/admin\.html$/.test(location.pathname)) return;

  function jstDateKey(now = new Date()) {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Tokyo',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).formatToParts(now);
    const values = Object.fromEntries(parts.map(p => [p.type, p.value]));
    return `${values.year}-${values.month}-${values.day}`;
  }

  function hit(key) {
    const nonce = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const url = `${ENDPOINT}/${encodeURIComponent(NAMESPACE)}/${encodeURIComponent(ACTION)}/${encodeURIComponent(key)}?trackOnly=true&_=${nonce}`;
    fetch(url, {
      method: 'GET',
      mode: 'cors',
      cache: 'no-store',
      credentials: 'omit',
      keepalive: true,
      referrerPolicy: 'strict-origin-when-cross-origin'
    }).catch(() => {
      // カウンター障害で本体サイトの表示を止めない。
    });
  }

  hit('all-time');
  hit(`day-${jstDateKey()}`);
})();
