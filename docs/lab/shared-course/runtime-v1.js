/* One engine/renderer contract; Kyoto delegates exact legacy C1 + source mask. */
(function(g){'use strict';
function create(blueprint,spec,adapters={}){
 g.RaceCourseValidator.validate(blueprint,spec);
 const freeze=g.RaceCourseValidator.freeze;
 blueprint=freeze(JSON.parse(JSON.stringify(blueprint)));spec=freeze(JSON.parse(JSON.stringify(spec)));
 // Compatibility data is validated but is never used to recalculate Kyoto
 // physical metrics or its pixel mask. Both APIs remain bit-identical.
 let graph=null;
 if(spec.adapter==='graph-v1')graph=g.RaceRouteGraph.compile(blueprint,spec);
 const legacy=spec.adapter==='kyoto-compat-v1'?adapters.legacy:null;
 if(!graph&&(!legacy?.model||!legacy?.turf||!legacy?.geometry))throw Error('COURSE_ADAPTER_MISSING');
 if(legacy&&(legacy.model.id!==spec.id||legacy.model.distance!==spec.distanceM))throw Error('COURSE_ADAPTER_MISMATCH');
 function check(d,lane){
  if(!Number.isFinite(d)||d<0||d>spec.distanceM+spec.runoff.distanceM||!Number.isFinite(lane)||lane<0||lane>spec.mask.maxLane)throw Error('COURSE_POSITION_RANGE:'+JSON.stringify({d,lane,maxD:spec.distanceM+spec.runoff.distanceM,maxLane:spec.mask.maxLane}));
 }
 function position(d,lane=0){check(d,lane);if(legacy)return legacy.turf.point(d,lane);
 const edge=graph.blueprint.edges.find(e=>e.id===graph.rails(d).edgeId);
 const p=graph.position(d,Math.min(.95,(1.8+lane*1.65)/edge.widthM));
 return {x:p.x*blueprint.source.width,y:p.y*blueprint.source.height,d,lane,section:graph.section(d).name};}
 function rails(d){check(d,0);if(legacy){
  if(d<=spec.distanceM)return legacy.model.rails(d);
  const end=legacy.model.rails(spec.distanceM),before=legacy.model.rails(spec.distanceM-10),extra=d-spec.distanceM;
  const extend=key=>({x:end[key].x+(end[key].x-before[key].x)/10*extra,y:end[key].y+(end[key].y-before[key].y)/10*extra});
  return {...end,inner:extend('inner'),outer:extend('outer')};
 }const r=graph.rails(d);return {...r,inner:{x:r.inner.x*blueprint.source.width,y:r.inner.y*blueprint.source.height},outer:{x:r.outer.x*blueprint.source.width,y:r.outer.y*blueprint.source.height}};}
 function tangent(d,lane=0){check(d,lane);const a=position(Math.max(0,d-.01),lane),b=position(Math.min(spec.distanceM+spec.runoff.distanceM,d+.01),lane),n=Math.hypot(b.x-a.x,b.y-a.y);return {x:(b.x-a.x)/n,y:(b.y-a.y)/n};}
 function section(d){check(d,0);return legacy?legacy.model.segment(Math.min(spec.distanceM,d)):graph.section(d);}
 const geometry=legacy?legacy.geometry:graph.geometry;
 const model=legacy?legacy.model:Object.freeze({id:spec.id,distance:spec.distanceM,sections:spec.sections,
  widthMetres:Math.min(...blueprint.edges.map(e=>e.widthM)),widthPx:27,sourceImageSize:{width:blueprint.source.width,height:blueprint.source.height},
  center:d=>{const p=position(d,0),t=tangent(d),x=t.x,y=t.y,n=Math.hypot(x,y);return {...p,tx:x/n,ty:y/n,section:section(d).name};},
  rails,point:position,segment:section,fraction:lane=>Math.min(.95,(1.8+lane*1.65)/Math.min(...blueprint.edges.map(e=>e.widthM)))});
 function simulate(data,options={}){
  if(data.course_id!==spec.id||data.distance_m!==spec.distanceM||data.turn!==blueprint.turn||data.venue!==blueprint.venue)throw Error('COURSE_ENTRY_MISMATCH');
  return g.RaceSimEngine.create(data,{...options,courseRuntime:{geometry,runoffM:spec.runoff.finishThresholdM,goalBeforeM:spec.camera.switchBeforeM}});
 }
 return Object.freeze({id:spec.id,spec:freeze(JSON.parse(JSON.stringify(spec))),blueprint:freeze(JSON.parse(JSON.stringify(blueprint))),position,rails,tangent,section,
  grade:d=>legacy?geometry.slope(geometry.get(spec.id),d):graph.grade(d),simulate,
  runners:state=>state.horses.map(h=>({number:h.number,d:h.displayD??h.d,lane:h.lane,...position(h.displayD??h.d,h.lane),finished:h.finished})),
  physicalGeometry:geometry,model,graph});
}
g.RaceCourseRuntime=Object.freeze({create});
})(typeof window==='undefined'?globalThis:window);
