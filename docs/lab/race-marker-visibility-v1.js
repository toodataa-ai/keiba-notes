/* Shared LAB marker visibility v32, presentation-only and course-agnostic.
 * Root cause fixed: old label solver re-optimized / eased at EVERY paint, so
 * higher FPS, pause/repaint and unstable overlap decisions created tremor.
 * This solver changes the target only after an elapsed RACE time interval,
 * and slews the display offsets using elapsed time, not frame count.
 * Identical simulated time is perfectly idempotent.
 */
(function(global){'use strict';
const MAX=18,CLEAR=24,REPLAN_SECONDS=2.4,SLEW_PX_PER_RACE_SEC=6;
const CANDIDATES=Object.freeze([0,-5,5,-9,9,-13,13,-18,18]);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function overlap(pts,distance=CLEAR){
 let penalty=0,pairs=0;
 for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){
  const distanceBetween=Math.hypot(pts[i].x-pts[j].x,pts[i].y-pts[j].y);
  const amount=Math.max(0,distance-distanceBetween);
  if(amount>1e-4){pairs++;penalty+=amount*amount}
 }
 return {pairs,penalty:Number(penalty.toFixed(4))};
}
function create({lockAfterFirstPlan=false}={}){
 const current=new Map(),goals=new Map(),normals=new Map(),stableSide=new Map();
 let replanTime=null,lastTime=null,metrics=null,planCount=0;
 function reset(){
  current.clear();goals.clear();normals.clear();stableSide.clear();
  replanTime=null;lastTime=null;metrics=null;planCount=0;
 }
 function layout(points,{normalAt,minimumDistance=CLEAR,timeSeconds}={}){
  if(!Array.isArray(points)||typeof normalAt!=='function'||
    !Number.isFinite(timeSeconds))throw Error('MARKER_TIME_AND_NORMAL_REQUIRED');
  if(lastTime!==null&&timeSeconds<lastTime-1e-6)reset();
  const dt=lastTime===null?0:clamp(timeSeconds-lastTime,0,.4);
  const horses=points.map(p=>{
   if(!Number.isInteger(p.number)||!Number.isFinite(p.x)||!Number.isFinite(p.y))
    throw Error('MARKER_SCREEN_POSE_INVALID');
   const raw=normalAt(p),m=Math.hypot(raw.x,raw.y)||1;
   const unit={x:raw.x/m,y:raw.y/m},prior=normals.get(p.number);
   if(!prior){normals.set(p.number,unit);return {...p,nx:unit.x,ny:unit.y}}
   // Camera/frame-rate independent angular velocity bound.
   const angle=Math.atan2(prior.x*unit.y-prior.y*unit.x,
    prior.x*unit.x+prior.y*unit.y);
   const step=clamp(angle,-dt*2.4,dt*2.4);
   const c=Math.cos(step),s=Math.sin(step),next={
    x:prior.x*c-prior.y*s,y:prior.x*s+prior.y*c
   };
   normals.set(p.number,next);
   return {...p,nx:next.x,ny:next.y};
  }).sort((a,b)=>a.number-b.number);
  if(replanTime===null||!lockAfterFirstPlan&&timeSeconds-replanTime>=REPLAN_SECONDS){
   const shifts=horses.map(h=>current.get(h.number)??0);
   function evaluate(i,candidate){
    const h=horses[i],x=h.x+h.nx*candidate,y=h.y+h.ny*candidate;
    const old=current.get(h.number)??0;
    let value=.045*candidate*candidate+.28*(candidate-old)**2;
    if(Math.abs(old)>6&&old*candidate<0)value+=65; // side-change hysteresis
    for(let j=0;j<horses.length;j++){
     if(i===j)continue;
     const other=horses[j];
     const ox=other.x+other.nx*shifts[j],oy=other.y+other.ny*shifts[j];
     value+=2.4*Math.max(0,minimumDistance-Math.hypot(x-ox,y-oy))**2;
    }
    return value;
   }
   for(let pass=0;pass<4;pass++)for(let i=0;i<horses.length;i++){
    let winner=shifts[i],best=evaluate(i,winner);
    for(const candidate of CANDIDATES){
     const side=stableSide.get(horses[i].number);
     // A flip between left/right label sides looks like a vibrating
     // marker even when a frequency-limited solver eases the transition.
     // Lock the first nonzero label side for this race, not a venue.
     if(side && candidate*side<0)continue;
     const score=evaluate(i,candidate);
     if(score<best-1e-7){best=score;winner=candidate}
    }
    shifts[i]=winner;
   }
   horses.forEach((h,i)=>{
    goals.set(h.number,shifts[i]);
    if(!stableSide.has(h.number)&&Math.abs(shifts[i])>3)
     stableSide.set(h.number,Math.sign(shifts[i]));
    if(!current.has(h.number))current.set(h.number,shifts[i]);
   });
   replanTime=timeSeconds;planCount++;
  }
  const result=horses.map(h=>{
   const old=current.get(h.number)??0,goal=goals.get(h.number)??old;
   const next=clamp(goal,old-SLEW_PX_PER_RACE_SEC*dt,
     old+SLEW_PX_PER_RACE_SEC*dt);
   current.set(h.number,next);
   return {...h,anchorX:h.x,anchorY:h.y,
    x:h.x+h.nx*next,y:h.y+h.ny*next,labelOffset:next};
  });
  lastTime=timeSeconds;
  const base=overlap(horses,minimumDistance),after=overlap(result,minimumDistance);
  metrics={base,after,maxShiftPx:Math.max(0,...result.map(h=>Math.abs(h.labelOffset))),
   displaced:result.filter(h=>Math.abs(h.labelOffset)>2).length,
   solverRuns:planCount,simulatedTime:timeSeconds,
   motionMode:lockAfterFirstPlan?'locked-per-race-label-targets':'stable-label-side-2.4s-race-time-replan-6px-sec',
   assignmentsFrozen:lockAfterFirstPlan,
   physicalPositionsUnchanged:true};
  return result;
 }
 return Object.freeze({layout,reset,metrics:()=>metrics});
}
global.RaceMarkerVisibility=Object.freeze({
 create,overlap,maxOffsetPx:MAX,replanSeconds:REPLAN_SECONDS,
 courseIndependent:true,paintIdempotent:true,simulationTimeDriven:true
});
})(typeof window!=='undefined'?window:globalThis);
