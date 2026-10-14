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
function smoothedCenter(course,d){
 const x=clamp(d,0,course.distance_m),p=rawCenter(course,x);
 let gap=Infinity;
 for(const s of course.segments.slice(1))gap=Math.min(gap,Math.abs(x-s.from));
 if(gap>=18)return {x:p.x,y:p.y};
 let ax=0,ay=0;
 for(const [step,k] of [[-12,1],[-6,4],[0,6],[6,4],[12,1]]){
  const q=rawCenter(course,clamp(x+step,0,course.distance_m));ax+=q.x*k;ay+=q.y*k;
 }
 const t=clamp(gap/18,0,1),fade=1-t*t*(3-2*t);
 return {x:p.x*(1-fade)+ax*fade/16,y:p.y*(1-fade)+ay*fade/16};
}
function point(course,d,lane=0){
 const parts=path[course?.id];if(!parts)throw Error('UMAPOT_UNSUPPORTED_COURSE');
 if(d>course.distance_m){
  const finish=point(course,course.distance_m,lane),tail=parts.at(-1);
  const tangent=sampleAt(tail,1);
  const scale=lookup.get(tail).at(-1).len/(course.segments.at(-1).to-course.segments.at(-1).from);
  const offset=Math.min(40,d-course.distance_m)*scale;
  return {x:finish.x+tangent.tx*offset,y:finish.y+tangent.ty*offset};
 }
 const distance=clamp(Number(d)||0,0,course.distance_m);
 const p=smoothedCenter(course,distance);
 const back=smoothedCenter(course,clamp(distance-1.5,0,course.distance_m));
 const next=smoothedCenter(course,clamp(distance+1.5,0,course.distance_m));
 const magnitude=Math.hypot(next.x-back.x,next.y-back.y)||1;
 const tx=(next.x-back.x)/magnitude,ty=(next.y-back.y)/magnitude;
 // Do not stack outer runners at lane 9: share physics' complete rail range.
 const maxLane=clamp(Math.floor((Math.min(...course.track_width_m)-3.6)/1.65),7,18);
 const outside=(clamp(Number(lane)||0,0,maxLane)-maxLane/2)*1.30*(course.turn==='左'?1:-1);
 return {x:p.x-ty*outside,y:p.y+tx*outside};
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
 if(pathOn)for(const horse of state.horses){
  if(horse.number!==selected&&horse.mark!=='◎')continue;
  ctx.beginPath();let first=true;
  for(const t of horse.trail){const p=point(course,t.d,t.lane);if(first){ctx.moveTo(p.x,p.y);first=false}else ctx.lineTo(p.x,p.y)}
  if(!first){ctx.strokeStyle=horse.number===selected?'rgba(25,50,68,.90)':'rgba(48,65,58,.7)';ctx.lineWidth=horse.number===selected?2.8:1.8;ctx.stroke()}
 }
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
global.RaceUmapotOverlay=Object.freeze({point,validate,draw,width:620,height:430});
})(typeof window!=='undefined'?window:globalThis);
