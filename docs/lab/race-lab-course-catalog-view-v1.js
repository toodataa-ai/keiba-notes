/* Dynamic status view of the existing 10-venue official JRA course catalog.
   A course is never marked playable solely because its official spec exists. */
(function(){'use strict';
const $=id=>document.getElementById(id);
const source='race-course-catalog-v1.json';
const enabled={
 'kyoto_turf_inner_2000':{status:'基準LAB v26',href:'race-clean-course-v1.html?trial=shuka2026&v=26'},
 'kyoto_turf_outer_1400':{status:'試走中・未承認',href:'race-lab-cross-course-v1.html?v=43'}
};
function courseId(venue,route,distance){
 if(venue.code==='tokyo'&&route.surface==='turf'&&distance===2000)return'tokyo_turf_2000';
 if(venue.code==='kyoto'&&route.surface==='turf'&&route.layout==='inner'&&distance===2000)return'kyoto_turf_inner_2000';
 if(venue.code==='kyoto'&&route.surface==='turf'&&route.layout==='outer'&&distance===1400)return'kyoto_turf_outer_1400';
 return venue.code+'_'+route.surface+'_'+route.layout+'_'+distance;
}
function label(route){return(route.surface==='turf'?'芝':'ダート')+
 (route.layout==='inner'?'内回り':route.layout==='outer'?'外回り':
 route.layout==='straight'?'直線':route.layout==='outer_to_inner'?'外→内':'');}
async function setup(){
 try{
  const response=await fetch(source,{cache:'no-store'});
  if(!response.ok)throw Error('CATALOG_HTTP_'+response.status);
  const catalog=await response.json();
  if(catalog.venues.length!==10)throw Error('JRA_VENUE_COUNT_MISMATCH');
  let count=0,ready=0;
  const root=$('catalogGroups');root.replaceChildren();
  for(const venue of catalog.venues){
   const section=document.createElement('section');section.className='venue';
   const title=document.createElement('h2');title.textContent=venue.name;section.appendChild(title);
   for(const route of venue.routes){
    const distances=route.distances_m||[];
    for(const distance of distances){
     count++;
     const id=courseId(venue,route,distance),item=enabled[id];
     if(item)ready++;
     const row=document.createElement('div');row.className='course-row';
     const main=document.createElement('div');main.className='details';
     const name=document.createElement(item?'a':'span');
     name.textContent=label(route)+' '+distance+'m';
     if(item)name.href=item.href;
     main.appendChild(name);
     const tag=document.createElement('em');
     tag.textContent=item?item.status:id==='tokyo_turf_2000'?'原SVG待ち':'仕様登録・未検証';
     row.append(main,tag);section.appendChild(row);
    }
   }root.appendChild(section);
  }
  $('venuesTotal').textContent=String(catalog.venues.length);
  $('routesTotal').textContent=String(count);
  $('runningTotal').textContent=String(ready);
 }catch(err){$('catalogGroups').textContent='公式コース台帳の読み込みに失敗: '+String(err)}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);else setup();
})();