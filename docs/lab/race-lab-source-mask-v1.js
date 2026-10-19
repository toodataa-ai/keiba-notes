/* Reusable SOURCE IMAGE validation for an existing route guide.
 * The image is kept untouched. Movement is display-only, and the physical
 * RaceSimEngine/RaceLaneAI positions remain authoritative.
 */
(function(g){'use strict';
const W=620,H=430,RASTER=2,DISC=1.45,MAX_CORRECTION=7;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function build({image,course,guide,projection,geometry}){
 if(!image?.complete||!image.naturalWidth)throw Error('SOURCE_VECTOR_NOT_LOADED');
 const canvas=document.createElement('canvas');
 canvas.width=W*RASTER;canvas.height=H*RASTER;
 const ctx=canvas.getContext('2d',{willReadFrequently:true});
 ctx.drawImage(image,0,0,canvas.width,canvas.height);
 const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
 const turf=new Uint8Array(canvas.width*canvas.height);
 for(let i=0;i<turf.length;i++){
  const j=i*4,r=pixels[j],green=pixels[j+1],b=pixels[j+2],a=pixels[j+3];
  turf[i]=(a>=240&&green>=108&&green>r*1.4&&green>b*1.4)?1:0;
 }
 function isGreen(x,y){
  const i=Math.floor(x*RASTER),j=Math.floor(y*RASTER);
  return i>=0&&j>=0&&i<W*RASTER&&j<H*RASTER&&turf[j*W*RASTER+i]===1;
 }
 function disc(x,y){
  if(!isGreen(x,y))return false;
  for(let i=0;i<16;i++){const a=2*Math.PI*i/16;
   if(!isGreen(x+DISC*Math.cos(a),y+DISC*Math.sin(a)))return false;
  }
  return true;
 }
 const distance=course.distance_m,anchors=[0,...course.segments.map(s=>s.to)];
 // The identical course-neutral arclength algorithm used in the original
 // LAB, with only official section bounds as route-specific metadata.
 const map=geometry.build({distanceM:distance,anchorsM:anchors,
   pointAt:(d,l)=>guide(course,d,l),displayGain:()=>1,
   enableGlobalOptimization:false});
 function point(d,lane){
  const limited=clamp(d,0,distance),source=map.sourceDistance(limited);
  const p=guide(course,source,lane),
   inner=guide(course,source,0),outer=guide(course,source,14);
  const dx=outer.x-inner.x,dy=outer.y-inner.y,span=Math.hypot(dx,dy)||1;
  const ux=dx/span,uy=dy/span;
  const wanted={x:p.x-ux*span*projection.INNER_INSET_FRACTION,
   y:p.y-uy*span*projection.INNER_INSET_FRACTION};
  let final=null;
  if(disc(wanted.x,wanted.y))final={...wanted,corrected:0};
  if(!final)for(let i=1;i<=MAX_CORRECTION*2&&!final;i++){
   const move=i*.5;
   for(const sign of [-1,1]){
    const x=wanted.x+ux*sign*move,y=wanted.y+uy*sign*move;
    if(disc(x,y)){final={x,y,corrected:move};break}
   }
  }
  if(!final)return {...wanted,corrected:null,d,lane};
  if(d>distance){
   const prev=guide(course,distance-10,lane),last=guide(course,distance,lane);
   const extra=d-distance;
   return {...final,x:final.x+(last.x-prev.x)*extra/10,
    y:final.y+(last.y-prev.y)*extra/10,d,lane};
  }
  return {...final,d,lane};
 }
 const issues=[];let maxCorrection=0,checked=0;
 for(let d=0;d<=distance;d+=5)for(const lane of [0,2,4,8,11,14]){
  const p=point(d,lane);checked++;
  if(!disc(p.x,p.y)||p.corrected===null)issues.push({d,lane});
  maxCorrection=Math.max(maxCorrection,p.corrected??Infinity);
 }
 const report=Object.freeze({id:course.id,checked,badDiscs:issues.length,
  maxCorrection,badSamples:issues.slice(0,12),sourceUnchanged:true,
  geometryIndependent:true});
 return Object.freeze({point,disc,report});
}
g.RaceLabSourceMask=Object.freeze({build});
})(typeof window!=='undefined'?window:globalThis);
