/* Reusable broadcast-only pose anti-jitter, independent of race/venue.
 * Physical and overview points stay raw; only close-up image coordinates are
 * eased against temporal spikes in source SVG path projection.
 * Exactly same race timestamp => exactly same screen pose, even after 20 paints.
 */
(function(global){'use strict';
const TAU_SECONDS=.055,MAX_DEVIATION_SOURCE_PX=1.15;
function create(){
 const byNumber=new Map();let lastTime=null;
 function reset(){byNumber.clear();lastTime=null}
 function apply(physicalPoints,{timeSeconds,containsDisc}={}){
  if(!Number.isFinite(timeSeconds)||!Array.isArray(physicalPoints))
   throw Error('BROADCAST_POSE_INPUT_INVALID');
  if(lastTime!==null&&timeSeconds<lastTime-1e-6)reset();
  const delta=lastTime===null?0:Math.max(0,Math.min(.4,timeSeconds-lastTime));
  const weight=1-Math.exp(-delta/TAU_SECONDS);
  const out=physicalPoints.map(p=>{
   const prev=byNumber.get(p.number);
   if(!Number.isFinite(p.x)||!Number.isFinite(p.y))throw Error('POSE_NOT_FINITE');
   if(!prev){byNumber.set(p.number,{x:p.x,y:p.y});return {...p}}
   let x=prev.x+(p.x-prev.x)*weight,y=prev.y+(p.y-prev.y)*weight;
   const dx=x-p.x,dy=y-p.y,lag=Math.hypot(dx,dy);
   // Important: limit the visible offset from exact physical course. Do not
   // distort actual track positions or arc-length calculations.
   if(lag>MAX_DEVIATION_SOURCE_PX){
    x=p.x+dx/lag*MAX_DEVIATION_SOURCE_PX;
    y=p.y+dy/lag*MAX_DEVIATION_SOURCE_PX;
   }
   if(typeof containsDisc==='function'&&!containsDisc(x,y)){x=p.x;y=p.y}
   byNumber.set(p.number,{x,y});
   return {...p,x,y,unfilteredX:p.x,unfilteredY:p.y}
  });
  lastTime=timeSeconds;
  return out;
 }
 return Object.freeze({apply,reset,lastTime:()=>lastTime});
}
global.RaceBroadcastPoseFilter=Object.freeze({
 create,timeBased:true,physicalPositionImmutable:true,sourceDeviationCap:MAX_DEVIATION_SOURCE_PX,courseIndependent:true
});
})(typeof window!=='undefined'?window:globalThis);
