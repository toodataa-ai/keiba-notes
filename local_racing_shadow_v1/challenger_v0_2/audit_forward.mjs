// Independent post-commit immutable proof audit, no file modifications.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { COEFFICIENTS_SHA256 } from "./scoring.mjs";

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"../../");
const date=process.argv[2];
if (!/^\d{4}-\d{2}-\d{2}$/.test(date||""))throw Error("Usage: node audit_forward.mjs YYYY-MM-DD");
const dir=path.join(repo,"local_racing_shadow_v1/challenger_v0_2/predictions",date);
if(!fs.existsSync(dir))throw Error("NO_CHALLENGER_PREDICTIONS");
const git=(...args)=>execFileSync("git",["-C",repo,...args],{encoding:"utf8"}).trim();
const verified=[],blocked=[];
for(const file of fs.readdirSync(dir).filter(x=>x.endsWith(".json")).sort()){
 try{
  const dest=path.join(dir,file),rel=path.relative(repo,dest).split(path.sep).join("/");
  const bytes=fs.readFileSync(dest),p=JSON.parse(bytes.toString("utf8"));
  if(p.mode!=="FORWARD" || p.production_effect!==false || p.coefficients_sha256!==COEFFICIENTS_SHA256)throw Error("BAD_VERSION_OR_MODE");
  const proof=git("log","--diff-filter=A","--format=%H","--",rel).split("\n")[0];
  if(!/^[a-f0-9]{40}$/.test(proof||""))throw Error("CHALLENGER_NOT_COMMITTED");
  if(git("log","-1","--format=%H","--",rel)!==proof)throw Error("CHALLENGER_MUTATED");
  if(!execFileSync("git",["-C",repo,"show",proof+":"+rel]).equals(bytes))throw Error("CHALLENGER_BYTES_MISMATCH");
  const createdAt=Date.parse(git("show","-s","--format=%cI",proof));
  const start=Date.parse(p.scheduled_start_at);
  if(!(createdAt<start && Date.parse(p.information_cutoff_at)<createdAt))throw Error("CHALLENGER_CUTOFF_FAILURE");
  const src=path.join(repo,p.source_prediction_path),srcBytes=fs.readFileSync(src);
  if(createHash("sha256").update(srcBytes).digest("hex")!==p.source_sha256)throw Error("BASELINE_SHA_MISMATCH");
  if(git("log","-1","--format=%H","--",p.source_prediction_path)!==p.source_proof_commit)throw Error("BASELINE_CHANGED");
  if(Date.parse(p.source_committed_at)>=start)throw Error("BASELINE_LATE");
  verified.push(p.source_race_id);
 }catch(e){blocked.push({file,reason:String(e.message||e)});}
}
console.log(JSON.stringify({date,scope:"CHALLENGER_FORWARD_COMMIT_PROOF",verified_count:verified.length,blocked_count:blocked.length,blocked},null,2));
if(blocked.length)process.exitCode=2;
