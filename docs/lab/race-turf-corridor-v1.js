/* Generic source-image rail-corridor -> horse position projection, LAB v0.49.
 * Source is derived numerical green turf boundaries, no bitmap redistributed.
 * The physical tactical lane index is unchanged: same RaceLaneAI/Engine as Kyoto
 * outer 1400. Display lies BETWEEN inner & outer turf edges for every lane.
 */
(function(global){'use strict';
const registry=new Map();
const clamp=(x,lo,hi)=>Math.min(hi,Math.max(lo,x));
function register(data){
 if(data?.schema_version!=='lab-turf-rail-v1'||!Array.isArray(data.rail_offsets)||
    data.rail_offsets.length<100||data.source_not_embedded!==true||
    data.image_size?.[0]!==620||data.image_size?.[1]!==430)
  throw Error('TURF_RAIL_DATA_UNVERIFIED');
 let previous=-Infinity;
 for(const [d,outer,inner] of data.rail_offsets){
  if(!Number.isFinite(d)||d<=previous||![outer,inner].every(Number.isFinite)||
    !(inner>outer+3 && inner<outer+70))
   throw Error('TURF_RAIL_INVALID_EDGES_AT_'+d);
  previous=d;
 }
 if(data.rail_offsets[0][0]!==0 ||previous<1000)
  throw Error('TURF_RAIL_INCOMPLETE');
 registry.set(data.course_id,data);
 return true;
}
function has(courseId){return registry.has(courseId)}
function offsets(course,d){
 const record=registry.get(course.id);
 if(!record)throw Error('TURF_RAIL_COURSE_NOT_CALIBRATED_'+course.id);
 const seq=record.rail_offsets,dist=clamp(d,0,course.distance_m);
 let lo=0,hi=seq.length-1;
 while(lo<hi){const m=Math.floor((lo+hi)/2);if(seq[m][0]<dist)lo=m+1;else hi=m}
 const j=Math.max(0,lo-1),a=seq[j],b=seq[Math.min(j+1,seq.length-1)];
 const t=clamp((dist-a[0])/(b[0]-a[0]||1),0,1);
 return {outer:a[1]*(1-t)+b[1]*t,inner:a[2]*(1-t)+b[2]*t};
}
function rails(course,d,legacyPoint){
 if(!has(course.id))throw Error('TURF_RAIL_COURSE_NOT_CALIBRATED_'+course.id);
 const at=clamp(d,0,course.distance_m),before=legacyPoint(course,Math.max(0,at-.3),0);
 const after=legacyPoint(course,Math.min(course.distance_m,at+.3),0);
 const length=Math.hypot(after.x-before.x,after.y-before.y)||1;
 const normal={x:-(after.y-before.y)/length,y:(after.x-before.x)/length};
 const centre=legacyPoint(course,at,0),off=offsets(course,at);
 const offsetPosition=shift=>({x:centre.x+normal.x*shift,y:centre.y+normal.y*shift});
 const outer=offsetPosition(off.outer),inner=offsetPosition(off.inner);
 return {inner,outer,normal,widthPx:off.inner-off.outer,
   widthMetres:Math.min(...course.track_width_m)};
}
function fraction(course,lane){
 const width=Math.min(...course.track_width_m);
 if(!(width>0))throw Error('TURF_RAIL_WIDTH_UNKNOWN');
 // 1.8m off the inner rail for line 0, plus physical 1.65m per lane.
 return clamp((1.8+Math.max(0,Number(lane)||0)*1.65)/width,.025,.975);
}
function point(course,d,lane,legacyPoint){
 const band=rails(course,d,legacyPoint),r=fraction(course,lane);
 return {x:band.inner.x+(band.outer.x-band.inner.x)*r,
         y:band.inner.y+(band.outer.y-band.inner.y)*r};
}
global.RaceTurfCorridor=Object.freeze({register,has,offsets,rails,fraction,point});
})(typeof window!=='undefined'?window:globalThis);
