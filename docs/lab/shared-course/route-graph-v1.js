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

// Compile immutable course data into the distance-domain API used by the engine.
// The small build() API above is retained for PR1's original structural tests.
function compile(blueprint,spec){
 g.RaceCourseValidator.validate(blueprint,spec);
 const clone=x=>JSON.parse(JSON.stringify(x));
 blueprint=g.RaceCourseValidator.freeze(clone(blueprint));
 spec=g.RaceCourseValidator.freeze(clone(spec));
 const edgeMap=new Map(blueprint.edges.map(e=>[e.id,e]));
 function spline(edge,d){
  const k=edge.rails;
  const slopes=k.slice(1).map((r,i)=>r.slice(1).map((v,j)=>(v-k[i][j+1])/(r[0]-k[i][0])));
  const tangent=i=>{
   if(edge.from===edge.to&&(i===0||i===k.length-1)){
    const h0=k.at(-1)[0]-k.at(-2)[0],h1=k[1][0]-k[0][0];
    return slopes.at(-1).map((a,j)=>(a*h1+slopes[0][j]*h0)/(h0+h1));
   }
   if(i===0)return slopes[0];if(i===k.length-1)return slopes.at(-1);
   const h0=k[i][0]-k[i-1][0],h1=k[i+1][0]-k[i][0];
   return slopes[i-1].map((a,j)=>(a*h1+slopes[i][j]*h0)/(h0+h1));
  };
  let i=0;while(i<k.length-2&&d>k[i+1][0])i++;
  const a=k[i],b=k[i+1],h=b[0]-a[0],t=(d-a[0])/h,t2=t*t,t3=t2*t;
  const m=tangent(i),n=tangent(i+1);
  return a.slice(1).map((v,j)=>(2*t3-3*t2+1)*v+(t3-2*t2+t)*h*m[j]+(-2*t3+3*t2)*b[j+1]+(t3-t2)*h*n[j]);
 }
 function legs(ids,offset=0){
  let start=-offset;
  return ids.map(id=>{const edge=edgeMap.get(id),leg={edge,start,end:start+edge.lengthM};start=leg.end;return leg;});
 }
 const race=legs(spec.edgeIds,spec.startOffsetM),runoff=legs(spec.runoff.edgeIds);
 const maxD=spec.distanceM+spec.runoff.distanceM;
 function locate(d){
  if(!Number.isFinite(d)||d<0||d>maxD)fail('distance outside registered route/runoff');
  const list=d>spec.distanceM?runoff:race,x=d>spec.distanceM?d-spec.distanceM:d;
  const leg=list.find(l=>x<l.end)||list.at(-1);
  return {edge:leg.edge,d:x-leg.start,runoff:d>spec.distanceM};
 }
 function rails(d){const at=locate(d),r=spline(at.edge,at.d);return {inner:{x:r[0],y:r[1]},outer:{x:r[2],y:r[3]},edgeId:at.edge.id,surface:at.edge.surface};}
 function position(d,fraction=.5){
  if(!Number.isFinite(fraction)||fraction<0||fraction>1)fail('lane fraction');
  const r=rails(d);return {x:r.inner.x+(r.outer.x-r.inner.x)*fraction,y:r.inner.y+(r.outer.y-r.inner.y)*fraction};
 }
 function tangent(d,fraction=.5){
  const a=position(Math.max(0,d-.001),fraction),b=position(Math.min(maxD,d+.001),fraction);
  const n=Math.hypot(b.x-a.x,b.y-a.y);if(n<1e-12)fail('stationary/reversing tangent');
  return {x:(b.x-a.x)/n,y:(b.y-a.y)/n};
 }
 function height(d){const at=locate(d),k=at.edge.gradeProfile;let i=1;while(i<k.length-1&&at.d>k[i][0])i++;return k[i-1][1]+(k[i][1]-k[i-1][1])*(at.d-k[i-1][0])/(k[i][0]-k[i-1][0]);}
 function grade(d){const a=Math.max(0,d-.1),b=Math.min(maxD,d+.1);return (height(b)-height(a))/(b-a);}
 function section(d){locate(d);return d>spec.distanceM?{kind:'straight',name:'ゴール後'}:spec.sections.find(s=>d<s.to)||spec.sections.at(-1);}
 // Reject bow-tie corridors and spline overshoot, including between knots.
 const cross=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
 const intersect=(a,b,c,d)=>cross(a,b,c)*cross(a,b,d)<-1e-15&&cross(c,d,a)*cross(c,d,b)<-1e-15;
 let previous=null;
 const samples=Math.ceil(maxD*4);
 for(let i=0;i<=samples;i++){
  const d=maxD*i/samples,r=rails(d);
  if([r.inner.x,r.inner.y,r.outer.x,r.outer.y].some(v=>!Number.isFinite(v)||v<0||v>1)||Math.hypot(r.inner.x-r.outer.x,r.inner.y-r.outer.y)<1e-7)fail('invalid interpolated rails');
  if(previous&&(intersect(previous.inner,r.inner,previous.outer,r.outer)||intersect(previous.inner,previous.outer,r.inner,r.outer)))fail('crossed rails');
  const heading=tangent(d),side=heading.x*(r.outer.y-r.inner.y)-heading.y*(r.outer.x-r.inner.x);
  if(blueprint.turn==='右'&&side>=-1e-12||blueprint.turn==='左'&&side<=1e-12||Math.abs(side)<1e-12)fail('inner/outer rail orientation');
  previous=r;
 }
 // Node joins require position and travel direction continuity. Branches may
 // share a merge node; only the selected directed edge sequence is traversed.
 for(const list of [race,[...race.slice(-1),...runoff]])for(let i=1;i<list.length;i++){
  const a=list[i-1].edge,b=list[i].edge;
  const p=spline(a,a.lengthM-.001),q=spline(a,a.lengthM),r=spline(b,0),t=spline(b,.001);
  const u=[(q[0]+q[2]-p[0]-p[2]),(q[1]+q[3]-p[1]-p[3])],v=[(t[0]+t[2]-r[0]-r[2]),(t[1]+t[3]-r[1]-r[3])];
  const cosine=(u[0]*v[0]+u[1]*v[1])/(Math.hypot(...u)*Math.hypot(...v));
  if(!Number.isFinite(cosine)||cosine<1-1e-6)fail('discontinuous join tangent');
 }
 const geometryProfile={id:spec.id,venue:blueprint.venue,turn:blueprint.turn,distance_m:spec.distanceM,
  straight_m:spec.finalStraightM,track_width_m:[Math.min(...race.map(l=>l.edge.widthM)),Math.max(...race.map(l=>l.edge.widthM))],
  // The legacy downhill helper consumes profile; expose the same height API
  // as an explicit sampled profile. Unknown elevations remain labelled.
  profile:Array.from({length:spec.distanceM+1},(_,d)=>[d,height(d)]),landmarks:spec.anchorsM.map(d=>({d,label:section(d).name}))};
 g.RaceCourseValidator.freeze(geometryProfile);
 function metrics(profile,d,lane=0){
  if(profile!==geometryProfile)fail('profile mismatch');
  d=Math.max(0,Math.min(spec.distanceM,d));const at=locate(d),s=section(d),bend=at.edge.bend;
  return {segment:s.name,kind:s.kind,bend,grade:grade(d),height:height(d),surface:at.edge.surface,
   pathStretch:bend>.001?1+Math.max(0,lane)*1.65/(130/Math.max(bend,.2)):1,
   straightLeft:Math.min(spec.finalStraightM,spec.distanceM-d),toFinalStraight:Math.max(0,spec.distanceM-spec.finalStraightM-d),isFinalStraight:d>=spec.distanceM-spec.finalStraightM};
 }
 const geometry=Object.freeze({get:id=>id===spec.id?geometryProfile:null,metrics,height:(_p,d)=>height(d)});
 return Object.freeze({blueprint,spec,distanceM:spec.distanceM,maxDistanceM:maxD,rails,position,tangent,section,grade,height,geometry});
}
g.RaceRouteGraph=Object.freeze({build,compile});
})(typeof window==='undefined'?globalThis:window);
