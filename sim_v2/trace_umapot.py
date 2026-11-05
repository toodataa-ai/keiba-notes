"""うまぽっと（umapot.com）のコース素材（パワーポイントを画像にしたもの・ラベル無しの2枚目）から、
走路の内ラチの線をなぞる。背景にはその画像をそのまま使い、馬はこの線に沿って描く（研究用・LAB）。
素材の利用規約：個人・商用とも無料で利用可、再配布・販売は不可（https://umapot.com/?page_id=116）。
ページには出典を表示する。"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, cv2
from sim_v2.trace_courses import resample, smooth, offset, hull

GREEN = (0, 176, 80); ORANGE = (197, 90, 17)
DIRS = {"tokyo": "tokyo", "nakayama": "nakayama", "kyoto": "kyoto", "hanshin": "hanshin", "chukyo": "chukyo", "niigata": "nigata",
        "fukushima": "fukushima", "kokura": "kokura", "sapporo": "sapporo", "hakodate": "hakodate"}


def mask(img, rgb, tol=60):
    d = np.abs(img.astype(int) - np.array(rgb[::-1])).sum(axis=2)
    return (d < tol).astype(np.uint8) * 255


def largest(cnts):
    return max(cnts, key=cv2.contourArea)


def goal_x(img, dirt_outer):
    """GOAL の黒い縦線：ダートの下のあたりで、黒い画素が縦に長く続く列。"""
    blk = (img.sum(axis=2) < 120).astype(np.uint8)
    x0, y0, w, h = cv2.boundingRect(dirt_outer)
    best = None
    for x in range(x0, x0 + w):
        col = blk[y0 + h // 2: y0 + h + 140, x]
        run = 0; mx = 0
        for v in col:
            run = run + 1 if v else 0; mx = max(mx, run)
        if mx > 40 and (best is None or mx > best[1]):
            best = (x, mx)
    return best[0] if best else None


def trace(path, two_turf, left_loop=False):
    img = cv2.imread(str(path))
    g = mask(img, GREEN); o = mask(img, ORANGE)
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    o = cv2.morphologyEx(o, cv2.MORPH_CLOSE, k5, iterations=2)
    cnts, hier = cv2.findContours(o, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    i = max(range(len(cnts)), key=lambda i: cv2.contourArea(cnts[i]) if hier[0][i][3] == -1 else 0)
    holes = [cnts[j] for j in range(len(cnts)) if hier[0][j][3] == i]
    dirt_in = hull(largest(holes)[:, 0, :]); dirt_out = hull(cnts[i][:, 0, :])
    dirt_band = (cv2.contourArea(dirt_out.reshape(-1, 1, 2)) - cv2.contourArea(dirt_in.reshape(-1, 1, 2))) / cv2.arcLength(dirt_out.reshape(-1, 1, 2), True)
    # 芝の内ラチ：ダートの外側から外へ、最初に緑に当たるまでの距離（白いすき間）の中央値だけずらす
    do = smooth(resample(dirt_out, 720)[0], 3)
    gaps = []
    for d in range(1, 40):
        pts = offset(do, d).astype(int)
        ok = [(0 <= y < g.shape[0] and 0 <= x < g.shape[1] and g[y, x] > 0) for x, y in pts]
        gaps.append(np.mean(ok))
        if np.mean(ok) > 0.6:
            break
    gap = len(gaps) + 1
    out = {"dirt": smooth(resample(dirt_in, 720)[0], 3), "turf_inner": offset(do, gap), "dirt_band_px": float(dirt_band)}
    # 外回り：緑のかたまりの外形から引き込み線を除き、帯の幅だけ内側へ
    cg, _ = cv2.findContours(g, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    blob = np.zeros_like(g); cv2.drawContours(blob, [largest(cg)], -1, 255, -1)
    band = dirt_band * 0.95
    # 引き込み線の細い帯を除くため、ダートの外形を少し広げた枠の中の緑だけを使う（新潟は左の大きな周回も含める）
    x0, y0, w, h = cv2.boundingRect(dirt_out)
    m = int(band * 2.4)
    box = np.zeros_like(g)
    lx = x0 - m
    if left_loop:
        ys, xs = np.where(g > 0)
        lx = int(np.percentile(xs, 2)) + 55
    box[max(0, y0 - m): y0 + h + m, max(0, lx): x0 + w + m] = 255
    cut = cv2.bitwise_and(g, box)
    cg, _ = cv2.findContours(cut, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    oe = smooth(resample(hull(largest(cg)[:, 0, :]), 720)[0], 3)
    band = dirt_band * 0.9
    out["turf_outer"] = offset(oe, -band)
    gx = goal_x(img, dirt_out.reshape(-1, 1, 2))
    return img, out, gx


def main(src, catalog, out_json, img_dir):
    cat = json.loads(Path(catalog).read_text(encoding="utf-8"))
    Path(img_dir).mkdir(parents=True, exist_ok=True)
    res = {}
    for v in cat["venues"]:
        code = v["code"]; d = DIRS[code]
        p = Path(src) / d / f"{d}-2.png"
        if not p.exists():
            continue
        two = any(r["layout"] == "outer" for r in v["routes"])
        img, loops, gx = trace(p, two, left_loop=(code == 'niigata'))
        # 背景用に、走路のまわりだけ切り出す（左上の題字は入れない）
        g = mask(img, GREEN) | mask(img, ORANGE)
        ys, xs = np.where(g > 0); x0, x1, y0, y1 = xs.min() - 20, xs.max() + 20, ys.min() - 20, ys.max() + 60
        x0, y0 = max(0, x0), max(60, y0)
        crop = img[y0:y1, x0:x1]
        cv2.imwrite(str(Path(img_dir) / f"{code}.png"), crop, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        routes = {}
        for r in v["routes"]:
            var = list(r["variants"].values())[0]; lap = var.get("lap_m")
            if r["layout"] == "straight" or not lap:
                continue
            key = "dirt" if r["surface"] == "dirt" else ("turf_outer" if r["layout"] in ("outer", "outer_to_inner") else "turf_inner")
            if key == "turf_outer" and code != "niigata":
                # 外回りは、内回りの線を外へ広げたもの（一周が公式の長さの比になる幅）
                ri = next(q for q in v["routes"] if q["surface"] == "turf" and q["layout"] in ("inner", "single"))
                lap_i = list(ri["variants"].values())[0]["lap_m"]
                base = loops["turf_inner"]
                per0 = float(np.sum(np.linalg.norm(np.diff(np.vstack([base, base[:1]]), axis=0), axis=1)))
                loops = dict(loops); loops["turf_outer"] = offset(base, per0 * (lap / lap_i - 1) / (2 * np.pi))
            pts = loops[key] - np.array([x0, y0])
            # ゴール：GOAL の縦線の x で、下側の直線上の点
            cand = [k for k in range(len(pts)) if pts[k][1] > np.median(pts[:, 1])]
            gi = min(cand, key=lambda k: abs(pts[k][0] - (gx - x0))) if gx else 0
            pts = np.roll(pts, -gi, axis=0)
            dx = pts[1][0] - pts[-1][0]; right = v["turn"] == "right"
            if (right and dx > 0) or (not right and dx < 0):
                pts = np.vstack([pts[:1], pts[1:][::-1]])
            per = float(np.sum(np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)))
            routes[r["surface"] + "|" + r["layout"]] = {"pts": [[round(float(x), 1), round(float(y), 1)] for x, y in pts[::3]], "lap_m": lap, "per_px": round(per, 1)}
        res[code] = {"img": f"sim-v2/umapot/{code}.png", "w": int(crop.shape[1]), "h": int(crop.shape[0]), "routes": routes,
                     "m_per_px": round(float(np.median([r["lap_m"] / r["per_px"] for r in routes.values()])), 4)}
        print(code, "goal_x", gx, {k: (r["lap_m"], r["per_px"]) for k, r in routes.items()})
    Path(out_json).write_text(json.dumps({"source": "うまぽっと（https://umapot.com/）の競馬場コース素材をもとに作成。走路の線は自前でなぞったもの。",
                                          "units": "画像の画素（各コースの一周が公式の長さになるよう、エンジン側で伸縮）", "venues": res}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
