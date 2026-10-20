/* Venue-independent original-SVG broadcast camera.
 * NEVER redraws or unwraps the source course. Horse labels are projected
 * from the same affine transform as the registered original course image.
 * Framing adapts gently to the true pack extent before the home straight.
 */
(function(g){'use strict';
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 function create(){
  let center=null,zoom=null,lastTime=null,lastFrame=null;
  function reset(){center=null;zoom=null;lastTime=null;lastFrame=null}
  function frame({ctx,image,points,width,height,timeSeconds,paintNumber,
    leaderNo,labelLayout}){
   if(!image?.naturalWidth||!points?.length||!Number.isFinite(timeSeconds))
    throw Error('NATIVE_SOURCE_IMAGE_AND_RACE_TIME_REQUIRED');
   if(lastTime!==null && timeSeconds<lastTime-1e-7)reset();
   const first=Math.max(...points.map(p=>p.d)),last=Math.min(...points.map(p=>p.d));
   const forward=points.find(p=>p.d===first);
   const rear=points.find(p=>p.d===last);
   const cx=(forward.x+rear.x)/2,cy=(forward.y+rear.y)/2;
   const dx=Math.abs(forward.x-rear.x),dy=Math.abs(forward.y-rear.y);
   // A moderate native-image zoom makes the field readable without
   // stretching horses off the true course ribbon. It is deliberately
   // capped: a huge zoom would hide all rail/track context.
   const candidate=clamp(Math.min(
    width*.75/Math.max(16,dx),height*.70/Math.max(16,dy)),8.4,11.0);
   const dt=lastTime===null?0:clamp(timeSeconds-lastTime,0,.35);
   const follow=1-Math.exp(-dt*4.0),zoomFollow=1-Math.exp(-dt*1.8);
   if(center===null){center={x:cx,y:cy};zoom=candidate}
   else{
    center.x+=(cx-center.x)*follow;center.y+=(cy-center.y)*follow;
    zoom+=(candidate-zoom)*zoomFollow;
   }
   lastTime=timeSeconds;
   const left=width*.50-center.x*zoom,top=height*.53-center.y*zoom;
   ctx.save();
   ctx.imageSmoothingEnabled=true;
   ctx.drawImage(image,left,top,620*zoom,430*zoom);
   ctx.restore();
   const trueScreen=points.map(p=>({...p,x:left+p.x*zoom,y:top+p.y*zoom}));
   const visible=typeof labelLayout==='function'?
    labelLayout(trueScreen):trueScreen;
   for(const p of visible){
    if(p.x>=-18&&p.x<=width+18&&p.y>=-18&&p.y<=height+18)
     paintNumber(ctx,p.number,p.x,p.y,width<540?.78:.84,p.number===leaderNo);
   }
   lastFrame={mode:'native-original-svg',unwarpedSourceImage:true,
    sourceSvgDimensions:[620,430],zoom,centerX:center.x,centerY:center.y,
    truePhysicalGapM:first-last,
    geometricChordPx:Math.hypot(dx,dy)*zoom,
    labelPositions:visible.map(p=>({number:p.number,x:p.x,y:p.y})),
    physicalPositionsUnchanged:true};
   return lastFrame;
  }
  return Object.freeze({frame,reset,metrics:()=>lastFrame});
 }
 g.RaceNativeBroadcast=Object.freeze({create,courseIndependent:true,
  sourceImageUnwarped:true,physicalPositionsUnchanged:true});
})(typeof window!=='undefined'?window:globalThis);
