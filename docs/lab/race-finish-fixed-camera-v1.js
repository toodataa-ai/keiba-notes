/* LAB fixed finish photography viewport.
 * Static background is rasterized ONCE per viewport geometry and reused
 * unchanged; only numerals advance using immutable physical distance/lane.
 * All races share this renderer. Venue imagery/style and orientation are
 * descriptive data, never race physics or per-corner position patches.
 */
(function(root){'use strict';
const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
const SWITCH_REMAINING_M=60;
function layout({width,height,turn='右',maxLane=14}){
 if(!(width>0&&height>0&&maxLane>=1))throw Error('FINISH_FRAME_INVALID');
 const right=turn==='右',boardX=width*(right?.22:.78);
 // At 60m out a typical 20-25m spread fits on a small phone without
 // altering individual runner positions or adjusting zoom mid-race.
 const pixelsPerMetre=clamp((width*.78-18)/(SWITCH_REMAINING_M+25),2.35,7.0);
 const innerRailY=height*.14,outerRailY=height*.88;
 const laneStep=(outerRailY-innerRailY-28)/maxLane;
 return Object.freeze({width,height,turn,boardX,pixelsPerMetre,
   laneStep,lane0Y:innerRailY+14,innerRailY,outerRailY,maxLane,
   switchRemainingM:SWITCH_REMAINING_M});
}
function project(h,{distance,frame}){
 if(!Number.isFinite(h.d)||!Number.isFinite(h.lane))
  throw Error('FINISH_HORSE_POSITION_INVALID');
 const remaining=distance-h.d;
 return {number:h.number,d:h.d,lane:h.lane,remaining,
  x:frame.boardX+(frame.turn==='右'?1:-1)*remaining*frame.pixelsPerMetre,
  y:frame.lane0Y+clamp(h.lane,0,frame.maxLane)*frame.laneStep};
}
function create({venueLabel='KYOTO',turn='右',maxLane=14}={}){
 let cache=null,backgroundBuilds=0,lastResult=null;
 function drawBackground(ctx,frame){
  const {width:w,height:h,boardX:x,innerRailY:y1,outerRailY:y2}=frame;
  // Fixed track-level illustration, not a moving map or a fabricated SVG
  // course route. The source map and race positions are untouched.
  ctx.fillStyle='#e3ece4';ctx.fillRect(0,0,w,h);
  const sky=ctx.createLinearGradient(0,0,0,y1);
  sky.addColorStop(0,'#cbdad2');sky.addColorStop(1,'#e6eee3');
  ctx.fillStyle=sky;ctx.fillRect(0,0,w,y1);
  ctx.fillStyle='#286347';ctx.fillRect(0,y1,w,y2-y1);
  for(let band=0;band<9;band++){
   ctx.fillStyle=band%2?'rgba(208,240,170,.11)':'rgba(12,54,23,.09)';
   ctx.fillRect(band*w/9,y1,w/9,y2-y1);
  }
  const turf=ctx.createLinearGradient(0,y1,0,y2);
  turf.addColorStop(0,'rgba(139,196,88,.45)');
  turf.addColorStop(.5,'rgba(125,194,85,.13)');
  turf.addColorStop(1,'rgba(15,94,53,.34)');
  ctx.fillStyle=turf;ctx.fillRect(0,y1,w,y2-y1);
  ctx.strokeStyle='#fbfff8';ctx.lineWidth=3;
  for(const y of [y1,y2]){
   ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();
  }
  ctx.strokeStyle='rgba(5,35,25,.28)';ctx.lineWidth=1;
  for(const y of [y1+4,y2+4]){
   ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();
  }
  // The finish line and its architecture occupy ONE immutable position.
  for(let y=y1+3,row=0;y<y2-3;y+=10,row++){
   ctx.fillStyle=row%2?'#edf8e9':'#173e30';
   ctx.fillRect(x-2,y,4,10);
  }
  if(!root.RaceFinishBroadcastV2?.drawGoalBoard)
   throw Error('FINISH_GOAL_ARCH_MISSING');
  root.RaceFinishBroadcastV2.drawGoalBoard(ctx,{
   x,top:y1-24,bottom:y1+131,venueLabel
  });
  // Keep top-right clear: the persistent race clock occupies this region.
 }
 function render({canvas,points,distance,paintNumber,focusedNo}){
  if(!canvas||!Array.isArray(points)||!points.length||
    typeof paintNumber!=='function'||!(distance>0))
   throw Error('FIXED_FINISH_CAMERA_INPUT_INVALID');
  const rect=canvas.getBoundingClientRect(),w=Math.max(1,rect.width),
   h=Math.max(1,rect.height),dpr=clamp(root.devicePixelRatio||1,1,2.5);
  const cw=Math.round(w*dpr),ch=Math.round(h*dpr);
  const key=cw+':'+ch+':'+turn+':'+maxLane+':'+venueLabel;
  if(!cache||cache.key!==key){
   const frame=layout({width:w,height:h,turn,maxLane});
   const bitmap=document.createElement('canvas');
   bitmap.width=cw;bitmap.height=ch;
   const ctx=bitmap.getContext('2d');
   ctx.setTransform(cw/w,0,0,ch/h,0,0);
   drawBackground(ctx,frame);
   cache={key,bitmap,frame};
   backgroundBuilds++;
  }
  if(canvas.width!==cw||canvas.height!==ch){canvas.width=cw;canvas.height=ch}
  const ctx=canvas.getContext('2d');
  ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,cw,ch);
  ctx.drawImage(cache.bitmap,0,0); // identical across all race times
  ctx.setTransform(cw/w,0,0,ch/h,0,0);
  const projected=points.map(p=>project(p,{distance,frame:cache.frame}));
  const shown=projected.filter(p=>p.x>=-18&&p.x<=w+18&&
    p.y>=-18&&p.y<=h+18);
  for(const p of shown)paintNumber(ctx,p.number,p.x,p.y,.84,
    p.number===focusedNo);
  const leading=Math.max(...points.map(p=>p.d));
  lastResult=Object.freeze({
   mode:'fixed-finish-background',backgroundFixed:true,
   backgroundBuilds,boardX:cache.frame.boardX,
   pixelsPerMetre:cache.frame.pixelsPerMetre,
   laneStep:cache.frame.laneStep,backgroundKey:key,
   remaining:distance-leading,visible:shown.length,
   projected,markers:shown,venueLabel,
   sourceRacePhysicsUnchanged:true,originalSVGUnchanged:true
  });
  return lastResult;
 }
 return Object.freeze({render,metrics:()=>lastResult,layout,project,
  reset:()=>{lastResult=null}});
}
root.RaceFinishFixedCamera=Object.freeze({
 create,layout,project,transitionRemainingM:SWITCH_REMAINING_M,
 backgroundStatic:true,physicalPositionsUnchanged:true,
 courseIndependent:true
});
})(typeof window!=='undefined'?window:globalThis);
