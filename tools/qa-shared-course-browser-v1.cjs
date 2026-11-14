/* Browser evidence. Fixed clock for exhaustive matrix; optional wall-clock full replays. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),out=path.resolve(process.env.COURSE_QA_OUT||'/tmp/keiba-pr1-qa');
const wall=process.argv.includes('--realtime');fs.mkdirSync(out,{recursive:true});
const resume=process.argv.includes('--resume');
const previous=resume?JSON.parse(fs.readFileSync(path.join(out,wall?'realtime.json':'matrix.json'),'utf8')):null;
const rows=previous?.rows||[];const summary={mode:wall?'wall-clock requestAnimationFrame':'controlled browser clock requestAnimationFrame',rows,visualReview:'not performed by user',priorHarnessErrors:previous?.errors||[],errors:[]};
const stable=x=>JSON.stringify(x);
const hash=x=>crypto.createHash('sha256').update(stable(x)).digest('hex');
(async()=>{
const browser=await chromium.launch({...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:fs.existsSync('/usr/bin/chromium')?{executablePath:'/usr/bin/chromium'}:{}),headless:true,args:['--no-sandbox','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']});
async function pageFor(width,query){
 const page=await browser.newPage({viewport:{width,height:900},deviceScaleFactor:2});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>{
  const u=new URL(route.request().url());if(u.hostname!=='lab.test')return route.abort();
  const p=path.resolve(root,'.'+decodeURIComponent(u.pathname));
  if(!p.startsWith(root+path.sep)||!fs.existsSync(p)||!fs.statSync(p).isFile())return route.fulfill({status:404,body:''});
  return route.fulfill({contentType:{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[path.extname(p)]||'text/plain',body:fs.readFileSync(p)});
 });
 if(!wall)await page.clock.install();
 await page.goto('http://lab.test/docs/lab/race-clean-course-v1.html?'+query);
 await page.waitForFunction(()=>window.CleanLab?.inspect().sharedGeometryEnabled,{timeout:30000});
 return {page,errors};
}
const view=page=>page.evaluate(()=>{
 const state=CleanLab.getState(),a=CleanLab.inspect();
 const svg=document.getElementById('liveCourseImage'),matrix=new DOMMatrix(getComputedStyle(svg).transform);
 const overview=document.getElementById('overview').getBoundingClientRect();
 const actual=RaceCleanTurf.runners(state);
 return {t:state.t,leader:state.leader,positions:a.positions,field:state.horses.length,
  overflow:document.documentElement.scrollWidth>innerWidth,goal:a.goalFrame,goalVisible:a.goalBoardVisible,
  clock:a.broadcastClock,split:a.splitClock,rows:a.allResultRows,results:a.resultsVisible,podium:a.podiumNames,
  finishDone:a.finishSequenceDone,finished:state.finished,allCrossed:state.allCrossedAt,
  turfBad:a.turfBadCenters,discsBad:a.turfBadDiscs,directError:a.directMarkerMaxError,radiusSpread:a.markerRadiusSpreadPx,
  touching:a.touchingPairs,severe:a.severeOverlapPairs,labels:a.liveLabelPositions,
  inside4:state.horses.filter(h=>h.lane<=3.45).length,maxLane:Math.max(...state.horses.map(h=>h.lane)),
  goalTouching:a.goalFrame?.markers.reduce((n,a,i,all)=>n+all.slice(i+1).filter(b=>Math.hypot(a.x-b.x,a.y-b.y)<21.87).length,0)??0,
  affine:{a:matrix.a,b:matrix.b,c:matrix.c,d:matrix.d},aspect:overview.width/overview.height,
  synchronizationMaxError:Math.max(...actual.map(p=>{const q=RaceCleanTurf.point(p.d,p.lane);return Math.hypot(p.x-q.x,p.y-q.y)})),
  waku:state.horses.map(h=>({number:h.number,...CleanLab.waku(h.number,state.horses.length)})),
  marker18:a.positions.find(p=>p.number===18)||null,
  physical:JSON.parse(JSON.stringify(state)),settings:CleanLab.settings()};
});
function verify(s){
 assert(!s.overflow);assert.equal(s.turfBad,0);assert.equal(s.discsBad,0);
 assert.equal(s.directError,0);assert.equal(s.radiusSpread,0);assert.equal(s.synchronizationMaxError,0);
 assert(Math.abs(s.affine.a-s.affine.d)<1e-8&&s.affine.b===0&&s.affine.c===0);
 assert(Math.abs(s.aspect-620/430)<.03);assert(s.positions.every(p=>p.lane>=0&&p.lane<=14));
 if(s.marker18)assert(s.marker18.lane<=14);
 assert(s.waku.every(w=>w.waku>=1&&w.waku<=8));
 if(s.field===18){assert.equal(s.waku[17].waku,8);assert.equal(s.waku[17].fill,'#f4a1c5');}
}
async function run(width,mode,seed,speed){
 const query=new URLSearchParams({trial:mode==='real17'?'shuka2026':'synthetic',field:mode==='small6'?'6':'18',seed:String(seed),speed:String(speed)});
 const {page,errors}=await pageFor(width,query),samples=[];
 const name=`${width}-${mode}-${seed}-${speed}x`;
 const screenshots=seed===2026&&speed===2;
 const start=Date.now();let lastD=-1,sawEntry=false,sawWire=false;const wireCrossings=new Set();
 try{
  const initial=await view(page);verify(initial);samples.push({...initial,physicalHash:hash(initial.physical),physical:undefined});
  if(screenshots){await page.locator('#broadcastStage').screenshot({path:path.join(out,name+'-start.png')});await page.screenshot({path:path.join(out,name+'-controls.png')});}
  await page.locator('#startBtn').click();
  const checkpoints=[1270,1672,1920,2000,Infinity];let next=0;
  // Sample real playback rather than seeking; all checkpoint states belong
  // to this one uninterrupted run. No engine stepping from the test.
  for(let i=0;i<10000;i++){
   if(wall)await page.waitForTimeout(80);else await page.clock.runFor(160);
   const brief=await page.evaluate(()=>({d:CleanLab.getState().leader,done:CleanLab.inspect().finishSequenceDone,goal:CleanLab.inspect().goalFrame}));
   if(brief.goal?.visible===0)sawEntry=true;
   for(const marker of brief.goal?.markers||[]){if(marker.d>=2000){sawWire=true;wireCrossings.add(marker.number);}}
   if(brief.d>=checkpoints[next]||brief.done){
    const s=await view(page);verify(s);assert(s.leader>=lastD);lastD=s.leader;
    samples.push({...s,physicalHash:hash(s.physical),physical:undefined});
    if(s.goalVisible&&s.goal?.visible===0)sawEntry=true;
    if(s.goal?.markers.some(p=>p.d>=2000))sawWire=true;
    if(screenshots){await page.locator('#broadcastStage').screenshot({path:path.join(out,name+'-'+(brief.done?'finished':checkpoints[next])+'m.png')});await page.locator('.race-overview-view').screenshot({path:path.join(out,name+'-'+(brief.done?'finished':checkpoints[next])+'m-overview.png')});}
    if(brief.done)break;next++;
   }
   if(wall&&Date.now()-start>240000)throw Error('wall-clock timeout '+name);
  }
  const final=await view(page);verify(final);assert(final.finished&&final.finishDone);assert.equal(final.rows,final.field);assert(final.results);assert(final.podium.includes('1着')&&final.podium.includes('3着'));
  assert.equal(errors.length,0,errors.join('\n'));assert(sawEntry);assert(sawWire);assert.equal(wireCrossings.size,final.field);
  rows.push({width,mode,seed,speed,elapsedWallMs:Date.now()-start,finalPhysicalHash:hash(final.physical),order:final.physical.horses.slice().sort((a,b)=>a.finishTime-b.finishTime).map(h=>h.number),samples,sawEntry,sawWire,wireCrossings:[...wireCrossings]});
  console.log('PASS_BROWSER_MATRIX',name,Date.now()-start);
  return final.physical;
 }finally{await page.close();fs.writeFileSync(path.join(out,wall?'realtime.json':'matrix.json'),JSON.stringify(summary,null,2)+'\n');}
}
try{
 const cases=[];
 for(const width of [390,1024])for(const mode of ['small6','synthetic18','real17'])for(const seed of (wall?[2026]:[2026,1,75]))cases.push({width,mode,seed});
 // Each batch checks 1/2/4 on the same input. Bounded concurrency avoids
 // hiding wall-clock frame starvation behind an accelerated test hook.
 for(let i=0;i<cases.length;i+=2){
  await Promise.all(cases.slice(i,i+2).map(async c=>{
   if(resume&&[1,2,4].every(speed=>rows.some(r=>r.width===c.width&&r.mode===c.mode&&r.seed===c.seed&&r.speed===speed)))return;
   const states=await Promise.all([1,2,4].map(speed=>run(c.width,c.mode,c.seed,speed)));
   assert.deepEqual(states[0],states[1]);assert.deepEqual(states[0],states[2]);
  }));
 }
 // UI changes construct a new race; sealed real17 remains fixed at 17.
 const {page,errors}=await pageFor(390,'');
 await page.selectOption('#fieldSize','6');assert.equal(await page.evaluate(()=>CleanLab.getState().horses.length),6);
 await page.fill('#seed','75');await page.locator('#seed').dispatchEvent('change');assert.equal(await page.evaluate(()=>CleanLab.getState().seed),75);
 await page.selectOption('#trialMode','shuka2026');assert(await page.locator('#fieldSize').isDisabled());assert.equal(await page.evaluate(()=>CleanLab.getState().horses.length),17);
 assert.equal(await page.locator('#surfaceSelect option[value=dirt]').evaluate(el=>el.disabled&&el.matches(':disabled')),true);
 assert.equal(await page.locator('#distanceSelect option[value="1400"]').evaluate(el=>el.disabled&&el.matches(':disabled')),true);
 assert.equal(await page.locator('#courseSelect option:not([disabled])').count(),1);
 assert.equal(errors.length,0);summary.uiControlsVerified=true;await page.screenshot({path:path.join(out,'controls-390.png')});await page.close();
}catch(e){summary.errors.push(String(e.stack));throw e;}
finally{await browser.close();fs.writeFileSync(path.join(out,wall?'realtime.json':'matrix.json'),JSON.stringify(summary,null,2)+'\n');}
})().catch(e=>{console.error(e);process.exitCode=1;});
