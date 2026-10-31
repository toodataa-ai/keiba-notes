/* Source-local inspection only. No publisher image/paths are distributed here.
 * Coordinate inputs come from a SHA-pinned PPTX converted on the user's machine.
 * A successful numerical audit NEVER enables race animation or grants approval. */
(function(g){'use strict';
const PPTX_SHA='c6c372babca741439fe2c18857ea7d3fbccd42d115377448a836327ed53dc6c4';
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function build(input){
 if(input?.courseId!=='tokyo_turf_2000'||input.sourcePptxSha256!==PPTX_SHA||
   input.canAnimate!==false||input.distanceAnchorsSurveyed!==false||
   input.width!==620||Math.abs(input.height-620*9/13)>.001||
   !Number.isFinite(input.strokeWidth)||input.strokeWidth<22||input.strokeWidth>25||
   input.maxLane!==16||input.laneOffset!==9||input.discRadius!==.6||
   !/^[a-f0-9]{64}$/.test(input.sourceSvgSha256||''))throw Error('TOKYO_LOCAL_SOURCE_INVALID');
 const sections=JSON.parse(JSON.stringify(input.sections));
 const anchors=[0,100,300,900,1145,1474.1,2000,2120];
 if(sections?.length!==7)throw Error('TOKYO_SECTIONS_INVALID');
 function curve(s,t){
  if(s.kind==='arc'){
   const a=s.angles[0]+(s.angles[1]-s.angles[0])*t;
   return {x:s.center[0]+s.radius*Math.cos(a),y:s.center[1]+s.radius*Math.sin(a)};
  }
  const p=s.points,u=1-t;
  if(s.kind==='line')return{x:p[0][0]*u+p[1][0]*t,y:p[0][1]*u+p[1][1]*t};
  if(s.kind!=='cubic')throw Error('TOKYO_CURVE_INVALID');
  return{x:u**3*p[0][0]+3*u*u*t*p[1][0]+3*u*t*t*p[2][0]+t**3*p[3][0],
   y:u**3*p[0][1]+3*u*u*t*p[1][1]+3*u*t*t*p[2][1]+t**3*p[3][1]};
 }
 const table=[],sourceAnchors=[0];let length=0,last=null;
 for(let i=0;i<sections.length;i++){
  const s=sections[i];
  if(s.from!==anchors[i]||s.to!==anchors[i+1])throw Error('TOKYO_ANCHORS_INVALID');
  for(let j=0;j<=1000;j++){
   const p=curve(s,j/1000);
   if(!Number.isFinite(p.x)||!Number.isFinite(p.y)||p.x<0||p.x>620||p.y<0||p.y>input.height)
    throw Error('TOKYO_COORDINATE_INVALID');
   if(j===0&&last&&Math.hypot(p.x-last.x,p.y-last.y)>.001)throw Error('TOKYO_SOURCE_GAP');
   if(last)length+=Math.hypot(p.x-last.x,p.y-last.y);
   table.push({...p,s:length});last=p;
  }
  sourceAnchors.push(length);
 }
 // Shape-preserving cubic Hermite distance->source arclength; fixed anchors.
 // Shared tangents prevent a visible speed jump at a physical sector boundary.
 const gaps=anchors.slice(1).map((x,i)=>x-anchors[i]);
 const rates=gaps.map((h,i)=>(sourceAnchors[i+1]-sourceAnchors[i])/h);
 const derivatives=rates.map((r,i)=>i===0?r:
  (3*(gaps[i-1]+gaps[i]))/((2*gaps[i]+gaps[i-1])/rates[i-1]+(gaps[i]+2*gaps[i-1])/r));
 derivatives.push(rates.at(-1));
 function arcAt(d){
  d=clamp(d,0,2120);let i=sections.findIndex(s=>d<=s.to);if(i<0)i=6;
  const t=(d-anchors[i])/gaps[i],u=t*t,v=u*t;
  return (2*v-3*u+1)*sourceAnchors[i]+(v-2*u+t)*gaps[i]*derivatives[i]+
   (-2*v+3*u)*sourceAnchors[i+1]+(v-u)*gaps[i]*derivatives[i+1];
 }
 function atArc(s){
  s=clamp(s,0,length);let lo=0,hi=table.length-1;
  while(lo<hi){const mid=Math.floor((lo+hi)/2);if(table[mid].s<s)lo=mid+1;else hi=mid;}
  const b=table[lo],a=table[Math.max(0,lo-1)],t=(s-a.s)/(b.s-a.s||1);
  return{x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t};
 }
 function center(d){
  const s=arcAt(d),p=atArc(s),a=atArc(Math.max(0,s-.02)),b=atArc(Math.min(length,s+.02));
  const dx=b.x-a.x,dy=b.y-a.y,m=Math.hypot(dx,dy)||1;
  return {...p,tx:dx/m,ty:dy/m};
 }
 function point(d,lane){
  if(!Number.isFinite(d)||!Number.isFinite(lane)||d<0||d>2120||lane<0||lane>16)
   throw Error('TOKYO_PROBE_OUT_OF_RANGE');
  // Source coordinates have y downward: the LEFT-turn interior is (ty,-tx).
  const p=center(d),offset=9-18*lane/16;
  return{x:p.x+p.ty*offset,y:p.y-p.tx*offset,tx:p.tx,ty:p.ty};
 }
 function rail(d,side){const p=center(d),offset=(side==='inner'?1:-1)*input.strokeWidth/2;
  return{x:p.x+p.ty*offset,y:p.y-p.tx*offset};}
 return Object.freeze({point,center,rail,arcAt,width:620,height:input.height,
  canAnimate:false,discRadius:.6,sourceHalfWidth:input.strokeWidth/2});
}
g.RaceTokyoSourceAudit=Object.freeze({build,PPTX_SHA});
})(typeof window!=='undefined'?window:globalThis);
