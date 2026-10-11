const esc=(v='')=>String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function jstToday(){return new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Tokyo'});}
function jstClock(){const parts=new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(new Date());const o=Object.fromEntries(parts.map(p=>[p.type,p.value]));return `${o.hour}:${o.minute}`;}
function isoUtc(s){const [y,m,d]=s.split('-').map(Number);return new Date(Date.UTC(y,m-1,d));}
function dayGap(a,b){return Math.round((isoUtc(b)-isoUtc(a))/86400000);}
function hasReview(r){if(typeof r?.review==='string')return r.review.trim().length>0;return !!(r?.review&&typeof r.review==='object'&&String(r.review.summary||'').trim());}
function niceDate(s,weekday=''){const [,m,d]=s.split('-').map(Number);return `${m}/${d}${weekday?`（${weekday}）`:''}`;}
function card(r){
  const marks=r.marks?`<div class="marks"><span class="mark"><b>◎</b>${esc(r.marks.win||'—')}</span><span class="mark"><b>○</b>${esc(r.marks.second||'—')}</span><span class="mark"><b>▲</b>${esc(r.marks.third||'—')}</span></div>`:'';
  const links=[];
  if(r.report)links.push(`<a class="btn" href="${encodeURI(r.report)}">AI予想詳細を見る</a>`);
  if(r.pdf)links.push(`<a class="btn secondary" href="${encodeURI(r.pdf)}">PDF</a>`);
  return `<article class="race-card"><div class="race-top"><div><div class="meta">${esc(r.date)} · ${esc(r.venue||'JRA')} · ${esc(r.prompt_version||'—')}</div><h3>${esc(r.race||'')}</h3></div><span class="status">AI予想公開済み</span></div>${marks}${links.length?`<div class="actions">${links.join('')}</div>`:''}</article>`;
}
// Display the newest audited v3.11 report, while preserving historical prereace proof.
// This overlay only changes visitor-facing links: settlement/analysis history is untouched.
function displayNewestPredictions(rows, parallel){
  if(parallel?.schema_version!==1 || parallel.original_v310_immutable!==true || !Array.isArray(parallel.races)) return rows;
  const originalById=new Map(rows.map(r=>[r.id,r]));
  const overrides=new Map();
  for(const x of parallel.races){
    if(!x || x.prompt_version!=='v3.11' || typeof x.race_id!=='string') continue;
    const previous=originalById.get(x.race_id);
    if(!previous || previous.scope!=='jra-main' || previous.status!=='predicted' ||
       previous.prompt_version!=='v3.10' || previous.date!==x.date) continue;
    if(x.report!==`reports/${x.race_id}-v311.html` || x.pdf!==`pdfs/${x.race_id}-v311.pdf`) continue;
    if(!/^[a-f0-9]{40}$/.test(x.proof_commit||'') ||
       !Number.isInteger(x.pdf_pages) || x.pdf_pages<(previous.field_size||0)+8) continue;
    if(!Array.isArray(x.final_bets) || x.final_bets.some(b=>!b.id || !b.type || !Array.isArray(b.selection))) continue;
    overrides.set(x.race_id,{...previous,prompt_version:'v3.11',
      report:x.report,pdf:x.pdf,full_report_pages:x.pdf_pages,
      pdf_mode:'full',proof_commit:x.proof_commit,
      purchase_decision:x.decision,total_stake_yen:x.total_stake_yen,
      final_bets:x.final_bets});
  }
  return rows.map(r=>overrides.get(r.id)||r);
}
function estimateHtml(day,publishedCount,policy){
  const total=(day.races||[]).length;
  if(!total||publishedCount>=total)return '';
  const today=jstToday(),clock=jstClock();
  const win=policy?.publish_window||{};
  const start=win.start||'08:00',end=win.end||'09:00',label=win.label||'8:00〜9:00頃';
  let title;
  if(day.date>today)title=`AI予想 公開予定：${niceDate(day.date,day.weekday)} ${label}`;
  else if(day.date===today&&clock<start)title=`AI予想 公開予定：本日 ${label}`;
  else if(day.date===today&&clock<end)title=`AI予想を順次公開中：${label}が目安です`;
  else if(day.date===today)title='AI予想を順次公開中';
  else title='未公開のAI予想があります';
  const progress=publishedCount?`現在 ${publishedCount}/${total}レース公開済み。`:'';
  const note=policy?.note||'最新の出馬表・馬場情報を確認して順次公開します。処理状況により前後する場合があります。';
  return `<div class="publish-estimate"><strong>${esc(title)}</strong><small>${esc(progress+note)}</small></div>`;
}
function selectNextBlock(days,rows){
  const today=jstToday();
  const sorted=[...(days||[])].filter(d=>Array.isArray(d.races)&&d.races.length).sort((a,b)=>a.date.localeCompare(b.date));
  const reviewedByDate=new Map();
  for(const r of rows){
    if(r.scope!=='jra-main'||r.status!=='reviewed')continue;
    reviewedByDate.set(r.date,(reviewedByDate.get(r.date)||0)+1);
  }
  const unresolved=sorted.filter(d=>{
    if(d.date<today)return false;
    const reviewed=reviewedByDate.get(d.date)||0;
    return reviewed<(d.races||[]).length;
  });
  if(!unresolved.length)return [];
  const block=[unresolved[0]];
  for(let i=1;i<unresolved.length;i++){
    const prev=block[block.length-1],cur=unresolved[i];
    if(dayGap(prev.date,cur.date)===1)block.push(cur);
    else break;
  }
  return block;
}
(async()=>{
  const root=document.getElementById('weekPredictions');
  const scheduleRoot=document.getElementById('weekSchedule');
  const period=document.getElementById('weekPeriod');
  const scheduleTitle=document.getElementById('scheduleTitle');
  try{
    const [raceRes,scheduleRes,policyRes,parallelRes]=await Promise.all([
      fetch('data/races.json',{cache:'no-store'}),
      fetch('data/upcoming_schedule.json',{cache:'no-store'}),
      fetch('data/prediction_publication_policy.json',{cache:'no-store'}),
      fetch('data/jra-v311-parallel-2026-10-11.json',{cache:'no-store'}).catch(()=>null)
    ]);
    const db=await raceRes.json();
    const schedule=scheduleRes.ok?await scheduleRes.json():{days:[]};
    const policy=policyRes.ok?await policyRes.json():{};
    const parallel=parallelRes?.ok?await parallelRes.json():null;
    const allRows=displayNewestPredictions(
      (db.races||[]).filter(r=>r.scope==='jra-main'&&!(r.source==='legacy-performance-list'&&!hasReview(r))),
      parallel);
    const days=selectNextBlock(schedule.days||[],allRows);
    if(scheduleTitle)scheduleTitle.textContent='次回の対象レース';
    if(days.length){
      period.textContent=days.length===1?days[0].date:`${days[0].date} 〜 ${days[days.length-1].date}`;
    }else{
      period.textContent='次回開催は未登録です';
    }
    const dateSet=new Set(days.map(d=>d.date));
    const rows=allRows.filter(r=>dateSet.has(r.date)&&r.status!=='reviewed').sort((a,b)=>`${a.date}-${a.id}`.localeCompare(`${b.date}-${b.id}`));
    if(rows.length){
      root.innerHTML=rows.map(card).join('');
    }else if(days.length){
      const first=days[0];
      const label=policy?.publish_window?.label||'8:00〜9:00頃';
      root.innerHTML=`<div class="publish-estimate"><strong>次回のAI予想はまだ公開前です</strong><small>${esc(`${niceDate(first.date,first.weekday)} ${label}を目安に順次公開します。`)}${esc(policy?.note?' '+policy.note:'')}</small></div>`;
    }else{
      root.innerHTML='<p class="muted">次回の対象レース予定はまだ登録されていません。</p>';
    }
    scheduleRoot.innerHTML=days.length?days.map(d=>{
      const published=allRows.filter(r=>r.date===d.date).length;
      return `<article class="week-day"><h3>${esc(d.date)}（${esc(d.weekday||'')}）</h3>${d.races.map(r=>`<div class="week-race"><span>${esc(r.track)}</span><strong>${esc(r.race)}</strong><time>${esc(r.post_time||'')}</time></div>`).join('')}${estimateHtml(d,published,policy)}</article>`;
    }).join(''):'<p class="muted">次回の対象レース予定はまだ登録されていません。</p>';
  }catch(e){
    root.innerHTML=`<p class="muted">読み込みに失敗しました: ${esc(e.message)}</p>`;
  }
})();