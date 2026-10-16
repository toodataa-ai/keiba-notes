// Forward-only recorder. Must run AFTER baseline pre-race commit and BEFORE each start.
// No results, no old predictions, no JRA files modified.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { scoreRace } from "./scoring.mjs";

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"../../");
const shadow=path.join(repo,"local_racing_shadow_v1");
const outRoot=path.join(shadow,"challenger_v0_2","predictions");
const date=process.argv[2];
if(!/^\d{4}-\d{2}-\d{2}$/.test(date||""))throw Error("Usage: node record_forward.mjs YYYY-MM-DD");
const today=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Tokyo",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
if(date!==today) throw Error("FORWARD_ONLY_CURRENT_JST_DAY");
const runGit=(...args)=>execFileSync("git",["-C",repo,...args],{encoding:"utf8"}).trim();
const folder=path.join(shadow,"predictions",date);
if(!fs.existsSync(folder))throw Error("NO_BASELINE_SOURCE");
const done=[],blocked=[],already=[];
for(const file of fs.readdirSync(folder).filter(x=>x.endsWith(".json")).sort()){
  const src=path.join(folder,file);
  const rel=path.relative(repo,src).split(path.sep).join("/");
  const dest=path.join(outRoot,date,file);
  try{
    const bytes=fs.readFileSync(src);
    const original=JSON.parse(bytes.toString("utf8"));
    const candidate=scoreRace(original);
    const proof=runGit("log","--diff-filter=A","--format=%H","--",rel).split("\n")[0];
    if(!/^[a-f0-9]{40}$/.test(proof||""))throw Error("BASELINE_PROOF_NOT_COMMITTED");
    const last=runGit("log","-1","--format=%H","--",rel);
    if(last!==proof)throw Error("BASELINE_REWRITTEN_SINCE_ORIGINAL_COMMIT");
    const origBytes=execFileSync("git",["-C",repo,"show",proof+":"+rel]);
    if(!origBytes.equals(bytes)) throw Error("BASELINE_BYTES_DIFFER_FROM_FIRST_COMMIT");
    const commitAt=runGit("show","-s","--format=%cI",proof);
    const start=Date.parse(original.scheduled_start_at),now=Date.now();
    if(Date.parse(commitAt)>=start)throw Error("BASELINE_PROOF_AFTER_START");
    if(start-now<10*60*1000)throw Error("TOO_CLOSE_TO_START_FOR_CHALLENGER_COMMIT");
    if(fs.existsSync(dest)){
      const existing=JSON.parse(fs.readFileSync(dest,"utf8"));
      if(existing.source_sha256!==createHash("sha256").update(bytes).digest("hex") ||
          existing.coefficients_sha256!==candidate.coefficients_sha256)throw Error("IMMUTABLE_CHALLENGER_CONFLICT");
      already.push(original.race_id);continue;
    }
    fs.mkdirSync(path.dirname(dest),{recursive:true});
    const record={...candidate,mode:"FORWARD",source_prediction_path:rel,
      source_sha256:createHash("sha256").update(bytes).digest("hex"),
      source_proof_commit:proof,source_committed_at:commitAt,
      generated_at:new Date(now).toISOString(),information_cutoff_at:new Date(now).toISOString(),
      proof_state:"PENDING_GITHUB_COMMIT_AUDIT"};
    fs.writeFileSync(dest,JSON.stringify(record,null,2)+"\n",{encoding:"utf8",flag:"wx"});
    done.push(original.race_id);
  } catch(e) {blocked.push({file,reason:String(e.message||e)});}
}
const report={date,mode:"FORWARD",new_count:done.length,existing_count:already.length,blocked_count:blocked.length,new_races:done,already,blocked,
  note:"Outputs are not yet committed/proven; run audit_forward.mjs AFTER separate GitHub commit."};
console.log(JSON.stringify(report,null,2));
if(blocked.some(x=>!x.reason.includes("UNSUPPORTED_BANEI")))process.exitCode=2;
