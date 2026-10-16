/* Stage route design review: approved-route distance PROBE only.
 * Never invent runners or read/alter STEP1, bets, payouts, or JRA results. */
(()=>{'use strict';
const NS='http://www.w3.org/2000/svg',get=id=>document.getElementById(id);
const make=(tag,txt)=>{const n=document.createElement(tag);n.textContent=String(txt);return n};
const svg=(tag,attributes={})=>{
 const n=document.createElementNS(NS,tag);
 for(const [key,value] of Object.entries(attributes))n.setAttribute(key,String(value));
 return n;
};
const profilePath=segs=>segs.map((c,i)=>(i?'':'M '+c[0].join(' '))+
 ' C '+c[1].join(' ')+' '+c[2].join(' ')+' '+c[3].join(' ')).join(' ');
const approxMeter=(b,i)=>Math.round((b.segment_bounds[i+1]-b.segment_bounds[i])*10)/10;
let currentProfile=null,probe=null,playing=false,frame=0,lastTime=0;
const approvedGeometry=b=>b.approval?.status==='user_approved_illustration'&&
 b.approval.real_horse_replay_requires_pre_race_frozen_report===true&&
 typeof RaceCourseGeometry!=='undefined'&&
 RaceCourseGeometry.get(b.course_id)?.user_approved_stage_geometry===true&&
 RaceCourseGeometry.get(b.course_id)?.distance_m===b.distance_m;
function sharedSplineSvg(profile){
 const commands=[];
 for(let d=0;d<=profile.distance_m;d+=4){
  const p=RaceCourseGeometry.center(profile,d);
  commands.push((d===0?'M ':'L ')+p.x.toFixed(2)+' '+p.y.toFixed(2));
 }
 const p=RaceCourseGeometry.center(profile,profile.distance_m);
 commands.push('L '+p.x.toFixed(2)+' '+p.y.toFixed(2));
 return commands.join(' ');
}
function setProbeDistance(d){
 if(!currentProfile||!probe)return;
 const distance=Math.max(0,Math.min(currentProfile.distance_m,Number(d)||0));
 const p=RaceCourseGeometry.center(currentProfile,distance);
 probe.setAttribute('cx',p.x.toFixed(3));probe.setAttribute('cy',p.y.toFixed(3));
 get('rehearsalScrub').value=String(Math.round(distance));
 get('rehearsalDistance').textContent=Math.round(distance)+' / '+currentProfile.distance_m+' m';
}
function stopProbe(){
 playing=false;cancelAnimationFrame(frame);frame=0;lastTime=0;
}
function tick(time){
 if(!playing||!currentProfile)return;
 if(!lastTime)lastTime=time;
 const dt=Math.max(0,Math.min(.1,(time-lastTime)/1000));
 lastTime=time;
 const curr=Number(get('rehearsalScrub').value||0),next=Math.min(currentProfile.distance_m,curr+dt*115);
 setProbeDistance(next);
 if(next>=currentProfile.distance_m){stopProbe();return}
 frame=requestAnimationFrame(tick);
}
get('rehearsalPlay').addEventListener('click',()=>{
 if(!currentProfile)return;
 if(Number(get('rehearsalScrub').value)>=currentProfile.distance_m)setProbeDistance(0);
 stopProbe();playing=true;frame=requestAnimationFrame(tick);
});
get('rehearsalPause').addEventListener('click',stopProbe);
get('rehearsalScrub').addEventListener('input',()=>{
 stopProbe();setProbeDistance(get('rehearsalScrub').value);
});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopProbe()});
window.addEventListener('pagehide',stopProbe);
function render(blueprint){
 stopProbe();currentProfile=null;probe=null;
 get('courseRehearsal').hidden=true;
 const title=get('courseTitle'),box=get('diagram');box.replaceChildren();
 title.textContent=blueprint.date+' '+blueprint.venue+'11R '+blueprint.race+' · '+
   (blueprint.surface==='dirt'?'ダート':'芝')+blueprint.distance_m+'m'+
   ({inner:'内回り',outer:'外回り',single:'通常周回'}[blueprint.layout]||'');
 const view=svg('svg',{viewBox:'20 15 560 340',role:'img','aria-label':'独立した'+
   blueprint.course_id+'走行線設計案。緑は発走、赤はゴール。測量原図ではありません。'});
 const h=svg('defs'),marker=svg('marker',{id:'dirArrow',markerWidth:'8',markerHeight:'8',refX:'5',refY:'3',orient:'auto'});
 marker.appendChild(svg('path',{d:'M 0 0 L 6 3 L 0 6 Z',fill:'#144a70'}));h.appendChild(marker);view.appendChild(h);
 for(let i=0;i<4;i++){view.appendChild(svg('path',{d:'M 24 '+(40+i*87)+' H 570',
   stroke:'#e0e9f2','stroke-dasharray':'3 6','stroke-width':'1'}));}
 // The route used by real engine physics is also the EXACT preview line.
 // Other unapproved routes stay as static Bézier designs.
 const approved=approvedGeometry(blueprint);
 const d=approved?sharedSplineSvg(RaceCourseGeometry.get(blueprint.course_id)):
   profilePath(blueprint.segments);
 const dirt=blueprint.surface==='dirt';
 view.appendChild(svg('path',{d,class:'outer',stroke:dirt?'#bd926a':'#7caf98'}));
 view.appendChild(svg('path',{d,class:'surface',stroke:dirt?'#d6b08a':'#65b887'}));
 view.appendChild(svg('path',{d,class:'center'}));
 for(const i of [0,Math.max(0,Math.floor(blueprint.segments.length/3)),
  Math.max(0,blueprint.segments.length-2)]){
  const s=blueprint.segments[i],start=s[0],near=s[3];
  const arrow=svg('path',{d:'M '+start.join(' ')+' L '+near.join(' '),
   stroke:'transparent','stroke-width':'1'});view.appendChild(arrow);
  const x=.5*start[0]+.5*near[0],y=.5*start[1]+.5*near[1];
  // A short static direction arrow helps distinguish start point and turn.
  const vx=near[0]-start[0],vy=near[1]-start[1],m=Math.hypot(vx,vy)||1;
  view.appendChild(svg('path',{d:'M '+(x-14*vx/m).toFixed(1)+' '+(y-14*vy/m).toFixed(1)+
   ' L '+(x+14*vx/m).toFixed(1)+' '+(y+14*vy/m).toFixed(1),
   stroke:'#144a70','stroke-width':'2.4','marker-end':'url(#dirArrow)'}));
 }
 function flag(pt,color,label,dy){
  view.appendChild(svg('circle',{cx:pt[0],cy:pt[1],r:7,fill:color,stroke:'white','stroke-width':'2'}));
  const t=svg('text',{x:pt[0]+10,y:pt[1]+dy,'class':'point-tag',fill:'#1e354d'});
  t.textContent=label;view.appendChild(t);
 }
 flag(blueprint.segments[0][0],'#358965','START',-10);
 flag(blueprint.segments.at(-1)[3],'#ca5555','GOAL',-9);
 // Show the actual corner-entry locations from each independently authored
 // route, so a malformed first-corner/gate/goal position is easy to spot.
 for(let i=1;i<blueprint.segments.length-1;i++){
  const match=blueprint.segment_names[i].match(/^([1-4])コーナー/);
  if(!match)continue;
  const p=blueprint.segments[i][0],text=svg('text',{
   x:p[0]+8,y:p[1]-10,'class':'point-tag',fill:'#493d8a'});
  text.textContent=match[1]+'C';
  view.appendChild(svg('circle',{cx:p[0],cy:p[1],r:4.2,fill:'#7764a9',stroke:'#fff','stroke-width':1.2}));
  view.appendChild(text);
 }
 if(approved){
  currentProfile=RaceCourseGeometry.get(blueprint.course_id);
  probe=svg('circle',{cx:0,cy:0,r:8,fill:'#1267a7',stroke:'#fff','stroke-width':2.8,
   'aria-label':'コース上の距離を示す青い点。馬ではありません'});
  view.appendChild(probe);
  const test=get('courseRehearsal');test.hidden=false;
  get('rehearsalScrub').max=String(blueprint.distance_m);
  setProbeDistance(0);
 }
 box.appendChild(view);
 const grid=get('courseMetrics');grid.replaceChildren();
 for(const [label,value] of [
  ['正式距離',blueprint.distance_m+'m'],
  ['1周（A代表）',blueprint.lap_m+'m'],
  ['最後の直線',blueprint.straight_m+'m'],
  ['周回・走路', (blueprint.turn==='right'?'右回り':'左回り')+' / '+(blueprint.surface==='dirt'?'ダート':blueprint.layout==='inner'?'芝内':'芝')]
 ]){
  const item=make('div',label);item.className='metric';item.appendChild(make('strong',value));grid.appendChild(item);
 }
 get('courseNotes').textContent=blueprint.notes;
 get('courseStatus').textContent='コース専用型 '+blueprint.course_id+
  (approved?' ／ 形状承認済み・距離マーカーで試走可 ／ 出走馬の発走前原本待ち':
   ' ／ コース形状未承認・試走不可 ／ 出走馬の再生も不可');
 get('officialCourse').href=blueprint.official_course;
 get('officialEntries').href=blueprint.official_entries;
 const officialDetail=get('officialRaceReference');
 if(officialDetail){
  officialDetail.hidden=!blueprint.reference?.official_race;
  if(blueprint.reference?.official_race)officialDetail.href=blueprint.reference.official_race;
 }
 const tbody=get('sectorTable');tbody.replaceChildren();
 for(let i=0;i<blueprint.segments.length;i++){
  const tr=make('tr',''),th=make('th','区間'+(i+1));th.scope='row';
  const td=make('td',blueprint.segment_names[i]+'　'+
   blueprint.segment_bounds[i].toFixed(1)+'–'+blueprint.segment_bounds[i+1].toFixed(1)+
   'm（'+approxMeter(blueprint,i)+'m）');
  tr.append(th,td);tbody.appendChild(tr);
 }
}
function validateFile(data){
 if(data.status!=='PROVISIONAL_BLUEPRINT_NO_ANIMATION'||
   data.safe_for_live_simulator!==false||
   !data.restrictions?.no_unverified_live_animation||
   !Array.isArray(data.courses)||data.courses.length!==6)throw Error('コース承認ゲートが無効');
 for(const b of data.courses){
  if(b.segments.length!==b.segment_names.length||
   b.segments.length!==b.segment_bounds.length-1||
   Math.abs(b.segment_bounds.at(-1)-b.distance_m)>.001||
   Math.abs(b.segment_bounds.at(-2)-(b.distance_m-b.straight_m))>.001)
   throw Error('コースの距離・直線長が不整合 '+b.course_id);
 }
 return data.courses.slice().sort((a,b)=>a.priority-b.priority);
}
fetch('weekend-main-course-blueprints-20261017.json',{cache:'no-store'})
 .then(r=>{if(!r.ok)throw Error('設計案を取得できませんでした');return r.json()})
 .then(data=>{
  const all=validateFile(data),list=get('courseList');
  const buttons=all.map((b,i)=>{
   const label=make('button',b.date.slice(5).replace('-','/')+' '+b.venue+'11R');
   label.className='course-item';label.type='button';label.setAttribute('aria-pressed',String(i===0));
   label.appendChild(make('strong',b.race));label.appendChild(make('span',
     (b.surface==='dirt'?'ダート':'芝')+b.distance_m+'m / '+
     ({inner:'内回り',outer:'外回り',single:'通常周回'}[b.layout]||'')));
   label.addEventListener('click',()=>{buttons.forEach(x=>x.setAttribute('aria-pressed','false'));
     label.setAttribute('aria-pressed','true');render(b)});
   list.appendChild(label);return label;
  });
  const requested=new URLSearchParams(location.search).get('course');
  const initial=all.findIndex(x=>x.course_id===requested);
  if(initial>=0){buttons[initial].click()}else render(all[0]);
 })
 .catch(err=>{get('courseStatus').textContent='読み込みエラー：'+err.message});
})();
