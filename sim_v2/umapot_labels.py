#!/usr/bin/env python3
"""うまぽっとの pptx（主要コース図）から、発走位置の文字（1600外・D1400 など）の位置を取り出す。
グループの入れ子（位置・拡大・回転）をたどって、スライド上の中心座標（-2.png と同じ画素）にする。"""
import math, re, zipfile
from lxml import etree

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main", "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
LABEL = re.compile(r"^(D?\d{3,4})(内|外)?$")


def _xf(el):
    x = el.find("./p:grpSpPr/a:xfrm", NS) if el.tag.endswith("grpSp") else el.find("./p:spPr/a:xfrm", NS)
    return x


def labels(pptx_path, img_w=1192):
    z = zipfile.ZipFile(pptx_path)
    sz = etree.fromstring(z.read("ppt/presentation.xml")).find(".//p:sldSz", NS)
    sw = float(sz.get("cx"))
    root = etree.fromstring(z.read("ppt/slides/slide1.xml"))
    out = []

    def walk(el, mats):
        for ch in el:
            tag = etree.QName(ch).localname
            if tag == "grpSp":
                x = ch.find("./p:grpSpPr/a:xfrm", NS)
                if x is None:
                    walk(ch, mats); continue
                off, ext = x.find("a:off", NS), x.find("a:ext", NS)
                co, ce = x.find("a:chOff", NS), x.find("a:chExt", NS)
                ox, oy, ex, ey = (float(off.get("x")), float(off.get("y")), float(ext.get("cx")), float(ext.get("cy")))
                cx0, cy0, cex, cey = (float(co.get("x")), float(co.get("y")), float(ce.get("cx")) or 1, float(ce.get("cy")) or 1)
                rot = math.radians(int(x.get("rot", "0")) / 60000.0)
                sx, sy = ex / cex, ey / cey
                mid = (ox + ex / 2, oy + ey / 2)

                def f(pt, ox=ox, oy=oy, cx0=cx0, cy0=cy0, sx=sx, sy=sy, rot=rot, mid=mid):
                    px, py = ox + (pt[0] - cx0) * sx, oy + (pt[1] - cy0) * sy
                    if rot:
                        dx, dy = px - mid[0], py - mid[1]
                        px, py = mid[0] + dx * math.cos(rot) - dy * math.sin(rot), mid[1] + dx * math.sin(rot) + dy * math.cos(rot)
                    return (px, py)
                walk(ch, [f] + mats)
            elif tag == "sp":
                txt = "".join(ch.xpath(".//a:t/text()", namespaces=NS)).strip()
                m = LABEL.match(txt)
                if not m:
                    continue
                x = ch.find("./p:spPr/a:xfrm", NS)
                off, ext = x.find("a:off", NS), x.find("a:ext", NS)
                pt = (float(off.get("x")) + float(ext.get("cx")) / 2, float(off.get("y")) + float(ext.get("cy")) / 2)
                for f in mats:
                    pt = f(pt)
                k = img_w / sw
                out.append({"text": txt, "x": round(pt[0] * k, 1), "y": round(pt[1] * k, 1)})
            else:
                if len(ch):
                    walk(ch, mats)
    walk(root.find(".//p:spTree", NS), [])
    return out


if __name__ == "__main__":
    import sys, json
    print(json.dumps(labels(sys.argv[1]), ensure_ascii=False))
