const pct=(n,d)=>d?`${(n/d*100).toFixed(1)}%`:'—';
const yen=n=>Number.isFinite(n)?`${Math.round(n).toLocaleString('ja-JP')}円`:'—';
const esc=(v='')=>String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function hasReview(r){if(typeof r?.review==='string')return r.review.trim().length>0;return !!(r?.review&&typeof r.review==='object'&&String(r.review.summary||'').trim());}
function dateParts(s){const [y,m,d]=s.split('-').map(Number);return {y,m,d};}
function isoDate(dt){return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth()+1).padStart(2,'0')}-${String(dt.getUTCDate()).padStart(2,'0')}`;}
function weekRange(s){const {y,m,d}=dateParts(s);const dt=new Date(Date.UTC(y,m-1,d));const dow=dt.getUTCDay();const back=(dow+6)%7;const start=new Date(dt);start.setUTCDate(dt.getUTCDate()-back);const end=new Date(start);end.setUTCDate(start.getUTCDate()+6);return {key:isoDate(start),start:isoDate(start),end:isoDate(end)};}
function periodKey(mode,r){if(mode==='year')return r.date.slice(0,4);if(mode==='month')return r.date.slice(0,7);if(mode==='week')return weekRange(r.date).key;return 'all';}
function periodText(mode,key,rows){if(mode==='all')return '全期間';if(mode==='year')return `${key}年`;if(mode==='month'){const [y,m]=key.split('-');return `${y}年${Number(m)}月`;}if(mode==='week'){const sample=rows.find(r=>weekRange(r.date).key===key);const w=sample?weekRange(sample.date):{start:key,end:key};return `${w.start}〜${w.end}`;}return key;}
function splitBet(text){const m=String(text||'').trim().match(/^(\S+)\s+(.+)$/);return m?{type:m[1],selection:m[2]}:{type:'買い目',selection:String(text||'—')};}
function betTypeSummary(bets){const counts=new Map();for(const b of bets){const {type}=splitBet(b);counts.set(type,(counts.get(type)||0)+1);}return [...counts.entries()].map(([k,v])=>`${k}${v}点`).join('・');}
function betPanel(r){
  const p=r.performance||{};
  const hitSet=new Set(Array.isArray(p.hit_bets)?p.hit_bets:[]);
  const missSet=new Set(Array.isArray(p.miss_bets)?p.miss_bets:[]);
  const bets=Array.isArray(r.bets)&&r.bets.length?r.bets:[...hitSet,...missSet];
  if(!bets.length)return '<div class="bet-panel"><div class="bet-empty">買い目ごとの内訳は記録されていません。</div></div>';
  const stake=Number(p.stake_yen||0),payout=Number(p.payout_yen||0),profit=Number(p.profit_yen??(payout-stake));
  const explicitDetails=Array.isArray(p.bet_details)?p.bet_details:[];
  const detailMap=new Map(explicitDetails.map(x=>[x.bet||x.selection_text||x.id,x]));
  const equal100=stake===bets.length*100;
  const hitCount=bets.filter(b=>hitSet.has(b)).length;
  const rows=bets.map(b=>{
    const parsed=splitBet(b),detail=detailMap.get(b)||{};
    const isHit=detail.hit===true||hitSet.has(b);
    const isMiss=detail.hit===false||missSet.has(b);
    const amount=Number.isFinite(Number(detail.stake_yen))?Number(detail.stake_yen):(equal100?100:null);
    let rowPayout=Number.isFinite(Number(detail.payout_yen))?Number(detail.payout_yen):null;
    if(rowPayout==null&&isHit&&hitCount===1&&payout>0)rowPayout=payout;
    const status=isHit?'的中':isMiss?'ハズレ':'結果不明';
    const cls=isHit?'hit':'miss';
    const payoutText=rowPayout!=null&&rowPayout>0?`払戻 ${yen(rowPayout)}`:'';
    return `<div class="bet-row ${isHit?'is-hit':''}"><span class="bet-type">${esc(parsed.type)}</span><span class="bet-selection">${esc(parsed.selection)}</span><span class="bet-stake">${amount!=null?yen(amount):'—'}</span><span class="bet-status ${cls}">${status}</span><span class="bet-payout">${esc(payoutText)}</span></div>`;
  }).join('');
  const pointText=equal100?`${bets.length}点 × 100円`:`${bets.length}点`;
  const summary=betTypeSummary(bets);
  return `<section class="bet-panel" aria-label="購入した馬券"><div class="bet-panel-head"><strong>購入した馬券</strong><span>${esc(summary)} ／ ${esc(pointText)}</span></div><div class="bet-list">${rows}</div><div class="bet-total"><div><small>購入合計</small><strong>${yen(stake)}</strong></div><div><small>払戻合計</small><strong>${yen(payout)}</strong></div><div><small>収支</small><strong class="${profit>0?'positive':profit<0?'negative':''}">${yen(profit)}</strong></div></div></section>`;
}
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
      const outcome=p.ticket_hit?'<span class="status reviewed">的中あり</span>':'<span class="status">全買い目ハズレ</span>';
      return `<article class="race-card"><div class="race-top"><div><div class="meta">${esc(r.date)} · ${esc(r.venue||'JRA')} · ${esc(r.prompt_version||'—')}</div><h3>${esc(r.race||'')}</h3></div>${outcome}</div>${marks}<div class="result-box result-summary"><b>レース結果</b><br>${esc(r.result?.summary||'成績確定')}</div>${betPanel(r)}<details class="review-disclosure"><summary>反省会を見る</summary><div class="review-box">${esc(reviewText)}</div></details>${r.report?`<div class="actions"><a class="btn" href="${encodeURI(r.report)}">予想詳細を見る</a>${r.pdf?`<a class="btn secondary" href="${encodeURI(r.pdf)}">PDF</a>`:''}</div>`:''}</article>`;
    }).join(''):'<p class="muted">該当する成績はありません。</p>';
  }
  mode.addEventListener('change',()=>{fill();render();});value.addEventListener('change',render);fill();render();
})().catch(e=>{document.getElementById('raceList').innerHTML=`<p class="muted">読み込みに失敗しました: ${esc(e.message)}</p>`});