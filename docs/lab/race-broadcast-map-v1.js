/* LAB v0.51: Kyoto 1400-inspired broadcast camera, smoothed original turf-rail geometry
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
 // Kyoto 1400's camera principle: use actual LOCAL group spread with
 // margins instead of zooming as close as possible to a single horse.
 const group=points.filter(p=>Math.abs(p.d-focus.d)<=110);
 if(!group.includes(focus))group.push(focus);
 const xs=group.map(p=>p.x),ys=group.map(p=>p.y);
 const loX=Math.min(...xs),hiX=Math.max(...xs),loY=Math.min(...ys),hiY=Math.max(...ys);
 const pixelRatio=canvasWidth/Math.max(1,renderedWidth||canvasWidth);
 const marginX=Math.min(canvasWidth*.24,Math.max(48,22*pixelRatio));
 const marginY=Math.min(canvasHeight*.30,Math.max(64,42*pixelRatio));
 const zoom=Math.max(1.7,Math.min(points.length===1?5.2:4.6,
   (canvasWidth-2*marginX)/Math.max(65,hiX-loX+15),
   (canvasHeight-2*marginY)/Math.max(55,hiY-loY+12)));
 const mean={x:(loX+hiX)/2,y:(loY+hiY)/2};
 const origin={x:focus.x+.16*(mean.x-focus.x),y:focus.y+.16*(mean.y-focus.y)};
 const anchor={x:canvasWidth/2,y:canvasHeight*.50};
 const actualWidth=Math.max(1,renderedWidth||canvasWidth);
 return {zoom,origin,anchor,markerScale:canvasWidth/actualWidth,
  sourceWidth:width,sourceHeight:height,rotationRadians:0,
  cameraMode:'kyoto-1400-like-group-framing'};
}
function screenPoint(p,view){
 return {x:view.anchor.x+(p.x-view.origin.x)*view.zoom,
   y:view.anchor.y+(p.y-view.origin.y)*view.zoom};
}
// SOURCE-RAIL VISUAL SMOOTHING ONLY: no change to horse location or game physics.
const smoothCache=new WeakMap();
function smoothTurfRails(course,overlay){
 if(smoothCache.has(course))return smoothCache.get(course);
 const raw=[];
 for(let d=0;d<=course.distance_m;d+=5)
   raw.push(global.RaceTurfCorridor.rails(course,d,overlay.legacyPoint));
 const radius=9,limit=3;
 const data=raw.map((p,i)=>{
  const sm={};
  for(const side of ['inner','outer']){
   let sx=0,sy=0,sw=0;
   for(let k=-radius;k<=radius;k++){
    const idx=Math.max(0,Math.min(raw.length-1,i+k));
    const w=(radius+1-Math.abs(k))**2;
    sx+=raw[idx][side].x*w;sy+=raw[idx][side].y*w;sw+=w;
   }
   const dx=sx/sw-p[side].x,dy=sy/sw-p[side].y;
   const mag=Math.hypot(dx,dy),factor=mag>limit?limit/mag:1;
   sm[side]={x:p[side].x+dx*factor,y:p[side].y+dy*factor};
  }
  return sm;
 });
 smoothCache.set(course,data);return data;
}
// Midpoint quadratic joining eliminates visible kinks at 5-metre data stations.
function traceRail(ctx,points,side,reverse=false,append=false){
 const list=reverse?points.slice().reverse():points;
 const first=list[0][side];
 if(append)ctx.lineTo(first.x,first.y);else ctx.moveTo(first.x,first.y);
 for(let i=1;i<list.length-1;i++){
  const p=list[i][side],n=list[i+1][side];
  ctx.quadraticCurveTo(p.x,p.y,(p.x+n.x)/2,(p.y+n.y)/2);
 }
 const last=list[list.length-1][side];ctx.lineTo(last.x,last.y);
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
 const stations=smoothTurfRails(course,overlay);
 if(stations.length<3)throw Error('TURF_RAIL_VECTOR_EMPTY');
 // A single connected ribbon traces the entire 2000m inner course.
 ctx.beginPath();
 traceRail(ctx,stations,'inner');
 traceRail(ctx,stations,'outer',true,true);
 ctx.closePath();
 ctx.fillStyle='#65af63';ctx.fill('evenodd');
 ctx.strokeStyle='#276c45';ctx.lineWidth=1.0;
 ctx.lineJoin='round';ctx.lineCap='round';
 for(const side of ['inner','outer']){
  ctx.beginPath();
  traceRail(ctx,stations,side);
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
    view.markerScale*(points.length>=12?(p.focused?1.02:.92):points.length>=6?.98:1.02),
    p.focused,
    p.leading,race.field_size,p.passing);
 }
 return {ready:true,view,points,markers,visibleCount:markers.filter(x=>x.visible).length,
    renderMode:'smoothed-source-derived-vector-rails',
    turfStations:stations.length,sourceImage:null};
}
global.RaceSimBroadcastMap=Object.freeze({
 supports,entries,frame,screenPoint,smoothTurfRails,draw,width,height
});
})(typeof window!=='undefined'?window:globalThis);
