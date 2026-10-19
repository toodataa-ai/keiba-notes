/* Shared image projection, near the detected safe inner edge.
 * Course-neutral and PRESENTATION-ONLY; physical racing lanes, source SVG and
 * crossing times are immutable.
 */
(function(root){'use strict';
 const INNER_INSET_FRACTION=.028,SAFE_FRACTION_FLOOR=.025,SAFE_FRACTION_CEILING=.95;
 const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 function fraction(physicalFraction){
  if(!Number.isFinite(physicalFraction))throw Error('INNER_RAIL_FRACTION_NOT_FINITE');
  return clamp(physicalFraction-INNER_INSET_FRACTION,SAFE_FRACTION_FLOOR,SAFE_FRACTION_CEILING);
 }
 function offset(low,high,physicalFraction){
  if(!Number.isFinite(low)||!Number.isFinite(high)||high<=low)throw Error('INNER_RAIL_SAFE_CORRIDOR_INVALID');
  return low+(high-low)*fraction(physicalFraction);
 }
 root.RaceSafeRailProjection=Object.freeze({
  fraction,offset,INNER_INSET_FRACTION,SAFE_FRACTION_FLOOR,SAFE_FRACTION_CEILING,
  immutablePhysicalLane:true,originalSvgIntact:true,courseIndependent:true
 });
})(typeof window!=='undefined'?window:globalThis);
