/* LAB shared distance-unwrapped broadcast camera v1.
 * Source imagery comes ONLY from the registered original SVG raster and
 * route.point(d, lane). Live TV view may straighten a bend so equal real
 * race-distance gaps stay equal on screen. The official-looking whole-course
 * map remains unchanged. No course-specific XY pixel adjustments.
 */
(function(g){'use strict';
const T_W=448,T_H=448,L_PX=20,BASE_LANE=7,CACHE_LIMIT=10;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function create({image,route,distance}){
 if(!image?.naturalWidth||typeof route?.point!=='function'||!(distance>0))
  throw Error('DISTANCE_BROADCAST_SOURCE_UNAVAILABLE');
 const base=document.createElement('canvas');
 base.width=1240;base.height=860;
 const bctx=base.getContext('2d',{willReadFrequently:true});
 bctx.drawImage(image,0,0,1240,860);
 const src=bctx.getImageData(0,0,1240,860).data;
 const cache=new Map();
 let lastCenter=null,lastTime=null,lastInfo=null;
 function resetCamera(){lastCenter=null;lastTime=null;lastInfo=null}
 function pxPerMetre(width){return clamp((width-40)/47,6.7,8.2)}
 function makeTile(index,ppm){
  const key=index+':'+ppm.toFixed(4);
  if(cache.has(key)){const val=cache.get(key);cache.delete(key);cache.set(key,val);return val}
  const off=document.createElement('canvas');off.width=T_W;off.height=T_H;
  const ctx=off.getContext('2d');
  const pixels=ctx.createImageData(T_W,T_H),dst=pixels.data;
  const delta=1/ppm,start=index*T_W/ppm;
  for(let x=0;x<T_W;x++){
   const d=clamp(start+x*delta,0,distance);
   const p0=route.point(d,0),p14=route.point(d,14),
    vX=(p14.x-p0.x)/14,vY=(p14.y-p0.y)/14;
   for(let y=0;y<T_H;y++){
    const lane=BASE_LANE+(y-T_H/2)/L_PX,
     sx=Math.round((p0.x+vX*lane)*2),
     sy=Math.round((p0.y+vY*lane)*2),
     to=(y*T_W+x)*4;
    if(sx>=0&&sx<1240&&sy>=0&&sy<860){
     const from=(sy*1240+sx)*4;
     dst[to]=src[from];dst[to+1]=src[from+1];
     dst[to+2]=src[from+2];dst[to+3]=255;
    }else{dst[to]=245;dst[to+1]=247;dst[to+2]=241;dst[to+3]=255}
   }
  }
  ctx.putImageData(pixels,0,0);
  cache.set(key,off);
  while(cache.size>CACHE_LIMIT)cache.delete(cache.keys().next().value);
  return off;
 }
 function frame({ctx,width,height,points,leaderD,timeSeconds,paintNumber,leaderNo,labelLayout}){
  if(!Array.isArray(points)||!points.length||!Number.isFinite(timeSeconds))
   throw Error('DISTANCE_BROADCAST_INPUT_INVALID');
  if(lastTime!==null&&timeSeconds<lastTime-1e-7)resetCamera();
  const dt=lastTime===null?0:clamp(timeSeconds-lastTime,0,.3);
  const values=points.map(p=>p.lane);
  const low=Math.min(...values),high=Math.max(...values),center=(low+high)/2;
  if(lastCenter===null)lastCenter=center;
  else lastCenter+=(center-lastCenter)*(1-Math.exp(-dt*2.4));
  lastTime=timeSeconds;
  const ppm=pxPerMetre(width);
  const leadX=width*.23;
  const yShift=height/2-T_H/2+(BASE_LANE-lastCenter)*L_PX;
  ctx.save();
  // Each tile is reconstructed ONCE from source imagery, then reused for
  // the rest of the race. All markers use exact (d,lane) in this projection.
  const d0=leaderD-(width-leadX)/ppm-1;
  const d1=leaderD+leadX/ppm+1;
  const tileStart=Math.floor(d0*ppm/T_W)-1;
  const tileEnd=Math.floor(d1*ppm/T_W)+1;
  for(let idx=tileStart;idx<=tileEnd;idx++){
   const tile=makeTile(idx,ppm);
   const screenLeft=leadX+(leaderD-(idx+1)*T_W/ppm)*ppm;
   ctx.save();ctx.translate(screenLeft+T_W,0);ctx.scale(-1,1);
   ctx.drawImage(tile,0,yShift);ctx.restore();
  }
  const trueMarkers=points.map(p=>({
   number:p.number,x:leadX+(leaderD-p.d)*ppm,
   y:height/2+(p.lane-lastCenter)*L_PX,d:p.d,lane:p.lane
  }));
  // Optional race-time-locked *display* offset. It cannot change distance
  // scale or individual physical horse values.
  const markers=typeof labelLayout==='function'?labelLayout(trueMarkers):trueMarkers;
  for(const p of markers){
   if(p.x>=-16&&p.x<=width+16&&p.y>=-16&&p.y<=height+16)
    paintNumber(ctx,p.number,p.x,p.y,width<540?.78:.84,p.number===leaderNo);
  }
  ctx.restore();
  const fieldGap=Math.max(...points.map(p=>p.d))-Math.min(...points.map(p=>p.d));
  lastInfo={mode:'source-ribbon-arc-length',fieldGapM:fieldGap,
   fieldGapPx:fieldGap*ppm,ppm,leadX,laneCenter:lastCenter,
   markers,originalSvgSamples:true,sourceGeometryImmutable:true,
   raceDistancesPreserved:true,
   physicalPositionsUnchanged:true};
  return lastInfo;
 }
 return Object.freeze({frame,metrics:()=>lastInfo,resetCamera,
  pxPerMetre,format:'original-svg-sampled-ribbon',courseIndependent:true});
}
g.RaceDistanceBroadcast=Object.freeze({create,courseIndependent:true,
 physicalPositionsUnchanged:true,sourceGeometryImmutable:true});
})(typeof window!=='undefined'?window:globalThis);
