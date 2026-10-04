const pct=(n,d)=>d?`${(n/d*100).toFixed(1)}%`:'—';
const yen=n=>Number.isFinite(n)?`${Math.round(n).toLocaleString('ja-JP')}円`:'—';
const esc=(v='')=>String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

function dateParts(s){const [y,m,d]=s.split('-').map(Number);return {y,m,d};}
function isoDate(dt){return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth()+1).padStart(2,'0')}-${String(dt.getUTCDate()).padStart(2,'0')}`;}
function weekRange(s){
  const {y,m,d}=dateParts(s);const dt=new Date(Date.UTC(y,m-1,d));
  const dow=dt.getUTCDay();const back=(dow+6)%7;
  const start=new Date(dt);start.setUTCDate(dt.getUTCDate()-back);
  const end=new Date(start);end.setUTCDate(start.getUTCDate()+6);
  return {key:isoDate(start),start:isoDate(start),end:isoDate(end)};
}
function jpDate(s){const {y,m,d}=dateParts(s);return `${y}/${m}/${d}`;}
function periodKey(mode,r){
  if(mode==='year') return r.date.slice(0,4);
  if(mode==='month') return r.date.slice(0,7);
  if(mode==='week') return weekRange(r.date).key;
  return 'all';
}
function periodText(mode,key,rows){
  if(mode==='all') return '全期間';
  if(mode==='year') return `${key}年`;
  if(mode==='month'){const [y,m]=key.split('-');return `${y}年${Number(m)}月`;}
  if(mode==='week'){
    const sample=rows.find(r=>weekRange(r.date).key===key);const w=sample?weekRange(sample.date):{start:key,end:key};
    return `${jpDate(w.start)}〜${jpDate(w.end)} 開催週`;
  }
  return key;
}

async function load(){
  const [raceRes,promptRes]=await Promise.all([
    fetch('data/races.json',{cache:'no-store'}),
    fetch('data/latest_prompt.json',{cache:'no-store'})
  ]);
  const db=await raceRes.json();
  const prompt=await promptRes.json();
  document.getElementById('promptBadge').textContent=`最新版プロンプト ${prompt.version}`;

  const allRaces=(db.races||[]).filter(r=>r.scope==='jra-main');
  const periodMode=document.getElementById('periodMode');
  const periodValue=document.getElementById('periodValue');
  const statusFilter=document.getElementById('statusFilter');

  function fillPeriodValues(){
    const mode=periodMode.value;
    periodValue.innerHTML='';
    if(mode==='all'){
      periodValue.disabled=true;
      periodValue.innerHTML='<option value="all">全期間</option>';
      return;
    }
    periodValue.disabled=false;
    const keys=[...new Set(allRaces.map(r=>periodKey(mode,r)))].sort().reverse();
    keys.forEach(k=>{
      const op=document.createElement('option');op.value=k;op.textContent=periodText(mode,k,allRaces);periodValue.appendChild(op);
    });
  }

  function currentRows(){
    const mode=periodMode.value;const val=periodValue.value;
    if(mode==='all') return [...allRaces];
    return allRaces.filter(r=>periodKey(mode,r)===val);
  }

  function renderStats(rows){
    const reviewed=rows.filter(r=>r.status==='reviewed'&&r.performance);
    const hits=reviewed.filter(r=>r.performance?.ticket_hit===true).length;
    const stake=reviewed.reduce((s,r)=>s+Number(r.performance?.stake_yen||0),0);
    const payout=reviewed.reduce((s,r)=>s+Number(r.performance?.payout_yen||0),0);
    const profit=payout-stake;
    const honmeiRows=reviewed.filter(r=>r.performance?.honmei_finish!=null&&Number.isFinite(Number(r.performance.honmei_finish)));
    const wins=honmeiRows.filter(r=>Number(r.performance.honmei_finish)===1).length;
    const places=honmeiRows.filter(r=>Number(r.performance.honmei_finish)<=3).length;
    document.getElementById('statReviewed').textContent=reviewed.length;
    document.getElementById('statTicketRate').textContent=pct(hits,reviewed.length);
    document.getElementById('statROI').textContent=stake?`${(payout/stake*100).toFixed(1)}%`:'—';
    const profitEl=document.getElementById('statProfit');profitEl.textContent=yen(profit);profitEl.className=profit>0?'positive':profit<0?'negative':'';
    document.getElementById('statHonmei').textContent=honmeiRows.length?`${pct(wins,honmeiRows.length)} / ${pct(places,honmeiRows.length)}`:'—';
    document.getElementById('statHonmeiNote').textContent=honmeiRows.length<reviewed.length?`印着順を保存済みの${honmeiRows.length}レースで算出`:'';
  }

  function renderLegacyNote(rows){
    const box=document.getElementById('legacyNote');
    const n=rows.filter(r=>r.source==='legacy-performance-list').length;
    if(!n){box.hidden=true;box.innerHTML='';return;}
    const s=db.legacy_summary;
    box.hidden=false;
    if(s){
      box.innerHTML=`<b>過去成績を移行済み</b>：2026/9/5〜10/3の厳密集計12レースを初期データとして反映しています。全12レースでは投資 ${yen(Number(s.stake_yen))}、払戻 ${yen(Number(s.payout_yen))}、収支 ${yen(Number(s.profit_yen))}、回収率 ${Number(s.roi_pct).toFixed(1)}%、的中 ${s.ticket_hits}/${s.race_count}。神戸新聞杯は券種不明のため集計外です。`;
    }else{box.textContent=`過去成績一覧から${n}レースを移行済みです。`;}
  }

  function render(){
    const periodRows=currentRows();
    document.getElementById('periodLabel').textContent=periodText(periodMode.value,periodValue.value,allRaces);
    renderStats(periodRows);renderLegacyNote(periodRows);
    const rows=periodRows
      .filter(r=>statusFilter.value==='all'||r.status===statusFilter.value)
      .sort((a,b)=>`${b.date}-${b.id}`.localeCompare(`${a.date}-${a.id}`));
    const root=document.getElementById('raceList');
    if(!rows.length){root.innerHTML='<p class="muted">該当するJRAメイン予想はありません。</p>';return;}
    root.innerHTML=rows.map(r=>{
      const p=r.performance;
      const result=p?`<details class="result-disclosure"><summary>結果を見る</summary><div class="result-box"><b>${r.result?.summary?esc(r.result.summary):'成績確定'}</b><br>馬券: ${p.ticket_hit?'的中':'不的中'} / 投資 ${yen(Number(p.stake_yen||0))} / 払戻 ${yen(Number(p.payout_yen||0))} / 収支 <span class="${Number(p.profit_yen)>0?'positive':Number(p.profit_yen)<0?'negative':''}">${yen(Number(p.profit_yen??(Number(p.payout_yen||0)-Number(p.stake_yen||0))))}</span></div></details>`:'';
      const marks=r.marks?`<div class="marks"><span class="mark"><b>◎</b>${esc(r.marks.win||'—')}</span><span class="mark"><b>○</b>${esc(r.marks.second||'—')}</span><span class="mark"><b>▲</b>${esc(r.marks.third||'—')}</span></div>`:'';
      const links=[];
      if(r.report) links.push(`<a class="btn" href="${encodeURI(r.report)}">予想詳細を見る</a>`);
      if(r.pdf) links.push(`<a class="btn secondary" href="${encodeURI(r.pdf)}">PDF</a>`);
      const actions=links.length?`<div class="actions">${links.join('')}</div>`:`<div class="legacy-source">過去の成績一覧から移行した記録</div>`;
      return `<article class="race-card">
        <div class="race-top"><div><div class="meta">${esc(r.date)} · ${esc(r.venue||'JRA')} · ${esc(r.prompt_version||'—')}</div><h3>${esc(r.race)}</h3></div><span class="status ${r.status==='reviewed'?'reviewed':''}">${r.status==='reviewed'?'結果登録済み':'予想済み'}</span></div>
        ${marks}${result}${actions}
      </article>`;
    }).join('');
  }

  periodMode.addEventListener('change',()=>{fillPeriodValues();render();});
  periodValue.addEventListener('change',render);
  statusFilter.addEventListener('change',render);
  fillPeriodValues();render();
}

load().catch(e=>{document.getElementById('raceList').innerHTML=`<p class="muted">読み込みに失敗しました: ${esc(e.message)}</p>`});
