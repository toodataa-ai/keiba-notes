/* v0.35 stage visual regression: no phantom TV-caption text beneath HUD. */
'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const base='docs/staging/';
const html=fs.readFileSync(base+'race-simulator.html','utf8');
const js=fs.readFileSync(base+'race-simulator.js','utf8');
const css=fs.readFileSync(base+'race-simulator.css','utf8');
function between(start,end){
 const a=js.indexOf(start),b=js.indexOf(end,a+start.length);
 assert.ok(a>=0&&b>a,'source area not found: '+start);
 return js.slice(a,b);
}
const live=between('function drawRace(){','/* Source-relative x/y');
const finish=between('function drawGoalCamera(','window.RaceSimGoalView=');
// Video canvas must not paint the old upper-left and upper-right headers.
// This prevents the hidden "馬番を追走" and "18 / 18頭 表示中" from
// reappearing through the HTML's translucent status badges.
for(const [name,draw] of [['live',live],['finish',finish]]){
 assert.doesNotMatch(draw,/rect\(ctx,\s*12,\s*34,/,'canvas '+name+' old top-left box');
 assert.doesNotMatch(draw,/rect\(ctx,\s*(700|773),\s*34,/,'canvas '+name+' old top-right box');
 assert.doesNotMatch(draw,/馬番を追走|頭 表示中|馬群を広く|PHOTO FINISH|ゴール板固定カメラ|ゴール通過・余走中/,'canvas '+name+' duplicate overlay');
}
assert.match(live,/drawRaceNumbers\(ctx,points,/,'race numbers preserved');
assert.match(finish,/drawGoalPost\(ctx,/,'goal post preserved');
assert.match(finish,/raceNumberMarker\(ctx,/,'runner numbers at finish preserved');
// Exactly one HTML-owned HUD must remain, with the split beneath the timer.
assert.match(html,/<div class="stage-top">[\s\S]*?id="stageCaption"[\s\S]*?class="stage-clock-stack"[\s\S]*?id="elapsed"[\s\S]*?id="splitTime"/);
assert.match(css,/#elapsed\{font-size:/);
assert.match(css,/\.stage-split-value\{font:900/);
assert.match(html,/race-simulator\.js\?v=20261016-35/);
assert.match(html,/HUD fix v0\.35/);
console.log('PASS_V035_NO_GHOST_CANVAS_HUD_BOTH_VIEWS_HTML_TIMER_AND_GOAL_PRESERVED');
