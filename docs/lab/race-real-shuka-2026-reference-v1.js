/* Observed JRA post-race facts: READ-ONLY validation target.
 * This script is NOT referenced by RaceSimEngine, fixture.horses(),
 * RaceAbilityModel or RaceLaneAI, and NEVER alters the outcome.
 * https://www.jra.go.jp/datafile/seiseki/g1/shuka/result/shuka2026.html
 * 2026-10-18 Kyoto 11R 秋華賞; 17 runners, turf good.
 * Grouping ((), '-' and '=') is displayed as a flat order for ranking
 * comparison only; photo or lane position within tied groups not inferred.
 */
(function(global){'use strict';
const actual=Object.freeze({
 race_id:'2026-10-18-shuka-sho',date:'2026-10-18',
 source_url:'https://www.jra.go.jp/datafile/seiseki/g1/shuka/result/shuka2026.html',
 observed_after_race:true,independent_reference_only:true,
 race:'第31回秋華賞',venue:'京都',surface:'芝',going:'良',distance_m:2000,
 runners:17,winnerTimeSeconds:116.1,finalTop3:[8,1,13],
 cumulative200m:Object.freeze([12.2,23.1,35.0,46.5,57.8,69.4,80.7,92.1,104.1,116.1]),
 officialCorners:Object.freeze([
  Object.freeze({label:'1コーナー',distanceApprox:308.7,
   order:Object.freeze([2,10,1,11,8,12,4,5,6,9,3,16,7,17,13,14,15])}),
  Object.freeze({label:'2コーナー',distanceApprox:530,
   order:Object.freeze([2,1,10,11,8,12,4,5,3,6,9,16,7,13,17,14,15])}),
  Object.freeze({label:'3コーナー',distanceApprox:1435,
   order:Object.freeze([2,1,10,11,8,4,12,3,5,6,16,13,7,14,9,17,15])}),
  Object.freeze({label:'4コーナー',distanceApprox:1671.6,
   order:Object.freeze([2,1,10,11,8,4,12,3,5,6,13,16,7,14,15,17,9])})
 ])
});
global.RaceRealShuka2026Reference=actual;
})(typeof window!=='undefined'?window:globalThis);
