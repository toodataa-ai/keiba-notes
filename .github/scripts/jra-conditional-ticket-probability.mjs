// Explicit conditional finishing distribution from a fixed PRE-RACE full-field strength vector.
// PL describes one scenario and is not a calibrated performance model.
export function normalizeFullFieldStrengths(entries){
  if(!Array.isArray(entries)||entries.length<3)throw Error('At least 3 runners required');
  const id=new Set();
  const all=entries.map(e=>{
    if(!Number.isInteger(e.horse_number)||e.horse_number<1||id.has(e.horse_number))throw Error('Invalid or duplicate horse number');
    id.add(e.horse_number);
    if(!(Number.isFinite(e.strength)&&e.strength>0))throw Error('Every runner requires finite positive strength');
    if(!Number.isInteger(e.frame_number)||e.frame_number<1||e.frame_number>8)throw Error('Frame number required');
    return {...e};
  });
  const total=all.reduce((t,e)=>t+e.strength,0);
  return all.map(e=>({...e,win_probability:e.strength/total}));
}
export function finishingTriples(fullField){
  const runners=normalizeFullFieldStrengths(fullField);
  const n=runners.length;
  const triples=[];
  for(let i=0;i<n;i++)for(let j=0;j<n;j++)for(let k=0;k<n;k++){
    if(i===j||i===k||j===k)continue;
    const a=runners[i],b=runners[j],c=runners[k];
    const probability=a.win_probability *
      (b.win_probability/(1-a.win_probability)) *
      (c.win_probability/(1-a.win_probability-b.win_probability));
    triples.push({finish:[a.horse_number,b.horse_number,c.horse_number],
      frames:[a.frame_number,b.frame_number,c.frame_number],probability});
  }
  const sum=triples.reduce((t,e)=>t+e.probability,0);
  if(Math.abs(sum-1)>1e-8)throw Error('Triple mass not normalized: '+sum);
  return triples;
}
export function ticketProbability(triples,type,selection,fieldSize){
  if(!Array.isArray(triples)||triples.length===0)throw Error('Distribution missing');
  if(!Array.isArray(selection))throw Error('selection must be an array');
  const p=e=>{const [a,b,c]=e.finish,[fa,fb]=e.frames;
    if(type==='単勝')return a===selection[0];
    if(type==='複勝')return (fieldSize>=8? [a,b,c]:fieldSize>=5?[a,b]:[a]).includes(selection[0]);
    if(type==='枠連')return (fa===selection[0]&&fb===selection[1])||(fa===selection[1]&&fb===selection[0]);
    if(type==='馬連')return (a===selection[0]&&b===selection[1])||(a===selection[1]&&b===selection[0]);
    if(type==='馬単')return a===selection[0]&&b===selection[1];
    if(type==='ワイド')return selection.every(x=>[a,b,c].includes(x));
    if(type==='三連複')return selection.every(x=>[a,b,c].includes(x));
    if(type==='三連単')return a===selection[0]&&b===selection[1]&&c===selection[2];
    throw Error('Only eight JRA local ticket types supported');
  };
  if((type==='三連単'||type==='三連複')&&selection.length!==3)throw Error('3 selections required');
  const vals=triples.reduce((sum,e)=>sum+(p(e)?e.probability:0),0);
  return Number(vals.toFixed(12));
}
export function evaluateScenario(runners,selection,type,odds){
  const dist=finishingTriples(runners);
  const probability=ticketProbability(dist,type,selection,runners.length);
  const oddsLow=Array.isArray(odds)?odds[0]:odds;
  if(!(Number.isFinite(oddsLow)&&oddsLow>1))throw Error('Verified quoted odds required');
  return {method:'Plackett–Luce / full-field conditional ranking (uncalibrated scenario)',
    probability,break_even_probability:1/oddsLow,
    expected_return_multiple:probability*oddsLow,
    scenario_only:true};
}
