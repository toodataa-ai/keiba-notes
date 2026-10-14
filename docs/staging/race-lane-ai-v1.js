/* Race Lane Decision v0.6 — safe inward convergence, deterministic hypothesis, not horse tracking data.
   Lane 0 is the inside rail on both turn directions.
   Model minimum observed JRA course width, leave safety buffers and score
   inward distance savings against traffic and safe overtaking room. */
(function(global){
'use strict';
const clamp=(x,lo,hi)=>Math.min(hi,Math.max(lo,x));
const LANE_METRES=1.65, HORSE_LENGTH_M=2.55;
const PACK_MAX_LANE=3.45, PASS_MAX_LANE=5.35;
function config(profile){
 if(!profile||!Array.isArray(profile.track_width_m))throw Error('LANE_WIDTH_SOURCE_MISSING');
 const minWidth=Math.min(...profile.track_width_m);
 const maxLane=clamp(Math.floor((minWidth-3.6)/LANE_METRES),7,18);
 return Object.freeze({minWidth,maxLane,packMaxLane:Math.min(PACK_MAX_LANE,maxLane),passMaxLane:Math.min(PASS_MAX_LANE,maxLane),laneWidthM:LANE_METRES,minimumLongitudinalM:HORSE_LENGTH_M});
}
function distances(a,b){
 return {fore:a.d-b.d,side:Math.abs(a.lane-b.lane)};
}
function nearAt(h,other,sideLane,forwardDistance=8){
 if(other===h||other.finished)return false;
 const side=Math.abs(other.lane-sideLane);
 // A horse is about 0.8m wide. Lateral half-width in model lane units
 // leaves a buffer to avoid overlapping when crossing another lane.
 return side<.72 && other.d>=h.d-2.5&&other.d<=h.d+forwardDistance;
}
function laneSafe(h,horses,toLane,cfg){
 if(toLane<0 || toLane>cfg.maxLane)return false;
 const origin=h.lane;
 const steps=Math.max(1,Math.ceil(Math.abs(toLane-origin)/.30));
 for(let t=1;t<=steps;t++){
   const lateral=origin+(toLane-origin)*t/steps;
   for(const other of horses){
     if(other===h||other.finished)continue;
     // A minimum of 3.5m of fore-aft clearing room for lane crossings.
     // Look ahead to avoid squeezing in front of a closely following horse.
     if(Math.abs(other.lane-lateral)<.84 && Math.abs(other.d-h.d)<3.5)return false;
   }
 }
 return true;
}
function nearestAhead(h,horses,atLane=h.lane){
 return horses.filter(o=>o!==h&&!o.finished&&o.d>=h.d-.01&&
   Math.abs(o.lane-atLane)<.62).sort((a,b)=>a.d-b.d||a.number-b.number)[0]||null;
}
function plan(h,horses,cfg,courseMetrics,bias,t){
 const m=courseMetrics,front=nearestAhead(h,horses);
 const gap=front?front.d-h.d:Infinity;
 const inStraight=Boolean(m.isFinalStraight);
 const toHome=Number.isFinite(m.toFinalStraight)?m.toFinalStraight:Infinity;
 const tactical=inStraight||toHome<=145;
 const blocked=Boolean(front&&gap<(tactical?12:5.2));
 h.blocked=blocked;
 if(Math.abs(h.lane-h.desiredLane)>.07)return null;
 const cooldown=inStraight?.75:tactical?1.25:m.bend>.5?2.1:1.4;
 if(t-h.lastChange<cooldown||h.d<8)return null;
 const old=h.lane;
 const preferred=Number.isFinite(h.preferredLane)?h.preferredLane:null;
 function route(target,mode,reason,buffer=3.5){
  if(Math.abs(target-old)<.26||!laneSafe(h,horses,target,cfg))return null;
  const next=nearestAhead(h,horses,target);
  if(next&&next.d-h.d<buffer)return null;
  return {lane:target,mode,reason,avoids:blocked,scoreGain:1};
 }
 // PRE-RACE horses hold one of four individual pack lanes. Crowded bends
 // must not funnel all runners into a literal single-file rail procession.
 if(preferred!==null&&old>preferred+.36){
  const target=route(Math.max(preferred,old-1),'inward','return-to-pack');
  if(target)return target;
 }
 // Preserve existing standalone lane tests without preferredLane metadata.
 if(m.bend>.25&&old>cfg.packMaxLane+.4&&(bias!=='outer'||old>cfg.passMaxLane)){
  const inner=route(Math.max(cfg.packMaxLane,old-1),'inward','outer-turn-saving');
  if(inner)return inner;
 }
 if(preferred===null&&m.bend>.25&&old>1&&!blocked){
  const inner=route(Math.max(0,old-1),'inward','clear-inside-turn');
  if(inner)return inner;
 }
 // For a standalone scenario keep the historic outside-pass option. In the
 // real 18-runner pack an available adjacent inner line is considered first.
 if(blocked&&(tactical||gap<=4.25)){
  const options=preferred===null?[Math.min(cfg.passMaxLane,old+1),Math.max(0,old-1)]:
    [Math.max(0,old-1),Math.min(cfg.packMaxLane,old+1)];
  for(const target of options){
   const action=route(target,target>old?'outward':'inward','packed-passing-lane',7);
   if(action)return action;
  }
  if(tactical&&gap<=5.2&&old<cfg.passMaxLane-.35){
   const outside=route(Math.min(cfg.passMaxLane,old+1),'outward','late-outside-shoulder',7);
   if(outside)return outside;
  }
 }
 if(preferred!==null&&old>cfg.packMaxLane+.28&&!blocked){
  const rejoin=route(Math.max(cfg.packMaxLane,old-1),'inward','rejoin-pack');
  if(rejoin)return rejoin;
 }
 return null;
}
/* The first 100m are a coordinated inward merge, rather than
   isolated adjacent-lane decisions. A convoy can shift laterally
   together, while immediate physical occupancy is still checked.
   No runner may jump an occupied lane or overtake through the other. */
function launchStepSafe(h,horses,nextLane,cfg){
 if(nextLane<0||nextLane>cfg.maxLane)return false;
 for(const other of horses){
   if(other===h||other.finished)continue;
   const gap=Math.abs(other.d-h.d);
   // Use next-frame (sub-step) clearance, not the entire multi-lane
   // corridor from gate to target: the latter prevented all outside
   // horses from joining an inward-moving pack.
   if(gap<2.45 && Math.abs(other.lane-nextLane)<.67)return false;
 }
 return true;
}
function throttle(h,horses,requestedTravel,dt,cfg){
 const front=nearestAhead(h,horses,h.lane);
 if(!front)return {distance:requestedTravel,held:false};
 const gap=front.d-h.d;
 const minimumGap=cfg.minimumLongitudinalM;
 const maxTravel=gap-minimumGap;
 // If overlap is already present (e.g. start gate or transitions), avoid
 // moving backwards; wait in lane instead of trying to move through another horse.
 const accepted=clamp(Math.min(requestedTravel,Math.max(0,maxTravel)),0,requestedTravel);
 return {distance:accepted,held:accepted+1e-6<requestedTravel};
}
global.RaceLaneAI=Object.freeze({config,distances,nearAt,laneSafe,nearestAhead,plan,launchStepSafe,throttle});
})(typeof window!=='undefined'?window:globalThis);
