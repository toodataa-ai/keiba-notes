/* LAB v18: Distance-faithful KYOTO running-view from unchanged Umapot
 * course SVG pixels, not a synthetic drawing or a position-warped race.
 * Why: when a curved course is projected on the map, the CHORD between
 * horses necessarily shrinks even if their actual separation is constant;
 * at the end of a turn that chord grows. Arc-length remapping alone cannot
 * correct that. The TV view must use physical LONGITUDINAL DISTANCE as X.
 * The full overview keeps the exact untouched source SVG, and legacy
 * map-follow is independently selectable. The common Kyoto1400 physical
 * engine stays the only source of horse distance, pace and lane.
 */
(function(global){'use strict';
const ATLAS_PX_PER_M=2,ATLAS_PX_PER_LANE=15,LAST_METRE=2000,
 MAX_LANE=14,SOURCE_SCALE=2;
const clamp=(a,min,max)=>Math.max(min,Math.min(max,a));
let atlas=null,initData=null,atlasError=null;
const mkCanvas=(w,h)=>{
 const c=document.createElement('canvas');c.width=w;c.height=h;return c;
};
function create(original,turf){
 if(!original?.complete||!(original.naturalWidth>0)||
    Math.abs(original.naturalWidth/original.naturalHeight-620/430)>.025)
  throw Error('DISTANCE_TV_ORIGINAL_SVG_NOT_READY');
 if(!turf?.point)throw Error('DISTANCE_TV_SOURCE_TURF_NOT_READY');
 const source=mkCanvas(620*SOURCE_SCALE,430*SOURCE_SCALE);
 const sourceContext=source.getContext('2d',{willReadFrequently:true});
 sourceContext.drawImage(original,0,0,source.width,source.height);
 const img=sourceContext.getImageData(0,0,source.width,source.height);
 const atlasWidth=LAST_METRE*ATLAS_PX_PER_M+1;
 const atlasHeight=MAX_LANE*ATLAS_PX_PER_LANE+1;
 const tex=mkCanvas(atlasWidth,atlasHeight);
 const tctx=tex.getContext('2d');
 const out=tctx.createImageData(atlasWidth,atlasHeight);
 const data=img.data,target=out.data,rowWidth=img.width,sourceHeight=img.height;
 let sampled=0,skipped=0;
 // Precompute a one-time, read-only lookup. No per-frame geometry scans.
 // The colour at (distance,lane) comes from exactly the corresponding
 // Umapot SVG position used by the real overview numbers.
 const xNodes=Array.from({length:atlasWidth},(_,x)=>{
  const d=x/ATLAS_PX_PER_M,knots=[];
  for(let lane=0;lane<=MAX_LANE;lane++){
   const p=turf.point(d,lane);
   knots.push({sx:clamp(Math.round(p.x*SOURCE_SCALE),0,rowWidth-1),
    sy:clamp(Math.round(p.y*SOURCE_SCALE),0,sourceHeight-1)});
  }
  return knots;
 });
 for(let x=0;x<atlasWidth;x++){
  const knots=xNodes[x];
  for(let y=0;y<atlasHeight;y++){
   // Top = outside lanes, bottom = the real inner rail.
   const lane=MAX_LANE-y/ATLAS_PX_PER_LANE;
   const below=clamp(Math.floor(lane),0,MAX_LANE),
    above=Math.min(MAX_LANE,below+1),mix=lane-below;
   const a=knots[below],b=knots[above];
   const sx=clamp(Math.round(a.sx+(b.sx-a.sx)*mix),0,rowWidth-1),
    sy=clamp(Math.round(a.sy+(b.sy-a.sy)*mix),0,sourceHeight-1);
   const si=(sy*rowWidth+sx)*4,di=(y*atlasWidth+x)*4;
   // Preserve the original publisher's image raster, including the
   // varying green shading; no hand-drawn invented topography.
   target[di]=data[si];
   target[di+1]=data[si+1];
   target[di+2]=data[si+2];
   target[di+3]=255;
   if(data[si+1]>data[si]*1.4&&data[si+1]>data[si+2]*1.4)sampled++;
   else skipped++;
  }
 }
 tctx.putImageData(out,0,0);
 atlas=tex;
 atlasError=null;
 initData=Object.freeze({atlasWidth,atlasHeight,sourceWidth:620,
  sourceHeight:430,originalPublisherTexture:true,
  metresPerTexel:1/ATLAS_PX_PER_M,lanePerTexel:1/ATLAS_PX_PER_LANE,
  sampledGreenFraction:sampled/(sampled+skipped),
  immutablePhysics:true});
 return initData;
}
function geometry(width,height,focusedD,selectedLane=0){
 const w=Math.max(1,width),h=Math.max(1,height);
 // Never animate this longitudinal scale with crowd density or the camera's
 // course-heading: 10 real metres stay EXACTLY the same screen distance.
 const pxPerMetre=w<540?4.25:5.2;
 const laneStep=Math.min(18,(h-76)/(MAX_LANE));
 const centerY=h*.51;
 const centerX=w*.34;
 return {width:w,height:h,focusD:focusedD,
  centerX,centerY,pxPerMetre,laneStep,sourceAtlas:!!atlas};
}
function screenPoint(distance,lane,geo){
 return {x:geo.centerX+(geo.focusD-distance)*geo.pxPerMetre,
  y:geo.centerY+(7-clamp(lane,0,MAX_LANE))*geo.laneStep};
}
function render({canvas,points,focusNo,leaderNo,paintNumber,focusD,fieldSize=18}){
 if(!atlas)throw Error('DISTANCE_TV_SOURCE_ATLAS_NOT_READY');
 const rect=canvas.getBoundingClientRect(),w=Math.max(1,rect.width),
  h=Math.max(1,rect.height);
 const dpr=Math.min(2.5,Math.max(1,global.devicePixelRatio||1)),
  pixelsW=Math.round(w*dpr),pixelsH=Math.round(h*dpr);
 if(canvas.width!==pixelsW||canvas.height!==pixelsH){
  canvas.width=pixelsW;canvas.height=pixelsH;
 }
 const ctx=canvas.getContext('2d');ctx.setTransform(pixelsW/w,0,0,pixelsH/h,0,0);
 const geo=geometry(w,h,focusD);
 const top=geo.centerY-7*geo.laneStep,bottom=geo.centerY+7*geo.laneStep;
 ctx.clearRect(0,0,w,h);
 ctx.fillStyle='#304a38';ctx.fillRect(0,0,w,h);
 // Unwrap the unchanged source SVG's turf texture under this TV camera,
 // using source image pixels sampled along actual original rail positions.
 // Its rolling X axis is physical metres, NOT curved-map chord distance.
 ctx.save();
 ctx.beginPath();ctx.rect(0,top,w,bottom-top);ctx.clip();
 ctx.fillStyle='#6b9b57';ctx.fillRect(0,top,w,bottom-top);
 const minD=geo.focusD-(w-geo.centerX)/geo.pxPerMetre,
  maxD=geo.focusD+geo.centerX/geo.pxPerMetre;
 const from=clamp(minD,0,LAST_METRE),to=clamp(maxD,0,LAST_METRE);
 if(to>from){
  const sourceX=from*ATLAS_PX_PER_M,
   sourceWidth=Math.min(atlas.width-sourceX,(to-from)*ATLAS_PX_PER_M),
   targetLeft=w-(to-minD)*geo.pxPerMetre,
   targetWidth=(to-from)*geo.pxPerMetre;
  // Flip horizontally so increasing race metres run from right to left.
  ctx.save();ctx.translate(w,0);ctx.scale(-1,1);
  const reflectedLeft=w-targetLeft-targetWidth;
  ctx.drawImage(atlas,sourceX,0,sourceWidth,atlas.height,
   reflectedLeft,top,targetWidth,bottom-top);
  ctx.restore();
 }
 ctx.restore();
 // Turf edges are visual clipping boundaries only (not a new race rail).
 const numbers=[];
 const sorted=points.slice().sort((a,b)=>
  Number(a.number===focusNo)-Number(b.number===focusNo)||a.number-b.number);
 const radius=13.5*(w<540?.68:.76);
 for(const p of sorted){
  const pos=screenPoint(p.d,p.lane,geo);
  if(pos.x+radius<0||pos.x-radius>w||pos.y+radius<top||pos.y-radius>bottom)
   continue;
  const scale=w<540?.68:.76;
  paintNumber(ctx,p.number,pos.x,pos.y,scale,p.number===focusNo,
   p.number===leaderNo,fieldSize,false);
  numbers.push({number:p.number,x:pos.x,y:pos.y,d:p.d,lane:p.lane,r:radius,
   actual:{x:pos.x,y:pos.y}});
 }
 return {mode:'physical-distance-running-camera',geometry:geo,
  imageTextureSource:'same-umapot-svg-as-overview',
  sourceTurfUnwrapped:true,numbers,allPositions:points.map(p=>({
   number:p.number,d:p.d,lane:p.lane,...screenPoint(p.d,p.lane,geo)
  })),top,bottom};
}
global.RaceCleanDistanceCamera=Object.freeze({
 create,render,screenPoint,geometry,stats:()=>initData,
 ready:()=>Boolean(atlas),error:()=>atlasError
});
})(typeof window!=='undefined'?window:globalThis);
