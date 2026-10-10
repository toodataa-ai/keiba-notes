import fs from 'node:fs';
import path from 'node:path';

// Presentation-only guard. Do not read or modify historical predictions or results.
const slugs = [
  '2026-10-10-saudi-arabia-royal-cup',
  '2026-10-10-mimuro-stakes'
];
const requiredTypes = ['単勝', '複勝', '枠連', '馬連', '馬単', 'ワイド', '三連複', '三連単', 'WIN5'];
let failures = 0;
function assert(value, message) {
  if (!value) { console.error('FAIL: ' + message); failures++; }
}
for (const slug of slugs) {
  const reportPath = path.join('docs', 'reports', `v3.3-${slug}.html`);
  const predictionPath = path.join('e2e_validation', 'predictions', slug, 'v3.3.json');
  const html = fs.readFileSync(reportPath, 'utf8');
  const data = JSON.parse(fs.readFileSync(predictionPath, 'utf8'));
  const bet = data.priority_candidate;
  const selection = bet?.candidate?.selection;
  const separator = bet?.type === '三連単' || bet?.type === '馬単' ? '→' : '-';
  const expected = Array.isArray(selection) ? selection.join(separator) : String(selection ?? '');
  assert(bet && bet.candidate && bet.candidate.label === expected && expected.length > 0,
    `${slug}: best ticket selection/label does not match canonical JSON`);
  assert(html.includes(`最優先の参考候補（購入承認ではない）：${bet.type} ${expected}`),
    `${slug}: best ticket label not rendered from JSON`);
  assert(!/undefined|NaN|\[object Object\]/.test(html),
    `${slug}: unresolved placeholder in report`);
  assert(data.prompt_version === 'v3.3' && data.purchase_decision === 'pass' &&
    data.total_stake_yen === 0 && Array.isArray(data.final_bets) && data.final_bets.length === 0,
    `${slug}: purchase decision not consistent with official v3.3 snapshot`);
  assert(html.includes('最終購入買い目：なし／合計購入金額：0円'),
    `${slug}: display purchase instruction mismatch`);
  assert(html.includes('@page{size:A4 portrait;margin:0}'),
    `${slug}: A4 portrait styling absent`);
  const horsePages = (html.match(/class="page horse"/g) || []).length;
  assert(horsePages === data.runners.length &&
    html.includes(`data-horse-count="${data.runners.length}"`),
    `${slug}: one horse per page source count mismatch`);
  const pageSections = (html.match(/<section class="page/g) || []).length;
  assert(pageSections === data.runners.length + 6,
    `${slug}: original report pages + comparison and WIN5 pages mismatch`);
  const types = data.bet_type_evaluations.map(r => r.type);
  assert(JSON.stringify(types) === JSON.stringify(requiredTypes),
    `${slug}: incomplete or misordered nine ticket types`);
  for (const type of requiredTypes) assert(html.includes(type),
    `${slug}: ticket type ${type} missing from report`);
  console.log(`${slug}: validated priority ${bet.type} ${expected}, ${horsePages} horses, ${pageSections} pages, 9 ticket types.`);
}
if (failures) process.exit(1);
console.log('Both v3.3 snapshot reports passed presentation integrity checks.');
