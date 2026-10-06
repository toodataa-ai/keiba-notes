const pct=(n,d)=>d?`${(n/d*100).toFixed(1)}%`:'—';
const yen=n=>Number.isFinite(n)?`${Math.round(n).toLocaleString('ja-JP')}円`:'—';
const esc=(v='')=>String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function hasReview(r){if(typeof r?.review==='string')return r.review.trim().length>0;return !!(r?.review&&typeof r.review==='object'&&String(r.review.summary||'').trim());}
function dateParts(s){const [y,m,d]=s.split('-').map(Number);return {y,m,d};}
function isoDate(dt){return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth()+1).padStart(2,'0')}-${String(dt.getUTCDate()).padStart(2,'0')}`;}
function weekRange(s){const {y,m,d}=dateParts(s);const dt=new Date(Date.UTC(y,m-1,d));const dow=dt.getUTCDay();const back=(dow+6)%7;const start=new Date(dt);start.setUTCDate(dt.getUTCDate()-back);const end=new Date(start);end.setUTCDate(start.getUTCDate()+6);return {key:isoDate(start),start:isoDate(start),end:isoDate(end)};}
function periodKey(mode,r){if(mode==='year')return r.date.slice(0,4);if(mode==='month')return r.date.slice(0,7);if(mode==='week')return weekRange(r.date).key;return 'all';}
function periodText(mode,key,rows){if(mode==='all')return '全期間';if(mode==='year')return `${key}年`;if(mode==='month'){const [y,m]=key.split('-');return `${y}年${Number(m)}月`;}if(mode==='week'){const sample=rows.find(r=>weekRange(r.date).key===key);const w=sample?weekRange(sample.date):{start:key,end:key};return `${w.start}〜${w.end}`;}return key;}
(async()=>{
  const raceRes=await fetch('data/races.json',{cache:'no-store'});const db=await raceRes.json();
  const all=(db.races||[]).filter(r=>r.scope==='jra-main'&&r.status==='reviewed'&&r.performance&&hasReview(r)&&!(r.source==='legacy-performance-list'&&!hasReview(r))).sort((a,b)=>`${b.date}-${b.id}`.localeCompare(`${a.date}-${a.id}`));
  const mode=document.getElementById('periodMode'),value=document.getElementById('periodValue');
  function fill(){const m=mode.value;value.innerHTML='';if(m==='all'){value.disabled=true;value.innerHTML='<option value="all">全期間</option>';return;}value.disabled=false;[...new Set(all.map(r=>periodKey(m,r)))].sort().reverse().forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=periodText(m,k,all);value.appendChild(o);});}
  function rows(){return mode.value==='all'?[...all]:all.filter(r=>periodKey(mode.value,r)===value.value);}
  function render(){
    const rs=rows();document.getElementById('periodLabel').textContent=periodText(mode.value,value.value,all);
    const hits=rs.filter(r=>r.performance?.ticket_hit===true).length;
    const stake=rs.reduce((s,r)=>s+Number(r.performance?.stake_yen||0),0);
    const payout=rs.reduce((s,r)=>s+Number(r.performance?.payout_yen||0),0);
    const profit=payout-stake;
    const honmei=rs.filter(r=>Number.isFinite(Number(r.performance?.honmei_finish)));
    const wins=honmei.filter(r=>Number(r.performance.honmei_finish)===1).length;
    const places=honmei.filter(r=>Number(r.performance.honmei_finish)<=3).length;
    document.getElementById('statReviewed').textContent=rs.length;
    document.getElementById('statTicketRate').textContent=pct(hits,rs.length);
    document.getElementById('statStake').textContent=yen(stake);
    document.getElementById('statPayout').textContent=yen(payout);
    document.getElementById('statROI').textContent=stake?`${(payout/stake*100).toFixed(1)}%`:'—';
    const profitEl=document.getElementById('statProfit');profitEl.textContent=yen(profit);profitEl.className=profit>0?'positive':profit<0?'negative':'';
    document.getElementById('statHonmei').textContent=honmei.length?`${pct(wins,honmei.length)} / ${pct(places,honmei.length)}`:'—';
    document.getElementById('raceList').innerHTML=rs.length?rs.map(r=>{
      const p=r.performance;const reviewText=typeof r.review==='string'?r.review:(r.review?.summary||'');
      const marks=r.marks?`<div class="marks"><span class="mark"><b>◎</b>${esc(r.marks.win||'—')}</span><span class="mark"><b>○</b>${esc(r.marks.second||'—')}</span><span class="mark"><b>▲</b>${esc(r.marks.third||'—')}</span></div>`:'';
      return `<article class="race-card"><div class="race-top"><div><div class="meta">${esc(r.date)} · ${esc(r.venue||'JRA')} · ${esc(r.prompt_version||'—')}</div><h3>${esc(r.race||'')}</h3></div><span class="status reviewed">回顧済み</span></div>${marks}<div class="result-box"><b>${esc(r.result?.summary||'成績確定')}</b><br>馬券: ${p.ticket_hit?'的中':'不的中'} / 投資 ${yen(Number(p.stake_yen||0))} / 払戻 ${yen(Number(p.payout_yen||0))} / 収支 ${yen(Number(p.profit_yen??(Number(p.payout_yen||0)-Number(p.stake_yen||0))))}</div><details class="review-disclosure"><summary>反省会を見る</summary><div class="review-box">${esc(reviewText)}</div></details>${r.report?`<div class="actions"><a class="btn" href="${encodeURI(r.report)}">予想詳細を見る</a>${r.pdf?`<a class="btn secondary" href="${encodeURI(r.pdf)}">PDF</a>`:''}</div>`:''}</article>`;
    }).join(''):'<p class="muted">該当する成績はありません。</p>';
  }
  mode.addEventListener('change',()=>{fill();render();});value.addEventListener('change',render);fill();render();
})().catch(e=>{document.getElementById('raceList').innerHTML=`<p class="muted">読み込みに失敗しました: ${esc(e.message)}</p>`});