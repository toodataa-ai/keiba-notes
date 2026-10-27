/* PRODUCTION DISPLAY ONLY — route reviewed JRA report links to the read-only,
   evidence-checked rationale overlay. Never modify results.js, final_bets,
   settlement, performance, review, cumulative ROI, or report HTML/PDF. */
(() => {
  'use strict';
  const host = document.getElementById('raceList');
  if (!host) return;
  const normalize = path => String(path || '').replace(/^(\.\.\/)+/, '').split('?')[0];
  const eligible = new Map();

  function wire() {
    for (const a of host.querySelectorAll('.race-card .actions a[href]')) {
      const source = normalize(a.getAttribute('href'));
      const raceId = eligible.get(source);
      if (!raceId) continue;
      // Update only the visitor-facing navigation URL. Leave text, all results
      // panels, their calculated amounts, and the canonical href evidence intact.
      if (!a.dataset.originalReportHref) a.dataset.originalReportHref = source;
      const next = 'jra-purchase-rationale.html?race_id=' + encodeURIComponent(raceId);
      if (a.getAttribute('href') !== next) a.setAttribute('href', next);
    }
  }

  Promise.all([
    fetch('data/races.json', {cache:'no-store'}).then(r => {
      if (!r.ok) throw Error('races unavailable');
      return r.json();
    }),
    fetch('assets/jra-bet-rationale-evidence-v2.json', {cache:'no-store'}).then(r => {
      if (!r.ok) throw Error('rationale evidence unavailable');
      return r.json();
    })
  ]).then(([db, ev]) => {
    if (ev.schema_version !== 2 || !ev.records) return;
    for (const r of db.races || []) {
      const e = ev.records[r.id];
      if (!e || r.scope !== 'jra-main' || r.status !== 'reviewed' ||
          r.purchase_decision !== 'buy' ||
          !r.report?.startsWith('reports/') ||
          e.purchase_proof !== r.proof_commit ||
          e.purchase_version !== r.purchase_strategy_version) continue;
      eligible.set(r.report, r.id);
    }
    wire();
    new MutationObserver(wire).observe(host, {childList:true});
  }).catch(() => {
    // Fail closed: leave existing links and results completely unchanged.
  });
})();