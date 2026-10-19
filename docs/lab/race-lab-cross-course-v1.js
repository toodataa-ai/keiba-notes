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
let route=null,engine=null,playing=false,last=0,acc=0,prev=null,curr=null;
let shown=[],camera=null,lastPaint=0,finishElapsed=0,blocked=null;
const cache={signature:''};
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
 prev=curr=capture();acc=0;last=0;playing=false;camera=null;shown=[];
 finishElapsed=0;cache.signature='';$('resultsBody').replaceChildren();
 $('fullResults').hidden=true;$('startBtn').textContent='▶ スタート';draw();
}
function fail(reason){
 blocked=String(reason);playing=false;$('startBtn').disabled=true;
 $('sourceAudit').classList.add('blocked');
 $('sourceAudit').textContent='安全ゲートで停止しました: '+blocked;
}
function load(){
 if(blocked)return;
 try{
  route=RaceLabSourceMask.build({image:$('realCourseImage'),course,
   guide:RaceUmapotOverlay.legacyPoint,
   projection:RaceSafeRailProjection,geometry:RaceCourseImageGeometry});
  RaceLabCourseRollout.assertCanAnimate(courseId,course,route);
  $('sourceAudit').textContent='原図の芝帯監査 '+route.report.checked+
   '地点 合格／芝帯外0／画像・物理変更なし';
  $('startBtn').disabled=false;reset();
 }catch(e){fail(e)}
}
function points(){
 if(!engine)return[];
 if(playing&&!engine.state.finished)return RaceFrameInterpolator.interpolate(
   prev,curr,acc/STEP).map(h=>({...h,...route.point(h.d,h.lane)}));
 if(shown.length)return shown;
 return engine.state.horses.map(h=>({number:h.number,d:h.displayD??h.d,
  lane:h.lane,...route.point(h.displayD??h.d,h.lane)}));
}
function draw(){
 if(!route||!engine)return;
 const state=engine.state,items=points();shown=items;
 const b=surface('broadcast'),m=surface('overview');
 const leaderD=Math.max(...items.map(h=>h.d));
 const center=route.point(Math.max(0,Math.min(course.distance_m,leaderD-10)),3);
 if(!camera)camera={x:center.x,y:center.y};
 else{camera.x+=(center.x-camera.x)*.16;camera.y+=(center.y-camera.y)*.16}
 const zoom=b.w<540?8.8:9.7,dpr=b.ctx.getTransform().a||1;
 const left=Math.round((b.w*.54-camera.x*zoom)*dpr)/dpr;
 const top=Math.round((b.h*.51-camera.y*zoom)*dpr)/dpr;
 $('liveCourseImage').style.transform='translate('+left+'px,'+top+'px) scale('+zoom+')';
 for(const h of items){
  const x=left+h.x*zoom,y=top+h.y*zoom;
  if(x>=-18&&x<=b.w+18&&y>=-18&&y<=b.h+18)
   numbers(b.ctx,h.number,x,y,b.w<540?.78:.84,h.number===state.leadingNo);
  numbers(m.ctx,h.number,h.x*m.w/620,h.y*m.h/430,.48,h.number===state.leadingNo);
 }
 if(state.firstFinishTime!==null){
  $('goalCamera').hidden=false;
  RaceCleanGoalView.render({canvas:$('goalCamera'),points:items,
   leaderNo:state.leadingNo,focusedNo:state.leadingNo,
   paintNumber:numbers,turn:course.turn,distance:course.distance_m,
   fieldSize:18,maxLane:14});
 }else $('goalCamera').hidden=true;
 RaceBroadcastHud.render(state,elements(),cache);
 $('progress').textContent=Math.round(state.leader)+'m / '+course.distance_m+'m';
 $('section').textContent=state.leader>=course.distance_m-course.straight_m?
  '最後の直線':'京都芝1400m外回り';
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
 inspect:()=>({courseId,blocked,ready:!!engine,playing,fieldSize:engine?.state.horses.length,
  source:RaceLabCourseRollout.get(courseId).svg})
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);
else setup();
})();