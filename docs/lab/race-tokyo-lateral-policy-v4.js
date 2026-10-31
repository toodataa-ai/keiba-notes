/* Explicit opt-in Tokyo LAB candidate only. No result/time/rank targets.
 * Bounds below are engineering hypotheses, not official horse measurements. */
(function(g){'use strict';
const ID='bounded-lateral-v4';
const LIMITS=Object.freeze({maxSpeedMps:1.2,maxAccelerationMps2:.8,bodyWidthM:.8,sideBufferM:.35,lookaheadSeconds:1.5,nearForeM:8,runoffSpeedMps:14.2});
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function create(data,cfg){
 if(data.course_id!=='tokyo_turf_2000'||data.labTokyoMotion!==ID||data.scope!=='LAB_SYNTHETIC_NOT_OFFICIAL'||
    data.horses.length!==18||data.horses.some(h=>h.styleMeta?.source!=='LAB_SYNTHETIC_NOT_OFFICIAL'))
  throw Error('TOKYO_LATERAL_OPT_IN_INVALID');
 // Source-linked candidate reserves extra room for sequential runner updates.
 // The v4/default path retains its original .35m side buffer.
 const sideBuffer=data.labTokyoSourceModel==='source-linked-v5'?.55:LIMITS.sideBufferM;
 const laneM=cfg.laneWidthM,velocity=new Map(),pending=new Map(),snapshot=new Map(),previous=new Map();
 let lastTime=null;
 const stats={id:ID,emergencyStops:0,limitedSteps:0,maxPlannedSpeedMps:0};
 function beginStep(horses,dt,t){
  snapshot.clear();pending.clear();
  for(const h of horses){const old=previous.get(h.number),elapsed=lastTime===null?dt:t-lastTime;
   const foreSpeed=old?Math.max(0,(h.d-old.d)/elapsed):0;
   snapshot.set(h.number,{d:h.d,lane:h.lane,finished:h.finished,foreSpeed});
   previous.set(h.number,{d:h.d,lane:h.lane});
  }
  lastTime=t;
 }
 function propose(h,targetLane,dt){
  const own=snapshot.get(h.number),v=velocity.get(h.number)||0,error=(targetLane-h.lane)*laneM;
  const sign=Math.sign(error),a=LIMITS.maxAccelerationMps2;
  let room=Math.abs(error),limit=LIMITS.maxSpeedMps;
  for(const [number,other] of snapshot){
   if(number===h.number||other.finished)continue;
   const otherV=velocity.get(number)||0;
   if(Math.abs(other.d-own.d)>LIMITS.nearForeM+Math.abs(other.foreSpeed-own.foreSpeed)*LIMITS.lookaheadSeconds)continue;
   const side=(other.lane-h.lane)*laneM;
   if(side*sign<=0)continue;
   // Reserve the other runner's stopping distance only if it moves toward us.
   const approaching=otherV*side<0?Math.abs(otherV):0;
   const reserve=approaching*dt+approaching*approaching/(2*a);
   room=Math.min(room,Math.max(0,Math.abs(side)-LIMITS.bodyWidthM-sideBuffer-reserve));
  }
  limit=Math.min(limit,Math.sqrt(Math.max(0,2*a*room)));
  // One-step anticipation avoids reaching a stopping envelope too late.
  limit=Math.max(0,limit-a*dt);
  const desired=sign*limit,next=clamp(desired,v-a*dt,v+a*dt);
  let movement=(v+next)*.5*dt/laneM;
  if(Math.sign(movement)===sign&&Math.abs(movement)>Math.abs(error/laneM))movement=error/laneM;
  const lane=clamp(h.lane+movement,0,cfg.maxLane);
  pending.set(h.number,{next,proposedMovement:lane-h.lane,dt});
  if(Math.abs(next)<LIMITS.maxSpeedMps-1e-9)stats.limitedSteps++;
  stats.maxPlannedSpeedMps=Math.max(stats.maxPlannedSpeedMps,Math.abs(next));
  return lane;
 }
 function commit(h,actualMovement){
  const plan=pending.get(h.number);if(!plan)return;
  if(Math.abs(actualMovement-plan.proposedMovement)>1e-8){
   if(Math.abs(velocity.get(h.number)||0)>.02)stats.emergencyStops++;
   velocity.set(h.number,0);
  }else if(Math.abs(actualMovement)<1e-10)velocity.set(h.number,0);
  else velocity.set(h.number,plan.next);
 }
 function limitTravel(h,horses,original,dt,t){
  let distance=original.distance;
  if(data.labTokyoSourceModel==='source-linked-v5'){
   // Match forward clearance to the wider lateral stopping envelope. Otherwise
   // a faster follower can enter LaneAI's side corridor while its neighbour is
   // already braking sideways, forcing an instantaneous lateral stop.
   for(const other of horses){
    if(other===h||other.finished||other.d<h.d)continue;
    if(Math.abs(other.lane-h.lane)*laneM>=LIMITS.bodyWidthM+sideBuffer)continue;
    distance=Math.min(distance,Math.max(0,other.d-cfg.minimumLongitudinalM-h.d));
   }
  }
  // The shared loop marks a leading runner finished before processing followers.
  // Keep that real runner's current runoff position in the clearance calculation.
  // Without this, a follower may advance through it during the same physical tick.
  for(const other of horses){
   if(other===h||!other.finished||other.displayD<h.d)continue;
   if(Math.abs(other.lane-h.lane)*laneM>=LIMITS.bodyWidthM+LIMITS.sideBufferM)continue;
   distance=Math.min(distance,Math.max(0,other.displayD-cfg.minimumLongitudinalM-h.d));
   const crossingFraction=(other.finishTime-(t-dt))/dt;
   if(crossingFraction>0&&crossingFraction<1){
    // Check the exact wire-crossing instant as well as the end of this tick.
    // A traffic-held leader can be slower before crossing than its initial runoff speed.
    distance=Math.min(distance,Math.max(0,(data.distance_m-cfg.minimumLongitudinalM-h.d)/crossingFraction));
   }
  }
  return {distance,held:original.held||distance+1e-6<original.distance};
 }
 function postFinishTravel(seconds){
  // Continue at the shared model's initial runoff speed until all runners clear
  // the runoff zone. Equal constant speeds preserve the physically secured gap;
  // separate exponential deceleration would shrink it after the wire.
  return LIMITS.runoffSpeedMps*Math.max(0,seconds);
 }
 return Object.freeze({beginStep,propose,commit,limitTravel,postFinishTravel,stats});
}
g.RaceTokyoLateralV4=Object.freeze({ID,LIMITS,create});
})(typeof window!=='undefined'?window:globalThis);
