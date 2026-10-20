/* Independent LAB expansion pilot. Original publisher SVG is not redrawn.
 * Shared engine, frame interpolation, safe green mask and clock modules.
 * Unsafe or unknown course: fail closed, not an invented run. */
(function(){'use strict';
const $=id=>document.getElementById(id);
const courseId='kyoto_turf_outer_1400',course=RaceCourseGeometry.get(courseId);
const original=RaceLab18Fixture,base=original.entry();
const race={...base,id:'outer-1400-hypothetical-18',
 course_id:courseId,distance_m:course.distance_m,turn:course.turn,
 venue:course.venue,field_size:18,horses:original.horses(),
 race:'京都芝1400m外回り・架空18頭'};
const STEP=RaceFrameInterpolator.STEP_SECONDS;
let route=null,nativeCamera=null,engine=null,playing=false,last=0,acc=0,prev=null,curr=null;
let shown=[],camera=null,lastCameraTime=null,lastPaint=0,finishElapsed=0,blocked=null;
const cache={signature:''};
const markerVisibility=RaceMarkerVisibility.create({lockAfterFirstPlan:true});
const broadcastPose=RaceBroadcastPoseFilter.create();
const cameraPose=RaceBroadcastPoseFilter.create();
const fixedFinish=RaceFinishFixedCamera.create({venueLabel:'KYOTO',turn:course.turn,maxLane:14,goalPostSide:'inner'});
let visualMetrics=null,lastFinishView=null,lastSmoothedPositions=[],lastNativeView=null;
let lastStartGate={overview:false,broadcast:false};

const colors=[['#fffdf5','#161616'],['#15191f','#fff'],
 ['#d9142f','#fff'],['#164bb8','#fff'],['#ffde30','#171717'],
 ['#1d8c49','#fff'],['#f9811f','#161616'],['#f4a1c5','#161616']];
function numbers(ctx,num,x,y,scale=.8,focus=false){
 const i=num<=12?Math.floor((num-1)/2):num<=15?6:7;
 const r=13.5*scale,col=colors[i];ctx.save();
 ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=col[0];ctx.fill();
 ctx.lineWidth=(focus?3.4:2.1)*scale;ctx.strokeStyle=focus?'#e9af30':'#26362f';ctx.stroke();
 ctx.fillStyle=col[1];ctx.font='900 '+((num>9?16:18)*scale)+'px Arial, sans-serif';
 ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(num),x,y);ctx.restore();
}
function surface(id){
 const el=$(id),rect=el.getBoundingClientRect(),w=Math.max(1,rect.width),
 h=Math.max(1,rect.height),dpr=Math.min(2.5,devicePixelRatio||1);
 const cw=Math.round(w*dpr),ch=Math.round(h*dpr);
 if(el.width!==cw||el.height!==ch){el.width=cw;el.height=ch}
 const ctx=el.getContext('2d');ctx.setTransform(cw/w,0,0,ch/h,0,0);
 ctx.clearRect(0,0,w,h);return {ctx,w,h};
}
function elements(){return{clock:$('clock'),split:$('splitTime'),splitLabel:$('splitLabel'),
 banner:$('finishBanner'),heading:$('finishHeading'),podium:$('finishPodium'),
 results:$('fullResults'),rows:$('resultsBody')}}
function capture(){return RaceFrameInterpolator.capture(engine.state.horses)}
function reset(){
 engine=RaceSimEngine.create(race,{seed:2026,bias:'neutral'});
 prev=curr=capture();acc=0;last=0;playing=false;camera=null;lastCameraTime=null;shown=[];
 finishElapsed=0;cache.signature='';markerVisibility.reset();
 broadcastPose.reset();cameraPose.reset();fixedFinish.reset();visualMetrics=null;lastFinishView=null;
 lastSmoothedPositions=[];lastNativeView=null;
 lastStartGate={overview:false,broadcast:false};nativeCamera?.reset();$('goalCamera').hidden=true;$('goalCamera').style.opacity='0';
 $('resultsBody').replaceChildren();
 $('fullResults').hidden=true;$('startBtn').textContent='▶ スタート';draw();
}
function fail(reason){
 blocked=String(reason);playing=false;$('startBtn').disabled=true;
 $('sourceAudit').classList.add('blocked');
 $('sourceAudit').textContent='安全ゲートで停止しました: '+blocked;
}
async function load(){
 if(blocked)return;
 try{
  const source=RaceLabCourseRollout.get(courseId);
  if(!source.svgGreenPathIndices?.length)throw Error('OUTER_PATH_TOPOLOGY_NOT_REGISTERED');
  const response=await fetch($('realCourseImage').currentSrc,{cache:'no-store'});
  if(!response.ok)throw Error('ORIGINAL_SVG_FETCH_FAILED_'+response.status);
  const sourceSvgText=await response.text();
  route=RaceLabSourceMask.build({image:$('realCourseImage'),course,
   guide:RaceUmapotOverlay.legacyPoint,
   projection:RaceSafeRailProjection,geometry:RaceCourseImageGeometry,
   sourceSvgText,sourcePathIndices:source.svgGreenPathIndices});
  RaceLabCourseRollout.assertCanAnimate(courseId,course,route);
  // Use only the original image and certified per-horse course geometry.
  // Never sample/unwrap the image into a fabricated uniformly green TV strip.
  nativeCamera=RaceNativeBroadcast.create();
  $('sourceAudit').textContent='原図の芝帯監査 '+route.report.checked+
   '地点 合格／外回り元SVGパス#'+route.report.sourcePathIndices.join(',')+
   ' 固定・芝帯外0・最大1m移動'+route.report.maxProjectedStep.toFixed(2)+'px／原図不変';
  $('startBtn').disabled=false;reset();
 }catch(e){fail(e)}
}
function points(){
 if(!engine)return[];
 if(playing&&!engine.state.finished)return RaceFrameInterpolator.interpolate(
   prev,curr,acc/STEP).map(h=>({...h,...route.point(h.d,h.lane)}));
 if(engine.state.finished){
  // Identical display-only coast used in LAB v26. Physics has ended.
  const portion=Math.max(0,Math.min(1,finishElapsed/3.2));
  const coast=6*(1-(1-portion)**3);
  return engine.state.horses.map(h=>{
   const d=(h.displayD??h.d)+coast;
   return {number:h.number,d,lane:h.lane,...route.point(d,h.lane)};
  });
 }
 if(shown.length)return shown;
 return engine.state.horses.map(h=>({number:h.number,d:h.displayD??h.d,
  lane:h.lane,...route.point(h.displayD??h.d,h.lane)}));
}
function draw(){
 if(!route||!engine)return;
 const state=engine.state,items=points();shown=items;
 const b=surface('broadcast'),m=surface('overview');
 const leaderD=Math.max(...items.map(h=>h.d));
 // The same physical clock drives visual offsets AND camera smoothing.
 // Repainting, pausing, or a faster display cannot advance their animation.
 const visualTime=state.finished?state.t:
   Math.max(0,state.t-STEP+Math.min(STEP,acc));
 const straightEntry=course.distance_m-course.straight_m;
 if(!nativeCamera)throw Error('ORIGINAL_SVG_CAMERA_NOT_READY');
 const originalSvg=$('liveCourseImage');
 if(!originalSvg.complete||!originalSvg.naturalWidth)
  throw Error('ORIGINAL_SVG_IMAGE_NOT_LOADED');
 originalSvg.style.visibility='hidden';
 originalSvg.style.transform='none';
 // Exact same original course image, and original source x/y horse positions.
 // No independent track transformations and no rebuilt green background.
 lastSmoothedPositions=items.map(p=>({
  number:p.number,x:p.x,y:p.y,rawX:p.x,rawY:p.y
 }));
 lastNativeView=nativeCamera.frame({ctx:b.ctx,image:originalSvg,
  points:items,width:b.w,height:b.h,timeSeconds:visualTime,
  paintNumber:numbers,leaderNo:state.leadingNo,
  decorate:(ctx,{left,top,zoom})=>{
   const gate=RaceTracksideFurniture.startGate(ctx,{
    point:route.point,maxLane:14,leaderD,
    project:p=>({x:left+p.x*zoom,y:top+p.y*zoom}),
    overview:false,showUntilM:22
   });
   lastStartGate.broadcast=!!gate;
  },
  labelLayout:anchors=>markerVisibility.layout(anchors,{
   timeSeconds:visualTime,
   normalAt:h=>{
    const q=route.point(Math.max(0,h.d-2),h.lane),
     z=route.point(Math.min(course.distance_m,h.d+2),h.lane);
    return {x:-(z.y-q.y),y:z.x-q.x};
   }
  })
 });
 visualMetrics=markerVisibility.metrics();
 lastStartGate.overview=!!RaceTracksideFurniture.startGate(m.ctx,{
  point:route.point,maxLane:14,leaderD,
  project:p=>({x:p.x*m.w/620,y:p.y*m.h/430}),
  overview:true,showUntilM:22
 });
 for(const h of items)numbers(m.ctx,h.number,h.x*m.w/620,h.y*m.h/430,.48,
  h.number===state.leadingNo);
 // The last segment is a real STATIC camera. The goal arch, winning
 // line, grass and rails are rendered ONCE to a cached bitmap. Individual
 // horse numbers move over that bitmap strictly by the race engine's d/lane.
 // Do not track the pack, shift the goal post or rescale during the finish.
 const leaderPosition=Math.max(...items.map(h=>h.d));
 const remaining=course.distance_m-leaderPosition;
 if(remaining<=RaceFinishFixedCamera.transitionRemainingM){
  const finishCanvas=$('goalCamera');
  finishCanvas.hidden=false;
  const blend=Math.max(0,Math.min(1,
   (RaceFinishFixedCamera.transitionRemainingM-remaining)/4));
  finishCanvas.style.opacity=String(blend);
  lastFinishView=fixedFinish.render({canvas:finishCanvas,points:items,
   distance:course.distance_m,paintNumber:numbers,focusedNo:state.leadingNo});
 }else{
  $('goalCamera').hidden=true;
  $('goalCamera').style.opacity='0';
  lastFinishView=null;
 }
 RaceBroadcastHud.render(state,elements(),cache);
 $('progress').textContent=Math.round(state.leader)+'m / '+course.distance_m+'m';
 $('section').textContent=state.leader>=straightEntry?
  '最後の直線':'京都芝1400m外回り・原図追従';
}
function tick(now){
 if(!last)last=now;
 const delta=Math.max(0,Math.min(.18,(now-last)/1000));last=now;
 if(playing&&engine&&!blocked){
  if(!engine.state.finished){
   acc+=delta*Number($('speed').value);
   let i=0;while(acc>=STEP&&i++<12&&!engine.state.finished){
    prev=curr;engine.step(STEP);curr=capture();acc-=STEP;
   }
  }else{finishElapsed+=delta;if(finishElapsed>=3.2){
   playing=false;$('startBtn').textContent='▶ 再スタート'}}
  if(now-lastPaint>14){draw();lastPaint=now}
 }
 requestAnimationFrame(tick);
}
function setup(){
 $('startBtn').disabled=true;
 $('startBtn').addEventListener('click',()=>{
  if(!route||blocked)return;
  if(engine.state.finished)reset();
  playing=true;$('startBtn').textContent='▶ 再生中';
 });
 $('pauseBtn').addEventListener('click',()=>{playing=false;$('startBtn').textContent='▶ 再開'});
 $('resetBtn').addEventListener('click',()=>{if(!blocked)reset()});
 $('realCourseImage').addEventListener('load',load);
 $('realCourseImage').addEventListener('error',()=>fail('ORIGINAL_SVG_UNAVAILABLE'));
 if($('realCourseImage').complete&&$('realCourseImage').naturalWidth)load();
 addEventListener('resize',()=>{camera=null;draw()});
 requestAnimationFrame(tick);
}
window.CrossCoursePilot=Object.freeze({
 state:()=>engine?.state,routeReport:()=>route?.report,
 // Read-only instrumentation for the common source-curve continuity audit.
 sourcePoint:(d,lane)=>{if(!route)throw Error('LAB_SOURCE_NOT_READY');
  return route.point(d,lane)},
 visualMetrics:()=>visualMetrics,
 broadcastPoints:()=>lastSmoothedPositions,
 nativeCamera:()=>lastNativeView,
 distanceCamera:()=>null,
 finishView:()=>lastFinishView,
 startGate:()=>({...lastStartGate}),
 previewFrame:()=>{if(!engine||blocked)throw Error('LAB_NOT_READY');draw();return visualMetrics},
 // Course-neutral LAB-only check: move the same physical race to a distance
 // for reproducible corner screenshots; this never rewrites race geometry.
 seekTo(distance){
  if(!route||!engine||blocked)throw Error('LAB_COURSE_NOT_READY');
  const requested=Math.max(0,Math.min(course.distance_m-2,Number(distance)||0));
  playing=false;let i=0;
  while(engine.state.leader<requested&&!engine.state.finished&&i++<2500)engine.step(STEP);
  prev=curr=capture();acc=0;shown=[];camera=null;lastCameraTime=null;
  markerVisibility.reset();broadcastPose.reset();cameraPose.reset();
  nativeCamera?.reset();draw();
  return engine.state.leader;
 },
 inspect:()=>({courseId,blocked,ready:!!engine,playing,fieldSize:engine?.state.horses.length,
  source:RaceLabCourseRollout.get(courseId).svg,
 sharedVisualMode:true,markerTimeDriven:true,atomicSvgCanvas:true,
 ribbonCameraActive:false,nativeOriginalSvg:!!lastNativeView,
 visualCameraTime:lastCameraTime,
 finishCameraActive:!$('goalCamera').hidden,
 finishCameraThreshold:RaceFinishFixedCamera.transitionRemainingM,
 fixedFinishBackground:!!lastFinishView?.backgroundFixed,
 fixedFinishBackgroundBuilds:lastFinishView?.backgroundBuilds??0,
 goalBoardBeyondRail:lastFinishView?.boardOutsideRail??null,
 startGateShown:lastStartGate.overview,
 broadcastPoseMaxDrift:RaceBroadcastPoseFilter.sourceDeviationCap,
 visibilityMetrics:visualMetrics})
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);
else setup();
})();