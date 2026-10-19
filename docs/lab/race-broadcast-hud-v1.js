/* Reusable LAB race HUD. Never reads official outcomes or modifies simulation physics. */
(function(root){'use strict';
 const METRES_PER_LENGTH=2.4; // approximate, never an official JRA margin
 function clock(seconds){
  if(!Number.isFinite(seconds)||seconds<0)return '—';
  const ticks=Math.round(seconds*10);
  return Math.floor(ticks/600)+'.'+String(Math.floor(ticks%600/10)).padStart(2,'0')+'.'+ticks%10;
 }
 function finishers(state){
  return state.horses.filter(h=>Number.isFinite(h.finishTime))
   .sort((a,b)=>a.finishTime-b.finishTime||a.number-b.number);
 }
 function gap(previous,horse){
  if(!previous)return {seconds:0,lengths:0};
  const seconds=Math.max(0,horse.finishTime-previous.finishTime);
  const speed=((Number(previous.runoffSpeed)||16)+(Number(horse.runoffSpeed)||16))/2;
  return {seconds,lengths:seconds*speed/METRES_PER_LENGTH};
 }
 function render(state,e,cache){
  // Stop the broadcast stopwatch on the virtual WINNER crossing,
  // while keeping every trailing horse finishTime available for results.
  e.clock.textContent=clock(state.firstFinishTime===null?state.t:state.firstFinishTime);
  e.split.textContent=state.splitTime===null?'—':clock(state.splitTime);
  e.splitLabel.textContent=state.splitDistanceM+'m 通過';
  const placed=finishers(state);
  e.banner.hidden=!placed.length;
  if(placed.length){
   e.heading.textContent=placed.length<3?'ゴール速報':'上位3着確定（仮想）';
   e.podium.textContent=placed.slice(0,3).map((h,i)=>(i+1)+'着 '+h.number+'番 '+h.name).join('　');
  }else e.podium.textContent='';
  const complete=state.allCrossedAt!==null&&placed.length===state.horses.length;
  e.results.hidden=!complete;
  if(!complete){cache.signature='';e.rows.replaceChildren();return;}
  const signature=placed.map(h=>h.number+':'+h.finishTime).join('|');
  if(cache.signature===signature)return;
  cache.signature=signature;
  const doc=e.rows.ownerDocument,fragment=doc.createDocumentFragment();
  for(let i=0;i<placed.length;i++){
   const h=placed[i],g=gap(placed[i-1],h);
   const values=[i+1,h.number+'番',h.name,clock(h.finishTime),
    i===0?'—':'約'+g.lengths.toFixed(1)+'馬身 / +'+g.seconds.toFixed(2)+'秒',
    i===0?'—':'+'+(h.finishTime-placed[0].finishTime).toFixed(2)+'秒'];
   const row=doc.createElement('tr');
   for(const value of values){const cell=doc.createElement('td');cell.textContent=String(value);row.appendChild(cell)}
   fragment.appendChild(row);
  }
  e.rows.replaceChildren(fragment);
 }
 root.RaceBroadcastHud=Object.freeze({clock,finishers,gap,render,METRES_PER_LENGTH});
})(typeof window!=='undefined'?window:globalThis);
