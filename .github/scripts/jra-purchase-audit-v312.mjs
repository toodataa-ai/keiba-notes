// JRA v3.12: purchase-only, append-only coverage and portfolio-comparison audit.
// STEP1, odds provenance, v3.11 bounded-risk purchase decision and all historic files stay unchanged.
import {buildTicketUniverse,optimizePurchasePortfolio} from './jra-portfolio-optimizer-v310.mjs';
import {ticketKey,matches,evaluateStrategy} from './jra-strategy-engine-v39.mjs';

const scenarios=['low','central','high'];
const unique=(tickets)=>[...new Map(tickets.map(t=>[ticketKey(t.type,t.selection),t])).values()];
const pct=x=>Math.round(x*1000000)/10000;
const money=x=>Math.round(x*1000)/1000;
function measures(lines,args){
 if(!lines.length)return {tickets:0,stake_yen:0,hit_pct:null,profit_yen:null,loss_pct:null,roi_pct:null,
   all_scenarios:null};
 const m=evaluateStrategy(lines,args.outcome_distributions,args.frame_map,args.race_context);
 return {tickets:lines.length,stake_yen:m.total_stake_yen,
   hit_pct:pct(m.hit_probability_scenarios.central),
   profit_yen:money(m.expected_payout_yen_scenarios.central-m.total_stake_yen),
   loss_pct:pct(m.loss_probability_scenarios.central),
   roi_pct:pct(m.roi_scenarios.central),
   all_scenarios:Object.fromEntries(scenarios.map(s=>[s,{
     hit_pct:pct(m.hit_probability_scenarios[s]),
     profit_yen:money(m.expected_payout_yen_scenarios[s]-m.total_stake_yen),
     loss_pct:pct(m.loss_probability_scenarios[s]),
     roi_pct:pct(m.roi_scenarios[s])
   }]))};
}
// One input selection means one exact market quote, not merely a general odds URL.
// The v3.11 source captured only part of the trifecta grid (8/86 Tokyo, 14/86 Kyoto).
// A formal "all strategies compared" report must not quietly discard these lines.
export function inspectExactQuoteCoverageV312(strategies,{strict=true}={}){
 const byKey=new Map(),byType=new Map();
 for(const st of strategies){
   for(const line of st.lines||[]){
     const key=ticketKey(line.type,line.selection);
     const present=line.quote_verified===true&&line.market_odds!==null&&
       typeof line.source_url==='string'&&line.source_url.startsWith('https://')&&
       typeof line.observed_at==='string'&&Number.isFinite(Date.parse(line.observed_at));
     if(!byKey.has(key))byKey.set(key,{key,type:line.type,selection:line.selection,priced:present,
       origin_modes:[st.type+'/'+st.strategy_kind]});
     else{
       const old=byKey.get(key);
       if(old.priced!==present)throw Error('BLOCKER: inconsistent exact quote across strategy modes: '+key);
       old.origin_modes.push(st.type+'/'+st.strategy_kind);
     }
   }
 }
 for(const line of byKey.values()){
   const bucket=byType.get(line.type)||{type:line.type,generated:0,priced:0,missing:0};
   bucket.generated++;if(line.priced)bucket.priced++;else bucket.missing++;
   byType.set(line.type,bucket);
 }
 const missing=[...byKey.values()].filter(t=>!t.priced);
 const result={total_candidates:byKey.size,priced:byKey.size-missing.length,
   missing_count:missing.length,coverage_pct:byKey.size?pct((byKey.size-missing.length)/byKey.size):0,
   status:missing.length?'incomplete':'complete',by_type:[...byType.values()],
   missing_lines:missing.map(x=>({key:x.key,type:x.type,selection:x.selection,modes:[...new Set(x.origin_modes)]})),
   limitation:'Unobserved prices are not evidence of negative expected return or an unoffered wager.'};
 if(strict&&missing.length){
   throw Error('BLOCKER: exact prereace odds incomplete: '+missing.length+' of '+byKey.size+
     ' unique lines have no verified quote; '+[...byType.values()].filter(t=>t.missing).map(t=>t.type+' '+t.missing+'/'+t.generated).join(', ')+
     '. Recover exact documented market quotes before the formal snapshot; no odds inference.');
 }
 return result;
}

