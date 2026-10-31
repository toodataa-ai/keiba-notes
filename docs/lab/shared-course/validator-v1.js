/* Strict validation for the checked-in JSON Schema vocabulary + route invariants. */
(function(g){'use strict';
const error=(p,m)=>{throw Error('COURSE_INVALID '+p+': '+m);};
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
function schema(value,s,path='$'){
 if(s===false)error(path,'extra item');
 if(s.const!==undefined&&value!==s.const)error(path,'const');
 if(s.enum&&!s.enum.includes(value))error(path,'enum');
 if(s.type){
  const ok=s.type==='object'?object(value):s.type==='array'?Array.isArray(value):s.type==='integer'?Number.isInteger(value):s.type==='number'?Number.isFinite(value):typeof value===s.type;
  if(!ok)error(path,'expected '+s.type);
 }
 if(typeof value==='number'){
  if(!Number.isFinite(value))error(path,'finite required');
  if(s.minimum!==undefined&&value<s.minimum||s.maximum!==undefined&&value>s.maximum)error(path,'bounds');
 }
 if(typeof value==='string'){
  if(s.minLength&&value.length<s.minLength||s.pattern&&!new RegExp(s.pattern).test(value))error(path,'string');
 }
 if(Array.isArray(value)){
  if(s.minItems!==undefined&&value.length<s.minItems||s.maxItems!==undefined&&value.length>s.maxItems)error(path,'array length');
  value.forEach((x,i)=>schema(x,s.prefixItems?.[i]??s.items,path+'['+i+']'));
 }
 if(object(value)){
  for(const key of s.required||[])if(!Object.hasOwn(value,key))error(path+'.'+key,'required');
  for(const key of Object.keys(value)){
   if(!Object.hasOwn(s.properties||{},key)){if(s.additionalProperties===false)error(path+'.'+key,'unknown property');}
   else schema(value[key],s.properties[key],path+'.'+key);
  }
 }
 return true;
}
const close=(a,b)=>Math.abs(a-b)<1e-7;
function validate(blueprint,spec){
 schema(blueprint,g.RaceCourseSchemas.blueprint);schema(spec,g.RaceCourseSchemas.spec);
 if(!/^assets\/[a-zA-Z0-9_./-]+\.(svg|png|jpe?g|webp)$/.test(blueprint.source.url)||blueprint.source.url.includes('..'))error('source.url','local image asset path required');
 if(blueprint.id!==spec.blueprintId)error('blueprintId','mismatch');
 const unique=(values,p)=>{if(new Set(values).size!==values.length)error(p,'duplicate');};
 unique(blueprint.nodes,'nodes');unique(blueprint.edges.map(e=>e.id),'edges');
 const nodes=new Set(blueprint.nodes),edges=new Map(blueprint.edges.map(e=>[e.id,e]));
 for(const e of blueprint.edges){
  if(!nodes.has(e.from)||!nodes.has(e.to))error(e.id,'unknown node');
  for(const [list,key] of [[e.rails,'rails'],[e.gradeProfile,'grade']]){
   if(list[0][0]!==0||!close(list.at(-1)[0],e.lengthM))error(e.id+'.'+key,'endpoint');
   for(let i=1;i<list.length;i++)if(list[i][0]<=list[i-1][0])error(e.id+'.'+key,'order');
  }
  for(const r of e.rails)if(Math.hypot(r[1]-r[3],r[2]-r[4])<1e-7)error(e.id,'zero width');
 }
 const legs=ids=>ids.map(id=>{const e=edges.get(id);if(!e)error(id,'unknown edge');return e;});
 const race=legs(spec.edgeIds),runoff=legs(spec.runoff.edgeIds);
 const chain=(list,p)=>{
  for(let i=1;i<list.length;i++){
   const a=list[i-1],b=list[i];
   if(a.to!==b.from)error(p,'disconnected nodes');
   if(a.rails.at(-1).slice(1).some((v,j)=>!close(v,b.rails[0][j+1])))error(p,'disconnected rails');
  }
 };
 chain(race,'race');chain(runoff,'runoff');
 if(spec.startOffsetM>=race[0].lengthM||spec.endOffsetM>=race.at(-1).lengthM)error('offset','out of edge');
 if(!close(race.reduce((n,e)=>n+e.lengthM,0)-spec.startOffsetM-spec.endOffsetM,spec.distanceM))error('distanceM','route length');
 if(spec.endOffsetM!==0)error('endOffsetM','runoff must start at an explicit goal node; split edge at goal');
 chain([race.at(-1),runoff[0]],'goal/runoff');
 if(!close(runoff.reduce((n,e)=>n+e.lengthM,0),spec.runoff.distanceM))error('runoff','length');
 if(spec.runoff.displayExtraM+spec.runoff.finishThresholdM>spec.runoff.distanceM)error('runoff','coast length');
 if(spec.anchorsM[0]!==0||spec.anchorsM.at(-1)!==spec.distanceM)error('anchorsM','endpoints');
 for(let i=1;i<spec.anchorsM.length;i++)if(spec.anchorsM[i]<=spec.anchorsM[i-1])error('anchorsM','order');
 let end=0;
 for(const section of spec.sections){if(!close(section.from,end)||section.to<=section.from)error('sections','gap/order');end=section.to;}
 if(!close(end,spec.distanceM)||spec.finalStraightM>spec.distanceM)error('sections','length');
 if(!close(spec.sections.at(-1).from,spec.distanceM-spec.finalStraightM)||spec.sections.at(-1).kind!=='straight')error('finalStraightM','section mismatch');
 if(race[0].surface!==spec.surface)error('surface','start mismatch');
 const expectedLane=Math.min(18,Math.max(7,Math.floor((Math.min(...race.map(e=>e.widthM))-3.6)/1.65)));
 if(spec.mask.maxLane!==expectedLane)error('mask.maxLane','physical lane configuration mismatch');
 if(blueprint.turn==='直線'&&race.some(e=>e.kind==='turn'||e.bend!==0))error('turn','straight course has a bend');
 const legacy=spec.mask.legacyCalibration.turnAnchorsM;
 if(legacy.some((v,i)=>v>spec.distanceM||i&&v<=legacy[i-1]))error('mask.legacyCalibration','anchor extent/order');
 const camera=spec.camera,lens=camera.lens,N=spec.distanceM-camera.switchBeforeM;
 if(N<=0||camera.focusLane>spec.mask.maxLane||lens.lane>spec.mask.maxLane||lens.referenceToM>N||lens.referenceFromM>=lens.referenceToM)error('camera','invalid calibration extent');
 for(const extent of Object.values(lens.metrics))if(extent[0]>=extent[1]||extent[1]>N)error('camera.metrics','extent');
 if(spec.status.productionApproval)error('status','PR1 does not grant production approval');
 return true;
}
const freeze=x=>{if(x&&typeof x==='object'){Object.values(x).forEach(freeze);Object.freeze(x);}return x;};
g.RaceCourseValidator=Object.freeze({schema,validate,freeze});
})(typeof window==='undefined'?globalThis:window);
