/* LAB v12 — source inner green safety pixels with smoothed and tightened lane bounds.
 * v10 wrongly targeted the CENTER of an often-merged green region; where
 * inside/outside green paths meet, it steered horses outside then suddenly
 * recentered. v11 instead selects a SAFE inner corridor relative to the
 * historical rail (the physical race engine is completely untouched).
 * Only SVG-relative VISUAL coordinates are calibrated, never race distances,
 * lane preference, pace, overtaking, outcomes, bets or other production data.
 */
(function(global){'use strict';
const W=620,H=430,RASTER=3;
const CLEARANCE=3.1, MIN_INNER_OFFSET=3.25, MAX_SPAN=17.5,
 SLOPE=.55, SMOOTH_RADIUS=17;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const c=global.RaceCleanCourse;
let grid=null,samples=null,statistics=null;
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
 if(!image||!image.complete||image.naturalWidth!==W||image.naturalHeight!==H)
  throw Error('TURF_ORIGINAL_VECTOR_IMAGE_UNAVAILABLE');
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
  const wanted=7;
  runs.sort((a,b)=>
   Math.max(a.a-wanted,wanted-a.b,0)-Math.max(b.a-wanted,wanted-b.b,0)||
   Math.abs(a.a-5)-Math.abs(b.a-5));
  const run=runs[0];
  if(!run){samples.push(null);missing++;continue}
  const low=Math.max(MIN_INNER_OFFSET,run.a+.45);
  const high=Math.min(run.b-.45,low+MAX_SPAN);
  if(high-low<3){samples.push(null);missing++;continue}
  samples.push({x:inner.x,y:inner.y,nx,ny,low,high,
   safeLow:low,safeHigh:high});
  if(previousRuns.length<7&&d%400===0)
   previousRuns.push({d,first:run.a,last:run.b,low,high});
 }
 if(missing)throw Error('TURF_INNER_CORRIDOR_MISSING:'+missing);
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
  if(!discOnTurf(a.x,a.y,3.2))badStations++;
  if(d>0){
   const b=at(samples[d-1]);
   const jump=Math.hypot(a.x-b.x,a.y-b.y);
   if(jump>maxStationJump){maxStationJump=jump;maxStationJumpAt=d}
  }
 }
 statistics={count:samples.length,missing,forkSections,minWidth,
  maxLane0FromInner,tooFarOut,maxStationJump,maxStationJumpAt,
  badStations,greenPixels,slopeLimit:SLOPE,smoothRadius:SMOOTH_RADIUS,
  source:'original-publisher-inner-rail'};
 if(badStations||tooFarOut||maxStationJump>1.6)
  throw Error('TURF_INNER_ROUTE_UNSAFE:'+JSON.stringify(statistics));
 return statistics;
}
function positionAt(d,lane){
 const r=samples[d],f=c.fraction(lane);
 const t=r.low+(r.high-r.low)*f;
 return {x:r.x+r.nx*t,y:r.y+r.ny*t};
}
function point(distance,lane=0){
 if(!samples)throw Error('TURF_SOURCE_MASK_NOT_READY');
 if(distance>2000){
  const end=point(2000,lane),originalEnd=c.point(2000,lane),
   originalBeyond=c.point(distance,lane);
  let x=end.x+originalBeyond.x-originalEnd.x;
  let y=end.y+originalBeyond.y-originalEnd.y;
  // Retain the existing runoff on green beyond the finish line.
  if(!discOnTurf(x,y,3.0)){
   const r=c.rails(2000),nx=(r.outer.x-r.inner.x)/r.widthPx,
    ny=(r.outer.y-r.inner.y)/r.widthPx;
   let best=null;
   for(let a=-8;a<=8;a+=.25){
    const tx=x+nx*a,ty=y+ny*a;
    if(discOnTurf(tx,ty,3.0)&&(!best||Math.abs(a)<best.delta))
     best={x:tx,y:ty,delta:Math.abs(a)};
   }
   if(best){x=best.x;y=best.y}
  }
  return {x,y,d:distance,lane,section:'ゴール後'};
 }
 const d=clamp(Number(distance)||0,0,2000);
 const a=Math.floor(d),b=Math.ceil(d),t=d-a;
 const first=positionAt(a,lane),last=positionAt(b,lane);
 const x=first.x+(last.x-first.x)*t,y=first.y+(last.y-first.y)*t;
 return {x,y,d:distance,lane,section:c.center(distance).section};
}
function runners(state){
 return state.horses.map(h=>{
  const d=h.displayD??h.d;
  return {number:h.number,d,lane:h.lane,...point(d,h.lane),finished:h.finished};
 });
}
function audit(step=1,radius=3){
 let total=0,badCenters=0,badDiscs=0,maxJump=0,maxJumpAt=0,
  maxActualInnerOffset=0;
 for(let lane=0;lane<=14;lane++){
  let prev=null;
  for(let d=0;d<=2000;d+=step){
   const p=point(d,lane);
   total++;
   if(!isGreen(p.x,p.y))badCenters++;
   if(!discOnTurf(p.x,p.y,radius))badDiscs++;
   const inner=c.rails(d).inner;
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
global.RaceCleanTurf=Object.freeze({
 create,point,runners,isGreen,discOnTurf,audit,stats:()=>statistics
});
})(typeof window!=='undefined'?window:globalThis);
