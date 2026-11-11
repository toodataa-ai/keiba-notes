"""build_course_paths が作った道すじを、直線と円弧だけの軌跡に作り直す（ルールは arc_spline.py）。"""
import math
import numpy as np
from scipy.spatial import cKDTree
from . import arc_spline as A

SNAP_STRAIGHT = {("chukyo", 1300), ("chukyo", 3000)}   # JRAの図で発走が直線上にあるもの：目安の位置が円弧の途中なら、その円弧を出た所（直線のはじまり）に置く
FORCE_CHUTE = {("tokyo", "1600")}; CHUTE_KEYS_FORCED = None   # 印が円弧の途中にあっても、発走は引き込み線（直線）から入る形にする
CHUTE_KEYS = {("tokyo", "2000"): ("LAA", "LAAA")}   # 角ばって見える所は、最後の直線を大きな円弧に置き換える
TOL_RATIO = 0.10     # 中心線からのずれの上限（走路の幅に対する割合）


def resample(P, step):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    t = np.arange(0, d[-1], step)
    return np.c_[np.interp(t, d, P[:, 0]), np.interp(t, d, P[:, 1])]


def arcify(code, out, centre, half, routes, log=print):
    loops = {}
    for rk, C in centre.items():
        th, _ = A.heading_curv(C, True)
        fy = 1.0 if (th[-1] - th[0]) > 0 else -1.0       # 曲がる向きが正になる座標系にそろえる
        Cf = C * [1.0, fy]
        tol = TOL_RATIO * 2 * half[rk]
        r = A.fit_closed(Cf, tol)
        if r is None:
            raise SystemExit(f"{code} {rk}: 直線と円弧の周回線が作れません")
        sp, dev, _ = r
        # ゴール線の位置（C の先頭）を道のりの始点にそろえる
        smp = sp.sample(0.25); k = int(np.argmin(np.linalg.norm(smp - Cf[0], axis=1)))
        sg = k * 0.25
        base = A.rebase(sp, sg)
        loops[rk] = dict(sp=sp, base=base, fy=fy, tol=tol, dev=dev, C=C, Cf=Cf, tree=cKDTree(C))
        log(f"  {code} {rk}: 周回 {sp.kinds()}（{len(sp.L)}部品）中心線からの最大ずれ {dev:.1f}px = 幅の{dev / (2 * half[rk]) * 100:.1f}%  半径 " + ",".join(f"{1 / k:.0f}" for k in sp.K if k > 0))
    res = []
    for o in out:
        if "path" not in o or "route" not in o or o["route"] not in loops:
            res.append(o); continue
        rk = o["route"]; Lp = loops[rk]; base = Lp["base"]; fy = Lp["fy"]; L = base.length
        P = resample(np.array(o["path"], float), 1.0)
        d, _ = Lp["tree"].query(P)
        far = np.nonzero(d > 1.2)[0]
        j = int(far[-1]) + 1 if len(far) else 0
        info = ""
        if j <= 3 and (code, str(o["label"])) not in FORCE_CHUTE:     # はじめから本線の上：印を新しい線の上へ
            smp = base.sample(0.25); k = int(np.argmin(np.linalg.norm(smp - np.array([o["x"], o["y"]]) * [1, fy], axis=1)))
            s0 = k * 0.25; sx, sy = base.at(s0)[:2]
            chute = None; first = L - s0; verts = base.vertices(s0, L)
        else:
            ref = P[:min(len(P), j + 12)] * [1.0, fy]
            smp = base.sample(0.5)
            s_hint = int(np.argmin(np.linalg.norm(smp - ref[-1], axis=1))) * 0.5
            forced = (code, str(o["label"])) in FORCE_CHUTE
            S = np.array([o.get("mx", o["x"]), o.get("my", o["y"])] if forced else [o["x"], o["y"]]) * [1.0, fy]
            if forced:   # 印の位置から本線の円弧へ、接線になる直線を引く（印は動かさない）
                ch = _tangent_chute(S, base, s_hint)
            else:
                ch = A.fit_chute(S, ref, base, Lp["tol"], s_hint, keys=CHUTE_KEYS.get((code, str(o["label"]))))
            if ch is None:
                log(f"  !! {code} {o['label']}: 引き込み線が直線＋円弧で作れない"); res.append(o); continue
            cs, dev, ss = ch; sx, sy = cs.st[0][:2]
            chute = cs; first = cs.length + (L - ss)
            verts = np.vstack([cs.vertices(), base.vertices(ss, L)[1:]])
            info = f"引込 {cs.kinds()} ずれ{dev:.1f}px(幅の{dev / (2 * half[rk]) * 100:.0f}%)"
        mpp = routes[rk]["lap_m"] / L
        laps = max(0, round((o["dist"] - first * mpp) / routes[rk]["lap_m"]))
        loop = base.vertices()
        full = np.vstack([verts] + [loop[1:]] * laps) * [1.0, fy]
        q = dict(o); q["x"] = round(float(sx), 2); q["y"] = round(float(sy * fy), 2); q["path"] = [[round(float(a), 2), round(float(b), 2)] for a, b in full]
        q["measured_m"] = round(first * mpp + laps * routes[rk]["lap_m"]); q["laps"] = int(laps)
        q["prim"] = ("" if chute is None else chute.kinds()) + "|" + base.kinds()
        res.append(q)
        log(f"  {code:9s}{o['label']:7s} {o['dist']:5d}m→{q['measured_m']:5d}m {info}")
    return res, loops


