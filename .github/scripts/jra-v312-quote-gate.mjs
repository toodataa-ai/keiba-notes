// v3.12: exact-selection odds coverage gate. No network scraping and no invented prices.
// The collector must supply a source snapshot, observation time and SHA for each quote.
// This gate operates before the immutable proof and never edits STEP1 or prior predictions.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {TYPES, expandStrategy, ticketKey, oddsFloor} from './jra-strategy-engine-v39.mjs';
const goodTime=s=>typeof s==='string'&&Number.isFinite(Date.parse(s));
export function reconcileQuotes(input){
 if(!Array.isArray(input?.strategies)||!Array.isArray(input?.market_quotes))
  throw Error('strategies and market_quotes must be arrays');
 const requested=new Map(), quotes=new Map(), duplicates=[],invalid=[];
 for(const strategy of input.strategies){
  if(!TYPES.includes(strategy.type))throw Error('Unsupported strategy type');
  for(const ticket of expandStrategy(strategy.type,strategy.strategy_kind,strategy.definition)){
   const key=ticketKey(ticket.type,ticket.selection);
   if(!requested.has(key))requested.set(key,{key,type:ticket.type,selection:ticket.selection,origins:[]});
   requested.get(key).origins.push({strategy_id:strategy.strategy_id,mode:strategy.strategy_kind});
  }
 }
 for(const q of input.market_quotes){
  let key;
  try{key=ticketKey(q.type,q.selection)}catch(e){invalid.push({selection:q.selection,error:e.message});continue;}
  if(quotes.has(key)){duplicates.push(key);continue;}
  const issue=[];
  if(q.market_selection_id!==key)issue.push('selection_id_mismatch');
  if(q.quote_verified!==true||oddsFloor(q.market_odds)===null)issue.push('invalid_or_unverified_odds');
  if(!goodTime(q.observed_at)||!goodTime(input.race_context?.start_at)||
    Date.parse(q.observed_at)>=Date.parse(input.race_context.start_at))issue.push('not_prestart');
  if(typeof q.source_url!=='string'||!q.source_url.startsWith('https://'))issue.push('source_url_missing');
  if(!/^[0-9a-f]{64}$/i.test(q.source_capture_sha256||''))issue.push('capture_sha_missing');
  if(typeof q.source_capture_path!=='string'||
    !q.source_capture_path.startsWith('e2e_validation/quote-evidence/')||
    q.source_capture_path.includes('..'))issue.push('capture_path_missing');
  quotes.set(key,{q,issue});
 }
 const missing=[],perType={};
 for(const type of TYPES)perType[type]={generated:0,verified:0,missing:0,invalid:0};
 for(const row of requested.values()){
  const value=quotes.get(row.key);
  const reason=!value?'not_collected':value.issue.length?value.issue.join(','):'';
  perType[row.type].generated++;
  if(!reason)perType[row.type].verified++;
  else{perType[row.type].missing++;if(value)perType[row.type].invalid++;
   missing.push({...row,reason});
  }
 }
 const unused=[...quotes.keys()].filter(k=>!requested.has(k));
 return {schema_version:1,policy:'v3.12-exact-line-coverage',race_id:input.race_id,
   generated_unique:requested.size,verified:[...Object.values(perType)].reduce((s,x)=>s+x.verified,0),
   missing_count:missing.length,quote_count:input.market_quotes.length,
   type_coverage:perType,missing,duplicates,invalid,unused,
   complete:missing.length===0&&duplicates.length===0&&invalid.length===0,
   action:'Collect actual exact odds for every generated ticket from the live market BEFORE freeze; preserve each quote source capture and do not invent missing prices.'};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const file=process.argv[2],output=process.argv[3];
 if(!file||!output){console.error('Usage: node jra-v312-quote-gate.mjs input.json audit.json');process.exit(2);}
 const audit=reconcileQuotes(JSON.parse(fs.readFileSync(file,'utf8')));
 fs.mkdirSync(output.split('/').slice(0,-1).join('/')||'.',{recursive:true});
 fs.writeFileSync(output,JSON.stringify(audit,null,2)+'\n');
 console.log('V312 QUOTE COVERAGE',JSON.stringify({generated:audit.generated_unique,verified:audit.verified,missing:audit.missing_count,by_type:audit.type_coverage}));
 if(!audit.complete){console.error('BLOCKER: exact market prices unverified; fix items in '+output+' before proof');process.exit(1);}
}