const pct=(n,d)=>d?`${(n/d*100).toFixed(1)}%`:'—';
const yen=n=>Number.isFinite(n)?`${Math.round(n).toLocaleString('ja-JP')}円`:'—';

async function load(){
  const [raceRes,promptRes]=await Promise.all([
    fetch('data/races.json',{cache:'no-store'}),
    fetch('data/latest_prompt.json',{cache:'no-store'})
  ]);
  const db=await raceRes.json();
  const prompt=await promptRes.json();
  document.getElementById('promptBadge').textContent=`最新版プロンプト ${prompt.version}`;
  const reviewed=db.races.filter(r=>r.status==='reviewed'&&r.performance);
  const winHits=reviewed.filter(r=>r.performance?.honmei_finish===1).length;
  const placeHits=reviewed.filter(r=>Number(r.performance?.honmei_finish)<=3).length;
  const ticketHits=reviewed.filter(r=>r.performance?.ticket_hit===true).length;
  const stake=reviewed.reduce((s,r)=>s+Number(r.performance?.stake_yen||0),0);
  const payout=reviewed.reduce((s,r)=>s+Number(r.performance?.payout_yen||0),0);
  document.getElementById('statReviewed').textContent=reviewed.length;
  document.getElementById('statWinRate').textContent=pct(winHits,reviewed.length);
  document.getElementById('statPlaceRate').textContent=pct(placeHits,reviewed.length);
  document.getElementById('statTicketRate').textContent=pct(ticketHits,reviewed.length);
  document.getElementById('statROI').textContent=stake?`${(payout/stake*100).toFixed(1)}%`:'—';

  const filter=document.getElementById('statusFilter');
  const render=()=>{
    const rows=[...db.races]
      .filter(r=>filter.value==='all'||r.status===filter.value)
      .sort((a,b)=>`${b.date}-${b.id}`.localeCompare(`${a.date}-${a.id}`));
    const root=document.getElementById('raceList');
    if(!rows.length){root.innerHTML='<p class="muted">該当する予想はありません。</p>';return;}
    root.innerHTML=rows.map(r=>{
      const result=r.result?`<div class="result-box"><b>結果</b> ${escapeHtml(r.result.summary||'確定')} ${r.performance?` / 馬券: ${r.performance.ticket_hit?'的中':'不的中'} / 投資 ${yen(Number(r.performance.stake_yen||0))} / 払戻 ${yen(Number(r.performance.payout_yen||0))}`:''}</div>`:'';
      return `<article class="race-card">
        <div class="race-top"><div><div class="meta">${escapeHtml(r.date)} · ${escapeHtml(r.venue)} · ${escapeHtml(r.prompt_version)}</div><h3>${escapeHtml(r.race)}</h3></div><span class="status ${r.status==='reviewed'?'reviewed':''}">${r.status==='reviewed'?'回顧済み':'予想済み'}</span></div>
        <div class="marks"><span class="mark"><b>◎</b>${escapeHtml(r.marks?.win||'—')}</span><span class="mark"><b>○</b>${escapeHtml(r.marks?.second||'—')}</span><span class="mark"><b>▲</b>${escapeHtml(r.marks?.third||'—')}</span></div>
        ${result}
        <div class="actions"><a class="btn" href="${encodeURI(r.report)}">予想・回顧を見る</a><a class="btn secondary" href="${encodeURI(r.pdf)}">PDF</a></div>
      </article>`;
    }).join('');
  };
  filter.addEventListener('change',render);render();
}
function escapeHtml(v=''){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
load().catch(e=>{document.getElementById('raceList').innerHTML=`<p class="muted">読み込みに失敗しました: ${escapeHtml(e.message)}</p>`});
