"""JRA公式のコース平面図（非公開リポジトリに保存した画像）から、各コースの内ラチの形をなぞる（研究用）。
画像は公開しない。出力は自前で作った座標（メートル、一周の長さを公式の値に合わせる）だけ。
芝＝緑、ダート＝オレンジの色で領域を分け、
  ダート：オレンジの帯の内側の縁
  芝（周回が1つ／内回り）：オレンジの帯の外側の縁（＝芝の内ラチ）
  芝（外回り）：緑の領域の外形から細い引き込み線を除き、帯の幅だけ内側へずらした線
をとる。ゴールの位置は図の「ゴール」の印の画素で指定する。"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np, cv2

GREEN = (124, 195, 118); ORANGE = (230, 171, 100)
# 図の中のゴールの印の位置（画素）。図を見て決めた値
GOAL = {"nakayama": (238, 322), "tokyo": (400, 282), "kyoto": (276, 212), "hanshin": (168, 282), "sapporo": (203, 268),
        "niigata": (430, 145), "chukyo": (382, 232), "hakodate": (226, 252), "kokura": (214, 252)}
TWO_TURF = {"nakayama", "kyoto", "hanshin", "niigata"}


def mask(img, rgb, tol=28):
    d = np.abs(img.astype(int) - np.array(rgb[::-1])).sum(axis=2)
    return (d < tol).astype(np.uint8) * 255


def resample(pts, n=720):
    pts = np.asarray(pts, float)
    seg = np.r_[np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)]
    s = np.r_[0, np.cumsum(seg)]; L = s[-1]
    t = np.linspace(0, L, n, endpoint=False)
    closed = np.vstack([pts, pts[:1]])
    x = np.interp(t, s, closed[:, 0]); y = np.interp(t, s, closed[:, 1])
    return np.c_[x, y], L


def smooth(pts, k=9):
    n = len(pts); out = np.zeros_like(pts)
    for i in range(n):
        idx = [(i + j) % n for j in range(-k, k + 1)]
        out[i] = pts[idx].mean(axis=0)
    return out


def offset(pts, d):
    """閉じた線を外向きに d 画素ずらす（内側へは負）。外向き＝多角形の外側。"""
    n = len(pts); area = 0.5 * sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    out = []
    for i in range(n):
        p0, p1 = pts[i - 1], pts[(i + 1) % n]
        tx, ty = p1 - p0; l = math.hypot(tx, ty) or 1
        nx, ny = ty / l, -tx / l       # 右手の法線
        if area < 0: nx, ny = -nx, -ny
        out.append(pts[i] + np.array([nx, ny]) * d)
    return np.array(out)


def largest(cnts):
    return max(cnts, key=cv2.contourArea)


OPEN_K = {"kyoto": 45, "nakayama": 35, "hanshin": 31}


def trace(img_path, kopen=25):
    img = cv2.imread(str(img_path))
    g = mask(img, GREEN); o = mask(img, ORANGE)
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    o = cv2.morphologyEx(o, cv2.MORPH_CLOSE, k5, iterations=2)
    g = cv2.morphologyEx(g, cv2.MORPH_CLOSE, k5, iterations=2)
    out = {}
    # ダート：最大の帯の、穴（内側の縁）と外形
    cnts, hier = cv2.findContours(o, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if cnts:
        i = max(range(len(cnts)), key=lambda i: cv2.contourArea(cnts[i]) if hier[0][i][3] == -1 else 0)
        holes = [cnts[j] for j in range(len(cnts)) if hier[0][j][3] == i]
        if holes:
            out["dirt"] = largest(holes)[:, 0, :]
        out["dirt_outer"] = cnts[i][:, 0, :]
        band = cv2.contourArea(cnts[i]) - (cv2.contourArea(largest(holes)) if holes else 0)
        out["dirt_band_px"] = band / max(1, cv2.arcLength(cnts[i], True))
    # 芝の外形（穴を埋めて、細い引き込み線を開きで除く）
    cnts, _ = cv2.findContours(g, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    blob = np.zeros_like(g); cv2.drawContours(blob, [largest(cnts)], -1, 255, -1)
    kk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kopen, kopen))
    opened = cv2.morphologyEx(blob, cv2.MORPH_OPEN, kk)
    c2, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out["turf_outer_edge"] = largest(c2)[:, 0, :]
    gl = cv2.bitwise_and(g, opened)
    out["turf_band_px"] = float(cv2.countNonZero(gl)) / max(1, cv2.arcLength(largest(c2), True))
    return img, out


def hull(c):
    return cv2.convexHull(c.reshape(-1, 1, 2).astype(np.int32))[:, 0, :]


def build(src, catalog):
    """各コースの内ラチの形（メートル）を作る。"""
    cat = json.loads(Path(catalog).read_text(encoding="utf-8"))
    out = {}
    for v in cat["venues"]:
        code = v["code"]; p = Path(src) / code / "pic_course_heimenzu.png"
        if not p.exists() or not GOAL.get(code):
            continue
        img, t = trace(p, OPEN_K.get(code, 25))
        loops = {}
        loops["dirt"] = smooth(resample(hull(t["dirt"]), 720)[0], 3)
        inner_turf = offset(smooth(resample(hull(t["dirt_outer"]), 720)[0], 3), 3.0)
        loops["turf_inner"] = inner_turf
        outer = smooth(resample(hull(t["turf_outer_edge"]), 720)[0], 3)
        loops["turf_outer"] = offset(outer, -t["turf_band_px"] * 0.8)
        routes = {}
        for r in v["routes"]:
            var = list(r["variants"].values())[0]; lap = var.get("lap_m")
            if r["layout"] == "straight" or not lap:
                continue
            if r["surface"] == "dirt":
                key = "dirt"
            elif r["layout"] == "outer" or (r["layout"] == "outer_to_inner"):
                key = "turf_outer"
            elif r["layout"] == "inner":
                key = "turf_inner"
            else:
                key = "turf_inner"
            pts = loops[key]
            # ゴールに最も近い点から、レースの向きに並べ直す
            gi = int(np.argmin(np.linalg.norm(pts - np.array(GOAL[code]), axis=1)))
            pts = np.roll(pts, -gi, axis=0)
            dx = pts[1][0] - pts[-1][0]
            right = v["turn"] == "right"
            if (right and dx > 0) or (not right and dx < 0):
                pts = np.vstack([pts[:1], pts[1:][::-1]])
            per = float(np.sum(np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)))
            routes[r["surface"] + "|" + r["layout"]] = {"px": pts, "per_px": per, "lap_m": lap}
        if not routes:
            continue
        mpp = float(np.median([x["lap_m"] / x["per_px"] for x in routes.values()]))
        cx, cy = np.mean(np.vstack([x["px"] for x in routes.values()]), axis=0)
        out[code] = {"m_per_px": round(mpp, 4), "routes": {k: {"pts": [[round((x - cx) * mpp, 1), round((y - cy) * mpp, 1)] for x, y in r["px"][::3]],
                                                             "lap_m": r["lap_m"], "traced_lap_m": round(r["per_px"] * mpp, 1)} for k, r in routes.items()}}
        print(code, {k: (r["lap_m"], round(r["per_px"] * mpp)) for k, r in routes.items()})
    return out


if __name__ == "__main__":
    src = Path(sys.argv[1]); dst = Path(sys.argv[2])
    res = build(src, Path(__file__).resolve().parents[1] / "docs/lab/race-course-catalog-v1.json")
    dst.write_text(json.dumps({"note": "JRA公式のコース平面図をなぞって作った内ラチの形（メートル、ゴール地点から走る向きの順）。近似。福島は平面図が無いため未作成（楕円で近似）。", "venues": res}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
