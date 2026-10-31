/* Page-local adapter; shared Kyoto ability model remains byte-identical. */
(function(g){'use strict';
const original=g.RaceSimAbility;
const keys=Object.freeze(['early','cruise','burst','sustain','stamina','acceleration']);
function profile(h,race,avg){
 const base=original.profile(h,race,avg);
 if(race.course_id!=='tokyo_turf_2000'||race.labAbilityScale!=='90-v1'||
    race.labTokyoAbility90!==true)return base;
 if(h.styleMeta?.source!=='LAB_SYNTHETIC_NOT_OFFICIAL')throw Error('TOKYO_SYNTHETIC_ONLY');
 const display={},six={};
 for(const key of keys){
  const score=h.labAbility90?.[key];
  if(!Number.isFinite(score)||score<82||score>98)throw Error('TOKYO_ABILITY90_INVALID');
  display[key]=score;six[key]=50+(score-90)/.3;
 }
 return Object.freeze({...base,six:Object.freeze(six),displaySix:Object.freeze(display),
  scale:'90-v1',neutral:90,legacyPointsPerScore:1/.3});
}
g.RaceSimAbility=Object.freeze({...original,profile});
})(typeof window!=='undefined'?window:globalThis);
