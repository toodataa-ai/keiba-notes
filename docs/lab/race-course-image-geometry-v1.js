/* LAB SHADOW v1 — shared distance-to-illustration geometry.
 * COURSE-INDEPENDENT. This module knows no venue, race, turf image URL,
 * turn location, horse or betting model. Registered course anchors and a
 * sampling callback are the only source data. Never modifies original SVG,
 * actual race physics, lane preference, horse positions or results.
 *
 * Output is a distance -> source-image parameter mapping. We derive the
 * map from the arclength of the source trace, with fully fixed anchors.
 * An optional course-independent numeric optimizer reduces abrupt image
 * chord expansion/compression for equally spaced real runners, by tuning
 * only interior anchor derivatives, never manually per-corner offsets.
 */
(function(global){'use strict';
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function cubic(t,start,end,m0,m1,length){
 const u=t/length,u2=u*u,u3=u2*u;
 return (2*u3-3*u2+1)*start+(u3-2*u2+u)*length*m0+
   (-2*u3+3*u2)*end+(u3-u2)*length*m1;
}
function build({distanceM,anchorsM,pointAt,lane=2,
 sampleM=1,enableGlobalOptimization=true,displayGain}){
 if(typeof pointAt!=='function'||!(distanceM>=100))
  throw Error('IMAGE_GEOMETRY_SOURCE_REQUIRED');
 const anchors=anchorsM.slice(), last=anchors.at(-1);
 if(anchors[0]!==0||Math.abs(last-distanceM)>1e-8||
    anchors.some((v,i)=>!Number.isFinite(v)||(i&&v<=anchors[i-1])))
  throw Error('IMAGE_GEOMETRY_ANCHORS_INVALID');
 if(!(sampleM>0&&sampleM<=1))throw Error('IMAGE_GEOMETRY_SAMPLE_STEP_INVALID');
 const steps=Math.ceil(distanceM/sampleM),gap=distanceM/steps;
 const length=new Float64Array(steps+1);
 const xy=[];
 for(let i=0;i<=steps;i++){
  const d=i*gap,p=pointAt(d,lane);
  if(!Number.isFinite(p?.x)||!Number.isFinite(p?.y))
   throw Error('IMAGE_GEOMETRY_POINT_UNAVAILABLE:'+d);
  xy.push({x:p.x,y:p.y});
  if(i)length[i]=length[i-1]+Math.hypot(p.x-xy[i-1].x,p.y-xy[i-1].y);
 }
 function arcAt(d){
  const x=clamp(d,0,distanceM)/gap,i=Math.floor(x),f=x-i;
  return length[i]*(1-f)+length[Math.min(steps,i+1)]*f;
 }
 function invertArc(v){
  const t=clamp(v,0,length[steps]);let lo=0,hi=steps;
  while(lo<hi){
   const mid=(lo+hi)>>1;
   if(length[mid]<t)lo=mid+1;else hi=mid;
  }
  const i=clamp(lo-1,0,steps-1),
   delta=length[i+1]-length[i];
  return (i+(delta>1e-9?(t-length[i])/delta:0))*gap;
 }
 const knots=anchors.map(arcAt);
 const rates=anchors.slice(1).map((x,i)=>
  (knots[i+1]-knots[i])/(x-anchors[i]));
 if(rates.some(s=>s<=1e-6))throw Error('IMAGE_GEOMETRY_ARC_DEGENERATE');
 const slopes=anchors.map((d,i)=>{
  if(i===0)return rates[0];
  if(i===anchors.length-1)return rates.at(-1);
  const a=rates[i-1],b=rates[i];
  const h0=anchors[i]-anchors[i-1],h1=anchors[i+1]-anchors[i];
  // Weighted harmonic mean (PCHIP), same formula for EVERY course.
  const w0=2*h1+h0,w1=h1+2*h0;
  return (w0+w1)/(w0/a+w1/b);
 });
 function sourceAt(d,localSlopes=slopes){
  const v=clamp(d,0,distanceM);let lo=0,hi=anchors.length-1;
  while(lo<hi){const mid=(lo+hi)>>1;if(anchors[mid]<v)lo=mid+1;else hi=mid}
  if(Math.abs(anchors[lo]-v)<1e-9)return anchors[lo];
  const i=Math.max(0,lo-1),h=anchors[i+1]-anchors[i];
  const desired=cubic(v-anchors[i],knots[i],knots[i+1],
   localSlopes[i],localSlopes[i+1],h);
  return invertArc(desired);
 }
 function imagePoint(d,laneValue=lane,localSlopes=slopes){
  return pointAt(sourceAt(d,localSlopes),laneValue);
 }
 const sampleInterval=Math.max(5,Math.ceil(distanceM/400)),
  probeGap=Math.max(22,Math.min(40,distanceM*.015));
 const probes=[];
 for(let d=probeGap;d<=distanceM-5;d+=sampleInterval)probes.push(d);
 // Objective is independent of the course and runner seed: use virtual
 // equal-spaced runners on source geometry, not actual race finishing gaps.
 // Penalize relative pack "breathing" per metre more than overall size;
 // physical layout legitimately foreshortens in turns, so this is bounded.
 function score(localSlopes){
  const gain=typeof displayGain==='function'?displayGain:()=>1;
  let prev=0,loss=0,n=0,maxJump=0;
  for(const d of probes){
   const a=imagePoint(d,lane,localSlopes),
    b=imagePoint(d-probeGap,lane,localSlopes);
   const chord=Math.hypot(a.x-b.x,a.y-b.y)*gain(d);
   if(!(chord>1e-5))return Infinity;
   const v=Math.log(chord);
   if(n){
    const change=Math.abs(v-prev);
    // Global 2% per sample movement budget, not a site-specific point.
    const excess=Math.max(0,change-.018);
    loss+=change*change+8*excess*excess;
    maxJump=Math.max(maxJump,change);
   }
   prev=v;n++;
  }
  // Keep anchors exactly and discourage wild phase adjustment.
  for(let d=0;d<distanceM;d+=Math.max(15,sampleInterval*3)){
   const phase=(sourceAt(d,localSlopes)-d)/distanceM;
   loss+=20*phase*phase;
  }
  // Smoothly varying acceleration at anchor, not overfitting one bend.
  for(let i=1;i<localSlopes.length-1;i++){
   const prior=(localSlopes[i]-slopes[i])/
    Math.max(.1,Math.max(rates[i-1],rates[i]));
   loss+=.003*prior*prior;
  }
  return loss;
 }
 const baseline=slopes.slice(),baselineScore=score(baseline);
 let optimizationPasses=0;
 if(enableGlobalOptimization){
  // Coordinate descent under shape-preserving cubic monotonicity.
  // Search is performed identically at every internal landmark.
  let best=baselineScore;
  for(let pass=0;pass<3;pass++){
   let improved=false;
   for(let i=1;i<slopes.length-1;i++){
    const before=slopes[i],left=rates[i-1],right=rates[i],
     maxAllowed=3*Math.min(left,right);
    const candidates=[.76,.86,.94,1,1.06,1.14,1.25,1.36].map(f=>
     Math.min(maxAllowed,Math.max(.20*Math.min(left,right),before*f)));
    let chosen=before,localBest=best;
    for(const c of candidates){
     if(c===before)continue;
     slopes[i]=c;
     const q=score(slopes);
     if(q<localBest-1e-8){localBest=q;chosen=c}
    }
    slopes[i]=chosen;
    if(chosen!==before){improved=true;best=localBest}
   }
   optimizationPasses++;
   if(!improved)break;
  }
 }
 // A full monotonicity audit is required before returning a new mapping.
 let previous=-Infinity,minAdvance=Infinity,maxAdvance=0,maxPhase=0;
 for(let d=0;d<=distanceM;d+=sampleM){
  const x=sourceAt(d);
  if(x<=previous&&d>0)throw Error('IMAGE_GEOMETRY_NONMONOTONE:'+d);
  if(d>0){
   const rate=(x-previous)/sampleM;
   minAdvance=Math.min(minAdvance,rate);
   maxAdvance=Math.max(maxAdvance,rate);
  }
  previous=x;maxPhase=Math.max(maxPhase,Math.abs(x-d));
 }
 for(const a of anchors)
  if(Math.abs(sourceAt(a)-a)>1e-8)
   throw Error('IMAGE_GEOMETRY_LANDMARK_MOVED:'+a);
 const output=Object.freeze({
  distanceM,anchors:anchors.slice(),sampleM,lane,sourceSvgIntact:true,
  immutableSharedEngine:true,courseSpecificSlopeOverrides:0,
  physicalDistanceImmutable:true,sourceArcPixels:length[steps],
  sourceRates:rates,globalOptimizedSlopes:slopes.slice(),
  baselineSlopes:baseline,
  baselineScore,optimizedScore:score(slopes),
  globalOptimizationPasses:optimizationPasses,
  minSourceAdvancePerM:minAdvance,maxSourceAdvancePerM:maxAdvance,
  maxPhaseMetres:maxPhase
 });
 return Object.freeze({
  distanceM,anchors:anchors.slice(),sourceDistance:d=>sourceAt(d),
  point:(d,l=lane)=>imagePoint(d,l),stats:()=>output
 });
}
global.RaceCourseImageGeometry=Object.freeze({build});
})(typeof window!=='undefined'?window:globalThis);
