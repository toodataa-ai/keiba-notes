/* Staging-only running-style classification from documented PRE-RACE last-run passages.
 * Provisional: a single past run cannot confirm an enduring running style.
 * No popularity, betting odds, predicted finishing rank or post-race data used. */
(function(global){
'use strict';
const TYPES=['nige','senko','sashi','oikomi','unknown'];
function inferFromLastRace(text){
 const source=String(text||'');
 const last=source.split('JRA前走：')[1]||'';
 const places=last.match(/\bkg\s+((?:\d{1,2}\s+){1,4})3F\b/);
 const field=last.match(/\b\d+\s*着\s+(\d+)\s*頭/);
 if(!places||!field)return {style:'unknown',confidence:'unavailable',first:null,last:null,field:null,positions:[],source:'prior_jra_run_unavailable'};
 const runners=Number(field[1]);
 const positions=places[1].trim().split(/\s+/).map(Number);
 if(runners<2||runners>24||positions.some(p=>p<1||p>runners))return {style:'unknown',confidence:'invalid',first:null,last:null,field:null,positions:[],source:'prior_jra_run_invalid'};
 const first=positions[0],end=positions.at(-1);
 const firstPct=(first-1)/(runners-1);
 const lastPct=(end-1)/(runners-1);
 let style;
 if(firstPct<=.105&&lastPct<=.20)style='nige';
 else if(firstPct<=.34)style='senko';
 else if(firstPct>=.72||lastPct>=.84&&firstPct>=.60)style='oikomi';
 else style='sashi';
 return {style,confidence:'single_previous_race',first,last:end,field:runners,positions,source:'pre_race_report_last_run'};
}
const styleGap={nige:0,senko:3.0,sashi:7.0,oikomi:13.0,unknown:7.0};
function positionAdjustment(style,gap,d,t,prior){
 const category=TYPES.includes(style)?style:'unknown';
 // Prior-race early passage gives each runner a DIFFERENT desired pack gap.
 // This spreads a crowded middle group fore-and-aft, opening safe rail slots
 // instead of forcing ten horses abreast into more than six inner lanes.
 const priorPct=prior&&prior.source==='pre_race_report_last_run'&&prior.field>=2?
    (prior.first-1)/(prior.field-1):.5;
 const target=styleGap[category]+Math.max(-5,Math.min(5,(priorPct-.5)*12));
 const progress=Math.max(0,Number(d)||0);
 const fade=Math.max(0,Math.min(1,(progress-100)/320));
 const early=1-fade*fade*(3-2*fade);
 const requested=Math.max(-1.15,Math.min(1.15,(gap-target)*.11));
 // Initially offer extra acceleration for leading runners and hold back
 // deep closers. Later allow racing ability and tactics to decide order.
 const launch={nige:.92,senko:.35,sashi:-.15,oikomi:-.65,unknown:-.15}[category];
 const startBlend=Math.min(1,Math.max(0,(Number(t)||0)/2.2));
 return (requested+launch)*early*startBlend;
}
global.RaceRunnerStyle=Object.freeze({TYPES,inferFromLastRace,positionAdjustment,styleGap});
})(typeof window!=='undefined'?window:globalThis);
