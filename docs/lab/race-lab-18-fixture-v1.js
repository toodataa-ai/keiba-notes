/* LAB synthetic 18-horse Kyoto inner 2000m cohort, v0.48.
   Not a JRA entry list, not a prediction, not an official past race. */
(function(global){'use strict';
const id='lab-kyoto-inner-2000-synthetic-18-v048';
function entry(){return {id,demo_mode:'synthetic_18_inner_lane_v048',
 date:'2026-10-18',venue:'京都',number:11,
 race:'芝2000m内回り・内優先18頭検証（全馬架空）',
 surface:'芝',turn:'右',distance_m:2000,
 course_id:'kyoto_turf_inner_2000',field_size:18,
 scope:'LAB_SYNTHETIC_NOT_OFFICIAL',going:'仮想',going_observed_at:'—'};}
// Fixed LAB90 cohorts, specified before simulation. No observed race
// outcome, finishing-time target, random draw or horse-number ranking.
const TRAIT_KEYS=['early','cruise','burst','sustain','stamina','acceleration'];
const ABILITY90=Object.freeze([
 [96,89,85,88,89,94],[94,92,86,90,91,95],
 [92,94,92,93,92,93],[91,88,87,88,89,90],
 [90,91,89,90,90,91],[87,86,85,86,87,86],[93,92,91,92,91,92],
 [88,90,94,93,91,94],[86,88,92,90,89,92],[89,93,96,94,92,95],
 [87,90,93,91,90,93],[85,86,87,86,85,87],[88,91,95,93,92,94],
 [84,89,96,94,93,95],[86,90,94,92,91,94],[85,92,98,96,95,97],
 [82,86,89,87,86,90],[85,89,95,93,92,96]
].map(row=>Object.freeze(row)));
function horses(options={}){
 const styles=['nige','nige','senko','senko','senko','senko','senko',
  'sashi','sashi','sashi','sashi','sashi','sashi',
  'oikomi','oikomi','oikomi','oikomi','oikomi'];
 return styles.map((style,i)=>({
  number:i+1,name:'検証馬'+String(i+1).padStart(2,'0')+'（架空）',
  mark:'△',grade:'B',pace_grade:'B',
  factorGrades:Array(9).fill('B'),
  style,styleMeta:{source:'LAB_SYNTHETIC_NOT_OFFICIAL'},
  recentRuns:[],win_pct:NaN,
  ...(options.abilityScale==='90-v1'?{labAbility90:
   Object.fromEntries(TRAIT_KEYS.map((key,j)=>[key,ABILITY90[i][j]]))}:{})
 }));
}
global.RaceLab18Fixture=Object.freeze({id,entry,horses});
})(typeof window!=='undefined'?window:globalThis);
