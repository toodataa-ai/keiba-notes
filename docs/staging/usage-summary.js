(() => {
  'use strict';
  // Read-only staging preview; never POST /keiba/collect.
  const ids={today:document.getElementById('stageUsageToday'),total:document.getElementById('stageUsageTotal')};
  const note=document.getElementById('stageUsageNote');
  if(!ids.today||!ids.total||!note)return;
  const KEYS=['page_home','page_this_week','page_results','page_schedule','page_methodology','page_research','page_other'];
  const ROOT='https://tokyo-family-events-metrics.tooda-t-aa.workers.dev/keiba';
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),9000);
  async function read(url){
    const res=await fetch(url,{cache:'no-store',credentials:'omit',signal:controller.signal});
    if(!res.ok)throw new Error('HTTP '+res.status);
    return res.json();
  }
  (async()=>{
    try{
      const config=await read('staging/usage-analytics-config.json');
      if(config.enabled!==true||config.site!=='keiba-notes'||config.endpoint!==ROOT)
        throw new Error('競馬用の集計設定が未確認です');
      const data=await read(ROOT+'/stats');
      if(data.site!=='keiba-notes'||data.schema_version!==1||!data.today||!data.totals)
        throw new Error('取得した集計の形式が不正です');
      const sum=counts=>KEYS.reduce((acc,key)=>{
        const value=counts[key];
        if(!Number.isSafeInteger(value)||value<0)throw new Error('PV形式が不正です');
        return acc+value;
      },0);
      ids.today.textContent=sum(data.today).toLocaleString('ja-JP');
      ids.total.textContent=sum(data.totals).toLocaleString('ja-JP');
      note.textContent='PV（ページ表示回数）。新方式の本番計測は未開始で、過去の利用数は含みません。';
    }catch(_){
      ids.today.textContent='—';ids.total.textContent='—';
      note.textContent='アクセス集計を取得できません。予想・回顧の閲覧には影響しません。';
    }finally{clearTimeout(timer)}
  })();
})();
