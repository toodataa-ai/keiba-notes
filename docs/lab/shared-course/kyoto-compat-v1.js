/* Compatibility descriptor: preserves the audited Kyoto spline/mask/physics. */
(function(g){'use strict';
const freeze=x=>{if(x&&typeof x==='object'){Object.values(x).forEach(freeze);Object.freeze(x);}return x;};
const spec=freeze({schemaVersion:1,id:'kyoto_turf_inner_2000',blueprintId:'kyoto_turf_inner_A',
 label:'京都 芝2000m 内回り A',distanceM:2000,turn:'右',maxLane:14,
 source:{url:'assets/kyoto-umapot-course-clean-v8.svg',width:620,height:430,
  attribution:'うまぽっと',reference:'https://umapot.com/?p=13277',accuracy:'illustration'},
 anchorsM:[0,308.7,530,720,1270,1435,1671.6,2000],
 camera:{goalSpanM:100,legacyGoalSpanM:290},
 status:{geometry:'legacy_audited',visualApproval:false,productionApproval:false},
 adapter:'kyoto-compat-v1'});
const requested=new URLSearchParams(g.location?.search||'').get('course');
if(requested&&requested!==spec.id)throw Error('COURSE_UNAVAILABLE:'+requested);
g.RaceSharedCourse=Object.freeze({active:spec,catalog:Object.freeze([spec])});
})(typeof window==='undefined'?globalThis:window);
