#!/usr/bin/env python3
"""競馬場の傾向ページ用：発走地点からゴールまでの道すじを、走路の帯の「中央」を通るなめらかな線で作り直す。

これまでの線は内ラチ（帯の内側のふち・白いすき間）をなぞっていて、合流もカクッと曲がっていた。
ここでは次のように作る。
  1. 各走路（芝・ダート・内回り・外回り）ごとに、帯の中央を通る一周の線（中心線）を作る。
     どの帯がその走路かは、既存のなぞり線（umapot-shapes.json）の近くだけを使うことで決める。
  2. 各発走地点から、帯の中だけを通って中心線に乗り、ゴール手前まで進む（ゴール線は逆向きに越えられない）。
  3. 距離が一周より長いときは、その分の周回を足す。
  4. 全体をなめらかにして、点を間引く。
発走地点の位置（x, y）と距離の札は、既存の umapot-starts.json のものをそのまま使う（元図が無くても作り直せる）。
umapot-shapes.json（LABのシミュレータが使う内ラチの線）は変更しない。

  python3 -m sim_v2.build_course_paths --shapes docs/lab/sim-v2/umapot-shapes.json \
      --starts docs/lab/sim-v2/umapot-starts.json --img-root docs/lab/sim-v2/umapot [--write] [--overlay <dir>]
"""
import argparse, json, math
from pathlib import Path
import cv2, numpy as np
from . import arc_paths
from scipy import ndimage as ndi
from skimage.graph import MCP_Geometric
import scipy.sparse as sp, scipy.sparse.linalg as spl

GREEN = (0, 176, 80); ORANGE = (197, 90, 17)

# 図の上で道が二手に分かれていて、どちらを通るかを決める必要がある発走だけ、通らない側に壁を置く（背景画像の画素）。
# 東京芝2000m：1コーナー奥のポケットから外側の大きな弧を回って向正面へ（斜めの直線は1800mの発走用）。
BARRIERS = {("tokyo", "2000"): [((750, 245), (825, 190))]}


def mask(img, rgb, tol=60):
    d = np.abs(img.astype(int) - np.array(rgb[::-1])).sum(axis=2)
    return (d < tol).astype(np.uint8) * 255


def arclen(P):
    return np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])


def resample(P, step):
    P = np.asarray(P, float); d = arclen(P)
    n = max(2, int(round(d[-1] / step)) + 1); t = np.linspace(0, d[-1], n)
    return np.stack([np.interp(t, d, P[:, 0]), np.interp(t, d, P[:, 1])], axis=1)


def smooth_closed(P, sigma):
    Q = resample(np.vstack([P, P[:1]]), 1.0)[:-1]
    return np.stack([ndi.gaussian_filter1d(Q[:, i], sigma, mode="wrap") for i in (0, 1)], axis=1)


def smooth_open(P, sigma):
    """両端を動かさずになめらかにする（端は点対称に折り返す）。"""
    Q = resample(P, 1.0); n = len(Q); pad = min(n - 1, int(4 * sigma))
    if pad < 2:
        return Q
    head = 2 * Q[0] - Q[pad:0:-1]; tail = 2 * Q[-1] - Q[-2:-pad - 2:-1]
    E = np.vstack([head, Q, tail])
    S = np.stack([ndi.gaussian_filter1d(E[:, i], sigma, mode="nearest") for i in (0, 1)], axis=1)
    return S[pad:pad + n]


def rdp(P, eps):
    """点の間引き（線の形は eps 画素以内で保つ）。"""
    P = np.asarray(P, float); keep = np.zeros(len(P), bool); keep[0] = keep[-1] = True
    st = [(0, len(P) - 1)]
    while st:
        a, b = st.pop()
        if b <= a + 1:
            continue
        v = P[b] - P[a]; L = np.hypot(*v) or 1.0
        d = np.abs(v[0] * (P[a + 1:b, 1] - P[a, 1]) - v[1] * (P[a + 1:b, 0] - P[a, 0])) / L
        i = int(np.argmax(d))
        if d[i] > eps:
            k = a + 1 + i; keep[k] = True; st += [(a, k), (k, b)]
    return P[keep]


