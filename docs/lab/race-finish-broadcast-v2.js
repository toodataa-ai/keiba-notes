/* Shared finish-line broadcast camera v2.
 * Referenced from Kyoto's real green-and-white finish arch, but drawn as a
 * neutral vector interpretation — no photographic image substitution.
 * All race tracks reuse the same renderer; venue label/theme are data only.
 * Entirely presentational; RaceSimEngine determines actual finish timings.
 */
(function(g){'use strict';
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
/* TV camera follows the pack until the board enters the picture.
 * A previous fixed goal board stretched 215 metres across one screen:
 * actual 22m gaps appeared as only 40px on a phone, compressing the pack.
 * This camera uses one truthful metres->px scale and moves its viewpoint;
 * no stretching of individual horses or change to physics gaps.
 */
function packCamera({points,distance,width,height=336,turn='右'}){
 const leader=Math.max(...points.map(p=>p.d)),last=Math.min(...points.map(p=>p.d));
 const right=turn==='右',gap=Math.max(0,leader-last);
 // Crop like an actual TV zoom: keep 20-25m of racing pack readable
 // rather than squeezing a whole 215m stretch into one camera image.
 const scale=clamp(width/43,7.2,9.0);
 const fixedGoalX=width*(right?.20:.80),leadX=width*(right?.42:.58);
 // Vertical zoom on the actual active lanes, NOT a per-horse lane edit.
 const minLane=Math.min(...points.map(p=>p.lane??0)),
  maxLane=Math.max(...points.map(p=>p.lane??0)),
  laneCenter=(minLane+maxLane)/2,
  laneStep=clamp((height-115)/(maxLane-minLane+1.5),16,30);
 const remaining=distance-leader;
 const natural=leadX+(right?-1:1)*remaining*scale;
 // Once the board reaches its broadcast-safe position it remains fixed;
 // horses keep crossing at the exact distance-proportional screen speed.
 const goalX=right?Math.min(fixedGoalX,natural):Math.max(fixedGoalX,natural);
 return {goalX,leader,last,gap,pxPerMetre:scale,remaining,
  laneCenter,laneStep,minLane,maxLane,
  cameraMode:Math.abs(goalX-fixedGoalX)<1e-6?'fixed-finish':'tracking-pack'};
}
function goalScreenPosition(d,lane,distance,width,height,maxLane,turn='右',camera){
 const view=camera??packCamera({points:[{d,lane}],distance,width,height,turn});
 return {x:view.goalX+(turn==='右'?1:-1)*(distance-d)*view.pxPerMetre,
  y:height*.59+(lane-view.laneCenter)*view.laneStep};
}
function drawGoalBoard(ctx,{x,top,bottom,venueLabel='KYOTO'}){
 // Actual Kyoto finish apparatus has a deep-green/white double arched
 // silhouette, with KYOTO on its vertical column and floodlights.
 // Stylization is deterministic, vectorial and scalable.
 const h=Math.max(64,Math.min(88,bottom-top-54)),width=51;
 const y=top+12,cy=y+45;
 ctx.save();
 ctx.shadowColor='rgba(13,40,25,.23)';ctx.shadowBlur=5;ctx.shadowOffsetX=2;
 ctx.strokeStyle='#174b3b';ctx.lineWidth=15;ctx.lineCap='round';
 ctx.beginPath();ctx.moveTo(x-width*.48,y+h);
 ctx.lineTo(x-width*.48,cy);
 ctx.bezierCurveTo(x-width*.50,y-4,x+width*.50,y-4,x+width*.48,cy);
 ctx.lineTo(x+width*.48,y+h);ctx.stroke();
 ctx.shadowBlur=0;ctx.shadowOffsetX=0;
 ctx.strokeStyle='#fafdf3';ctx.lineWidth=9;
 ctx.beginPath();ctx.moveTo(x-width*.48,y+h);
 ctx.lineTo(x-width*.48,cy);
 ctx.bezierCurveTo(x-width*.50,y-4,x+width*.50,y-4,x+width*.48,cy);
 ctx.lineTo(x+width*.48,y+h);ctx.stroke();
 ctx.strokeStyle='#174b3b';ctx.lineWidth=3;
 ctx.beginPath();ctx.moveTo(x-width*.31,y+h);
 ctx.lineTo(x-width*.31,cy+9);
 ctx.bezierCurveTo(x-width*.30,y+22,x+width*.30,y+22,x+width*.31,cy+9);
 ctx.lineTo(x+width*.31,y+h);ctx.stroke();
 // Stable timing device and racecourse wordmark: not a JRA trademark copy.
 ctx.fillStyle='#173e32';
 ctx.fillRect(x-4,y+29,8,h-23);
 ctx.fillStyle='#184b3b';ctx.font='bold 8px Arial,sans-serif';
 ctx.textBaseline='middle';ctx.textAlign='center';
 const vertical=String(venueLabel).slice(0,6).split('');
 for(let i=0;i<vertical.length;i++)ctx.fillText(vertical[i],x+width*.48,y+42+i*9);
 ctx.fillStyle='#172b24';ctx.fillRect(x-3,y-14,6,16);
 for(let row=0;row<2;row++)for(let col=0;col<3;col++){
  ctx.fillStyle='#1d3e35';ctx.fillRect(x-13+col*10,y-30+row*11,7,8);
  ctx.fillStyle='#edf5dd';ctx.fillRect(x-11+col*10,y-28+row*11,3,4);
 }
 ctx.restore();
}
function render({canvas,points,paintNumber,focusedNo,leaderNo,turn='右',distance,
 maxLane=14,venueLabel='KYOTO'}){
 if(!(distance>0)||!Array.isArray(points)||!canvas)throw Error('GOAL_CAMERA_ARGS_INVALID');
 const rect=canvas.getBoundingClientRect(),w=Math.max(1,rect.width),
 h=Math.max(1,rect.height),pixelRatio=clamp(g.devicePixelRatio||1,1,2.5);
 const cw=Math.round(w*pixelRatio),ch=Math.round(h*pixelRatio);
 if(canvas.width!==cw||canvas.height!==ch){canvas.width=cw;canvas.height=ch}
 const ctx=canvas.getContext('2d');ctx.setTransform(cw/w,0,0,ch/h,0,0);
 ctx.clearRect(0,0,w,h);
 // Green grandstand side camera with light mowing stripes, visible white
 // inner/outer rails and an accurate linear distance-to-finish axis.
 ctx.fillStyle='#204634';ctx.fillRect(0,0,w,h);
 const camera=packCamera({points,distance,width:w,height:h,turn});
 // Entire vertical viewport follows the occupied racing lanes. Both
 // rail lines are viewport framing guides, not reconstructed source rails.
 const innerY=Math.max(10,h*.59+(camera.minLane-camera.laneCenter-1.3)*camera.laneStep);
 const outerY=Math.min(h-10,h*.59+(camera.maxLane-camera.laneCenter+1.3)*camera.laneStep);
 ctx.fillStyle='#72a75e';ctx.fillRect(0,innerY,w,outerY-innerY);
 for(let i=0;i<7;i++){
  ctx.fillStyle=i%2?'rgba(243,253,235,.045)':'rgba(9,65,20,.065)';
  ctx.fillRect(i*w/7,innerY,w/7,outerY-innerY);
 }
 ctx.strokeStyle='#e9f7df';ctx.lineWidth=3;
 for(const y of [innerY,outerY]){
  ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();
 }
 const x=camera.goalX;
 // Thin checkered winning line across all lanes, visible UNDER the horses.
 for(let y=innerY+2,part=0;y<outerY-2;y+=9,part++){
  ctx.fillStyle=part%2?'rgba(251,252,244,.88)':'rgba(21,47,34,.9)';
  ctx.fillRect(x-2,y,4,9);
 }
 // Draw the finish architecture behind runners; it visually sits at the
 // near-side course boundary rather than pretending to bridge the track.
 drawGoalBoard(ctx,{x,top:innerY-26,bottom:innerY+140,venueLabel});
 ctx.save();ctx.fillStyle='rgba(13,39,30,.83)';
 ctx.beginPath();ctx.roundRect(9,9,130,23,5);ctx.fill();
 ctx.fillStyle='#fff';ctx.font='bold 12px Arial,sans-serif';
 ctx.textBaseline='middle';ctx.textAlign='left';ctx.fillText('ゴール前・アップ映像',17,21);
 ctx.restore();
 const markers=[];
 for(const p of points){
  const q=goalScreenPosition(p.d,p.lane,distance,w,h,maxLane,turn,camera);
  const scale=.95,rad=13.5*scale;
  if(q.x<-rad||q.x>w+rad||q.y<-rad||q.y>h+rad)continue;
  paintNumber(ctx,p.number,q.x,q.y,scale,p.number===focusedNo);
  markers.push({number:p.number,x:q.x,y:q.y,d:p.d});
 }
 return {mode:'finish-100m-camera',goalX:x,visible:markers.length,
  markers,remaining:Math.max(0,camera.remaining),venueLabel,
  physicalSpreadM:camera.gap,visualSpreadPx:camera.gap*camera.pxPerMetre,
  pxPerMetre:camera.pxPerMetre,cameraMode:camera.cameraMode,
  laneStep:camera.laneStep,activeLaneRange:[camera.minLane,camera.maxLane]};
}
g.RaceFinishBroadcastV2=Object.freeze({render,goalScreenPosition,drawGoalBoard,
  packCamera,transitionRemainingM:100,sourceGeometryIndependent:true,
  physicalResultsUnchanged:true,physicalGapScaleLinear:true});
})(typeof window!=='undefined'?window:globalThis);
