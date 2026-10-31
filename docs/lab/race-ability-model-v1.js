/* Stage v0.22. PRE-RACE evidence only. Six uncalibrated runner traits.
   No raw-time/3F cross-course comparisons, post-race data or betting odds. */
(function(global){'use strict';
const G=Object.freeze({'A+':5,A:4,'B+':3,B:2,'B-':1,C:0});
const cl=(v,a,b)=>Math.max(a,Math.min(b,v));
const grade=g=>typeof g==='string'&&Object.prototype.hasOwnProperty.call(G,g)?G[g]:null;
function profile(h,race,avg){
 const g=Array.isArray(h.factorGrades)?h.factorGrades:[];
 const v=i=>grade(g[i]);
 const prev=h.styleMeta?.source==='pre_race_report_last_run'&&h.styleMeta.field>=2?h.styleMeta:null;
 const recent=Array.isArray(h.recentRuns)?h.recentRuns.filter(x=>Number.isInteger(x?.distance_m)&&
   Number.isInteger(x?.finish)&&x.finish>=1&&x.finish<=24).slice(0,4):[];
 const same=recent.filter(x=>x.venue===race.venue&&x.distance_m===race.distance_m);
 const longPlaced=recent.filter(x=>x.distance_m>=race.distance_m&&x.finish<=3).length;
 const win=Number(h.win_pct),margin=Number.isFinite(win)&&Number.isFinite(avg)?cl(win-avg,-12,15):0;
 const baseSpeed=cl((v(8)===null?0:v(8)-2)*.13+margin*.018,-.50,.66);
 const courseSpeed=cl((v(4)===null?0:v(4)-2)*.06+(v(2)===null?0:v(2)-2)*.018,-.23,.30);
 const paceSpeed=cl((v(1)===null?0:v(1)-2)*.065,-.13,.20);
 const earlySpeed=prev?cl((.5-(prev.first-1)/(prev.field-1))*.32,-.16,.16):0;
 const kick=prev?cl((prev.first-prev.last)/(prev.field-1)*.28,-.28,.28):0;
 const stamina=cl(1+Math.min(2,longPlaced)*.055,1,1.11);
 // Six 0-100 stage-only hypotheses; unavailable signals stay neutral.
 // Neither post-race facts nor cross-course raw timings enter these values.
 const priorEarly=prev?(.5-(prev.first-1)/(prev.field-1)):0;
 const priorChange=prev?(prev.first-prev.last)/(prev.field-1):0;
 const meanFinish=recent.length?recent.reduce((s,r)=>s+r.finish,0)/recent.length:null;
 const placing=meanFinish===null?0:cl((8-meanFinish)/8,-1,1);
 const basic=v(8)===null?0:v(8)-2;
 const form=v(3)===null?0:v(3)-2;
 const paceGrade=v(1)===null?0:v(1)-2;
 const courseGrade=v(4)===null?0:v(4)-2;
 const distanceEvidence=Math.min(2,longPlaced);
 const bounded=n=>Math.round(cl(n,0,100));
 const six=Object.freeze({
   early:bounded(50+priorEarly*30+paceGrade*2+placing*2),
   cruise:bounded(50+basic*5+courseGrade*2+margin*.9+placing*3),
   burst:bounded(50+priorChange*25+basic*2+form*2),
   sustain:bounded(50+basic*3+distanceEvidence*4+placing*3+form*2),
   stamina:bounded(50+distanceEvidence*7+basic*2+placing*2),
   acceleration:bounded(50+priorEarly*7+priorChange*15+paceGrade*3+form*2)
 });
 const evidence=[];
 for(const [i,label] of [[8,'基礎能力⑨'],[4,'コース適性⑤'],[2,'馬場③'],[1,'展開②']])
   if(v(i)!==null)evidence.push(label+':'+g[i]);
 if(Number.isFinite(win))evidence.push('STEP1単勝確率:'+win.toFixed(1)+'%（未校正）');
 if(prev)evidence.push('前走通過順:'+prev.first+'→'+prev.last+'/'+prev.field+'頭');
 if(same.length)evidence.push('近走同場同距離:'+same.length+'走（3着内'+same.filter(x=>x.finish<=3).length+'走）');
 if(longPlaced)evidence.push('同距離以上の近走3着内:'+longPlaced+'走');
 const missing=[];
 if(v(8)===null)missing.push('⑨基礎能力');
 if(v(4)===null)missing.push('⑤コース適性');
 if(!prev)missing.push('前走通過順');
 if(!recent.length)missing.push('近走距離・着順');
 // Opt-in only for the clean Kyoto2000 LAB. Other courses retain every
 // original value. A 90-centred point is 1/.3 legacy points: normalize
 // before the unchanged engine applies its 50-centred coefficients.
 const use90=race.labAbilityScale==='90-v1'&&race.course_id==='kyoto_turf_inner_2000';
 const keys=Object.keys(six),displaySix={},normalizedSix={};
 if(use90){
  const synthetic=h.styleMeta?.source==='LAB_SYNTHETIC_NOT_OFFICIAL';
  const fixed=synthetic?h.labAbility90:null;
  for(const key of keys){
   const score=fixed?.[key]??Math.round(cl(90+(six[key]-50)*.3,82,98)*10)/10;
   if(!Number.isFinite(score)||score<82||score>98)throw Error('LAB_ABILITY_90_INVALID');
   displaySix[key]=score;
   // Prestart grades have integer legacy scores. Keep their exact original
   // physics contribution, without round-trip floating point drift.
   normalizedSix[key]=fixed?(score-90)/.3+50:six[key];
  }
 }
 return Object.freeze({baseSpeed,courseSpeed,paceSpeed,earlySpeed,kick,stamina,
  six:use90?Object.freeze(normalizedSix):six,
  ...(use90?{displaySix:Object.freeze(displaySix),
   scale:'90-v1',neutral:90,legacyPointsPerScore:1/.3}:{}),
  evidence:Object.freeze(evidence),missing:Object.freeze(missing),confidence:missing.length?'低い':'限定的',
  excluded:'異条件の生時計・上がり3Fの直接比較、未取得調教、事後結果・払戻'});
}
global.RaceSimAbility=Object.freeze({profile,gradeValue:grade});
})(typeof window!=='undefined'?window:globalThis);
