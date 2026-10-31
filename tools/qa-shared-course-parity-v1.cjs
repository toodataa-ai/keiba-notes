/* Fixed compatibility baseline. Existing compare test remains unchanged. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),base=path.resolve(process.argv[2]||''),out=process.argv[3]||'/tmp/keiba-pr1-baseline.json';
const load=dir=>{const c=vm.createContext({URLSearchParams});for(const name of ['race-course-geometry-v1','race-lane-ai-v1','race-runner-style-v1','race-ability-model-v1','race-cohort-speed-v1','race-sim-engine','race-lab-18-fixture-v1','race-real-shuka-2026-fixture-v1','race-clean-course-v1'])vm.runInContext(fs.readFileSync(dir+'/docs/lab/'+name+'.js','utf8'),c);return c;};
const old=load(base),modern=load(root),json=x=>JSON.parse(JSON.stringify(x));
for(const n of ['definitions-v1','validator-v1','route-graph-v1','runtime-v1','kyoto-compat-v1'])vm.runInContext(fs.readFileSync(root+'/docs/lab/shared-course/'+n+'.js','utf8'),modern);
// Numerical adapter test delegates the original C1 raw-coordinate API. The
// separately run browser tests exercise the actual SVG-derived pixel mask.
modern.RaceCleanTurf=modern.RaceCleanCourse;
const runtime=modern.RaceSharedCourse.createRuntime();
const final=(c,mode,scale,seed,useRuntime=false)=>{
 const f=mode==='real17'?c.RaceRealShuka2026Fixture:c.RaceLab18Fixture;
 const horses=f.horses({abilityScale:scale}).slice(0,mode==='small6'?6:18);
 const data={...f.entry(),horses,field_size:horses.length,...(scale==='90-v1'?{labAbilityScale:scale}:{})};
 const engine=useRuntime?runtime.simulate(data,{seed,bias:'neutral'}):c.RaceSimEngine.create(data,{seed,bias:'neutral'});
 for(let i=0;i<6000&&!engine.state.finished;i++)engine.step(.08);
 assert(engine.state.finished);return json(engine.state);
};
const result={baseline:'c653c23fc7d80745dce08e32b890cb92a846e2eb',cases:[],nodeExpected:{},rawPositions:0};
for(const mode of ['synthetic18','real17'])for(const scale of ['90-v1','legacy-50'])for(const seed of [2026,1,75]){
 const expected=final(old,mode,scale,seed),actual=final(modern,mode,scale,seed,true);
 assert.deepEqual(actual,expected);assert.deepEqual(actual,final(modern,mode,scale,seed,true));
 result.cases.push({mode,scale,seed,exact:true,finalHash:crypto.createHash('sha256').update(JSON.stringify(expected)).digest('hex')});
}
for(let d=0;d<=2000;d++)for(let lane=0;lane<=14;lane++){
 assert.deepEqual(json(runtime.position(d,lane)),json(old.RaceCleanCourse.point(d,lane)));result.rawPositions++;
}
for(const mode of ['small6','synthetic18','real17'])for(const seed of [2026,1,75]){
 const expected=final(old,mode,'90-v1',seed);
 result.nodeExpected[mode+'-'+seed]=crypto.createHash('sha256').update(JSON.stringify(expected)).digest('hex');
}
fs.writeFileSync(out,JSON.stringify(result,null,2)+'\n');
console.log('PASS_COMPATIBILITY_ADAPTER_12_FINAL_STATES_AND_30015_COORDINATES',out);
