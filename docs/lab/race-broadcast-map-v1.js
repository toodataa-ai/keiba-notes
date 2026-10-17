/* LAB v0.47 — Kyoto inner 2000: the broadcast is a moving WINDOW onto the
   exact same licensed Umapot image and the SAME pixel positions as the overview.
   Do not change engine time, overtakes, pace, lanes, distance or JRA outputs.
   No image is copied/repackaged and no GPS coordinates are implied. */
(function(global){'use strict';
const width=620,height=430,courseId='kyoto_turf_inner_2000';
function supports(race){return race?.course_id===courseId}
function entries(state,course,overlay){
 if(!state?.horses||!course||!overlay)throw Error('LAB_SHARED_IMAGE_INPUTS_MISSING');
 return state.horses.filter(h=>!h.finished||(h.displayD??h.d)<=state.distance+40).map(h=>{
  const pt=overlay.point(course,h.displayD??h.d,h.lane);
  if(!Number.isFinite(pt.x)||!Number.isFinite(pt.y))throw Error('LAB_SHARED_IMAGE_BAD_COORDINATE');
  return {number:h.number,x:pt.x,y:pt.y,d:h.displayD??h.d};
 });
}
function frame(points,canvasWidth,canvasHeight,renderedWidth,focusNo){
 if(!Array.isArray(points)||!points.length)throw Error('LAB_SHARED_IMAGE_EMPTY_FIELD');
 const focus=points.find(p=>p.number===focusNo)||points[0];
 const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
 const loX=Math.min(...xs),hiX=Math.max(...xs),loY=Math.min(...ys),hiY=Math.max(...ys);
 // Constant pixel coordinates for both displays. Wide racing fields scale to
 // fit together; a one-runner demonstration stays centered, never stretched.
 // Larger zoom for both one and eighteen runners, but the entire active
 // field is always included. Larger spreads automatically zoom back out.
 const xspan=Math.max(points.length===1?185:180,hiX-loX+(points.length===1?0:58));
 const yspan=Math.max(points.length===1?115:116,hiY-loY+(points.length===1?0:52));
 const zoom=Math.min(canvasWidth/xspan,canvasHeight/yspan);
 const origin=points.length===1?{x:focus.x,y:focus.y}:
  {x:(loX+hiX)/2,y:(loY+hiY)/2};
 const anchor={x:canvasWidth/2,y:canvasHeight*.50};
 const actualWidth=Math.max(1,renderedWidth||canvasWidth);
 return {zoom,origin,anchor,markerScale:canvasWidth/actualWidth,
  sourceWidth:width,sourceHeight:height,rotationRadians:0};
}
function screenPoint(p,view){
 return {x:view.anchor.x+(p.x-view.origin.x)*view.zoom,
   y:view.anchor.y+(p.y-view.origin.y)*view.zoom};
}
function draw(options){
 const {ctx,canvas,image,state,race,course,overlay,focusNo,paintNumber,
   renderedWidth,passingNo=null,guide=false}=options;
 if(!supports(race))return {ready:false,reason:'UNSUPPORTED_COURSE'};
 if(!image?.complete||image.naturalWidth!==width||image.naturalHeight!==height)
   return {ready:false,reason:'SOURCE_IMAGE_NOT_READY'};
 if(typeof paintNumber!=='function')throw Error('LAB_SHARED_IMAGE_MARKER_MISSING');
 const points=entries(state,course,overlay);
 if(!points.length)return {ready:false,reason:'NO_VISIBLE_RUNNERS'};
 const view=frame(points,canvas.width,canvas.height,renderedWidth,focusNo);
 // The licensed 620x430 bitmap is drawn without rotation or distortion.
 // Both the bitmap and the horse positions share one 620x430 coordinate space.
 ctx.clearRect(0,0,canvas.width,canvas.height);
 ctx.fillStyle='#ffffff';ctx.fillRect(0,0,canvas.width,canvas.height);
 ctx.save();
 ctx.translate(view.anchor.x,view.anchor.y);
 ctx.scale(view.zoom,view.zoom);
 ctx.translate(-view.origin.x,-view.origin.y);
 ctx.imageSmoothingEnabled=true;
 ctx.drawImage(image,0,0,width,height);
 if(guide){
  ctx.save();ctx.strokeStyle='#8d27bd';ctx.lineWidth=1/view.zoom;
  ctx.setLineDash([4/view.zoom,4/view.zoom]);ctx.beginPath();
  for(let d=0;d<=course.distance_m;d+=5){
   const p=overlay.point(course,d,0);
   if(d===0)ctx.moveTo(p.x,p.y);else ctx.lineTo(p.x,p.y);
  }
  ctx.stroke();ctx.restore();
 }
 ctx.restore();
 const selected=focusNo;
 const markers=points.map(p=>({
  ...p,...screenPoint(p,view),
  focused:p.number===selected,leading:p.number===state.leadingNo,
  passing:p.number===passingNo
 })).sort((a,b)=>Number(a.passing)-Number(b.passing)||
    Number(a.focused)-Number(b.focused)||Number(a.leading)-Number(b.leading)||a.number-b.number);
 for(const p of markers){
  paintNumber(ctx,p.number,p.x,p.y,
    view.markerScale*(points.length>=12?(p.focused?.72:.59):points.length>=6?.75:1),
    p.focused,
    p.leading,race.field_size,p.passing);
 }
 return {ready:true,view,points,markers,sourceImage:image.currentSrc||image.src};
}
global.RaceSimBroadcastMap=Object.freeze({
 supports,entries,frame,screenPoint,draw,width,height
});
})(typeof window!=='undefined'?window:globalThis);
