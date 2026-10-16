/* Staging race simulator v0.20. JRA bracket colors and licensed actual course reference. */
(() => {
'use strict';
const $=id=>document.getElementById(id);
const ui={
 race:$('raceSelect'),bias:$('biasSelect'),seed:$('seedInput'),
 speed:$('speedSelect'),start:$('startBtn'),pause:$('pauseBtn'),
 restart:$('restartBtn'),newSeed:$('newSeedBtn'),
 focus:$('focusSelect'),change:$('changeNotice'),
 canvas:$('raceCanvas'),map:null,remaining:$('remaining'),meta:$('raceMeta'),
 caption:$('stageCaption'),elapsed:$('elapsed'),moment:$('moment'),lap:$('lap'),bar:$('meterFill'),paceDynamics:$('paceDynamics'),
 stands:$('standings'),events:$('raceEvents'),course:$('courseLabel'),source:$('sourceInfo'),abilityInfo:$('abilityInfo'),sixTraits:$('runnerSixTraits')
};
let catalog=[],race=null,sim=null,running=false,frameId=0,lastFrame=0,renderAt=0,scenarioVersion=0;
let cameraMotion=null;
// A race-view preset changes how much of the track is visible. The horse sprite
// also gets its OWN pixel target: previously /zoom cancelled magnification,
// leaving horses roughly 40px across even with a closer track camera.
const CAMERA_ZOOM=Object.freeze({follow:13.8,followWide:6.2,overview:1.72});
function viewCamera(mode,screenWidth,canvasWidth){
 const chosen=Object.prototype.hasOwnProperty.call(CAMERA_ZOOM,mode)?mode:'follow';
 const width=Math.max(1,Number(screenWidth)||Number(canvasWidth)||1000);
 const backing=Math.max(1,Number(canvasWidth)||1000);
 const narrow=width<640;
 const horsePx=chosen==='overview'?(narrow?22:35):
               chosen==='followWide'?(narrow?38:62):(narrow?51:88);
 const zoom=CAMERA_ZOOM[chosen]*(narrow&&chosen==='follow'?2.5:1);
 // The source sprite measures ~45 local x pixels nose to tail.
 const spriteScale=horsePx*backing/(width*45*zoom);
 return Object.freeze({mode:chosen,zoom,spriteScale,horsePx});
}
// Pure sizing function is exposed for automated mobile/desktop pixel validation.
// The complete camera API is exposed after the frame solver is initialized.
function resizeRaceCanvas(){
 const tall=window.innerWidth<=640;
 const next=tall?730:470;
 if(ui.canvas.height!==next)ui.canvas.height=next;
}
const baseColor=['#e13c58','#2b67b8','#e9b939','#299e72','#a064bf','#e57824','#4e7891','#c74997','#7d9840','#57a4b6','#e26262','#827bb8','#339b9a','#ba833c','#b64d63','#678551','#928e83','#385cab'];
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function notify(s){ui.change.hidden=!s;ui.change.textContent=s||''}
function dur(t){
 const tenths=Math.floor(Math.max(0,Number(t)||0)*10+1e-7);
 const min=Math.floor(tenths/600),sec=Math.floor((tenths%600)/10),frac=tenths%10;
 return min?min+'.'+String(sec).padStart(2,'0')+'.'+frac:sec+'.'+frac;
}
function firstThree(state){
 return state.horses.filter(h=>h.finished&&Number.isFinite(h.finishTime))
  .sort((a,b)=>a.finishTime-b.finishTime||a.number-b.number).slice(0,3);
}
// Real race-engine crossing telemetry only; never manufacture a position swap.
function recentOvertake(state,windowSeconds=1.9){
 const pass=state?.lastVisualPass;
 return state?.firstFinishTime===null&&pass&&
  state.t>=pass.t&&state.t-pass.t<windowSeconds?pass:null;
}
window.RaceSimTiming=Object.freeze({format:dur,firstThree,recentOvertake});
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
  if(grades.length!==9)throw Error('STEP1の評価9項目が不足: '+m[1]+'番');
  const recentRuns=[...section.querySelectorAll('.run-table tbody tr')].slice(0,4).map(tr=>{
    const td=[...tr.querySelectorAll('td')].map(x=>x.textContent.trim());
    const distance=td[2]?.match(/^芝([0-9]{3,4})m$/),finish=td[3]?.match(/^([0-9]{1,2})着$/);
    return {date:td[0],venue:td[1],distance_m:distance?Number(distance[1]):null,
      finish:finish?Number(finish[1]):null};
  }).filter(x=>x.date<entry.date);
  const winMatch=(section.querySelector('.supplement')?.textContent||'').match(/モデル単勝確率[:：]\s*([\d.]+)%/);
  if(!winMatch)throw Error('原本の勝率情報が未確認です（'+m[1]+'番）');
  const styleMeta=RaceRunnerStyle.inferFromLastRace(section.querySelector('.assessment')?.textContent||'');
  return {number:Number(m[1]),name:m[2],mark:m[3],grade,
    pace_grade:grades[1]||'B',factorGrades:grades,recentRuns,
    win_pct:Number(winMatch[1]),style:styleMeta.style,styleMeta};
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
  const profile=RaceCourseGeometry.get(entry.course_id);
  if(!profile||profile.distance_m!==entry.distance_m||profile.venue!==entry.venue||profile.turn!==entry.turn)
    throw Error('公式コース条件とレース定義が一致しません');
  const report=await reportRes.text();
  const horses=parseHorseReport(report,entry);
  if(version!==scenarioVersion)return;
  race={...entry,horses};
  reset(false);
  updateCourseReference();
  ui.start.disabled=false;
  ui.meta.textContent=entry.date+' '+entry.venue+entry.number+'R '+entry.surface+entry.distance_m+'m（'+entry.turn+'回り）';
  ui.course.textContent=profile.layout+' / 直線'+profile.straight_m+'m / 高低差'+profile.elevation_range_m+'m';
  const details=$('courseFeatures');
  if(details)details.textContent=profile.info;
  const mapsource=$('mapSourceLink');
  if(mapsource){mapsource.href=profile.official;mapsource.textContent=profile.venue+'・JRA公式コース図と数値';}
  const feat=$('courseMeasurements');
  if(feat)feat.textContent='芝Aコース 1周'+profile.lap_m+'m　直線'+profile.straight_m+
    'm　総高低差'+profile.elevation_range_m+'m。コース曲線・高さの途中地点は近似。';
  ui.source.textContent='原本：'+entry.report+' ／ 発走前 STEP1 proof '+entry.proof_commit.slice(0,12)+'… ／ 馬場「'+entry.going+'」観測 '+entry.going_observed_at+' ／ この画面は仮説シミュレーションです。';
  ui.focus.innerHTML='<option value="leader">先頭を追跡</option>'+horses.slice().sort((a,b)=>a.number-b.number).map(h=>'<option value="'+h.number+'">'+h.number+' '+esc(h.name)+'（'+h.mark+'・'+({nige:'逃',senko:'先',sashi:'差',oikomi:'追',unknown:'不明'}[h.style]||'不明')+'）</option>').join('');
  const styles=$('runnerStyleInfo');
  if(styles){
    const names={nige:'逃げ',senko:'先行',sashi:'差し',oikomi:'追込',unknown:'不明'};
    styles.textContent='脚質の暫定推定：'+Object.entries(names).map(([key,name])=>name+' '+horses.filter(h=>h.style===key).length+'頭').join('／')+
      '。発走前レポートの前走通過順から推定（1走分のため確定ではありません）。';
  }
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

/* Licensed reference map and hypothetical simulation must remain distinct:
   no number overlays on real imagery until independently georeferenced. */
function updateCourseReference(){
 const figure=$('referenceMapFigure'),tokyo=$('tokyoRealCourseMap'),kyoto=$('kyotoRealCourseMap');
 const region=race?.course_id==='tokyo_turf_2000'?'tokyo':race?.course_id==='kyoto_turf_outer_1400'?'kyoto':null;
 if(figure)figure.hidden=!region;
 if(tokyo)tokyo.hidden=region!=='tokyo';
 if(kyoto)kyoto.hidden=region!=='kyoto';
}
function setupReferenceMapErrorHandling(){
 for(const id of ['tokyoCourseImage','kyotoCourseImage']){
   const img=$(id);
   if(!img)continue;
   img.addEventListener('error',()=>{
     const warn=$('courseMapWarning');
     if(warn){warn.hidden=false;
       warn.textContent='うまぽっとの画像を読み込めませんでした。素材の出典リンクをご確認ください。';}
     img.hidden=true;
   });
   img.addEventListener('load',()=>{
     const warn=$('courseMapWarning');
     if(warn && !Array.from(document.querySelectorAll('#referenceMapFigure img')).some(x=>x.hidden))warn.hidden=true;
   });
 }
}

function reset(startNow){
 if(!race)return;
 cancelAnimationFrame(frameId);
 const seed=seedValue();ui.seed.value=String(seed);
 sim=RaceSimEngine.create(race,{seed,pace:'auto',bias:ui.bias.value});
 cameraMotion=null;
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
 if(ui.abilityInfo){
  const selected=ui.focus.value==='leader'?state.horses.find(h=>h.number===state.leadingNo):
    state.horses.find(h=>String(h.number)===ui.focus.value);
  if(selected){
   const a=selected.abilityProfile;
   ui.abilityInfo.textContent=selected.number+'番 '+selected.name+'｜根拠の確かさ：'+a.confidence+
    '｜速度補正 '+(selected.ability+selected.paceFit).toFixed(2)+'m/秒（仮説）｜'+
    a.evidence.join(' ／ ')+(a.missing.length?' ／ 不足:'+a.missing.join('、'):'')+
    ' ／ 比較除外：'+a.excluded;
    if(ui.sixTraits){
      const labels={early:'先行力',cruise:'巡航速度',burst:'瞬発力',sustain:'持続力',stamina:'スタミナ',acceleration:'加速性能'};
      ui.sixTraits.innerHTML=Object.entries(labels).map(([key,label])=>
        '<div class="runner-trait"><span>'+label+'</span><strong>'+a.six[key]+'</strong><div class="trait-bar"><i style="width:'+a.six[key]+'%"></i></div></div>'
      ).join('');
    }
  }
 }
 if(ui.paceDynamics){
   const k={S:'スロー',M:'平均',H:'ハイ'}[state.splitPaceBand]||'計測中';
   const peak={S:'低',M:'中',H:'高'}[state.peakPaceBand]||'不明';
   ui.paceDynamics.textContent='通過時計ペース '+k+' ／ 先頭争い '+state.paceContestants+
     '頭（逃'+state.paceEscapers+'・先'+state.paceStalkers+
     '） ／ 序盤の競り合い最大 '+peak+' ／ 現在の競り合い負荷 '+Math.round(state.pacePressure*100)+'%'+
     (state.splitTime!==null?' ／ 前半'+state.splitDistanceM+'m '+dur(state.splitTime):'')+
     (state.straightEntryOrder?' ／ 直線順位変動 '+state.straightEntryOrder.filter(
       (no,i)=>sim.standings().findIndex(h=>h.number===no)!==i).length+'頭':'');
   ui.paceDynamics.setAttribute('data-pace',state.splitPaceBand||'M');
 }
 ui.remaining.textContent=Math.max(0,Math.round(state.distance-state.leader))+' m';
 const current=state.courseMetrics;
 ui.caption.textContent=state.finished?'全馬ゴール・余走完了':state.firstFinishTime!==null?'ゴール通過中':(current ? current.segment : 'スタート');
 const slopeInfo=$('courseSegment');
 if(slopeInfo){
   const z=current?.grade||0;
   slopeInfo.textContent=state.finished?'全馬ゴール':state.firstFinishTime!==null?'直線・ゴール板通過中':(current?.segment||'発走前')+
     (z>.0007?' ／ 上り':z<-.0007?' ／ 下り':' ／ 平坦')+
     (current?.kind==='turn'?' ／ コーナー':'');
 }
 const laneText=$('laneStatus');
 if(laneText){
   const watched=ui.focus.value==='leader'?state.horses.find(x=>x.number===state.leadingNo):
     state.horses.find(x=>String(x.number)===ui.focus.value);
   if(watched)laneText.textContent=watched.number+'番｜内ラチから約'+
      (1.8+watched.lane*1.65).toFixed(1)+'m　内へ '+watched.inwardMoves+
      '回／外へ '+watched.outwardMoves+'回　詰まり '+watched.trafficHoldSeconds.toFixed(1)+'秒';
 }
 // Stop the visible race clock at the winner's actual line-crossing time.
 ui.elapsed.textContent=dur(state.firstFinishTime??state.t);
 const splitEl=$('splitTime');
 if(splitEl){
  // Keep the sectional beneath the main timer once the line is crossed.
  // Do not expire after eight seconds: the two clocks remain comparable at
  // the finish and throughout the remainder of the simulation.
  splitEl.hidden=state.splitTime===null;
  const label=$('splitLabel'),value=$('splitValue');
  if(label)label.textContent='前半'+state.splitDistanceM+'m';
  if(value)value.textContent=state.splitTime===null?'—':dur(state.splitTime);
 }
 const podium=$('podium');
 if(podium){
  const finishers=firstThree(state);
  podium.hidden=finishers.length===0;
  podium.innerHTML=finishers.map((h,i)=>
    '<div class="podium-row"><span class="podium-rank">'+(i+1)+'着</span>'+
    '<span class="podium-name">'+esc(h.number+'番 '+h.name)+'</span>'+
    '<span class="podium-time">'+dur(h.finishTime)+'</span></div>').join('');
 }
 const latestPass=recentOvertake(state,2.2);
 ui.moment.textContent=state.finished?'全馬がゴールを駆け抜けました（仮想結果）':state.firstFinishTime!==null?'着順は線上で確定・全馬ゴール板へ進行中':latestPass?latestPass.attackerNo+'番 '+latestPass.attackerName+'が'+latestPass.victimNo+'番をかわす':state.leader>.05?'先頭 '+state.leadingNo+'番　'+(state.horses.find(h=>h.number===state.leadingNo)?.name||''):'スタートを押すとレースが始まります';
 ui.lap.textContent=Math.round(state.progress*100)+'%';
 ui.bar.style.width=(state.progress*100).toFixed(1)+'%';
 ui.stands.innerHTML=sim.standings().map((h,i)=>{
  const lead=state.leader-h.d;
  const gap=state.finished?dur(h.finishTime):i===0?'先頭':lead<.5?'並走':Math.round(lead)+'m';
  const focus=ui.focus.value===String(h.number);
  return '<div class="standing-row'+(focus?' focused':'')+'"><span class="rank-no">'+(i+1)+'</span><span class="saddle" style="background:'+jraWaku(h.number,race.field_size).fill+
     ';color:'+jraWaku(h.number,race.field_size).text+';border:1px solid '+
     jraWaku(h.number,race.field_size).border+'">'+h.number+'</span><span class="standing-name" title="'+esc(h.name)+'">'+esc(h.name)+' <span class="small-muted">'+({nige:'逃',senko:'先',sashi:'差',oikomi:'追',unknown:'？'}[h.style]||'？')+'</span></span><span class="standing-mark">'+h.mark+'</span><span class="standing-gap">'+gap+'</span></div>';
 }).join('');
 ui.events.innerHTML=state.events.slice(0,7).map(e=>
 '<li><strong>'+dur(e.t)+'</strong>　'+esc(e.message)+
 (e.kind==='split'&&state.splitTime!==null?' '+dur(state.splitTime):'')+'</li>').join('');
}
function drawIdle(message){
 const ctx=ui.canvas.getContext('2d');if(!ctx)return;
 ctx.clearRect(0,0,ui.canvas.width,ui.canvas.height);ctx.fillStyle='#202a36';ctx.fillRect(0,0,ui.canvas.width,ui.canvas.height);
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
/* A number marker IS the runner; its centre never leaves simulated track
   coordinates. No horse sprite, floating label, offset, leader line or tether. */
/* JRA official eight frame colors and starter-card assignment.
   18 starters: 1–6 frames two each, frames 7–8 three each.
   NEVER infer color from horse number modulo eight. */
const JRA_WAKU=Object.freeze([
 {name:'白',fill:'#fffdf5',text:'#111827',border:'#111827'},
 {name:'黒',fill:'#15191f',text:'#ffffff',border:'#f4f4f5'},
 {name:'赤',fill:'#d9142f',text:'#ffffff',border:'#fff4f4'},
 {name:'青',fill:'#164bb8',text:'#ffffff',border:'#f1f5ff'},
 {name:'黄',fill:'#ffde30',text:'#171717',border:'#35301c'},
 {name:'緑',fill:'#1d8c49',text:'#ffffff',border:'#edfff4'},
 {name:'橙',fill:'#f9811f',text:'#111827',border:'#422509'},
 {name:'桃',fill:'#f4a1c5',text:'#171717',border:'#542e3f'}
]);
function jraWaku(number,fieldSize=18){
 if(!Number.isInteger(number)||!Number.isInteger(fieldSize)||
   fieldSize<8||fieldSize>18||number<1||number>fieldSize)
   throw Error('JRA_WAKU_FIELD_INVALID');
 const base=Math.floor(fieldSize/8),extra=fieldSize%8;
 let first=1;
 for(let i=0;i<8;i++){
   const n=base+(i>=8-extra?1:0);
   if(number<first+n)return {waku:i+1,...JRA_WAKU[i]};
   first+=n;
 }
 throw Error('JRA_WAKU_NOT_FOUND');
}
window.RaceWakuColors=Object.freeze({forHorse:jraWaku,palette:JRA_WAKU});
function paintWakuLegend(){
 const root=$('wakuLegend');if(!root)return;
 root.innerHTML=JRA_WAKU.map((p,i)=>'<span class="waku-key" role="listitem"><span class="waku-swatch" style="background:'+
   p.fill+';color:'+p.text+';border-color:'+p.border+'">'+(i+1)+'</span>'+
   (i+1)+'枠 '+p.name+'</span>').join('');
}
function raceNumberMarker(ctx,number,x,y,scale,focused=false,leading=false,fieldSize=18,passing=false){
 if(!Number.isInteger(number)||number<1||!Number.isFinite(x)||!Number.isFinite(y))
  throw Error('SIM_NUMBER_POSITION_INVALID');
 const radius=(focused?15.5:13.5)*scale;
 const waku=jraWaku(number,fieldSize);
 ctx.save();
 ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);
 ctx.fillStyle=waku.fill;ctx.fill();
 ctx.lineWidth=(focused?2.8:2.1)*scale;
 ctx.strokeStyle=waku.border;ctx.stroke();
 if(focused){
   ctx.beginPath();ctx.arc(x,y,radius+4.3*scale,0,Math.PI*2);
   ctx.lineWidth=3.2*scale;ctx.strokeStyle='#f9d46c';ctx.stroke();
 }
 if(passing){
   // A thin ring around the genuine crossing point; no position offset.
   ctx.beginPath();ctx.arc(x,y,radius+7*scale,0,Math.PI*2);
   ctx.lineWidth=2.6*scale;ctx.strokeStyle='#b6f3a0';ctx.stroke();
 }
 ctx.textAlign='center';ctx.textBaseline='middle';
 ctx.fillStyle=waku.text;
 ctx.font='900 '+(number>9?16:18)*scale+'px Arial, sans-serif';
 ctx.fillText(String(number),x,y+.4*scale);
 ctx.restore();
 return {number,x,y,waku:waku.waku};
}
function projectRaceNumbers(horses,profile,origin,zoom,width,height,focusedNo,leadingNo,anchor={x:width*.5,y:height*.52},passingNo=null){
 if(!Array.isArray(horses))throw Error('SIM_HORSES_MISSING');
 return horses.map(h=>{
  const p=RaceCourseGeometry.point(profile,h.displayD??h.d,h.lane);
  return {number:h.number,x:anchor.x+zoom*(p.x-origin.x),
    y:anchor.y+zoom*(p.y-origin.y),
    focused:h.number===focusedNo,leading:h.number===leadingNo,
    passing:h.number===passingNo};
 }).sort((x,y)=>Number(x.passing)-Number(y.passing)||
  Number(x.focused)-Number(y.focused)||
  Number(x.leading)-Number(y.leading)||x.number-y.number);
}
function drawRaceNumbers(ctx,points,width,height,renderedWidth,fieldSize=18){
 const scale=width/Math.max(1,renderedWidth),visible=[];
 for(const p of points){
  const radius=(p.focused?15.5:13.5)*scale;
  // A number that is out of view stays out of view: never detach it
  // from the actual moving horse coordinates.
  if(p.x+radius<0||p.x-radius>width||p.y+radius<0||p.y-radius>height)continue;
  visible.push(raceNumberMarker(ctx,p.number,p.x,p.y,scale,p.focused,p.leading,fieldSize,p.passing));
 }
 return visible;
}
window.RaceSimNumbers=Object.freeze({
 marker:raceNumberMarker,project:projectRaceNumbers,draw:drawRaceNumbers
});
/* Always keep EVERY runner in frame in the standard camera. Fit the
   true world-coordinate bbox, including last place, and reserve space
   for number circles and mobile HUD. No label displacement. */
function frameEntireField(horses,profile,mode,width,height,renderedWidth){
 if(!Array.isArray(horses)||!horses.length)throw Error('SIM_AUTOFRAME_EMPTY_FIELD');
 const points=horses.map(h=>RaceCourseGeometry.point(profile,h.displayD??h.d,h.lane));
 const left=Math.min(...points.map(p=>p.x)),right=Math.max(...points.map(p=>p.x));
 const top=Math.min(...points.map(p=>p.y)),bottom=Math.max(...points.map(p=>p.y));
 const pixelRatio=width/Math.max(1,renderedWidth);
 const marginX=Math.min(width*.24,Math.max(48,22*pixelRatio));
 const marginTop=Math.min(height*.30,Math.max(110,82+19*pixelRatio));
 const marginBottom=Math.min(height*.30,Math.max(86,64+19*pixelRatio));
 const availableW=Math.max(80,width-2*marginX);
 const availableH=Math.max(80,height-marginTop-marginBottom);
 const maxZoom=mode==='followWide'?6.2:(renderedWidth<640?34.5:13.8);
 const zoom=Math.min(maxZoom,availableW/Math.max(.01,right-left),
     availableH/Math.max(.01,bottom-top));
 return {zoom,origin:{x:(left+right)/2,y:(top+bottom)/2},
   anchor:{x:width/2,y:(marginTop+height-marginBottom)/2},
   bounds:{left,right,top,bottom},count:horses.length,maxZoom};
}
/* Interpolate camera travel without teleporting at gate release.
   Limit zoom from the CURRENT bbox, not only the target bbox: keeping all
   real horse coordinates visible takes precedence over smoothing. */
function stableCameraFrame(target,previous,simTime,width,height,renderedWidth){
 if(!previous||simTime<previous.time||simTime===0){
   return {...target,time:simTime};
 }
 const dt=Math.max(0,Math.min(.25,simTime-previous.time));
 const alpha=1-Math.exp(-dt/.26);
 const center={
   x:previous.origin.x+(target.origin.x-previous.origin.x)*alpha,
   y:previous.origin.y+(target.origin.y-previous.origin.y)*alpha
 };
 const candidateZoom=previous.zoom+(target.zoom-previous.zoom)*alpha;
 const pixelRatio=width/Math.max(1,renderedWidth);
 const mx=Math.min(width*.24,Math.max(48,22*pixelRatio));
 const mt=Math.min(height*.30,Math.max(110,82+19*pixelRatio));
 const mb=Math.min(height*.30,Math.max(86,64+19*pixelRatio));
 const safeLeft=target.anchor.x-mx,safeRight=width-mx-target.anchor.x;
 const safeTop=target.anchor.y-mt,safeBottom=height-mb-target.anchor.y;
 const b=target.bounds;
 const maxZoom=Math.min(
   safeLeft/Math.max(.01,center.x-b.left),
   safeRight/Math.max(.01,b.right-center.x),
   safeTop/Math.max(.01,center.y-b.top),
   safeBottom/Math.max(.01,b.bottom-center.y)
 );
 const zoom=Math.max(.1,Math.min(candidateZoom,maxZoom));
 return {...target,origin:center,zoom,time:simTime};
}
window.RaceSimCamera=Object.freeze({viewCamera,frameEntireField,stableCameraFrame});
// Shared course rendering primitives, retained when replacing sprite display.
function traceCommands(ctx,parts){
 ctx.beginPath();
 for(const op of parts){
  if(op[0]==='M')ctx.moveTo(op[1],op[2]);
  else if(op[0]==='C')ctx.bezierCurveTo(...op.slice(1));
 }
}
// Active track and horse markers share ONE spline on ALL courses.
// The raw source Bézier pieces remain for the muted background illustration,
// but must not define a second, differently curved racing surface.
const raceTrackTraceCache=new WeakMap();
function traceRacePoints(course){
 if(!raceTrackTraceCache.has(course)){
  const sampleCount=Math.ceil(course.distance_m/1.0),points=[];
  for(let i=0;i<=sampleCount;i++){
   const d=course.distance_m*i/sampleCount;
   const p=RaceCourseGeometry.center(course,d);
   points.push({x:p.x,y:p.y});
  }
  raceTrackTraceCache.set(course,points);
 }
 return raceTrackTraceCache.get(course);
}
function traceRace(ctx,course){
 const pts=traceRacePoints(course);
 ctx.beginPath();ctx.moveTo(pts[0].x,pts[0].y);
 for(let i=1;i<pts.length;i++)ctx.lineTo(pts[i].x,pts[i].y);
}
function strokePath(ctx,width,color){
 ctx.strokeStyle=color;ctx.lineWidth=width;
 ctx.lineCap='round';ctx.lineJoin='round';ctx.stroke();
}

/* STAGE v0.21: goal camera keeps the trailing runners in view.
 * Tokyo goes screen-left to right; Kyoto's home straight goes right to left. */
function goalScreenPosition(distance,lane,finish,width,height,maxLane,turn='左'){
 const center=height*.52,step=Math.min(30,height/16);
 const direction=turn==='右'?-1:1,finishX=turn==='右'?width*.30:width*.70;
 return {x:finishX+direction*(distance-finish)*width/290,
         y:center+(lane-maxLane/2)*step};
}
function drawGoalPost(ctx,x,top,bottom){
 ctx.fillStyle='#26332d';ctx.fillRect(x-5,top-20,10,bottom-top+25);
 for(let y=top;y<bottom;y+=12){
   ctx.fillStyle=Math.floor((y-top)/12)%2?'#293532':'#faf8ed';
   ctx.fillRect(x-4,y,8,Math.min(12,bottom-y));
 }
 ctx.fillStyle='#f9f9ef';ctx.fillRect(x-38,top-48,76,26);
 ctx.lineWidth=2;ctx.strokeStyle='#243438';ctx.strokeRect(x-38,top-48,76,26);
 ctx.font='bold 16px Meiryo';ctx.fillStyle='#15282d';ctx.textAlign='center';
 ctx.fillText('GOAL',x,top-29);ctx.textAlign='left';
}
function drawGoalCamera(ctx,state,profile,width,height,renderedWidth,target){
 const maxLane=sim.laneConfig.maxLane,center=height*.52;
 const span=(maxLane/2+1.6)*Math.min(30,height/16);
 const top=Math.max(94,center-span),bottom=Math.min(height-48,center+span);
 ctx.clearRect(0,0,width,height);
 rect(ctx,0,0,width,height,'#244736');
 rect(ctx,0,top,width,bottom-top,'#e3dfbe');
 rect(ctx,0,top+13,width,bottom-top-26,'#79a65d');
 ctx.lineWidth=3;ctx.strokeStyle='#f8f5e3';
 for(const y of [top+13,bottom-13]){
   ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(width,y);ctx.stroke();
 }
 drawGoalPost(ctx,profile.turn==='右'?width*.30:width*.70,top+13,bottom-13);
 const scale=width/Math.max(1,renderedWidth);
 const passingNo=recentOvertake(state)?.attackerNo??null;
 // Apply the same actual-pass foreground order when the camera switches
 // 80m before the line; do not suppress the decisive final 80m.
 const runners=state.horses.slice().sort((a,b)=>
   Number(a.number===passingNo)-Number(b.number===passingNo)||
   Number(a.number===target.number)-Number(b.number===target.number)||
   a.number-b.number);
 for(const runner of runners){
   const q=goalScreenPosition(runner.displayD??runner.d,runner.lane,profile.distance_m,width,height,maxLane,profile.turn);
   if(q.x<-35||q.x>width+35)continue;
   raceNumberMarker(ctx,runner.number,q.x,q.y,scale,
     runner.number===target.number,runner.number===state.leadingNo,
     race.field_size,runner.number===passingNo);
 }
 // HUD lives exclusively in HTML stageCaption / elapsed / splitTime.
 // Do not draw extra television banners behind translucent labels.
}
window.RaceSimGoalView=Object.freeze({position:goalScreenPosition,drawPost:drawGoalPost});

function drawRace(){
 if(!sim||!race){drawIdle('出走馬の原本を確認中…');return}
 const ctx=ui.canvas.getContext('2d');if(!ctx)return;
 const w=ui.canvas.width,h=ui.canvas.height,state=sim.state,profile=RaceCourseGeometry.get(race.course_id);
 if(!profile)return;
 const mode='follow';
 const renderedWidth=ui.canvas.getBoundingClientRect?.().width||
     ui.canvas.clientWidth||Math.min(w,Math.max(1,window.innerWidth-20));
 const camera=viewCamera(mode,renderedWidth,w);
 const focus=ui.focus.value==='leader'?state.horses.find(x=>x.number===state.leadingNo):
       state.horses.find(x=>String(x.number)===ui.focus.value);
 const target=focus||state.horses[0];
 if(state.goalCamera){
   drawGoalCamera(ctx,state,profile,w,h,renderedWidth,target);
   drawCourse();
   if(window.RaceUmapotOverlay)RaceUmapotOverlay.draw(state,race,ui.focus.value,
      false,RaceSimNumbers.marker);
   return;
 }
 const requested=mode==='overview'
   ?{zoom:camera.zoom,origin:{x:306,y:119},anchor:{x:w*.5,y:h*.52}}
   :frameEntireField(state.horses,profile,mode,w,h,renderedWidth);
 // Only track a live chase camera; manual overview is an explicit hard cut.
 const frame=mode==='overview'?requested:
    stableCameraFrame(requested,cameraMotion,state.t,w,h,renderedWidth);
 cameraMotion=mode==='overview'?null:frame;
 const {zoom,origin,anchor}=frame;
 ctx.clearRect(0,0,w,h);
 // World camera stays north-up. As horses travel the curved course,
 // head/torso visibly rotate in the world coordinate system.
 rect(ctx,0,0,w,h,'#315b40');
 ctx.save();
 ctx.translate(anchor.x,anchor.y);
 ctx.scale(zoom,zoom);
 ctx.translate(-origin.x,-origin.y);
 ctx.fillStyle='#345f41';ctx.fillRect(-600,-600,1800,1500);
 for(let k=0;k<80;k++){
   const x=(k*149)%860-110,y=(k*41)%370-74;
   rect(ctx,x,y,24,3,k%2?'#3b6c48':'#2e573d');
 }
 // Off-route racetrack remains visible but muted.
 traceCommands(ctx,profile.background);strokePath(ctx,44,'#2a4233');
 traceCommands(ctx,profile.background);strokePath(ctx,38,'#738a65');
 traceCommands(ctx,profile.background);strokePath(ctx,32,'#63884c');
 if(profile.inner_turn){
   traceCommands(ctx,profile.inner_turn);strokePath(ctx,33,'#2a4233');
   traceCommands(ctx,profile.inner_turn);strokePath(ctx,27,'#73925d');
 }
 if(profile.branch){
   traceCommands(ctx,profile.branch);strokePath(ctx,35,'#2a4233');
   traceCommands(ctx,profile.branch);strokePath(ctx,29,'#648c59');
 }
 // Race-specific running route with clear inner and outer rails.
 traceRace(ctx,profile);strokePath(ctx,41,'#274832');
 traceRace(ctx,profile);strokePath(ctx,35,'#7a9e61');
 traceRace(ctx,profile);strokePath(ctx,31,'#87af65');
 traceRace(ctx,profile);strokePath(ctx,27,'#75a85f');
 // Distance markings use the shared physical race d-axis.
 const marks=[0,profile.distance_m-profile.straight_m,profile.distance_m-400,profile.distance_m-200,profile.distance_m];
 for(const d of marks){
   if(d<0||d>profile.distance_m)continue;
   const q=RaceCourseGeometry.point(profile,d,0);
   ctx.fillStyle=d===profile.distance_m?'#faf2b8':'#e8f5d4';
   ctx.beginPath();ctx.arc(q.x,q.y,2.8,0,Math.PI*2);ctx.fill();
 }
 ctx.restore();
 // Draw the real overtaker last for 1.9s. No displacement of number centres.
 const activePass=recentOvertake(state);
 const points=projectRaceNumbers(state.horses,profile,origin,zoom,w,h,
   target.number,state.leadingNo,anchor,activePass?.attackerNo??null);
 drawRaceNumbers(ctx,points,w,h,renderedWidth,race.field_size);
 // The HTML course-section and timing badges are the only HUD in this view.
 // The canvas renders the course and moving numbers, never duplicate titles.
 drawCourse();
 if(window.RaceUmapotOverlay)RaceUmapotOverlay.draw(state,race,ui.focus.value,false,RaceSimNumbers.marker);
}
/* Source-relative x/y after tracing JRA official planar course diagrams.
 * No additional anisotropic rendering correction is permitted. */
const COURSE_PLAN_Y=Object.freeze({});
function planPoint(profile,p){return {x:p.x,y:p.y}}
function planCoordinates(profile,commands){
 return commands.map(op=>{
   if(op[0]==='M'){
     const p=planPoint(profile,{x:op[1],y:op[2]});
     return ['M',p.x,p.y];
   }
   if(op[0]==='C'){
     const a=planPoint(profile,{x:op[1],y:op[2]});
     const b=planPoint(profile,{x:op[3],y:op[4]});
     const c=planPoint(profile,{x:op[5],y:op[6]});
     return ['C',a.x,a.y,b.x,b.y,c.x,c.y];
   }
   throw Error('UNKNOWN_PLAN_SEGMENT');
 });
}
window.RaceSimMapView=Object.freeze({point:planPoint,commands:planCoordinates,verticalRatio:COURSE_PLAN_Y});
function drawCourse(){
 // The old schematic canvas is intentionally absent in Umapot-only mode.
 if(!ui.map||!sim||!race)return;
 const ctx=ui.map.getContext('2d');if(!ctx)return;
 const prof=RaceCourseGeometry.get(race.course_id);if(!prof)return;
 ctx.clearRect(0,0,580,410);
 rect(ctx,0,0,580,410,'#1b3a2c');
 for(let k=0;k<70;k++){
   const x=(k*83)%580,y=(k*47)%310;
   rect(ctx,x,y,18,2,k%4===0?'#295039':'#234432');
 }
 // Full course and any additional Kyoto inner track are traced as separate
 // cubic outlines (topologically matched to official descriptions, not GPS).
 function path(commands){
   ctx.beginPath();
   // Background, inside/outside rails and racing line share the same
   // plan transform as every numbered horse and landmark.
   for(const op of planCoordinates(prof,commands)){
     if(op[0]==='M')ctx.moveTo(op[1],op[2]);
     if(op[0]==='C')ctx.bezierCurveTo(...op.slice(1));
   }
 }
 function stroke(commands,width,color){
   path(commands);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineJoin='round';ctx.lineCap='round';ctx.stroke();
 }
 stroke(prof.background,36,'#354b39');
 stroke(prof.background,32,'#789a69');
 stroke(prof.background,26,'#a4bf80');
 stroke(prof.background,23,'#73a96b');
 if(prof.inner_turn){
   stroke(prof.inner_turn,26,'#38503c');
   stroke(prof.inner_turn,18,'#6d9f64');
   stroke(prof.inner_turn,1,'rgba(239,243,215,.65)');
   ctx.fillStyle='#ecf6ce';ctx.font='bold 10px Meiryo';ctx.fillText('内回り',446,124);
 }
 if(prof.branch){stroke(prof.branch,27,'#34523d');stroke(prof.branch,23,'#91b87b');}
 const raceCmd=[['M',...prof.segments[0].p0]];
 for(const sg of prof.segments)raceCmd.push(['C',...sg.p1,...sg.p2,...sg.p3]);
 stroke(raceCmd,29,'#30523a');
 stroke(raceCmd,25,'#a9c58d');
 stroke(raceCmd,23,'#8cb574');
 stroke(raceCmd,1.3,'rgba(249,255,222,.55)');
 // All landmark locations use EXACTLY the same d-axis as the engine.
 for(const land of prof.landmarks){
   if(land.label==='2角'||land.label==='3角'||land.label==='4角'||land.label==='直線入口')continue;
   const p=planPoint(prof,RaceCourseGeometry.point(prof,land.d,0));
   if(land.label==='START'||land.label==='GOAL'){
      ctx.strokeStyle=land.label==='START'?'#fff6b1':'#fff';
      ctx.lineWidth=2.6;ctx.beginPath();ctx.moveTo(p.x-7,p.y-11);ctx.lineTo(p.x+7,p.y+11);ctx.stroke();
      ctx.font='bold 10px monospace';ctx.fillStyle=land.label==='START'?'#fbe7a1':'#fff';
      const shift=land.label==='START'?-36:12;
      ctx.fillText(land.label,p.x+shift,p.y+22);
   }else if(land.label.includes('坂')){
      ctx.fillStyle='#ebd67b';ctx.beginPath();ctx.arc(p.x,p.y,3.7,0,Math.PI*2);ctx.fill();
   }
 }
 const route=prof.landmarks;
 const first=RaceCourseGeometry.point(prof,0,0);
 const finish=RaceCourseGeometry.point(prof,prof.distance_m,0);
 ctx.fillStyle='#eff1e6';ctx.font='bold 11px Meiryo';
 ctx.fillText(prof.layout,16,19);
 ctx.fillStyle='#b8d1bd';ctx.font='10px Meiryo';
 ctx.fillText('JRA公式平面図ベース・測量座標ではありません',16,34);
 // The 18 runners share a continuous, monotone race-only path;
 // no horse is drawn on the non-racing inner/outer circuit.
 const horses=sim.state.horses.slice().sort((x,y)=>(x.displayD??x.d)-(y.displayD??y.d));
 for(const h of horses){
   const p=planPoint(prof,RaceCourseGeometry.point(prof,h.displayD??h.d,h.lane));
   const waku=jraWaku(h.number,race.field_size);
   ctx.fillStyle=waku.fill;
   ctx.beginPath();ctx.arc(p.x,p.y,h.number===sim.state.leadingNo?6.3:5.1,0,Math.PI*2);ctx.fill();
   ctx.lineWidth=h.number===sim.state.leadingNo?2.5:1.5;
   ctx.strokeStyle=h.number===sim.state.leadingNo?'#ffe694':waku.border;ctx.stroke();
   if(h.number===sim.state.leadingNo || ui.focus.value===String(h.number)){
     ctx.font='bold 10px monospace';ctx.fillStyle='#fff';ctx.fillText(String(h.number),p.x+8,p.y-8);
   }
 }
 // Elevation chart shares the exact profile breakpoints consumed by physics.
 const chartTop=334,chartBottom=395,left=65,right=552;
 rect(ctx,0,318,580,92,'#152e25');
 ctx.fillStyle='#bfd0c4';ctx.font='bold 10px Meiryo';ctx.fillText('標高差',8,338);
 ctx.font='10px monospace';ctx.fillText('m',29,351);
 const zvals=prof.profile.map(p=>p[1]);const zlo=Math.min(...zvals),zhi=Math.max(...zvals);
 const zToY=v=>chartBottom-10-(v-zlo)/(zhi-zlo||1)*43;
 const dToX=d=>left+(right-left)*d/prof.distance_m;
 ctx.strokeStyle='#688872';ctx.lineWidth=1;ctx.beginPath();
 ctx.moveTo(left,zToY(0));ctx.lineTo(right,zToY(0));ctx.stroke();
 ctx.beginPath();
 prof.profile.forEach((p,i)=>{if(i===0)ctx.moveTo(dToX(p[0]),zToY(p[1]));else ctx.lineTo(dToX(p[0]),zToY(p[1]));});
 ctx.strokeStyle='#f2d491';ctx.lineWidth=2.4;ctx.stroke();
 const pin=dToX(sim.state.leader),z=zToY(RaceCourseGeometry.height(prof,sim.state.leader));
 ctx.fillStyle='#fef7dc';ctx.beginPath();ctx.arc(pin,z,4,0,Math.PI*2);ctx.fill();
 ctx.font='10px monospace';ctx.fillStyle='#b6c5bb';
 ctx.fillText('START',left,405);ctx.fillText('GOAL',right-28,405);
 ctx.font='bold 10px Meiryo';ctx.fillStyle='#e6ebdf';
 ctx.fillText('▲ '+prof.elevation_range_m.toFixed(1)+'m',470,335);
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
setupReferenceMapErrorHandling();
ui.race.addEventListener('change',()=>loadRace(ui.race.value));
for(const input of [ui.bias,ui.seed])input.addEventListener('change',markDirty);
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
ui.speed.addEventListener('change',render);
window.addEventListener('resize',()=>{cameraMotion=null;resizeRaceCanvas();render()});
resizeRaceCanvas();
paintWakuLegend();
window.addEventListener('pagehide',()=>{running=false;cancelAnimationFrame(frameId)});
initialize();
})();
