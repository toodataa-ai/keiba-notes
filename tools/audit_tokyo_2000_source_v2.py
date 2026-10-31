#!/usr/bin/env python3
"""Generate LOCAL audit inputs from the publisher's PPTX; never fetch or publish source files.
Outputs contain source material: keep them outside docs/ and outside Git.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

PPTX_SHA256 = 'c6c372babca741439fe2c18857ea7d3fbccd42d115377448a836327ed53dc6c4'
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
IDENTITY = (1, 0, 0, 1, 0, 0)


def mul(a, b):
    x, y, z, w, t, u = a
    A, B, C, D, T, U = b
    return (x*A+z*B, y*A+w*B, x*C+z*D, y*C+w*D, x*T+z*U+t, y*T+w*U+u)


def point(m, x, y):
    return [m[0]*x+m[2]*y+m[4], m[1]*x+m[3]*y+m[5]]


def transform(e, group=False):
    if e is None:
        return IDENTITY
    off, ext = e.find('a:off', NS), e.find('a:ext', NS)
    x, y, w, h = int(off.get('x')), int(off.get('y')), int(ext.get('cx')), int(ext.get('cy'))
    angle = int(e.get('rot', '0')) / 60000 * math.pi / 180
    fx, fy = (-1 if e.get('flipH') == '1' else 1), (-1 if e.get('flipV') == '1' else 1)
    rotation = (math.cos(angle)*fx, math.sin(angle)*fx, -math.sin(angle)*fy, math.cos(angle)*fy, 0, 0)
    m = mul((1, 0, 0, 1, x+w/2, y+h/2), mul(rotation, (1, 0, 0, 1, -w/2, -h/2)))
    if group:
        co, ce = e.find('a:chOff', NS), e.find('a:chExt', NS)
        cw, ch = int(ce.get('cx')), int(ce.get('cy'))
        if not cw or not ch:
            return IDENTITY
        sx, sy = w/cw, h/ch
        m = mul(m, (sx, 0, 0, sy, -int(co.get('x'))*sx, -int(co.get('y'))*sy))
    return m


def shapes(xml):
    result = {}
    root = ET.fromstring(xml)
    def walk(node, parent):
        for child in node:
            tag = child.tag.split('}')[-1]
            if tag == 'grpSp':
                walk(child, mul(parent, transform(child.find('p:grpSpPr/a:xfrm', NS), True)))
            elif tag in ('sp', 'cxnSp'):
                nv = child.find('.//p:cNvPr', NS)
                pr = child.find('p:spPr', NS)
                xf = pr.find('a:xfrm', NS)
                if xf is not None:
                    result[nv.get('id')] = (pr, mul(parent, transform(xf)), xf)
    walk(root.find('p:cSld/p:spTree', NS), IDENTITY)
    return result


def compile_geometry(pptx):
    with zipfile.ZipFile(pptx) as z:
        size = ET.fromstring(z.read('ppt/presentation.xml')).find('p:sldSz', NS)
        width, height = int(size.get('cx')), int(size.get('cy'))
        scale = width/620
        labelled = shapes(z.read('ppt/slides/slide1.xml'))
        clean = shapes(z.read('ppt/slides/slide2.xml'))
    def bounds(shape):
        pr, mat, xf = shape
        ext = xf.find('a:ext', NS)
        a = point(mat, 0, 0);b = point(mat, int(ext.get('cx')), int(ext.get('cy')))
        return a[0]/scale, a[1]/scale, (b[0]-a[0])/scale, (b[1]-a[1])/scale
    x, y, w, h = bounds(clean['4'])
    radius = h/2
    left, cy = x+radius, y+radius
    pr, mat, xf = clean['9']
    path = pr.find('a:custGeom/a:pathLst/a:path', NS)
    ext = xf.find('a:ext', NS)
    sx, sy = int(ext.get('cx'))/int(path.get('w')), int(ext.get('cy'))/int(path.get('h'))
    def coords(node):
        return [point(mat, int(p.get('x'))*sx, int(p.get('y'))*sy) for p in node.findall('a:pt', NS)]
    commands = list(path)
    arc_start = coords(commands[1])[0]
    cubic = [arc_start] + coords(commands[2])
    cubic = [[a/scale, b/scale] for a,b in cubic]
    # Start marker is in a 90-degree rotated GROUP. Its transformed midpoint is essential.
    start_shape = labelled['93'];pr, mat, xf = start_shape
    ext = xf.find('a:ext', NS)
    marker = point(mat, int(ext.get('cx'))/2, int(ext.get('cy'))/2)
    chute_x, chute_y, chute_w, chute_h = bounds(clean['10'])
    start = [chute_x, marker[1]/scale]
    assert abs(start[0]-marker[0]/scale) < .2, 'START_MARKER_OFF_CHUTE'
    goal_x, goal_y, goal_w, goal_h = bounds(labelled['20'])
    finish_x = goal_x+goal_w/2
    sections = [
        {'from':0,'to':100,'kind':'line','name':'ポケット・発走直後（距離配分は仮説）','points':[start,cubic[3]]},
        {'from':100,'to':300,'kind':'cubic','name':'2コーナー・外側走路','points':list(reversed(cubic))},
        {'from':300,'to':900,'kind':'line','name':'向正面・直線保持','points':[cubic[0],[left,y]]},
        {'from':900,'to':1145,'kind':'arc','name':'3コーナー','center':[left,cy],'radius':radius,'angles':[-math.pi/2,-math.pi]},
        {'from':1145,'to':1474.1,'kind':'arc','name':'4コーナー','center':[left,cy],'radius':radius,'angles':[-math.pi,-3*math.pi/2]},
        {'from':1474.1,'to':2000,'kind':'line','name':'最後の直線525.9m','points':[[left,y+h],[finish_x,y+h]]},
        {'from':2000,'to':2120,'kind':'line','name':'余走検査120m','points':[[finish_x,y+h],[finish_x+(finish_x-left)*120/525.9,y+h]]}
    ]
    stroke = int(clean['4'][0].find('a:ln', NS).get('w'))/scale
    assert all(abs(a-b)<.001 for a,b in zip(sections[0]['points'][-1],cubic[3]))
    return {'courseId':'tokyo_turf_2000','sourcePptxSha256':PPTX_SHA256,
            'sourceSlide':2,'width':620,'height':height/scale,'sections':sections,
            'finishMark':{'x':goal_x,'y':goal_y,'width':goal_w,'height':goal_h},
            'strokeWidth':stroke,'laneOffset':9,'discRadius':.6,'maxLane':16,
            'sourceShapeIds':{'circuit':'4','outerBend':'9','chute':'10','startMarkerSlide1':'93','goalSlide1':'20'},
            'distanceAnchorsSurveyed':False,'canAnimate':False,
            'warning':'原図対応候補。途中距離配分・走行安全・目視は未承認。'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pptx', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    data = args.pptx.read_bytes()
    if hashlib.sha256(data).hexdigest() != PPTX_SHA256:
        raise SystemExit('SOURCE_SHA256_MISMATCH: unknown publisher version; do not silently accept')
    out = args.out.resolve()
    repo = Path(__file__).resolve().parents[1]
    if out == repo or repo in out.parents:
        raise SystemExit('SOURCE_OUTPUT_MUST_BE_OUTSIDE_REPOSITORY')
    out.mkdir(parents=True, exist_ok=True)
    geometry = compile_geometry(args.pptx)
    with tempfile.TemporaryDirectory(prefix='tokyo-source-audit-') as temp:
        temp = Path(temp)
        source = temp/'source.pptx';source.write_bytes(data)
        subprocess.run(['soffice','--headless',f'-env:UserInstallation={(temp/"lo-profile").as_uri()}',
                        '--convert-to','pdf','--outdir',str(temp),str(source)],check=True,capture_output=True)
        pdf = temp/'source.pdf'
        subprocess.run(['pdftocairo','-f','2','-l','2','-svg',str(pdf),str(out/'source-local.svg')],check=True)
        subprocess.run(['pdftoppm','-f','2','-singlefile','-scale-to','2480','-png',str(pdf),str(out/'source-local')],check=True)
    svg = (out/'source-local.svg').read_bytes()
    geometry['sourceSvgSha256'] = hashlib.sha256(svg).hexdigest()
    (out/'audit-local.json').write_text(json.dumps(geometry,ensure_ascii=False,indent=2)+'\n')
    (out/'DO_NOT_PUBLISH.txt').write_text('LOCAL SOURCE MATERIAL: do not commit or upload this directory. Source terms: https://umapot.com/?page_id=116\n')
    print(json.dumps({'out':str(out),'sourceSha256':PPTX_SHA256,'start':geometry['sections'][0]['points'][0],
                      'sourceSize':[geometry['width'],geometry['height']],'canAnimate':False},ensure_ascii=False))

if __name__ == '__main__':
    main()
