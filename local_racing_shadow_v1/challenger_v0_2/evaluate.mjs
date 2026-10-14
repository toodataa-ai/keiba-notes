// Read-only exploratory paired comparison on frozen v0.1 snapshots.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { scoreRace } from "./scoring.mjs";

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"../../");
const root=path.join(repo,"local_racing_shadow_v1");
const dates=process.argv.slice(2).filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x));
const chosen=dates.length?dates:fs.readdirSync(path.join(root,"results")).filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x));
const rows=[], excluded=[];
for(const date of chosen){
  const dir=path.join(root,"results",date);
  if (!fs.existsSync(dir)) continue;
  for(const f of fs.readdirSync(dir).filter(x=>x.endsWith(".json"))){
    const rid=f.slice(0,-5);
    try {
      const pred=JSON.parse(fs.readFileSync(path.join(root,"predictions",date,f),"utf8"));
      const result=JSON.parse(fs.readFileSync(path.join(dir,f),"utf8"));
      if (result.race_id!==rid || pred.race_id!==rid || result.validation?.prediction_immutable!==true || !result.proof_commit) throw new Error("Missing audited immutable result join");
      const actual=result.finish_order.filter(h=>Number.isInteger(h.finish_position));
      const position=new Map(actual.map(h=>[h.horse_no,h.finish_position]));
      const baseline=pred.ability_order[0]?.horse_no, challenger=scoreRace(pred).top_pick.horse_no;
      if (!position.has(baseline)||!position.has(challenger)) throw new Error("Top pick lacks official rank");
      rows.push({race_id:rid,date,venue:pred.venue,baseline_rank:position.get(baseline),challenger_rank:position.get(challenger)});
    }catch(e){excluded.push({race_id:rid,reason:String(e.message||e)});}
  }
}
const aggregate=ar=>({n:ar.length,baseline_wins:ar.filter(x=>x.baseline_rank===1).length,
 challenger_wins:ar.filter(x=>x.challenger_rank===1).length,
 baseline_top3:ar.filter(x=>x.baseline_rank<=3).length,challenger_top3:ar.filter(x=>x.challenger_rank<=3).length,
 better_rank:ar.filter(x=>x.challenger_rank<x.baseline_rank).length,
 worse_rank:ar.filter(x=>x.challenger_rank>x.baseline_rank).length,
 equal_rank:ar.filter(x=>x.challenger_rank===x.baseline_rank).length});
const groups={};
for(const row of rows)(groups[row.venue]??=[]).push(row);
console.log(JSON.stringify({study:"RETROSPECTIVE_EXPLORATORY_NOT_FORWARD",model:"local-challenger-v0.2.0-candidate",
 cutoff_rule:"Only original frozen pre-race data are scored; no learned tuning on these outcomes",
 dates:chosen,overall:aggregate(rows),by_venue:Object.fromEntries(Object.entries(groups).map(([k,v])=>[k,aggregate(v)])),
 excluded,limitations:["No pre-race odds so no ROI or EV","No unbiased future holdout yet","Do not compare Banei until separate model"]},null,2));
