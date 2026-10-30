/* LAB-only candidate for future production tracking: this file is not loaded in production. */
(() => {
  'use strict';
  const ROOT='/keiba-notes/';
  const PAGES=Object.freeze({
    [ROOT]:'page_home',
    [ROOT+'index.html']:'page_home',
    [ROOT+'this-week.html']:'page_this_week',
    [ROOT+'results.html']:'page_results',
    [ROOT+'schedule.html']:'page_schedule',
    [ROOT+'methodology.html']:'page_methodology',
    [ROOT+'local-racing-shadow.html']:'page_research',
    [ROOT+'experience-regime.html']:'page_research',
    [ROOT+'e2e.html']:'page_research',
    [ROOT+'baba-models.html']:'page_research'
  });
  // Never count LAB, staging, admin pages, other websites or history views.
  const pathname=location.pathname;
  if(location.origin!=='https://toodataa-ai.github.io'||!Object.hasOwn(PAGES,pathname))return;
  const jstDay=()=>{
    const p=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Tokyo',year:'numeric',
      month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const get=t=>p.find(x=>x.type===t)?.value;
    return [get('year'),get('month'),get('day')].join('-');
  };
  async function init(){
    // Will remain disabled until explicitly approved & deployed.
    let settings;
    try{
      const r=await fetch(ROOT+'data/site-usage-config.json',{cache:'no-store',credentials:'omit'});
      if(!r.ok)return;
      settings=await r.json();
    }catch(_){return}
    if(settings.schema_version!==1||settings.site!=='keiba-notes'||settings.enabled!==true||
       !/^https:\/\//.test(settings.endpoint||''))return;
    const url=settings.endpoint.replace(/\/$/,'')+'/collect';
    function hit(event){
      const body=JSON.stringify({site:'keiba-notes',event});
      try{
        if(navigator.sendBeacon&&navigator.sendBeacon(url,new Blob([body],{type:'text/plain'})))return;
      }catch(_){}
      fetch(url,{method:'POST',headers:{'Content-Type':'text/plain'},body,
        mode:'cors',credentials:'omit',keepalive:true}).catch(()=>{});
    }
    hit(PAGES[pathname]);
    try{
      const key='keiba_usage_session_jst_'+jstDay();
      if(sessionStorage.getItem(key)!=='1'){
        sessionStorage.setItem(key,'1');
        hit('session_start');
      }
    }catch(_){/* Private browsing may disable sessionStorage. Do not fabricate sessions. */}
  }
  init();
})();