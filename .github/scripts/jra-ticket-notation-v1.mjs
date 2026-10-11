// Human-readable JRA betting notation. Presentation ONLY.
// "－" joins unordered (quinella/trio/frames/wide); "→" joins ordered
// (exacta/trifecta). A group list separated with "・" is a set, NOT a ticket.
const UNORDERED=new Set(['枠連','馬連','ワイド','三連複']);
const ORDERED=new Set(['馬単','三連単']);
const allowed=new Set(['単勝','複勝',...UNORDERED,...ORDERED]);
const requireValue=(ok,msg)=>{if(!ok)throw Error('JRA_NOTATION_BLOCKER: '+msg)};
const isHorse=n=>Number.isInteger(n)&&n>=1&&n<=18;
const validate=a=>{requireValue(Array.isArray(a)&&a.length>0&&a.every(isHorse),'missing/invalid number list');return a};
const sort=xs=>[...xs].sort((a,b)=>a-b);
const dots=xs=>sort(validate(xs)).join('・');
const list=xs=>'（'+dots(xs)+'）';
function oneTicket(type,sel){
 validate(sel);
 if(type==='単勝'||type==='複勝'){
  requireValue(sel.length===1,'single selection arity');
  return String(sel[0]);
 }
 if(UNORDERED.has(type)){
  requireValue(sel.length===(type==='三連複'?3:2),'unordered arity');
  return sort(sel).join('－');
 }
 if(ORDERED.has(type)){
  requireValue(sel.length===(type==='三連単'?3:2),'ordered arity');
  return sel.join('→');
 }
 throw Error('JRA_NOTATION_BLOCKER: unsupported ticket type '+type);
}
export function formatPurchaseCommand(c){
 const type=c?.type,method=c?.method,d=c?.definition||{};
 if(method==='pass')return c?.jra_input||'見送り';
 requireValue(allowed.has(type),'unsupported ticket type');
 if(method==='single')return oneTicket(type,d.selection);
 if(method==='box'){
   validate(d.horses);
   requireValue(d.horses.length>=(type==='三連複'||type==='三連単'?3:2),'BOX too short');
   return dots(d.horses)+' BOX';
 }
 if(method==='formation'){
   requireValue(Array.isArray(d.slots)&&d.slots.length===(type==='三連単'||type==='三連複'?3:2),'formation arity');
   const parts=d.slots.map(xs=>list(xs));
   if(type==='単勝'||type==='複勝')throw Error('JRA_NOTATION_BLOCKER: unsupported single-horse formation');
   return parts.join(ORDERED.has(type)?'→':'－');
 }
 if(method==='key_wheel'){
   requireValue(['馬連','ワイド','枠連'].includes(type)&&isHorse(d.key),'unordered one-axis wheel');
   return d.key+'－'+list(d.partners);
 }
 if(method==='key_wheel_first'){
   requireValue(type==='馬単'&&isHorse(d.key),'exacta first-fixed wheel');
   return d.key+'→'+list(d.partners);
 }
 if(method==='key_wheel_second'){
   requireValue(type==='馬単'&&isHorse(d.key),'exacta second-fixed wheel');
   return list(d.partners)+'→'+d.key;
 }
 if(method==='key_wheel_multi'){
   requireValue(type==='馬単'&&isHorse(d.key),'exacta multi');
   return d.key+'⇄'+list(d.partners)+'（馬単マルチ）';
 }
 if(method==='one_key_wheel'){
   requireValue(type==='三連複'&&isHorse(d.key),'trio one-axis wheel');
   return d.key+'－'+list(d.partners)+'から2頭';
 }
 if(method==='two_key_wheel'){
   requireValue(type==='三連複'&&d.axes?.length===2,'trio two-axis wheel');
   return sort(validate(d.axes)).join('－')+'－'+list(d.partners)+'から1頭';
 }
 if(method==='two_key_fixed'){
   requireValue(type==='三連単'&&d.axes?.length===2&&d.positions?.length===2,'trifecta two-key fixed');
   const places=[null,null,null];
   d.positions.forEach((pos,i)=>{
     requireValue([1,2,3].includes(pos)&&!places[pos-1],'two-key distinct positions');
     places[pos-1]=String(d.axes[i]);
   });
   requireValue(places.filter(Boolean).length===2,'two-key fixed missing axes');
   places[places.findIndex(x=>x===null)]=list(d.partners);
   return places.join('→');
 }
 if(method==='two_key_multi'){
   requireValue(type==='三連単'&&d.axes?.length===2,'trifecta two-axis multi');
   return sort(validate(d.axes)).join('・')+'＋'+list(d.partners)+'から1頭（3連単全着順マルチ）';
 }
 if(method==='one_key_fixed'){
   requireValue(type==='三連単'&&[1,2,3].includes(d.position)&&isHorse(d.key),'trifecta one-axis fixed');
   const cols=[list(d.partners),list(d.partners),list(d.partners)];
   cols[d.position-1]=String(d.key);
   return cols.join('→')+'（相手は異なる2頭）';
 }
 if(method==='one_key_multi'){
   requireValue(type==='三連単'&&isHorse(d.key),'trifecta one-axis multi');
   return d.key+'＋'+list(d.partners)+'から2頭（3連単全着順マルチ）';
 }
 throw Error('JRA_NOTATION_BLOCKER: unsupported method '+method+' / '+type);
}

