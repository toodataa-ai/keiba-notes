/* Independent LAB clean-vector trial. Only the synthetic 18-horse engine is
 * connected; no official prediction, no Umapot bitmap or green-pixel extraction.
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
let engine,playing=false,last=0,acc=0,renderStamp=0,focusNo='leader',lastCamera=null;
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
function track(ctx,loc){
 // A fill and two smooth rail strokes for each 5-segment centerline.
 // Bezier control points remain geometrically C1-continuous at boundaries.
 ctx.save();
 ctx.translate(loc.cx,loc.cy);
 ctx.scale(loc.scale,loc.scale);
 ctx.translate(-loc.x,-loc.y);
 const W=model;
 for(const s of W.sections){
  const n=Math.max(12,Math.ceil((s.to-s.from)/7)),inPts=[],outPts=[];
  for(let i=0;i<=n;i++){
   const e=W.rails(s.from+(s.to-s.from)*i/n);
   inPts.push(e.inner);outPts.push(e.outer);
  }
  ctx.beginPath();ctx.moveTo(inPts[0].x,inPts[0].y);
  inPts.slice(1).forEach(p=>ctx.lineTo(p.x,p.y));
  outPts.slice().reverse().forEach(p=>ctx.lineTo(p.x,p.y));
  ctx.closePath();ctx.fillStyle='#7abc75';ctx.fill();
  ctx.strokeStyle='#3d7f50';ctx.lineWidth=.8;
  for(const arr of [inPts,outPts]){
   ctx.beginPath();ctx.moveTo(arr[0].x,arr[0].y);
   arr.slice(1).forEach(p=>ctx.lineTo(p.x,p.y));
   ctx.stroke();
  }
 }
 ctx.restore();
}
function position(p,camera){
 return {x:camera.cx+(p.x-camera.x)*camera.scale,
         y:camera.cy+(p.y-camera.y)*camera.scale};
}
function cameraFor(points,w,h,chosen){
 // Field-relative camera inspired by the earlier Kyoto 1400 view.
 const focus=points.find(p=>p.number===chosen)||points.slice().sort((a,b)=>b.d-a.d)[0];
 const pack=points.filter(p=>Math.abs(p.d-focus.d)<80);
 if(!pack.some(p=>p.number===focus.number))pack.push(focus);
 const xs=pack.map(p=>p.x),ys=pack.map(p=>p.y);
 const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
 const zoom=Math.max(1.35,Math.min(3.15,(w-70)/Math.max(85,maxX-minX+20),
  (h-60)/Math.max(72,maxY-minY+22)));
 // Keep a modest amount of nearby pack in view without hiding the leader.
 const mid={x:(minX+maxX)/2,y:(minY+maxY)/2};
 return {x:focus.x*.79+mid.x*.21,y:focus.y*.79+mid.y*.21,
  cx:w*.51,cy:h*.54,scale:zoom};
}
function roundedWaku(ctx,p,x,y,mobile,focused){
 const colors=waku(p.number);
 const radius=focused?14.5:12.5; // CSS pixels, independent of camera zoom.
 if(focused){ctx.beginPath();ctx.arc(x,y,radius+2,0,Math.PI*2);
  ctx.fillStyle='#f1bd53';ctx.fill()}
 ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);
 ctx.fillStyle=colors.fill;ctx.fill();
 ctx.strokeStyle=colors.fill==='#ffffff'?'#4c5961':'#22333b';
 ctx.lineWidth=1.7;ctx.stroke();
 ctx.fillStyle=colors.ink;ctx.textAlign='center';ctx.textBaseline='middle';
 ctx.font=(p.number>9?'800 12px':'900 14px')+' Arial, sans-serif';
 ctx.fillText(String(p.number),x,y+.4);
}
function markers(ctx,points,loc,focused,mini=false){
 const ordered=points.slice().sort((a,b)=>
  Number(a.number===focused)-Number(b.number===focused));
 for(const p of ordered){
  const s=position(p,loc);
  if(s.x< -20||s.x>loc.w+20||s.y<-20||s.y>loc.h+20)continue;
  if(mini){
   const col=waku(p.number);
   ctx.fillStyle=col.fill;
   ctx.beginPath();ctx.arc(s.x,s.y,6.3,0,Math.PI*2);ctx.fill();
   ctx.strokeStyle='#182d26';ctx.lineWidth=.8;ctx.stroke();
   ctx.fillStyle=col.ink;ctx.font='bold 7.5px Arial,sans-serif';
   ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(p.number),s.x,s.y+.3);
  }else roundedWaku(ctx,p,s.x,s.y,loc.w<500,p.number===focused);
 }
}
function paint(){
 if(!engine)return;
 const state=engine.state,points=model.runners(state);
 const chosen=focusNo==='leader'?state.leadingNo:Number(focusNo);
 const live=sizeCanvas($('broadcast'));
 live.ctx.fillStyle='#f0f4ed';live.ctx.fillRect(0,0,live.w,live.h);
 const target=cameraFor(points,live.w,live.h,chosen);
 // Smooth camera pan with state-time-independent interpolation on each frame.
 if(!lastCamera)lastCamera=target;
 else lastCamera={...target,x:lastCamera.x*.85+target.x*.15,
      y:lastCamera.y*.85+target.y*.15,
      scale:lastCamera.scale*.88+target.scale*.12};
 track(live.ctx,{...lastCamera,w:live.w,h:live.h});
 markers(live.ctx,points,{...lastCamera,w:live.w,h:live.h},chosen);
 const map=sizeCanvas($('overview'));
 map.ctx.fillStyle='#fafcf9';map.ctx.fillRect(0,0,map.w,map.h);
 const scale=Math.min((map.w-25)/620,(map.h-12)/430);
 const overview={x:310,y:220,cx:map.w/2,cy:map.h/2,scale,w:map.w,h:map.h};
 track(map.ctx,overview);markers(map.ctx,points,overview,chosen,true);
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
  return {leader:engine.state.leader,positions:points,
    selectedHorse:selected,selectedScreen:screen,
    selectedVisible:Boolean(screen&&screen.x>=16&&screen.x<=live.width-16&&
     screen.y>=16&&screen.y<=live.height-16),
    imageCalls:0,section:model.center(engine.state.leader).section,
    fixedSegments:model.sections.filter(s=>s.kind==='straight').map(s=>[s.from,s.to])};
 },advanceTo
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);
else setup();
})();
