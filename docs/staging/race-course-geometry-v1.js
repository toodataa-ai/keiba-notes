/* JRA course geometry experiment v0.2.
 * Official numbers: Tokyo turf A lap 2083.1m, final straight 525.9m, elevation range 2.7m;
 * Kyoto turf outer A lap 1894.3m, final straight 403.7m, elevation range 4.3m.
 * Bezier waypoints are hand-fit TOPOLOGICAL approximations, not surveyed GPS coordinates.
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
  info:'1・2コーナー奥の引き込み線発走／ゆったりした3つのコーナー／最後の525.9mと残り460〜300mの上り坂',
  official:'https://jra.jp/facilities/race/tokyo/course/',
  feature_source:'https://www.jra.go.jp/keiba/thisweek/2025/1102_1/race.html',
  // Outer circuit continues beyond the race-only start; turn 1 is passed on the chute.
  background:[
    ['M',138,181],['C',215,182,375,181,452,181],
    ['C',511,181,532,149,523,103],['C',518,63,499,47,452,42],
    ['C',368,39,250,43,164,47],['C',107,49,74,72,68,111],
    ['C',62,152,91,179,138,181]
  ],
  branch:[['M',518,131],['C',519,111,519,92,507,76]],
  // All segment lengths sum to 2000.0, last one exactly 525.9.
  segments:[
   {from:0,to:130,name:'引き込み線・スタート',kind:'chute',bend:.15,p0:[518,131],p1:[520,112],p2:[516,90],p3:[507,76]},
   {from:130,to:300,name:'2コーナー',kind:'turn',bend:.85,p0:[507,76],p1:[497,50],p2:[478,43],p3:[452,42]},
   {from:300,to:900,name:'向正面',kind:'straight',bend:.03,p0:[452,42],p1:[357,37],p2:[257,43],p3:[164,47]},
   {from:900,to:1145,name:'3コーナー',kind:'turn',bend:.67,p0:[164,47],p1:[113,49],p2:[74,73],p3:[68,111]},
   {from:1145,to:1474.1,name:'4コーナー',kind:'turn',bend:.82,p0:[68,111],p1:[62,154],p2:[94,182],p3:[150,181]},
   {from:1474.1,to:2000,name:'最後の直線 525.9m',kind:'straight',bend:0,p0:[150,181],p1:[245,182],p2:[357,181],p3:[452,181]}
  ],
  // High/low location estimated; absolute height origin arbitrary. Change across
  // final ramp is official ~2.0m, 1540m to 1700m (remaining 460m to 300m).
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
  info:'2角を回り切った向正面から発走／3コーナーの坂を上って残り800m付近から下る／平坦な403.7m直線',
  official:'https://www.jra.go.jp/facilities/race/kyoto/course/',
  feature_source:'https://www.jra.go.jp/keiba/thisweek/2025/1013_1/race.html',
  // Kyoto: the backstretch gently inclines upward toward the right on
  // the published plan; the LEFT 1st/2nd bend is broad and rounded.
  // The outer 3rd/4th bend on the RIGHT opens wider than the inner bend.
  // This drawing is an original schematic fitted to JRA's plane map,
  // NOT a set of geographical/surveyed GPS measurements.
  // Both 3rd/4th courses share the upper branch and 4th exit.
  background:[
    ['M',190,183],['C',116,184,77,166,71,123],
    ['C',67,89,99,54,166,59],['C',268,52,372,31,446,35],
    ['C',501,31,534,52,548,80],['C',563,124,550,153,521,168],
    ['C',508,180,484,183,462,183],
    ['C',377,183,272,183,190,183]
  ],
  inner_turn:[
    ['M',446,35],['C',488,39,508,62,512,99],
    ['C',517,136,496,169,462,183]
  ],
  segments:[
   {from:0,to:365,name:'向正面・先行争い',kind:'straight',bend:0,p0:[195,56],p1:[282,52],p2:[381,33],p3:[446,35]},
   {from:365,to:570,name:'3コーナー・上り',kind:'turn',bend:.62,p0:[446,35],p1:[502,31],p2:[531,49],p3:[548,80]},
   {from:570,to:805,name:'3〜4コーナー・急な下り',kind:'turn',bend:.83,p0:[548,80],p1:[561,112],p2:[548,149],p3:[521,168]},
   {from:805,to:996.3,name:'4コーナー・直線へ',kind:'turn',bend:.66,p0:[521,168],p1:[509,179],p2:[487,183],p3:[462,183]},
   {from:996.3,to:1400,name:'平坦な直線 403.7m',kind:'straight',bend:0,p0:[462,183],p1:[377,183],p2:[277,183],p3:[195,183]}
  ],
  // Crest at approximately 800m remaining, then a sharp descent; external
  // source confirms total relief of 4.3m, while profile breakpoints are estimates.
  profile:[[0,0],[210,.25],[575,4.3],[610,4.3],[850,.4],[996.3,0],[1400,0]],
  landmarks:[{d:0,label:'START'},{d:365,label:'3角'},{d:600,label:'坂頂上'},
    {d:805,label:'4角'},{d:996.3,label:'直線入口'},{d:1400,label:'GOAL'}]
 }
};
function clamp(v,a,b){return Math.min(b,Math.max(a,v));}
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
function point(profile,d,lane=0){
 if(d>profile.distance_m){
   const end=point(profile,profile.distance_m,lane),last=profile.segments.at(-1);
   const pxPerMeter=arcTable(last).total/(last.to-last.from);
   const extra=clamp(d-profile.distance_m,0,40)*pxPerMeter;
   return {...end,x:end.x+end.tx*extra,y:end.y+end.ty*extra,segment:last,t:1};
 }
 const s=segmentAt(profile,d);
 const ratio=clamp((clamp(d,0,profile.distance_m)-s.from)/(s.to-s.from),0,1);
 const t=tByLength(s,ratio);
 const p=cubic(s,t);
 // Lane zero is the inside running line. Lateral scale is illustrative,
 // but physical width in metres is applied separately in the simulator.
 // Map physical lane spacing to the JRA-reported minimum track width.
 // Leave ~1.8m per side for a safe rail buffer. This shares the lane model's
 // 1.65m spacing; outside horses must not be drawn beyond the turf rail.
 const railBuffer=1.8,minWidth=Math.min(...profile.track_width_m);
 const offset=(lane*1.65-(minWidth/2-railBuffer))*(profile.turn==='左'?1:-1);
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
 // Derivative over 1m using one-sided samples at breakpoints.
 const x=clamp(d,.5,profile.distance_m-.5);
 return height(profile,x+.5)-height(profile,x-.5);
}
function metrics(profile,d,lane=0){
 const s=segmentAt(profile,d);
 const turn=s.kind==='turn';
 // Approximate effective radius for lane-dependent path penalties:
 // absolute values are hypotheses because JRA does not publish all bend radii.
 const bend=turn?s.bend:0;
 const laneOffsetM=Math.max(0,lane)*2.9;
 const pathStretch=turn?1+laneOffsetM/(130/Math.max(bend,.2)):1;
 const groundBonus=slope(profile,d);
 return {segment:s.name,kind:s.kind,bend,grade:groundBonus,
         height:height(profile,d),pathStretch,
         straightLeft:Math.min(profile.straight_m,profile.distance_m-d),
         isFinalStraight:d>=profile.distance_m-profile.straight_m};
}
for(const c of Object.values(COURSE))validate(c);
function get(id){return COURSE[id]||null}
global.RaceCourseGeometry=Object.freeze({get,validate,point,heading,segmentAt,height,slope,metrics,COURSE});
})(typeof window!=='undefined'?window:globalThis);
