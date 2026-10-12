/* Race Lane Decision v0.4 — safe inward convergence, deterministic hypothesis, not horse tracking data.
   Lane 0 is the inside rail on both turn directions.
   Model minimum observed JRA course width, leave safety buffers and score
   inward distance savings against traffic and safe overtaking room. */
(function(global){
'use strict';
const clamp=(x,lo,hi)=>Math.min(hi,Math.max(lo,x));
const LANE_METRES=1.65, HORSE_LENGTH_M=2.55;
function config(profile){
 if(!profile||!Array.isArray(profile.track_width_m))throw Error('LANE_WIDTH_SOURCE_MISSING');
 const minWidth=Math.min(...profile.track_width_m);
 const maxLane=clamp(Math.floor((minWidth-3.6)/LANE_METRES),7,18);
 return Object.freeze({minWidth,maxLane,laneWidthM:LANE_METRES,minimumLongitudinalM:HORSE_LENGTH_M});
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
 const m=courseMetrics;
 const front=nearestAhead(h,horses);
 // Straight runners plan a pass before they are fully boxed in. A blocked
 // finisher needs an alternative LINE, not a position teleport or speed cheat.
 const finalStraight=Boolean(m.isFinalStraight);
 const obstructed=Boolean(front && front.d-h.d<(finalStraight?12.5:7.5));
 h.blocked=obstructed;
 if(Math.abs(h.lane-h.desiredLane)>.07)return null;
 // Each move is gradual (engine clamps lateral velocity); check the whole
 // crossing corridor and the space ahead before choosing a route.
 const cooldown=finalStraight?.65:m.bend>.5?1.50:1.0;
 if(t-h.lastChange<cooldown || h.d<8)return null;
 const old=h.lane;
 function freeForward(lane,buffer){
   const other=nearestAhead(h,horses,lane);
   return !other || other.d-h.d>=buffer;
 }
 function route(lane,mode,reason){
   if(Math.abs(lane-old)<.35||!laneSafe(h,horses,lane,cfg))return null;
   if(!freeForward(lane,8.5))return null;
   return {lane,mode,avoids:obstructed,scoreGain:1,reason};
 }
 // A fast finisher in the home straight must consider free outside lines
 // BEFORE continuing its automatic inward drift into a boxed-in lane.
 // Test more than one outside target: the adjacent lane may be occupied.
 if(finalStraight&&obstructed){
   for(const spread of [1,2,3]){
     const outside=route(Math.min(cfg.maxLane,old+spread),'outward','home-straight-pass');
     if(outside)return outside;
   }
 }
 // Before the final straight: shorter inside arcs remain the default.
 // In the straight, a clear inside lane is still a valid passing route.
 // "外有利" can keep a useful wider line on the final straight, but
 // cannot push a free runner out arbitrarily at every tick.
 const preferInside=bias!=='outer'||m.bend>.22||old>4;
 if(preferInside&&old>.38){
   const inside=route(Math.max(0,old-1),'inward','clear-inner');
   if(inside)return inside;
 }
 // A blocked horse sometimes has to peel to the outside to pass;
 // avoid inventing large outward moves when no traffic needs passing.
 if(obstructed&&old<cfg.maxLane-.35){
   const outside=route(Math.min(cfg.maxLane,old+1),'outward','outside-pass');
   if(outside)return outside;
 }
 // In an outer-biased straight, allow moves toward the rail only
 // when the lane remains conspicuously wide (left of the default
 // target in clock-face terms). This never overrides safety.
 if(bias==='outer'&&old>4.5){
   const inside=route(Math.max(0,old-1),'inward','reduce-excess-width');
   if(inside)return inside;
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
