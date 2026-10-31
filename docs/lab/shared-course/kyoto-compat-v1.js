/* Registry admits only the existing Kyoto compatibility adapter in PR1. */
(function(g){'use strict';
const {blueprints,specs}=g.RaceCourseDefinitions,validator=g.RaceCourseValidator;
for(const spec of specs){const bp=blueprints.find(b=>b.id===spec.blueprintId);validator.validate(bp,spec);}
validator.freeze(g.RaceCourseDefinitions);validator.freeze(g.RaceCourseSchemas);
const spec=specs[0],blueprint=blueprints.find(b=>b.id===spec.blueprintId);
// No catalog/status edit can unlock a new course: admission requires an
// adapter registered in code after separate review. PR1 contains only Kyoto.
if(spec.id!=='kyoto_turf_inner_2000'||spec.adapter!=='kyoto-compat-v1')throw Error('COURSE_NOT_ADMITTED');
const requested=new URLSearchParams(g.location?.search||'').get('course');
if(requested&&requested!==spec.id)throw Error('COURSE_UNAVAILABLE:'+requested);
const active=validator.freeze({...spec,source:blueprint.source,turn:blueprint.turn,maxLane:spec.mask.maxLane});
g.RaceSharedCourse=Object.freeze({active,catalog:Object.freeze([active]),blueprint,spec,
 createRuntime:()=>g.RaceCourseRuntime.create(blueprint,spec,{legacy:{model:g.RaceCleanCourse,turf:g.RaceCleanTurf,geometry:g.RaceCourseGeometry}})});
})(typeof window==='undefined'?globalThis:window);
