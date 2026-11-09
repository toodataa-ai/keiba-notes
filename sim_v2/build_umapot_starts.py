#!/usr/bin/env python3
"""うまぽっと主要コース図の発走位置（点線）を、距離・芝ダ・内外つきで docs/lab/sim-v2/umapot-starts.json にする。
各発走位置から、なぞった走路の線に合流してゴールまで走る道すじ（pts）も作る（周回が必要な距離は周回を足す）。
  python3 -m sim_v2.build_umapot_starts --src <pptx/svg/png を置いた場所> --shapes docs/lab/sim-v2/umapot-shapes.json --out docs/lab/sim-v2/umapot-starts.json"""
import argparse, json, math, re
from pathlib import Path
import cv2, numpy as np
from .umapot_labels import labels
from .umapot_markers import markers, DIRS
from .trace_umapot import mask, GREEN, ORANGE
from skimage.graph import MCP_Geometric
from scipy import ndimage as ndi

CODE = {"nigata": "niigata"}
LAB = re.compile(r"^(D?)(\d{3,4})(内|外)?$")


def crop_offset(src, d, crop_png):
    full = cv2.imread(str(Path(src) / f"{d}-2.png")); crop = cv2.imread(str(crop_png))
    r = cv2.matchTemplate(full, crop, cv2.TM_SQDIFF)
    _, _, loc, _ = cv2.minMaxLoc(r) if False else (None, None, cv2.minMaxLoc(-r)[3], None)
    return loc  # (x0, y0)


def smooth_path(pts, step=4.0, win=9):
    P = np.array(pts, float)
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    if d[-1] < step * 3:
        return P
    t = np.arange(0, d[-1], step); t = np.append(t, d[-1])
    Q = np.stack([np.interp(t, d, P[:, 0]), np.interp(t, d, P[:, 1])], axis=1)
    h = win // 2; R = Q.copy()
    for i in range(1, len(Q) - 1):
        a, b = max(0, i - h), min(len(Q), i + h + 1)
        w = min(i - a, b - 1 - i)
        a, b = i - w, i + w + 1
        R[i] = Q[a:b].mean(axis=0)
    return R


def band_path(M, start, P, cum_dir):
    """発走地点から、走路の帯（緑・ダートの橙）の中を通って本線の線に合流する道すじ。
    帯の外（内馬場・別の帯）は通れない。合流は、走る向きと逆にならない点のうち最短のもの。"""
    dt = ndi.distance_transform_edt(M > 0)
    cost = np.where(M > 0, 1.0 + 8.0 / (dt + 1.0), np.inf)
    ys, xs = np.nonzero(M > 0)

    def snap(pt):
        j = int(np.argmin((xs - pt[0]) ** 2 + (ys - pt[1]) ** 2)); return (int(ys[j]), int(xs[j]))
    s0 = snap(start)
    mcp = MCP_Geometric(cost, fully_connected=True)
    costs, _ = mcp.find_costs([s0])
    n = len(P); cand = []
    for k in range(n):
        r, c = snap(P[k]); cand.append((costs[r, c], k, (r, c)))
    cand.sort(key=lambda t: t[0])
    for cst, k, (r, c) in cand[:60]:
        if not np.isfinite(cst):
            continue
        tr = np.array(mcp.traceback((r, c)))[:, ::-1].astype(float)   # (x, y)
        if len(tr) >= 6:
            v = tr[-1] - tr[-6]
        else:
            v = P[(k + 1) % n] - P[k]
        tg = P[(k + 1) % n] - P[k - 1]
        if float(np.dot(v, tg)) > 0.6 * np.linalg.norm(v) * np.linalg.norm(tg):
            return tr, k
    return None, None


