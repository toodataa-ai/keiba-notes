/* Prestart-only, course-independent LAB cohort speed rule. Provisional, not official. */
(function(global){'use strict';
const BASE_CRUISE_MPS=17.0;
const RULES=Object.freeze([
 Object.freeze({id:'three-year-old-fillies-middle-turf-v1',ageYears:3,sex:'牝',
  surface:'芝',minDistance:1800,maxDistance:2400,baseCruiseMps:16.65,
  provisional:true})
]);
function resolve(race){
 if(!race||typeof race!=='object')throw Error('COHORT_RACE_MISSING');
 const rule=RULES.find(x=>race.age_restriction_years===x.ageYears &&
  race.sex_restriction===x.sex && race.surface===x.surface &&
  Number.isFinite(race.distance_m)&&
  race.distance_m>=x.minDistance&&race.distance_m<=x.maxDistance);
 return Object.freeze({id:rule?.id||'legacy-unrestricted-baseline',
  baseCruiseMps:rule?.baseCruiseMps??BASE_CRUISE_MPS,
  provisional:Boolean(rule)});
}
global.RaceCohortSpeed=Object.freeze({resolve,BASE_CRUISE_MPS,RULES});
})(typeof window!=='undefined'?window:globalThis);
