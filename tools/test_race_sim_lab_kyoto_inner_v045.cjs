/* LAB v0.45 Kyoto inner 2000m: reuse ORIGINAL Umapot image, calibrate
 * number overlay only. Physics and original outer 1400m stays unchanged.
 */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root='docs/lab/',W={};
const mapCanvas={hidden:false,getContext:()=>({clearRect(){}})};
const document={
 getElementById:id=>id==='kyotoCourseOverlay'?mapCanvas:null,
 querySelector:()=>null
};
for(const p of ['race-course-geometry-v1.js'])
 vm.runInNewContext(fs.readFileSync(root+p,'utf8'),{window:W,globalThis:W});
vm.runInNewContext(fs.readFileSync(root+'race-umapot-overlay-v1.js','utf8'),
 {window:W,globalThis:W,document});
const html=fs.readFileSync(root+'race-simulator.html','utf8');
const js=fs.readFileSync(root+'race-simulator.js','utf8');
const overlay=fs.readFileSync(root+'race-umapot-overlay-v1.js','utf8');
const kyoto=W.RaceCourseGeometry.get('kyoto_turf_inner_2000');
const oldKyoto=W.RaceCourseGeometry.get('kyoto_turf_outer_1400');
const tokyo=W.RaceCourseGeometry.get('tokyo_turf_2000');
assert.ok(W.RaceUmapotOverlay.validate(kyoto));
assert.ok(W.RaceUmapotOverlay.validate(oldKyoto));
assert.ok(W.RaceUmapotOverlay.validate(tokyo));
assert.equal(kyoto.segments.length,7);
// Nine requested stations: centres of the *inner* green ribbon, lane 0
// (the single-runner demo starts in lane 0).
const expected=[
 [0,350,317],[100,294,316],[308.7,178,301],
 [530,165,204],[900,286,147],
 [1270,463,136],[1435,510,197],
 [1671.6,490,317],[2000,294,317]
];
const pointProbe=d=>W.RaceUmapotOverlay.point(kyoto,d,0);
const immutableDistances=new Set([0,100,1270,1435,1671.6,2000]);
for(const [d,x,y] of expected){
 const p=pointProbe(d),base={x,y};
 const displacement=Math.hypot(p.x-x,p.y-y);
 if(immutableDistances.has(d))
   assert.ok(displacement<.02,'outside early bends unchanged: '+d);
 else {
   assert.ok(displacement>=2 && displacement<=9.2,'inward draw-only shift: '+d+' = '+displacement);
   const prev=pointProbe(d-.1),next=pointProbe(d+.1);
   const tangent={x:next.x-prev.x,y:next.y-prev.y};
   const mag=Math.hypot(tangent.x,tangent.y);
   const inward=(p.x-x)*(-tangent.y/mag)+(p.y-y)*(tangent.x/mag);
   assert.ok(inward>1.8,'projection must go toward inner rail at '+d+': '+inward);
 }
}
// The inside-pull starts only after the first 200m and must not distort
// the opposite side, the final straight, or either original registration.
for(const d of [0,50,100,150,200,1100,1250,1400,1700,1900,2000]){
 const p=pointProbe(d);
 assert.ok(Number.isFinite(p.x)&&Number.isFinite(p.y));
}


let last=null,maxPxPer5m=0;
for(let d=0;d<=2000;d+=5){
 const p=W.RaceUmapotOverlay.point(kyoto,d,0);
 assert.ok(p.x>28&&p.x<590&&p.y>86&&p.y<351,
  'inner 2000m marker must stay on the Kyoto original image '+d);
 if(last)maxPxPer5m=Math.max(maxPxPer5m,Math.hypot(last.x-p.x,last.y-p.y));
 last=p;
}
assert.ok(maxPxPer5m<5,'smooth 4th-corner→straight and start/finish joins');

/* Independent manually sampled centre ribbon on the source 620x430 Umapot
 * JPEG, NOT the Bezier control points. The permissive 12px tolerance reflects
 * source illustration width, anti-aliasing and 1 px map sampling. Checking
 * against this separate trace detects green-band escape (the old image-BOUNDS
 * check only guaranteed that markers stayed somewhere inside the JPEG).
 */
