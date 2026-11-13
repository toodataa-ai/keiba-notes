"""build_course_paths が作った道すじを、直線と円弧だけの軌跡に作り直す（ルールは arc_spline.py）。"""
import math
import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from . import arc_spline as A

HOME_EXTEND = {("hanshin", "turf|outer")}   # 2600mなど、発走地点がゴール前の直線の手前（4コーナーの中）になる距離を、直線の延長上（引き込み線）に置く
SNAP_STRAIGHT = {("chukyo", 1300), ("chukyo", 3000)}   # JRAの図で発走が直線上にあるもの：目安の位置が円弧の途中なら、その円弧を出た所（直線のはじまり）に置く
FORCE_CHUTE = {("tokyo", "1600")}; CHUTE_KEYS_FORCED = None   # 印が円弧の途中にあっても、発走は引き込み線（直線）から入る形にする
CHUTE_KEYS = {("tokyo", "2000"): ("LAA", "LAAA")}   # 角ばって見える所は、最後の直線を大きな円弧に置き換える
TOL_RATIO = 0.10     # 中心線からのずれの上限（走路の幅に対する割合）
LOOP_SHARE = {("hanshin", "turf|outer"): dict(**{"with": "turf|inner"}, arcs=((177.0, 305.0), (201.0, 155.0))),
              ("kyoto", "turf|outer"): dict(**{"with": "turf|inner"}, arcs=((209.0, 549.0), (159.0, 98.0)), R_last=250.0)}   # 京都外回りも同じ（2コーナー・4コーナーが外に膨れていた。ユーザー依頼 2026-11-14）   # 阪神外回りの1〜2コーナー（内回りと同じ走路）は内回りの線と同じ円弧を使い、向正面の直線へ接線でつなぐ（ユーザー依頼 2026-11-13「内回りと同じラインが理想」）
LOOP_MERGE = {("hanshin", "turf|outer"): dict(parts=(4, 5, 6, 7), R=230.0, n=10)}   # 阪神外回りの3〜4コーナー：4つの円弧（半径177/321/131/137）を、手前の円弧（半径177のまま）＋半径230の1つの円弧にまとめる。最後の直線は元のまま（同じ線・同じ向き）。ユーザー依頼 2026-11-13「もっと内側・半径が長い円弧で、最後の直線はまっすぐ」。中心線からのずれは幅の約36%で、規定の10%を超える例外
OUTER_INNER_OFF = {"hanshin": 3.0}   # 外回り→内回りのつなぎが線から離れてよい上限（帯の許容 tol の倍数）。阪神は4コーナーを内寄りにしたため外回りの線と内回りの線の間が少し広がる
SINGLE_ARC = {("tokyo", "2000")}   # 引き込み線を『直線＋円弧1つ＋向正面の直線の延長』にする距離（ユーザー依頼 2026-11-12）。中心線からのずれが幅の10%を超える（東京芝2000mは約16%）規定外の例外


def _merge_corner(sp, mg):
    """parts の円弧群を『手前の円弧＋半径Rの円弧』に置き換える。最後の直線は元の線のまま（終わりの位置・向きを固定）にして、手前の円弧の長さと最後の直線の長さを解く。
    全体の曲がり角は変えないので向きは必ず一致し、つなぎ目はすべて接線がそろう。"""
    from scipy.optimize import fsolve
    x0, y0, th0 = sp.st[0]
    L = list(sp.L); K = list(sp.K)
    a, c = mg["parts"][0], mg["parts"][-1]
    T = sum(L[i] * K[i] for i in mg["parts"]); k4 = K[a]; k = 1.0 / mg["R"]
    def mk(l4, L8):
        LL = L[:a] + [l4, (T - l4 * k4) / k, L8] + L[c + 2:]
        KK = K[:a] + [k4, k, 0.0] + K[c + 2:]
        return A.Spline(x0, y0, th0, LL, KK)
    def err(v):
        e = mk(*v).end(); return [e[0] - x0, e[1] - y0]
    sol, _, ier, _ = fsolve(err, [292.0, 376.0], full_output=True)
    if ier != 1 or sol[0] <= 0 or sol[1] <= 0 or T - sol[0] * k4 <= 0:
        raise SystemExit("4コーナーの円弧への置き換えが解けません")
    return mk(*sol)


