/* Exact comparison within Chromium; Math implementations can differ from Node. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),base=path.resolve(process.argv[2]),target=process.argv[3];
const names=['race-course-geometry-v1','race-lane-ai-v1','race-runner-style-v1','race-ability-model-v1','race-cohort-speed-v1','race-sim-engine','race-lab-18-fixture-v1','race-real-shuka-2026-fixture-v1','race-clean-course-v1'];
const sources=dir=>names.map(n=>fs.readFileSync(dir+'/docs/lab/'+n+'.js','utf8'));
(async()=>{const browser=await chromium.launch({...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:fs.existsSync('/usr/bin/chromium')?{executablePath:'/usr/bin/chromium'}:{}),headless:true,args:['--no-sandbox']});
try{
 const p=await browser.newPage();
 const states=await p.evaluate(({oldSources,newSources,shared})=>{
  const load=sources=>{const c={};for(const code of sources)new Function('window','globalThis',code)(c,c);return c;};
  const old=load(oldSources),modern=load(newSources);
  for(const code of shared)new Function('window','globalThis',code)(modern,modern);
  modern.RaceCleanTurf=modern.RaceCleanCourse;const runtime=modern.RaceSharedCourse.createRuntime();
  const run=(c,mode,scale,seed,adapter)=>{
   const f=mode==='real17'?c.RaceRealShuka2026Fixture:c.RaceLab18Fixture,horses=f.horses({abilityScale:scale}).slice(0,mode==='small6'?6:18);
   const data={...f.entry(),horses,field_size:horses.length,...(scale==='90-v1'?{labAbilityScale:scale}:{})};
   const engine=adapter?runtime.simulate(data,{seed,bias:'neutral'}):c.RaceSimEngine.create(data,{seed,bias:'neutral'});
   for(let i=0;i<6000&&!engine.state.finished;i++)engine.step(.08);if(!engine.state.finished)throw Error('unfinished');return JSON.parse(JSON.stringify(engine.state));
  };
  const out=[];
  for(const mode of ['small6','synthetic18','real17'])for(const seed of [2026,1,75])for(const scale of mode==='small6'?['90-v1']:['90-v1','legacy-50'])out.push({mode,seed,scale,before:run(old,mode,scale,seed),after:run(modern,mode,scale,seed,true)});
  return out;
 },{oldSources:sources(base),newSources:sources(root),shared:['definitions-v1','validator-v1','route-graph-v1','runtime-v1','kyoto-compat-v1'].map(n=>fs.readFileSync(root+'/docs/lab/shared-course/'+n+'.js','utf8'))});
 const result=JSON.parse(fs.readFileSync(target,'utf8'));result.browserExpected={};result.browserVersion=browser.version();result.browserExactCases=[];
 for(const row of states){assert.deepEqual(row.after,row.before);const hash=crypto.createHash('sha256').update(JSON.stringify(row.before)).digest('hex');if(row.scale==='90-v1')result.browserExpected[row.mode+'-'+row.seed]=hash;result.browserExactCases.push({mode:row.mode,seed:row.seed,scale:row.scale,exact:true,hash});}
 fs.writeFileSync(target,JSON.stringify(result,null,2)+'\n');console.log('PASS_BROWSER_BASELINE_EXACT',result.browserExactCases.length,browser.version());
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
