const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const baseline=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const dirs=process.argv.slice(3),result={baseline:baseline.baseline,mandatoryFinalStates:baseline.cases.length,coordinateMatches:baseline.rawPositions,modes:[],humanVisualReview:'pending',permissionForNewPublication:'unconfirmed'};
for(const dir of dirs){
 const name=fs.existsSync(path.join(dir,'realtime.json'))?'realtime.json':'matrix.json';
 const data=JSON.parse(fs.readFileSync(path.join(dir,name),'utf8'));assert.equal(data.errors.length,0);
 const expected=name==='realtime.json'?18:54;assert.equal(data.rows.length,expected);
 const rows=data.rows.map(r=>{
  assert.equal(r.finalPhysicalHash,baseline.browserExpected[r.mode+'-'+r.seed],JSON.stringify({width:r.width,mode:r.mode,seed:r.seed,speed:r.speed}));
  assert.equal(r.samples.length,6);assert(r.samples.at(-1).finishDone);
  return {width:r.width,mode:r.mode,seed:r.seed,speed:r.speed,elapsedWallMs:r.elapsedWallMs,finalPhysicalHash:r.finalPhysicalHash,
   snapshots:r.samples.map((s,i)=>({checkpoint:['start',1270,1672,1920,2000,'finished'][i],leader:s.leader,clock:s.clock,field:s.field,touching:s.touching,severe:s.severe,turfBad:s.turfBad,discsBad:s.discsBad,directError:s.directError,synchronizationMaxError:s.synchronizationMaxError,aspect:s.aspect,marker18:s.marker18,goalVisible:s.goalVisible,goalMarkers:s.goal?.visible??0,rows:s.rows,podium:s.podium,physicalHash:s.physicalHash}))};
 });
 result.modes.push({mode:data.mode,cases:rows.length,rows,screenshots:fs.readdirSync(dir).filter(p=>p.endsWith('.png')).sort().map(name=>({name,sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(dir,name))).digest('hex')}))});
}
const target=path.resolve(__dirname,'../docs/lab/shared-course/QA-RESULTS-PR1.json');fs.writeFileSync(target,JSON.stringify(result,null,2)+'\n');console.log('PASS_EVERY_BROWSER_FINAL_STATE_MATCHES_FIXED_BASELINE',result.modes.map(m=>m.cases));
