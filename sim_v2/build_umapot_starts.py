#!/usr/bin/env python3
"""うまぽっと主要コース図の発走位置（点線）を、距離・芝ダ・内外つきで docs/lab/sim-v2/umapot-starts.json にする。
各発走位置から、なぞった走路の線に合流してゴールまで走る道すじ（pts）も作る（周回が必要な距離は周回を足す）。
  python3 -m sim_v2.build_umapot_starts --src <pptx/svg/png を置いた場所> --shapes docs/lab/sim-v2/umapot-shapes.json --out docs/lab/sim-v2/umapot-starts.json"""
import argparse, json, math, re
from pathlib import Path
import cv2, numpy as np
from .umapot_labels import labels
from .umapot_markers import markers, DIRS

CODE = {"nigata": "niigata"}
LAB = re.compile(r"^(D?)(\d{3,4})(内|外)?$")


def crop_offset(src, d, crop_png):
    full = cv2.imread(str(Path(src) / f"{d}-2.png")); crop = cv2.imread(str(crop_png))
    r = cv2.matchTemplate(full, crop, cv2.TM_SQDIFF)
    _, _, loc, _ = cv2.minMaxLoc(r) if False else (None, None, cv2.minMaxLoc(-r)[3], None)
    return loc  # (x0, y0)


def main(src, shapes, out, img_root):
    sh = json.loads(Path(shapes).read_text(encoding="utf-8"))["venues"]
    res = {}
    for d in DIRS:
        code = CODE.get(d, d); v = sh[code]
        x0, y0 = crop_offset(src, d, Path(img_root) / f"{code}.png")
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
                    path = [[round(mx, 1), round(my, 1)], [round(float(P[0][0]), 1), round(float(P[0][1]), 1)]]
                    total = math.hypot(mx - P[0][0], my - P[0][1]) * mpp
                else:
                    k = int(np.argmin(np.linalg.norm(P - np.array([mx, my]), axis=1)))
                    bridge = float(np.linalg.norm(P[k] - np.array([mx, my])))
                    arc = Lpx - cum[k]
                    first_m = (bridge + arc) * mpp
                    laps = max(0, round((dist - first_m) / R["lap_m"]))
                    pts = [[mx, my]] + [list(map(float, p)) for p in P[k:]] + [list(map(float, P[0]))]
                    for _ in range(laps):
                        pts += [list(map(float, p)) for p in P[1:]] + [list(map(float, P[0]))]
                    path = [[round(a, 1), round(b, 1)] for a, b in pts]
                    total = first_m + laps * R["lap_m"]
                starts.append({"label": t, "dist": dist, "surface": "dirt" if dirt else "turf", "inout": io, "route": rk,
                               "x": round(mx, 1), "y": round(my, 1), "path": path, "measured_m": round(total)})
        res[code] = starts
        print(code, [(s["label"], s["measured_m"]) for s in starts])
    Path(out).write_text(json.dumps({"source": "うまぽっと（https://umapot.com/）のコース素材の発走位置の印をもとに作成。", "venues": res}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True); ap.add_argument("--shapes", required=True); ap.add_argument("--out", required=True); ap.add_argument("--img-root", required=True)
    a = ap.parse_args(); main(a.src, a.shapes, a.out, a.img_root)
