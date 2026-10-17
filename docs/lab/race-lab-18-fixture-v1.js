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
function horses(){
 const styles=['nige','nige','senko','senko','senko','senko','senko',
  'sashi','sashi','sashi','sashi','sashi','sashi',
  'oikomi','oikomi','oikomi','oikomi','oikomi'];
 return styles.map((style,i)=>({
  number:i+1,name:'検証馬'+String(i+1).padStart(2,'0')+'（架空）',
  mark:'△',grade:'B',pace_grade:'B',
  factorGrades:Array(9).fill('B'),
  style,styleMeta:{source:'LAB_SYNTHETIC_NOT_OFFICIAL'},
  recentRuns:[],win_pct:NaN
 }));
}
global.RaceLab18Fixture=Object.freeze({id,entry,horses});
})(typeof window!=='undefined'?window:globalThis);
