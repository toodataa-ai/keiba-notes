/* Shared presentation-only animation: physics pose A -> pose B at fixed 80 ms;
   no prediction, course-specific parameters, or geometry changes. */
(function(global){'use strict';
const STEP_SECONDS=.08;
function capture(horses){
 if(!Array.isArray(horses))throw Error('MOTION_FIELD_MISSING');
 return horses.map(h=>{
  const d=h.displayD??h.d;
  if(!Number.isFinite(d)||!Number.isFinite(h.lane))throw Error('MOTION_POSE_INVALID');
  return {number:h.number,d,lane:h.lane,finished:Boolean(h.finished)};
 });
}
function interpolate(previous,current,alpha){
 if(!Array.isArray(previous)||!Array.isArray(current)||previous.length!==current.length)
  throw Error('MOTION_FIELD_MISMATCH');
 const t=Math.max(0,Math.min(1,Number.isFinite(alpha)?alpha:0));
 return current.map((q,i)=>{
  const p=previous[i];
  if(!p||p.number!==q.number)throw Error('MOTION_ID_CHANGED');
  return {number:q.number,d:p.d+(q.d-p.d)*t,lane:p.lane+(q.lane-p.lane)*t,
   finished:q.finished&&t>=1};
 });
}
global.RaceFrameInterpolator=Object.freeze({STEP_SECONDS,capture,interpolate,courseIndependent:true,presentationOnly:true});
})(typeof window!=='undefined'?window:globalThis);