def band_width(M):
    dt = ndi.distance_transform_edt(M > 0)
    return 4.0 * float(np.median(dt[M > 0]))


def centre_cost(A, half):
    dt = ndi.distance_transform_edt(A)
    pen = np.clip((half - dt) / half, 0, 1)
    return np.where(A, 1.0 + 10.0 * pen, np.inf)


def run_centre(col, y_near):
    """縦1列の中で、y_near に一番近い帯の中央の y。"""
    ys = np.nonzero(col)[0]
    if not len(ys):
        return None
    runs = np.split(ys, np.nonzero(np.diff(ys) > 1)[0] + 1)
    r = min(runs, key=lambda r: 0 if r[0] <= y_near <= r[-1] else min(abs(r[0] - y_near), abs(r[-1] - y_near)))
    return float(r.mean())


def path_between(cost, a, b):
    mcp = MCP_Geometric(cost, fully_connected=True)
    c, _ = mcp.find_costs([(int(round(a[1])), int(round(a[0])))], [(int(round(b[1])), int(round(b[0])))])
    if not np.isfinite(c[int(round(b[1])), int(round(b[0]))]):
        return None
    return np.array(mcp.traceback((int(round(b[1])), int(round(b[0])))))[:, ::-1].astype(float)


def snap(A, p):
    ys, xs = np.nonzero(A); j = int(np.argmin((xs - p[0]) ** 2 + (ys - p[1]) ** 2)); return (float(xs[j]), float(ys[j]))


def line_dist(shape, P, closed=True):
    """線 P からの距離（画素）。"""
    m = np.ones(shape, np.uint8); Q = np.round(np.vstack([P, P[:1]]) if closed else P).astype(np.int32)
    cv2.polylines(m, [Q], False, 0, 1)
    return ndi.distance_transform_edt(m)


