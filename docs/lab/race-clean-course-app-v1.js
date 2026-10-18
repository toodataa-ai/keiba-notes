/* LAB v15: Kyoto1400 GOAL board camera at 80m, closer broadcast zoom and reasoned pack diagnostics.
 * Source bitmap is never redrawn as an approximate course. A browser-local,
 * fourfold high-quality resample is a display cache, not a new detailed source.
 * Only synthetic 18-horse data; no official prediction/odds/bets/PDF changes.
 */
(function(){'use strict';
const $=id=>document.getElementById(id);
const model=window.RaceCleanCourse;
const turf=window.RaceCleanTurf;
const fixture=window.RaceLab18Fixture;
const entries=fixture.horses();
const race={...fixture.entry(),horses:entries};
// Ported faithfully from working Kyoto 1400 RaceSimNumbers.marker.
const JRA_WAKU=Object.freeze([
 {name:'白',fill:'#fffdf5',text:'#111827',border:'#111827'},
 {name:'黒',fill:'#15191f',text:'#ffffff',border:'#f4f4f5'},
 {name:'赤',fill:'#d9142f',text:'#ffffff',border:'#fff4f4'},
 {name:'青',fill:'#164bb8',text:'#ffffff',border:'#f1f5ff'},
 {name:'黄',fill:'#ffde30',text:'#171717',border:'#35301c'},
 {name:'緑',fill:'#1d8c49',text:'#ffffff',border:'#edfff4'},
 {name:'橙',fill:'#f9811f',text:'#111827',border:'#422509'},
 {name:'桃',fill:'#f4a1c5',text:'#171717',border:'#542e3f'}
]);
function jraWaku(number,fieldSize=18){
 // Only the separately flagged one-runner course demonstration gets a
 // neutral white marker. Official 8–18 runner JRA waku validation is unchanged.
 
 if(!Number.isInteger(number)||!Number.isInteger(fieldSize)||
   fieldSize<8||fieldSize>18||number<1||number>fieldSize)
   throw Error('JRA_WAKU_FIELD_INVALID');
 const base=Math.floor(fieldSize/8),extra=fieldSize%8;
 let first=1;
 for(let i=0;i<8;i++){
   const n=base+(i>=8-extra?1:0);
   if(number<first+n)return {waku:i+1,...JRA_WAKU[i]};
   first+=n;
 }
 throw Error('JRA_WAKU_NOT_FOUND');
}
function raceNumberMarker(ctx,number,x,y,scale,focused=false,leading=false,fieldSize=18,passing=false){
 if(!Number.isInteger(number)||number<1||!Number.isFinite(x)||!Number.isFinite(y))
  throw Error('SIM_NUMBER_POSITION_INVALID');
 // Equal diameter for all horses. Focus uses the same circumference:
 // a gold stroke, without any larger marker or external gold halo.
 const radius=13.5*scale;
 const waku=jraWaku(number,fieldSize);
 ctx.save();
 ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);
 ctx.fillStyle=waku.fill;ctx.fill();
 ctx.lineWidth=(focused?3.4:2.1)*scale;
 ctx.strokeStyle=focused?'#e9af30':waku.border;
 ctx.stroke();
 if(focused){
   // The inner hairline keeps the original JRA bracket border recognizable.
   ctx.beginPath();ctx.arc(x,y,radius-2.5*scale,0,Math.PI*2);
   ctx.lineWidth=.8*scale;ctx.strokeStyle=waku.border;ctx.stroke();
 }
 if(passing){
   // A thin ring around the genuine crossing point; no position offset.
   ctx.beginPath();ctx.arc(x,y,radius+7*scale,0,Math.PI*2);
   ctx.lineWidth=2.6*scale;ctx.strokeStyle='#b6f3a0';ctx.stroke();
 }
 ctx.textAlign='center';ctx.textBaseline='middle';
 ctx.fillStyle=waku.text;
 ctx.font='900 '+(number>9?16:18)*scale+'px Arial, sans-serif';
 ctx.fillText(String(number),x,y+.4*scale);
 ctx.restore();
 return {number,x,y,waku:waku.waku};
}

function waku(no){const w=jraWaku(no,18);return {fill:w.fill,ink:w.text};}
let engine,playing=false,last=0,acc=0,renderStamp=0,focusNo='leader',
 lastCamera=null,lastLabelPositions=[],lastRenderedPoints=[],cameraRenderTime=0,
 visualLaneState=new Map(),visualRenderTime=null,
 finishSequenceActive=false,finishSequenceElapsedMs=0,finishSequenceDone=false;
const FINISH_SEQUENCE_MS=3200;
let vectorReady=false,originalError=false,turfReady=false,turfError=null,turfStats=null;
let lastGoalFrame=null;
const SOURCE_VECTOR='assets/kyoto-umapot-course-clean-v8.svg';
function reset(){
 engine=RaceSimEngine.create({...race,horses:fixture.horses()},{seed:2026,bias:'neutral'});
 playing=false;last=0;acc=0;lastCamera=null;lastRenderedPoints=[];
 cameraRenderTime=0;visualRenderTime=null;visualLaneState.clear();
 finishSequenceActive=false;finishSequenceElapsedMs=0;finishSequenceDone=false;
 const banner=$('finishBanner');if(banner)banner.hidden=true;
 $('startBtn').textContent='▶ スタート';
 paint();
}
function advanceTo(distance){
 reset();
 let i=0;
 while(engine.state.leader<distance&&!engine.state.finished&&i++<1500)engine.step(.12);
 // Seek is a jump in simulation time. Do NOT interpolate the camera from
 // the starting gate across 900 metres: it leaves every horse off-screen.
 lastCamera=null;cameraRenderTime=0;visualRenderTime=null;
 visualLaneState.clear();
 finishSequenceActive=false;finishSequenceElapsedMs=0;finishSequenceDone=false;
 const banner=$('finishBanner');if(banner)banner.hidden=true;
 paint();return engine.state;
}
function sizeCanvas(canvas){
 const rect=canvas.getBoundingClientRect();
 const w=Math.max(1,rect.width),h=Math.max(1,rect.height);
 const dpr=Math.min(2.5,Math.max(1,window.devicePixelRatio||1));
 const pxW=Math.round(w*dpr),pxH=Math.round(h*dpr);
 if(canvas.width!==pxW||canvas.height!==pxH){canvas.width=pxW;canvas.height=pxH}
 const ctx=canvas.getContext('2d');
 ctx.setTransform(pxW/w,0,0,pxH/h,0,0);
 ctx.clearRect(0,0,w,h);
 return {ctx,w,h};
}
function backdrop(camera){
 // The photo and canvas must share EXACTLY the same affine projection.
 // This transform crops the unchanged image; it never draws new rail shapes.
 const left=camera.cx-camera.x*camera.scale;
 const top=camera.cy-camera.y*camera.scale;
 const transform='translate('+left+'px,'+top+'px) scale('+camera.scale+')';
 for(const id of ['liveCourseImage']){
  const element=$(id);
  if(element)element.style.transform=transform;
 }
}
function sourceImageReady(img){
 // Crucial Safari/WebKit fix: a responsive SVG <img> can report its
 // layout-scaled naturalWidth (368x255 on iPhone), despite the exact
 // original file being 620x430. Pixel-equality wrongly blocked painting.
 // The source viewBox and intended 620:430 coordinate space are unchanged.
 return Boolean(img&&img.complete&&img.naturalWidth>0&&img.naturalHeight>0&&
  Math.abs(img.naturalWidth/img.naturalHeight-620/430)<.025&&
  img.getAttribute('src')===SOURCE_VECTOR);
}
function verifyVectorSource(){
 const a=$('realCourseImage'),b=$('liveCourseImage');
 const sourceLoaded=sourceImageReady(a);
 const broadcastLoaded=sourceImageReady(b);
 vectorReady=sourceLoaded&&broadcastLoaded;
 // Do not let an unrelated viewport's computed SVG naturalWidth prevent
 // loading. Calibrate from the image's scalable source viewBox instead.
 if(sourceLoaded&&!turfReady&&!turfError){
  try{turfStats=turf.create(a);turfReady=true;}
  catch(err){
   turfError=String(err);console.error('KYOTO_TURF_MASK_INIT',err);
   const note=document.querySelector('.source-credit');
   if(note)note.textContent='コース初期化に失敗しました: '+turfError;
  }
 }
 if(vectorReady)originalError=false;
}
function position(p,camera){
 return {x:camera.cx+(p.x-camera.x)*camera.scale,
         y:camera.cy+(p.y-camera.y)*camera.scale};
}
// For a crowd's leader camera, use SOFT race-order weights (no membership
// toggles when a horse crosses +/-80m or when the lead changes at the wire).
// The focal point can still follow an individually selected horse.
function cameraFor(points,w,h,chosen,autoLeader=true){
 let center=points.find(p=>p.number===chosen)||points[0];
 if(autoLeader){
  const leaderDistance=Math.max(...points.map(p=>p.d));
  let x=0,y=0,total=0;
  for(const p of points){
   const weight=Math.exp(Math.max(-25,(p.d-leaderDistance)/15));
   x+=p.x*weight;y+=p.y*weight;total+=weight;
  }
  center={x:x/total,y:y/total};
 }
 // Fix the optical zoom; the old density-based group bounds changed camera
 // magnification at every overtake and caused visible frame-to-frame shakes.
 return {x:center.x,y:center.y,cx:w*.54,cy:h*.51,
  // Tighter normal broadcast. Fixed across overtakes to prevent breathing.
  scale:w<540?8.8:9.7};
}
// At 4x playback, physics advances in 80ms simulation steps. A canvas drawn
// between steps used to alternate between a stationary and jumping position.
// Extrapolate ONLY visual positions over the unconsumed simulation accumulator
// and low-pass rapid physical LANE reversals; physics state stays immutable.
function displayPoints(state){
 if(state.finished&&finishSequenceActive){
  // Extend the drawn run-off gently after the virtual results are locked.
  // This is a display-only coast, not an extra RaceSimEngine step.
  const progress=Math.min(1,finishSequenceElapsedMs/FINISH_SEQUENCE_MS);
  const coast=6*(1-Math.pow(1-progress,3));
  return state.horses.map(h=>{
   const d=(h.displayD??h.d)+coast;
   return {number:h.number,d,lane:h.lane,
    ...turf.point(d,h.lane),finished:true};
  });
 }
 if(!playing||state.finished){
  visualLaneState.clear();visualRenderTime=null;
  return turf.runners(state);
 }
 const fraction=Math.max(0,Math.min(acc,.08));
 const simTime=state.t+fraction;
 const dt=visualRenderTime===null?0:Math.max(0,Math.min(.16,simTime-visualRenderTime));
 visualRenderTime=simTime;
 return state.horses.map(h=>{
  const trail=h.trail||[];
  const last=trail.at(-1),before=trail.at(-2);
  const travel=last&&before?Math.max(0,last.d-before.d):0;
  const lastStep=.08;
  const visualD=(h.displayD??h.d)+Math.min(1.7,travel/lastStep*fraction);
  const desiredLane=Math.max(0,Math.min(14,h.lane+(h.laneVelocity||0)*fraction));
  const previous=visualLaneState.get(h.number);
  const alpha=1-Math.exp(-dt/.14);
  const smoothed=previous===undefined?desiredLane:
   previous+(desiredLane-previous)*alpha;
  visualLaneState.set(h.number,smoothed);
  return {number:h.number,d:visualD,lane:smoothed,
   ...turf.point(visualD,smoothed),finished:h.finished};
 });
}
// A circled number IS the moving horse (Kyoto 1400 contract). No pixel
// position displacement to evade overlap; dense packs may obscure neighbours.
function markers(ctx,points,loc,focused,mini=false){
 const sorted=points.map(p=>({...p,actual:position(p,loc)}))
  .sort((a,b)=>Number(a.number===focused)-Number(b.number===focused)||a.number-b.number);
 const displayed=[];
 for(const p of sorted){
  const x=p.actual.x,y=p.actual.y;
  // All 18 horses receive the same scale in each view, including focus.
  // No offset from the running coordinates and no larger highlighted marker.
  const compact=loc.w<540;
  const scale=mini?.48:(points.length>=12?(compact?.68:.76):.82);
  const radius=13.5*scale;
  if(x+radius<0||x-radius>loc.w||y+radius<0||y-radius>loc.h)continue;
  raceNumberMarker(ctx,p.number,x,y,scale,p.number===focused,false,18,false);
  displayed.push({...p,x,y,r:radius});
 }
 return displayed;
}
function updateRunningOrder(points,chosen){
 const host=$('runningOrder');
 if(!host)return;
 if(!host.dataset.ready){
  for(const p of points){
   const btn=document.createElement('button');
   btn.type='button';btn.className='position-chip';btn.dataset.horse=p.number;
   btn.setAttribute('aria-label',p.number+'番を追跡');
   btn.addEventListener('click',()=>{
    focusNo=String(p.number);$('focus').value=focusNo;
    lastCamera=null;paint();
   });
   host.appendChild(btn);
  }
  host.dataset.ready='true';
 }
 const chips=new Map([...host.children].map(x=>[Number(x.dataset.horse),x]));
 const order=points.slice().sort((a,b)=>b.d-a.d||a.number-b.number);
 for(let i=0;i<order.length;i++){
  const p=order[i],chip=chips.get(p.number),col=waku(p.number);
  chip.textContent=String(p.number);
  chip.style.backgroundColor=col.fill;
  chip.style.color=col.ink;
  chip.classList.toggle('is-focus',p.number===chosen);
  chip.title=(i+1)+'番手・'+p.number+'番を追跡';
  host.appendChild(chip);
 }
 $('orderNote').textContent='左から先頭順 / '+order.length+'頭。タップで追跡';
}
function paint(){
 // Refuse to paint numbers using the obsolete JPEG-position centerline
 // while the real Umapot SVG green-corridor occupancy is loading.
 if(!engine||!turfReady)return;
 const state=engine.state,points=displayPoints(state);
 lastRenderedPoints=points;
 const chosen=focusNo==='leader'?state.leadingNo:Number(focusNo);
 const live=sizeCanvas($('broadcast'));
 // Transparent canvas: original Umapot image is the only course background.
 const target=cameraFor(points,live.w,live.h,chosen,focusNo==='leader');
 if(finishSequenceActive){
  // Ease from the horse-focused close camera to a wider finish tableau.
  const p=Math.min(1,finishSequenceElapsedMs/FINISH_SEQUENCE_MS);
  const eased=p*p*(3-2*p);
  target.scale*=1-.22*eased;
 }
 // Stabilize view with a real elapsed-time exponential filter; frame rate
 // changes do not change the amount of camera smoothing.
 const now=performance.now(),dt=cameraRenderTime?
  Math.min(.06,(now-cameraRenderTime)/1000):0;
 cameraRenderTime=now;
 if(!lastCamera)lastCamera=target;
 else {
  const blend=1-Math.exp(-dt/.13);
  lastCamera={...target,
   x:lastCamera.x+(target.x-lastCamera.x)*blend,
   y:lastCamera.y+(target.y-lastCamera.y)*blend};
 }
 backdrop(lastCamera);
 const labels=markers(live.ctx,points,{...lastCamera,w:live.w,h:live.h},chosen);
 lastLabelPositions=labels;
 // Kyoto1400 contract: exactly 80 metres from the finish, replace the
 // zoomed course with the right-to-left GOAL-board television camera.
 // RaceSimEngine.goalCamera was already computed on physical race distance.
 const goalCanvas=$('goalCamera');
 if(goalCanvas){
  const goalMode=Boolean(state.goalCamera||state.firstFinishTime!==null);
  goalCanvas.hidden=!goalMode;
  if(goalMode){
   const p=finishSequenceActive?
     Math.min(1,finishSequenceElapsedMs/FINISH_SEQUENCE_MS):0;
   const eased=p*p*(3-2*p);
   lastGoalFrame=window.RaceCleanGoalView.render({
    canvas:goalCanvas,points,leaderNo:state.leadingNo,focusedNo:chosen,
    paintNumber:raceNumberMarker,maxLane:14,distance:2000,turn:'右',
    fieldSize:18,pullback:1+.22*eased
   });
  }else lastGoalFrame=null;
 }
 const map=sizeCanvas($('overview'));
 // Transparent numbers over the ACTUAL original 620x430 course diagram.
 const overview={x:310,y:215,cx:map.w/2,cy:map.h/2,
  scale:Math.min(map.w/620,map.h/430),w:map.w,h:map.h};
 markers(map.ctx,points,overview,chosen,true);
 updateRunningOrder(points,chosen);
 $('progress').textContent=Math.round(state.leader)+'m / 2000m';
 $('clock').textContent=state.t.toFixed(1)+'秒';
 $('section').textContent=(state.allCrossedAt!==null?'全馬ゴール・余走中':
   state.goalCamera?'ゴール板固定カメラ':model.center(state.leader).section)+
   ' ／ 内4列 '+state.horses.filter(h=>h.lane<=3.45).length+'頭'+
   ' ／ 内へ '+state.totalInsideMoves+'回';
 const banner=$('finishBanner');
 if(banner&&finishSequenceActive){
  const p=Math.min(1,finishSequenceElapsedMs/FINISH_SEQUENCE_MS);
  banner.hidden=p<.30;
  if(!banner.hidden){
   const podium=state.horses.slice().filter(h=>h.finishTime!==null)
    .sort((a,b)=>a.finishTime-b.finishTime).slice(0,3);
   $('finishHeading').textContent=finishSequenceDone?'全馬ゴール・余走終了':'全馬ゴール・余走中';
   $('finishPodium').textContent=podium.map((h,i)=>(i+1)+'着 '+h.number+'番').join('　');
  }
 }else if(banner){banner.hidden=true}
}
function tick(ts){
 if(!last)last=ts;
 let delta=Math.min(.06,(ts-last)/1000);last=ts;
 if(playing){
  if(!engine.state.finished){
   acc+=delta*Number($('speed').value);
   let count=0;
   while(acc>=.08&&count++<8&&!engine.state.finished){engine.step(.08);acc-=.08}
  }
  if(engine.state.finished){
   // The physics state is final. Keep the animation alive for a gentle
   // 3.2s real-time camera pullback and 6m display-only coasting.
   finishSequenceActive=true;
   finishSequenceElapsedMs=Math.min(FINISH_SEQUENCE_MS,
    finishSequenceElapsedMs+delta*1000);
   if(finishSequenceElapsedMs>=FINISH_SEQUENCE_MS){
    playing=false;finishSequenceDone=true;
    $('startBtn').textContent='▶ 再スタート';
   }
  }
  if(ts-renderStamp>14||finishSequenceDone){paint();renderStamp=ts}
 }
 requestAnimationFrame(tick);
}
function setup(){
 for(const id of ['realCourseImage','liveCourseImage']){
  const img=$(id);
  if(!img)throw Error('ORIGINAL_VECTOR_MISSING');
  img.addEventListener('load',()=>{verifyVectorSource();paint()});
  img.addEventListener('error',()=>{originalError=true;vectorReady=false});
 }
 verifyVectorSource();
 $('focus').insertAdjacentHTML('beforeend',fixture.horses().map(h=>
   '<option value="'+h.number+'">'+h.number+'番</option>').join(''));
 $('horseGrid').innerHTML=fixture.horses().map(h=>{
  const col=waku(h.number);
  return '<div class="horsechip" style="background:'+col.fill+';color:'+col.ink+
   '">'+h.number+'</div>';
 }).join('');
 $('focus').addEventListener('change',e=>{
  focusNo=e.target.value;lastCamera=null;cameraRenderTime=0;
  visualLaneState.clear();visualRenderTime=null;paint();
 });
 $('startBtn').addEventListener('click',()=>{
  if(engine.state.finished)reset();
  playing=true;$('startBtn').textContent='▶ 再生中';
 });
 $('pauseBtn').addEventListener('click',()=>{
  playing=false;$('startBtn').textContent='▶ 再開';
 });
 $('resetBtn').addEventListener('click',reset);
 addEventListener('resize',()=>{lastCamera=null;cameraRenderTime=0;paint()});
 reset();
 const params=new URLSearchParams(location.search);
 const checkpoint=Number(params.get('checkpoint'));
 if(params.has('checkpoint')&&Number.isFinite(checkpoint)&&checkpoint>=0&&checkpoint<=2000)
  advanceTo(checkpoint);
 requestAnimationFrame(tick);
}
window.CleanLab=Object.freeze({
 getState:()=>engine?.state,
 // Cheap, per-animation-frame diagnostic for REAL 4x playback QA.
 frameSample:()=>({t:engine?.state?.t??0,playing,zoom:lastCamera?.scale??0,
  camera:lastCamera?{x:lastCamera.x,y:lastCamera.y}:null,
  finishSequenceActive,finishSequenceDone,finishSequenceElapsedMs,
  horses:lastRenderedPoints.map(p=>({number:p.number,x:p.x,y:p.y,d:p.d,lane:p.lane}))}),
 inspect:()=>{
  const points=turfReady?(lastRenderedPoints.length?lastRenderedPoints:
  turf.runners(engine.state)):model.runners(engine.state);
  const selected=focusNo==='leader'?engine.state.leadingNo:Number(focusNo);
  const chosen=points.find(p=>p.number===selected)||points[0];
  const screen=lastCamera?position(chosen,lastCamera):null;
  const live=$('broadcast').getBoundingClientRect();
  const rect=$('overview').getBoundingClientRect();
  const image=$('realCourseImage');
  return {leader:engine.state.leader,positions:points,
   originalImageSrc:image?.getAttribute('src')||null,
   originalLoaded:sourceImageReady(image),
   liveImageLoaded:sourceImageReady($('liveCourseImage')),
   sourceNaturalSize:image?{
    width:image.naturalWidth,height:image.naturalHeight}:null,
   liveImageSrc:$('liveCourseImage')?.getAttribute('src')||null,
   originalError,vectorReady,turfReady,turfError,turfStats,
   visualInterpolationEnabled:true,fixedCameraZoom:!finishSequenceActive,
   goalBoardVisible:Boolean(!$('goalCamera')?.hidden),
   goalFrame:lastGoalFrame,goalCameraSwitchDistance:1920,
   finishSequenceActive,finishSequenceDone,finishSequenceElapsedMs,
   finishedBannerVisible:Boolean(!$('finishBanner')?.hidden),
   visualSimulationTime:visualRenderTime,
   displayedDeltas:points.map(p=>({
     number:p.number,d:p.d-(engine.state.horses.find(h=>h.number===p.number)?.displayD||0),
     lane:p.lane-(engine.state.horses.find(h=>h.number===p.number)?.lane||0)
   })),
   highResolutionMode:'publisher-original-svg-not-resampled-jpeg',
   normalBroadcastZoom:8.8,normalDesktopZoom:9.7,
   actualNumberCircles:true,paintedTrack:false,leaderLines:false,
   mapAspect:rect.width/Math.max(1,rect.height),
   zoom:lastCamera?.scale??0,
   visibleOrder:[...$('runningOrder').children].map(el=>Number(el.dataset.horse)),
   liveLabelPositions:lastLabelPositions.map(p=>({number:p.number,x:p.x,y:p.y,r:p.r,
     anchorX:p.actual.x,anchorY:p.actual.y})),
   directMarkerMaxError:lastLabelPositions.reduce((m,p)=>
     Math.max(m,Math.hypot(p.x-p.actual.x,p.y-p.actual.y)),0),
   turfBadCenters:turfReady?points.filter(p=>!turf.isGreen(p.x,p.y)).length:null,
   turfBadDiscs:turfReady?points.filter(p=>
     !turf.discOnTurf(p.x,p.y,
       13.5*(live.width<540?.68:.76)/Math.max(1.7,lastCamera?.scale||2.3)+.6)).length:null,
   calibratedRunPositions:turfReady,
   uniformMarkerRadiusPx:lastLabelPositions[0]?.r??null,
   markerRadiusSpreadPx:lastLabelPositions.length?
     Math.max(...lastLabelPositions.map(p=>p.r))-
     Math.min(...lastLabelPositions.map(p=>p.r)):0,
   focusedMarkerRadiusPx:lastLabelPositions.find(p=>p.number===selected)?.r??null,
   severeOverlapPairs:lastLabelPositions.reduce((n,a,i)=>n+
    lastLabelPositions.slice(i+1).filter(b=>
     Math.hypot(a.x-b.x,a.y-b.y)<.55*(a.r+b.r)).length,0),
   touchingPairs:lastLabelPositions.reduce((n,a,i)=>n+
    lastLabelPositions.slice(i+1).filter(b=>
     Math.hypot(a.x-b.x,a.y-b.y)<a.r+b.r).length,0),
   commonLaneController:Boolean(window.RaceLaneAI?.plan&&window.RaceLaneAI?.launchStepSafe),
   inwardMoves:engine.state.totalInsideMoves,
   outwardMoves:engine.state.totalOutsidePasses,
   insideFour:engine.state.horses.filter(h=>h.lane<=3.45).length,
   turfVisualWidthPx:model.widthPx,physicalWidthM:model.widthMetres,
    selectedHorse:selected,selectedScreen:screen,
    selectedVisible:Boolean(screen&&screen.x>=16&&screen.x<=live.width-16&&
     screen.y>=16&&screen.y<=live.height-16),
    imageCalls:vectorReady?1:0,section:model.center(engine.state.leader).section,
    fixedSegments:model.sections.filter(s=>s.kind==='straight').map(s=>[s.from,s.to])};
 },advanceTo
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);
else setup();
})();