def _share_with_inner(sp, spi, sh):
    """外回りの『ゴール→1〜2コーナー→向正面の直線』を、内回りの線と同じ円弧にする。
    内回りの2つの円弧（半径127・348）はそのまま使い、3〜4コーナーの2つの円弧（半径は変えない）は、
    3コーナーは2つの円弧（sh["arcs"]、帯の中央より少し外側を通るように選んだ）にし、4コーナーの円弧の長さを曲がり角の合計から出す。
    向正面の直線とゴール前の直線の長さは、周回が閉じる（位置も向きも一致する）ように解く。
    3コーナーの円弧の長さは、中心線からのずれが最小になるように選んだ（外回りの帯の中央に近い）。"""
    from scipy.optimize import fsolve
    x0, y0, th0 = spi.st[0]
    iL = [i for i, k in enumerate(sp.K) if k == 0]
    a, b = iL[0], iL[-1]
    arcs = list(range(a + 1, b))
    if "R_last" in sh:
        k4 = 1.0 / sh["R_last"]
    else:
        if len(arcs) != 2:
            raise SystemExit("外回りの3〜4コーナーの円弧が2つではありません")
        k4 = sp.K[arcs[1]]
    pre = [(1.0 / R, l) for R, l in sh["arcs"]]            # 3コーナーの円弧（半径, 長さ）。4コーナーの円弧（半径230のまま）の長さは曲がり角の合計から出す
    if spi.K[2] != 0:
        raise SystemExit("内回りの最初の直線が3番目の部品ではありません")
    k0, k1, l0, l1 = spi.K[0], spi.K[1], spi.L[0], spi.L[1]
    l4 = (2 * math.pi - l0 * k0 - l1 * k1 - sum(k * l for k, l in pre)) / k4
    if l4 <= 0:
        raise SystemExit("外回りの4コーナーの円弧の長さが負になります")
    def mk(L2, L5):
        return A.Spline(x0, y0, th0, [l0, l1, L2] + [l for _, l in pre] + [l4, L5], [k0, k1, 0.0] + [k for k, _ in pre] + [k4, 0.0])
    def err(v):
        e = mk(*v).end(); return [e[0] - x0, e[1] - y0]
    sol, _, ier, _ = fsolve(err, [sp.L[a], sp.L[b]], full_output=True)
    if ier != 1 or sol[0] <= 0 or sol[1] <= 0:
        raise SystemExit("外回りの1〜2コーナーの置き換えが解けません")
    return mk(*sol)


def resample(P, step):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    t = np.arange(0, d[-1], step)
    return np.c_[np.interp(t, d, P[:, 0]), np.interp(t, d, P[:, 1])]


def arcify(code, out, centre, half, routes, log=print):
    fits = {}
    for rk, C in centre.items():
        th, _ = A.heading_curv(C, True)
        fy = 1.0 if (th[-1] - th[0]) > 0 else -1.0       # 曲がる向きが正になる座標系にそろえる
        Cf = C * [1.0, fy]
        tol = TOL_RATIO * 2 * half[rk]
        r = A.fit_closed(Cf, tol)
        if r is None:
            raise SystemExit(f"{code} {rk}: 直線と円弧の周回線が作れません")
        fits[rk] = dict(sp=r[0], dev=r[1], fy=fy, C=C, Cf=Cf, tol=tol)
    for (c_, rk), mg in LOOP_MERGE.items():
        f = fits.get(rk)
        if c_ == code and f and len(f["sp"].L) == mg["n"]:
            f["sp"] = _merge_corner(f["sp"], mg)
    for (c_, rk), sh in LOOP_SHARE.items():
        f = fits.get(rk)
        if c_ == code and f and sh["with"] in fits:
            f["sp"] = _share_with_inner(f["sp"], fits[sh["with"]]["sp"], sh)
    loops = {}
    for rk, f in fits.items():
        sp, C, Cf, fy, tol = f["sp"], f["C"], f["Cf"], f["fy"], f["tol"]
        dev = float(cKDTree(C).query(sp.sample(1.0) * [1.0, fy])[0].max()) if (code, rk) in LOOP_MERGE or (code, rk) in LOOP_SHARE else f["dev"]
        # ゴール線の位置（C の先頭）を道のりの始点にそろえる
        smp = sp.sample(0.25); k = int(np.argmin(np.linalg.norm(smp - Cf[0], axis=1)))
        sg = k * 0.25
        base = A.rebase(sp, sg)
        loops[rk] = dict(sp=sp, base=base, fy=fy, tol=tol, dev=dev, C=C, Cf=Cf, tree=cKDTree(C))
        log(f"  {code} {rk}: 周回 {sp.kinds()}（{len(sp.L)}部品）中心線からの最大ずれ {dev:.1f}px = 幅の{dev / (2 * half[rk]) * 100:.1f}%  半径 " + ",".join(f"{1 / k:.0f}" for k in sp.K if k > 0) + ("  ※10%超" if dev > tol else ""))
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
            if (code, str(o["label"])) in SINGLE_ARC:
                ch = _single_arc_chute(S, ref, base)
            elif forced:   # 印の位置から本線の円弧へ、接線になる直線を引く（印は動かさない）
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


