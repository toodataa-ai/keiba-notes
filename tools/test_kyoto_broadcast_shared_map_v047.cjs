/* v0.47: Kyoto broadcast MUST be one camera onto original image
 * and same exact point source as transparent overview canvas. */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const base='docs/lab/';
const sandbox={};const doc={
 getElementById:()=>null,
 querySelector:()=>null
};
for(const name of ['race-course-geometry-v1.js','race-umapot-overlay-v1.js',
  'race-broadcast-map-v1.js','race-turf-corridor-v1.js']){
 vm.runInNewContext(fs.readFileSync(base+name,'utf8'),{
  window:sandbox,globalThis:sandbox,document:doc
 },{filename:name});
}
const map=sandbox.RaceSimBroadcastMap,overlay=sandbox.RaceUmapotOverlay;
const profile=sandbox.RaceCourseGeometry.get('kyoto_turf_inner_2000');
sandbox.RaceTurfCorridor.register(JSON.parse(fs.readFileSync(base+'race-turf-rails-kyoto-inner-2000-v1.json','utf8')));
assert.equal(map.supports({course_id:profile.id}),true);
assert.equal(map.supports({course_id:'tokyo_turf_2000'}),false);
assert.equal(map.width,620);assert.equal(map.height,430);
for(const d of [0,100,210,308.7,440,530,620,720,800,900,1000,1200,1270,1435,1671.6,1800,2000]){
 const state={distance:2000,leadingNo:1,horses:[{number:1,d,lane:0,finished:false}]};
 const actual=map.entries(state,profile,overlay);
 assert.equal(actual.length,1);
 const expected=overlay.point(profile,d,0);
 assert.ok(Math.hypot(actual[0].x-expected.x,actual[0].y-expected.y)<1e-9,'pixel same '+d);
 for(const [width,height,display] of [[1000,730,390],[1000,470,1000]]){
   const view=map.frame(actual,width,height,display,1);
   assert.equal(view.rotationRadians,0);
   const screen=map.screenPoint(actual[0],view);
   assert.ok(Math.hypot(screen.x-view.anchor.x,screen.y-view.anchor.y)<1e-8);
   assert.ok(view.zoom>=1.7&&view.zoom<=5.2);
   assert.equal(view.cameraMode,'kyoto-1400-like-group-framing');
 }
}

const operations=[];
const ctx={fillStyle:null,strokeStyle:null,lineWidth:0,
 clearRect:(...v)=>operations.push(['clear',...v]),
 fillRect:(...v)=>operations.push(['fillRect',...v]),
 save:()=>operations.push(['save']),restore:()=>operations.push(['restore']),
 translate:(...v)=>operations.push(['translate',...v]),scale:(...v)=>operations.push(['scale',...v]),
 drawImage:()=>{throw Error('BROADCAST_RASTER_MUST_NEVER_BE_SCALED')},
 beginPath:()=>operations.push(['begin']),
 moveTo:(...v)=>operations.push(['move',...v]),
 lineTo:(...v)=>operations.push(['line',...v]),
 quadraticCurveTo:(...v)=>operations.push(['quad',...v]),
 closePath:()=>operations.push(['close']),
 fill:(...v)=>operations.push(['fill',...v]),
 stroke:()=>operations.push(['stroke']),
 setLineDash:()=>{}
};
const state={distance:2000,leadingNo:1,horses:[{number:1,d:800,lane:0,finished:false}]};
const markers=[],image=null; // source image is only needed by the full overview
const out=map.draw({ctx,canvas:{width:1000,height:620},image,state,
 race:{course_id:profile.id,field_size:1},course:profile,overlay,
 focusNo:1,paintNumber:(c,n,x,y,size)=>markers.push({n,x,y,size}),renderedWidth:390});
assert.equal(out.ready,true);
assert.equal(out.renderMode,'smoothed-source-derived-vector-rails');
assert.equal(out.turfStations,401);
assert.equal(operations.filter(x=>x[0]==='fill').length,1,'one connected turf ribbon');
assert.equal(operations.filter(x=>x[0]==='stroke').length,2,'only inside/outside boundaries');
assert.ok(operations.filter(x=>x[0]==='quad').length>=800,'smooth vector interpolation');
assert.equal(markers.length,1);
// In CSS pixels 1.02x focused, rather than the former enormous 1.55x.
const cssScale=markers[0].size*390/1000;
assert.ok(cssScale>=1&&cssScale<=1.1,'modest one-runner label size '+cssScale);
assert.equal(operations.filter(x=>x[0]==='scale').length,1);
assert.equal(operations.filter(x=>x[0]==='translate').length,2);
const html=fs.readFileSync(base+'race-simulator.html','utf8');
const sim=fs.readFileSync(base+'race-simulator.js','utf8');
assert.ok(html.includes('race-broadcast-map-v1.js?v=20261018-52'));
assert.ok(html.includes('height="620"'));
assert.ok(html.includes('race-turf-corridor-v1.js?v=20261018-49'));
assert.ok(sim.includes('RaceSimBroadcastMap.draw({'));
assert.ok(sim.indexOf('RaceSimBroadcastMap.draw({')<sim.indexOf('if(state.goalCamera){'));
console.log('PASS_LAB_V050_SHARP_GREEN_RAIL_VECTOR_NO_LABELS_17_STATIONS_SHARED_COORDS');

const smooth=map.smoothTurfRails(profile,overlay);
let maxShift=0;
for(let i=0;i<smooth.length;i++){
 const raw=sandbox.RaceTurfCorridor.rails(profile,i*5,overlay.legacyPoint);
 for(const side of ['inner','outer']){
  maxShift=Math.max(maxShift,Math.hypot(
   smooth[i][side].x-raw[side].x,smooth[i][side].y-raw[side].y));
 }
}
assert.ok(maxShift<=6.00001,'smoothed turf cannot drift from source by more than 3 px');
console.log('PASS_V051_BOUNDARY_QUALITY_MAX_SHIFT_PX',maxShift.toFixed(2));
