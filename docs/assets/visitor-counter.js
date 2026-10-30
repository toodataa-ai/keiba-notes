/* Anonymous production-only keiba metrics. The old CounterAPI is retired. */
(() => {
  'use strict';
  const ROOT='/keiba-notes/';
  const pages=Object.freeze({
    [ROOT]:'page_home',
    [ROOT+'index.html']:'page_home',
    [ROOT+'this-week.html']:'page_this_week',
    [ROOT+'schedule.html']:'page_schedule',
    [ROOT+'results.html']:'page_results',
    [ROOT+'methodology.html']:'page_methodology',
    [ROOT+'roadmap.html']:'page_research',
    [ROOT+'improvement-cycle.html']:'page_research',
    [ROOT+'release-history.html']:'page_other',
    [ROOT+'baba-models.html']:'page_research',
    [ROOT+'e2e.html']:'page_research',
    [ROOT+'experience-regime.html']:'page_research',
    [ROOT+'local-racing-shadow.html']:'page_research'
  });
  // Never count STAGING, LAB, admin, trend reports, immutable forecasts or PDFs.
  const pathname=location.pathname;
  if(location.origin!=='https://toodataa-ai.github.io'||
     !Object.prototype.hasOwnProperty.call(pages,pathname))return;

  function jstDay(){
    const p=new Intl.DateTimeFormat('en-US',{
      timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'
    }).formatToParts(new Date());
    const get=k=>p.find(x=>x.type===k)?.value;
    return [get('year'),get('month'),get('day')].join('-');
  }
  async function start(){
    let settings;
    try{
      const r=await fetch(ROOT+'assets/site-usage-config.json',{cache:'no-store',credentials:'omit'});
      if(!r.ok)return;
      settings=await r.json();
    }catch(_){return}
    if(settings?.schema_version!==1||settings.site!=='keiba-notes'||
       settings.enabled!==true||
       settings.endpoint!=='https://tokyo-family-events-metrics.tooda-t-aa.workers.dev/keiba')return;
    const url=settings.endpoint+'/collect';
    function hit(event){
      const body=JSON.stringify({site:'keiba-notes',event});
      try{
        if(navigator.sendBeacon&&
           navigator.sendBeacon(url,new Blob([body],{type:'text/plain'})))return;
      }catch(_){}
      fetch(url,{method:'POST',headers:{'Content-Type':'text/plain'},body,
        mode:'cors',credentials:'omit',keepalive:true}).catch(()=>{});
    }
    hit(pages[pathname]);
    try{
      const key='keiba-notes-jst-session-'+jstDay();
      if(sessionStorage.getItem(key)!=='1'){
        sessionStorage.setItem(key,'1');
        hit('session_start');
      }
    }catch(_){/* Session estimate unavailable when storage is blocked. */}
  }
  start();
})();
