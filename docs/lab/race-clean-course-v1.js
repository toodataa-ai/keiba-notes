/* LAB Clean Course v1 — normalized geometry, independent of image pixels.
 * Kyoto turf inner 2000m demonstration model; illustration-scale coordinates,
 * NOT GPS/surveyed rail geometry. Only race distances and 328.4m final straight
 * use the JRA profile. 1C 308.7m, 2C exit 530m, 3C entry 1270m are blueprint
 * checkpoints. Physical simulation and formal predictions are not modified. */
(function(global){'use strict';
const id='kyoto_turf_inner_2000';
// Umapot original (620x430) visual-registration points, separate from
// JRA's physical measurements. Intermediate section breaks are approximate.
const sections=Object.freeze([
 {from:0,to:308.7,kind:'straight',name:'スタート後の直線',
  p0:[350,317],p3:[178,303]},
 {from:308.7,to:530,kind:'turn',name:'1コーナー',
  p0:[178,303],p1:[135,299.5],p2:[153,223],p3:[165,203]},
 {from:530,to:720,kind:'turn',name:'2コーナー',
  p0:[165,203],p1:[177,183],p2:[173,164.431372549],p3:[208,161]},
 {from:720,to:1270,kind:'straight',name:'向正面（2角出口〜3角入口）',
  p0:[208,161],p3:[463,136]},
 {from:1270,to:1435,kind:'turn',name:'3コーナー',
  p0:[463,136],p1:[498.7,132.5],p2:[510,165],p3:[510,197]},
 {from:1435,to:1671.6,kind:'turn',name:'4コーナー',
  p0:[510,197],p1:[510,235],p2:[526,317],p3:[490,317]},
 {from:1671.6,to:2000,kind:'straight',name:'最後の直線',
  p0:[490,317],p3:[294,317]}
]);
const WIDTH_PX=28,WIDTH_M=24,DISTANCE=2000;
const JRA_DIMENSIONS=Object.freeze({distanceM:2000,lapInnerA:1782.8,
 firstTurnDistanceM:308.7,homeStraightA:328.4,
 minTurfWidthM:24,maxTurfWidthM:38,elevationInnerM:3.1});
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function segment(distance){
 const d=clamp(distance,0,DISTANCE);
 return sections.find(s=>d<=s.to+1e-8)||sections[sections.length-1];
}
function cubic(s,t){
 const q=1-t;
 const x=q*q*q*s.p0[0]+3*q*q*t*s.p1[0]+3*q*t*t*s.p2[0]+t*t*t*s.p3[0];
 const y=q*q*q*s.p0[1]+3*q*q*t*s.p1[1]+3*q*t*t*s.p2[1]+t*t*t*s.p3[1];
 const dx=3*q*q*(s.p1[0]-s.p0[0])+6*q*t*(s.p2[0]-s.p1[0])+3*t*t*(s.p3[0]-s.p2[0]);
 const dy=3*q*q*(s.p1[1]-s.p0[1])+6*q*t*(s.p2[1]-s.p1[1])+3*t*t*(s.p3[1]-s.p2[1]);
 return {x,y,dx,dy};
}
function raw(s,t){
 if(s.kind==='straight'){
  const dx=s.p3[0]-s.p0[0],dy=s.p3[1]-s.p0[1];
  return {x:s.p0[0]+dx*t,y:s.p0[1]+dy*t,dx,dy};
 }
 return cubic(s,t);
}
const tables=new WeakMap();
function byArc(s,fraction){
 if(s.kind==='straight')return fraction;
 if(!tables.has(s)){
  const arc=[0];let last=raw(s,0),length=0;
  for(let i=1;i<=200;i++){
   const p=raw(s,i/200);length+=Math.hypot(p.x-last.x,p.y-last.y);
   arc.push(length);last=p;
  }
  tables.set(s,{arc,length});
 }
 const table=tables.get(s),wanted=clamp(fraction,0,1)*table.length;
 let lo=0,hi=200;
 while(lo<hi){const mid=Math.floor((lo+hi)/2);if(table.arc[mid]<wanted)lo=mid+1;else hi=mid}
 const j=Math.max(0,lo-1);
 return (j+(wanted-table.arc[j])/(table.arc[j+1]-table.arc[j]||1))/200;
}
function center(distance){
 const s=segment(distance);
 const t=byArc(s,clamp((distance-s.from)/(s.to-s.from),0,1));
 const p=raw(s,t),m=Math.hypot(p.dx,p.dy)||1;
 const endOver=Math.max(0,Math.min(40,distance-DISTANCE));
 return {x:p.x+p.dx/m*endOver*.52,y:p.y+p.dy/m*endOver*.52,
   tx:p.dx/m,ty:p.dy/m,section:s.name,kind:s.kind};
}
function rails(d){
 const c=center(d),nx=-c.ty,ny=c.tx;
 return {inner:{x:c.x+nx*WIDTH_PX/2,y:c.y+ny*WIDTH_PX/2},
  outer:{x:c.x-nx*WIDTH_PX/2,y:c.y-ny*WIDTH_PX/2},
  center:c,widthPx:WIDTH_PX,widthMetres:WIDTH_M};
}
function fraction(lane){return clamp((1.8+Math.max(0,Number(lane)||0)*1.65)/WIDTH_M,.025,.95)}
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
 if(sections[0].from!==0||sections.at(-1).to!==DISTANCE)throw Error('CLEAN_COURSE_DISTANCE');
 for(let i=0;i<sections.length;i++){
  const s=sections[i];
  if(!(s.to>s.from))throw Error('CLEAN_COURSE_BAD_SPAN');
  if(i){
   const p=sections[i-1];
   if(Math.abs(s.from-p.to)>1e-8 ||
    Math.hypot(s.p0[0]-p.p3[0],s.p0[1]-p.p3[1])>1e-6)
      throw Error('CLEAN_COURSE_DISCONNECTED');
   const a=raw(p,1),b=raw(s,0);
   const cross=a.dx*b.dy-a.dy*b.dx,dot=a.dx*b.dx+a.dy*b.dy;
   if(Math.abs(cross)>Math.hypot(a.dx,a.dy)*Math.hypot(b.dx,b.dy)*1e-8||dot<=0)
    throw Error('CLEAN_COURSE_TANGENT_BROKEN');
  }
 }
 for(let d=0;d<=DISTANCE;d+=5){
  const e=rails(d);
  for(const l of [0,1,3,6,9,12]){
   const p=point(d,l),f=fraction(l);
   if(Math.hypot(p.x-e.inner.x-(e.outer.x-e.inner.x)*f,
    p.y-e.inner.y-(e.outer.y-e.inner.y)*f)>1e-7)
    throw Error('CLEAN_COURSE_OUTSIDE_TURF');
  }
 }
 return true;
}
const api=Object.freeze({id,distance:DISTANCE,widthPx:WIDTH_PX,
 widthMetres:WIDTH_M,jraDimensions:JRA_DIMENSIONS,
 sourceImageSize:{width:620,height:430},
 illustratedRouteModel:'Umapot visual alignment, not surveyed coordinates',
 sections,segment,center,rails,fraction,point,runners,validate});
api.validate();
global.RaceCleanCourse=api;
})(typeof window!=='undefined'?window:globalThis);