def _tangent_chute(S, base, s_hint, span=120.0):
    """点 S から、本線の円弧に接する直線（引き込み線）。S 自体は動かさない。接する点は s_hint の前後で探す。"""
    best = None
    for s in np.arange(max(0.0, s_hint - span), min(base.length, s_hint + span), 0.25):
        x, y, th = base.at(s)
        i = int(np.clip(np.searchsorted(base.cum, s, side="right") - 1, 0, len(base.L) - 1))
        if base.K[i] <= 0:
            continue
        v = np.array([x, y]) - S; n = float(np.hypot(*v))
        if n < 2.0 or v @ np.array([math.cos(th), math.sin(th)]) <= 0:
            continue
        g = abs(v[0] * math.sin(th) - v[1] * math.cos(th)) / n       # 直線の向きと接線の向きのずれ（sin）
        if best is None or g < best[0]:
            best = (g, s, n, math.atan2(v[1], v[0]))
    if best is None or best[0] > 1e-3:
        return None
    g, s, n, thv = best

    def sg(s_):   # 符号つきのずれ（0 になる s が、ぴったり接する点）
        x, y, th = base.at(s_); v = np.array([x, y]) - S
        return v[0] * math.sin(th) - v[1] * math.cos(th)
    lo, hi = s - 0.5, s + 0.5
    if sg(lo) * sg(hi) > 0:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if sg(lo) * sg(mid) <= 0: hi = mid
        else: lo = mid
    s = 0.5 * (lo + hi); x, y, th = base.at(s)
    n = float(np.hypot(x - S[0], y - S[1]))
    cs = A.Spline(S[0], S[1], th, [n], [0.0])
    return cs, 0.0, s


