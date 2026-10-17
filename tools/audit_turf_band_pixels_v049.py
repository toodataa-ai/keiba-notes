#!/usr/bin/env python3
"""LAB: verify projected horse lanes really lie on source illustration's GREEN turf.

Image never committed: only CI fetch. The 18-horse engine's physical lane indices
are mapped to the measured green inner/outer rails, not a fitted horse spline.
Labels and rail markings can obscure individual sampled pixels.
"""
import io
import json
import subprocess
import urllib.request
from PIL import Image

URL="https://umapot.com/data/powerpoint/kyoto_couse/kyoto_couse_1.jpg"
JS=r"""
const fs=require('fs'),vm=require('vm'),w={},document={getElementById:()=>null,querySelector:()=>null};
for(const p of ['race-course-geometry-v1.js','race-turf-corridor-v1.js','race-umapot-overlay-v1.js']){
 vm.runInNewContext(fs.readFileSync('docs/lab/'+p,'utf8'),
   {window:w,globalThis:w,document},{filename:p});
}
const data=JSON.parse(fs.readFileSync('docs/lab/race-turf-rails-kyoto-inner-2000-v1.json','utf8'));
w.RaceTurfCorridor.register(data);
const profile=w.RaceCourseGeometry.get('kyoto_turf_inner_2000'),rows=[];
for(let d=0;d<=2000;d+=10){
 for(const lane of [0,1,3,5,8,14]){
  const p=w.RaceUmapotOverlay.point(profile,d,lane);
  const band=w.RaceTurfCorridor.rails(profile,d,w.RaceUmapotOverlay.legacyPoint);
  rows.push({d,lane,x:p.x,y:p.y,
    inner:band.inner,outer:band.outer,
    fraction:w.RaceTurfCorridor.fraction(profile,lane)});
 }
}
process.stdout.write(JSON.stringify(rows));
"""
def is_green(c):
    r,g,b=c[:3]
    return g>105 and g>r*1.38 and g>b*1.17 and r<135 and b<150
def nearby_green(im,x,y,radius):
    for dx in range(-radius,radius+1):
        for dy in range(-radius,radius+1):
            if dx*dx+dy*dy>radius*radius:continue
            cx,cy=int(round(x))+dx,int(round(y))+dy
            if 0<=cx<im.width and 0<=cy<im.height and is_green(im.getpixel((cx,cy))):return True
    return False
def main():
    req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 (LAB geometry QA)'})
    with urllib.request.urlopen(req,timeout=30) as r:
        im=Image.open(io.BytesIO(r.read())).convert('RGB')
    assert im.size==(620,430),im.size
    pts=json.loads(subprocess.check_output(['node','-e',JS],text=True))
    counts={lane:{"raw":0,"near":0,"count":0} for lane in [0,1,3,5,8,14]}
    worst=[]
    for p in pts:
        lane=p['lane']
        counts[lane]['count']+=1
        xi=int(round(p['x']))
        yi=int(round(p['y']))
        if is_green(im.getpixel((xi,yi))):
            counts[lane]['raw']+=1
        if nearby_green(im,p['x'],p['y'],2):counts[lane]['near']+=1
        else:worst.append([p['d'],lane,round(p['x'],1),round(p['y'],1)])
        ratio=p['fraction']
        assert 0<ratio<1
        for axis in 'xy':
            goal=p['inner'][axis]+(p['outer'][axis]-p['inner'][axis])*ratio
            assert abs(goal-p[axis])<.001,("not inside convex rail corridor",p)
    metrics={lane:{"raw_pct":round(v["raw"]*100/v["count"],1),
                     "near_pct":round(v["near"]*100/v["count"],1),
                     "sample":v["count"]} for lane,v in counts.items()}
    print("GREEN_CORRIDOR_SOURCE_PIXEL_AUDIT "+json.dumps({"lanes":metrics,"bad_first":worst[:35],
      "total":len(pts),"not_green_near":len(worst)},separators=(",",":")))
    overall=sum(v["near"] for v in counts.values())/len(pts)
    if overall<.80:raise AssertionError("too few projected horse points inside original green turf: "+str(overall))
    if min(v['near']/v['count'] for v in counts.values())<.60:
        raise AssertionError("some lanes appear outside turf band: "+str(metrics))
    print("PASS_LAB_KYOTO_ACTUAL_ORIGINAL_GREEN_TURF_PIXELS",round(overall*100,2))
if __name__=="__main__":main()
