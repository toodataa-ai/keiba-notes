// シミュレータ v2 の当たり具合の検証（node）。入力は非公開の作業用ファイル（公開しない）。
// 使い方: node tools/sim_v2_backtest.cjs <eng_races.json> <mode:calib|test> [n_races] [n_sims] [kSec] [noiseSd]
const E = require('../docs/lab/sim-v2/engine.js');
const [, , file, mode = 'test', nR = '400', nS = '120', k = '', sd = '', lf = ''] = process.argv;
const all = require(require('path').resolve(file)).races.filter(r => r.std_time && r.runners.every(x => x.finish));
const split = '2026-03-01';
const pool = all.filter(r => mode === 'calib' ? r.date < split : r.date >= split);
// 毎回同じ並びで間引く
const step = Math.max(1, Math.floor(pool.length / +nR));
const races = pool.filter((_, i) => i % step === 0).slice(0, +nR);
function ll(ps, r) { const w = r.runners.findIndex(x => x.finish === 1); return -Math.log(Math.max(ps[w], 1e-6)); }
function softmax(z) { const m = Math.max(...z); const e = z.map(x => Math.exp(x - m)); const s = e.reduce((a, b) => a + b, 0); return e.map(x => x / s); }
function evalCfg(kSec, noiseSd) {
  let L = 0;
  for (const r of races) {
    const mc = E.monteCarlo(r, +nS, { kFin: kSec, noiseSd, seed: 11, ...(lf ? { leadFade: +lf } : {}) });
    const H = r.runners.length; const ps = mc.map(m => (m.win * +nS + 0.5) / (+nS + 0.5 * H));
    L += ll(ps, r);
  }
  return L / races.length;
}
const base = { odds: 0, model: 0, uniform: 0 };
for (const r of races) {
  const o = r.runners.map(x => 1 / x.odds); const so = o.reduce((a, b) => a + b, 0);
  base.odds += ll(o.map(x => x / so), r); base.model += ll(softmax(r.runners.map(x => x.strength)), r); base.uniform += Math.log(r.runners.length);
}
for (const kk in base) base[kk] = +(base[kk] / races.length).toFixed(4);
console.log(JSON.stringify({ mode, races: races.length, sims: +nS, base }));
const grid = k ? [[+k, +sd]] : [[0.35, 0.7], [0.5, 0.7], [0.5, 1.0], [0.7, 1.0], [0.7, 1.3], [0.9, 1.3], [0.9, 1.6], [1.1, 1.6]];
for (const [kSec, noiseSd] of grid) {
  const t = Date.now(); const v = evalCfg(kSec, noiseSd);
  console.log(JSON.stringify({ kSec, noiseSd, ll: +v.toFixed(4), ms: Date.now() - t }));
}
