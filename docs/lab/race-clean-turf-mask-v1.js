/* LAB v17 — every-course-section continuous metre-to-source-image arc calibration.
 * v10 wrongly targeted the CENTER of an often-merged green region; where
 * inside/outside green paths meet, it steered horses outside then suddenly
 * recentered. v11 instead selects a SAFE inner corridor relative to the
 * historical rail (the physical race engine is completely untouched).
 * Only SVG-relative VISUAL coordinates are calibrated, never race distances,
 * lane preference, pace, overtaking, outcomes, bets or other production data.
 */
(function(global){'use strict';
const W=620,H=430,RASTER=3;
// A smartphone badge radius 13.5*0.68/7=1.31 source px.
const CLEARANCE=1.95, MIN_INNER_OFFSET=1.60, MAX_SPAN=17.5,
 SLOPE=.44, SMOOTH_RADIUS=19;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const c=global.RaceCleanCourse;
let grid=null,samples=null,statistics=null,sourceDistanceTable=null,sharedGeometry=null;
const ARC_ANCHORS=Object.freeze([0,308.7,530,720,1270,1435,1671.6,2000]);
// SVG artwork is stylized rather than surveyed. Around 1435m the drawn
// centreline changes from about 0.76 to 0.50 source px per race metre,
// making real horses appear to telescope together. Equalize physical
// metres along the ORIGINAL turf path across the connected third/fourth
// turns while keeping each horse on the source image and the original
// physics (RaceSimEngine / RaceLaneAI) untouched.
function isGreen(x,y){
 if(!grid||!Number.isFinite(x)||!Number.isFinite(y))return false;
 const ix=Math.floor(x*RASTER),iy=Math.floor(y*RASTER);
 return ix>=0&&iy>=0&&ix<W*RASTER&&iy<H*RASTER&&
  grid[iy*W*RASTER+ix]===1;
}
function discOnTurf(x,y,r=CLEARANCE){
 if(!isGreen(x,y))return false;
 for(let i=0;i<16;i++){
  const a=Math.PI*2*i/16;
  if(!isGreen(x+r*Math.cos(a),y+r*Math.sin(a)))return false;
 }
 return true;
}
function create(image){
 sharedGeometry=null;
 if(!image||!image.complete||image.naturalWidth<=0||image.naturalHeight<=0||
    Math.abs(image.naturalWidth/image.naturalHeight-W/H)>.025)
  throw Error('TURF_ORIGINAL_VECTOR_IMAGE_UNAVAILABLE');
 // drawImage(...,W*RASTER,H*RASTER) rescales the SAME vector viewBox,
 // irrespective of Safari reporting 368x255 CSS density-corrected pixels.
 const canvas=document.createElement('canvas');
 canvas.width=W*RASTER;canvas.height=H*RASTER;
 const ctx=canvas.getContext('2d',{willReadFrequently:true});
 if(!ctx)throw Error('TURF_IMAGE_CONTEXT_MISSING');
 ctx.drawImage(image,0,0,canvas.width,canvas.height);
 const raw=ctx.getImageData(0,0,canvas.width,canvas.height).data;
 grid=new Uint8Array(canvas.width*canvas.height);
 let greenPixels=0;
 for(let i=0;i<grid.length;i++){
  const j=i*4,r=raw[j],g=raw[j+1],b=raw[j+2],a=raw[j+3];
  if(a>=240&&g>=108&&g>r*1.4&&g>b*1.4){grid[i]=1;greenPixels++}
 }
 samples=[];
 let forkSections=0,missing=0;
 const previousRuns=[];
 // 2001 scalar distances, each using the physically meaningful INNER rail
 // and its outward normal, rather than the moving midpoint of a green blob.
 for(let d=0;d<=2000;d++){
  const rr=c.rails(d),inner=rr.inner,ox=rr.outer.x-inner.x,
   oy=rr.outer.y-inner.y,len=Math.hypot(ox,oy)||1,
   nx=ox/len,ny=oy/len;
  const runs=[];
  let first=null,last=null;
  // Search only where the illustrated inner track is expected; never
  // follow a second outer-course stripe or join between green branches.
  for(let i=-45;i<=225;i++){
   const t=i/3,x=inner.x+nx*t,y=inner.y+ny*t;
   const safe=discOnTurf(x,y,CLEARANCE);
   if(safe){
    if(first===null)first=t;
    last=t;
   }else if(first!==null){
    if(last-first>=8)runs.push({a:first,b:last});
    first=null;
   }
  }
  if(first!==null&&last-first>=8)runs.push({a:first,b:last});
  if(runs.length>1)forkSections++;
  // Fixed target near the true *inner* rail: merging green corridors must
  // not pull the horses to the centroid of the whole green region.
  const wanted=5.0;
  runs.sort((a,b)=>
   Math.max(a.a-wanted,wanted-a.b,0)-Math.max(b.a-wanted,wanted-b.b,0)||
   Math.abs(a.a-5)-Math.abs(b.a-5));
  const run=runs[0];
  if(!run){samples.push(null);missing++;continue}
  const low=Math.max(MIN_INNER_OFFSET,run.a+.30);
  const high=Math.min(run.b-.30,low+MAX_SPAN);
  if(high-low<3){samples.push(null);missing++;continue}
  samples.push({x:inner.x,y:inner.y,nx,ny,low,high,
   safeLow:low,safeHigh:high,rawInnerEdge:run.a});
  if(previousRuns.length<7&&d%400===0)
   previousRuns.push({d,first:run.a,last:run.b,low,high});
 }
 if(missing)throw Error('TURF_INNER_CORRIDOR_MISSING:'+missing);
 // At some crossings the illustrated physical inner rail vanishes, even
 // though the infield is GREEN. A long safe-edge collapse would incorrectly
 // steer the horses inside the track. Interpolate BETWEEN the adjacent
 // visible rail boundaries and never target an infield centroid.
 const gaps=[];
 let open=-1;
 for(let i=0;i<=samples.length;i++){
  const p=samples[i];
  const suspect=Boolean(p&&p.safeLow<=MIN_INNER_OFFSET+1.2);
  if(suspect&&open<0)open=i;
  if((!suspect||i===samples.length)&&open>=0){
   const end=i-1;
   if(end-open>=22){
    const from=Math.max(0,open-12),to=Math.min(samples.length-1,end+12);
    const left=samples[from].safeLow,right=samples[to].safeLow;
    for(let j=from+1;j<to;j++){
     const q=(j-from)/(to-from),eased=q*q*(3-2*q);
     const floor=left+(right-left)*eased;
     const r=samples[j];
     const newLow=Math.max(r.low,Math.min(floor,r.safeHigh-5.5));
     r.low=newLow;
     r.high=Math.min(r.safeHigh,Math.max(r.high,newLow+5.5));
    }
    gaps.push({start:open,end,from,to,left,right});
   }
   open=-1;
  }
 }
 // Smoothing is over distance, not over frames, so it is deterministic and
 // retains exactly the same result when the user changes playback speed.
 function limitSlope(){
  for(let i=1;i<samples.length;i++){
   let a=samples[i-1],b=samples[i];
   b.low=Math.max(b.low,a.low-SLOPE);
   b.high=Math.min(b.high,a.high+SLOPE);
  }
  for(let i=samples.length-2;i>=0;i--){
   let a=samples[i+1],b=samples[i];
   b.low=Math.max(b.low,a.low-SLOPE);
   b.high=Math.min(b.high,a.high+SLOPE);
  }
 }
 function lowpass(values){
  const prefix=new Float64Array(values.length+1);
  for(let i=0;i<values.length;i++)prefix[i+1]=prefix[i]+values[i];
  return values.map((_,i)=>{
   const left=i-SMOOTH_RADIUS,right=i+SMOOTH_RADIUS;
   let sum=prefix[Math.min(values.length,right+1)]-prefix[Math.max(0,left)];
   if(left<0)sum-=left*values[0];
   if(right>=values.length)sum+=(right-values.length+1)*values.at(-1);
   return sum/(2*SMOOTH_RADIUS+1);
  });
 }
 limitSlope();
 // Pixel-grid fluctuations at adjacent metre stations are removed by
 // two symmetric averaging passes; stay within each original safe interval.
 for(let iteration=0;iteration<2;iteration++){
  const low=lowpass(samples.map(p=>p.low)),
   high=lowpass(samples.map(p=>p.high));
  for(let i=0;i<samples.length;i++){
   const p=samples[i];
   p.low=Math.max(p.safeLow,Math.min(low[i],p.high-5));
   p.high=Math.min(p.safeHigh,Math.max(high[i],p.low+5));
  }
 }
 limitSlope();
 let minWidth=Infinity,maxLane0FromInner=0,maxStationJump=0,
  maxStationJumpAt=0,badStations=0,tooFarOut=0;
 for(let d=0;d<=2000;d++){
  const p=samples[d];
  minWidth=Math.min(minWidth,p.high-p.low);
  if(p.high-p.low<3)throw Error('TURF_INNER_CORRIDOR_TOO_NARROW_'+d);
  const at=e=>{
   const t=e.low+(e.high-e.low)*c.fraction(0);
   return {x:e.x+e.nx*t,y:e.y+e.ny*t,t};
  };
  const a=at(p);
  maxLane0FromInner=Math.max(maxLane0FromInner,a.t);
  if(a.t>19)tooFarOut++;
  if(!discOnTurf(a.x,a.y,1.80))badStations++;
  if(d>0){
   const b=at(samples[d-1]);
   const jump=Math.hypot(a.x-b.x,a.y-b.y);
   if(jump>maxStationJump){maxStationJump=jump;maxStationJumpAt=d}
  }
 }
 sourceDistanceTable=buildSourceArcMap();
 statistics={count:samples.length,missing,forkSections,minWidth,
  maxLane0FromInner,tooFarOut,maxStationJump,maxStationJumpAt,
  badStations,greenPixels,slopeLimit:SLOPE,smoothRadius:SMOOTH_RADIUS,
  hiddenRailBridges:gaps,source:'original-publisher-inner-rail',
  imageArcRegistration:sourceDistanceTable.summary};
 if(badStations||tooFarOut||maxStationJump>1.6)
  throw Error('TURF_INNER_ROUTE_UNSAFE:'+JSON.stringify(statistics));
 return statistics;
}
function positionAt(d,lane){
 const r=samples[d],f=c.fraction(lane);
 const t=r.low+(r.high-r.low)*f;
 return {x:r.x+r.nx*t,y:r.y+r.ny*t};
}
// A monotonically increasing picture-distance mapping, fully anchored to
// the source drawing and race metre checkpoints.
// Deterministic non-visual anchor preservation, including the fractional
// 308.7m and 1671.6m entries. Both the SVG and RaceSimEngine are untouched.
// Only the distance -> source-image path parameter is changed.
function buildSourceArcMap(){
 const end=2000,arc=new Float64Array(end+1);
 let prev=positionAt(0,2);
 for(let d=1;d<=end;d++){
  const p=positionAt(d,2);
  arc[d]=arc[d-1]+Math.hypot(p.x-prev.x,p.y-prev.y);
  prev=p;
 }
 const arcAt=d=>{
  const a=Math.floor(d),b=Math.ceil(d),t=d-a;
  return arc[a]*(1-t)+arc[b]*t;
 };
 // Mean illustrated arc px per race metre within every physically named
 // course section; adapt segment velocity continuously at the boundaries.
 const edgeArc=ARC_ANCHORS.map(arcAt);
 const rates=ARC_ANCHORS.slice(1).map((b,i)=>
  (edgeArc[i+1]-edgeArc[i])/(b-ARC_ANCHORS[i]));
 const slopes=ARC_ANCHORS.map((_,i)=>{
  if(i===0)return rates[0];
  if(i===ARC_ANCHORS.length-1)return rates.at(-1);
  const a=rates[i-1],b=rates[i];
  // Harmonic mean gives C1 image progress at section boundaries without
  // allowing a nonmonotonic spline between any two fixed checkpoints.
  return 2*a*b/(a+b);
 });
 const hermite=(q,len,start,finish,startSlope,endSlope)=>{
  const t=q/len,t2=t*t,t3=t2*t;
  return (2*t3-3*t2+1)*start+
   (t3-2*t2+t)*len*startSlope+
   (-2*t3+3*t2)*finish+
   (t3-t2)*len*endSlope;
 };
 const nodes=Array.from({length:end+1},(_,i)=>i);
 for(const a of ARC_ANCHORS){
  if(!Number.isInteger(a))nodes.push(a);
 }
 nodes.sort((a,b)=>a-b);
 const dedup=nodes.filter((x,i)=>i===0||x>nodes[i-1]+1e-8);
 const mapped=[];
 const locate=px=>{
  let lo=0,hi=end;
  while(lo<hi){
   const mid=(lo+hi)>>1;
   if(arc[mid]<px)lo=mid+1;else hi=mid;
  }
  const i=Math.max(0,Math.min(end-1,lo-1)),
   span=arc[i+1]-arc[i];
  return i+(span>.00000001?(px-arc[i])/span:0);
 };
 // First equalize every physical section while retaining its endpoints.
 // The complex third/fourth-turn bend additionally uses the narrower
 // v16-style two-section profile, which passed the 1440–1460m collapse
 // regression better than the all-section derivative choice.
 let section=0;
 for(let n=0;n<dedup.length;n++){
  const d=dedup[n];
  while(section<ARC_ANCHORS.length-2&&d>ARC_ANCHORS[section+1]+1e-8)
   section++;
  const from=ARC_ANCHORS[section],to=ARC_ANCHORS[section+1],
   base=edgeArc[section],goal=edgeArc[section+1];
  const target=hermite(d-from,to-from,base,goal,
   slopes[section],slopes[section+1]);
  let src=locate(target);
  if(ARC_ANCHORS.some(a=>Math.abs(d-a)<1e-8))src=d;
  mapped.push(src);
 }
 // Preserve the validated 1435m boundary compression fix. Blend it into
 // the overall image-distance profile over 45m on either side of the
 // outer endpoints to avoid generating a new jolt at 1270 or 1671.6m.
 const thirdStart=1270,thirdEnd=1435,fourthEnd=1671.6;
 const thirdArc=arcAt(thirdStart),junctionArc=arcAt(thirdEnd),
  fourthArc=arcAt(fourthEnd);
 const leftRate=(junctionArc-thirdArc)/(thirdEnd-thirdStart),
  rightRate=(fourthArc-junctionArc)/(fourthEnd-thirdEnd),
  junctionRate=2*leftRate*rightRate/(leftRate+rightRate);
 const fade=t=>{
  const v=clamp(t,0,1);
  return v*v*(3-2*v);
 };
 const transitionM=45;
 for(let n=0;n<dedup.length;n++){
  const d=dedup[n];
  if(d<=thirdStart||d>=fourthEnd)continue;
  const target=d<=thirdEnd?
   hermite(d-thirdStart,thirdEnd-thirdStart,thirdArc,junctionArc,
    leftRate,junctionRate):
   hermite(d-thirdEnd,fourthEnd-thirdEnd,junctionArc,fourthArc,
    junctionRate,rightRate);
  const special=locate(target);
  const w=fade((d-thirdStart)/transitionM)*
   fade((fourthEnd-d)/transitionM);
  mapped[n]=mapped[n]*(1-w)+special*w;
  if(ARC_ANCHORS.some(a=>Math.abs(d-a)<1e-8))mapped[n]=d;
 }
 let maxShift=0,maxRate=0,minRate=Infinity;
 for(let n=0;n<dedup.length;n++){
  const d=dedup[n],src=mapped[n];
  if(!Number.isFinite(src)||src<0||src>end)
   throw Error('FULL_COURSE_IMAGE_PROJECTION_OUTSIDE_SOURCE_'+d);
  maxShift=Math.max(maxShift,Math.abs(src-d));
  if(n>0){
   const rate=(src-mapped[n-1])/(d-dedup[n-1]);
   if(!Number.isFinite(rate)||rate<.10||rate>3)
    throw Error('FULL_COURSE_IMAGE_PROJECTION_NONMONOTONE_'+d+'_'+rate);
   maxRate=Math.max(maxRate,rate);
   minRate=Math.min(minRate,rate);
  }
 }
 const summary={anchors:ARC_ANCHORS.slice(),rates,slopes,
  illustratedArcPx:arc[end],maxMetresOfImagePhaseAdjustment:maxShift,
  turn1435ArcBlend:'validated-local-arc-correction',
  physicalMarkersUnchanged:true,
  minSourceAdvancePerRaceM:minRate,maxSourceAdvancePerRaceM:maxRate,
  immutableSharedEngine:true,samplingEveryM:1};
 return {nodes:dedup,mapped,summary};
}
function sourceDistance(distance){
 const d=clamp(Number(distance)||0,0,2000);
 if(sharedGeometry)return sharedGeometry.sourceDistance(d);
 if(!sourceDistanceTable)return d;
 const nodes=sourceDistanceTable.nodes,map=sourceDistanceTable.mapped;
 let lo=0,hi=nodes.length-1;
 while(lo<hi){
  const mid=(lo+hi)>>1;
  if(nodes[mid]<d)lo=mid+1;else hi=mid;
 }
 if(Math.abs(nodes[lo]-d)<1e-9)return map[lo];
 const lower=Math.max(0,lo-1),span=nodes[lo]-nodes[lower];
 const frac=span>0?(d-nodes[lower])/span:0;
 return map[lower]*(1-frac)+map[lo]*frac;
}
// LAB v21: attach an independently tested, COURSE-INDEPENDENT geometry
// model. The legacy hardcoded 3/4-turn blend stays as a reversible control.
function activateSharedGeometry(model){
 if(!samples||!model||typeof model.sourceDistance!=='function')
  throw Error('SHARED_GEOMETRY_NOT_READY');
 if(Math.abs(model.distanceM-2000)>1e-8)
  throw Error('SHARED_GEOMETRY_WRONG_RACE_DISTANCE');
 const before=sharedGeometry;
 sharedGeometry=model;
 const originalStats=statistics;
 try{
  const auditResult=audit(1,1.8);
  if(auditResult.badDiscs||auditResult.badCenters||
     auditResult.maxJump>1.8)
   throw Error('SHARED_GEOMETRY_TURF_AUDIT_FAILED:'+JSON.stringify({
     badDiscs:auditResult.badDiscs,badCenters:auditResult.badCenters,
     maxJump:auditResult.maxJump}));
  statistics={...originalStats,
   imageArcRegistration:{...model.stats(),mode:'shared-course-independent'},
   sharedGeometryGreenVerifiedPoints:auditResult.total,
   sharedGeometryMaxJump:auditResult.maxJump};
  return {valid:true,greenVerified:auditResult.total,
   sourceSvgUnchanged:true,stats:model.stats()};
 }catch(err){
  sharedGeometry=before;
  statistics=originalStats;
  throw err;
 }
}
// LAB read-only diagnostic: raw position on the UNMODIFIED source image
// before physical-race-distance reparameterization. Needed to compare
// alternative anchor-preserving calibrations without altering race physics.
function pointAtImageDistance(distance,lane=0){
 if(!samples)throw Error('TURF_SOURCE_MASK_NOT_READY');
 const d=clamp(Number(distance)||0,0,2000),a=Math.floor(d),b=Math.ceil(d),t=d-a;
 const first=positionAt(a,lane),last=positionAt(b,lane);
 return {x:first.x+(last.x-first.x)*t,y:first.y+(last.y-first.y)*t};
}
function point(distance,lane=0){
 if(!samples)throw Error('TURF_SOURCE_MASK_NOT_READY');
 if(distance>2000){
  // Unclamped tangent extension after the finish. The old source spline
  // capped extra metres at 45 and visibly stopped the leading numbers.
  const end=point(2000,lane),before=point(1990,lane),extra=distance-2000;
  const tx=(end.x-before.x)/10,ty=(end.y-before.y)/10;
  let x=end.x+tx*extra,y=end.y+ty*extra;
  if(!discOnTurf(x,y,1.9)){
   const normal=samples[2000];
   let nearest=null;
   for(let a=-5;a<=5;a+=.25){
    const px=x+normal.nx*a,py=y+normal.ny*a;
    if(discOnTurf(px,py,1.9)&&(!nearest||Math.abs(a)<nearest.delta))
     nearest={x:px,y:py,delta:Math.abs(a)};
   }
   if(nearest){x=nearest.x;y=nearest.y}
  }
  return {x,y,d:distance,lane,section:'ゴール後'};
 }
 const raceD=clamp(Number(distance)||0,0,2000);
 const d=sourceDistance(raceD);
 const a=Math.floor(d),b=Math.ceil(d),t=d-a;
 const first=positionAt(a,lane),last=positionAt(b,lane);
 const x=first.x+(last.x-first.x)*t,y=first.y+(last.y-first.y)*t;
 return {x,y,d:distance,lane,imageCourseDistance:d,
  section:c.center(distance).section};
}
function runners(state){
 return state.horses.map(h=>{
  const d=h.displayD??h.d;
  return {number:h.number,d,lane:h.lane,...point(d,h.lane),finished:h.finished};
 });
}
function audit(step=1,radius=1.80){
 let total=0,badCenters=0,badDiscs=0,maxJump=0,maxJumpAt=0,
  maxActualInnerOffset=0;
 for(let lane=0;lane<=14;lane++){
  let prev=null;
  for(let d=0;d<=2000;d+=step){
   const p=point(d,lane);
   total++;
   if(!isGreen(p.x,p.y))badCenters++;
   if(!discOnTurf(p.x,p.y,radius))badDiscs++;
   const inner=c.rails(sourceDistance(d)).inner;
   maxActualInnerOffset=Math.max(maxActualInnerOffset,
    Math.hypot(p.x-inner.x,p.y-inner.y));
   if(prev){
    const diff=Math.hypot(p.x-prev.x,p.y-prev.y);
    if(diff>maxJump){maxJump=diff;maxJumpAt=d}
   }
   prev=p;
  }
 }
 return {...statistics,total,badCenters,badDiscs,maxJump,maxJumpAt,
  maxActualInnerOffset,step,radius};
}
// Read-only geometry diagnostics for tracing missing drawn-rail segments.
function trace(from=0,to=2000,step=25){
 if(!samples)return [];
 const out=[];
 for(let d=Math.max(0,from);d<=Math.min(2000,to);d+=step){
  const sourceD=sourceDistance(d),
   p=samples[Math.round(sourceD)],rr=c.rails(sourceD),
   pos=point(d,0),dist=Math.hypot(pos.x-rr.inner.x,pos.y-rr.inner.y);
  let greenInside=0;
  // How far into the infield is still green from inner runner position?
  for(let t=0;t<=35;t+=.5){
   if(!isGreen(pos.x-p.nx*t,pos.y-p.ny*t)){greenInside=t;break}
  }
  out.push({d,sourceD:+sourceD.toFixed(3),low:+p.low.toFixed(2),high:+p.high.toFixed(2),
   safeLow:+p.safeLow.toFixed(2),safeHigh:+p.safeHigh.toFixed(2),
   dist:+dist.toFixed(2),greenInside});
 }
 return out;
}
global.RaceCleanTurf=Object.freeze({
 create,point,pointAtImageDistance,runners,isGreen,discOnTurf,audit,trace,sourceDistance,
  activateSharedGeometry,sharedGeometryEnabled:()=>Boolean(sharedGeometry),
  stats:()=>statistics
});
})(typeof window!=='undefined'?window:globalThis);
