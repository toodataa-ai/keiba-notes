#!/usr/bin/env python3
"""LAB image-rail registration, v1. Not a race physics model.

Read the *linked* original Umapot JPEG in CI and extract the green turf band
at each 5m station on a course-specific coarse registration. Store only
derived numeric rail coordinates, never a copy of the copyrighted image.

The coarse registration chooses WHICH circuit at intersections. Every
subsequent lateral horse position is obtained automatically between traced
INNER and OUTER green edges, not by per-distance horse display nudges.
"""
import argparse
import io
import json
import math
import subprocess
import urllib.request
from statistics import median
from PIL import Image

IMAGE_URL = "https://umapot.com/data/powerpoint/kyoto_couse/kyoto_couse_1.jpg"
COURSE_ID = "kyoto_turf_inner_2000"
DISTANCE = 2000
STEP = 5
JAVASCRIPT = r"""
const fs=require('fs'),vm=require('vm'),w={},document={getElementById:()=>null,querySelector:()=>null};
for(const p of ['race-course-geometry-v1.js','race-umapot-overlay-v1.js']){
 vm.runInNewContext(fs.readFileSync('docs/lab/'+p,'utf8'),
   {window:w,globalThis:w,document},{filename:p});
}
const c=w.RaceCourseGeometry.get('kyoto_turf_inner_2000');
const rows=[];
for(let d=0;d<=2000;d+=5){
 const p=w.RaceUmapotOverlay.point(c,d,0);
 const b=w.RaceUmapotOverlay.point(c,Math.max(0,d-.3),0);
 const a=w.RaceUmapotOverlay.point(c,Math.min(2000,d+.3),0);
 const len=Math.hypot(a.x-b.x,a.y-b.y)||1;
 rows.push({d,cx:p.x,cy:p.y,nx:-(a.y-b.y)/len,ny:(a.x-b.x)/len});
}
process.stdout.write(JSON.stringify(rows));
"""

def green(rgb):
    r,g,b=rgb[:3]
    return g>105 and g>r*1.38 and g>b*1.17 and r<135 and b<150

def get_runs(im, point):
    runs=[]
    cells=[]
    for offset in range(-52,53):
        x=int(round(point["cx"]+point["nx"]*offset))
        y=int(round(point["cy"]+point["ny"]*offset))
        inside=0<=x<im.width and 0<=y<im.height
        cells.append((offset, green(im.getpixel((x,y))) if inside else False))
    start=None
    for offset,on in cells+[(53,False)]:
        if on and start is None:start=offset
        if not on and start is not None:
            if offset-start>=4:runs.append((start,offset-1))
            start=None
    return runs

def select(runs):
    runs=[(a,b) for a,b in runs if b-a>=7]
    # Only choose a green stripe close to the already-registered circuit.
    # A second circuit behind a white divider must not be mistaken for this one.
    ranked=sorted(runs,key=lambda x:(max(0,x[0]-2,-x[1]-2),
                         abs((x[0]+x[1])/2),-min(30,x[1]-x[0])))
    return ranked[0] if ranked and max(0,ranked[0][0]-2,-ranked[0][1]-2)<=17 else None

def nearest_clean(rows, i):
    good=[(abs(j-i),j) for j,r in enumerate(rows) if r.get("raw") is not None]
    if not good:raise ValueError("no green rail at any station")
    return sorted(good)[0][1]

def fill_gaps(rows):
    good=[i for i,row in enumerate(rows) if row["raw"] is not None]
    if len(good)<len(rows)*.65:raise ValueError("green extraction confidence too low: "+str(len(good)))
    for i,row in enumerate(rows):
        if row["raw"] is not None:continue
        lo=max((x for x in good if x<i),default=None)
        hi=min((x for x in good if x>i),default=None)
        if lo is None or hi is None:row["raw"]=rows[nearest_clean(rows,i)]["raw"]
        else:
            z=(i-lo)/(hi-lo)
            row["raw"]=[rows[lo]["raw"][k]*(1-z)+rows[hi]["raw"][k]*z for k in (0,1)]
    return good

