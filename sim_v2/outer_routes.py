#!/usr/bin/env python3
"""外回り（京都・阪神・中山）の芝の線を、図の緑の帯の上で作り直す。
内回りの線を外へ広げた近似は、阪神の右端の大きな膨らみや中山の上の大きな弧を通らないため、
図を見て決めた通過点（外回りの帯の中心）を順に、帯の中だけを通る最短の道でつなぐ。
  python3 -m sim_v2.outer_routes --shapes docs/lab/sim-v2/umapot-shapes.json --img-root docs/lab/sim-v2/umapot"""
import argparse, json
from pathlib import Path
import cv2, numpy as np
from scipy import ndimage as ndi
from skimage.graph import MCP_Geometric
from .trace_umapot import mask, GREEN
from .build_umapot_starts import smooth_path

# 走る向きの順（ゴールの次から一周）。座標は背景画像（docs/lab/sim-v2/umapot/<場>.png）の画素。
WAYPOINTS = {
    "hanshin": [(200, 457), (125, 395), (123, 320), (170, 255), (300, 172), (500, 116), (650, 72), (760, 62), (840, 110), (866, 200), (852, 300), (790, 370), (730, 410), (600, 452), (400, 455)],
    "kyoto": [(400, 462), (300, 425), (272, 330), (290, 250), (400, 142), (600, 97), (800, 52), (900, 62), (990, 110), (1035, 200), (1040, 290), (1010, 380), (985, 425), (940, 455), (800, 460), (650, 462)],
    "niigata": [(940, 343), (1000, 325), (1030, 270), (1030, 200), (1000, 130), (950, 90), (850, 88), (650, 88), (450, 88), (320, 88), (250, 100), (200, 150), (190, 215), (215, 285), (270, 330), (350, 342), (500, 343), (700, 343)],
    "nakayama": [(200, 515), (130, 470), (120, 330), (150, 200), (215, 115), (330, 55), (450, 52), (560, 92), (660, 152), (730, 205), (780, 280), (790, 350), (770, 430), (710, 490), (640, 515), (480, 517)],
}


def build(venue, shapes, img_root):
    img = cv2.imread(str(Path(img_root) / f"{venue}.png")); M = mask(img, GREEN)
    M = cv2.morphologyEx(M, cv2.MORPH_CLOSE, np.ones((1, 15), np.uint8))   # ゴールの黒い縦線で帯が切れないように
    dt = ndi.distance_transform_edt(M > 0)
    cost = np.where(M > 0, 1.0 + 3.0 / (dt + 1.0), np.inf)
    ys, xs = np.nonzero(M > 0)

    def snap(p):
        j = int(np.argmin((xs - p[0]) ** 2 + (ys - p[1]) ** 2)); return (int(ys[j]), int(xs[j]))
    v = shapes[venue]; inner = v["routes"].get("turf|inner") or v["routes"].get("turf|single")
    gx = inner["pts"][0][0]
    col = np.nonzero(M[:, int(gx) + 12] > 0)[0]
    low = col[col > np.median(ys)]
    # 一番下の帯（ゴール線の下）の中心
    runs = np.split(low, np.nonzero(np.diff(low) > 1)[0] + 1)
    run = runs[-1]; start = (int(gx) + 12, int(run.mean()))
    pts_w = [start] + WAYPOINTS[venue] + [start]
    path = []
    for a, b in zip(pts_w[:-1], pts_w[1:]):
        sa, sb = snap(a), snap(b)
        mcp = MCP_Geometric(cost, fully_connected=True); mcp.find_costs([sa], [sb])
        seg = np.array(mcp.traceback(sb))[:, ::-1].astype(float)
        path.extend(seg.tolist() if not path else seg[1:].tolist())
    sm = smooth_path(path, step=4.0, win=21)
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(sm, axis=0), axis=1))])
    t = np.linspace(0, d[-1], 241)[:-1]
    out = np.stack([np.interp(t, d, sm[:, 0]), np.interp(t, d, sm[:, 1])], axis=1)
    return out, float(d[-1])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--shapes", required=True); ap.add_argument("--img-root", required=True); ap.add_argument("--write", action="store_true")
    a = ap.parse_args(); doc = json.loads(Path(a.shapes).read_text(encoding="utf-8")); sh = doc["venues"]
    for ven in WAYPOINTS:
        pts, per = build(ven, sh, a.img_root)
        r = sh[ven]["routes"]["turf|outer"]; mpp = sh[ven]["m_per_px"]
        print(ven, "周長(画素)", round(per), "×", mpp, "=", round(per * mpp), "m / 公式", r["lap_m"], "旧", r["per_px"])
        if a.write:
            r["pts"] = [[round(float(x), 1), round(float(y), 1)] for x, y in pts]; r["per_px"] = round(per, 1)
    if a.write:
        Path(a.shapes).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
