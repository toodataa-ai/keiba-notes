// JRA v3.9 purchase-only strategy engine. No STEP1 data is modified.
export const TYPES=['単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単'];
export const MODES={
  単勝:['single','multiple_singles'],
  複勝:['single','multiple_singles'],
  枠連:['single','box','key_wheel','formation'],
  馬連:['single','box','key_wheel','formation'],
  馬単:['single','box','key_wheel_first','key_wheel_second','key_wheel_multi','formation'],
  ワイド:['single','box','key_wheel','formation'],
  三連複:['single','box','one_key_wheel','two_key_wheel','formation'],
  三連単:['single','box','formation','one_key_fixed','two_key_fixed','one_key_multi','two_key_multi']
};
export const MIXED_MODES=['win_place_support']; // Single & place, two independently priced lines.
const arity={単勝:1,複勝:1,枠連:2,馬連:2,馬単:2,ワイド:2,三連複:3,三連単:3};
const unordered=new Set(['枠連','馬連','ワイド','三連複']);
const uniq=a=>[...new Set(a)];
const validHorse=n=>Number.isInteger(n)&&n>0;
const isArr=a=>Array.isArray(a)&&a.length>0&&a.every(validHorse);
const num=n=>typeof n==='number'&&Number.isFinite(n);
export function normalize(type,selection){
 if(!TYPES.includes(type)||!Array.isArray(selection)||selection.length!==arity[type]||!selection.every(validHorse))throw Error('invalid ticket type or selection');
 if(type!=='枠連'&&new Set(selection).size!==selection.length)throw Error('duplicate horse');
 if(type==='枠連'&&selection.some(x=>x>8))throw Error('invalid frame number');
 return unordered.has(type)?[...selection].sort((a,b)=>a-b):[...selection];
}
export const ticketKey=(type,selection)=>type+':'+JSON.stringify(normalize(type,selection));
function permute(xs){
 if(xs.length===0)return [[]];
 return xs.flatMap((x,i)=>permute([...xs.slice(0,i),...xs.slice(i+1)]).map(ys=>[x,...ys]));
}
function combinations(xs,n){
 if(n===0)return [[]];if(xs.length<n)return [];
 return xs.flatMap((x,i)=>combinations(xs.slice(i+1),n-1).map(ys=>[x,...ys]));
}
const append=(raw,arr)=>raw.push(arr);
export function expandStrategy(type,kind,definition={}){
 const d=definition,raw=[];
 if(kind==='win_place_support'&&type==='mixed'){
   if(!validHorse(d.horse))throw Error('support horse missing');
   return [{type:'単勝',selection:[d.horse]},{type:'複勝',selection:[d.horse]}];
 }
 if(!TYPES.includes(type)||!MODES[type].includes(kind))throw Error('unsupported ticket strategy');
 if(kind==='single')append(raw,d.selection);
 if(kind==='multiple_singles')for(const h of d.horses||[])append(raw,[h]);
 if(kind==='box'){
   if(!isArr(d.horses))throw Error('box horses/frames missing');
   const n=arity[type];
   // JRA frame-box NEVER includes same-frame tickets.
   for(const pair of combinations(uniq(d.horses),n))
     for(const order of unordered.has(type)?[pair]:permute(pair))append(raw,order);
 }
 if(kind==='formation'){
   const slots=d.slots||[];
   if(slots.length!==arity[type]||slots.some(x=>!isArr(x)))throw Error('invalid formation slots');
   let products=[[]];
   for(const slot of slots)products=products.flatMap(x=>slot.map(y=>[...x,y]));
   for(const p of products)append(raw,p);
 }
 if(kind==='key_wheel'){
   if(!['馬連','ワイド','枠連'].includes(type))throw Error('wheel not allowed');
   if(!validHorse(d.key)||!isArr(d.partners))throw Error('invalid wheel');
   for(const h of d.partners)append(raw,[d.key,h]);
 }
 if(['key_wheel_first','key_wheel_second','key_wheel_multi'].includes(kind)){
   if(type!=='馬単'||!validHorse(d.key)||!isArr(d.partners))throw Error('invalid exacta wheel');
   for(const h of d.partners){
     if(kind!=='key_wheel_second')append(raw,[d.key,h]);
     if(kind!=='key_wheel_first')append(raw,[h,d.key]);
   }
 }
 if(['one_key_wheel','two_key_wheel'].includes(kind)){
   if(type!=='三連複'||!isArr(d.partners))throw Error('invalid trio key wheel');
   if(kind==='one_key_wheel'){
     if(!validHorse(d.key))throw Error('trio key missing');
     for(const pair of combinations(uniq(d.partners),2))append(raw,[d.key,...pair]);
   }else{
     if(!isArr(d.axes)||d.axes.length!==2||d.axes[0]===d.axes[1])throw Error('invalid trio axes');
     for(const h of d.partners)append(raw,[...d.axes,h]);
   }
 }
 if(['one_key_fixed','one_key_multi','two_key_fixed','two_key_multi'].includes(kind)){
   if(type!=='三連単'||!isArr(d.partners))throw Error('invalid trifecta wheel');
   if(kind.startsWith('one_key')){
     if(!validHorse(d.key))throw Error('invalid one-key horse');
     if(kind==='one_key_fixed'&&![1,2,3].includes(d.position))throw Error('invalid fixed position');
     for(const pair of combinations(uniq(d.partners),2)){
       for(const order of permute([d.key,...pair])){
         if(kind==='one_key_multi'||order[d.position-1]===d.key)append(raw,order);
       }
     }
   }else{
     if(!isArr(d.axes)||d.axes.length!==2||d.axes[0]===d.axes[1])throw Error('invalid trifecta axes');
     if(kind==='two_key_fixed'&&(!isArr(d.positions)||d.positions.length!==2||
       d.positions[0]===d.positions[1]||d.positions.some(x=>x<1||x>3)))throw Error('invalid fixed axis positions');
     for(const h of d.partners){
       if(kind==='two_key_multi')for(const p of permute([...d.axes,h]))append(raw,p);
       else{
         const sel=Array(3).fill(0);sel[d.positions[0]-1]=d.axes[0];sel[d.positions[1]-1]=d.axes[1];
         sel[sel.indexOf(0)]=h;append(raw,sel);
       }
     }
   }
 }
 const result=[],seen=new Set();
 for(const rawLine of raw){
   // Repeated horses in formations are invalid combinations rather than valid tickets.
   if(!Array.isArray(rawLine)||rawLine.some(v=>!validHorse(v)))throw Error('invalid expanded selection');
   if(type!=='枠連'&&new Set(rawLine).size!==rawLine.length)continue;
   const normalized=normalize(type,rawLine),k=ticketKey(type,normalized);
   if(!seen.has(k)){seen.add(k);result.push({type,selection:normalized});}
 }
 if(!result.length)throw Error('zero legal combinations');
 return result.sort((a,b)=>ticketKey(a.type,a.selection).localeCompare(ticketKey(b.type,b.selection),'en'));
}
export function matches(ticket,finish,frameMap,race){
 const type=ticket.type,s=normalize(type,ticket.selection),[a,b,c]=finish;
 const sorted=(xs)=>[...xs].sort((x,y)=>x-y);
 if(type==='単勝')return s[0]===a;
 if(type==='複勝'){
   const paid=race?.place_paid_positions;
   const n=Number.isInteger(paid)?paid:(race?.sale_field_size>=8?3:2);
   return finish.slice(0,n).includes(s[0]);
 }
 if(type==='枠連'){
   const fa=frameMap?.[String(a)],fb=frameMap?.[String(b)];
   if(!validHorse(fa)||!validHorse(fb))throw Error('frame_map unavailable');
   return JSON.stringify(s)===JSON.stringify(sorted([fa,fb]));
 }
 if(type==='馬連')return JSON.stringify(s)===JSON.stringify(sorted([a,b]));
 if(type==='馬単')return a===s[0]&&b===s[1];
 if(type==='ワイド')return s.every(v=>[a,b,c].includes(v));
 if(type==='三連複')return JSON.stringify(s)===JSON.stringify(sorted([a,b,c]));
 if(type==='三連単')return JSON.stringify(s)===JSON.stringify([a,b,c]);
 throw Error('unknown event');
}
export const oddsFloor=o=>num(o)&&o>1?o:Array.isArray(o)&&o.length===2&&o.every(x=>num(x)&&x>1)&&o[0]<=o[1]?o[0]:null;
export function evaluateStrategy(lines,scenarioOutcomes,frameMap,race){
 if(!Array.isArray(lines)||!lines.length)throw Error('no lines');
 const keys=new Set(),priceOk=lines.every(l=>{
   const k=ticketKey(l.type,l.selection);
   if(keys.has(k))throw Error('duplicate line');
   keys.add(k);
   return Number.isInteger(l.stake_yen)&&l.stake_yen>=100&&l.stake_yen%100===0&&oddsFloor(l.market_odds)!==null;
 });
 const stake=lines.reduce((s,l)=>s+l.stake_yen,0);
 if(!priceOk)return {total_stake_yen:stake,hit_probability_scenarios:null,expected_payout_yen_scenarios:null,roi_scenarios:null,full_loss_probability_scenarios:null,loss_probability_scenarios:null};
 const hit={},payout={},roi={},full={},loss={};
 for(const [scenario,outcomes] of Object.entries(scenarioOutcomes||{})){
   if(!Array.isArray(outcomes)||!outcomes.length)throw Error('missing scenario outcomes '+scenario);
   let h=0,ep=0,fl=0,netLoss=0,sum=0;const seen=new Set();
   for(const o of outcomes){
     if(!Array.isArray(o.finish)||o.finish.length!==3||new Set(o.finish).size!==3||
       !o.finish.every(validHorse)||!num(o.probability)||o.probability<0||o.probability>1)throw Error('malformed joint outcome');
     const id=JSON.stringify(o.finish);
     if(seen.has(id))throw Error('duplicate joint outcome');seen.add(id);
     sum+=o.probability;
     let pays=0;
     for(const line of lines){
       if(matches(line,o.finish,frameMap,race))pays+=line.stake_yen*oddsFloor(line.market_odds);
     }
     ep+=o.probability*pays;
     if(pays>0)h+=o.probability;
     else fl+=o.probability;
     if(pays<stake)netLoss+=o.probability;
   }
   if(Math.abs(sum-1)>0.00001)throw Error('joint outcomes are not normalized');
   hit[scenario]=h;payout[scenario]=ep;roi[scenario]=ep/stake;
   full[scenario]=fl;loss[scenario]=netLoss;
 }
 return {total_stake_yen:stake,hit_probability_scenarios:hit,expected_payout_yen_scenarios:payout,roi_scenarios:roi,
   full_loss_probability_scenarios:full,loss_probability_scenarios:loss};
}
