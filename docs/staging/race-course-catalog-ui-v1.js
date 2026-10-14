/* Read-only staging registry browser: no connections to predictions or bets. */
(()=>{'use strict';
 const by=id=>document.getElementById(id);
 const el=(tag,text)=>{const n=document.createElement(tag);n.textContent=String(text);return n};
 const escStatus=x=>x==='stage_experiment'?'既存試作あり／再検品待ち':'座標・発走位置未登録';
 const human=x=>({inner:'内回り',outer:'外回り',straight:'直線',single:'通常周回',outer_to_inner:'外→内'})[x]||x;
 fetch('race-course-catalog-v1.json',{cache:'no-store'})
 .then(r=>{if(!r.ok)throw Error('台帳を取得できませんでした');return r.json()})
 .then(data=>{
  const catalog=JraCourseCatalog.create(data),stats=catalog.stats,totals=by('totals');
  totals.replaceChildren();
  for(const [name,value] of [['競馬場',stats.venues],['基本走路',stats.families],
    ['芝A/B/C/D・ダートの設定',stats.rail_variants],['距離別テンプレート',stats.templates],
    ['座標検品・承認済み',stats.geometry_approved]]){
   const c=el('div',name);c.className='metric';const strong=el('strong',value);
   c.prepend(strong);totals.appendChild(c);
  }
  for(const v of data.venues){const option=el('option',v.name);option.value=v.code;
   by('venueFilter').appendChild(option)}
  const grouped=[];
  for(const v of data.venues)for(const r of v.routes)for(const rail of Object.keys(r.variants)){
   const items=catalog.list({venue:v.code,surface:r.surface,layout:r.layout,rail:rail==='dirt'?null:rail})
    .filter(t=>t.rail===rail);
   grouped.push({venue:v,route:r,rail,items,details:r.variants[rail]});
  }
  const render=()=>{
   const venue=by('venueFilter').value,surface=by('surfaceFilter').value,layout=by('layoutFilter').value;
   const subset=grouped.filter(g=>(venue==='all'||g.venue.code===venue)&&
     (surface==='all'||g.route.surface===surface)&&(layout==='all'||g.route.layout===layout));
   const body=by('courseRows');body.replaceChildren();
   const registered=subset.reduce((n,g)=>n+g.items.length,0);
   by('filterSummary').textContent=subset.length+'種類の走路設定／'+registered+'件の距離別型が該当';
   if(!subset.length){const tr=document.createElement('tr'),td=el('td','一致する型がありません');
     td.colSpan=5;tr.appendChild(td);body.appendChild(tr);return}
   for(const g of subset){
    const row=document.createElement('tr'),r=g.route,t=g.details;
    const statuses=g.items.filter(i=>i.stage_experiment_id).map(i=>i.distance_m+'m（既存試作）');
    for(const value of [
     g.venue.name+' '+(r.surface==='turf'?'芝':'ダート')+' '+human(r.layout),
     g.rail==='dirt'?'—':g.rail,
     r.distances_m.join('・'),
     (t.lap_m??'—')+' / '+(t.straight_m??'—'),
     (statuses.length?statuses.join('、')+'。':'')+escStatus(statuses.length?'stage_experiment':'geometry_untraced')
    ])row.appendChild(el('td',value));
    row.lastChild.className='status';
    body.appendChild(row);
   }
  };
  for(const id of ['venueFilter','surfaceFilter','layoutFilter'])by(id).addEventListener('change',render);
  by('venueFilter').value='kyoto';render();
 })
 .catch(err=>{by('courseRows').replaceChildren(el('tr',''));
  by('filterSummary').textContent='読み込みに失敗しました: '+err.message});
})();