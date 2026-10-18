/* LAB v0.50: sharp vector turf rail preview from SAME derived pixel geometry
   as the Umapot overview. NO raster zoom, label, arrow or extraneous helper
   stroke in broadcast. Full overview original JPEG is untouched.
   Physics, race timing, official predictions and actual lanes are unchanged. */
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
 // A broadcast is an optically close camera, NOT a "fit all 18" map.
 // The full overview retains all 18. Here the selected horse and its nearby
 // rivals remain legible on phones; off-camera horses are intentionally cropped.
 const zoom=Math.min(points.length===1?10.5:8.5,
   canvasWidth/(points.length===1?90:120),
   canvasHeight/(points.length===1?70:80));
 const nearby=points.filter(p=>Math.hypot(p.x-focus.x,p.y-focus.y)<20);
 const mean=nearby.reduce((a,p)=>({x:a.x+p.x/nearby.length,y:a.y+p.y/nearby.length}),{x:0,y:0});
 const origin={x:focus.x+.18*(mean.x-focus.x),y:focus.y+.18*(mean.y-focus.y)};
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
 if(!global.RaceTurfCorridor?.has(course.id))
   return {ready:false,reason:'DERIVED_TURF_RAILS_NOT_READY'};
 if(typeof paintNumber!=='function')throw Error('LAB_SHARED_IMAGE_MARKER_MISSING');
 const points=entries(state,course,overlay);
 if(!points.length)return {ready:false,reason:'NO_VISIBLE_RUNNERS'};
 const view=frame(points,canvas.width,canvas.height,renderedWidth,focusNo);
 // LIVE broadcast uses source-derived RAIL VECTORS, not a scaled 620px JPEG.
 // No blurred raster, printed annotations, crossing guide lines or bitmap text.
 // The ORIGINAL linked bitmap remains untouched in the full overview.
 ctx.clearRect(0,0,canvas.width,canvas.height);
 ctx.fillStyle='#edf1ea';ctx.fillRect(0,0,canvas.width,canvas.height);
 ctx.save();
 ctx.translate(view.anchor.x,view.anchor.y);
 ctx.scale(view.zoom,view.zoom);
 ctx.translate(-view.origin.x,-view.origin.y);
 const stations=[];
 for(let d=0;d<=course.distance_m;d+=5)
   stations.push(global.RaceTurfCorridor.rails(course,d,overlay.legacyPoint));
 if(stations.length<3)throw Error('TURF_RAIL_VECTOR_EMPTY');
 // A single connected ribbon traces the entire 2000m inner course.
 ctx.beginPath();
 stations.forEach((s,i)=>i?ctx.lineTo(s.inner.x,s.inner.y):ctx.moveTo(s.inner.x,s.inner.y));
 for(let i=stations.length-1;i>=0;i--)ctx.lineTo(stations[i].outer.x,stations[i].outer.y);
 ctx.closePath();
 ctx.fillStyle='#65af63';ctx.fill('evenodd');
 // Preserve only the two actual turf/rail boundaries; NOT course captions.
 ctx.strokeStyle='#276c45';ctx.lineWidth=1.2;
 for(const side of ['inner','outer']){
  ctx.beginPath();
  stations.forEach((s,i)=>i?ctx.lineTo(s[side].x,s[side].y):ctx.moveTo(s[side].x,s[side].y));
  ctx.stroke();
 }
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
  // A number outside this close-up is still present on the full overview.
  const visible=p.x>=-55*view.markerScale&&p.x<=canvas.width+55*view.markerScale&&
                p.y>=-55*view.markerScale&&p.y<=canvas.height+55*view.markerScale;
  p.visible=visible;
  if(!visible)continue;
  paintNumber(ctx,p.number,p.x,p.y,
    view.markerScale*(points.length>=12?(p.focused?1.55:1.34):points.length>=6?1.30:1.48),
    p.focused,
    p.leading,race.field_size,p.passing);
 }
 return {ready:true,view,points,markers,visibleCount:markers.filter(x=>x.visible).length,
    renderMode:'source-derived-vector-rails',
    turfStations:stations.length,sourceImage:null};
}
global.RaceSimBroadcastMap=Object.freeze({
 supports,entries,frame,screenPoint,draw,width,height
});
})(typeof window!=='undefined'?window:globalThis);
