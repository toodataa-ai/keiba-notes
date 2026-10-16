/* Existing HTML simulator interaction, not a standalone replacement player.
 * CI installs jsdom@26 in the normal deterministic stage test job.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const read=path=>fs.readFileSync(path,'utf8');
const manifest=JSON.parse(read('docs/staging/race-sim-manifest-v1.json'));
function mockCanvas(){
 return new Proxy({},{get(target,key){
  if(key in target)return target[key];
  if(key==='canvas')return null;
  return ()=>{};
 },set(target,key,value){target[key]=value;return true;}});
}
async function main(){
 const url='https://toodataa-ai.github.io/keiba-notes/staging/race-simulator.html?demo=shuka-one';
 const dom=new JSDOM(read('docs/staging/race-simulator.html'),{url,runScripts:'outside-only'});
 const w=dom.window;
 let animation=null;
 w.requestAnimationFrame=fn=>{animation=fn;return 1;};
 w.cancelAnimationFrame=()=>{animation=null;};
 w.HTMLCanvasElement.prototype.getContext=mockCanvas;
 w.HTMLElement.prototype.scrollIntoView=function(){};
 const calls=[];
 w.fetch=async u=>{
  calls.push(String(u));
  assert.equal(String(u),'race-sim-manifest-v1.json',
   'demo should never load JRA prediction registry, race report, or results');
  return {ok:true,status:200,json:async()=>manifest};
 };
 for(const name of ['race-course-geometry-v1.js','race-lane-ai-v1.js',
  'race-runner-style-v1.js','race-ability-model-v1.js',
  'race-umapot-overlay-v1.js','race-sim-engine.js','race-simulator.js'])
  w.eval(read('docs/staging/'+name));
 // initialize() awaits the registry, then loadRace() handles demo synchronously.
 for(let i=0;i<20;i++)await Promise.resolve();
 const el=id=>w.document.getElementById(id);
 assert.equal(calls.length,1,'fixture must not retrieve a real pre-race report');
 assert.ok(el('singleDemoNotice')&&!el('singleDemoNotice').hidden);
 assert.equal(el('raceSelect').value,'stage-shuka-inner-one-runner-demo-v1');
 assert.equal(el('genericCourseMap').hidden,true,
  'Shuka must no longer display its hand-drawn approximate map');
 assert.equal(el('kyotoRealCourseMap').hidden,false,
  'Shuka shares the real original Kyoto map with outer 1400m');
 assert.equal(el('kyotoCourseImage').getAttribute('src'),
  'https://umapot.com/data/powerpoint/kyoto_couse/kyoto_couse_1.jpg');
 assert.equal(el('kyotoCourseOverlay').hidden,false);
 const kyoto=w.RaceCourseGeometry.get('kyoto_turf_inner_2000');
 assert.equal(w.RaceUmapotOverlay.validate(kyoto),true);
 for(const distance of [0,100,308.7,530,720,1000,1435,1671.6,2000]){
  const p=w.RaceUmapotOverlay.point(kyoto,distance,0);
  assert.ok(p.x>28&&p.x<590&&p.y>86&&p.y<351,
   'runner remains registered on actual Kyoto bitmap '+distance);
 }
 assert.equal(el('tokyoRealCourseMap').hidden,true);
 assert.equal(el('startBtn').disabled,false);
 assert.equal(w.document.querySelectorAll('.standing-row').length,1);
 assert.match(el('sourceInfo').textContent,/仮1頭デモ/);
 assert.match(el('raceMeta').textContent,/非公式・仮1頭/);
 assert.match(el('paceDynamics').textContent,/競り合いなし/);
 assert.equal(el('remaining').textContent,'2000 m');
 el('startBtn').click();
 assert.ok(animation,'existing Start button must schedule race animation');
 let n=0,t=0,mid=0,highest=0;
 while(animation&&n++<1500){
  const fn=animation;
  animation=null;
  t+=100;
  fn(t);
  const remaining=Number(el('remaining').textContent.replace(/[^0-9]/g,''));
  if(remaining<1000&&remaining>0)mid++;
  highest=Math.max(highest,Number(el('lap').textContent.replace('%',''))||0);
 }
 assert.ok(n>400&&n<1500,'existing playback should finish promptly');
 assert.ok(mid>15,'horse advanced through second half');
 assert.equal(highest,100,'race should reach finish');
 assert.equal(el('kyotoRealCourseMap').hidden,false,'original map stays on for entire run');
 assert.equal(el('genericCourseMap').hidden,true,'generic map stays off');
 assert.equal(el('remaining').textContent,'0 m');
 assert.ok(el('splitTime').hidden===false,'1000m split should persist after finish');
 assert.match(el('podium').textContent,/試走完了/);
 assert.equal(w.document.querySelectorAll('.standing-row').length,1);
 assert.match(el('moment').textContent,/仮1頭が完走/);
 assert.match(el('sourceInfo').textContent,/予想、買い目、結果には一切使用しません/);
 assert.equal(el('singleDemoNotice').hidden,false);
 assert.equal(calls.length,1,'must remain disconnected from real JRA races');
 // Normal replay state management works with a single runner.
 el('restartBtn').click();
 assert.ok(animation,'Restart remains available');
 assert.equal(el('remaining').textContent,'2000 m');
 w.close();
 console.log('PASS_STAGE_SHUKA_SINGLE_HORSE_REAL_UI_START_PAUSE_GOAL_OVERLAY_NO_REPORT_FETCH');
}
main().catch(e=>{console.error(e);process.exit(1)});
