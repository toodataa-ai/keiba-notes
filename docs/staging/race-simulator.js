/* Staging retro racing simulator v0.1. All course lanes/outcomes are illustrative scenarios. */
(() => {
'use strict';
const $=id=>document.getElementById(id);
const ui={
 race:$('raceSelect'),pace:$('paceSelect'),bias:$('biasSelect'),seed:$('seedInput'),
 speed:$('speedSelect'),start:$('startBtn'),pause:$('pauseBtn'),
 restart:$('restartBtn'),newSeed:$('newSeedBtn'),path:$('pathToggle'),
 focus:$('focusSelect'),change:$('changeNotice'),
 canvas:$('raceCanvas'),map:$('courseCanvas'),remaining:$('remaining'),meta:$('raceMeta'),
 caption:$('stageCaption'),elapsed:$('elapsed'),moment:$('moment'),lap:$('lap'),bar:$('meterFill'),
 stands:$('standings'),events:$('raceEvents'),course:$('courseLabel'),source:$('sourceInfo')
};
let catalog=[],race=null,sim=null,running=false,frameId=0,lastFrame=0,renderAt=0,scenarioVersion=0;
const baseColor=['#e13c58','#2b67b8','#e9b939','#299e72','#a064bf','#e57824','#4e7891','#c74997','#7d9840','#57a4b6','#e26262','#827bb8','#339b9a','#ba833c','#b64d63','#678551','#928e83','#385cab'];
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function notify(s){ui.change.hidden=!s;ui.change.textContent=s||''}
function dur(t){let n=Math.floor(t);return String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0')}
function seedValue(){return Math.max(1,Math.min(999999,parseInt(ui.seed.value,10)||1))}
function chooseRace(id){return catalog.find(r=>r.id===id)||null}
function readerUrl(report){
 if(!/^reports\/[\w./-]+\.html$/.test(report)||report.includes('..'))throw Error('予想レポートの参照先が不正です');
 return '../'+report;
}
function parseHorseReport(markup,entry){
 const document=new DOMParser().parseFromString(markup,'text/html');
 const sections=[...document.querySelectorAll('section.horse-page')];
 if(sections.length!==entry.field_size)throw Error('全頭の評価ページが不足しています（'+sections.length+'/'+entry.field_size+'頭）。省略データでは再現できません');
 const horses=sections.map(section=>{
  const title=section.querySelector('h1')?.textContent?.trim()||'';
  const m=title.match(/^(\d+)番[\s\u3000]+(.+?)[\s\u3000]+([◎○▲△×])$/u);
  if(!m)throw Error('馬名・印を正確に読み取れません: '+title);
  const grade=section.querySelector('.horse-score .grade')?.textContent?.trim()||'B';
  const grades=[...section.querySelectorAll('.factor-grid .grade')].map(x=>x.textContent.trim());
  const winMatch=(section.querySelector('.supplement')?.textContent||'').match(/モデル単勝確率[:：]\s*([\d.]+)%/);
  if(!winMatch)throw Error('原本の勝率情報が未確認です（'+m[1]+'番）');
  return {number:Number(m[1]),name:m[2],mark:m[3],grade,pace_grade:grades[1]||'B',win_pct:Number(winMatch[1])};
 });
 RaceSimEngine.validData({...entry,horses});
 const numbers=new Set(horses.map(h=>h.number));
 if(numbers.size!==entry.field_size)throw Error('馬番重複のため読み込み不可');
 return horses;
}
function isValidEntry(entry,registry){
 const original=(registry.races||[]).find(r=>r.id===entry.id&&r.scope==='jra-main');
 if(!original)throw Error('正式レース一覧に対象レースがありません');
 if(original.venue!==entry.venue || original.date!==entry.date ||
    original.field_size!==entry.field_size)throw Error('公式レース条件と保存データが一致しません');
 if(!original.step1_fixed_at || !original.proof_commit)throw Error('発走前原本の固定証跡がありません');
 return original;
}
async function loadRace(id){
 scenarioVersion++;
 const version=scenarioVersion;
 running=false;cancelAnimationFrame(frameId);lastFrame=0;
 ui.start.disabled=true;ui.pause.disabled=true;ui.pause.textContent='一時停止';
 ui.meta.textContent='データ検証中…';ui.remaining.textContent='— m';
 ui.stands.innerHTML='<p class="small-muted">全頭の評価原本を確認しています…</p>';
 ui.events.innerHTML='<li>固定済みの発走前レポートを読み込み中…</li>';
 try{
  const entry=chooseRace(id);if(!entry)throw Error('このレースのシミュレーション設定はまだ作成されていません');
  const [dbRes,reportRes]=await Promise.all([
   fetch('../data/races.json',{cache:'no-store'}),
   fetch(readerUrl(entry.report),{cache:'no-store'})
  ]);
  if(!dbRes.ok||!reportRes.ok)throw Error('原本取得に失敗しました（HTTP '+dbRes.status+'/'+reportRes.status+'）');
  const db=await dbRes.json();
  isValidEntry(entry,db);
  const report=await reportRes.text();
  const horses=parseHorseReport(report,entry);
  if(version!==scenarioVersion)return;
  race={...entry,horses};
  reset(false);
  ui.start.disabled=false;
  ui.meta.textContent=entry.date+' '+entry.venue+entry.number+'R '+entry.surface+entry.distance_m+'m（'+entry.turn+'回り）';
  ui.course.textContent=entry.venue+'／'+entry.surface+entry.distance_m+'m　'+entry.turn+'回り';
  ui.source.textContent='原本：'+entry.report+' ／ 発走前 STEP1 proof '+entry.proof_commit.slice(0,12)+'… ／ 馬場「'+entry.going+'」観測 '+entry.going_observed_at+' ／ この画面は仮説シミュレーションです。';
  ui.focus.innerHTML='<option value="leader">先頭を追跡</option>'+horses.slice().sort((a,b)=>a.number-b.number).map(h=>'<option value="'+h.number+'">'+h.number+' '+esc(h.name)+'（'+h.mark+'）</option>').join('');
  const queryId=new URLSearchParams(location.search).get('focus');
  if(queryId&&horses.some(h=>String(h.number)===queryId))ui.focus.value=queryId;
 }catch(e){
  if(version!==scenarioVersion)return;
  race=null;sim=null;
  ui.stands.innerHTML='<p class="error">'+esc(e.message)+'</p>';
  ui.events.innerHTML='<li>安全のためシミュレーションを開始できません。</li>';
  ui.source.textContent='原本データがない場合、馬の名前や着順を推測して表示しません。';
  ui.moment.textContent='読み込みできませんでした';
  drawIdle(e.message);
 }
}
function reset(startNow){
 if(!race)return;
 cancelAnimationFrame(frameId);
 const seed=seedValue();ui.seed.value=String(seed);
 sim=RaceSimEngine.create(race,{seed,pace:ui.pace.value,bias:ui.bias.value});
 running=false;lastFrame=0;renderAt=0;notify('');
 ui.pause.disabled=true;ui.pause.textContent='一時停止';ui.start.disabled=false;
 ui.start.textContent='▶ レーススタート';
 ui.focus.value='leader';
 render(true);
 if(startNow)start();
}
function start(){
 if(!sim)return;
 if(sim.state.finished)reset(false);
 running=true;lastFrame=0;ui.pause.disabled=false;ui.pause.textContent='一時停止';
 ui.start.disabled=true;ui.start.textContent='走行中';
 cancelAnimationFrame(frameId);frameId=requestAnimationFrame(loop);
}
function pause(){
 if(!sim || sim.state.finished)return;
 running=!running;
 if(running){
  ui.pause.textContent='一時停止';ui.start.disabled=true;lastFrame=0;
  frameId=requestAnimationFrame(loop);
 }else{
  ui.pause.textContent='▶ 再開';ui.start.disabled=false;ui.start.textContent='▶ 再開';
  cancelAnimationFrame(frameId);
 }
}
function loop(t){
 if(!running||!sim)return;
 if(!lastFrame)lastFrame=t;
 let elapsed=Math.min(.10,Math.max(0,(t-lastFrame)/1000))*Number(ui.speed.value||2);
 lastFrame=t;
 // Fixed substeps ensure 1x/2x/4x use the same deterministic dynamics.
 while(elapsed>.00001){
   const dt=Math.min(.05,elapsed);
   sim.step(dt);elapsed-=dt;
 }
 drawRace();
 if(t-renderAt>125){renderData();renderAt=t}
 if(sim.state.finished){
   running=false;
   ui.pause.disabled=true;ui.start.disabled=false;ui.start.textContent='▶ 最初から再生';
   renderData();return;
 }
 frameId=requestAnimationFrame(loop);
}
function render(full=false){
 drawRace();renderData();
}
function renderData(){
 if(!sim)return;
 const state=sim.state;
 ui.remaining.textContent=Math.max(0,Math.round(state.distance-state.leader))+' m';
 ui.caption.textContent=state.finished?'ゴール':'仮想レース・'+(state.progress>.73?'最後の直線':state.progress>.32?'向正面・コーナー':'スタート・先行争い');
 ui.elapsed.textContent=dur(state.t);
 ui.moment.textContent=state.finished?'仮想着順が確定しました（予想や結果ではありません）':state.leader>.05?'先頭 '+state.leadingNo+'番　'+(state.horses.find(h=>h.number===state.leadingNo)?.name||''):'スタートを押すとレースが始まります';
 ui.lap.textContent=Math.round(state.progress*100)+'%';
 ui.bar.style.width=(state.progress*100).toFixed(1)+'%';
 ui.stands.innerHTML=sim.standings().map((h,i)=>{
  const lead=state.leader-h.d;
  const gap=state.finished?Number(h.finishTime||0).toFixed(1)+'秒':i===0?'先頭':lead<.5?'並走':Math.round(lead)+'m';
  const focus=ui.focus.value===String(h.number);
  return '<div class="standing-row'+(focus?' focused':'')+'"><span class="rank-no">'+(i+1)+'</span><span class="saddle">'+h.number+'</span><span class="standing-name" title="'+esc(h.name)+'">'+esc(h.name)+'</span><span class="standing-mark">'+h.mark+'</span><span class="standing-gap">'+gap+'</span></div>';
 }).join('');
 ui.events.innerHTML=state.events.slice(0,7).map(e=>'<li><strong>'+dur(e.t)+'</strong>　'+esc(e.message)+'</li>').join('');
}
function drawIdle(message){
 const ctx=ui.canvas.getContext('2d');if(!ctx)return;
 ctx.clearRect(0,0,1000,470);ctx.fillStyle='#202a36';ctx.fillRect(0,0,1000,470);
 ctx.fillStyle='#fff';ctx.font='18px Meiryo';ctx.fillText(message||'準備中',50,210);
}
function rect(ctx,x,y,w,h,color){ctx.fillStyle=color;ctx.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h))}
function horseSprite(ctx,x,y,h,time,selected){
 const color=baseColor[(h.number-1)%baseColor.length];
 ctx.save();ctx.translate(Math.round(x),Math.round(y));
 if(selected){ctx.strokeStyle='#ffe18c';ctx.lineWidth=2;ctx.strokeRect(-32,-28,65,49)}
 ctx.fillStyle='rgba(0,0,0,.26)';ctx.beginPath();ctx.ellipse(0,14,27,4,0,0,Math.PI*2);ctx.fill();
 const gait=Math.sin(time*17+h.phase);
 rect(ctx,-22,-2,38,13,'#6e4939');
 rect(ctx,-18,-7,30,13, '#866246');
 rect(ctx,11,-10,12,8,'#866246');rect(ctx,19,-19,9,14,'#866246');
 rect(ctx,24,-17,7,6,'#9d7956');rect(ctx,22,-23,3,7,'#594030');
 rect(ctx,-28,-7,12,5,'#473024');
 rect(ctx,-13,4,15,7,'#f4f0e6');
 rect(ctx,-10,3,10,9,'#1b2534');
 rect(ctx,-8,5,6,7,'#f8f8f4');
 // Repeating pixel gallop cycle, two leg pairs.
 rect(ctx,-16,5,5,10,'#624634');rect(ctx,-15+gait*6,15,4,7,'#4e3629');
 rect(ctx,8,5,5,10,'#644431');rect(ctx,8-gait*6,15,4,7,'#493122');
 rect(ctx,-8,-16,18,10,color);rect(ctx,-4,-20,11,5,color);
 rect(ctx,1,-24,9,7, '#e4c4a4');rect(ctx,0,-31,12,7,color);
 rect(ctx,7,-16,4,12,'#2e3341');rect(ctx,10,-7,7,5,'#2e3341');
 ctx.fillStyle='#fff';ctx.font='bold 12px monospace';ctx.textAlign='center';
 ctx.fillText(String(h.number),-3,10);
 if(h.mark==='◎'||selected){
   ctx.font='bold 12px Meiryo';ctx.fillStyle='#fff8d6';ctx.strokeStyle='#222';ctx.lineWidth=3;
   const label=h.mark+' '+h.name;
   ctx.strokeText(label,0,-35);ctx.fillText(label,0,-35);
 }
 ctx.restore();
}
function drawRace(){
 if(!sim||!race){drawIdle('出走馬の原本を確認中…');return}
 const ctx=ui.canvas.getContext('2d');if(!ctx)return;
 const w=1000,h=470,s=sim.state,hs=s.horses;
 ctx.clearRect(0,0,w,h);
 rect(ctx,0,0,w,112,'#81b9d2');
 for(let i=0;i<8;i++){
  rect(ctx,0,i*12,w,2,i%2?'#8bc8e0':'#78acc7');
 }
 // Distant low-res silhouette grandstand.
 for(let i=0;i<25;i++){
  const x=i*44-20;
  rect(ctx,x,65+(i%3)*4,40,46,'#526b73');
  rect(ctx,x+5,72+(i%3)*4,29,3,'#9daeb3');
  for(let k=0;k<4;k++)rect(ctx,x+5+k*7,83,4,3,k%2?'#d4cfb0':'#c37868');
 }
 rect(ctx,0,111,w,8,'#d8ece5');rect(ctx,0,119,w,15,'#829c69');
 rect(ctx,0,134,w,306,'#4e8d48');
 const laneTop=150,laneGap=35;
 for(let i=0;i<8;i++){
   rect(ctx,0,laneTop+i*laneGap,w,laneGap,i%2===0?'#56974d':'#5a9c52');
   for(let k=0;k<40;k++) {
     const scroll=Math.floor(s.leader*3)%42;
     rect(ctx,k*42-scroll+(i%2)*14,laneTop+i*laneGap+27,13,1,'#7db46e');
   }
 }
 for(let i=0;i<9;i++)rect(ctx,0,laneTop+i*laneGap,w,2,'rgba(255,255,255,.15)');
 // Shadowed track rail.
 rect(ctx,0,144,w,4,'#ecf2df');rect(ctx,0,148,w,3,'#7b8885');
 rect(ctx,0,434,w,5,'#eef0e8');rect(ctx,0,440,w,30,'#385e32');
 const lead=Math.max(0,s.leader);
 const anchor=Math.max(0,lead-98);
 const xAt=d=>140+(d-anchor)*5.15;
 const finishX=xAt(race.distance_m);
 if(finishX>=-12&&finishX<w+45){
   rect(ctx,finishX-5,137,12,305,'#f4f4eb');
   for(let i=0;i<36;i++)for(let j=0;j<2;j++)rect(ctx,finishX-5+j*6,142+i*8,6,8,(i+j)%2===0?'#1c2534':'#f2f2ee');
 }
 for(const d of [400,200,100,0]){
   const x=xAt(race.distance_m-d);
   if(x>0&&x<w){rect(ctx,x,128,3,14,'#fcfafa');ctx.fillStyle='#202932';ctx.font='bold 12px monospace';ctx.fillText(d===0?'GOAL':d+'m',x+7,136)}
 }
 const focused=ui.focus.value==='leader'?null:hs.find(x=>String(x.number)===ui.focus.value);
 const sorted=hs.slice().sort((a,b)=>a.lane-b.lane||a.d-b.d);
 if(ui.path.checked){
  for(const horse of hs){
    if(focused&&horse!==focused && horse.number!==s.leadingNo)continue;
    if(!focused&&horse.number!==s.leadingNo&&horse.mark!=='◎'&&horse.mark!=='○')continue;
    ctx.beginPath();ctx.strokeStyle=horse===focused?'rgba(255,226,120,.9)':'rgba(243,250,249,.60)';
    ctx.lineWidth=2;
    horse.trail.forEach((pos,i)=>{const x=xAt(pos.d),y=laneTop+17+pos.lane*laneGap;
      if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)});
    ctx.stroke();
  }
 }
 for(const horse of sorted){
    const x=xAt(horse.d);
    if(x<-80||x>w+80)continue;
    const y=laneTop+12+horse.lane*laneGap;
    horseSprite(ctx,x,y,horse,s.t,horse===focused);
 }
 // Stylized broadcast overlays.
 rect(ctx,13,33,216,32,'rgba(15,23,34,.78)');
 ctx.font='bold 16px Meiryo';ctx.textAlign='left';ctx.fillStyle='#fff';ctx.fillText(race.venue+' '+race.surface+race.distance_m+'m',24,55);
 rect(ctx,790,33,192,32,'rgba(15,23,34,.78)');
 ctx.font='bold 13px Meiryo';ctx.fillStyle='#ffe6a8';ctx.fillText(s.finished?'PHOTO FINISH':'仮想レース実況',811,55);
 ctx.textAlign='start';
 drawCourse();
}
function drawCourse(){
 if(!sim||!race)return;
 const ctx=ui.map.getContext('2d');if(!ctx)return;
 ctx.clearRect(0,0,580,186);
 rect(ctx,0,0,580,186,'#315c39');
 // Track geometry is generic schematic only (not the official racing course).
 ctx.beginPath();ctx.ellipse(290,93,243,70,0,0,Math.PI*2);
 ctx.strokeStyle='#9d825e';ctx.lineWidth=44;ctx.stroke();
 ctx.beginPath();ctx.ellipse(290,93,243,70,0,0,Math.PI*2);
 ctx.strokeStyle='#c2ad81';ctx.lineWidth=34;ctx.stroke();
 ctx.beginPath();ctx.ellipse(290,93,243,70,0,0,Math.PI*2);
 ctx.strokeStyle='#7eaf79';ctx.lineWidth=13;ctx.stroke();
 ctx.strokeStyle='#f5eac1';ctx.lineWidth=2;ctx.stroke();
 const direction=race.turn==='右'?-1:1;
 function mapP(d,lane){
   const a=direction*2*Math.PI*(d/race.distance_m) - Math.PI/2;
   const r=lane*1.6-5;
   return [290+(231+r)*Math.cos(a),93+(63+r*.28)*Math.sin(a)];
 }
 for(const horse of sim.state.horses){
   if(ui.path.checked && (horse.mark==='◎'||ui.focus.value===String(horse.number))){
    ctx.beginPath();
    horse.trail.forEach((pt,i)=>{const pos=mapP(pt.d,pt.lane);if(i===0)ctx.moveTo(...pos);else ctx.lineTo(...pos)});
    ctx.strokeStyle='rgba(255,250,190,.8)';ctx.lineWidth=2;ctx.stroke();
   }
 }
 const group=sim.state.horses.slice().sort((a,b)=>a.d-b.d);
 for(const horse of group){
    const [x,y]=mapP(horse.d,horse.lane);
    ctx.fillStyle=baseColor[(horse.number-1)%baseColor.length];
    ctx.beginPath();ctx.arc(x,y,horse.number===sim.state.leadingNo?6.8:5.4,0,Math.PI*2);ctx.fill();
    ctx.strokeStyle=horse.number===sim.state.leadingNo?'#ffefab':'#152824';ctx.lineWidth=2;ctx.stroke();
    if(horse.number===sim.state.leadingNo || ui.focus.value===String(horse.number)){
      ctx.fillStyle='#fff';ctx.font='bold 10px monospace';ctx.fillText(horse.number,x+8,y-8);
    }
 }
 ctx.fillStyle='rgba(14,37,24,.81)';ctx.fillRect(202,61,180,67);
 ctx.textAlign='center';ctx.fillStyle='#efffea';ctx.font='bold 18px Meiryo';ctx.fillText(race.venue+' '+race.distance_m+'m',292,86);
 ctx.font='11px Meiryo';ctx.fillStyle='#cbe6cd';ctx.fillText(race.turn+'回り（概略）',292,107);
 ctx.textAlign='left';
}
function markDirty(){if(running){notify('条件変更は次の再スタートから反映されます。')}else{notify('変更した条件はスタート時に使用します。')}}
async function initialize(){
 try{
  const res=await fetch('race-sim-manifest-v1.json',{cache:'no-store'});
  if(!res.ok)throw Error('シミュレータのレース登録を取得できません（HTTP '+res.status+'）');
  const registry=await res.json();
  if(registry.schema_version!==1||registry.status!=='STAGING_RESEARCH_ONLY')throw Error('未承認データ形式です');
  catalog=registry.races||[];
  if(!catalog.length)throw Error('シミュレーション可能なレースがありません');
  ui.race.innerHTML=catalog.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.date+' '+x.venue+x.number+'R '+x.race)+'</option>').join('');
  const wanted=new URLSearchParams(location.search).get('race');
  if(wanted&&chooseRace(wanted))ui.race.value=wanted;
  await loadRace(ui.race.value);
 }catch(e){ui.stands.innerHTML='<p class="error">'+esc(e.message)+'</p>';ui.moment.textContent='原本データを確認できません'}
}
ui.race.addEventListener('change',()=>loadRace(ui.race.value));
for(const input of [ui.pace,ui.bias,ui.seed])input.addEventListener('change',markDirty);
ui.start.addEventListener('click',()=>{
 if(!sim)return;
 if(sim.state.finished || sim.state.t===0 && !running){reset(false);start()}
 else if(!running){running=true;ui.pause.textContent='一時停止';ui.start.disabled=true;lastFrame=0;frameId=requestAnimationFrame(loop)}
});
ui.pause.addEventListener('click',pause);
ui.restart.addEventListener('click',()=>reset(true));
ui.newSeed.addEventListener('click',()=>{
 ui.seed.value=String((seedValue()*48271+67)%999999+1);
 reset(true);
});
ui.focus.addEventListener('change',render);
ui.path.addEventListener('change',render);
ui.speed.addEventListener('change',render);
window.addEventListener('pagehide',()=>{running=false;cancelAnimationFrame(frameId)});
initialize();
})();
