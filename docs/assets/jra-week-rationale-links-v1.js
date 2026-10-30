/* Display-only JRA rationale link restoration for this-week preview.
   No edits to signed reports, PDFs, prediction, marks, selections or ROI. */
(() => {
  'use strict';
  const host = document.getElementById('weekPredictions');
  if (!host) return;
  const eligible = new Map();
  const normalize = s => String(s || '').replace(/^(\.\.\/)+/, '').split('?')[0];
  const key = b => String(b.type) + ':' + JSON.stringify(b.selection || []);
  function wire() {
    for (const a of host.querySelectorAll('.race-card .actions a[href]')) {
      const source = normalize(a.dataset.originalReportHref || a.getAttribute('href'));
      const raceId = eligible.get(source);
      if (!raceId || !source.startsWith('reports/') || !source.endsWith('.html')) continue;
      if (!a.dataset.originalReportHref) a.dataset.originalReportHref = source;
      const next = 'jra-purchase-rationale.html?race_id=' + encodeURIComponent(raceId);
      if (a.getAttribute('href') !== next) a.setAttribute('href', next);
    }
  }
  Promise.all([
    fetch('data/races.json', {cache:'no-store'}).then(r => { if (!r.ok) throw Error('registry missing'); return r.json(); }),
    fetch('assets/jra-bet-rationale-evidence-v2.json', {cache:'no-store'}).then(r => { if (!r.ok) throw Error('evidence missing'); return r.json(); })
  ]).then(([data, evidence]) => {
    if (evidence.schema_version !== 2 || !evidence.records) return;
    for (const r of data.races || []) {
      const e = evidence.records[r.id];
      if (!e || r.scope !== 'jra-main' ||
          !['predicted', 'reviewed'].includes(r.status) ||
          r.purchase_decision !== 'buy' || !r.report?.startsWith('reports/') ||
          !r.purchase_risk_metrics || !r.final_bets?.length ||
          e.purchase_proof !== r.proof_commit ||
          e.purchase_version !== r.purchase_strategy_version ||
          e.tickets?.length !== r.final_bets.length ||
          r.final_bets.some((b,i) => key(b) !== key(e.tickets[i]) ||
             b.quote_verified !== true || !Number.isInteger(b.stake_yen) || b.stake_yen <= 0)) continue;
      eligible.set(r.report, r.id);
    }
    wire();
    new MutationObserver(wire).observe(host,{childList:true,subtree:true});
  }).catch(() => { /* fail closed: preserve canonical report links */ });
})();
