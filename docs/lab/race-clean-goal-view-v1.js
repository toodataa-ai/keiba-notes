/* LAB Kyoto 2000 goal-camera view. Port of Kyoto 1400's
 * RaceSimGoalView.goalScreenPosition and drawGoalPost from race-simulator.js.
 * RIGHT-handed Kyoto finishes screen right-to-left, with the GOAL post
 * fixed at 30% of the broadcast width. Display only: no race physics.
 */
(function(global){'use strict';
// The original Kyoto1400 goal camera has a 94px HUD margin. The clean
// LAB broadcast is only 380px high, so compute the lane step to keep all
// 15 lanes *inside* the painted turf rather than above the track on iPhone.
function laneStep(height,maxLane){
 return Math.min(30,height/16,(height-100)/(maxLane+3.2));
}
function goalScreenPosition(distance,lane,finish,width,height,maxLane,turn='左',pullback=1){
 const center=height*.52,step=laneStep(height,maxLane)/pullback;
 const direction=turn==='右'?-1:1,finishX=turn==='右'?width*.30:width*.70;
 // A fixed 100m screen span puts the leader at 110% width at the
 // 80m camera cut (right-handed course). Keep this linear through the
 // wire: entry, gaps and speed all use the same physical distance.
 return {x:finishX+direction*(distance-finish)*width/(100*pullback),
         y:center+(lane-maxLane/2)*step};
}
function drawGoalPost(ctx,x,top,bottom){
 ctx.fillStyle='#26332d';ctx.fillRect(x-5,top-20,10,bottom-top+25);
 for(let y=top;y<bottom;y+=12){
  ctx.fillStyle=Math.floor((y-top)/12)%2?'#293532':'#faf8ed';
  ctx.fillRect(x-4,y,8,Math.min(12,bottom-y));
 }
 ctx.fillStyle='#f9f9ef';ctx.fillRect(x-38,top-48,76,26);
 ctx.lineWidth=2;ctx.strokeStyle='#243438';ctx.strokeRect(x-38,top-48,76,26);
 ctx.font='bold 16px Meiryo';ctx.fillStyle='#15282d';ctx.textAlign='center';
 ctx.fillText('GOAL',x,top-29);ctx.textAlign='left';
}
function render(options){
 const {canvas,points,leaderNo,focusedNo,paintNumber,pullback=1,
  fieldSize=18,turn='右',distance=2000,maxLane=14}=options;
 const rect=canvas.getBoundingClientRect(),w=Math.max(1,rect.width),
   h=Math.max(1,rect.height),dpr=Math.min(2.5,Math.max(1,global.devicePixelRatio||1)),
   pixelW=Math.round(w*dpr),pixelH=Math.round(h*dpr);
 if(canvas.width!==pixelW||canvas.height!==pixelH){
  canvas.width=pixelW;canvas.height=pixelH;
 }
 const ctx=canvas.getContext('2d');
 ctx.setTransform(pixelW/w,0,0,pixelH/h,0,0);
 const center=h*.52,span=(maxLane/2+1.6)*laneStep(h,maxLane);
 const top=Math.max(18,center-span),bottom=Math.min(h-22,center+span);
 ctx.clearRect(0,0,w,h);
 ctx.fillStyle='#244736';ctx.fillRect(0,0,w,h);
 ctx.fillStyle='#e3dfbe';ctx.fillRect(0,top,w,bottom-top);
 ctx.fillStyle='#79a65d';ctx.fillRect(0,top+13,w,bottom-top-26);
 ctx.strokeStyle='#f8f5e3';ctx.lineWidth=3;
 for(const y of [top+13,bottom-13]){
  ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();
 }
 const goalX=turn==='右'?w*.30:w*.70;
 drawGoalPost(ctx,goalX,top+13,bottom-13);
 const markers=[];
 for(const p of points.slice().sort((a,b)=>
  Number(a.number===focusedNo)-Number(b.number===focusedNo)||a.number-b.number)){
  const q=goalScreenPosition(p.d,p.lane,distance,w,h,maxLane,turn,pullback);
  const scale=.81,rad=13.5*scale;
  if(q.x<-rad||q.x>w+rad||q.y<-rad||q.y>h+rad)continue;
  paintNumber(ctx,p.number,q.x,q.y,scale,p.number===focusedNo,
   p.number===leaderNo,fieldSize,false);
  markers.push({number:p.number,x:q.x,y:q.y,d:p.d});
 }
 return {mode:'kyoto1400-goal-camera',goalX,top,bottom,
  markers,visible:markers.length,pullback,leaderD:Math.max(...points.map(p=>p.d))};
}
global.RaceCleanGoalView=Object.freeze({goalScreenPosition,drawGoalPost,render,laneStep});
})(typeof window!=='undefined'?window:globalThis);
