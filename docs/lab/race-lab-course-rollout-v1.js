/* Route readiness gate, separate from JRA betting and live production. */
(function(g){'use strict';
const courses=Object.freeze([
 Object.freeze({id:'kyoto_turf_inner_2000',name:'京都 芝2000m 内回り',status:'v26_lab_approved',
  svg:'assets/kyoto-umapot-course-clean-v8.svg',reference:'https://umapot.com/?p=13277'}),
 Object.freeze({id:'kyoto_turf_outer_1400',name:'京都 芝1400m 外回り',status:'pilot_safety_pending',
  svg:'assets/kyoto-umapot-course-clean-v8.svg',reference:'https://umapot.com/?p=13277'}),
 Object.freeze({id:'tokyo_turf_2000',name:'東京 芝2000m',status:'blocked_svg_missing',
  reference:'https://umapot.com/?p=13273'})
]);
function get(id){return courses.find(c=>c.id===id)||null}
function assertCanAnimate(id,profile,route){
 const c=get(id);
 if(!c?.svg||profile?.id!==id||route?.report?.badDiscs!==0)
  throw Error('COURSE_GEOMETRY_UNVERIFIED:'+id);
 return true;
}
g.RaceLabCourseRollout=Object.freeze({courses,get,assertCanAnimate});
})(typeof window!=='undefined'?window:globalThis);
