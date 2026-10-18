/* LAB v19 — uniform-affine camera correction on untouched Umapot SVG.
 *
 * The real shape is NOT redrawn, flattened, warped, traced, re-sampled or
 * replaced. Physics and horse coordinates are untouched. Every frame is
 * only ONE translation + ONE UNIFORM scale of the *identical* publisher
 * source SVG and the numbers. Camera correction depends on race distance
 * and source-centreline geometry, NOT on crowd size, popularity or speed.
 *
 * Fundamental limitation: a camera cannot preserve every pairwise arc
 * distance and simultaneously preserve the curved course drawing. It can
 * reduce the large pack-span fluctuations via a slowly varying crop zoom,
 * never falsify a horse's own position.
 */
(function(root){'use strict';
const N=1920,SPAN=65,LANE=2,
 MAX_GAIN=1.45,RADIUS=48,DEADZONE=0.012;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
let samples=null,summary=null;
const sortNumbers=values=>values.slice().sort((a,b)=>a-b);
function profile(turf){
 if(!turf?.point)throw Error('CAMERA_COMP_SOURCE_TURF_MISSING');
 const chords=new Float64Array(N+1);
 for(let d=0;d<=N;d++){
  const a=Math.max(SPAN,d),b=a-SPAN,
    p=turf.point(a,LANE),q=turf.point(b,LANE);
  chords[d]=Math.hypot(p.x-q.x,p.y-q.y);
  if(!(chords[d]>1))throw Error('CAMERA_COMP_DEGENERATE_COURSE_'+d);
 }
 const sorted=sortNumbers(Array.from(chords).slice(120,1850));
 const ref=sorted[Math.floor(sorted.length*.88)];
 const raw=Array.from(chords,chord=>{
  const ratio=ref/chord;
  return clamp(ratio>1+DEADZONE?ratio:1,1,MAX_GAIN);
 });
 // Smooth spatially over >=96 physical race metres so the whole scene
 // cannot breathe when the leader changes / a horse joins the pack.
 const prefix=new Float64Array(raw.length+1);
 for(let i=0;i<raw.length;i++)prefix[i+1]=prefix[i]+raw[i];
 const smooth=d=>{
  const left=Math.max(0,d-RADIUS),right=Math.min(N,d+RADIUS);
  const sum=prefix[right+1]-prefix[left];
  return sum/(right-left+1);
 };
 const easing=t=>{
  t=clamp(t,0,1);return t*t*(3-2*t);
 };
 samples=new Float64Array(N+1);
 for(let d=0;d<=N;d++){
  // Fade in at the start; fade back to fixed camera before GOAL-board
  // takeover at 1920m, so the last-stage transition is stable.
  const fade=easing(d/130)*easing((N-d)/155);
  samples[d]=1+(smooth(d)-1)*fade;
 }
 const metrics=(from=1250,to=1830)=>{
  const reference=[],corrected=[];
  for(let d=from;d<=to;d+=5){
   reference.push(chords[d]);
   corrected.push(chords[d]*samples[d]);
  }
  const extent=a=>Math.max(...a)/Math.min(...a);
  const variationBefore=extent(reference),variationAfter=extent(corrected);
  return {from,to,uniformPackM:SPAN,ratioBefore:variationBefore,
   ratioAfter:variationAfter,
   minBefore:Math.min(...reference),maxBefore:Math.max(...reference),
   minAfter:Math.min(...corrected),maxAfter:Math.max(...corrected)};
 };
 let maxGain=0,maxStep=0;
 for(let d=0;d<=N;d++){
  maxGain=Math.max(maxGain,samples[d]);
  if(d)maxStep=Math.max(maxStep,Math.abs(samples[d]-samples[d-1]));
 }
 summary=Object.freeze({source:'publisher-svg-uniform-affine-only',
  imageUnmodified:true,physicsUnmodified:true,normalZoomUnchanged:false,
  maxGain,maxGainLimit:MAX_GAIN,maxGainStepPerMetre:maxStep,
  reference65mChordPx:ref,lookbackM:SPAN,smoothingRadiusM:RADIUS,
  thirdFourthTurn:metrics(1250,1800),
  firstSecondTurn:metrics(310,710),
  midStraight:metrics(770,1190),
  fullRace:metrics(130,1830)});
 return summary;
}
function gain(distance){
 if(!samples)return 1;
 const d=clamp(Number(distance)||0,0,N);
 const i=Math.floor(d),frac=d-i;
 return samples[i]*(1-frac)+samples[Math.min(N,i+1)]*frac;
}
root.RaceCleanCurveCamera=Object.freeze({profile,gain,stats:()=>summary});
})(typeof window!=='undefined'?window:globalThis);
