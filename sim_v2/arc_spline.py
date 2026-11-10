"""直線と円弧だけでできた軌跡（G1連続）を、なめらかな参照線にあてはめる。

ルール
  * 軌跡は直線と円弧だけ。円弧は常に走路の内側へ曲がる（円の中心が内側）＝曲率は一方向（0以上）。
  * 直線と円弧の継ぎ目は向きがぴったり一致（積分で作るので必ず一致）。
  * 中心線からのずれは走路の幅の10%以内。
  * 部品（直線＋円弧）の数はできるだけ少なく（少ない数から順に試して、最初に許容内へ入ったものを採用）。
作り方：向き θ(s) を曲率一定の区間（直線は曲率0）で区切る → 区間の数を増やしながら最小二乗＋等式制約（一周で閉じる）で詰める。
"""
import math
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter1d


def _adv(x, y, th, l, k):
    if abs(k) < 1e-9:
        return x + l * math.cos(th), y + l * math.sin(th), th
    return x + (math.sin(th + k * l) - math.sin(th)) / k, y + (math.cos(th) - math.cos(th + k * l)) / k, th + k * l


class Spline:
    """始点 (x,y)・向き th0 から、(長さ, 曲率) の部品を順につないだもの。"""

    def __init__(self, x, y, th, L, K):
        self.L = [float(a) for a in L]; self.K = [float(a) for a in K]
        self.st = [(float(x), float(y), float(th))]
        for l, k in zip(self.L, self.K):
            self.st.append(_adv(*self.st[-1], l, k))
        self.cum = np.concatenate([[0.0], np.cumsum(self.L)])
        self.length = float(self.cum[-1])

    def end(self):
        return self.st[-1]

    def at(self, s):
        """道のり s の位置と向き（閉じた線なら s は一周で巻き戻す）"""
        i = int(np.clip(np.searchsorted(self.cum, s, side="right") - 1, 0, len(self.L) - 1))
        x, y, th = _adv(*self.st[i], float(s - self.cum[i]), self.K[i])
        return x, y, th

    def sample(self, step=1.0):
        out = []
        for (x, y, th), l, k in zip(self.st, self.L, self.K):
            n = max(1, int(math.ceil(l / step)))
            t = np.linspace(0, l, n + 1)[:-1]
            if abs(k) < 1e-9:
                out.append(np.c_[x + t * math.cos(th), y + t * math.sin(th)])
            else:
                out.append(np.c_[x + (np.sin(th + k * t) - math.sin(th)) / k, y + (math.cos(th) - np.cos(th + k * t)) / k])
        out.append(np.array([self.st[-1][:2]]))
        return np.vstack(out)

    def vertices(self, s0=0.0, s1=None, sag=0.03):
        """s0〜s1 の部分を、円弧のたるみ（弦の誤差）が sag 画素以下になる点列で返す"""
        s1 = self.length if s1 is None else s1
        pts = []
        for i, (l, k) in enumerate(zip(self.L, self.K)):
            a, b = max(s0, self.cum[i]), min(s1, self.cum[i + 1])
            if b <= a + 1e-9:
                continue
            if abs(k) < 1e-9:
                n = 1
            else:
                R = 1.0 / k; n = max(1, int(math.ceil((b - a) / math.sqrt(8 * R * sag))))
            for t in np.linspace(a, b, n + 1)[:-1]:
                pts.append(self.at(t)[:2])
        pts.append(self.at(s1)[:2])
        return np.array(pts)

    def kinds(self):
        return "".join("L" if abs(k) < 1e-9 else "A" for k in self.K)


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def heading_curv(P, closed, sig=6.0):
    """1画素間隔の点列から、向きθ（つながるように展開）と曲率κ"""
    if closed:
        d = np.roll(P, -1, axis=0) - P
    else:
        d = np.diff(P, axis=0); d = np.vstack([d, d[-1:]])
    th = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    dth = np.gradient(th) if not closed else (np.roll(th, -1) - th)
    if closed:
        dth[-1] = wrap(th[0] - th[-1])
    k = gaussian_filter1d(dth / np.maximum(np.linalg.norm(d, axis=1), 1e-6), sig, mode="wrap" if closed else "nearest")
    return th, k


