"""build_course_paths が作った道すじを、直線と円弧だけの軌跡に作り直す（ルールは arc_spline.py）。"""
import math
import numpy as np
from scipy.spatial import cKDTree
from . import arc_spline as A

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
        if j <= 3:     # はじめから本線の上：印を新しい線の上へ
            smp = base.sample(0.25); k = int(np.argmin(np.linalg.norm(smp - np.array([o["x"], o["y"]]) * [1, fy], axis=1)))
            s0 = k * 0.25; sx, sy = base.at(s0)[:2]
            chute = None; first = L - s0; verts = base.vertices(s0, L)
        else:
            ref = P[:min(len(P), j + 12)] * [1.0, fy]
            smp = base.sample(0.5)
            s_hint = int(np.argmin(np.linalg.norm(smp - ref[-1], axis=1))) * 0.5
            S = np.array([o["x"], o["y"]]) * [1.0, fy]
            ch = A.fit_chute(S, ref, base, Lp["tol"], s_hint)
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
            x, y = base.at(s0)[:2]
            full = np.vstack([base.vertices(s0, L)] + [base.vertices()[1:]] * laps) * [1.0, fy]
            new.append(dict(label=("D" if r["surface"] == "dirt" else "") + str(dist) + (io or ""), dist=dist, surface=r["surface"], inout=io, route=rk,
                            x=round(float(x), 2), y=round(float(y * fy), 2), path=[[round(float(a), 2), round(float(b), 2)] for a, b in full],
                            prim="|" + base.kinds(), measured_m=int(round(dist)), official=True, mx=round(float(x), 2), my=round(float(y * fy), 2), laps=int(laps), approx=True))
    return new


def _outer_to_inner(code, loops, routes, r, have):
    """外回りで発走し、ゴールを通ったあと内回りを一周する距離（中山・阪神の芝3200m）。
    ゴールの手前（まだ直線）で、外回りの線から内回りの線へ、向きを保ったまま直線＋円弧でつなぎ替える。"""
    if "turf|outer" not in loops or "turf|inner" not in loops:
        return []
    O = loops["turf|outer"]; I = loops["turf|inner"]; bo, bi = O["base"], I["base"]; fy = O["fy"]
    Lo, Li = bo.length, bi.length
    mo = routes["turf|outer"]["lap_m"] / Lo; mi = routes["turf|inner"]["lap_m"] / Li; lap_i = routes["turf|inner"]["lap_m"]
    out = []
    for dist in r["distances_m"]:
        if any(s["surface"] == "turf" and s["dist"] == dist and s.get("route") == "turf|outer_to_inner" for s in have):
            continue
        for back in (250, 180, 330, 120, 420, 520, 620, 700, 90, 60):
            sa = Lo - back; xa, ya, tha = bo.at(sa)
            smp = bo.sample(1.0); ref = smp[int(sa):]
            ch = A.fit_chute(np.array([xa, ya]), ref, bi, O["tol"], Li - back * 0.5, pin_th=tha, max_shift=1e-6)
            if ch is not None and ch[1] <= O["tol"]:
                break
        else:
            print(f"  !! {code} {dist}: 外回り→内回りのつなぎ替えが作れない"); continue
        cs, dev, ss = ch
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
        print(f"  {code} {dist}: 外→内 つなぎ {cs.kinds()}（長さ{cs.length:.0f}px・ずれ{dev:.1f}px・ゴール{back}px手前）")
    return out
