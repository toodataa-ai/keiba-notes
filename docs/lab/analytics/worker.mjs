// Dedicated anonymous keiba-notes metrics Worker: DO NOT bind to the family-events D1.
// Preserve only JST day, fixed event type and aggregate count.
const EVENTS=Object.freeze(['page_home','page_this_week','page_results','page_schedule',
  'page_methodology','page_research','page_other','session_start']);
const EVENT_SET=new Set(EVENTS);
const ORIGIN='https://toodataa-ai.github.io';
const json=(data,status,origin)=>new Response(JSON.stringify(data),{status,headers:{
  'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',
  'X-Content-Type-Options':'nosniff','Vary':'Origin',
  ...(origin===ORIGIN?{'Access-Control-Allow-Origin':ORIGIN}:{})
}});
function todayJst(now=new Date()){
  const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
  const get=t=>parts.find(x=>x.type===t)?.value;
  return [get('year'),get('month'),get('day')].join('-');
}
function dateFromToday(day,distance){
  const d=new Date(day+'T00:00:00Z');d.setUTCDate(d.getUTCDate()-distance);
  return d.toISOString().slice(0,10);
}
export default {async fetch(request,env){
  const url=new URL(request.url),origin=request.headers.get('Origin');
  if(request.method==='OPTIONS'&&url.pathname==='/collect'){
    if(origin!==ORIGIN)return json({error:'forbidden'},403,origin);
    return new Response(null,{status:204,headers:{'Access-Control-Allow-Origin':ORIGIN,
      'Access-Control-Allow-Methods':'POST,OPTIONS','Access-Control-Allow-Headers':'Content-Type',
      'Access-Control-Max-Age':'600','Vary':'Origin'}});
  }
  if(!env.DB)return json({error:'storage_unavailable'},503,origin);
  if(url.pathname==='/collect'&&request.method==='POST'){
    if(origin!==ORIGIN)return json({error:'forbidden'},403,origin);
    if(!['text/plain','application/json'].includes((request.headers.get('Content-Type')||'').split(';')[0].trim()))
      return json({error:'unsupported_media_type'},415,origin);
    if(Number(request.headers.get('Content-Length')||0)>256)return json({error:'too_large'},413,origin);
    let payload;
    try{const body=await request.text();if(body.length>256)throw Error('too_large');payload=JSON.parse(body);}
    catch(_){return json({error:'invalid_event'},400,origin);}
    if(!payload||typeof payload!=='object'||Array.isArray(payload)||
       Object.keys(payload).length!==2||payload.site!=='keiba-notes'||!EVENT_SET.has(payload.event))
      return json({error:'invalid_event'},400,origin);
    try{
      await env.DB.prepare('INSERT INTO event_counts (day,event,count) VALUES (?1,?2,1) '+
        'ON CONFLICT(day,event) DO UPDATE SET count=count+1').bind(todayJst(),payload.event).run();
      return json({ok:true},200,origin);
    }catch(_){return json({error:'collection_failed'},503,origin);}
  }
  if(url.pathname==='/stats'&&request.method==='GET'){
    if(url.search)return json({error:'unexpected_query'},400,origin);
    try{
      const day=todayJst();
      const result=await env.DB.prepare('SELECT event,SUM(count) AS total,'+
        'SUM(CASE WHEN day=?1 THEN count ELSE 0 END) AS today FROM event_counts GROUP BY event').bind(day).all();
      const totals=Object.fromEntries(EVENTS.map(e=>[e,0]));
      const today=Object.fromEntries(EVENTS.map(e=>[e,0]));
      for(const x of result.results||[]){
        if(!EVENT_SET.has(x.event))continue;
        if(!Number.isSafeInteger(Number(x.total))||Number(x.total)<0||
           !Number.isSafeInteger(Number(x.today))||Number(x.today)<0)throw Error('invalid_counts');
        totals[x.event]=Number(x.total);today[x.event]=Number(x.today);
      }
      return json({schema_version:1,site:'keiba-notes',day_jst:day,totals,today},200,origin);
    }catch(_){return json({error:'stats_unavailable'},503,origin);}
  }
  if(url.pathname==='/history'&&request.method==='GET'){
    const range=url.searchParams.get('days')||'30';
    if(!['7','30','90','365'].includes(range)||
      url.searchParams.size>(url.searchParams.has('days')?1:0))
      return json({error:'invalid_range'},400,origin);
    try{
      const end=todayJst(),start=dateFromToday(end,Number(range)-1);
      const result=await env.DB.prepare('SELECT day,event,count FROM event_counts '+
        'WHERE day>=?1 AND day<=?2 ORDER BY day DESC,event').bind(start,end).all();
      const days=new Map();
      for(const x of result.results||[]){
        if(!/^\d{4}-\d{2}-\d{2}$/.test(x.day)||x.day<start||x.day>end||
          !EVENT_SET.has(x.event)||!Number.isSafeInteger(Number(x.count))||Number(x.count)<0)continue;
        if(!days.has(x.day))days.set(x.day,Object.fromEntries(EVENTS.map(e=>[e,0])));
        days.get(x.day)[x.event]+=Number(x.count);
      }
      const rows=[...days].sort((a,b)=>b[0].localeCompare(a[0])).map(([day,counts])=>({day,counts}));
      return json({schema_version:1,site:'keiba-notes',day_jst:end,days:Number(range),
        recorded_days:rows.length,rows,note:'記録がある日のみ表示。未計測日は0としません。人数は識別しません。'},200,origin);
    }catch(_){return json({error:'history_unavailable'},503,origin);}
  }
  return json({error:'not_found'},404,origin);
}};
