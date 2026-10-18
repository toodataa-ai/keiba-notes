/* LAB v10: original publisher SVG with SOURCE GREEN turf occupancy and same-size horse numbers.
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
let engine,playing=false,last=0,acc=0,renderStamp=0,focusNo='leader',lastCamera=null,lastLabelPositions=[];
let vectorReady=false,originalError=false,turfReady=false,turfError=null,turfStats=null;
const SOURCE_VECTOR='assets/kyoto-umapot-course-clean-v8.svg';
function reset(){
 engine=RaceSimEngine.create({...race,horses:fixture.horses()},{seed:2026,bias:'neutral'});
 playing=false;last=0;acc=0;lastCamera=null;paint();
}
function advanceTo(distance){
 reset();
 let i=0;
 while(engine.state.leader<distance&&!engine.state.finished&&i++<1500)engine.step(.12);
 // Seek is a jump in simulation time. Do NOT interpolate the camera from
 // the starting gate across 900 metres: it leaves every horse off-screen.
 lastCamera=null;
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
function verifyVectorSource(){
 const a=$('realCourseImage'),b=$('liveCourseImage');
 vectorReady=Boolean(a&&b&&a.complete&&b.complete&&
   a.naturalWidth===620&&a.naturalHeight===430&&
   b.naturalWidth===620&&b.naturalHeight===430&&
   a.getAttribute('src')===SOURCE_VECTOR&&b.getAttribute('src')===SOURCE_VECTOR);
 if(vectorReady){
  originalError=false;
  if(!turfReady&&!turfError){
   try{turfStats=turf.create(full);turfReady=true;}
   catch(err){turfError=String(err);console.error('KYOTO_TURF_MASK_INIT',err)}
  }
 }
}
function position(p,camera){
 return {x:camera.cx+(p.x-camera.x)*camera.scale,
         y:camera.cy+(p.y-camera.y)*camera.scale};
}
function cameraFor(points,w,h,chosen){
 // Kyoto1400's real-position number rendering with a closer group camera.
 const focus=points.find(p=>p.number===chosen)||points.slice().sort((a,b)=>b.d-a.d)[0];
 const group=points.filter(p=>Math.abs(p.d-focus.d)<=80);
 if(!group.some(p=>p.number===focus.number))group.push(focus);
 const xs=group.map(p=>p.x),ys=group.map(p=>p.y);
 const loX=Math.min(...xs),hiX=Math.max(...xs),loY=Math.min(...ys),hiY=Math.max(...ys);
 const mx=Math.min(w*.18,28),my=Math.min(h*.18,40);
 const zoom=Math.max(2.3,Math.min(w<540?8.2:9.6,
  (w-2*mx)/Math.max(30,hiX-loX+12),
  (h-2*my)/Math.max(25,hiY-loY+8)));
 const mean={x:(loX+hiX)/2,y:(loY+hiY)/2};
 const origin={x:focus.x+.16*(mean.x-focus.x),y:focus.y+.16*(mean.y-focus.y)};
 return {x:origin.x,y:origin.y,cx:w/2,cy:h*.5,scale:zoom};
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
 const state=engine.state,points=turf.runners(state);
 const chosen=focusNo==='leader'?state.leadingNo:Number(focusNo);
 const live=sizeCanvas($('broadcast'));
 // Transparent canvas: original Umapot image is the only course background.
 const target=cameraFor(points,live.w,live.h,chosen);
 // Smooth camera pan with state-time-independent interpolation on each frame.
 if(!lastCamera)lastCamera=target;
 else lastCamera={...target,x:lastCamera.x*.85+target.x*.15,
      y:lastCamera.y*.85+target.y*.15,
      scale:lastCamera.scale*.88+target.scale*.12};
 backdrop(lastCamera);
 const labels=markers(live.ctx,points,{...lastCamera,w:live.w,h:live.h},chosen);
 lastLabelPositions=labels;
 const map=sizeCanvas($('overview'));
 // Transparent numbers over the ACTUAL original 620x430 course diagram.
 const overview={x:310,y:215,cx:map.w/2,cy:map.h/2,
  scale:Math.min(map.w/620,map.h/430),w:map.w,h:map.h};
 markers(map.ctx,points,overview,chosen,true);
 updateRunningOrder(points,chosen);
 $('progress').textContent=Math.round(state.leader)+'m / 2000m';
 $('clock').textContent=state.t.toFixed(1)+'秒';
 $('section').textContent=model.center(state.leader).section+
   ' ／ 内4列 '+state.horses.filter(h=>h.lane<=3.45).length+'頭'+
   ' ／ 内へ '+state.totalInsideMoves+'回';
 if(state.finished){playing=false;$('startBtn').textContent='▶ 再スタート'}
}
function tick(ts){
 if(!last)last=ts;
 let delta=Math.min(.06,(ts-last)/1000);last=ts;
 if(playing){
  acc+=delta*Number($('speed').value);
  let count=0;
  while(acc>=.08&&count++<8&&!engine.state.finished){engine.step(.08);acc-=.08}
  if(ts-renderStamp>25){paint();renderStamp=ts}
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
 $('focus').addEventListener('change',e=>{focusNo=e.target.value;lastCamera=null;paint()});
 $('startBtn').addEventListener('click',()=>{
  if(engine.state.finished)reset();
  playing=true;$('startBtn').textContent='▶ 再生中';
 });
 $('pauseBtn').addEventListener('click',()=>{
  playing=false;$('startBtn').textContent='▶ 再開';
 });
 $('resetBtn').addEventListener('click',reset);
 addEventListener('resize',()=>{lastCamera=null;paint()});
 reset();
 const params=new URLSearchParams(location.search);
 const checkpoint=Number(params.get('checkpoint'));
 if(params.has('checkpoint')&&Number.isFinite(checkpoint)&&checkpoint>=0&&checkpoint<=2000)
  advanceTo(checkpoint);
 requestAnimationFrame(tick);
}
window.CleanLab=Object.freeze({
 getState:()=>engine?.state,inspect:()=>{
  const points=turfReady?turf.runners(engine.state):model.runners(engine.state);
  const selected=focusNo==='leader'?engine.state.leadingNo:Number(focusNo);
  const chosen=points.find(p=>p.number===selected)||points[0];
  const screen=lastCamera?position(chosen,lastCamera):null;
  const live=$('broadcast').getBoundingClientRect();
  const rect=$('overview').getBoundingClientRect();
  const image=$('realCourseImage');
  return {leader:engine.state.leader,positions:points,
   originalImageSrc:image?.getAttribute('src')||null,
   originalLoaded:Boolean(image?.complete&&image?.naturalWidth===620&&image?.naturalHeight===430),
   liveImageLoaded:Boolean($('liveCourseImage')?.complete&&$('liveCourseImage')?.naturalWidth===620),
   liveImageSrc:$('liveCourseImage')?.getAttribute('src')||null,
   originalError,vectorReady,turfReady,turfError,turfStats,
   highResolutionMode:'publisher-original-svg-not-resampled-jpeg',
   actualNumberCircles:true,paintedTrack:false,leaderLines:false,
   mapAspect:rect.width/Math.max(1,rect.height),
   zoom:lastCamera?.scale??0,
   visibleOrder:[...$('runningOrder').children].map(el=>Number(el.dataset.horse)),
   liveLabelPositions:lastLabelPositions.map(p=>({number:p.number,x:p.x,y:p.y,r:p.r,
     anchorX:p.actual.x,anchorY:p.actual.y})),
   directMarkerMaxError:lastLabelPositions.reduce((m,p)=>
     Math.max(m,Math.hypot(p.x-p.actual.x,p.y-p.actual.y)),0),
   turfBadCenters:turfReady?points.filter(p=>!turf.isGreen(p.x,p.y)).length:null,
   turfBadDiscs:turfReady?points.filter(p=>!turf.discOnTurf(p.x,p.y)).length:null,
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
