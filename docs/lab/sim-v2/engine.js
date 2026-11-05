/* JRAレースシミュレータ v2 エンジン（LAB・研究用）
 * ブラウザと node の両方で動く。正式予想・買い目には接続しない。
 *
 * コース：JRA公表の諸元（一周・直線・回り・高低差）から、競技場型（直線2本＋半円2つ）で近似する。
 *   直線の長さ Ls = 公式の直線距離×1.15（ゴール後の余裕）、コーナー半径 R = (一周 − 2Ls) / 2π。
 *   実際のコーナーの形・引き込み線・スタート位置の細部は近似（芝のA〜Dの違いも省略）。
 * 馬：強さ（過去の走りから計算した数字）・先行力・瞬発力・道悪・スタミナ。
 * 走り：各馬の「その日の目標タイム」を、基準タイム−強さ×k＋その日の出来（ばらつき）で決め、
 *   前半・中盤・終盤の速さの配分を、脚質・ペース（先行馬の数）・瞬発力で決める。
 *   走っている間は、進路（内ラチからの距離）・前が詰まったときの減速と進路変更・
 *   コーナーで外を回る距離のロス・最後の直線での外への持ち出しを1歩ずつ計算するので、計画どおりにはいかない。
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.RaceSimV2 = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';

  // ---------- 乱数（再現できるように種つき） ----------
  function rng(seed) {
    let s = (seed >>> 0) || 1;
    const next = () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
    next.normal = () => { let u = 0, v = 0; while (u === 0) u = next(); v = next(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
    return next;
  }

  // ---------- コース ----------
  // route: {venue, surface, layout, turn:'left'|'right', lap_m, straight_m, width_m:[a,b], elevation_m}
  function buildCourse(route, dist) {
    const straightOnly = route.layout === 'straight';
    const width = (route.width_m && route.width_m[0]) || (route.surface === 'dirt' ? 20 : 25);
    if (straightOnly) {
      return { straightOnly: true, lap: dist, Ls: dist + 60, R: 0, dist, goalParam: dist, width, turn: route.turn, elevation: route.elevation_m || 0, home: dist };
    }
    const home = route.straight_m;
    const Ls = Math.max(home * 1.15, home + 40);
    const R = Math.max(55, (route.lap_m - 2 * Ls) / (2 * Math.PI));
    const lap = 2 * Ls + 2 * Math.PI * R;
    return { straightOnly: false, lap, Ls, R, dist, goalParam: home, width, turn: route.turn, elevation: route.elevation_m || 0, home };
  }

  // 「ゴールまで u メートル」の地点の、周回上の位置（0 = 4コーナー出口＝最後の直線の入り口）
  function loopParam(course, u) {
    if (course.straightOnly) return course.goalParam - u;
    let p = (course.goalParam - u) % course.lap; if (p < 0) p += course.lap; return p;
  }
  // 周回位置 p の区間：直線か、コーナーか
  function segmentAt(course, p) {
    const { Ls, R } = course;
    if (course.straightOnly) return { kind: 'straight', name: 'home' };
    const c = Math.PI * R;
    if (p < Ls) return { kind: 'straight', name: 'home', t: p };
    if (p < Ls + c) return { kind: 'curve', name: 'c12', t: p - Ls };
    if (p < 2 * Ls + c) return { kind: 'straight', name: 'back', t: p - Ls - c };
    return { kind: 'curve', name: 'c34', t: p - 2 * Ls - c };
  }
  // 画面用の座標（メートル）。ホームストレッチを下側に置く。lane = 内ラチから外へのメートル
  function xy(course, u, lane) {
    const p = loopParam(course, u);
    const L = course.Ls, R = course.R, sign = course.turn === 'left' ? 1 : -1; // 左回り：下の直線を左→右へ
    if (course.straightOnly) {
      return { x: sign * (p - course.goalParam), y: R + lane, heading: sign > 0 ? 0 : Math.PI };
    }
    const seg = segmentAt(course, p);
    // 下の直線：y = +(R + lane)、x は -L/2 → +L/2（左回り）
    if (seg.name === 'home') {
      const x = -L / 2 + seg.t; return { x: sign * x, y: R + lane, heading: sign > 0 ? 0 : Math.PI };
    }
    if (seg.name === 'c12') {
      const a = Math.PI / 2 - seg.t / R; const r = R + lane;
      return { x: sign * (L / 2 + r * Math.cos(a)), y: r * Math.sin(a), heading: sign > 0 ? a - Math.PI / 2 : Math.PI - (a - Math.PI / 2) };
    }
    if (seg.name === 'back') {
      const x = L / 2 - seg.t; return { x: sign * x, y: -(R + lane), heading: sign > 0 ? Math.PI : 0 };
    }
    const a = -Math.PI / 2 - seg.t / R; const r = R + lane;
    return { x: sign * (-L / 2 + r * Math.cos(a)), y: r * Math.sin(a), heading: sign > 0 ? a - Math.PI / 2 : Math.PI - (a - Math.PI / 2) };
  }
  function inCurve(course, u) { return !course.straightOnly && segmentAt(course, loopParam(course, u)).kind === 'curve'; }
  // ゴールまで u の地点から、最後の直線に入るまでの距離（最後の直線の中なら0）
  function toFinalStraight(course, u) { return Math.max(0, u - course.home); }

  // ---------- 1レース ----------
  // kFin: 強さ1あたりの、最後の区間の速さの差（割合）／ noiseSd: その日の出来のばらつき（強さの単位）
  const DEFAULT = { kFin: 0.04, kCruise: 0.010, noiseSd: 0.4, paceSd: 0.12, leadFade: 0.045, finCap: 0.12, gapK: 0.45, dt: 0.25 };

  function frameOf(no, heads) {
    // JRAの枠番の決め方（頭数が多いとき外の枠に2頭ずつ）
    if (heads <= 8) return no;
    const two = heads - 8; const singles = 8 - two;
    return no <= singles ? no : singles + Math.ceil((no - singles) / 2);
  }

  // レース全体のペース（基準の馬が基準タイムで走る区間ごとの速さ）と、各馬の作戦
  function plan(race, o, R, course) {
    const H = race.runners.length, D = race.dist, Tstd = race.std_time || D / 16.2;
    const mean = race.runners.reduce((s, x) => s + x.strength, 0) / H;
    const nFront = race.runners.filter(x => x.early < 0.28).length;
    const pace = Math.max(-0.5, Math.min(0.7, 0.18 * (nFront - 2.5))) + o.paceSd * R.normal(); // +ならハイペース
    const vref = D / (Tstd - 2.9);                           // スタートの加速・位置取りの損を見込んで、勝ち馬が基準より少し速く走るように合わせた
    const earlyLen = Math.min(D * 0.3, 600);
    const finLen = Math.min(D * 0.4, Math.max(400, course.home + 150));
    const midLen = Math.max(50, D - earlyLen - finLen);
    const vE = vref * (1.012 + 0.02 * pace), vF = vref * (1.0 - 0.012 * pace);
    const vM = midLen / Math.max(midLen / (vref * 1.2), D / vref - earlyLen / vE - finLen / vF);
    const horses = race.runners.map((x, i) => {
      const s = (x.strength - mean) + o.noiseSd * R.normal() * (0.8 + 0.25 * Math.min(2.5, x.sd || 1.4) / 1.4) * (x.debut ? 1.2 : 1);
      const lead = 0.5 - x.early;                                 // 先行型ほど＋
      return { i, no: x.no, frame: frameOf(x.no, H), s, lead,
        cruise: vref * (1 + o.kCruise * s),                        // 無理なく走れる速さ
        fin: vF * (1 + o.finCap * Math.tanh((o.kFin * s + 0.006 * (x.kick || 0) - o.leadFade * lead) / o.finCap)),  // 速さの差は最大±finCap（現実の上がりの差の範囲に抑える）         // 最後の区間の速さ
        gap: Math.max(0, x.early) * (H * o.gapK) + 1.0 * R.normal(),   // 先頭から何m後ろにつけたいか
        styleLane: (lead > 0.15 ? 0.8 : lead > -0.1 ? 1.5 : 2.2) + 2.6 * R() + 0.05 * (x.no - 1) };
    });
    return { pace, vE, vM, vF, earlyLen, finLen, horses };
  }

  function simulate(race, opts = {}) {
    const o = Object.assign({}, DEFAULT, opts);
    const R = rng(o.seed || 1);
    const course = race._course || buildCourse(race.route, race.dist);
    const H = race.runners.length, D = race.dist;
    const PL = plan(race, o, R, course), P = PL.horses;
    const st = P.map(p => ({ u: D, v: 0, lane: 0.6 + (p.no - 1) * 1.05, done: false, t: null, blocked: 0, effort: 0, bank: 0 }));
    const rec = o.record ? [] : null; let t = 0; const dt = o.dt; let finished = 0;
    const maxT = (race.std_time || D / 15) * 1.6 + 30;
    while (finished < H && t < maxT) {
      const order = st.map((s, i) => i).sort((a, b) => st[a].u - st[b].u);
      const leadU = st[order.find(i => !st[i].done) ?? 0].u;
      for (const i of order) {
        const s = st[i], p = P[i];
        if (s.done) continue;
        const run = D - s.u;
        const final = s.u <= PL.finLen;
        let vt;
        if (!final) {
          // 道中：全体のペースに合わせ、狙いの位置（先頭から gap m 後ろ）へ少しずつ寄せる
          const base = run < PL.earlyLen ? PL.vE : PL.vM;
          const behind = (s.u - leadU) - p.gap;                     // ＋なら後ろすぎ
          vt = base * (1 + 0.012 * p.lead * (run < PL.earlyLen ? 1 : 0)) + Math.max(-0.8, Math.min(0.8, 0.12 * behind));
        } else {
          // 最後の区間：その馬の末脚。道中で無理をした分は鈍り、脚を溜めた分は伸びる
          vt = p.fin * (1 - Math.min(0.08, s.effort / 900)) + Math.min(0.5, s.bank / 60);
          // 先行馬はハイペースで苦しく、スローなら残る
          vt *= 1 - 0.018 * p.lead * PL.pace;
          // 最後の直線の坂（高低差の大きいコース）
          if (s.u < course.home * 0.6 && course.elevation > 2) vt *= 1 - 0.003 * course.elevation * (1 - 0.15 * (race.runners[i].power || 0));
        }
        // 道中で、自分の楽な速さより速く走った分は疲れとしてたまる
        if (!final && run > 60) s.effort += Math.max(0, s.v - p.cruise) * dt;
        const acc = run < 40 ? 4.5 : (final ? 1.2 : 0.8);
        let v = s.v + Math.max(-2.0 * dt, Math.min(acc * dt, vt - s.v));
        // 進路：基本の位置。最後の直線では差し・追込は外へ。前が詰まったら空いている進路を探す
        const inFinal = s.u < course.home;
        let want = p.styleLane + (inFinal && p.lead < 0.05 ? 2.0 + 1.5 * (-p.lead) : 0);
        let ahead = null;
        for (const j of order) {
          if (j === i || st[j].done) continue;
          const du = s.u - st[j].u;
          if (du > 0 && du < (final ? 12 : 5) && Math.abs(st[j].lane - s.lane) < 0.8 && st[j].v < vt) { ahead = j; break; }
        }
        if (ahead !== null) {
          const cands = final ? [1.0, -1.0, 2.0, -2.0, 3.0, 4.0] : [-1.0, 1.0, 2.0];
          for (const d of cands) {
            const L = s.lane + d; if (L < 0.5 || L > course.width - 1) continue;
            let clear = true;
            for (const j of order) { if (j === i || st[j].done) continue; const du = s.u - st[j].u; if (du > -1.2 && du < (final ? 10 : 6) && Math.abs(st[j].lane - L) < 0.75) { clear = false; break; } }
            if (clear) { want = L; break; }
          }
        }
        const side = Math.sign(want - s.lane);
        let free = true;
        for (const j of order) {
          if (j === i || st[j].done) continue;
          if (Math.abs(st[j].u - s.u) < 1.6 && (st[j].lane - s.lane) * side > 0 && Math.abs(st[j].lane - s.lane) < 0.9) { free = false; break; }
        }
        const lat = run < 400 ? 1.4 : (final ? 1.3 : 1.0);
        if (free) s.lane += Math.max(-lat * dt, Math.min(lat * dt, want - s.lane));
        s.lane = Math.max(0.5, Math.min(course.width - 1, s.lane));
        const k = inCurve(course, s.u) ? course.R / (course.R + s.lane) : 1;
        let adv = v * k * dt;
        // 前の馬にぶつからない（同じ進路で約2.1m以内には入れない）
        let wall = -Infinity, wj = -1;
        for (const j of order) {
          if (j === i || st[j].done) continue;
          if (run > 120 && st[j].u < s.u && Math.abs(st[j].lane - s.lane) < 0.7 && st[j].u + 2.1 > wall) { wall = st[j].u + 2.1; wj = j; }
        }
        if (s.u - adv < wall) {
          const ok = Math.max(0, s.u - wall);
          const lost = adv - ok;
          if (lost > 0.05) { s.blocked += dt; if (!final) s.bank += lost * 0.6; }
          adv = ok; v = Math.min(v, Math.max(st[wj].v, v - 1.5 * dt));
        }
        s.v = v;
        if (s.u - adv <= 0) { s.t = t + s.u / Math.max(0.1, v * k); s.u = 0; s.done = true; finished++; }
        else s.u -= adv;
      }
      t += dt;
      if (rec && Math.round(t / dt) % 2 === 0) rec.push({ t: +t.toFixed(2), h: st.map(s => [Math.round(s.u * 10) / 10, Math.round(s.lane * 100) / 100, +s.v.toFixed(2)]) });
    }
    st.forEach(s => { if (!s.done) s.t = t + s.u / 10; });
    const res = st.map((s, i) => ({ i, no: P[i].no, frame: P[i].frame, time: s.t, blocked: s.blocked }))
      .sort((a, b) => a.time - b.time);
    res.forEach((r, k) => r.pos = k + 1);
    return { results: res, record: rec, course, pace: PL.pace, plan: P };
  }

  function monteCarlo(race, n = 300, opts = {}) {
    const H = race.runners.length;
    const win = new Array(H).fill(0), top3 = new Array(H).fill(0), avgPos = new Array(H).fill(0);
    race._course = race._course || buildCourse(race.route, race.dist);
    for (let k = 0; k < n; k++) {
      const r = simulate(race, Object.assign({}, opts, { seed: (opts.seed || 7) * 7919 + k * 104729 + 13, record: false }));
      r.results.forEach(x => { if (x.pos === 1) win[x.i]++; if (x.pos <= 3) top3[x.i]++; avgPos[x.i] += x.pos; });
    }
    return race.runners.map((x, i) => ({ no: x.no, win: win[i] / n, top3: top3[i] / n, avgPos: avgPos[i] / n }));
  }

  return { rng, buildCourse, xy, loopParam, segmentAt, inCurve, simulate, monteCarlo, frameOf, DEFAULT };
});