def approx_starts(code, loops, routes, cat_routes, have):
    """元図に発走の印が無い距離を、本線の上でゴールから距離ぶん戻った所を発走地点にして補う（approx=True＝画面に「目安」と出す）。
    内回り→外回りの乗り換え（outer_to_inner）は、どこで乗り換えるか決められないので補わない。"""
    new = []
    for r in cat_routes:
        if r["layout"] == "outer_to_inner":
            new += _outer_to_inner(code, loops, routes, r, have)
            continue
        if r["layout"] not in ("inner", "outer", "single"):
            continue
        rk = f"{r['surface']}|{r['layout']}"
        if rk not in loops:
            continue
        io = {"inner": "内", "outer": "外"}.get(r["layout"])
        Lp = loops[rk]; base = Lp["base"]; L = base.length; fy = Lp["fy"]; lap = routes[rk]["lap_m"]; mpp = lap / L
        for dist in r["distances_m"]:
            if any(s["surface"] == r["surface"] and s["dist"] == dist and s.get("inout") == io for s in have):
                continue
            laps = max(0, math.ceil(dist / lap - 1e-9) - 1); rem = dist - laps * lap      # 0 < rem <= lap
            s0 = max(0.0, L - rem / mpp)
            if (code, dist) in SNAP_STRAIGHT:
                acc = 0.0
                for l_, k_ in zip(base.L, base.K):
                    if acc <= s0 < acc + l_ and k_ > 0:
                        s0 = acc + l_; break
                    acc += l_
                rem = (L - s0) * mpp
            x, y = base.at(s0)[:2]
            full = np.vstack([base.vertices(s0, L)] + [base.vertices()[1:]] * laps) * [1.0, fy]
            new.append(dict(label=("D" if r["surface"] == "dirt" else "") + str(dist) + (io or ""), dist=dist, surface=r["surface"], inout=io, route=rk,
                            x=round(float(x), 2), y=round(float(y * fy), 2), path=[[round(float(a), 2), round(float(b), 2)] for a, b in full],
                            prim="|" + base.kinds(), measured_m=int(round(laps * lap + rem)), official=True, mx=round(float(x), 2), my=round(float(y * fy), 2), laps=int(laps), approx=True))
    return new


HOME_STRAIGHT_M = {("tokyo", "turf|single"): 525.9}   # JRA公式のゴール前の直線の長さ（m）。東京芝は図の直線が実際より短く描かれている（図で約388m）


def fix_home_straight(code, loops, routes, out):
    """ゴール前の直線の上に発走地点がある距離（周回の長さ＋直線以内。東京芝なら2300〜2600m）を、直線の中の割合で置き直す。
    図の直線は実際より短い（東京芝は約388m ←→ 実際525.9m）ので、ゴールから距離ぶん戻ると円弧（4コーナー）に入ってしまう。
    ゴールから戻る距離÷実際の直線の長さ＝図の直線の中の位置、とする（2600mは直線のはじまり、2500mは直線に入って約109m先）。
    元図の印の位置は図の縮尺に合っていないので使わない（approx=True＝画面に「目安」と出る）。"""
    res = []
    for o in out:
        rk = o.get("route"); sm = HOME_STRAIGHT_M.get((code, rk))
        if sm is None or rk not in loops or o.get("surface") != "turf" or o.get("inout") is not None:
            res.append(o); continue
        Lp = loops[rk]; base = Lp["base"]; L = base.length; fy = Lp["fy"]; lap = routes[rk]["lap_m"]
        laps = max(0, math.ceil(o["dist"] / lap - 1e-9) - 1); back = o["dist"] - laps * lap      # ゴールから戻る距離（m）
        if laps < 1 or not (0 < back <= sm) or base.K[-1] != 0:
            res.append(o); continue
        s0 = L - back / sm * base.L[-1]                      # 図の最後の直線（ゴールの手前）の中の位置
        x, y = base.at(s0)[:2]
        full = np.vstack([base.vertices(s0, L)] + [base.vertices()[1:]] * laps) * [1.0, fy]
        q = dict(o); q.update(x=round(float(x), 2), y=round(float(y * fy), 2), mx=round(float(x), 2), my=round(float(y * fy), 2),
                              path=[[round(float(a), 2), round(float(b), 2)] for a, b in full], measured_m=int(o["dist"]), laps=int(laps), approx=True, basis="home_straight",
                              prim="|" + base.kinds())
        res.append(q)
    return res


