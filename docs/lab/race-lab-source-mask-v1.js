/* Shared image-derived green corridor for registered Umapot SVG routes.
 * Select a contiguous GREEN band by following the existing image guide in
 * race-distance order. Never repaint the source or alter RaceSimEngine lanes.
 * No venue, corner, or 1400/2000 special-case correction tables.
 */
(function(g){'use strict';
const W=620,H=430,R=2,CLEARANCE=1.45,SCAN=60,STEP=.5,MIN_WIDTH=6;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function build({image,course,guide,projection,geometry}){
 if(!image?.complete||!image.naturalWidth)throw Error('SOURCE_VECTOR_UNAVAILABLE');
 const canvas=document.createElement('canvas');canvas.width=W*R;canvas.height=H*R;
 const ctx=canvas.getContext('2d',{willReadFrequently:true});
 ctx.drawImage(image,0,0,canvas.width,canvas.height);
 const raw=ctx.getImageData(0,0,canvas.width,canvas.height).data;
 const green=new Uint8Array(W*H*R*R);
 for(let i=0;i<green.length;i++){const j=i*4,r=raw[j],v=raw[j+1],b=raw[j+2],a=raw[j+3];
  green[i]=(a>=240&&v>=108&&v>r*1.4&&v>b*1.4)?1:0;
 }
 function isGreen(x,y){
  const i=Math.floor(x*R),j=Math.floor(y*R);
  return i>=0&&j>=0&&i<W*R&&j<H*R&&green[j*W*R+i]===1;
 }
 function disc(x,y){
  if(!isGreen(x,y))return false;
  for(let i=0;i<16;i++){const a=Math.PI*2*i/16;
   if(!isGreen(x+CLEARANCE*Math.cos(a),y+CLEARANCE*Math.sin(a)))return false;
  }return true;
 }
 const distance=course.distance_m,samples=[],failures=[],candidates=[];
 let maxGuideDeviation=0,maxCenterStep=0,maxCenterStepAt=0,minBandWidth=Infinity;
 // Candidate safe green bands come directly from source SVG pixels.
 // A global dynamic program, not per-corner tuning, keeps us on the SAME
 // ribbon when an inner/outer track visually overlaps or briefly merges.
 for(let d=0;d<=distance;d++){
  const inner=guide(course,d,0),outer=guide(course,d,14),
   dx=outer.x-inner.x,dy=outer.y-inner.y,span=Math.hypot(dx,dy);
  if(!Number.isFinite(span)||span<.5)throw Error('SOURCE_RAIL_DIRECTION_UNKNOWN_'+d);
  const ux=dx/span,uy=dy/span,bands=[];let first=null,last=null;
  for(let i=0;i<=SCAN*4;i++){
   const t=-SCAN+i*STEP,x=inner.x+ux*t,y=inner.y+uy*t;
   if(disc(x,y)){if(first===null)first=t;last=t}
   else if(first!==null){
    if(last-first>=MIN_WIDTH)bands.push({low:first,high:last});
    first=null;last=null;
   }
  }
  if(first!==null&&last-first>=MIN_WIDTH)bands.push({low:first,high:last});
  if(!bands.length)throw Error('SOURCE_TURF_BAND_NOT_FOUND_'+d);
  const target=span*.44;
  candidates.push(bands.map(b=>{
   const mid=(b.low+b.high)/2;
   return {inner,ux,uy,low:b.low,high:b.high,mid,
    target,center:{x:inner.x+ux*mid,y:inner.y+uy*mid},source:d};
  }));
 }
 const dp=[],trace=[];
 for(let d=0;d<candidates.length;d++){
  const band=candidates[d],costs=[],choices=[];
  for(const q of band){
   const imageGuidePenalty=.016*(q.mid-q.target)**2;
   if(d===0){costs.push(imageGuidePenalty);choices.push(-1);continue;}
   let best=Infinity,index=-1;
   for(let i=0;i<candidates[d-1].length;i++){
    const prev=candidates[d-1][i],move=Math.hypot(
     q.center.x-prev.center.x,q.center.y-prev.center.y);
    // Strong preference for a physically continuous green ribbon rather
    // than jumping to another course when their green strokes approach.
    const candidate=dp[d-1][i]+move*move*5+imageGuidePenalty;
    if(candidate<best){best=candidate;index=i}
   }
   costs.push(best);choices.push(index);
  }
  dp.push(costs);trace.push(choices);
 }
 let index=dp.at(-1).indexOf(Math.min(...dp.at(-1)));
 for(let d=distance;d>=0;d--){
  samples[d]=candidates[d][index];
  index=trace[d][index];
 }
 for(let d=0;d<=distance;d++){
  const p=samples[d];
  maxGuideDeviation=Math.max(maxGuideDeviation,Math.abs(p.mid-p.target));
  minBandWidth=Math.min(minBandWidth,p.high-p.low);
  if(d){const q=samples[d-1];
   const move=Math.hypot(p.center.x-q.center.x,p.center.y-q.center.y);
   if(move>maxCenterStep){maxCenterStep=move;maxCenterStepAt=d}
  }
 }
 // Green strokes may MERGE at inner/outer track joins. Never spread the
 // complete horsefield over the enlarged merged patch: derive a robust
 // source-ribbon width from the entire route and cap the projection width.
 const widths=samples.map(s=>s.high-s.low).sort((a,b)=>a-b);
 const typicalBandWidth=widths[Math.floor(widths.length/2)];
 function boundedHigh(s){return Math.min(s.high,s.low+typicalBandWidth)}
 const anchors=[0,...course.segments.map(s=>s.to)];
 const geom=geometry.build({distanceM:distance,anchorsM:anchors,
  pointAt:(d,l)=>{const q=samples[Math.round(clamp(d,0,distance))];
    const f=projection.fraction((1.8+l*1.65)/27);
    return {x:q.inner.x+q.ux*(q.low+(boundedHigh(q)-q.low)*f),
      y:q.inner.y+q.uy*(q.low+(q.high-q.low)*f)};},
  displayGain:()=>1,enableGlobalOptimization:false});
 function position(d,lane){
  const raceD=clamp(d,0,distance),mapped=geom.sourceDistance(raceD),
   i=Math.min(distance-1,Math.floor(mapped)),a=samples[i],b=samples[i+1],
   t=clamp(mapped-i,0,1),l=clamp(Number(lane)||0,0,14);
  const low=a.low+(b.low-a.low)*t,high=boundedHigh(a)+(boundedHigh(b)-boundedHigh(a))*t;
  const f=projection.fraction((1.8+l*1.65)/27);
  const off=low+(high-low)*f;
  let x=(a.inner.x+(b.inner.x-a.inner.x)*t)+(a.ux+(b.ux-a.ux)*t)*off,
      y=(a.inner.y+(b.inner.y-a.inner.y)*t)+(a.uy+(b.uy-a.uy)*t)*off;
  if(d>distance){const last=samples[distance],before=samples[distance-10],
    ux=last.inner.x-before.inner.x,uy=last.inner.y-before.inner.y,
    extra=d-distance;x+=ux*extra/10;y+=uy*extra/10;}
  return {x,y,d,lane:l};
 }
 let checked=0,bad=0,maxProjectedStep=0,maxProjectedStepAt=0;
 for(let d=0;d<=distance;d+=5)for(const lane of [0,2,4,8,11,14]){
  const p=position(d,lane);checked++;
  if(!disc(p.x,p.y)){bad++;if(failures.length<20)failures.push({d,lane})}
 }
 for(let d=1;d<=distance;d++)for(const lane of [0,2,4,8,11,14]){
  const a=position(d-1,lane),b=position(d,lane);
  const step=Math.hypot(b.x-a.x,b.y-a.y);
  if(step>maxProjectedStep){maxProjectedStep=step;maxProjectedStepAt=d}
 }
 const report=Object.freeze({id:course.id,checked,badDiscs:bad,
  typicalBandWidth,maxProjectedStep,maxProjectedStepAt,
  maxGuideDeviation,maxCenterStep,maxCenterStepAt,minBandWidth,badSamples:failures,
  sourceUnchanged:true,corridorFromOriginalSvg:true,
  perCourseManualOffsets:0});
 return Object.freeze({point:position,disc,report,geometry:geom});
}
g.RaceLabSourceMask=Object.freeze({build});
})(typeof window!=='undefined'?window:globalThis);
