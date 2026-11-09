#!/usr/bin/env python3
"""うまぽっと「主要コース」図（-1.png）にある発走位置の印（点線）を、SVGから位置として取り出す。
  python3 -m sim_v2.umapot_markers --src <umapot/pptx を置いた場所> --out <markers.json> [--overlay <dir>]
点線＝1本が1つの発走位置（線の中点が発走地点、線の向きがコースの幅の向き）。座標は -2.png と同じ画素。"""
import argparse, json, re
from pathlib import Path

DIRS = ["sapporo", "hakodate", "fukushima", "nigata", "tokyo", "nakayama", "chukyo", "kyoto", "hanshin", "kokura"]


def markers(svg_path, img_w=1192, img_h=825):
    s = Path(svg_path).read_text(encoding="utf-8", errors="ignore")
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', s).group(1).split()]
    k = img_w / vb[2]
    out = []
    for m in re.finditer(r'<path[^>]*stroke-dasharray[^>]*d="M\s*([\d.]+),([\d.]+)\s*L\s*([\d.]+),([\d.]+)', s):
        x1, y1, x2, y2 = [float(v) * k for v in m.groups()]
        out.append({"x": round((x1 + x2) / 2, 1), "y": round((y1 + y2) / 2, 1), "x1": round(x1, 1), "y1": round(y1, 1), "x2": round(x2, 1), "y2": round(y2, 1)})
    out.sort(key=lambda o: (o["y"], o["x"]))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True); ap.add_argument("--out", required=True); ap.add_argument("--overlay")
    a = ap.parse_args(); res = {}
    for d in DIRS:
        res[d] = markers(Path(a.src) / f"{d}.svg")
        if a.overlay:
            import cv2
            img = cv2.imread(str(Path(a.src) / f"{d}-1.png"))
            for i, o in enumerate(res[d]):
                cv2.line(img, (int(o["x1"]), int(o["y1"])), (int(o["x2"]), int(o["y2"])), (0, 0, 255), 3)
                cv2.putText(img, str(i), (int(o["x"]) + 6, int(o["y"]) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 2)
            cv2.imwrite(str(Path(a.overlay) / f"{d}-mk.png"), img)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: len(v) for k, v in res.items()})
