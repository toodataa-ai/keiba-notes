/* Venue-independent original-SVG broadcast camera.
 * NEVER redraws or unwraps the source course. Horse labels are projected
 * from the same affine transform as the registered original course image.
 * Framing adapts gently to the true pack extent before the home straight.
 */
(function(g){'use strict';
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 function create(){
  let center=null,lastTime=null,lastFrame=null;
  function reset(){center=null;lastTime=null;lastFrame=null}
  function frame({ctx,image,points,width,height,timeSeconds,paintNumber,
    leaderNo,labelLayout,decorate}){
   if(!image?.naturalWidth||!points?.length||!Number.isFinite(timeSeconds))
    throw Error('NATIVE_SOURCE_IMAGE_AND_RACE_TIME_REQUIRED');
   if(lastTime!==null && timeSeconds<lastTime-1e-7)reset();
   const first=Math.max(...points.map(p=>p.d)),last=Math.min(...points.map(p=>p.d));
   // Leading/trailing *identities* can swap by centimetres, causing a
   // visible camera twitch. Follow the MEAN of all horses (continuous for
   // small race pose changes), not whichever horse currently ranks first.
   const cx=points.reduce((a,p)=>a+p.x,0)/points.length,
    cy=points.reduce((a,p)=>a+p.y,0)/points.length;
   const dx=Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x)),
    dy=Math.max(...points.map(p=>p.y))-Math.min(...points.map(p=>p.y));
   // A fixed optical zoom throughout a race prevents zoom pumping when
   // a race pack spreads/squeezes or runner ranks swap.
   const zoom=clamp(width/39,8.9,10.4);
   const dt=lastTime===null?0:clamp(timeSeconds-lastTime,0,.35);
   const follow=1-Math.exp(-dt*3.2);
   if(center===null){center={x:cx,y:cy}}
   else{center.x+=(cx-center.x)*follow;center.y+=(cy-center.y)*follow;}
   lastTime=timeSeconds;
   const left=width*.50-center.x*zoom,top=height*.53-center.y*zoom;
   ctx.save();
   ctx.imageSmoothingEnabled=true;
   ctx.drawImage(image,left,top,620*zoom,430*zoom);
   ctx.restore();
   if(typeof decorate==='function')decorate(ctx,{
    left,top,zoom,width,height,timeSeconds
   });
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
    cameraTarget:'all-runners-mean',constantZoom:true,
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
