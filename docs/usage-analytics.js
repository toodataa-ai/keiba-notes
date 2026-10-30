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
  const DAY_MS=86400000;
  const NS='http://www.w3.org/2000/svg';
  function utcDay(day){
    if(!/^\d{4}-\d{2}-\d{2}$/.test(day))throw Error('履歴の日付が不正です');
    const value=Date.parse(day+'T00:00:00Z');
    if(!Number.isFinite(value)||new Date(value).toISOString().slice(0,10)!==day)
      throw Error('無効な日付です');
    return value;
  }
  function svgNode(tag,attrs={},label){
    const el=document.createElementNS(NS,tag);
    for(const [name,value] of Object.entries(attrs))el.setAttribute(name,String(value));
    if(label!==undefined)el.textContent=label;
    return el;
  }
  function renderHistory(rows,days,endDay){
    const table=byId('historyRows'),chart=byId('chart'),detail=byId('chartDetail');
    table.replaceChildren();chart.replaceChildren();
    detail.textContent='点をタップすると日付とPVを確認できます。';
    const end=utcDay(endDay),start=end-(days-1)*DAY_MS;
    const seen=new Set();
    const entries=rows.map(row=>{
      const day=utcDay(row.day);
      if(day<start||day>end||seen.has(day))throw Error('履歴に期間外または重複した日付があります');
      seen.add(day);
      return {day:row.day,time:day,pv:pageViews(row.counts),sessions:sum(row.counts,['session_start'])};
    }).sort((a,b)=>a.time-b.time);
    if(!entries.length){
      const tr=make('tr');
      const td=make('td','','この期間には、記録された日別データがありません。');
      td.colSpan=3;tr.append(td);table.append(tr);
      chart.append(make('p','trend-empty','この期間はまだ計測データがありません。計測開始前を0件とは扱いません。'));
      detail.textContent='計測が開始されると、日別の変化を折れ線で表示します。';
      return;
    }
    for(const item of [...entries].reverse()){
      const tr=make('tr');
      for(const cell of [item.day,fmt(item.pv),fmt(item.sessions)])
        tr.append(make('td','',cell));
      table.append(tr);
    }
    // Dates use calendar spacing. Missing dates remain blank, not zero.
    // Draw line segments only between consecutive days with actual records.
    const width=860,height=286,left=56,right=22,top=24,bottom=50;
    const plotWidth=width-left-right,plotHeight=height-top-bottom;
    const high=Math.max(...entries.map(r=>r.pv));
    const step=Math.max(1,Math.ceil(Math.max(1,high)/4));
    const ceiling=step*4;
    const xFor=time=>left+(days===1?1:(time-start)/((days-1)*DAY_MS))*plotWidth;
    const yFor=pv=>top+plotHeight*(1-pv/ceiling);
    const svg=svgNode('svg',{
      viewBox:'0 0 '+width+' '+height,role:'img',class:'trend-chart-svg',
      'aria-label':'日付を横軸、PVを縦軸にした閲覧数の推移。実測日だけを点で示し、未計測の区間は線を引きません。'
    });
    const title=svgNode('title',{},'日別PVの折れ線グラフ');
    const description=svgNode('desc',{},'横軸は日本時間の日付、縦軸は閲覧回数です。未計測日を0回としていません。詳細は表にも掲載しています。');
    svg.append(title,description);
    for(let i=0;i<=4;i++){
      const value=step*i,y=yFor(value);
      svg.append(svgNode('line',{x1:left,x2:width-right,y1:y,y2:y,class:'trend-grid'}));
      svg.append(svgNode('text',{x:left-11,y:y+4,class:'trend-y-label','text-anchor':'end'},String(value)));
    }
    for(let i=0;i<=4;i++){
      const day=start+Math.round((days-1)*i/4)*DAY_MS;
      const label=new Date(day).toISOString().slice(5,10).replace('-','/');
      const x=xFor(day);
      svg.append(svgNode('line',{x1:x,x2:x,y1:top,y2:top+plotHeight,class:'trend-vertical'}));
      svg.append(svgNode('text',{x,y:height-20,class:'trend-x-label','text-anchor':'middle'},label));
    }
    svg.append(svgNode('text',{x:12,y:13,class:'trend-axis-title'},'PV'));
    svg.append(svgNode('text',{x:width-right,y:height-4,class:'trend-axis-title','text-anchor':'end'},'日付（JST）'));
    let segment=[];
    const drawSegment=()=>{
      if(segment.length>=2){
        svg.append(svgNode('polyline',{
          points:segment.map(v=>xFor(v.time).toFixed(2)+','+yFor(v.pv).toFixed(2)).join(' '),
          class:'trend-line'
        }));
      }
      segment=[];
    };
    for(const item of entries){
      if(segment.length && item.time-segment[segment.length-1].time!==DAY_MS)drawSegment();
      segment.push(item);
    }
    drawSegment();
    for(const item of entries){
      const circle=svgNode('circle',{
        cx:xFor(item.time).toFixed(2),cy:yFor(item.pv).toFixed(2),
        r:6,class:'trend-point',tabindex:0,role:'button',
        'aria-label':item.day+'：'+fmt(item.pv)+' PV、セッション目安 '+fmt(item.sessions)
      });
      circle.append(svgNode('title',{},item.day+'：'+fmt(item.pv)+' PV'));
      const select=()=>{
        detail.textContent=item.day+'：'+fmt(item.pv)+' PV／セッション目安 '+fmt(item.sessions);
        for(const node of svg.querySelectorAll('.trend-point'))node.classList.remove('selected');
        circle.classList.add('selected');
      };
      circle.addEventListener('click',select);
      circle.addEventListener('focus',select);
      circle.addEventListener('keydown',e=>{
        if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}
      });
      svg.append(circle);
    }
    chart.append(svg);
    if(entries.length===1)detail.textContent='現在は1日分の記録です。点を表示しています。2日以上蓄積すると折れ線になります。';
    else if(entries.some((e,i)=>i>0&&e.time-entries[i-1].time!==DAY_MS))
      detail.textContent='未計測の日付は線をつながず、空白として表示しています。点をタップすると日別の数値を確認できます。';
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
        renderHistory(data.rows,Number(days),data.day_jst);
        byId('historyStatus').textContent=data.recorded_days+'日分の実測記録を表示。記録開始前の日付は復元できません。';
      }catch(e){byId('historyStatus').textContent='履歴データを検証できません：'+e.message}
    }else byId('historyStatus').textContent='履歴取得失敗：'+history.reason?.message;
    byId('refresh').disabled=false;
  }
  // Staging-only demo. Never send synthetic numbers to the backend.
  // A visible warning makes sample data unambiguous and it is never persisted.
  const example=byId('previewExample');
  const backToActual=byId('returnLive');
  const sampleFlag=byId('sampleFlag');
  const exampleOff=()=>{
    if(!example)return;
    example.hidden=false;
    backToActual.hidden=true;
    sampleFlag.hidden=true;
  };
  if(example){
    example.addEventListener('click',()=>{
      ++requestSerial;
      byId('refresh').disabled=false;
      const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',
        year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
      const get=t=>parts.find(p=>p.type===t)?.value;
      const today=[get('year'),get('month'),get('day')].join('-');
      const end=utcDay(today);
      const hypothetical=[8,14,11,null,23,19,27];
      const rows=hypothetical.map((pv,i)=>{
        if(pv===null)return null;
        const day=new Date(end-(6-i)*DAY_MS).toISOString().slice(0,10);
        const counts=Object.fromEntries(EVENT_NAMES.map(name=>[name,0]));
        counts.page_home=pv;
        counts.session_start=Math.max(1,Math.round(pv/3));
        return {day,counts};
      }).filter(Boolean);
      byId('period').value='7';
      renderHistory(rows,7,today);
      example.hidden=true;
      backToActual.hidden=false;
      sampleFlag.hidden=false;
      byId('historyStatus').textContent='表示サンプル：仮の7日間のデータ（実際のアクセス数ではありません）';
      byId('chartDetail').textContent='表示サンプルです。点をタップすると仮の数値を確認できます。欠測日の線は途切れています。';
    });
    backToActual.addEventListener('click',()=>{exampleOff();refresh();});
  }
  byId('period').addEventListener('change',()=>{exampleOff();refresh();});
  byId('refresh').addEventListener('click',refresh);
  (async()=>{
    try{
      cfg=await getJson('usage-analytics-config.json');
      if(cfg.schema_version!==1||cfg.site!=='keiba-notes')throw Error('接続設定が不正です');
    }catch(e){status('設定を読み込めません：'+e.message,true)}
    await refresh();
  })();
})();