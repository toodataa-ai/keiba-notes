/* Race Lane Decision v0.7 — safe inward convergence, deterministic hypothesis, not horse tracking data.
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
function plan(h,horses,cfg,m,bias,t){
 const front=nearestAhead(h,horses),gap=front?front.d-h.d:Infinity;
 const straight=Boolean(m.isFinalStraight);
 const blocked=Boolean(front&&gap<(straight?13:5.2));
 h.blocked=blocked;
 if(Math.abs(h.lane-h.desiredLane)>.07)return null;
 const cooldown=straight?.75:m.bend>.5?1.25:1.35;
 if(t-h.lastChange<cooldown||h.d<8)return null;
 const old=h.lane,packMax=cfg.packMaxLane??3.45;
 function route(target,mode,reason,frontBuffer=6,backBuffer=4.5){
  if(Math.abs(target-old)<.29||target<0||target>cfg.maxLane||
     !laneSafe(h,horses,target,cfg))return null;
  const ahead=nearestAhead(h,horses,target);
  if(ahead&&ahead.d-h.d<frontBuffer)return null;
  if(horses.some(o=>o!==h&&!o.finished&&o.d<h.d&&h.d-o.d<backBuffer&&
    Math.abs(o.lane-target)<.77))return null;
  if(mode==='inward'&&old<=packMax+.25){
   // Leave several running files, rather than filling only the inner rail.
   const crowded=horses.filter(o=>o!==h&&!o.finished&&Math.abs(o.d-h.d)<28&&
     Math.abs(o.lane-target)<.72).length;
   const capacity=target<.7?4:target<1.7?5:6;
   if(crowded>=capacity)return null;
  }
  return {lane:target,mode,reason,avoids:blocked,scoreGain:1};
 }
 if(!straight){
  // Always pursue a SAFE open inner line before turning into the straight.
  // The starting gate's preferredLane is NOT a lower bound.
  for(const distance of [1,.70,.45,1.30]){
   const inside=route(Math.max(0,old-distance),'inward',
     'inner-first-before-straight',7.5,4.8);
   if(inside)return inside;
  }
  // Pre-straight outside movement is an emergency exception only: directly
  // blocked and the inside corridor is unavailable. Maximum fifth line.
  if(blocked&&gap<5.1&&old<packMax+.15){
   const shoulder=Math.min(cfg.passMaxLane??cfg.maxLane,packMax+.75);
   const outside=route(Math.min(shoulder,old+1),'outward',
     'blocked-no-inner-route',6.5,4.5);
   if(outside)return outside;
  }
  return null;
 }
 // Upon entering the home straight, overtaking lines can widen.
 if(!blocked&&old>.35){
  const inside=route(Math.max(0,old-1),'inward','straight-inner-clear');
  if(inside)return inside;
 }
 if(blocked){
  for(const spread of [1,1.7]){
   const outside=route(Math.min(cfg.passMaxLane??cfg.maxLane,old+spread),
     'outward','straight-outside-pass',7,4.5);
   if(outside)return outside;
  }
  if(old>.35)return route(Math.max(0,old-1),'inward','straight-inner-pass',7,4.5);
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
