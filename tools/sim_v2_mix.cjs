// シミュレータの勝率と、能力値だけの確率を混ぜたら当たり具合が上がるか（検証期間）。入力は非公開の作業用ファイル。
const E = require('../docs/lab/sim-v2/engine.js');
const [, , file, nR = '300', nS = '120', kFin = '0.04', noiseSd = '0.4', mode = 'test'] = process.argv;
const all = require(require('path').resolve(file)).races.filter(r => r.std_time && r.runners.every(x => x.finish));
const pool = all.filter(r => mode === 'calib' ? r.date < '2026-03-01' : r.date >= '2026-03-01');
const step = Math.max(1, Math.floor(pool.length / +nR)); const races = pool.filter((_, i) => i % step === 0).slice(0, +nR);
const sm = z => { const m = Math.max(...z); const e = z.map(x => Math.exp(x - m)); const s = e.reduce((a, b) => a + b, 0); return e.map(x => x / s); };
const W = [0, 0.1, 0.2, 0.3, 0.5, 0.7, 1]; const L = W.map(() => 0); let Lo = 0, Lm = 0;
for (const r of races) {
  const mc = E.monteCarlo(r, +nS, { kFin: +kFin, noiseSd: +noiseSd, seed: 5 }); const H = r.runners.length;
  const ps = mc.map(m => (m.win * +nS + 0.5) / (+nS + 0.5 * H)); const pm = sm(r.runners.map(x => x.strength));
  const w = r.runners.findIndex(x => x.finish === 1);
  W.forEach((a, k) => { const q = ps.map((p, i) => Math.pow(p, a) * Math.pow(pm[i], 1 - a)); const s = q.reduce((x, y) => x + y, 0); L[k] -= Math.log(q[w] / s); });
  const o = r.runners.map(x => 1 / x.odds); const so = o.reduce((a, b) => a + b, 0); Lo -= Math.log(o[w] / so); Lm -= Math.log(pm[w]);
}
console.log(JSON.stringify({ mode, races: races.length, sims: +nS, odds: +(Lo / races.length).toFixed(4), model: +(Lm / races.length).toFixed(4), mix: Object.fromEntries(W.map((a, k) => [a, +(L[k] / races.length).toFixed(4)])) }));