def dp_segments(kap, h, lam, mu, kmin=1 / 900.0):
    """曲率の列を、曲率一定（直線は0、円弧は正）の区間に分ける。区間ごとの罰 lam、円弧には余分に mu。"""
    n = len(kap)
    S1 = np.concatenate([[0], np.cumsum(kap)]); S2 = np.concatenate([[0], np.cumsum(kap ** 2)])
    best = np.full(n + 1, np.inf); best[0] = 0; prev = np.zeros(n + 1, int); typ = np.zeros(n + 1, int)
    for j in range(1, n + 1):
        i = np.arange(0, j); m = j - i
        s1 = S1[j] - S1[i]; s2 = S2[j] - S2[i]
        line = s2 + lam
        arc = np.where(s1 / m >= kmin, s2 - s1 ** 2 / m, np.inf) + lam + mu
        c = np.minimum(line, arc); tot = best[i] + c
        a = int(np.argmin(tot)); best[j] = tot[a]; prev[j] = a; typ[j] = 0 if line[a] <= arc[a] else 1
    segs = []; j = n
    while j > 0:
        i = prev[j]; s1 = S1[j] - S1[i]
        segs.append((i, j, 0.0 if typ[j] == 0 else s1 / (j - i))); j = i
    segs.reverse()
    out = []   # 隣り合う直線は一本に
    for i, j, k in segs:
        if out and k == 0.0 and out[-1][2] == 0.0:
            out[-1] = (out[-1][0], j, 0.0)
        else:
            out.append((i, j, k))
    return out


def _dist(model_pts, ref):
    """参照点から折れ線（モデルの標本点）までの距離（点と線分の距離なので、パラメータに対してなめらか）"""
    tree = cKDTree(model_pts)
    _, i = tree.query(ref)
    n = len(model_pts); i0 = np.clip(i - 1, 0, n - 2); i1 = np.clip(i, 0, n - 2)
    best = np.full(len(ref), np.inf)
    for j in (i0, i1):
        a = model_pts[j]; b = model_pts[j + 1]; ab = b - a
        u = np.clip(np.einsum("ij,ij->i", ref - a, ab) / np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-12), 0, 1)
        best = np.minimum(best, np.linalg.norm(ref - (a + u[:, None] * ab), axis=1))
    return best


def _res(d, tol):
    z = d / tol
    return z * (1 + z * z)


def _polish(eq, v, free):
    """等式 eq(v)=0 を、v をなるべく動かさずにぴったり満たす（ガウス・ニュートン）"""
    v = v.copy()
    for _ in range(12):
        g = eq(v)
        if np.abs(g).max() < 1e-9:
            break
        J = np.zeros((len(g), len(v)))
        for k in free:
            e = np.zeros(len(v)); e[k] = 1e-6
            J[:, k] = (eq(v + e) - eq(v - e)) / 2e-6
        v = v - np.linalg.pinv(J) @ g
    return v


def fit_closed(C, tol, h=4, verbose=False):
    """閉じた中心線 C（1画素間隔・曲がる向きが正になる座標系）→ Spline。部品が少ない順に、許容 tol に入る最初のもの。"""
    th, kap = heading_curv(C, True)
    # 円弧のはじまりを区切りの先頭にする
    up = np.nonzero((kap > 0.4 * kap.max()) & (np.roll(kap, 1) <= 0.4 * kap.max()))[0]
    n0 = int(up[0]) if len(up) else 0
    C = np.roll(C, -n0, axis=0); kap = np.roll(kap, -n0); th = np.roll(th, -n0)
    nb = len(kap) // h
    kb = kap[:nb * h].reshape(nb, h).mean(axis=1)
    Etot = float(np.sum(kb ** 2))
    ref = np.vstack([C, C[:1]])[::5]
    tried = None; found = []
    for lam_rel in np.geomspace(3e-2, 1e-7, 40):
        segs = dp_segments(kb, h, lam_rel * Etot, 0.3 * lam_rel * Etot)
        if len(segs) > 14:
            break
        if tried is not None and len(segs) == tried:
            continue
        tried = len(segs)
        res = _refine_closed(C, ref, segs, h, th[0], tol)
        if verbose:
            print("   closed", len(segs), "pieces", None if res is None else round(res[1], 2))
        if res is None:
            continue
        if res[1] <= tol:
            return res[0], res[1], n0
        found.append(res)
    if not found:
        return None
    # 許容に入るものが無い（曲がる向きが一方向という条件では、S字のところで届かない）：いちばんずれの小さいものに近く、部品が最も少ないもの
    mn = min(r[1] for r in found)
    for r in found:
        if r[1] <= mn * 1.1:
            return r[0], r[1], n0


