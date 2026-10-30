(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const EVENT_NAMES=['page_home','page_this_week','page_results','page_schedule',
    'page_methodology','page_research','page_other'];
  const toCount=n=>Number.isSafeInteger(n)&&n>=0?n:null;
  const fmt=n=>n===null?'—':n.toLocaleString('ja-JP');
  const status=(message,error=false)=>{
    byId('status').textContent=message;
    byId('status').className='status'+(error?' error':' ok');
  };
  let cfg=null;
  let requestSerial=0;
  function sum(p,keys){
    if(!p||typeof p!=='object')throw Error('集計データの形式が不正です');
    return keys.reduce((total,k)=>{
      const n=toCount(p[k]);if(n===null)throw Error('数値が不正です: '+k);
      return total+n;
    },0);
  }
  async function getJson(url){
    const c=new AbortController(),t=setTimeout(()=>c.abort(),8500);
    try {
      const r=await fetch(url,{cache:'no-store',credentials:'omit',signal:c.signal});
      if(!r.ok)throw Error('HTTP '+r.status);
      return await r.json();
    }finally{clearTimeout(t)}
  }
  const pageViews=c=>sum(c,EVENT_NAMES);
  function clearHistory(){
    byId('historyRows').replaceChildren();
    byId('chart').replaceChildren();
  }
  function clearCounters(){
    for(const id of ['pvToday','pvTotal','sessionToday','sessionTotal'])byId(id).textContent='—';
  }
  function make(tag,cls,value){
    const e=document.createElement(tag);if(cls)e.className=cls;
    if(value!==undefined)e.textContent=String(value);return e;
  }
  function renderHistory(rows){
    const target=byId('historyRows'),chart=byId('chart');
    target.replaceChildren();chart.replaceChildren();
    if(!rows.length){
      const tr=make('tr');const td=make('td','', '記録がある日がありません（計測開始後に表示）');
      td.colSpan=3;tr.append(td);target.append(tr);return;
    }
    const history=rows.map(row=>{
      if(!/^\d{4}-\d{2}-\d{2}$/.test(row.day))throw Error('履歴の日付が不正です');
      return {day:row.day,pv:pageViews(row.counts),sessions:sum(row.counts,['session_start'])};
    }).sort((a,b)=>b.day.localeCompare(a.day));
    const max=Math.max(1,...history.map(r=>r.pv));
    for(const row of history){
      const tr=make('tr');for(const value of [row.day,fmt(row.pv),fmt(row.sessions)])tr.append(make('td','',value));
      target.append(tr);
      const line=make('div','chart-row');
      const day=make('span','',row.day.slice(5));
      const track=make('div','bar-track'),bar=make('div','bar');
      bar.style.width=(row.pv/max*100).toFixed(1)+'%';
      bar.title=row.day+'：'+row.pv+'PV';
      track.append(bar);
      line.append(day,track,make('span','num',fmt(row.pv)));
      chart.append(line);
    }
  }
  async function refresh(){
    const serial=++requestSerial;
    byId('refresh').disabled=true;
    clearHistory();
    byId('historyStatus').textContent='履歴を取得中です…';
    if(!cfg?.enabled||!/^https:\/\//.test(cfg?.endpoint||'')){
      clearCounters();
      status('競馬専用の集計APIは接続準備中です。既存の人数や過去の閲覧記録を推測して表示しません。',true);
      byId('historyStatus').textContent='Cloudflare Worker／D1接続・動作検証後に利用できます。';
      byId('refresh').disabled=false;return;
    }
    const endpoint=cfg.endpoint.replace(/\/$/,'');
    status('本日と累計の集計を取得中です…');
    const days=byId('period').value;
    const [stats,history]=await Promise.allSettled([
      getJson(endpoint+'/stats'),getJson(endpoint+'/history?days='+encodeURIComponent(days))
    ]);
    if(serial!==requestSerial)return;
    if(stats.status==='fulfilled'){
      try{
        const d=stats.value;
        if(d.site!=='keiba-notes'||d.schema_version!==1||!/^\d{4}-\d{2}-\d{2}$/.test(d.day_jst))throw Error('別サイトの集計が混在しています');
        byId('pvToday').textContent=fmt(pageViews(d.today));
        byId('pvTotal').textContent=fmt(pageViews(d.totals));
        byId('sessionToday').textContent=fmt(sum(d.today,['session_start']));
        byId('sessionTotal').textContent=fmt(sum(d.totals,['session_start']));
        status('公式の集計APIに接続済み（'+d.day_jst+' 日本時間）');
      }catch(e){clearCounters();status('集計データの検証に失敗しました：'+e.message,true)}
    }else {clearCounters();status('カウンター取得失敗：'+stats.reason?.message,true)}
    if(history.status==='fulfilled'){
      try{
        const data=history.value;
        if(data.site!=='keiba-notes'||data.schema_version!==1||data.days!==Number(days)||!Array.isArray(data.rows))
          throw Error('履歴形式が正しくありません');
        renderHistory(data.rows);
        byId('historyStatus').textContent=data.recorded_days+'日分の実測記録を表示。記録開始前の日付は復元できません。';
      }catch(e){byId('historyStatus').textContent='履歴データを検証できません：'+e.message}
    }else byId('historyStatus').textContent='履歴取得失敗：'+history.reason?.message;
    byId('refresh').disabled=false;
  }
  byId('period').addEventListener('change',refresh);
  byId('refresh').addEventListener('click',refresh);
  (async()=>{
    try{
      cfg=await getJson('usage-analytics-config.json');
      if(cfg.schema_version!==1||cfg.site!=='keiba-notes')throw Error('接続設定が不正です');
    }catch(e){status('設定を読み込めません：'+e.message,true)}
    await refresh();
  })();
})();