const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {fixture,clone}=require('./lib/shared-course-fixture-v1.cjs');
const root=require('node:path').resolve(__dirname,'..');
const context=vm.createContext({URLSearchParams});
for(const n of ['definitions-v1','validator-v1','route-graph-v1','runtime-v1'])vm.runInContext(fs.readFileSync(root+'/docs/lab/shared-course/'+n+'.js','utf8'),context);
for(const n of ['race-course-geometry-v1','race-lane-ai-v1','race-runner-style-v1','race-ability-model-v1','race-cohort-speed-v1','race-sim-engine','race-lab-18-fixture-v1'])vm.runInContext(fs.readFileSync(root+'/docs/lab/'+n+'.js','utf8'),context);
const compile=x=>context.RaceRouteGraph.compile(x.blueprint,x.spec);
const original=fixture();
const mutations=[
 x=>x.spec.distanceM='600',x=>x.spec.extra=true,x=>x.blueprint.extra=true,
 x=>x.blueprint.turn='左',
 x=>x.blueprint.edges[0].rails[1][1]=NaN,x=>x.spec.camera.mobileZoom=Infinity,
 x=>x.spec.blueprintId='missing',x=>x.blueprint.nodes.push('start'),
 x=>x.blueprint.edges[1].id='pocket',x=>x.blueprint.edges[0].from='unknown',
 x=>x.spec.edgeIds[1]='absent',x=>x.blueprint.edges[1].from='start',
 x=>x.blueprint.edges[1].rails[0][1]+=.01,x=>x.spec.distanceM=601,
 x=>x.spec.sections[1].from=101,x=>x.spec.sections[1].to=599,
 x=>x.spec.anchorsM=[0,100,99,600],x=>x.spec.runoff.edgeIds=['pocket'],
 x=>x.spec.runoff.distanceM=39,x=>x.spec.startOffsetM=120,
 x=>x.spec.surface='dirt',x=>x.spec.status.productionApproval=true,
 x=>x.spec.camera.lens.referenceToM=900,x=>x.spec.mask.maxLane='14',
 x=>x.spec.mask.maxLane=18,x=>x.blueprint.source.url='../assets/test.svg',x=>x.spec.mask.legacyCalibration.turnAnchorsM=[200,100,500],
 x=>x.blueprint.edges[0].gradeProfile[1][0]=99,
 x=>x.blueprint.edges[0].rails[1][0]=99,
 x=>x.blueprint.edges[1].rails[1][2]=.28,x=>x.blueprint.edges[1].rails[1][4]=.32,
];
for(const mutate of mutations){const x=clone(original);mutate(x);assert.throws(()=>compile(x));}
const result=[];
for(const loop of [false,true]){
 const data=fixture(loop),before=JSON.stringify(data),graph=compile(data);
 assert.equal(JSON.stringify(data),before);assert(Object.isFrozen(graph.spec));
 for(let d=0;d<=725;d+=.25){
  const p=graph.position(d),r=graph.rails(d),t=graph.tangent(d);
  assert(Number.isFinite(p.x)&&Number.isFinite(p.y)&&Number.isFinite(t.x));
  assert(Math.abs(Math.hypot(t.x,t.y)-1)<1e-8);
  assert.equal(graph.grade(d),0);assert(r.surface==='turf'||r.surface==='dirt');
  if(d)assert(Math.hypot(p.x-graph.position(d-.25).x,p.y-graph.position(d-.25).y)<.01);
 }
 if(loop)assert.deepEqual(graph.position(200),graph.position(400));
 else {assert.equal(graph.rails(99).surface,'turf');assert.equal(graph.rails(100).surface,'dirt');}
 assert.throws(()=>graph.position(726));assert.throws(()=>graph.position(-1));assert.throws(()=>graph.position(0,NaN));
 // Real shared engine consumes graph metrics; no cloned engine or renderer.
 const runtime=context.RaceCourseRuntime.create(data.blueprint,data.spec);
 const testD=loop?175:50,ta=runtime.tangent(testD),pa=runtime.position(testD-.01),pb=runtime.position(testD+.01);
 assert(Math.abs(ta.x*(pb.y-pa.y)-ta.y*(pb.x-pa.x))<1e-10);
 assert.equal(runtime.model.distance,600);assert.equal(runtime.model.id,data.spec.id);assert(Number.isFinite(runtime.model.center(0).tx));
 const f=context.RaceLab18Fixture,race={...f.entry(),id:'structural-test',course_id:data.spec.id,venue:data.blueprint.venue,turn:data.blueprint.turn,distance_m:600,field_size:6,horses:f.horses().slice(0,6)};
 const run=()=>{const engine=runtime.simulate(race,{seed:75});for(let i=0;i<5000&&!engine.state.finished;i++)engine.step(.08);assert(engine.state.finished);assert.equal(engine.state.horses.filter(h=>h.finished).length,6);assert(runtime.runners(engine.state).every(p=>Number.isFinite(p.x)));return JSON.parse(JSON.stringify(engine.state));};
 assert.deepEqual(run(),run());
 const initial=runtime.position(0,0);data.blueprint.edges[0].rails[0][1]=.9;assert.deepEqual(runtime.position(0,0),initial);
 result.push({loop,runners:6,complete:true});
}
const left=fixture(true);left.blueprint.turn='左';for(const e of left.blueprint.edges)for(const k of e.rails){k[2]=1-k[2];k[4]=1-k[4];}
assert.equal(compile(left).geometry.get(left.spec.id).turn,'左');
console.log('PASS_STRICT_SCHEMA_AND_GRAPH_RUNTIME',JSON.stringify({invalidDefinitions:mutations.length,cases:result}));
