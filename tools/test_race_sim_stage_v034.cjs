/* Stage v0.34: persistent sectional clock directly below the live clock.
 * Only the stage presentation changes. No race physics or prediction inputs.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const root='docs/staging/';
const html=fs.readFileSync(root+'race-simulator.html','utf8');
const css=fs.readFileSync(root+'race-simulator.css','utf8');
const js=fs.readFileSync(root+'race-simulator.js','utf8');
// Both clocks must belong to one right-aligned container, not independently
// positioned over the runners or at opposite sides of the video.
assert.match(html,/<div class="stage-clock-stack"[^>]*>[\s\S]*?<span id="elapsed">[\s\S]*?<div id="splitTime"[^>]*>[\s\S]*?<span id="splitLabel"[^>]*>[\s\S]*?<strong id="splitValue"/);
assert.ok(html.indexOf('id="elapsed"')<html.indexOf('id="splitTime"'));
assert.ok(html.indexOf('id="splitTime"')<html.indexOf('class="stage-bottom"'));
assert.ok(html.includes('id="splitTime" class="stage-split" role="status" aria-live="off" hidden'));
// Pixel sizes of numeric glyphs must match at both desktop and phone widths.
const main=css.match(/#elapsed\{font-size:(clamp\([^;]+\))/);
const split=css.match(/\.stage-split-value\{font:900 (clamp\([^ ]+\))/);
assert.ok(main&&split);
assert.equal(main[1],split[1],'matching responsive font sizes');
assert.match(css,/@media\(max-width:500px\)\{#elapsed\{font-size:18px/);
assert.match(css,/\.stage-split-value\{font-size:18px\}/);
assert.match(css,/\.stage-clock-stack\{display:grid;justify-items:end/);
assert.match(css,/\.stage-split\{pointer-events:none;position:static/);
assert.ok(!css.includes('.stage-split{top:37px;left:7px}'),'legacy floating time removed');
// Split remains visible from actual 600m or 1000m crossing until goal,
// including the finished view (no eight-second timeout).
assert.ok(js.includes('splitEl.hidden=state.splitTime===null;'));
assert.ok(!js.includes('state.t-state.splitTime>8'));
assert.ok(js.includes("if(label)label.textContent='前半'+state.splitDistanceM+'m';"));
assert.ok(js.includes("if(value)value.textContent=state.splitTime===null?'—':dur(state.splitTime);"));
assert.ok(js.includes('state.firstFinishTime??state.t'));
assert.ok(html.includes('race-simulator.css?v=20261016-34'));
assert.ok(html.includes('race-simulator.js?v=20261016-39'));
assert.ok(html.includes('race-sim-engine.js?v=20261016-40'));
console.log('PASS_V034_RIGHT_STACK_EQUAL_FONT_600M_1000M_PERSISTENT_SPLIT');