def _refine_closed(C, ref, segs, h, th0, tol):
    n = len(segs)
    L0 = [(j - i) * h for i, j, k in segs]; L0[-1] += len(C) - sum(L0)
    K0 = [k for i, j, k in segs]
    arc = [i for i in range(n) if K0[i] > 0]
    if not arc:
        return None
    tot = sum(l * k for l, k in zip(L0, K0))
    K0 = [k * 2 * math.pi / tot if k > 0 else 0.0 for k in K0]

    def build(v):
        L = np.maximum(v[3:3 + n], 0.5); K = np.zeros(n); K[arc] = np.maximum(v[3 + n:], 0.1) / 100.0
        return v[0], v[1], v[2], L, K

    def eq(v):
        x0, y0, t0, L, K = build(v)
        x, y, t = x0, y0, t0
        for l, k in zip(L, K):
            x, y, t = _adv(x, y, t, l, k)
        return np.array([x - x0, y - y0, (t - t0 - 2 * math.pi) * 100.0])

    def fun(v):
        x0, y0, t0, L, K = build(v)
        r = _res(_dist(Spline(x0, y0, t0, L, K).sample(1.0), ref), tol)
        return np.concatenate([r, 30.0 * eq(v)])

    v0 = np.concatenate([[C[0, 0], C[0, 1], th0], L0, [K0[i] * 100.0 for i in arc]])
    free = list(range(len(v0)))
    try:
        lo = np.concatenate([[-np.inf] * 3, np.full(n, 1.0), np.full(len(arc), 0.1)]); hi = np.concatenate([[np.inf] * 3, np.full(n, np.inf), np.full(len(arc), 20.0)])
        r = least_squares(fun, np.clip(v0, lo + 1e-9, hi - 1e-9), bounds=(lo, hi), x_scale=np.concatenate([[10, 10, 0.1], np.full(n, 50.0), np.full(len(arc), 1.0)]), max_nfev=60, diff_step=1e-6)
        v = _polish(eq, r.x, free)
    except Exception:
        return None
    if np.abs(eq(v)).max() > 1e-6:
        return None
    x0, y0, t0, L, K = build(v)
    sp = Spline(x0, y0, t0, L, K)
    return sp, float(_dist(sp.sample(0.25), ref).max()), v


def tangent_inits(S, loop, s_hint):
    """S から loop の円弧へ接線を引く（左曲がりの向きに入るもの）。[(th0, 長さ, s*)] を s_hint に近い順に返す"""
    out = []
    for (x, y, th), l, k, c0 in zip(loop.st, loop.L, loop.K, loop.cum):
        if k < 1e-9:
            continue
        R = 1.0 / k; cx, cy = x - R * math.sin(th), y + R * math.cos(th)
        dx, dy = S[0] - cx, S[1] - cy; d = math.hypot(dx, dy)
        if d <= R:
            continue
        a0 = math.atan2(dy, dx); da = math.acos(R / d)
        for sg in (1, -1):
            beta = a0 + sg * da
            Tx, Ty = cx + R * math.cos(beta), cy + R * math.sin(beta)
            lin = math.atan2(Ty - S[1], Tx - S[0])
            if abs(wrap(lin - (beta + math.pi / 2))) > 1e-6:
                continue
            off = wrap(beta - (th - math.pi / 2))      # 円弧の始点から弧に沿って進んだ角
            if off < 0:
                off += 2 * math.pi
            if off * R > l:
                continue
            out.append((lin, math.hypot(Tx - S[0], Ty - S[1]), c0 + off * R))
    out.sort(key=lambda a: abs(a[2] - s_hint))
    return out[:3]


