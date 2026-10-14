/* JRA course geometry experiment v0.27.
 * Official numbers: Tokyo turf A lap 2083.1m, final straight 525.9m, elevation range 2.7m;
 * Kyoto turf outer A lap 1894.3m, final straight 403.7m, elevation range 4.3m.
 * Waypoints are traced from JRA official planar diagrams, not surveyed GPS coordinates.
 * The racing line respects each race's START, bends and finish; its d-axis is in race metres.
 * Keep all experimental geometry separate from the immutable JRA betting/prediction model.
 */
(function(global){
'use strict';
const COURSE={
 tokyo_turf_2000:{
  id:'tokyo_turf_2000',venue:'東京',course:'芝2000m',layout:'Aコース・左回り',
  turn:'左',distance_m:2000,lap_m:2083.1,straight_m:525.9,
  track_width_m:[31,41],elevation_range_m:2.7,
  mapUnitsPerMeter:.55,
  sourcePlan:{provider:'JRA official course plane diagram',sourceWidth:568,sourceHeight:386,
    sourceUrl:'https://www.jra.go.jp/facilities/race/tokyo/course/',
    shapeMethod:'manual tracing of turf centreline on official 568×386 plane illustration; not surveyed GPS'},
  info:'JRA公式平面図から走路輪郭を再トレース。1・2コーナー奥の引き込み線発走／525.9mの直線／最後の上り坂',
  official:'https://jra.jp/facilities/race/tokyo/course/',
  feature_source:'https://www.jra.go.jp/keiba/thisweek/2025/1102_1/race.html',
  // Shape traced against JRA's publicly displayed planar course diagram.
  // Never redistribute the source bitmap. All coordinates are original
  // approximate route waypoints, not GIS positions or surveyed measurements.
  background:[
    ['M',134,269],['C',79,269,43,236,42,181],
    ['C',39,107,73,68,143,61],['C',239,57,335,56,422,61],
    ['C',483,63,527,98,527,161],['C',530,220,480,269,423,271],
    ['C',327,273,231,270,134,269]
  ],
  branch:[['M',529,213],['C',535,177,533,146,526,131]],
  // JRA 2,000m turf route: 2nd bend chute, upper backstretch, 3rd and 4th,
  // 525.9m lower grandstand straight. d metres remain official race metres.
  segments:[
   {from:0,to:130,name:'引き込み線・スタート',kind:'chute',bend:.15,p0:[529,211],p1:[532,185],p2:[532,154],p3:[526,131]},
   {from:130,to:300,name:'2コーナー',kind:'turn',bend:.85,p0:[526,131],p1:[520,91],p2:[492,60],p3:[435,62]},
   {from:300,to:900,name:'向正面',kind:'straight',bend:.03,p0:[435,62],p1:[341,57],p2:[241,60],p3:[143,65]},
   {from:900,to:1145,name:'3コーナー',kind:'turn',bend:.67,p0:[143,65],p1:[91,63],p2:[45,98],p3:[44,157]},
   {from:1145,to:1474.1,name:'4コーナー',kind:'turn',bend:.82,p0:[44,157],p1:[42,229],p2:[84,269],p3:[135,270]},
   {from:1474.1,to:2000,name:'最後の直線 525.9m',kind:'straight',bend:0,p0:[135,270],p1:[231,271],p2:[328,270],p3:[423,270]}
  ],
  profile:[[0,0],[510,-1.6],[760,-1.6],[900,-.1],[1170,-1.35],
    [1420,-.9],[1540,-.9],[1700,1.1],[2000,1.1]],
  landmarks:[{d:0,label:'START'},{d:130,label:'2角'},{d:900,label:'3角'},
    {d:1145,label:'4角'},{d:1474.1,label:'直線入口'},
    {d:1540,label:'上り坂'},{d:1700,label:'坂上'},{d:2000,label:'GOAL'}]
 },
 kyoto_turf_outer_1400:{
  id:'kyoto_turf_outer_1400',venue:'京都',course:'芝1400m外回り',layout:'Aコース・右外回り',
  turn:'右',distance_m:1400,lap_m:1894.3,straight_m:403.7,
  track_width_m:[24,38],elevation_range_m:4.3,
  mapUnitsPerMeter:.70,
  sourcePlan:{provider:'JRA official course plane diagram',sourceWidth:571,sourceHeight:306,
    sourceUrl:'https://www.jra.go.jp/facilities/race/kyoto/course/',
    shapeMethod:'manual tracing of outer turf centreline on official 571×306 plane illustration; not surveyed GPS'},
  info:'JRA公式平面図の芝外回り走路を再トレース。上側に長い引き込み線／3コーナーの坂／外回り3〜4コーナー／403.7mの直線',
  official:'https://www.jra.go.jp/facilities/race/kyoto/course/',
  feature_source:'https://www.jra.go.jp/keiba/thisweek/2025/1013_1/race.html',
  background:[
    ['M',173,209],['C',146,208,147,154,164,116],
    ['C',181,79,214,71,262,60],['C',329,42,403,33,459,35],
    ['C',507,34,536,74,538,129],['C',541,176,508,210,462,209],
    ['C',379,210,267,210,173,209]
  ],
  // Inner course uses the shorter internal bend and rejoins near the exit.
  inner_turn:[
    ['M',458,49],['C',488,52,509,86,500,128],
    ['C',496,163,480,194,462,209]
  ],
  branch:[['M',198,78],['C',143,87,80,104,20,101]],
  // Outer-course turf 1,400m starts at the left backstretch and continues
  // into the broad right-hand outer 3rd/4th bend; 403.7m lower straight.
  segments:[
   {from:0,to:365,name:'向正面・先行争い',kind:'straight',bend:0,p0:[195,78],p1:[286,58],p2:[371,36],p3:[458,35]},
   {from:365,to:570,name:'3コーナー・上り',kind:'turn',bend:.62,p0:[458,35],p1:[502,32],p2:[530,62],p3:[539,99]},
   {from:570,to:805,name:'3〜4コーナー・急な下り',kind:'turn',bend:.83,p0:[539,99],p1:[553,146],p2:[532,177],p3:[509,189]},
   {from:805,to:996.3,name:'4コーナー・直線へ',kind:'turn',bend:.66,p0:[509,189],p1:[497,201],p2:[479,209],p3:[462,209]},
   {from:996.3,to:1400,name:'平坦な直線 403.7m',kind:'straight',bend:0,p0:[462,209],p1:[367,209],p2:[270,209],p3:[179,209]}
  ],
  profile:[[0,0],[210,.25],[575,4.3],[610,4.3],[850,.4],[996.3,0],[1400,0]],
  landmarks:[{d:0,label:'START'},{d:365,label:'3角'},{d:600,label:'坂頂上'},
    {d:805,label:'4角'},{d:996.3,label:'直線入口'},{d:1400,label:'GOAL'}]
 }
};
function clamp(v,a,b){return Math.min(b,Math.max(a,v));}
function smoothstep(v){const x=clamp(v,0,1);return x*x*(3-2*x)}
function validate(profile){
 if(!profile||!Array.isArray(profile.segments)||profile.segments.length<2)throw Error('COURSE_PROFILE_MISSING');
 if(profile.segments[0].from!==0 || Math.abs(profile.segments[profile.segments.length-1].to-profile.distance_m)>1e-6)throw Error('COURSE_DISTANCE_INVALID');
 for(let i=0;i<profile.segments.length;i++){
   const s=profile.segments[i];
   if(!(s.to>s.from)||i>0&&Math.abs(s.from-profile.segments[i-1].to)>1e-5)throw Error('COURSE_GAP');
   for(const pt of [s.p0,s.p1,s.p2,s.p3])if(!Array.isArray(pt)||pt.length!==2||pt.some(x=>!Number.isFinite(x)))throw Error('COURSE_BAD_CONTROL_POINT');
   if(i&&Math.hypot(s.p0[0]-profile.segments[i-1].p3[0],s.p0[1]-profile.segments[i-1].p3[1])>1e-7)throw Error('COURSE_DISCONNECTED');
 }
 if(Math.abs(profile.distance_m-profile.straight_m-profile.segments.at(-1).from)>1e-4)throw Error('FINAL_STRAIGHT_NOT_MATCHED');
 const z=profile.profile.map(p=>p[1]);
 if(Math.abs(Math.max(...z)-Math.min(...z)-profile.elevation_range_m)>.01)throw Error('RELIEF_NOT_MATCHED');
 return true;
}
function cubic(s,t){
 const q=1-t;const a=q*q*q,b=3*q*q*t,c=3*q*t*t,d=t*t*t;
 const x=a*s.p0[0]+b*s.p1[0]+c*s.p2[0]+d*s.p3[0];
 const y=a*s.p0[1]+b*s.p1[1]+c*s.p2[1]+d*s.p3[1];
 let tx=3*q*q*(s.p1[0]-s.p0[0])+6*q*t*(s.p2[0]-s.p1[0])+3*t*t*(s.p3[0]-s.p2[0]);
 let ty=3*q*q*(s.p1[1]-s.p0[1])+6*q*t*(s.p2[1]-s.p1[1])+3*t*t*(s.p3[1]-s.p2[1]);
 const m=Math.hypot(tx,ty)||1;tx/=m;ty/=m;
 return {x,y,tx,ty};
}
// Sample Bezier arc length, so on-screen horses move evenly along actual drawn bends.
const arcTables=new Map();
function arcTable(segment){
 if(arcTables.has(segment))return arcTables.get(segment);
 const samples=[{t:0,length:0}],N=80;
 let prev=cubic(segment,0),dist=0;
 for(let i=1;i<=N;i++){
   const t=i/N,p=cubic(segment,t);
   dist+=Math.hypot(p.x-prev.x,p.y-prev.y);
   samples.push({t,length:dist});prev=p;
 }
 const table={total:dist,samples};
 arcTables.set(segment,table);return table;
}
function tByLength(segment,ratio){
 const tab=arcTable(segment),target=clamp(ratio,0,1)*tab.total;
 let lo=0,hi=tab.samples.length-1;
 while(lo<hi){const m=(lo+hi)>>1;if(tab.samples[m].length<target)lo=m+1;else hi=m;}
 const high=tab.samples[lo],low=tab.samples[Math.max(0,lo-1)];
 return low.t+(high.t-low.t)*(target-low.length)/(high.length-low.length||1);
}
function segmentAt(profile,d){
 const x=clamp(d,0,profile.distance_m);
 return profile.segments.find(s=>x<=s.to+1e-8)||profile.segments.at(-1);
}
function rawCenter(profile,d){
 const x=clamp(d,0,profile.distance_m),s=segmentAt(profile,x);
 return cubic(s,tByLength(s,clamp((x-s.from)/(s.to-s.from),0,1)));
}
/* ONE globally smooth race curve in distance coordinates for position and
 * tangent. Source Beziers are used only to prepare sampled control points.
 * Every frame evaluates the same C1 cubic-Hermite spline, across landmarks. */
function continuousLine(profile,source){
 const n=Math.ceil(profile.distance_m),step=profile.distance_m/n;
 const raw=Array.from({length:n+1},(_,i)=>source(i*step));
 function ext(i){
  if(i<0)return{x:raw[0].x+i*(raw[1].x-raw[0].x),y:raw[0].y+i*(raw[1].y-raw[0].y)};
  if(i>n)return{x:raw[n].x+(i-n)*(raw[n].x-raw[n-1].x),y:raw[n].y+(i-n)*(raw[n].y-raw[n-1].y)};
  return raw[i];
 }
 const kernel=Array.from({length:41},(_,j)=>Math.exp(-.5*((j-20)/7)**2));
 const total=kernel.reduce((a,b)=>a+b,0);
 const pts=raw.map((_,i)=>{
  let x=0,y=0;for(let j=0;j<41;j++){const p=ext(i+j-20),w=kernel[j];x+=p.x*w;y+=p.y*w}
  return{x:x/total,y:y/total};
 });
 const v=pts.map((p,i)=>{
  const lo=Math.max(0,i-1),hi=Math.min(n,i+1),div=(hi-lo)*step;
  return{x:(pts[hi].x-pts[lo].x)/div,y:(pts[hi].y-pts[lo].y)/div};
 });
 const unit=(x,y)=>{const mag=Math.hypot(x,y)||1;return{tx:x/mag,ty:y/mag}};
 function at(distance){
  const d=Number.isFinite(distance)?distance:0;
  if(d<=0)return{...pts[0],...unit(v[0].x,v[0].y)};
  if(d>=profile.distance_m){
   const excess=Math.min(40,d-profile.distance_m);
   return{x:pts[n].x+excess*v[n].x,y:pts[n].y+excess*v[n].y,...unit(v[n].x,v[n].y)};
  }
  const i=Math.min(n-1,Math.floor(d/step)),t=(d-i*step)/step;
  const a=pts[i],b=pts[i+1],m=v[i],q=v[i+1],t2=t*t,t3=t2*t;
  const x=(2*t3-3*t2+1)*a.x+(t3-2*t2+t)*step*m.x+
          (-2*t3+3*t2)*b.x+(t3-t2)*step*q.x;
  const y=(2*t3-3*t2+1)*a.y+(t3-2*t2+t)*step*m.y+
          (-2*t3+3*t2)*b.y+(t3-t2)*step*q.y;
  const dx=((6*t2-6*t)*a.x+(3*t2-4*t+1)*step*m.x+
           (-6*t2+6*t)*b.x+(3*t2-2*t)*step*q.x)/step;
  const dy=((6*t2-6*t)*a.y+(3*t2-4*t+1)*step*m.y+
           (-6*t2+6*t)*b.y+(3*t2-2*t)*step*q.y)/step;
  return{x,y,...unit(dx,dy)};
 }
 // Globally smooth, monotone visual-arc-length reparameterization.
 // Preserve exact landmark d->position knots while making the apparent
 // speed continuous even when adjoining source pieces have different scale.
 const arcLength=[0];let last=at(0),arc=0;
 for(let i=1;i<=n;i++){const p=at(i*step);arc+=Math.hypot(p.x-last.x,p.y-last.y);arcLength.push(arc);last=p}
 function measure(d){
  const index=Math.min(n-1,Math.max(0,Math.floor(d/step))),f=clamp(d/step-index,0,1);
  return arcLength[index]*(1-f)+arcLength[index+1]*f;
 }
 const boundaries=[0,...profile.segments.slice(1).map(s=>s.from),profile.distance_m];
 const knots=boundaries.map(measure);
 const meanSpeed=boundaries.slice(1).map((d,i)=>(knots[i+1]-knots[i])/(d-boundaries[i]));
 const slope=boundaries.map((_,i)=>i===0?meanSpeed[0]:i===boundaries.length-1?meanSpeed.at(-1):
  2*meanSpeed[i-1]*meanSpeed[i]/(meanSpeed[i-1]+meanSpeed[i]));
 function smoothArc(d){
  let i=0;while(i<boundaries.length-2&&d>=boundaries[i+1])i++;
  const L=boundaries[i+1]-boundaries[i],t=clamp((d-boundaries[i])/L,0,1),t2=t*t,t3=t2*t;
  return (2*t3-3*t2+1)*knots[i]+(t3-2*t2+t)*L*slope[i]+
   (-2*t3+3*t2)*knots[i+1]+(t3-t2)*L*slope[i+1];
 }
 function uniformAt(d){
  if(d<=0)return at(0);
  if(d>=profile.distance_m){
   const p=at(profile.distance_m),extra=Math.min(40,d-profile.distance_m),speed=slope.at(-1);
   return{x:p.x+p.tx*speed*extra,y:p.y+p.ty*speed*extra,tx:p.tx,ty:p.ty};
  }
  const target=clamp(smoothArc(d),0,arc);
  let low=0,high=n;
  while(low<high){const mid=(low+high)>>1;if(arcLength[mid]<target)low=mid+1;else high=mid}
  const i=Math.max(0,Math.min(n-1,low-1));
  const f=(target-arcLength[i])/(arcLength[i+1]-arcLength[i]||1);
  return at((i+f)*step);
 }
 return Object.freeze({at:uniformAt,sampleStep:step,length:profile.distance_m});
}
const raceLineCache=new WeakMap();
function raceLine(profile){
 if(!raceLineCache.has(profile))raceLineCache.set(profile,continuousLine(profile,d=>rawCenter(profile,d)));
 return raceLineCache.get(profile);
}
function point(profile,d,lane=0){
 const p=raceLine(profile).at(d),s=segmentAt(profile,d);
 const ratio=clamp((clamp(d,0,profile.distance_m)-s.from)/(s.to-s.from),0,1);
 const t=tByLength(s,ratio);
 const metersToMap=profile.mapUnitsPerMeter||1;
 const offset=(lane*1.65-(Math.min(...profile.track_width_m)/2-1.8))*metersToMap*(profile.turn==='左'?1:-1);
 return {x:p.x-p.ty*offset,y:p.y+p.tx*offset,tx:p.tx,ty:p.ty,segment:s,t};
}
function heading(profile,d,lane=0,laneVelocity=0){
 // Direction vector from arc-length normalized course coordinates (not
 // simply a horizontal right-facing sprite). Lateral movement gently changes
 // nose angle to show real lane transitions during overtaking.
 const before=point(profile,clamp(d-1.5,0,profile.distance_m),lane);
 const after=point(profile,clamp(d+1.5,0,profile.distance_m),lane);
 let x=after.x-before.x,y=after.y-before.y;
 if(Math.hypot(x,y)<.001){const p=point(profile,d,lane);x=p.tx;y=p.ty}
 const side=profile.turn==='左'?1:-1;
 const lateral=Math.max(-.8,Math.min(.8,laneVelocity))*.14;
 const scale=Math.hypot(x,y)||1;
 x/=scale;y/=scale;
 return Math.atan2(y+x*lateral*side,x-y*lateral*side);
}
function height(profile,d){
 const values=profile.profile;
 const x=clamp(d,0,profile.distance_m);
 for(let i=1;i<values.length;i++)if(x<=values[i][0]){
    const a=values[i-1],b=values[i];
    return a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0]);
 }
 return values.at(-1)[1];
}
function slope(profile,d){
 // Gradual grade changes prevent one-frame acceleration at elevation landmarks.
 const x=clamp(d,0,profile.distance_m),r=9;
 return (height(profile,clamp(x+r,0,profile.distance_m))-height(profile,clamp(x-r,0,profile.distance_m)))/(2*r);
}
function metrics(profile,d,lane=0){
 const s=segmentAt(profile,d);
 const turn=s.kind==='turn';
 // Approximate effective radius for lane-dependent path penalties:
 // absolute values are hypotheses because JRA does not publish all bend radii.
 let bend=turn?s.bend:0;
 // Blend estimated bend resistance over sector boundaries; segment labels
 // change exactly at landmarks but a horse cannot change drag instantly.
 for(let i=1;i<profile.segments.length;i++){
  const b=profile.segments[i].from;
  if(Math.abs(d-b)>20)continue;
  const prev=profile.segments[i-1],next=profile.segments[i];
  const left=prev.kind==='turn'?prev.bend:0,right=next.kind==='turn'?next.bend:0;
  bend=left+(right-left)*smoothstep((d-b+20)/40);
  break;
 }
 const laneOffsetM=Math.max(0,lane)*1.65; // same units as lane decisions
 const pathStretch=bend>.001?1+laneOffsetM/(130/Math.max(bend,.2)):1;
 const groundBonus=slope(profile,d);
 return {segment:s.name,kind:s.kind,bend,grade:groundBonus,
         height:height(profile,d),pathStretch,
         straightLeft:Math.min(profile.straight_m,profile.distance_m-d),
         toFinalStraight:Math.max(0,profile.distance_m-profile.straight_m-d),
         isFinalStraight:d>=profile.distance_m-profile.straight_m};
}
for(const c of Object.values(COURSE))validate(c);
function get(id){return COURSE[id]||null}
global.RaceCourseGeometry=Object.freeze({get,validate,point,heading,segmentAt,height,slope,metrics,continuousLine,COURSE});
})(typeof window!=='undefined'?window:globalThis);
