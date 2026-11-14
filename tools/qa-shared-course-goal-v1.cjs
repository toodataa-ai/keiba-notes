const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),out=process.env.COURSE_GOAL_QA_OUT||'/tmp/keiba-pr1-goal';fs.mkdirSync(out,{recursive:true});
(async()=>{
 const b=await chromium.launch({...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:fs.existsSync('/usr/bin/chromium')?{executablePath:'/usr/bin/chromium'}:{}),headless:true,args:['--no-sandbox']});const rows=[];
 try{
 for(const width of [390,1024])for(const field of [2,6,18])for(const speed of [1,2,4]){
  const p=await b.newPage({viewport:{width,height:900},deviceScaleFactor:2});const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.route('**/*',r=>{const u=new URL(r.request().url());if(u.hostname!=='lab.test')return r.abort();const f=path.resolve(root,'.'+u.pathname);if(!f.startsWith(root+'/')||!fs.existsSync(f))return r.fulfill({status:404,body:''});return r.fulfill({contentType:{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[path.extname(f)]||'text/plain',body:fs.readFileSync(f)});});
  await p.clock.install();await p.goto(`http://lab.test/docs/lab/race-clean-course-v1.html?field=${field}&speed=${speed}&checkpoint=1920`);
  await p.waitForFunction(()=>CleanLab.inspect().sharedGeometryEnabled);
  assert.equal(await p.evaluate(()=>CleanLab.inspect().goalFrame.visible),0);
  await p.locator('#startBtn').click();let wire=new Set(),inFrame=new Set(),done=false;
  const xs=new Map();let backward=0;
  for(let i=0;i<1000;i++){
   await p.clock.runFor(160);
   const s=await p.evaluate(()=>{const a=CleanLab.inspect();return {goal:a.goalFrame,done:a.finishSequenceDone,state:CleanLab.getState().finished,podium:a.podiumNames,rows:a.allResultRows};});
   for(const marker of s.goal.markers){
    inFrame.add(marker.number);if(marker.d>=2000)wire.add(marker.number);
    const old=xs.get(marker.number);if(!s.state&&old!==undefined&&marker.x>old+.01)backward++;xs.set(marker.number,marker.x);
   }
   if(s.done){assert(s.state);assert.equal(s.rows,field);assert(s.podium.includes('1着'));if(field>=3)assert(s.podium.includes('3着'));done=true;break;}
  }
  assert(done);assert.equal(inFrame.size,field);assert.equal(wire.size,field);assert.equal(backward,0);assert.deepEqual(errors,[]);
  if(speed===2)await p.locator('#broadcastStage').screenshot({path:path.join(out,`${width}-${field}-goal-complete.png`)});
  rows.push({width,field,speed,entered:inFrame.size,wireCrossings:wire.size,backward,finished:true});await p.close();console.log('PASS_GOAL_ENTRY_WIRE_ALL_FINISH',width,field,speed);
 }
 }finally{await b.close();fs.writeFileSync(path.join(out,'goal.json'),JSON.stringify({rows},null,2)+'\n');}
})().catch(e=>{console.error(e);process.exitCode=1;});
