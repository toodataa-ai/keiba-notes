/* LAB clean course v4 - source-image registered inner Kyoto 2000 course.
 * The SVG-quality rendered guide is sampled every ONE race-metre in a common
 * arc-length-parametrized centerline. The guide is derived from visual
 * registrations against the original 620x430 Umapot reference and is NOT GPS.
 * Physical speed, lanes and official JRA data are never adjusted here. */
(function(global){'use strict';
const id='kyoto_turf_inner_2000',DISTANCE=2000;
const WIDTH_PX=16,WIDTH_M=27;
const JRA_DIMENSIONS=Object.freeze({distanceM:2000,lapInnerA:1782.8,
 firstTurnDistanceM:308.7,homeStraightA:328.4,
 minTurfWidthM:27,maxTurfWidthM:38,elevationInnerM:3.1});
const sections=Object.freeze([
 {from:0,to:308.7,kind:'straight',name:'スタート後の直線',p0:[350,317],p3:[183,317]},
 {from:308.7,to:530,kind:'turn',name:'1コーナー',
  p0:[183,317],p1:[159,317],p2:[166,280],p3:[167,226]},
 {from:530,to:720,kind:'turn',name:'2コーナー',
  p0:[167,226],p1:[167.5,199],p2:[181,166.8],p3:[215,162]},
 {from:720,to:1270,kind:'straight',name:'向正面（2角出口〜3角入口）',
  p0:[215,162],p3:[470,126]},
 {from:1270,to:1435,kind:'turn',name:'3コーナー',
  p0:[470,126],p1:[504,121.2],p2:[532,163],p3:[531,212]},
 {from:1435,to:1671.6,kind:'turn',name:'4コーナー',
  p0:[531,212],p1:[529.84,269],p2:[527,317],p3:[487,317]},
 {from:1671.6,to:2000,kind:'straight',name:'最後の直線',
  p0:[487,317],p3:[294,317]}
]);
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function segment(distance){
 const d=clamp(distance,0,DISTANCE);
 return sections.find(s=>d<=s.to+1e-8)||sections[sections.length-1];
}
function raw(s,t){
 const q=1-t;
 if(s.kind==='straight')return {x:s.p0[0]*q+s.p3[0]*t,y:s.p0[1]*q+s.p3[1]*t};
 const x=q*q*q*s.p0[0]+3*q*q*t*s.p1[0]+3*q*t*t*s.p2[0]+t*t*t*s.p3[0];
 const y=q*q*q*s.p0[1]+3*q*q*t*s.p1[1]+3*q*t*t*s.p2[1]+t*t*t*s.p3[1];
 return {x,y};
}
// Each source-image guide curve is parametrized by visual arc length,
// not by its Bezier t value; race distance changes position continuously.
const arcTables=new WeakMap();
function arcT(s,f){
 if(s.kind==='straight')return f;
 if(!arcTables.has(s)){
  const steps=600,arc=[0];let prev=raw(s,0),len=0;
  for(let i=1;i<=steps;i++){
   const next=raw(s,i/steps);
   len+=Math.hypot(next.x-prev.x,next.y-prev.y);
   arc.push(len);prev=next;
  }
  arcTables.set(s,{arc,len,steps});
 }
 const {arc,len,steps}=arcTables.get(s),want=clamp(f,0,1)*len;
 let lo=0,hi=steps;
 while(lo<hi){const m=(lo+hi)>>1;if(arc[m]<want)lo=m+1;else hi=m}
 const j=clamp(lo-1,0,steps-1);
 return (j+(want-arc[j])/(arc[j+1]-arc[j]||1))/steps;
}
function sourcePosition(distance){
 const d=clamp(distance,0,DISTANCE),s=segment(d);
 return raw(s,arcT(s,(d-s.from)/(s.to-s.from)));
}
// A dense shared 1m lookup eliminates per-frame image masks and permits
// smooth C1 Hermite interpolation across all section boundaries.
const coordinates=Array.from({length:DISTANCE+1},(_,d)=>sourcePosition(d));
const velocities=coordinates.map((pt,i)=>{
 const a=coordinates[Math.max(0,i-1)],b=coordinates[Math.min(DISTANCE,i+1)];
 const divisor=i===0||i===DISTANCE?1:2;
 return {x:(b.x-a.x)/divisor,y:(b.y-a.y)/divisor};
});
function smoothPoint(d){
 if(d>=DISTANCE){
  const end=coordinates[DISTANCE],v=velocities[DISTANCE];
  return {x:end.x+v.x*Math.min(42,d-DISTANCE),y:end.y+v.y*Math.min(42,d-DISTANCE),
   dx:v.x,dy:v.y};
 }
 const x=clamp(d,0,DISTANCE),i=Math.min(1999,Math.floor(x)),t=x-i;
 const a=coordinates[i],b=coordinates[i+1],u=velocities[i],v=velocities[i+1];
 const t2=t*t,t3=t2*t;
 const h00=2*t3-3*t2+1,h10=t3-2*t2+t,h01=-2*t3+3*t2,h11=t3-t2;
 return {
  x:h00*a.x+h10*u.x+h01*b.x+h11*v.x,
  y:h00*a.y+h10*u.y+h01*b.y+h11*v.y,
  dx:(6*t2-6*t)*a.x+(3*t2-4*t+1)*u.x+(-6*t2+6*t)*b.x+(3*t2-2*t)*v.x,
  dy:(6*t2-6*t)*a.y+(3*t2-4*t+1)*u.y+(-6*t2+6*t)*b.y+(3*t2-2*t)*v.y
 };
}
function center(distance){
 const c=smoothPoint(distance),m=Math.hypot(c.dx,c.dy)||1;
 const sec=segment(distance);
 return {x:c.x,y:c.y,tx:c.dx/m,ty:c.dy/m,section:sec.name,kind:sec.kind};
}
function rails(d){
 const c=center(d),nx=-c.ty,ny=c.tx;
 // Both rails use the same tangent and a constant visual corridor.
 // No independently interpolated per-section normal offsets or seams.
 return {inner:{x:c.x+nx*WIDTH_PX/2,y:c.y+ny*WIDTH_PX/2},
  outer:{x:c.x-nx*WIDTH_PX/2,y:c.y-ny*WIDTH_PX/2},
  center:c,widthPx:WIDTH_PX,widthMetres:WIDTH_M};
}
function fraction(lane){
 return clamp((1.8+Math.max(0,Number(lane)||0)*1.65)/WIDTH_M,.025,.95);
}
function point(d,lane=0){
 const edges=rails(d),f=fraction(lane);
 return {x:edges.inner.x+(edges.outer.x-edges.inner.x)*f,
  y:edges.inner.y+(edges.outer.y-edges.inner.y)*f,
  d,lane,section:edges.center.section};
}
function runners(state){
 return state.horses.map(h=>({number:h.number,d:h.displayD??h.d,lane:h.lane,
  ...point(h.displayD??h.d,h.lane),finished:h.finished}));
}
function validate(){
 if(coordinates.length!==2001||sections[0].from!==0||sections.at(-1).to!==2000)
  throw Error('LAB_PATH_LENGTH');
 for(let i=1;i<sections.length;i++){
  const a=sections[i-1],b=sections[i];
  if(Math.abs(a.to-b.from)>1e-8||
   Math.hypot(a.p3[0]-b.p0[0],a.p3[1]-b.p0[1])>1e-7)
    throw Error('LAB_JOIN_DISCONNECTED');
 }
 for(let d=1;d<=2000;d++){
  const a=center(d-1),b=center(d);
  if(!Number.isFinite(b.x+b.y+b.tx+b.ty) ||
   Math.hypot(a.x-b.x,a.y-b.y)>2.2)throw Error('LAB_PATH_JUMP_'+d);
 }
 for(let d=0;d<=2000;d+=5){
  const r=rails(d);
  for(const lane of [0,1,3,6,9,12]){
   const p=point(d,lane),f=fraction(lane);
   if(Math.hypot(p.x-r.inner.x-(r.outer.x-r.inner.x)*f,
    p.y-r.inner.y-(r.outer.y-r.inner.y)*f)>1e-7)
    throw Error('LAB_LANE_PROJECTION_'+d);
  }
 }
 return true;
}
const api=Object.freeze({id,distance:DISTANCE,widthPx:WIDTH_PX,
 widthMetres:WIDTH_M,jraDimensions:JRA_DIMENSIONS,
 sourceImageSize:{width:620,height:430},
 illustratedRouteModel:'Umapot traced smooth 1m path, not surveyed geometry',
 sections,segment,center,rails,fraction,point,runners,validate,
 densePointCount:coordinates.length,denseSpacingM:1});
api.validate();
global.RaceCleanCourse=api;
})(typeof window!=='undefined'?window:globalThis);