def pull_taut(P, ok):
    """道すじを、通ってよい場所（ok）の中でピンと張る（広い所ではまっすぐになる）。"""
    P = np.asarray(P, float); n = len(P); H, W = ok.shape

    def visible(a, b):
        L = int(np.hypot(*(P[b] - P[a]))) + 1; t = np.linspace(0, 1, L + 1)[:, None]
        q = np.round(P[a] + (P[b] - P[a]) * t).astype(int)
        return bool(ok[np.clip(q[:, 1], 0, H - 1), np.clip(q[:, 0], 0, W - 1)].all())
    out = [0]; i = 0
    while i < n - 1:
        k = n - 1
        while k > i + 1 and not visible(i, k):
            k -= max(1, (k - i) // 6)
        out.append(k); i = k
    return P[out]


def signed_dist(M):
    return ndi.distance_transform_edt(M) - ndi.distance_transform_edt(~M)


def fit_smooth(ref, sd, margin, closed, cap, w=None, lam=4e6, h=2.0):
    """線 ref をなめらかな曲線に置きかえる（曲がり具合が少しずつ変わる線。角も、急な曲がり始めも作らない）。
    「元の線に近い」と「曲がり具合の変化が小さい」のつり合いで決め、通ってよい範囲（sd >= margin、元の線から cap 以内）を
    はみ出した所だけ、元の線に強く引き寄せてやり直す。ref は h 画素おきの点。w は点ごとの重み（大きいほど動かさない）。"""
    R = np.asarray(ref, float); n = len(R)
    w = np.ones(n) if w is None else np.asarray(w, float).copy()
    if closed:
        D = sp.diags([-1.0, 3.0, -3.0, 1.0], [0, 1, 2, 3], shape=(n, n), format="lil")
        for r in range(n - 3, n):
            for c, val in zip(range(r, r + 4), (-1.0, 3.0, -3.0, 1.0)):
                D[r, c % n] = val
        D = D.tocsc()
    else:
        D = sp.diags([-1.0, 3.0, -3.0, 1.0], [0, 1, 2, 3], shape=(n - 3, n), format="csc")
    K = lam * (D.T @ D)
    Hh, Ww = sd.shape
    for it in range(14):
        lu = spl.splu((sp.diags(w) + K).tocsc())
        F = np.stack([lu.solve(w * R[:, 0]), lu.solve(w * R[:, 1])], axis=1)
        d = ndi.map_coordinates(sd, [np.clip(F[:, 1], 0, Hh - 1), np.clip(F[:, 0], 0, Ww - 1)], order=1, mode="nearest")
        bad = (d < margin) | (np.linalg.norm(F - R, axis=1) > cap)
        bad &= w < 100
        if not bad.any():
            break
        bad = ndi.binary_dilation(bad, iterations=4) if not closed else np.roll(ndi.binary_dilation(np.tile(bad, 3), iterations=4)[n:2 * n], 0)
        w = np.where(bad & (w < 100), np.minimum(w * 3.0, 100), w)
    return F


def corridor(B, raw, hb, shape, closed):
    """線 raw のまわり（帯の中）で、線を動かしてよい範囲を表す符号つき距離。"""
    return signed_dist(B & (line_dist(shape, raw, closed) < 1.6 * hb))


def build_venue(code, v, starts, img):
    H, W = img.shape[:2]
    k = np.ones((1, 15), np.uint8)   # ゴールの黒い縦線で帯が切れないように横につなぐ
    Mg = cv2.morphologyEx(mask(img, GREEN), cv2.MORPH_CLOSE, k) > 0
    Mo = cv2.morphologyEx(mask(img, ORANGE), cv2.MORPH_CLOSE, k) > 0
    # ダートの発走が芝の引き込み線にあるとき用：芝とダートの間の白いすき間をふさいだもの
    Mall = cv2.morphologyEx(((Mg | Mo) * 255).astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))) > 0
    routes = v["routes"]
    any_r = next(iter(routes.values()))["pts"]
    gx = int(round(any_r[0][0])); dirx = 1 if any_r[6][0] > any_r[0][0] else -1   # ゴールを過ぎたあとに進む向き
    gys = [r["pts"][0][1] for r in routes.values()]
    Wt0 = band_width(Mg)
    cut = np.zeros((H, W), bool)
    y0, y1 = int(max(0, min(gys) - 1.6 * Wt0)), int(min(H, max(gys) + 1.6 * Wt0))
    cut[y0:y1, gx - 1:gx + 2] = True   # ゴール線（ここは越えられない壁にして、向きを一つに決める）

    # 1. 各走路の中心線
    centre = {}; half = {}
    order = sorted(routes, key=lambda rk: rk == "turf|outer")   # 外回りは最後（芝の帯の幅を内回りで測ってから）
    for rk in order:
        r = routes[rk]; dirt = rk.startswith("dirt"); B = Mo if dirt else Mg
        old = np.array(r["pts"], float); yg = r["pts"][0][1]
        if rk != "turf|outer":
            # 既存の線は内ラチ（帯の内側のふち）。そこから帯の半分だけ外へ離れた所を通す
            ya = run_centre(B[:, gx + 4 * dirx], yg); yb = run_centre(B[:, gx - 4 * dirx], yg)
            off = max(4.0, abs((ya + yb) / 2 - yg)); half[rk] = off
            d_old = line_dist((H, W), old)
            A = B & (d_old < 2 * off + 3)
            cost = np.where(A, 1.0 + 10.0 * np.clip(np.abs(d_old - off) / off, 0, 1), np.inf)
        else:
            hb = half.get("turf|inner") or half.get("turf|single") or Wt0 / 2; half[rk] = hb
            A = B & (line_dist((H, W), old) < 1.7 * hb + 4)
            # 外回りは、芝の「外側のふち」（図の外の白地に接するふち）から帯の半分だけ内へ入った所を通す。
            # 内回りの帯と合わさって幅が倍になっている所でも、外回り自身の帯の中央になる（帯どうしの境目を通らない）。
            nong = ~(Mg | Mo)
            lab, _ = ndi.label(nong)
            ext = np.isin(lab, np.unique(np.r_[lab[0, :], lab[-1, :], lab[:, 0], lab[:, -1]])) & nong
            dE = ndi.distance_transform_edt(~ext)
            cost = np.where(A, 1.0 + 10.0 * np.clip(np.abs(dE - hb) / hb, 0, 1), np.inf)
            if code == "kyoto":   # 4コーナー出口：内外の帯が合流して幅が倍になる所は、外側のふちに引かれすぎないよう内回りの中心線とのまん中を狙う
                yy, xx = np.mgrid[0:H, 0:W]
                dIn = line_dist((H, W), centre["turf|inner"])
                zone = (xx > 880) & (yy > 330)
                cost = np.where(zone, 0.5 * cost + 0.5 * (1.0 + 10.0 * np.clip(dIn / hb, 0, 1)), cost)
            ya = run_centre(A[:, gx + 4 * dirx], yg); yb = run_centre(A[:, gx - 4 * dirx], yg)
        cost[cut] = np.inf
        raw = path_between(cost, snap(A & ~cut, (gx + 4 * dirx, ya)), snap(A & ~cut, (gx - 4 * dirx, yb)))
        if raw is None:
            raise SystemExit(f"{code} {rk}: 一周の線が作れません")
        ref = smooth_closed(raw, 8.0)[::2]
        if rk == "turf|outer":   # 外回り：内回りの線に乗り移る所を大きな弧でつなげるよう、動かせる幅を広めにとる
            C = fit_smooth(ref, signed_dist(B), 0.35 * half[rk], True, cap=3.0 * half[rk], lam=3e7)
        else:
            C = fit_smooth(ref, signed_dist(A), 0.35 * half[rk], True, cap=1.2 * half[rk])
        near = np.nonzero(np.abs(C[:, 1] - (ya + yb) / 2) < 2 * half[rk])[0]
        i0 = near[int(np.argmin(np.abs(C[near, 0] - gx)))]   # ゴール線の位置から始まるように並べ直す
        C = np.vstack([C[i0:], C[:i0]])
        if (C[8, 0] - C[0, 0]) * dirx < 0:
            C = C[::-1]
        centre[rk] = resample(np.vstack([C, C[:1]]), 1.0)[:-1]

    # 2. 各発走地点からの道すじ
    out = []
    for s in starts:
        rk = s["route"]; dirt = s["surface"] == "dirt"
        if code == "niigata" and not dirt and s["dist"] == 1000 and "turf|outer" in centre:
            rk = "turf|outer"   # 直線1000mは外回りと同じ下の直線を走る
        C = centre[rk]; hb = half[rk]
        A = Mall.copy() if dirt else Mg.copy()
        dC = line_dist((H, W), C)
        if rk == "turf|outer":   # 外回りの発走は、内回りだけの帯を近道に使わない
            for ok, Co in centre.items():
                if ok != rk and not ok.startswith("dirt"):
                    A &= ~((line_dist((H, W), Co) < 1.25 * hb) & (dC > 1.9 * hb))
        cost = centre_cost(A, hb)
        lane = np.where(dC < hb, 0.9 * (1.0 + 10.0 * dC / hb), np.inf)   # 中心線の近くでは、中心線に寄るほど通りやすい
        cost = np.where(A, np.minimum(cost, lane), np.inf)
        cost[cut] = np.inf
        for p0, p1 in BARRIERS.get((code, s["label"]), []):
            wall = np.zeros((H, W), np.uint8); cv2.line(wall, p0, p1, 255, 3); cost[wall > 0] = np.inf
        free = np.isfinite(cost)
        dtA = ndi.distance_transform_edt(A)
        okm = dtA >= 0.9 * min(hb, float(np.percentile(dtA[A], 99)))
        mx0, my0 = float(s.get("mx", s["x"])), float(s.get("my", s["y"]))   # 元図の印の位置（作り直しても変わらないように別に持つ）
        sx, sy = mx0, my0; straight_in = None
        gap = float(ndi.distance_transform_edt(~A)[int(round(sy)), int(round(sx))])
        if 0 < gap <= 20:      # 印が帯から少しはみ出している：帯の中央寄りへ寄せる
            sx, sy = snap(free & (dtA >= 0.8 * hb), (sx, sy))
        elif gap > 20:         # 背景の図に引き込み線が描かれていない：発走地点から本線へまっすぐ入る
            k0 = int(np.argmin(np.linalg.norm(C - [sx, sy], axis=1)))
            for dk in range(10, 400, 4):
                kk = k0 + dk
                if kk >= len(C) - 8:
                    break
                tg = C[kk + 6] - C[kk - 6]; vv = C[kk] - [sx, sy]
                if np.dot(tg, vv) / (np.linalg.norm(tg) * np.linalg.norm(vv)) > math.cos(math.radians(18)):
                    straight_in = kk; break
        if straight_in is None and dC[int(round(sy)), int(round(sx))] < hb:   # 本線の上の発走：印を線の上にのせる
            sx, sy = map(float, C[int(np.argmin(np.linalg.norm(C - [sx, sy], axis=1)))])
        tgt = snap(free & (dC < 1.5), C[-6]); st = snap(free, (sx, sy)) if straight_in is None else snap(free, C[straight_in])
        raw = path_between(cost, st, tgt)
        if raw is None:
            print("  !! 道が見つからない", code, s["label"]); out.append(s); continue
        on = dC[raw[:, 1].astype(int), raw[:, 0].astype(int)] <= 2.0
        off_idx = np.nonzero(~on)[0]
        j = int(off_idx[-1]) + 1 if len(off_idx) else 0      # ここから先はずっと中心線の上
        je = min(len(raw) - 1, j + 140)
        kC = int(np.argmin(np.linalg.norm(C - raw[je], axis=1)))
        if kC < 3:
            kC = len(C) - 1
        if j <= 3 and straight_in is None:      # はじめから本線の上
            k0 = int(np.argmin(np.linalg.norm(C - [sx, sy], axis=1))); kC = max(kC, k0)
            chute = C[k0:kC + 1]
        else:
            # 発走地点から、本線に乗って少し進んだ所までをピンと張る（引き込み線と本線が一直線なら、まっすぐ入る）。
            # その先に本線の線そのものを足し、そこで本線へ少しずつ寄せる（つなぎ目に角を作らない）
            kj = int(np.argmin(np.linalg.norm(C - raw[min(j, len(raw) - 1)], axis=1)))
            kC = min(len(C) - 1, kj + 140) if kj < len(C) - 4 else len(C) - 1
            pre = np.vstack([[sx, sy], raw[:j + 1], C[kj + 1:kC + 1]]) if kC > kj else np.vstack([[sx, sy], raw[:j + 1], C[kC]])
            tube = np.zeros((H, W), np.uint8); cv2.polylines(tube, [np.round(pre).astype(np.int32)], False, 255, 3)
            cv2.circle(tube, (int(round(sx)), int(round(sy))), int(hb), 255, -1)
            taut = pull_taut(resample(pre, 2.0), (okm | (tube > 0)))
            k2 = min(len(C) - 1, kC + 120)
            body = resample(smooth_open(np.vstack([taut, C[kC + 1:k2 + 1]]), 10.0), 2.0)
            n2 = max(0, (k2 - kC) // 2); kC = k2
            body[0] = [sx, sy]; body[-1] = C[kC]
            if n2 >= 2:
                body[-n2:] = resample(C[kC - 2 * n2 + 1:kC + 1], 2.0)[-n2:]
            walls = A & np.isfinite(cost) if BARRIERS.get((code, s["label"])) else A
            tailC = np.vstack([C[kC + 1:], C])[1:240:2]
            wt = np.ones(len(body) + len(tailC)); wt[0] = 1e6; wt[len(body):] = 1e5
            m = min(max(n2, 30), len(body) - 2); wt[len(body) - m:len(body)] = np.logspace(0, 5, m)
            F = fit_smooth(np.vstack([body, tailC]), signed_dist(walls), 0.35 * hb, False, cap=1.6 * hb, w=wt)
            chute = F[:len(body)]; chute[0] = [sx, sy]; chute[-1] = C[kC]
        seg = np.vstack([chute, C[kC + 1:], C[:1]])
        loop = np.vstack([C[1:], C[:1]])
        mpp = routes[rk]["lap_m"] / len(C)
        first_m = arclen(seg)[-1] * mpp
        laps = max(0, round((s["dist"] - first_m) / routes[rk]["lap_m"]))
        full = np.vstack([seg] + [loop] * laps)
        pts = rdp(resample(full, 1.5), 0.06)   # 細かめに残す（粗く間引くと折れ線の角が見える）
        Qk = resample(full, 3.0); dk = np.diff(Qk, axis=0); th = np.unwrap(np.arctan2(dk[:, 1], dk[:, 0]))
        turn = np.abs(th[6:] - th[:-6])       # 18画素進む間に向きが変わる量
        ik = int(np.argmax(turn)) if len(turn) else 0
        chk = resample(full, 3.0); cx = np.clip(np.round(chk[:, 0]).astype(int), 0, W - 1); cy = np.clip(np.round(chk[:, 1]).astype(int), 0, H - 1)
        o = dict(s); o["route"] = rk; o["x"] = round(sx, 1); o["y"] = round(sy, 1); o["mx"] = round(mx0, 1); o["my"] = round(my0, 1); o["path"] = [[round(float(a), 1), round(float(b), 1)] for a, b in pts]
        o["_kink"] = (float(np.degrees(turn[ik])) if len(turn) else 0.0, Qk[ik + 3].round().tolist() if len(turn) else None)
        o["measured_m"] = round(first_m + laps * routes[rk]["lap_m"]); o["laps"] = int(laps); o["_inside"] = float((A | cut)[cy, cx].mean())
        out.append(o)
    return out, centre, half


def fix_starts(code, starts, v):
    """元図の札の直しと、元図に印が無い主要コースの補い（どれも approx=True を付け、画面に「目安」と出す）。"""
    starts = [dict(s) for s in starts if not s.get("approx")]
    by = {s["label"]: s for s in starts}
    if code == "kyoto":
        if "2200内" in by:   # 京都の芝2200mは外回りだけ（内回りの設定は無い）
            by["2200内"].update(label="2200外", inout="外", route="turf|outer")
        if "1600内" in by and "1600外" not in by:   # 芝1600mは内・外とも同じ引き込み線から発走
            starts.append(dict(by["1600内"], label="1600外", inout="外", route="turf|outer", approx=True))
    if code == "tokyo" and "D1400" in by and "D1300" in by and "D1600" not in by:
        # ダート1600m：向正面を2コーナー側へのばした先の芝のポケットから発走。D1400 の印から200m手前に置く
        g = lambda t: np.array([by[t].get("mx", by[t]["x"]), by[t].get("my", by[t]["y"])], float)
        a, b = g("D1400"), g("D1300")
        r = v["routes"]["dirt|single"]; mpp = r["lap_m"] / r["per_px"]
        p = a + (a - b) / np.linalg.norm(a - b) * (200.0 / mpp)
        starts.append(dict(by["D1400"], label="D1600", dist=1600, x=round(float(p[0]), 1), y=round(float(p[1]), 1), mx=round(float(p[0]), 1), my=round(float(p[1]), 1), approx=True))
    return starts


def official(cat, code, s):
    """JRAのコース台帳にある距離かどうか（台帳が無ければ True）。"""
    if not cat:
        return True
    lay = {"内": ("inner",), "外": ("outer",), None: ("single", "straight", "inner", "outer")}[s["inout"]]
    for r in cat.get(code, []):
        if r["surface"] == s["surface"] and r["layout"] in lay and s["dist"] in r["distances_m"]:
            return True
    return False


def main(a):
    sh = json.loads(Path(a.shapes).read_text(encoding="utf-8"))["venues"]
    doc = json.loads(Path(a.starts).read_text(encoding="utf-8"))
    cat = {v["code"]: v["routes"] for v in json.loads(Path(a.catalog).read_text(encoding="utf-8"))["venues"]} if a.catalog else None
    res = {}
    for code, starts in doc["venues"].items():
        img = cv2.imread(str(Path(a.img_root) / f"{code}.png"))
        starts = fix_starts(code, starts, sh[code])
        for s0 in starts:
            s0["official"] = official(cat, code, s0)
        out, centre, half = build_venue(code, sh[code], starts, img)
        smooth = {o["label"]: o for o in out}                       # なめらかな折れ線版（直線と円弧に直す前）
        out, loops = arc_paths.arcify(code, out, centre, half, sh[code]["routes"], log=lambda *x: None)
        extra = arc_paths.approx_starts(code, loops, sh[code]["routes"], cat.get(code, []) if cat else [], out)
        out = out + extra
        for o in extra:
            print(f"  {code} {o['label']}: 印が無いので目安で補う（周回{o['laps']}）")
        k3 = np.ones((1, 15), np.uint8)
        band = (cv2.morphologyEx(((mask(img, GREEN) | mask(img, ORANGE)) * 255).astype(np.uint8), cv2.MORPH_CLOSE, k3) > 0)
        for rk, lp in loops.items():
            print(f"  {code} {rk}: 周回 {lp['sp'].kinds()}（{len(lp['sp'].L)}部品）中心線からの最大ずれ {lp['dev']:.1f}px = 幅の{lp['dev'] / (2 * half[rk]) * 100:.1f}%" + ("  ※10%超" if lp["dev"] > lp["tol"] else ""))
        for o in out:
            if "prim" not in o:
                print(f"  !! {code} {o['label']}: 直線と円弧に直せず（なめらかな線のまま）")
            e = o["measured_m"] - o["dist"]
            Q = np.array(o["path"]); cx = np.clip(np.round(Q[:, 0]).astype(int), 0, img.shape[1] - 1); cy = np.clip(np.round(Q[:, 1]).astype(int), 0, img.shape[0] - 1)
            ins = float(band[cy, cx].mean())
            o.pop("_inside", 0); o.pop("_kink", 0); prim = o.pop("prim", "-")
            flag = (" 距離ずれ" if abs(e) > 0.06 * o["dist"] else "") + (" 帯の外" if ins < 0.985 else "")
            so = smooth.get(o["label"], {})
            print(f"{code:10s}{o['label']:8s}{o['measured_m']:6d} ({e:+5d}; 前{so.get('measured_m', 0) - o['dist']:+5d}) 周回{o.get('laps', '-')} 帯の中{ins * 100:5.1f}% 点{len(o['path']):4d} {prim}{flag}")
        res[code] = out
        if a.overlay:
            Path(a.overlay).mkdir(parents=True, exist_ok=True)
            tiles = []
            for o in out:
                im = img.copy(); P = np.round(np.array(o["path"])).astype(np.int32)
                cv2.polylines(im, [P], False, (255, 255, 255), 9, cv2.LINE_AA); cv2.polylines(im, [P], False, (160, 60, 20), 5, cv2.LINE_AA)
                cv2.circle(im, (int(o["x"]), int(o["y"])), 9, (255, 255, 255), -1); cv2.circle(im, (int(o["x"]), int(o["y"])), 9, (0, 0, 0), 3)
                cv2.putText(im, f"{'D' if o['surface'] == 'dirt' else 'T'}{o['dist']}{ {'内': 'in', '外': 'out'}.get(o['inout'], '')} {o['measured_m']}", (10, 25), 0, 0.8, (0, 0, 0), 2)
                tiles.append(im)
            c = 3; r = math.ceil(len(tiles) / c); h, w = img.shape[:2]
            sheet = np.full((r * h, c * w, 3), 255, np.uint8)
            for i, t in enumerate(tiles):
                sheet[(i // c) * h:(i // c + 1) * h, (i % c) * w:(i % c + 1) * w] = t
            f = 1800 / sheet.shape[1]
            cv2.imwrite(str(Path(a.overlay) / f"{code}.png"), cv2.resize(sheet, None, fx=f, fy=f, interpolation=cv2.INTER_AREA))
    if a.write:
        doc["venues"] = res
        doc["source"] = "うまぽっと（https://umapot.com/）のコース素材の発走位置の印をもとに作成。道すじは走路の帯の中央を通る、直線と円弧だけの線（sim_v2/build_course_paths.py・arc_paths.py・arc_spline.py）。"
        Path(a.out or a.starts).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shapes", required=True); ap.add_argument("--starts", required=True); ap.add_argument("--img-root", required=True)
    ap.add_argument("--write", action="store_true"); ap.add_argument("--out"); ap.add_argument("--overlay"); ap.add_argument("--catalog")
    main(ap.parse_args())
