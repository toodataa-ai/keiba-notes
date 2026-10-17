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
  'race-broadcast-map-v1.js']){
 vm.runInNewContext(fs.readFileSync(base+name,'utf8'),{
  window:sandbox,globalThis:sandbox,document:doc
 },{filename:name});
}
const map=sandbox.RaceSimBroadcastMap,overlay=sandbox.RaceUmapotOverlay;
const profile=sandbox.RaceCourseGeometry.get('kyoto_turf_inner_2000');
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
   assert.ok(view.zoom>1&&view.zoom<6);
 }
}
const operations=[];
const ctx={
 fillStyle:null,strokeStyle:null,lineWidth:0,imageSmoothingEnabled:true,
 clearRect:(...args)=>operations.push(['clear',...args]),
 fillRect:(...args)=>operations.push(['fill',...args]),
 save:()=>operations.push(['save']),restore:()=>operations.push(['restore']),
 translate:(...args)=>operations.push(['translate',...args]),
 scale:(...args)=>operations.push(['scale',...args]),
 drawImage:(...args)=>operations.push(['image',...args]),
 beginPath:()=>operations.push(['path']),
 moveTo:()=>{},lineTo:()=>{},stroke:()=>{},
 setLineDash:()=>{}
};
const img={complete:true,naturalWidth:620,naturalHeight:430,src:'https://umapot.com/data/powerpoint/kyoto_couse/kyoto_couse_1.jpg'};
const state={distance:2000,leadingNo:1,horses:[{number:1,d:800,lane:0,finished:false}]};
const markers=[];
const output=map.draw({ctx,canvas:{width:1000,height:730},image:img,state,
 race:{course_id:profile.id,field_size:1},course:profile,overlay,
 focusNo:1,paintNumber:(context,n,x,y,scale)=>markers.push({n,x,y,scale}),renderedWidth:390});
assert.equal(output.ready,true);
const imageCalls=operations.filter(x=>x[0]==='image');
assert.equal(imageCalls.length,1);
assert.equal(imageCalls[0][1],img,'must draw exact existing external HTML image');
assert.deepEqual(Array.from(imageCalls[0].slice(2)),[0,0,620,430],'original aspect and bytes unchanged');
const coords=overlay.point(profile,800,0);
assert.equal(output.points[0].x,coords.x);
assert.equal(output.points[0].y,coords.y);
assert.equal(markers.length,1);
assert.ok(Math.hypot(markers[0].x-500,markers[0].y-365)<1e-9);
assert.equal(operations.filter(x=>x[0]==='scale').length,1);
assert.equal(operations.filter(x=>x[0]==='translate').length,2);
const notReady=map.draw({...{
 ctx,canvas:{width:1000,height:730},image:{complete:false},state,
 race:{course_id:profile.id,field_size:1},course:profile,overlay,
 focusNo:1,paintNumber:()=>{},renderedWidth:390
}});
assert.equal(notReady.ready,false);
assert.equal(operations.filter(x=>x[0]==='image').length,1,'do not use substitute geometry');
const html=fs.readFileSync(base+'race-simulator.html','utf8');
const sim=fs.readFileSync(base+'race-simulator.js','utf8');
assert.ok(html.includes('race-broadcast-map-v1.js?v=20261018-47'));
assert.ok(sim.includes('RaceSimBroadcastMap.draw({'));
assert.ok(sim.indexOf('RaceSimBroadcastMap.draw({')<sim.indexOf('if(state.goalCamera){'),'no separate finish cut for Kyoto');
assert.ok(!sim.includes("ctx.rotate("),'do not rotate original bitmap');
console.log('PASS_LAB_KYOTO_SHARED_IMAGE_BROADCAST_17_STATIONS_2_VIEWPORTS_SINGLE_PIXEL_COORDINATE');