def fit_chute(S, ref, loop, tol, s_hint, h=3, verbose=False, max_shift=None, pin_th=None, s_max=None, nu_max=20.0, keys=None):
    """発走地点 S から、閉じた軌跡 loop（Spline）へ乗り移る直線＋円弧（loop に接して入る）。
    ref：なぞりたい元の線（S から合流のあたりまで、1画素間隔）。発走の印は max_shift 画素までなら動かしてよい。
    返り値は (Spline, 最大ずれ, 合流位置 s*)。"""
    max_shift = tol if max_shift is None else max_shift
    th, kap = heading_curv(ref, False, 4.0)
    nb = max(1, len(kap) // h)
    kb = kap[:nb * h].reshape(nb, h).mean(axis=1)
    Etot = float(np.sum(kb ** 2)) + 1e-12
    T = len(ref); turn = max(float(th[-1] - th[0]), 0.01)
    cands = []; seen = set()
    for lam_rel in np.geomspace(0.3, 1e-6, 40):
        segs = dp_segments(kb, h, lam_rel * Etot, 0.3 * lam_rel * Etot)
        key = "".join("A" if k > 0 else "L" for _, _, k in segs)
        if len(segs) > 5 or key in seen:
            continue
        seen.add(key); cands.append((key, segs))
    for key in (("L", "LA", "AL", "LAL") if pin_th is not None else ("L", "LA", "AL", "LAL", "ALA", "LALA", "LAAL", "AAL")):   # 数が少ない順に、足りない型も試す
        if key in seen:
            continue
        seen.add(key)
        na = key.count("A"); w = T / len(key)
        segs = [(int(i * w / h), int((i + 1) * w / h), (turn / (na * w)) if c == "A" else 0.0) for i, c in enumerate(key)]
        cands.append((key, segs))
    if keys:   # 型を指定（例：最後の直線を、半径の大きい円弧に置き換える）
        cands = [c for c in cands if c[0] in keys]
        for key in keys:
            if all(c[0] != key for c in cands):
                na = key.count("A"); w = T / len(key)
                cands.append((key, [(int(i * w / h), int((i + 1) * w / h), (turn / (na * w)) if c == "A" else 0.0) for i, c in enumerate(key)]))
    cands.sort(key=lambda c: (len(c[0]), c[0].count("A")))
    best = None
    tans = [] if pin_th is not None else tangent_inits(S, loop, s_hint)
    runs = []
    for key, segs in cands:
        runs.append((key, segs, th[0], s_hint, None))
        for (t0, l0, s0) in tans:
            runs.append((key, segs, t0, s0, l0))
    for key, segs, th_init, s_init, l_init in runs:
        if l_init is not None and key[0] != "L":
            continue
        if l_init is not None:
            segs = [(0, max(1, int(l_init / h)), 0.0)] + list(segs[1:])
        r = _refine_chute(S, ref, segs, h, th_init if pin_th is None else pin_th, loop, tol, s_init, max_shift, s_hint, pin_th, s_max, nu_max)
        if verbose:
            print("   chute", key, None if r is None else round(r[1], 2))
        if r is not None and r[1] <= tol:
            return r
        if r is not None and (best is None or r[1] < best[1]):
            best = r
    return best


def _refine_chute(S, ref, segs, h, th0, loop, tol, s_hint, max_shift, s_anchor=None, pin_th=None, s_max=None, nu_max=20.0):
    s_anchor = s_hint if s_anchor is None else s_anchor
    n = len(segs)
    L0 = [max(1.0, (j - i) * h) for i, j, k in segs]
    K0 = [k for i, j, k in segs]
    arc = [i for i in range(n) if K0[i] > 0]
    Lloop = loop.length if s_max is None else s_max
    LP = loop.sample(0.5)

    def model(sp, s, step):      # 引き込み線＋合流したあとの本線（なぞる線は合流のあとも本線の上を続く）
        k = int(max(0.0, s) * 2)
        return np.vstack([sp.sample(step), LP[k:k + 700]])

    def build(v):
        L = np.maximum(v[3:3 + n], 0.5); K = np.zeros(n); K[arc] = np.maximum(v[3 + n:3 + n + len(arc)], 0.1) / 100.0
        return v[0], v[1], v[2], L, K, v[-1]

    def eq(v):
        x0, y0, t0, L, K, s = build(v)
        x, y, t = x0, y0, t0
        for l, k in zip(L, K):
            x, y, t = _adv(x, y, t, l, k)
        X, Y, T = loop.at(min(max(s, 0.0), loop.length))
        return np.array([x - X, y - Y, wrap(t - T) * 100.0])

    def fun(v):
        x0, y0, t0, L, K, s = build(v)
        r = _res(_dist(model(Spline(x0, y0, t0, L, K), s, 1.0), ref), tol)
        sh = math.hypot(x0 - S[0], y0 - S[1])
        return np.concatenate([r, 30.0 * eq(v), [0.03 * (v[-1] - s_anchor)], [max(0.0, sh - max_shift) * 3.0 / tol * 10 + sh * 0.3 / tol]])

    v0 = np.concatenate([[S[0], S[1], th0], L0, [K0[i] * 100.0 for i in arc], [s_hint]])
    try:
        lo = np.concatenate([[-np.inf] * 3, np.full(n, 1.0), np.full(len(arc), 0.1), [(Lloop - 25.0) if pin_th is not None else max(0.0, s_anchor - 800)]])
        hi = np.concatenate([[np.inf] * 3, np.full(n, np.inf), np.full(len(arc), nu_max), [Lloop]])
        if pin_th is not None:      # 始点の位置と向きを固定（直前の線にぴったりつなぐ）
            for k_, val in enumerate((S[0], S[1], pin_th)):
                lo[k_] = val - 1e-9; hi[k_] = val + 1e-9
        r = least_squares(fun, np.clip(v0, lo + 1e-12, hi - 1e-12), bounds=(lo, hi), x_scale=np.concatenate([[3, 3, 0.1], np.full(n, 30.0), np.full(len(arc), 1.0), [30.0]]), max_nfev=80, diff_step=1e-6)
        v = _polish(eq, r.x, list(range(3 if pin_th is not None else 0, len(v0))))
        if v[-1] > Lloop + 1e-6 or v[-1] < 0 or (pin_th is not None and v[-1] < Lloop - 25.0 - 1e-6):
            return None
    except Exception:
        return None
    if np.abs(eq(v)).max() > 1e-6:
        return None
    x0, y0, t0, L, K, s = build(v)
    if math.hypot(x0 - S[0], y0 - S[1]) > max_shift + 1e-6:
        return None
    sp = Spline(x0, y0, t0, L, K)
    return sp, float(_dist(model(sp, s, 0.25), ref).max()), min(s, Lloop)


def rebase(sp, s0):
    """閉じた Spline の始点を道のり s0 の位置へずらす（部品は途中で二つに割る）"""
    i = int(np.clip(np.searchsorted(sp.cum, s0, side="right") - 1, 0, len(sp.L) - 1))
    x, y, th = sp.at(s0)
    first = sp.cum[i + 1] - s0
    L = [first] + sp.L[i + 1:] + sp.L[:i] + [s0 - sp.cum[i]]
    K = [sp.K[i]] + sp.K[i + 1:] + sp.K[:i] + [sp.K[i]]
    keep = [j for j, l in enumerate(L) if l > 1e-6]
    return Spline(x, y, th, [L[j] for j in keep], [K[j] for j in keep])