def _outer_to_inner(code, loops, routes, r, have):
    """外回りで発走し、ゴールを通ったあと内回りを一周する距離（中山・阪神の芝3200m）。
    ゴールの手前（まだ直線）で、外回りの線から内回りの線へ、向きを保ったまま直線＋円弧でつなぎ替える。"""
    if "turf|outer" not in loops or "turf|inner" not in loops:
        return []
    O = loops["turf|outer"]; I = loops["turf|inner"]; bo, bi = O["base"], I["base"]; fy = O["fy"]
    Lo, Li = bo.length, bi.length
    for L_ in (O, I):
        L_["tree_f"] = cKDTree(L_["base"].sample(1.0))
    mo = routes["turf|outer"]["lap_m"] / Lo; mi = routes["turf|inner"]["lap_m"] / Li; lap_i = routes["turf|inner"]["lap_m"]
    out = []
    for dist in r["distances_m"]:
        if any(s["surface"] == "turf" and s["dist"] == dist and s.get("route") == "turf|outer_to_inner" for s in have):
            continue
        # 内回りの最後の円弧（最後のコーナー）のはじまりあたりまでに内回りの線に乗り、そこから先は1周目と2周目をぴったり重ねる
        # 内回りに乗る位置の候補：最後の円弧のはじまり／なかほど／最後の直線のはじまり（早く乗れるほど1周目と2周目が長く重なる）。
        # つなぎが外回りの線か内回りの線から遠く離れる（帯の外へ出る）ものは使わない。
        ia = max(i for i in range(len(bi.L)) if bi.K[i] > 0)
        lims = [bi.cum[ia], bi.cum[ia] + 0.5 * bi.L[ia], bi.cum[ia + 1]]
        ch = None
        for s_lim in lims:
            for back in range(int(Li - s_lim) + 30, int(Lo * 0.7), 30):
                sa = Lo - back; xa, ya, tha = bo.at(sa)
                P1 = np.array(bi.at(s_lim)[:2]); S0 = np.array([xa, ya]); n_ = max(2, int(np.linalg.norm(P1 - S0)))
                ref = np.c_[np.linspace(S0[0], P1[0], n_), np.linspace(S0[1], P1[1], n_)]
                c = A.fit_chute(S0, ref, bi, O["tol"] * 5, s_lim - 0.5, pin_th=tha, max_shift=1e-6, s_max=s_lim, nu_max=1.0)
                if c is not None:
                    q = c[0].sample(1.0)
                    off = np.minimum(O["tree_f"].query(q)[0], I["tree_f"].query(q)[0]).max()
                    if off <= O["tol"] * 2.5:
                        ch = c; break
            if ch is not None:
                break
        if ch is None:
            print(f"  !! {code} {dist}: 外回り→内回りのつなぎ替えが作れない"); continue
        cs, dev, ss = ch
        # ルールの確認：つなぎ目で位置も向きもぴったり一致していること（一致しなければ作らない）
        e = cs.end(); p1 = bi.at(ss); s1 = cs.st[0]; p0 = bo.at(sa)
        mis = max(math.hypot(e[0] - p1[0], e[1] - p1[1]), math.hypot(s1[0] - p0[0], s1[1] - p0[1]), abs(A.wrap(e[2] - p1[2])), abs(A.wrap(s1[2] - p0[2])))
        if mis > 1e-4 or any(k < 0 for k in cs.K):
            raise SystemExit(f"{code} {dist}: つなぎ目が一致しない（{mis:.2e}）")
        inner_m = (cs.length + (Li - ss)) * mi + lap_i
        s0 = sa - (dist - inner_m) / mo
        if s0 < 0:
            print(f"  !! {code} {dist}: 外回りの距離が足りない"); continue
        loop_i = bi.vertices()
        full = np.vstack([bo.vertices(s0, sa), cs.vertices()[1:], bi.vertices(ss, Li)[1:], loop_i[1:]]) * [1.0, fy]
        x, y = bo.at(s0)[:2]
        out.append(dict(label=str(dist), dist=dist, surface="turf", inout=None, route="turf|outer_to_inner", x=round(float(x), 2), y=round(float(y * fy), 2),
                        path=[[round(float(a), 2), round(float(b), 2)] for a, b in full], prim="outer>" + cs.kinds() + ">inner", measured_m=int(round(dist)), official=True,
                        mx=round(float(x), 2), my=round(float(y * fy), 2), laps=1, approx=True))
        print(f"  {code} {dist}: 外→内 つなぎ {cs.kinds()}（長さ{cs.length:.0f}px・ゴール{back}px手前から・内回りの線に乗る位置 s={ss:.0f}/{Li:.0f}）")
    return out
