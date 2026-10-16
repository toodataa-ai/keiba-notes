// Pure candidate scorer. Never reads race results or post-race files.
import { createHash } from "node:crypto";

export const MODEL_VERSION = "local-challenger-v0.2.0-candidate";
export const COEFFICIENTS = Object.freeze({
  first_corner_solo_front: 0.14,
  crowded_front_penalty: -0.16,
  crowded_closer_bonus: 0.08,
  medium_front_penalty: -0.06,
  layoff_over_90d: -0.18,
  layoff_46_to_90d: -0.07,
  turnaround_under_7d: -0.05
});
export const COEFFICIENTS_SHA256 = createHash("sha256").update(JSON.stringify(COEFFICIENTS)).digest("hex");
const forbidden = ["finish_order", "payouts", "official_result", "result", "review"];
const finite = (x) => typeof x === "number" && Number.isFinite(x);
const days = (a,b) => Math.floor((Date.parse(a)-Date.parse(b))/86400000);

export function scoreRace(source) {
  if (!source || typeof source !== "object" || !Array.isArray(source.runners)) throw new Error("Invalid pre-race snapshot");
  if (forbidden.some(k => Object.hasOwn(source,k))) throw new Error("Result leakage guard: forbidden post-race key");
  if (source.production_effect !== false || source.model_version !== "local-daily-shadow-v0.1") throw new Error("Unexpected source model/production mode");
  const start = Date.parse(source.scheduled_start_at), cutoff = Date.parse(source.information_cutoff_at);
  if (!Number.isFinite(start) || !Number.isFinite(cutoff) || cutoff >= start) throw new Error("Source missing valid pre-start cutoff");
  if (source.surface === "ばんえい") throw new Error("UNSUPPORTED_BANEI_SEPARATE_MODEL");
  const active = source.runners.filter(h=>!h.non_runner);
  if (active.length < 5 || active.some(h=>!Number.isInteger(h.horse_no) || !finite(h.evidence_score))) throw new Error("Insufficient pre-race evidence");
  const ids = new Set(active.map(h=>h.horse_no));
  if (ids.size!==active.length) throw new Error("Duplicate horse numbers");
  const mu = active.reduce((s,h)=>s+h.evidence_score,0)/active.length;
  const variance = active.reduce((s,h)=>s+(h.evidence_score-mu)**2,0)/active.length;
  const scale = Math.max(Math.sqrt(variance),0.75);
  const front = active.filter(h=>h.running_style_hypothesis==="先行").length;
  const pace = front>=5?"H（仮説）":front>=3?"M（仮説）":front<=1?"S（仮説）":"M（仮説）";
  const scored=active.map(h=>{
    const base=(h.evidence_score-mu)/scale;
    const style=h.running_style_hypothesis;
    let paceDelta=0;
    if (front<=1 && style==="先行") paceDelta=COEFFICIENTS.first_corner_solo_front;
    else if (front>=5 && style==="先行") paceDelta=COEFFICIENTS.crowded_front_penalty;
    else if (front>=5 && style==="差し・追込") paceDelta=COEFFICIENTS.crowded_closer_bonus;
    else if (front>=3 && style==="先行") paceDelta=COEFFICIENTS.medium_front_penalty;
    const raceDates=(h.recent_races||[]).map(r=>r.date).filter(Boolean).sort().reverse();
    let layoffDays=null,rotationDelta=0;
    if (raceDates.length){
      layoffDays=days(source.date,raceDates[0]);
      if (!Number.isFinite(layoffDays) || layoffDays<1) throw new Error("Recent race date not before target race");
      rotationDelta=layoffDays>90?COEFFICIENTS.layoff_over_90d:layoffDays>45?COEFFICIENTS.layoff_46_to_90d:layoffDays<7?COEFFICIENTS.turnaround_under_7d:0;
    }
    const total=base+paceDelta+rotationDelta;
    return { horse_no:h.horse_no,horse_name:h.horse_name,score: Number(total.toFixed(6)),
      components:{baseline_normalized:Number(base.toFixed(6)),pace_delta:paceDelta,rotation_delta:rotationDelta},
      diagnostics:{style:style||"不明",recent_races:(h.recent_races||[]).length,layoff_days:layoffDays,
        carried_weight:h.weight_carried??null,jockey:h.jockey??null,gate:h.gate??null,
        distance_record:h.distance_record??null,
        excluded_from_score:["jockey","weight","gate","class","clock","going","odds"]}};
  }).sort((a,b)=>b.score-a.score || a.horse_no-b.horse_no);
  return {schema_version:1,model_version:MODEL_VERSION,mode:"research_candidate",
    production_effect:false,source_race_id:source.race_id,source_date:source.date,
    venue:source.venue,surface:source.surface,distance:source.distance,
    scheduled_start_at:source.scheduled_start_at,source_cutoff_at:source.information_cutoff_at,
    coefficients_sha256:COEFFICIENTS_SHA256,pace_hypothesis:pace,front_runner_count:front,
    top_pick:{horse_no:scored[0].horse_no,horse_name:scored[0].horse_name},
    ability_order:scored.map((h,i)=>({rank:i+1,...h})),notes:[
      "Exploratory candidate weights predeclared; not statistically calibrated",
      "Do not infer forward performance from retrospective replay",
      "Odds and payouts are not used or available from the v0.1 source"
    ]};
}
