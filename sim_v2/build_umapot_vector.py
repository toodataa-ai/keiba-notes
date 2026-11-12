"""うまぽっとの元図（svg）から、走路まわりの図形をベクターのまま取り出し、
LABシミュレータの背景png（docs/lab/sim-v2/umapot/<場>.png）の画素座標に合わせて保存する。

使い方:
  python3 -m sim_v2.build_umapot_vector --src <非公開リポジトリの umapot/pptx> \
      --png-dir docs/lab/sim-v2/umapot --out docs/lab/sim-v2/umapot-vector.json [--overlay <dir>]

- 元の svg・png は公開リポジトリに置かない。出力は図形のパス（d）と色・線幅・座標の変換だけ。
- 2枚目のスライド（<場>-2.png と同じ図）の path 要素をそのまま使う（文字は除く）。
- svg の座標 → <場>-2.png の画素：一様な拡大（png幅 ÷ viewBox幅）。
- <場>-2.png → 背景png：切り出しの位置（画素の照合で求める。誤差0のときだけ採用）。
- 検証：ベクターを描いた画像と背景pngの、芝の緑・ダートの茶の画素の一致率（IoU）を出す。
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
from lxml import etree

SVG = "{http://www.w3.org/2000/svg}"
DIRS = {"tokyo": "tokyo", "nakayama": "nakayama", "kyoto": "kyoto", "hanshin": "hanshin", "chukyo": "chukyo",
        "niigata": "nigata", "fukushima": "fukushima", "kokura": "kokura", "sapporo": "sapporo", "hakodate": "hakodate"}
GREEN = (0, 176, 80)
ORANGE = (197, 90, 17)


def rgb2hex(v):
    if not v or v == "none":
        return None
    m = re.match(r"rgb\((\d+),(\d+),(\d+)\)", v)
    if m:
        return "#%02x%02x%02x" % tuple(int(x) for x in m.groups())
    return v


def slide_paths(svg_path):
    root = etree.parse(str(svg_path)).getroot()
    vb = [float(x) for x in root.get("viewBox").split()]
    slide = root.xpath('//*[@id="id2"]')[0]
    out = []
    for p in slide.iter(SVG + "path"):
        # 文字（text の中）は除く
        if any(a.tag == SVG + "text" for a in p.iterancestors()):
            continue
        if any(a.get("transform") for a in p.iterancestors()) or p.get("transform"):
            raise RuntimeError(f"{svg_path}: transform 付きの図形は未対応")
        d = re.sub(r"\s+", " ", p.get("d", "")).strip()
        if not d:
            continue
        fill, stroke = rgb2hex(p.get("fill")), rgb2hex(p.get("stroke"))
        if not fill and not stroke:
            continue
        e = {"d": d}
        if fill:
            e["fill"] = fill
        if stroke:
            e["stroke"] = stroke
            e["sw"] = float(p.get("stroke-width") or 28.222)
            if p.get("stroke-linejoin"):
                e["join"] = p.get("stroke-linejoin")
            if p.get("stroke-linecap"):
                e["cap"] = p.get("stroke-linecap")
        out.append(e)
    return vb, out


def render(vb, paths, k, ox, oy, w, h, scale=1):
    """ベクターを背景pngの画素座標で描いた画像（rsvg-convert）。"""
    body = "".join(
        '<path d="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="%s"/>' % (
            e["d"], e.get("fill", "none"), e.get("stroke", "none"), e.get("sw", 0), e.get("join", "miter"))
        for e in paths)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
           '<rect width="100%%" height="100%%" fill="#fff"/><g transform="translate(%f %f) scale(%f)">%s</g></svg>') % (
        w * scale, h * scale, w, h, -ox, -oy, k, body)
    with tempfile.TemporaryDirectory() as td:
        sp, pp = Path(td) / "a.svg", Path(td) / "a.png"
        sp.write_text(svg)
        subprocess.run(["rsvg-convert", "-o", str(pp), str(sp)], check=True)
        return cv2.imread(str(pp))


def cmask(img, rgb, tol=40):
    b, g, r = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    return (abs(r - rgb[0]) < tol) & (abs(g - rgb[1]) < tol) & (abs(b - rgb[2]) < tol)


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="非公開リポジトリの umapot/pptx のフォルダ")
    ap.add_argument("--png-dir", default="docs/lab/sim-v2/umapot")
    ap.add_argument("--out", default="docs/lab/sim-v2/umapot-vector.json")
    ap.add_argument("--overlay", help="重ね描きの確認画像の出力先（任意）")
    ap.add_argument("--min-iou", type=float, default=0.85)
    a = ap.parse_args()
    res = {"source": "元図：うまぽっと https://umapot.com/ の競馬場コース図（スライド2）。図形のパスだけを保存。",
           "units": "d は元図の座標。背景png画素 = (元図の座標 × k) − (ox, oy)", "venues": {}}
    report = {}
    for code, d in DIRS.items():
        svgp, two = Path(a.src) / d / f"{d}.svg", Path(a.src) / d / f"{d}-2.png"
        bgp = Path(a.png_dir) / f"{code}.png"
        if not (svgp.exists() and two.exists() and bgp.exists()):
            report[code] = "元ファイルなし"
            continue
        vb, paths = slide_paths(svgp)
        big, bg = cv2.imread(str(two)), cv2.imread(str(bgp))
        k = big.shape[1] / vb[2]
        if abs(big.shape[0] / vb[3] - k) / k > 0.005:
            report[code] = "縦横比が合わない"
            continue
        r = cv2.matchTemplate(big, bg, cv2.TM_SQDIFF)
        mn, _, loc, _ = cv2.minMaxLoc(r)
        # 画素あたりの差がごく小さい（圧縮の違い程度）ときだけ採用
        if mn / bg.size > 1.0:
            report[code] = f"切り出し位置が一致しない（差 {mn}）"
            continue
        ox, oy = loc
        h, w = bg.shape[:2]
        ren = render(vb, paths, k, ox, oy, w, h)
        ig, io = iou(cmask(ren, GREEN), cmask(bg, GREEN)), iou(cmask(ren, ORANGE), cmask(bg, ORANGE))
        ok = ig >= a.min_iou and (io >= a.min_iou or cmask(bg, ORANGE).sum() == 0)
        report[code] = {"iou_turf": round(ig, 3), "iou_dirt": round(io, 3), "ok": ok, "paths": len(paths)}
        if a.overlay:
            od = Path(a.overlay); od.mkdir(parents=True, exist_ok=True)
            # 左：背景png、中：ベクター（4倍）を縮小、右：差（赤＝png のみ、青＝ベクターのみ）
            diff = np.full_like(bg, 255)
            gb, gr = cmask(bg, GREEN) | cmask(bg, ORANGE), cmask(ren, GREEN) | cmask(ren, ORANGE)
            diff[gb & gr] = (180, 180, 180); diff[gb & ~gr] = (0, 0, 255); diff[~gb & gr] = (255, 0, 0)
            cv2.imwrite(str(od / f"{code}_cmp.png"), np.hstack([bg, ren, diff]))
            cv2.imwrite(str(od / f"{code}_vec4x.png"), render(vb, paths, k, ox, oy, w, h, scale=4))
        if not ok:
            continue
        res["venues"][code] = {"w": w, "h": h, "k": round(k, 8), "ox": ox, "oy": oy, "paths": paths}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("size", Path(a.out).stat().st_size)


if __name__ == "__main__":
    main()