export function auditPurchaseSetComparisonsV312(args,balanced){
 const {all}=buildTicketUniverse({...args,max_ticket_stake_yen:100});
 const baseline=optimizePurchasePortfolio(args);
 const picked=balanced.selected_lines;
 const states=args.outcome_distributions.central;
 const flags=all.map(t=>Uint8Array.from(states.map(o=>matches(t,o.finish,args.frame_map,args.race_context)?1:0)));
 const possibilities=new Map(all.map((t,i)=>[ticketKey(t.type,t.selection),i]));
 function marginal(selected,candidate){
   const idx=possibilities.get(ticketKey(candidate.type,candidate.selection));
   if(idx===undefined)return 0;
   let inc=0;
   for(let i=0;i<states.length;i++)if(flags[idx][i]&&!selected[i])inc+=states[i].probability;
   return inc;
 }
 const sets=[];
 const add=(label,kind,lines,explanation)=>sets.push({label,kind,keys:lines.map(t=>ticketKey(t.type,t.selection)),
   ...measures(lines,args),explanation});
 const seen=new Uint8Array(states.length),greedy=[],taken=new Set();
 const targetSizes=new Set([1,2,3,5,10,20,60].filter(n=>n<=args.budget_yen/100));
 const greedyBySize={};
 for(let n=1;n<=Math.min(all.length,args.budget_yen/100);n++){
   let best=-1,high=-1;
   for(let j=0;j<all.length;j++){
     if(taken.has(j))continue;
     let v=0;const f=flags[j];
     for(let i=0;i<states.length;i++)if(f[i]&&!seen[i])v+=states[i].probability;
     if(v>high+1e-12||(Math.abs(v-high)<=1e-12&&best!==-1&&all[j].expected_profit_yen>all[best].expected_profit_yen)){
       best=j;high=v;
     }
   }
   if(best<0)break;
   taken.add(best);greedy.push(all[best]);
   for(let i=0;i<states.length;i++)if(flags[best][i])seen[i]=1;
   if(targetSizes.has(n))greedyBySize[n]=[...greedy];
 }
 for(const n of [...targetSizes].sort((a,b)=>a-b))if(greedyBySize[n])
   add('的中率優先 '+n+'点','illustrative_max_marginal_hit',greedyBySize[n],
      '集合的中率を伸ばす比較用セット。利益・損失の制約を満たす購入推奨とは限りません。');
 add('期待利益最大の基準解','exact_profit_baseline',baseline.selected_lines,'v3.10 厳密ナップサック解');
 add('最終採用セット','final_balanced',picked,'v3.11で事前固定された実際の購入判断を一切変更しません。');
 const modeRows=[];
 for(const st of args.strategies){
   const lines=unique(st.lines||[]),missing=lines.filter(t=>t.quote_verified!==true);
   if(missing.length){
     modeRows.push({strategy_id:st.strategy_id,type:st.type,mode:st.strategy_kind,generated:lines.length,
       status:'unpriced',missing_count:missing.length,reason:'個別実オッズ未取得。価格未確認であって非採算とは断定しない。'});
     continue;
   }
   const exceeds=lines.reduce((v,t)=>v+t.stake_yen,0)>args.budget_yen;
   if(exceeds){
     modeRows.push({strategy_id:st.strategy_id,type:st.type,mode:st.strategy_kind,generated:lines.length,
       status:'over_budget',reason:'全点購入は6000円超。部分組合せは別途横断比較。'});
     continue;
   }
   modeRows.push({strategy_id:st.strategy_id,type:st.type,mode:st.strategy_kind,generated:lines.length,
     status:'evaluated',...measures(lines,args),reason:'全点購入の集合確率と収支を同じ着順分布で算定。'});
 }
 const selectedFlags=new Uint8Array(states.length);
 for(const x of picked){
   const j=possibilities.get(ticketKey(x.type,x.selection));
   if(j!==undefined)for(let i=0;i<states.length;i++)if(flags[j][i])selectedFlags[i]=1;
 }
 const selectedKeys=new Set(picked.map(t=>ticketKey(t.type,t.selection)));
 const notSelected=all.filter(x=>!selectedKeys.has(ticketKey(x.type,x.selection)));
 const canRaise=notSelected.filter(t=>marginal(selectedFlags,t)>1e-10);
 const noGain=notSelected.length-canRaise.length;
 const pricedButNoIncrement=notSelected.length>0&&canRaise.length===0;
 const balancedAudit=balanced.optimizer_audit.balanced_selection;
 const zeroReason=balancedAudit.correlated_portfolios_evaluated>0?'evaluated_but_none_passed_guards':
   !notSelected.length?'no_excluded_priced_candidates':
   pricedButNoIncrement?'every_priced_excluded_ticket_is_already_covered_by_selected_events':
   'v311_neighbourhood_pruned_all_proposals_before_full_evaluation_check_profit_floor_and_loss_guard';
 return {
   version:'v3.12',algorithm:'explain_only_joint_outcomes_no_purchase_mutation',
   original_purchase_unchanged:true,
   coverage:inspectExactQuoteCoverageV312(args.strategies,{strict:false}),
   comparison_sets:sets,mode_comparisons:modeRows,
   search_diagnostic:{
     baseline_profit_yen:money(balancedAudit.baseline_expected_profit_yen),
     required_profit_floor_yen:money(balancedAudit.expected_profit_floor_yen),
     baseline_hit_pct:pct(balancedAudit.baseline_hit_probability),
     selected_hit_pct:pct(balanced.hit_probability_scenarios?.central||0),
     tested_portfolios:balancedAudit.correlated_portfolios_evaluated,
     excluded_priced_candidates:notSelected.length,
     no_marginal_hit_gain:noGain,positive_marginal_hit_candidates:canRaise.length,
     zero_trial_reason:balancedAudit.correlated_portfolios_evaluated===0?zeroReason:null
   },
   disclaimer:'Representative top-N greedy portfolios are diagnostics, not proof of a global multi-objective optimum or real-world hit frequencies.'
 };
}