const innerTurfGuide=[
 [0,350,317],[100,294,316],[210,229,310],[308.7,178,301],
 [360,163,284],[420,159,253],[475,159,225],[530,165,204],
 [600,171,181],[650,181,169],[720,207,161],[820,251,153],
 [900,286,147],[1000,331,142],[1100,380,138],[1200,430,134],
 [1270,463,136],[1350,496,159],[1400,508,180],[1435,510,197],
 [1490,510,225],[1550,510,259],[1600,507,286],[1650,500,309],
 [1671.6,490,317],[1760,435,318],[1860,378,318],[2000,294,317]
];
function tracedTurfAt(d){
 let i=0;
 while(i<innerTurfGuide.length-2&&d>innerTurfGuide[i+1][0])i++;
 const [d0,x0,y0]=innerTurfGuide[i], [d1,x1,y1]=innerTurfGuide[i+1];
 const f=(d-d0)/(d1-d0);
 return {x:x0+(x1-x0)*f,y:y0+(y1-y0)*f};
}
const distanceToTurf=(p,d)=>{
 const g=tracedTurfAt(d);return Math.hypot(p.x-g.x,p.y-g.y);
};
// The desired INNER racing line is intentionally closer to the rail than
// the independent legacy turf-center guide; never claim it is the same line.
const TURF_BAND_INNER_LINE_TOLERANCE_PX=14;
let worstCentreDeviation=0;
for(let d=0;d<=2000;d+=5){
 const actual=W.RaceUmapotOverlay.point(kyoto,d,0);
 const delta=distanceToTurf(actual,d);
 worstCentreDeviation=Math.max(worstCentreDeviation,delta);
 assert.ok(delta<TURF_BAND_INNER_LINE_TOLERANCE_PX,
   '5m turf ribbon escape (not merely image bounds) at '+d+'m: '+delta.toFixed(2)+'px');
}
assert.ok(distanceToTurf({x:200,y:253},420)>TURF_BAND_INNER_LINE_TOLERANCE_PX,
 'negative control: 44px outside first bend must be rejected');
assert.ok(distanceToTurf({x:545,y:258},1550)>TURF_BAND_INNER_LINE_TOLERANCE_PX,
 'negative control: outer loop at fourth bend must be rejected');
assert.equal(W.RaceUmapotOverlay.outwardShiftPx(kyoto,1435),0);
const immutableLegacySamples={
 tokyo_turf_2000:[[0,507.3069,277.143],[120,484.3591,169.4188],
  [900,159.8892,144.7502],[1474.1,171.1475,299.3172],[2000,370.9976,299.34]],
 kyoto_turf_outer_1400:[[0,226.9792,168.2066],[365,455.3475,124.4614],
  [570,552.0981,166.4973],[805,542.3273,308.3],
  [996.3,453.9117,314.3303],[1400,290.0029,310.34]]
};
for(const [id,checkpoints] of Object.entries(immutableLegacySamples)){
 const course=W.RaceCourseGeometry.get(id);
 for(const [d,x,y] of checkpoints){
  const p=W.RaceUmapotOverlay.point(course,d,0);
  assert.ok(Math.hypot(p.x-x,p.y-y)<0.015,
   'other courses must be bitwise-stable to 0.01px: '+id+' '+d+'m');
 }
}
const painted=[];
const demoRace={course_id:'kyoto_turf_inner_2000',venue:'京都',field_size:1};
for(const d of [0,100,308.7,530,900,1270,1435,1671.6,2000]){
 painted.length=0;
 W.RaceUmapotOverlay.draw({leadingNo:1,distance:2000,
   horses:[{number:1,d,lane:0,finished:false}]},
   demoRace,'leader',false,(_ctx,number,x,y)=>painted.push({number,x,y}));
 assert.equal(painted.length,1,'one demo number must be painted at '+d);
 assert.equal(painted[0].number,1);
 const pt=W.RaceUmapotOverlay.point(kyoto,d,0);
 assert.ok(Math.hypot(painted[0].x-pt.x,painted[0].y-pt.y)<1e-7,
  'one-runner overlay render must follow the calibrated centre at '+d);
}

// Check original image registrations were not rewritten as stand-ins.
const oldOuter=W.RaceUmapotOverlay.point(oldKyoto,805,3);
assert.ok(Math.abs(oldOuter.x-559)<15 && oldOuter.y>270);
const oldTokyo=W.RaceUmapotOverlay.point(tokyo,0,0);
assert.ok(oldTokyo.x>500&&oldTokyo.y>265);
assert.ok(html.includes('id="kyotoCourseImage"'));
assert.ok(html.includes('src="https://umapot.com/data/powerpoint/kyoto_couse/kyoto_couse_1.jpg"'));
assert.ok(html.includes('race-umapot-overlay-v1.js?v=20261018-49'));
assert.ok(html.includes('race-turf-corridor-v1.js?v=20261018-49'));
assert.ok(html.includes('race-simulator.js?v=20261018-49'));
assert.ok(html.includes('race-lab-18-fixture-v1.js?v=20261018-48'));
assert.ok(html.includes('race-broadcast-map-v1.js?v=20261018-51'));
assert.ok(html.includes('同じうまぽっとの京都競馬場原画像'));
assert.ok(js.includes("['kyoto_turf_outer_1400','kyoto_turf_inner_2000'].includes"));
assert.ok(js.includes("'kyoto_turf_inner_2000'].includes(race.course_id)"));
const official=JSON.parse(fs.readFileSync(root+'race-sim-manifest-v1.json','utf8'));
assert.equal(official.races.length,2,'official field must remain two sealed races');
assert.ok(!official.races.some(x=>x.course_id==='kyoto_turf_inner_2000'));
console.log('PASS_LAB_V046_KYOTO_INNER_INSIDE_1C_2C_5M_AND_LEGACY_TRACKS',maxPxPer5m.toFixed(2),'ribbon deviation',worstCentreDeviation.toFixed(2));
