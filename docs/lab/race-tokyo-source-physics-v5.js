/* Opt-in numerical candidate. Source geometry is supplied locally, never bundled.
 * Neither this adapter nor a passing audit grants route/visual approval. */
(function(g){'use strict';
const ID='source-linked-v5',COURSE='tokyo_turf_2000';
const GEOMETRY_SHA='281afd0bffdc43c7b314c2d5bd3ed544344eee2f75c4b6240571aa8381a7723d';
const SVG_SHAS=new Set(['4160369ab4103688c12ee9e3dce30a5e551766a234aaf1403091a1f1c3906c8e','8bd5ae2bcae689c196deb1adc4be3ef1c36e395d1d139b933b77c7f68d37b152']);
const KEYS=['courseId','sourcePptxSha256','sourceSlide','width','height','sections','finishMark','strokeWidth','laneOffset','discRadius','maxLane','sourceShapeIds','distanceAnchorsSurveyed','canAnimate'];
const sessions=new WeakMap(),clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function canonical(v){
 if(Array.isArray(v))return v.map(canonical);
 if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])]));
 if(typeof v==='number'){if(!Number.isFinite(v))throw Error('TOKYO_SOURCE_NONFINITE');return Math.round(v*1e6)/1e6;}
 return v;
}
function payload(input){return JSON.stringify(canonical(Object.fromEntries(KEYS.map(k=>[k,input[k]]))));}
async function prepare(input){
 // Clone before awaiting; caller edits during SHA verification cannot change the session.
 const data=JSON.parse(JSON.stringify(input)),route=g.RaceTokyoSourceAudit.build(data);
 const bytes=new TextEncoder().encode(payload(data));
 const sha=Array.from(new Uint8Array(await g.crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
 if(sha!==GEOMETRY_SHA||!SVG_SHAS.has(data.sourceSvgSha256))throw Error('TOKYO_SOURCE_GEOMETRY_UNRECOGNIZED');
 const shared=g.RaceCourseGeometry,base=shared.get(COURSE);
 const profile=JSON.parse(JSON.stringify(base));
 profile.sourcePlan={provider:'local SHA-pinned publisher PPTX',shapeMethod:'schematic source-linked LAB candidate; distance allocation and grade approximate, not surveyed',sourceWidth:route.width,sourceHeight:route.height};
 profile.user_approved_stage_geometry=false;
 // Engine labels and bending now share the SAME source-route anchors; no 130m legacy boundary.
 profile.segments=data.sections.slice(0,6).map((s,i)=>({from:s.from,to:s.to,name:s.name,
  kind:s.kind==='line'?(i===0?'chute':'straight'):'turn',bend:0}));
 profile.landmarks=profile.landmarks.map(x=>x.d===130?{...x,d:100}:x);
 // Heading derivative per race metre (NOT source pixel). Source is a schematic:
 // the resulting radius is explicitly a model assumption, not a measured radius.
 function curvature(d){
  const a=route.center(clamp(d-.5,0,2000)),b=route.center(clamp(d+.5,0,2000));
  const span=Math.min(2000,d+.5)-Math.max(0,d-.5);
  return Math.abs(Math.atan2(a.tx*b.ty-a.ty*b.tx,a.tx*b.tx+a.ty*b.ty))/(span||1);
 }
 const table=Array.from({length:8001},(_,i)=>curvature(i*.25));
 function metrics(p,d,lane=0){
  if(p!==profile)throw Error('TOKYO_SOURCE_PROFILE_MISMATCH');
  const x=clamp(d,0,2000),i=Math.min(7999,Math.floor(x*4)),t=x*4-i;
  const k=table[i]+(table[i+1]-table[i])*t;
  const s=profile.segments.find(s=>x<s.to)||profile.segments.at(-1);
  return{segment:s.name,kind:s.kind,bend:130*k,grade:shared.slope(profile,x),height:shared.height(profile,x),
   pathStretch:1+Math.max(0,lane)*1.65*k,straightLeft:Math.min(525.9,2000-x),
   toFinalStraight:Math.max(0,1474.1-x),isFinalStraight:x>=1474.1};
 }
 function freeze(v){if(v&&typeof v==='object'){Object.values(v).forEach(freeze);Object.freeze(v);}return v;}
 freeze(profile);
 const geometry=Object.freeze({...shared,get:id=>id===COURSE?profile:shared.get(id),metrics});
 const session=Object.freeze({model:ID,courseId:COURSE,geometrySha256:sha,sourceSvgSha256:data.sourceSvgSha256,
  canAnimate:false,approval:'not_approved',distanceAnchorsSurveyed:false});
 sessions.set(session,{geometry,route,profile});return session;
}
function resolve(data,session){
 if(data?.course_id!==COURSE||data.labTokyoSourceModel!==ID||data.scope!=='LAB_SYNTHETIC_NOT_OFFICIAL'||
  data.labTokyoMotion!=='bounded-lateral-v4'||data.horses?.length!==18||data.horses.some(h=>h.styleMeta?.source!=='LAB_SYNTHETIC_NOT_OFFICIAL')||
  !sessions.has(session))throw Error('TOKYO_SOURCE_SESSION_REQUIRED');
 return sessions.get(session).geometry;
}
function inspect(session){const entry=sessions.get(session);if(!entry)throw Error('TOKYO_SOURCE_SESSION_REQUIRED');
 // Public numerical functions return fresh objects; private profile is not exposed.
 return Object.freeze({point:entry.route.point,center:entry.route.center,rail:entry.route.rail,
  metrics:(d,lane=0)=>entry.geometry.metrics(entry.profile,d,lane),
  boundaries:()=>entry.profile.segments.map(s=>({...s}))});}
g.RaceTokyoSourcePhysicsV5=Object.freeze({ID,GEOMETRY_SHA,prepare,resolve,inspect,payload});
})(typeof window!=='undefined'?window:globalThis);