def smooth(rows):
    # Median filter then five-station moving mean on cross-sectional EXTENTS,
    # not 2D coordinates; avoid changing the traced course's direction.
    for k in range(2):
        m=[]
        for i,row in enumerate(rows):
            neighbors=[rows[j]["raw"][k] for j in range(max(0,i-3),min(len(rows),i+4))]
            m.append(median(neighbors))
        for i,row in enumerate(rows):row.setdefault("med",[]).append(m[i])
    for i,row in enumerate(rows):
        bounds=[sum(rows[j]["med"][k] for j in range(max(0,i-2),min(len(rows),i+3)))/
           len(range(max(0,i-2),min(len(rows),i+3))) for k in (0,1)]
        row["edge"]=[round(bounds[0],3),round(bounds[1],3)]

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--image",default=None)
    cli.add_argument("--output",default=None)
    cli.add_argument("--log-json",action="store_true")
    args=cli.parse_args()
    if args.image:
        im=Image.open(args.image).convert("RGB")
    else:
        req=urllib.request.Request(IMAGE_URL,headers={"User-Agent":"Mozilla/5.0 (LAB geometry validation)"})
        with urllib.request.urlopen(req,timeout=35) as http:im=Image.open(io.BytesIO(http.read())).convert("RGB")
    if im.size!=(620,430):raise ValueError("source illustration image dimensions changed: "+str(im.size))
    stations=json.loads(subprocess.check_output(["node","-e",JAVASCRIPT],text=True))
    for p in stations:
        p["runs"]=get_runs(im,p)
        p["raw"]=select(p["runs"])
    confident=fill_gaps(stations)
    smooth(stations)
    # Assume the inner direction is the RIGHT normal of course travel in
    # bitmap coordinates. The derived inner edge is high-normal; outer is low.
    # At each station both edges must be traced from the SAME turf stripe.
    print("TURF_RAIL_SAMPLE_PRECHECK "+json.dumps([
      {"d":p["d"],"green":p["runs"],"edge":p["edge"]}
      for p in stations if p["d"] in (0,100,310,530,720,900,1270,1435,1670,1900,2000)
    ],separators=(",",":")))
    widths=[]
    for p in stations:
        outer,inner=p["edge"]
        if not 4<inner-outer<65:raise ValueError("unphysical turf band width at "+str(p["d"])+": "+str(p["edge"]))
        widths.append(inner-outer)
    outcome={
      "schema_version":"lab-turf-rail-v1",
      "course_id":COURSE_ID,
      "source_url":IMAGE_URL,
      "image_size":[620,430],
      "sampling_m":STEP,
      "source_color_method":"green-stripe-nearest-registered-circuit",
      "max_lane_physical_m":1.8,
      "source_not_embedded":True,
      "rail_offsets":[[int(p["d"]),*p["edge"]] for p in stations]
    }
    diagnostics={"stations":len(stations),"observed":len(confident),
      "inferred":len(stations)-len(confident),
      "min_width_px":round(min(widths),2),"max_width_px":round(max(widths),2),
      "sample":[{"d":p["d"],"center":[round(p["cx"],1),round(p["cy"],1)],
        "edge":p["edge"],"runs":p["runs"]}
          for p in stations if p["d"] in (0,100,210,308.7,310,530,720,900,1270,1435,1670,1900,2000)]}
    print("TURF_RAIL_EXTRACT_DIAGNOSTICS "+json.dumps(diagnostics,ensure_ascii=False,separators=(",",":")))
    if args.output:
        with open(args.output,"w",encoding="utf8") as f:json.dump(outcome,f,ensure_ascii=False,separators=(",",":"))
    if args.log_json:print("TURF_RAIL_EXTRACT_DATA "+json.dumps(outcome,ensure_ascii=False,separators=(",",":")))
    print("PASS_LAB_DERIVED_GREEN_RAIL_GEOMETRY",len(confident),len(stations))
if __name__=="__main__":main()
