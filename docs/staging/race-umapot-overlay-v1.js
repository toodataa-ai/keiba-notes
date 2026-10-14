/* Umapot illustration registration (not surveyed GPS). The original images
 are linked, not republished. https://umapot.com/?page_id=116
 Tokyo https://umapot.com/?p=13273 Kyoto https://umapot.com/?p=13277
 DRAW-ONLY: unchanged RaceSimEngine and sealed prediction inputs. */
(function(global){'use strict';
const path={"tokyo_turf_2000":[[[519,278],[522,246],[516,194],[485,159]],[[485,159],[469,136],[453,126],[427,127]],[[427,127],[353,126],[253,127],[159,128]],[[159,128],[107,132],[97,174],[105,216]],[[105,216],[105,282],[128,315],[171,315]],[[171,315],[250,315],[318,315],[371,315]]],"kyoto_turf_outer_1400":[[[223,151],[305,132],[382,116],[454,111]],[[454,111],[506,102],[543,130],[550,167]],[[550,167],[556,216],[540,265],[518,290]],[[518,290],[504,311],[481,317],[454,317]],[[454,317],[406,317],[340,317],[290,317]]]};
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function cubic(p,t){
 const q=1-t,v=[q*q*q,3*q*q*t,3*q*t*t,t*t*t];
 const x=p.reduce((sum,a,i)=>sum+a[0]*v[i],0),y=p.reduce((sum,a,i)=>sum+a[1]*v[i],0);
 const dx=3*q*q*(p[1][0]-p[0][0])+6*q*t*(p[2][0]-p[1][0])+3*t*t*(p[3][0]-p[2][0]);
 const dy=3*q*q*(p[1][1]-p[0][1])+6*q*t*(p[2][1]-p[1][1])+3*t*t*(p[3][1]-p[2][1]);
 const m=Math.hypot(dx,dy)||1;return {x,y,tx:dx/m,ty:dy/m};
}
const lookup=new WeakMap();
function sampleAt(p,f){
 if(!lookup.has(p)){
  const a=[{t:0,len:0}];let last=cubic(p,0),len=0;
  for(let i=1;i<=80;i++){const curr=cubic(p,i/80);len+=Math.hypot(curr.x-last.x,curr.y-last.y);a.push({t:i/80,len});last=curr}
  lookup.set(p,a);
 }
 const arr=lookup.get(p),distance=clamp(f,0,1)*arr.at(-1).len;let lo=0,hi=80;
 while(lo<hi){const mid=(lo+hi)>>1;if(arr[mid].len<distance)lo=mid+1;else hi=mid}
 const a=arr[Math.max(0,lo-1)],b=arr[lo];
 return cubic(p,a.t+(b.t-a.t)*(distance-a.len)/(b.len-a.len||1));
}
function rawCenter(course,d){
 const parts=path[course?.id];if(!parts)throw Error('UMAPOT_UNSUPPORTED_COURSE');
 const x=clamp(d,0,course.distance_m);
 const segment=course.segments.find(s=>x<=s.to+1e-8)||course.segments.at(-1);
 const part=parts[course.segments.indexOf(segment)];
 return sampleAt(part,(x-segment.from)/(segment.to-segment.from));
}
// Same continuous path evaluator for the licensed reference-map projection.
const referenceLines=new WeakMap();
function referenceLine(course){
 if(!referenceLines.has(course))referenceLines.set(course,
  global.RaceCourseGeometry.continuousLine(course,d=>rawCenter(course,d)));
 return referenceLines.get(course);
}
// Measured-image guide offsets approximate the inside turf edge
// of Umapot's JPG. Display-only, NOT surveyed/georeferenced positions.
const railGuide=Object.freeze({
 tokyo_turf_2000:[[0,19],[130,17],[300,19],[900,19],[1145,13],[1474.1,18],[2000,18]],
 kyoto_turf_outer_1400:[[0,20],[365,19],[570,18],[805,17],[996.3,15],[1400,15]]
});
function railEdgePx(course,d){
 const knots=railGuide[course.id];if(!knots)throw Error('UMAPOT_RAIL_MISSING');
 const x=clamp(d,0,course.distance_m);let i=0;
 while(i<knots.length-2&&x>knots[i+1][0])i++;
 const a=knots[i],b=knots[i+1],f=clamp((x-a[0])/(b[0]-a[0]||1),0,1);
 return a[1]+(b[1]-a[1])*f;
}
// Outer-course stripe registration on Umapot's Kyoto A-course illustration.
// At the 3rd and 4th bends the green *inner* and *outer* circuits coexist.
// The previous centerline followed the inner stripe; these independently
// sampled outward-normal shifts choose the OUTER turf ribbon. Image pixels,
// not physical track metres; no changes to race simulation physics.
const outerRailCorrection=Object.freeze({
 kyoto_turf_outer_1400:[
  // Source-image white split is only 5–10px wide. Place the NUMBER center
  // outside that split with positive margin through 3→4C (not on its edge).
  // In the bend's last half the two green fields merge; preserve the outer
  // continuation instead of cutting back toward the inside horse track.
  [0,0],[225,1],[365,3],[445,6],[500,10],[540,14],
  [570,18],[600,24],[650,29],[675,31],[700,33],
  [725,35],[750,40],[775,43],[805,45],[830,52],
  [860,46],[890,36],[920,25],[950,16],[970,13],
  [996.3,10],[1100,7],[1250,6],[1400,6]
 ]
});
function outwardShiftPx(course,d){
 const anchors=outerRailCorrection[course.id];if(!anchors)return 0;
 const x=clamp(d,0,course.distance_m);let i=0;
 while(i<anchors.length-2&&x>anchors[i+1][0])i++;
 const a=anchors[i],b=anchors[i+1],z=clamp((x-a[0])/(b[0]-a[0]||1),0,1);
 // Smooth at every anchor to prevent a kink when switching course sections.
 const smooth=z*z*(3-2*z);
 return a[1]+(b[1]-a[1])*smooth;
}
function point(course,d,lane=0){
 if(!path[course?.id])throw Error('UMAPOT_UNSUPPORTED_COURSE');
 const p=referenceLine(course).at(d);
 const towardInsidePx=railEdgePx(course,d)-(1.8+clamp(Number(lane)||0,0,18)*1.65)*1.30;
 const offset=-towardInsidePx*(course.turn==='左'?1:-1)-outwardShiftPx(course,d);
 return {x:p.x-p.ty*offset,y:p.y+p.tx*offset};
}
function validate(course){
 const parts=path[course.id];if(!parts||parts.length!==course.segments.length)throw Error('UMAPOT_UNREGISTERED');
 for(let i=1;i<parts.length;i++)if(Math.hypot(parts[i][0][0]-parts[i-1][3][0],parts[i][0][1]-parts[i-1][3][1])>.01)throw Error('UMAPOT_DISCONTINUITY');
 for(let d=0;d<=course.distance_m;d+=5)for(const lane of [0,4,8]){
  const p=point(course,d,lane);if(!(p.x>28&&p.x<590&&p.y>86&&p.y<351))throw Error('UMAPOT_OUT_OF_BOUNDS');
 }
 return true;
}
function draw(state,race,focus,pathOn,paintNumber){
 if(!state||!race)return;
 const canvas=document.getElementById(race.venue==='東京'?'tokyoCourseOverlay':'kyotoCourseOverlay');
 if(!canvas||canvas.hidden)return;
 const ctx=canvas.getContext('2d');if(!ctx)return;
 const course=global.RaceCourseGeometry.get(race.course_id);
 ctx.clearRect(0,0,620,430);
 const selected=focus==='leader'?state.leadingNo:Number(focus);
 const markers=state.horses.map(h=>({number:h.number,...point(course,h.displayD??h.d,h.lane),
  selected:h.number===selected,leading:h.number===state.leadingNo}))
 .sort((a,b)=>Number(a.selected)-Number(b.selected)||Number(a.leading)-Number(b.leading)||a.number-b.number);
 for(const h of markers)paintNumber(ctx,h.number,h.x,h.y,h.selected?.78:.64,h.selected,h.leading,race.field_size);
}
function setup(){
 const scale=document.getElementById('referenceScale'),figure=document.getElementById('referenceMapFigure');
 function applyScale(){
   if(!scale||!figure)return;
   figure.classList.toggle('native-scale',scale.value==='native');
   for(const scroller of figure.querySelectorAll('.real-course-scroll')){
     scroller.classList.toggle('zoom-150',scale.value==='zoom150');
     scroller.classList.toggle('zoom-200',scale.value==='zoom200');
     scroller.classList.toggle('show-original',scale.value==='uncropped');
     scroller.scrollLeft=0;
   }
 }
 if(scale&&figure){scale.addEventListener('change',applyScale);applyScale()}
 const panel=document.querySelector('.course-panel-wide');
 const expand=document.getElementById('mapExpandBtn');
 function setExpanded(enabled){
   if(!panel||!expand)return;
   panel.classList.toggle('is-expanded',enabled);
   document.body.classList.toggle('map-expanded',enabled);
   expand.setAttribute('aria-expanded',String(enabled));
   expand.textContent=enabled?'⨯ 全画面表示を閉じる':'⛶ 全画面で見る';
 }
 if(expand&&panel){
   expand.addEventListener('click',()=>setExpanded(!panel.classList.contains('is-expanded')));
   global.addEventListener('keydown',e=>{
      if(e.key==='Escape'&&panel.classList.contains('is-expanded'))setExpanded(false)
   });
 }
 for(const prefix of ['tokyo','kyoto']){
  const im=document.getElementById(prefix+'CourseImage'),canvas=document.getElementById(prefix+'CourseOverlay');
  if(im&&canvas){im.addEventListener('error',()=>{canvas.hidden=true});im.addEventListener('load',()=>{canvas.hidden=false})}
 }
}
setup();
global.RaceUmapotOverlay=Object.freeze({point,validate,draw,outwardShiftPx,width:620,height:430});
})(typeof window!=='undefined'?window:globalThis);
