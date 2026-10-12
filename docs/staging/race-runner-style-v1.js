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
const styleGap={nige:0,senko:4.0,sashi:10.0,oikomi:19.0,unknown:10.0};
function positionAdjustment(style,gap,d,t){
 const category=TYPES.includes(style)?style:'unknown';
 const target=styleGap[category];
 const progress=Math.max(0,Number(d)||0);
 const early=progress<100?1:progress<350?.52*(350-progress)/250:0;
 const requested=Math.max(-2.4,Math.min(2.4,(gap-target)*.18));
 // Initially offer extra acceleration for leading runners and hold back
 // deep closers. Later allow racing ability and tactics to decide order.
 const launch={nige:1.40,senko:.60,sashi:-.35,oikomi:-1.2,unknown:-.15}[category];
 const startBlend=Math.min(1,Math.max(0,(Number(t)||0)/2.2));
 return (requested+launch)*early*startBlend;
}
global.RaceRunnerStyle=Object.freeze({TYPES,inferFromLastRace,positionAdjustment,styleGap});
})(typeof window!=='undefined'?window:globalThis);