def _single_arc_chute(S, ref, base):
    """発走地点 S（動かさない）から、直線 → 円弧1つ → 向正面の直線の延長、で本線の向正面の直線のはじまりに入る引き込み線。
    円弧の半径と、はじめの向きを、元の線（ref）にいちばん近くなるように決める（直線の長さは、つなぎ目の位置と向きの一致から決まる）。
    返り値は (Spline, 最大ずれ, 合流位置 s*)。作れなければ None。"""
    ib = next((i for i in range(2, len(base.L)) if base.K[i] == 0), None)      # 本線の最初の円弧のあとの直線＝向正面
    if ib is None:
        return None
    sb0 = float(base.cum[ib]); B0 = np.array(base.at(sb0)[:2]); thb = base.at(sb0 + 1.0)[2]
    LP = base.sample(0.5); refT = cKDTree(ref)
    th_ref = math.atan2(*(ref[8] - ref[0])[::-1])
    db = np.array([math.cos(thb), math.sin(thb)])

    def build(v):
        R, th0 = v
        D = (thb - th0) % (2 * math.pi); d0 = np.array([math.cos(th0), math.sin(th0)])
        arcv = R * np.array([-math.sin(th0) + math.sin(thb), math.cos(th0) - math.cos(thb)])
        try:
            L1, L2 = np.linalg.solve(np.array([d0, db]).T, B0 - S - arcv)
        except np.linalg.LinAlgError:
            return None
        return R, th0, D, float(L1), float(L2)

    def obj(v, ret=False):
        b = build(v)
        if b is None or b[0] < 30 or b[2] <= 0 or b[2] > math.pi * 0.99:
            return 1e3
        R, th0, D, L1, L2 = b
        pen = (100 - L1 if L1 < 0 else 0) + (100 - L2 if L2 < 0 else 0)
        cs = A.Spline(S[0], S[1], th0, [max(L1, 0.0), R * D, max(L2, 0.0)], [0.0, 1.0 / R, 0.0])
        sm = cs.sample(1.0); Mp = np.vstack([sm, LP[int(sb0 * 2):int(sb0 * 2) + 700]])
        dev = max(float(cKDTree(Mp).query(ref)[0].max()), float(refT.query(sm)[0].max()))
        return (cs, dev) if ret else dev + pen

    best = None
    for R0 in (100, 140, 170, 200, 240):
        for off in (-0.05, 0.0, 0.05):
            r = minimize(obj, np.array([R0, th_ref + off]), method="Nelder-Mead", options=dict(xatol=1e-3, fatol=1e-4, maxiter=4000))
            if best is None or r.fun < best.fun:
                best = r
    if best.fun >= 100:
        return None
    cs, dev = obj(best.x, True)
    return cs, dev, sb0


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
            vs = base.vertices(s0, L); ext = False
            if (code, rk) in HOME_EXTEND and base.K[-1] == 0 and s0 < base.cum[len(base.L) - 1] - 1e-6:
                # 発走地点がゴール前の直線より手前（4コーナーの中）になる距離：直線を後ろへまっすぐ延ばした上（引き込み線）に置く。コーナーの中には置かない
                sj = base.cum[len(base.L) - 1]; xj, yj, thj = base.at(sj); e = sj - s0
                x, y = xj - e * math.cos(thj), yj - e * math.sin(thj)
                vs = np.vstack([[x, y], base.vertices(sj, L)]); ext = True
            full = np.vstack([vs] + [base.vertices()[1:]] * laps) * [1.0, fy]
            new.append(dict(label=("D" if r["surface"] == "dirt" else "") + str(dist) + (io or ""), dist=dist, surface=r["surface"], inout=io, route=rk,
                            x=round(float(x), 2), y=round(float(y * fy), 2), path=[[round(float(a), 2), round(float(b), 2)] for a, b in full],
                            prim="|" + base.kinds(), measured_m=int(round(laps * lap + rem)), official=True, mx=round(float(x), 2), my=round(float(y * fy), 2), laps=int(laps), approx=True, **({"basis": "straight_extension"} if ext else {})))
    return new


HOME_STRAIGHT_M = {("tokyo", "turf|single"): 525.9, ("tokyo", "dirt|single"): 501.6}   # JRA公式のゴール前の直線の長さ（m）。東京は図の直線が実際より短く描かれている（芝 図で約388m、ダート 図で約441m）


def fix_home_straight(code, loops, routes, out):
    """ゴール前の直線の上に発走地点がある距離（周回の長さ＋直線以内。東京芝なら2300〜2600m、東京ダートなら2100・2400m）を、直線の中の割合で置き直す。
    図の直線は実際より短い（東京芝は約388m ←→ 実際525.9m）ので、ゴールから距離ぶん戻ると円弧（4コーナー）に入ってしまう。
    ゴールから戻る距離÷実際の直線の長さ＝図の直線の中の位置、とする（2600mは直線のはじまり、2500mは直線に入って約109m先）。
    元図の印の位置は図の縮尺に合っていないので使わない（approx=True＝画面に「目安」と出る）。"""
    res = []
    for o in out:
        rk = o.get("route"); sm = HOME_STRAIGHT_M.get((code, rk))
        if sm is None or rk not in loops or o.get("inout") is not None:
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
                    if off <= O["tol"] * OUTER_INNER_OFF.get(code, 2.5):
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
