/* LAB v10 — rasterize the ACTUAL publisher SVG only for turf occupancy.
 * Turf edges are not redrawn. The UI computes its physical route position
 * from the already-approved racing model, then maps lane fractions inside
 * the original green band's cross-section, preserving the inside preference.
 * Shared Kyoto1400 physics / time / positions remain unchanged.
 */
(function(global){'use strict';
const W=620,H=430,RASTER=3,MARGIN=2.8;
const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
const c=global.RaceCleanCourse;
let grid=null,samples=null,statistics=null;
function create(image){
 if(!image||!image.complete||image.naturalWidth!==W||image.naturalHeight!==H)
  throw Error('TURF_ORIGINAL_VECTOR_IMAGE_UNAVAILABLE');
 const canvas=document.createElement('canvas');
 canvas.width=W*RASTER;canvas.height=H*RASTER;
 const ctx=canvas.getContext('2d',{willReadFrequently:true});
 if(!ctx)throw Error('TURF_IMAGE_CONTEXT_MISSING');
 ctx.drawImage(image,0,0,canvas.width,canvas.height);
 const raw=ctx.getImageData(0,0,canvas.width,canvas.height).data;
 const bits=new Uint8Array(canvas.width*canvas.height);
 for(let i=0;i<bits.length;i++){
  const j=i*4,r=raw[j],g=raw[j+1],b=raw[j+2],a=raw[j+3];
  if(a>=240&&g>=108&&g>r*1.40&&g>b*1.40)bits[i]=1;
 }
 grid=bits;
 samples=[];
 let missing=0,maxShift=0,maxGap=0,maxGapAt=0,jumpsOver4=0,possibleForks=0;
 const jumps=[];
 for(let d=0;d<=2000;d++){
  const rail=c.rails(d),mid=rail.center,wx=rail.outer.x-rail.inner.x,
   wy=rail.outer.y-rail.inner.y,den=Math.hypot(wx,wy)||1,
   nx=wx/den,ny=wy/den;
  const runs=[];
  let opened=null,lastGreen=-1000;
  for(let ix=-180;ix<=180;ix++){
   const t=ix/3;
   const green=isGreen(mid.x+nx*t,mid.y+ny*t);
   if(green){
    if(opened===null)opened=t;
    lastGreen=t;
   }else if(opened!==null){
    if(lastGreen-opened>=7.5)runs.push({a:opened,b:lastGreen,
     m:(opened+lastGreen)/2});
    opened=null;
   }
  }
  if(opened!==null&&lastGreen-opened>=7.5)
   runs.push({a:opened,b:lastGreen,m:(opened+lastGreen)/2});
  if(runs.length>1)possibleForks++;
  // FOLLOW A CONTINUOUS INNER-TURF FILE, not the midpoint of every
  // green run. A junction merges two original green strokes into one
  // 80px-wide segment: using that segment's midpoint caused a ~23px
  // teleport at 616m (and similar jumps at 537/1514/1578m).
  const prev=samples[d-1];
  const prevX=prev?prev.x+prev.nx*prev.shift:0;
  const prevY=prev?prev.y+prev.ny*prev.shift:0;
  const predicted=prev?(prevX-mid.x)*nx+(prevY-mid.y)*ny:0;
  function score(run){
   const lo=run.a+MARGIN,hi=run.b-MARGIN;
   const t=clamp(predicted,Math.min(lo,hi),Math.max(lo,hi));
   const ux=mid.x+nx*t,uy=mid.y+ny*t;
   // Seek the closest still-green point to the previous route, even
   // when this band's width suddenly expands near crossing rails.
   return (prev?Math.hypot(ux-prevX,uy-prevY)*4.5:Math.abs(t))+
    Math.abs(t)*.12+(hi-lo<5?35:0);
  }
  runs.sort((a,b)=>score(a)-score(b));
  if(!runs.length){
   missing++;samples.push(null);continue;
  }
  const match=runs[0];
  const safeLo=match.a+MARGIN,safeHi=match.b-MARGIN;
  if(safeLo>safeHi){missing++;samples.push(null);continue;}
  const half=Math.min(9,(safeHi-safeLo)/2);
  // Moving files should occupy a realistic local portion of a very
  // wide green junction, never fan out across both green rings.
  const optimal=clamp(predicted,safeLo+half,safeHi-half);
  const limited=prev?clamp(optimal,predicted-1.5,predicted+1.5):optimal;
  const shift=clamp(limited,safeLo,safeHi);
  // At a dividing rail temporarily narrow the lateral usable band
  // instead of teleporting runners or crossing white/dirt.
  const actualHalf=Math.max(0,Math.min(half,shift-safeLo,safeHi-shift));
  const low=shift-actualHalf,high=shift+actualHalf;
  maxShift=Math.max(maxShift,Math.abs(shift));
  samples.push({x:mid.x,y:mid.y,nx,ny,low,high,shift,
   width:match.b-match.a});
  if(prev){
   const dx=(mid.x+nx*shift)-(prev.x+prev.nx*prev.shift),
    dy=(mid.y+ny*shift)-(prev.y+prev.ny*prev.shift);
   const jump=Math.hypot(dx,dy);
   if(jump>4){jumpsOver4++;
    jumps.push({d,jump,prevShift:prev.shift,nowShift:shift,
      prevX:prev.x+prev.nx*prev.shift,prevY:prev.y+prev.ny*prev.shift,
      x:mid.x+nx*shift,y:mid.y+ny*shift,
      options:runs.map(run=>({a:run.a,b:run.b,m:run.m,
       x:mid.x+nx*run.m,y:mid.y+ny*run.m}))});
   }
   if(jump>maxGap){maxGap=jump;maxGapAt=d;}
  }
 }
 statistics={missing,maxShift,maxGap,maxGapAt,jumpsOver4,jumps,possibleForks,count:samples.length,
  greenPixels:bits.reduce((a,v)=>a+v,0)};
 if(missing){
  // The caller displays a safe loading error rather than perpetuating
  // wrong turf positions if the source SVG changes unexpectedly.
  throw Error('TURF_SOURCE_CALIBRATION_GAPS:'+missing);
 }
 return statistics;
}
function isGreen(x,y){
 if(!grid||!Number.isFinite(x)||!Number.isFinite(y))return false;
 const ix=Math.floor(x*RASTER),iy=Math.floor(y*RASTER);
 return ix>=0&&ix<W*RASTER&&iy>=0&&iy<H*RASTER&&
  grid[iy*W*RASTER+ix]===1;
}
function discOnTurf(x,y,r=4.4){
 if(!isGreen(x,y))return false;
 for(let i=0;i<16;i++){
  const a=2*Math.PI*i/16;
  if(!isGreen(x+r*Math.cos(a),y+r*Math.sin(a)))return false;
 }
 return true;
}
function point(distance,lane){
 if(!samples)throw Error('TURF_MASK_NOT_READY');
 const d=clamp(Number(distance)||0,0,2000);
 const lo=Math.floor(d),hi=Math.ceil(d),f=d-lo;
 const a=samples[lo],b=samples[hi];
 const portion=c.fraction(lane);
 const at=e=>{
  const t=e.low+(e.high-e.low)*portion;
  return {x:e.x+e.nx*t,y:e.y+e.ny*t};
 };
 const pa=at(a),pb=at(b);
 let x=pa.x+(pb.x-pa.x)*f,y=pa.y+(pb.y-pa.y)*f;
 // Guarantee complete 18px-ish visual badge is inside source green;
 // snap only ALONG the local turf normal, never freely onto a dirt path.
 if(!discOnTurf(x,y,MARGIN)){
  const m=a,half=Math.max(0,(m.high-m.low)/2);
  const midT=(m.high+m.low)/2;
  let nearest=null;
  for(let delta=0;delta<=half+3;delta+=.35){
   for(const t of [midT-delta,midT+delta]){
    const tx=m.x+m.nx*t,ty=m.y+m.ny*t;
    if(discOnTurf(tx,ty,MARGIN)){
     const score=Math.hypot(tx-x,ty-y);
     if(!nearest||score<nearest.score)nearest={x:tx,y:ty,score};
    }
   }
   if(nearest&&nearest.score<delta+.4)break;
  }
  if(nearest){x=nearest.x;y=nearest.y;}
 }
 return {x,y,d:distance,lane,section:c.center(distance).section};
}
function runners(state){
 return state.horses.map(h=>{
  const d=h.displayD??h.d;
  return {number:h.number,d,lane:h.lane,...point(d,h.lane),finished:h.finished};
 });
}
function audit(step=5){
 let total=0,badCenters=0,badDiscs=0,maxJump=0;
 for(let lane=0;lane<=14;lane+=1){
  let prev=null;
  for(let d=0;d<=2000;d+=step){
   const p=point(d,lane);
   total++;
   if(!isGreen(p.x,p.y))badCenters++;
   if(!discOnTurf(p.x,p.y,MARGIN))badDiscs++;
   if(prev)maxJump=Math.max(maxJump,Math.hypot(p.x-prev.x,p.y-prev.y));
   prev=p;
  }
 }
 return {...statistics,total,badCenters,badDiscs,maxJump,step};
}
global.RaceCleanTurf=Object.freeze({create,point,runners,isGreen,discOnTurf,audit,stats:()=>statistics});
})(typeof window!=='undefined'?window:globalThis);