def main(src, shapes, out, img_root):
    sh = json.loads(Path(shapes).read_text(encoding="utf-8"))["venues"]
    res = {}
    for d in DIRS:
        code = CODE.get(d, d); v = sh[code]
        x0, y0 = crop_offset(src, d, Path(img_root) / f"{code}.png")
        img = cv2.imread(str(Path(img_root) / f"{code}.png"))
        Mg = cv2.morphologyEx(mask(img, GREEN), cv2.MORPH_CLOSE, np.ones((1, 15), np.uint8)); Mo = cv2.morphologyEx(mask(img, ORANGE), cv2.MORPH_CLOSE, np.ones((1, 15), np.uint8)); Mall = np.maximum(Mg, Mo)
        ms = markers(Path(src) / f"{d}.svg"); L = labels(Path(src) / f"{d}.pptx")
        by = {i: [] for i in range(len(ms))}
        for l in L:
            j = min(range(len(ms)), key=lambda i: math.hypot(ms[i]["x"] - l["x"], ms[i]["y"] - l["y"]))
            by[j].append(l["text"])
        starts = []
        for i, m in enumerate(ms):
            mx, my = m["x"] - x0, m["y"] - y0
            for t in by[i]:
                g = LAB.match(t)
                if not g:
                    continue
                dirt, dist, io = g.group(1) == "D", int(g.group(2)), g.group(3)
                if dirt:
                    keys = ["dirt|single"]
                elif io == "内":
                    keys = ["turf|inner", "turf|single"]
                elif io == "外":
                    keys = ["turf|outer", "turf|single"]
                else:
                    keys = ["turf|single", "turf|inner"]
                rk = next((k for k in keys if k in v["routes"]), None)
                if rk is None:
                    continue
                R = v["routes"][rk]; P = np.array(R["pts"]); n = len(P)
                seg = np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1); cum = np.concatenate([[0], np.cumsum(seg)]); Lpx = cum[-1]
                mpp = R["lap_m"] / Lpx
                straight = (code == "niigata" and not dirt and io is None and dist == 1000)
                if straight:
                    G = v["routes"].get("turf|outer", R)["pts"][0]   # 直線コースのゴールは外回りの線（帯の中心）上
                    path = [[round(mx, 1), round(my, 1)], [round(float(G[0]), 1), round(float(G[1]), 1)]]
                    total = math.hypot(mx - G[0], my - G[1]) * mpp
                else:
                    tr, k = band_path(Mall if dirt else Mg, (mx, my), P, None)
                    if tr is None:
                        k = int(np.argmin(np.linalg.norm(P - np.array([mx, my]), axis=1))); tr = np.array([[mx, my]])
                    head = [list(map(float, q)) for q in tr] + [list(map(float, P[k]))]
                    arc = Lpx - cum[k]
                    first_px = float(np.sum(np.linalg.norm(np.diff(np.array(head), axis=0), axis=1))) + arc
                    first_m = first_px * mpp
                    laps = max(0, round((dist - first_m) / R["lap_m"]))
                    pts = head + [list(map(float, p)) for p in P[k + 1:]] + [list(map(float, P[0]))]
                    for _ in range(laps):
                        pts += [list(map(float, p)) for p in P[1:]] + [list(map(float, P[0]))]
                    sm = smooth_path(pts)
                    sm[0] = pts[0]; sm[-1] = pts[-1]
                    path = [[round(float(a), 1), round(float(b), 1)] for a, b in sm]
                    total = float(np.sum(np.linalg.norm(np.diff(sm, axis=0), axis=1))) * mpp
                starts.append({"label": t, "dist": dist, "surface": "dirt" if dirt else "turf", "inout": io, "route": rk,
                               "x": round(mx, 1), "y": round(my, 1), "path": path, "measured_m": round(total)})
        res[code] = starts
        print(code, [(s["label"], s["measured_m"]) for s in starts])
    Path(out).write_text(json.dumps({"source": "うまぽっと（https://umapot.com/）のコース素材の発走位置の印をもとに作成。", "venues": res}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True); ap.add_argument("--shapes", required=True); ap.add_argument("--out", required=True); ap.add_argument("--img-root", required=True)
    a = ap.parse_args(); main(a.src, a.shapes, a.out, a.img_root)
