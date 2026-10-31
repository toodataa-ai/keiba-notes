/* LAB only. Directed routes use metres; image coordinates are normalized. */
(function(g){'use strict';
const finite=Number.isFinite;
function fail(message){throw Error('COURSE_GRAPH:'+message);}
function build(blueprint,spec){
 if(!blueprint||!spec||spec.blueprintId!==blueprint.id)fail('blueprint');
 if(!finite(spec.distanceM)||spec.distanceM<=0)fail('distance');
 const edges=new Map();
 for(const edge of blueprint.edges||[]){
  if(edges.has(edge.id)||!edge.id)fail('duplicate edge');
  if(!finite(edge.lengthM)||edge.lengthM<=0)fail('edge length');
  const k=edge.rails;
  if(!Array.isArray(k)||k.length<2||k[0][0]!==0||k.at(-1)[0]!==edge.lengthM)fail('anchors');
  for(let i=0;i<k.length;i++){
   if(k[i].length!==5||!k[i].every(finite)||k[i].slice(1).some(v=>v<0||v>1))fail('normalized rails');
   if(i&&k[i][0]<=k[i-1][0])fail('anchor order');
   if(Math.hypot(k[i][1]-k[i][3],k[i][2]-k[i][4])<1e-8)fail('zero width');
  }
  edges.set(edge.id,edge);
 }
 const route=[];let total=0;
 for(const id of spec.edgeIds||[]){
  const edge=edges.get(id);if(!edge)fail('missing edge');
  const prev=route.at(-1)?.edge;
  if(prev){
   if(prev.to!==edge.from)fail('disconnected nodes');
   if(prev.rails.at(-1).slice(1).some((v,i)=>Math.abs(v-edge.rails[0][i+1])>1e-8))fail('disconnected rails');
  }
  route.push({edge,start:total});total+=edge.lengthM;
 }
 if(!route.length||Math.abs(total-spec.distanceM)>1e-6)fail('route length');
 function rails(distance){
  if(!finite(distance)||distance<0||distance>total)fail('outside race; use explicit runoff');
  const leg=route.find(r=>distance<r.start+r.edge.lengthM)||route.at(-1);
  const d=distance-leg.start,k=leg.edge.rails;
  let i=0;while(i<k.length-2&&d>k[i+1][0])i++;
  const a=k[i],b=k[i+1],t=(d-a[0])/(b[0]-a[0]);
  const xy=a.slice(1).map((v,j)=>v+(b[j+1]-v)*t);
  return {inner:{x:xy[0],y:xy[1]},outer:{x:xy[2],y:xy[3]},edgeId:leg.edge.id,surface:leg.edge.surface};
 }
 function position(distance,fraction=.5){
  if(!finite(fraction)||fraction<0||fraction>1)fail('lane fraction');
  const r=rails(distance);return {x:r.inner.x+(r.outer.x-r.inner.x)*fraction,y:r.inner.y+(r.outer.y-r.inner.y)*fraction};
 }
 return Object.freeze({distanceM:total,rails,position});
}
g.RaceRouteGraph=Object.freeze({build});
})(typeof window==='undefined'?globalThis:window);
