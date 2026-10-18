/* LAB v6: native Umapot bitmap in BOTH views; only numbered runners move.
 * Source bitmap is never redrawn as an approximate course. A browser-local,
 * fourfold high-quality resample is a display cache, not a new detailed source.
 * Only synthetic 18-horse data; no official prediction/odds/bets/PDF changes.
 */
(function(){'use strict';
const $=id=>document.getElementById(id);
const model=window.RaceCleanCourse;
const fixture=window.RaceLab18Fixture;
const entries=fixture.horses();
const race={...fixture.entry(),horses:entries};
const palette=[
 {fill:'#ffffff',ink:'#202a32'}, {fill:'#20242a',ink:'#ffffff'},
 {fill:'#c7374e',ink:'#ffffff'}, {fill:'#2556a9',ink:'#ffffff'},
 {fill:'#f2d345',ink:'#202b34'}, {fill:'#29905f',ink:'#ffffff'},
 {fill:'#ed8832',ink:'#272b30'}, {fill:'#eb9dc6',ink:'#272b30'}
];
function waku(no){
 const groups=[2,2,2,2,2,2,3,3];
 let offset=0;
 for(let i=0;i<8;i++){offset+=groups[i];if(no<=offset)return palette[i]}
 return palette[7];
}
let engine,playing=false,last=0,acc=0,renderStamp=0,focusNo='leader',lastCamera=null,lastLabelPositions=[];
let hiResReady=false,originalReady=false,originalError=false;
// Source image is linked directly from Umapot in a regular <img>. Browser
// local resampling does not upload, store or rehost the source image.
const IMAGE_SCALE=4;
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
 for(const id of ['liveCourseImage','liveCourseHiRes']){
  const element=$(id);
  if(element)element.style.transform=transform;
 }
}
function upscaleOriginal(){
 const original=$('realCourseImage'),out=$('liveCourseHiRes');
 if(!original||!out||!original.complete||!original.naturalWidth)return;
 originalReady=true;
 try{
  const targetWidth=original.naturalWidth*IMAGE_SCALE,
   targetHeight=original.naturalHeight*IMAGE_SCALE;
  if(out.width!==targetWidth)out.width=targetWidth;
  if(out.height!==targetHeight)out.height=targetHeight;
  const ctx=out.getContext('2d');
  if(!ctx)throw Error('UPSCALE_CANVAS_CONTEXT');
  ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
  // Upsample the ORIGINAL pixels. Does not hallucinate missing detail.
  ctx.drawImage(original,0,0,targetWidth,targetHeight);
  hiResReady=true;
  out.classList.add('is-ready');
  $('liveCourseImage').classList.add('is-upscaled');
 }catch(err){
  hiResReady=false;
  console.warn('Native image remains visible; browser upscale unavailable',err);
 }
}
function position(p,camera){
 return {x:camera.cx+(p.x-camera.x)*camera.scale,
         y:camera.cy+(p.y-camera.y)*camera.scale};
}
function cameraFor(points,w,h,chosen){
 // Kyoto 1400 approach: follow the nearby racing group (not all 18 horses).
 // Camera zoom and numbered circles are independent; circles remain readable.
 const focus=points.find(p=>p.number===chosen)||points.slice().sort((a,b)=>b.d-a.d)[0];
 const group=points.filter(p=>Math.abs(p.d-focus.d)<=56);
 if(!group.some(p=>p.number===focus.number))group.push(focus);
 const xs=group.map(p=>p.x),ys=group.map(p=>p.y);
 const loX=Math.min(...xs),hiX=Math.max(...xs),loY=Math.min(...ys),hiY=Math.max(...ys);
 const zoom=Math.max(3.4,Math.min(7.2,
  (w-36)/Math.max(44,hiX-loX+7),
  (h-56)/Math.max(42,hiY-loY+7)));
 const mid={x:(loX+hiX)/2,y:(loY+hiY)/2};
 return {x:focus.x*.87+mid.x*.13,y:focus.y*.87+mid.y*.13,
  cx:w*.5,cy:h*.52,scale:zoom};
}
function roundedWaku(ctx,p,x,y,focused){
 const colors=waku(p.number),radius=focused?14:11.7;
 if(focused){ctx.beginPath();ctx.arc(x,y,radius+2.6,0,Math.PI*2);
  ctx.fillStyle='#f1bd53';ctx.fill()}
 ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);
 ctx.fillStyle=colors.fill;ctx.fill();
 ctx.strokeStyle=colors.fill==='#ffffff'?'#4c5961':'#22333b';
 ctx.lineWidth=1.4;ctx.stroke();
 ctx.fillStyle=colors.ink;ctx.textAlign='center';ctx.textBaseline='middle';
 ctx.font=(p.number>9?'900 12.5px':'900 14px')+' Arial,sans-serif';
 ctx.fillText(String(p.number),x,y+.4);
}
// Layout applies ONLY to label positions in LIVE, never to the racing model
// or the original-image overview coordinates. Stable numeric ordering makes
// multi-runner collisions reproducible without random flicker.
function placeReadableLabels(points,loc,focused){
 // A horse is its circled number, never an external callout. To resolve
 // overlap, choose label locations ON the source-image turf strip at nearby
 // race-distance/rail fractions. Underlying racing positions never change.
 const nodes=points.map(p=>{
  const actual=position(p,loc);
  return {...p,actual,x:actual.x,y:actual.y,r:p.number===focused?14:11.7,onTurf:true};
 }).filter(p=>p.actual.x>=-45&&p.actual.x<=loc.w+45&&
  p.actual.y>=-45&&p.actual.y<=loc.h+45);
 const ordered=nodes.slice().sort((a,b)=>
  Number(b.number===focused)-Number(a.number===focused)||b.d-a.d||a.number-b.number);
 const placed=[];
 const distanceOffsets=[0];
 for(let k=1;k<=17;k++){distanceOffsets.push(-k*8,k*8)}
 for(const p of ordered){
  if(p.number===focused){placed.push(p);continue}
  const originalFraction=model.fraction(p.lane);
  const fractions=[originalFraction,.12,.23,.34,.45,.56,.67,.78,.90]
   .sort((a,b)=>Math.abs(a-originalFraction)-Math.abs(b-originalFraction));
  let choice=null,best=Infinity;
  for(const dd of distanceOffsets){
   const dist=Math.max(0,Math.min(model.distance,p.d+dd)),rail=model.rails(dist);
   for(const f of fractions){
    const point={x:rail.inner.x+(rail.outer.x-rail.inner.x)*f,
      y:rail.inner.y+(rail.outer.y-rail.inner.y)*f};
    const pos=position(point,loc);
    if(pos.x<p.r+3||pos.x>loc.w-p.r-3||
      pos.y<p.r+3||pos.y>loc.h-p.r-3)continue;
    if(placed.some(q=>Math.hypot(pos.x-q.x,pos.y-q.y)<p.r+q.r+2.5))continue;
    const score=Math.hypot(pos.x-p.actual.x,pos.y-p.actual.y)+
      Math.abs(dd)*.05;
    if(score<best){best=score;choice=pos}
   }
  }
  if(choice){p.x=choice.x;p.y=choice.y}
  else { // Keep the source position if no non-overlapping turf point exists.
   p.onTurf=true;
  }
  placed.push(p);
 }
 return nodes;
}
function markers(ctx,points,loc,focused,mini=false){
 if(mini){
  // The overview is metrically exact; labels are intentionally small.
  const ordered=points.slice().sort((a,b)=>Number(a.number===focused)-Number(b.number===focused));
  for(const p of ordered){
   const s=position(p,loc);
   if(s.x<-15||s.x>loc.w+15||s.y<-15||s.y>loc.h+15)continue;
   const col=waku(p.number);
   ctx.beginPath();ctx.arc(s.x,s.y,6.3,0,Math.PI*2);
   ctx.fillStyle=col.fill;ctx.fill();ctx.strokeStyle='#182d26';ctx.lineWidth=.8;ctx.stroke();
   ctx.fillStyle=col.ink;ctx.textAlign='center';ctx.textBaseline='middle';
   ctx.font='bold 7.5px Arial,sans-serif';ctx.fillText(String(p.number),s.x,s.y+.3);
  }
  return [];
 }
 const placed=placeReadableLabels(points,loc,focused);
 // The numbered circles ARE the runners. No locator pins, pointers,
 // leader lines, horse silhouettes or fake painted racecourse. Only the
 // numbers move. The overlap solver affects visual badge placement alone.
 for(const p of placed.filter(p=>p.number!==focused))
  roundedWaku(ctx,p,p.x,p.y,false);
 for(const p of placed.filter(p=>p.number===focused))
  roundedWaku(ctx,p,p.x,p.y,true);
 return placed;
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
 if(!engine)return;
 const state=engine.state,points=model.runners(state);
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
   ' ／ 内4列 '+state.horses.filter(h=>h.lane<=3.45).length+'頭';
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
 const original=$('realCourseImage');
 if(original){
  original.addEventListener('load',upscaleOriginal);
  original.addEventListener('error',()=>{
   originalError=true;
   const credit=document.querySelector('.source-credit');
   if(credit)credit.textContent='コースの原画像を読み込めません。うまぽっとの配信状況をご確認ください。';
  });
  if(original.complete&&original.naturalWidth)upscaleOriginal();
 }
 const liveImage=$('liveCourseImage');
 if(liveImage)liveImage.addEventListener('error',()=>{originalError=true;});
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
  const points=model.runners(engine.state);
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
   originalError,upscaledReady:hiResReady,
   upscaledCanvasWidth:$('liveCourseHiRes')?.width||0,
   upscaledCanvasHeight:$('liveCourseHiRes')?.height||0,
   actualNumberCircles:true,paintedTrack:false,leaderLines:false,
   mapAspect:rect.width/Math.max(1,rect.height),
   zoom:lastCamera?.scale??0,
   visibleOrder:[...$('runningOrder').children].map(el=>Number(el.dataset.horse)),
   liveLabelPositions:lastLabelPositions.map(p=>({number:p.number,x:p.x,y:p.y,r:p.r,
     anchorX:p.actual.x,anchorY:p.actual.y,onTurf:p.onTurf})),
   turfVisualWidthPx:model.widthPx,physicalWidthM:model.widthMetres,
    selectedHorse:selected,selectedScreen:screen,
    selectedVisible:Boolean(screen&&screen.x>=16&&screen.x<=live.width-16&&
     screen.y>=16&&screen.y<=live.height-16),
    imageCalls:hiResReady?1:0,section:model.center(engine.state.leader).section,
    fixedSegments:model.sections.filter(s=>s.kind==='straight').map(s=>[s.from,s.to])};
 },advanceTo
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);
else setup();
})();
