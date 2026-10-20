/* Shared non-physical course furniture. Source route is authoritative:
 * no extra geometric per-corner coordinates, no redrawn course surface.
 * Finish column stays entirely OUTSIDE rail; starting stalls span the
 * start cross-section and disappear as runners depart. LAB only. */
(function(global){'use strict';
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 function goal(ctx,{x,innerRailY,outerRailY,height,venueLabel='KYOTO',railSide='inner'}){
  if(!(outerRailY>innerRailY&&height>outerRailY))throw Error('GOAL_RAIL_INVALID');
  const side=railSide==='outer'?'outer':'inner';
  const foot=side==='inner'?innerRailY-8:outerRailY+8;
  const dir=side==='inner'?-1:1;
  const archTop=foot+dir*88,archShoulder=foot+dir*54;
  const sideX=x-20,otherX=x+20;
  ctx.save();
  ctx.strokeStyle='#143f31';ctx.lineWidth=9;ctx.lineCap='round';
  ctx.beginPath();ctx.moveTo(sideX,foot);ctx.lineTo(sideX,archShoulder);
  ctx.bezierCurveTo(sideX,archTop,otherX,archTop,otherX,archShoulder);
  ctx.lineTo(otherX,foot);ctx.stroke();
  ctx.strokeStyle='#f5fbf2';ctx.lineWidth=5.5;
  ctx.beginPath();ctx.moveTo(sideX,foot);ctx.lineTo(sideX,archShoulder);
  ctx.bezierCurveTo(sideX,archTop,otherX,archTop,otherX,archShoulder);
  ctx.lineTo(otherX,foot);ctx.stroke();
  ctx.strokeStyle='#144e39';ctx.lineWidth=1.8;
  ctx.beginPath();ctx.moveTo(sideX+4,foot);ctx.lineTo(sideX+4,archShoulder);
  ctx.bezierCurveTo(sideX+4,archTop+dir*5,otherX-4,archTop+dir*5,
    otherX-4,archShoulder);ctx.lineTo(otherX-4,foot);ctx.stroke();
  // The narrow photo-finish timing post is attached OUTSIDE the inner rail.
  ctx.fillStyle='#123d2d';ctx.fillRect(x-2.5,
   Math.min(foot,archTop)-4,5,Math.abs(foot-archTop)+4);
  const text=String(venueLabel).slice(0,6);
  ctx.font='bold 7.5px Arial,sans-serif';ctx.fillStyle='#fff';
  ctx.textBaseline='middle';ctx.textAlign='center';
  for(let i=0;i<text.length;i++)
   ctx.fillText(text[i],otherX,foot+dir*(18+i*10));
  ctx.restore();
  const minY=Math.min(foot,archTop)+dir*5,maxY=Math.max(foot,archTop)-dir*5;
  return Object.freeze({railSide:side,x,footY:foot,
   innerRailY,outerRailY,bodyMinY:minY,bodyMaxY:maxY,
   outsideTurf:side==='inner'?foot<innerRailY:foot>outerRailY});
 }
 function gateGeometry({point,maxLane=14,project}){
  if(typeof point!=='function'||typeof project!=='function')
   throw Error('START_GATE_ROUTE_REQUIRED');
  const a=project(point(0,0)),b=project(point(0,maxLane));
  const start=project(point(3,maxLane/2)),
   mid=project(point(0,maxLane/2));
  let nx=b.x-a.x,ny=b.y-a.y,len=Math.hypot(nx,ny);
  if(len<.5)throw Error('START_GATE_CROSS_TRACK_UNDEFINED');
  nx/=len;ny/=len;
  let tx=start.x-mid.x,ty=start.y-mid.y,tlen=Math.hypot(tx,ty);
  if(tlen<.1)throw Error('START_GATE_DIRECTION_UNDEFINED');
  tx/=tlen;ty/=tlen;
  return {a,b,mid,cross:{x:nx,y:ny},direction:{x:tx,y:ty},
    width:len,stalls:18,sourceDistance:0,courseIndependent:true};
 }
 function startGate(ctx,{point,project,maxLane=14,leaderD=0,
   overview=false,showUntilM=22}){
  if(leaderD>showUntilM)return null;
  const geom=gateGeometry({point,project,maxLane});
  const {a,b,mid,cross,direction}=geom;
  ctx.save();
  const minWidth=overview?17:90;
  const p1=geom.width<minWidth?{
   x:mid.x-cross.x*minWidth/2,y:mid.y-cross.y*minWidth/2}:a;
  const p2=geom.width<minWidth?{
   x:mid.x+cross.x*minWidth/2,y:mid.y+cross.y*minWidth/2}:b;
  // The overhanging gate roof is a few screen pixels BEHIND the
  // actual start cross-section. This leaves the 18 physical horse circles
  // at d=0 while making the stalls visible instead of hidden under them.
  const roofBack=overview?2:19;
  const roof1={x:p1.x-direction.x*roofBack,y:p1.y-direction.y*roofBack};
  const roof2={x:p2.x-direction.x*roofBack,y:p2.y-direction.y*roofBack};
  ctx.strokeStyle='#e7f0e8';ctx.lineWidth=overview?3:8;ctx.lineCap='round';
  ctx.beginPath();ctx.moveTo(roof1.x,roof1.y);ctx.lineTo(roof2.x,roof2.y);ctx.stroke();
  ctx.strokeStyle='#315a50';ctx.lineWidth=overview?1.8:5;
  ctx.beginPath();ctx.moveTo(roof1.x,roof1.y);ctx.lineTo(roof2.x,roof2.y);ctx.stroke();
  const n=overview?6:18;
  for(let i=0;i<=n;i++){
   const t=i/n,x=p1.x+(p2.x-p1.x)*t,y=p1.y+(p2.y-p1.y)*t;
   ctx.strokeStyle=i%2?'#d3e4df':'#f7fff6';
   ctx.lineWidth=overview?.9:2.4;
   ctx.beginPath();
   ctx.moveTo(x-direction.x*roofBack,y-direction.y*roofBack);
   ctx.lineTo(x+direction.x*(overview?1:3),
    y+direction.y*(overview?1:3));
   ctx.stroke();
  }
  // Stalls can be covered by the 18 horse-number circles at t=0.
  // Identify the real starting apparatus alongside the route, never
  // inventing a second gate position or changing the runner coordinates.
  const labelOffset=overview?23:43;
  const labelX=mid.x-direction.x*labelOffset,
   labelY=mid.y-direction.y*labelOffset,
   labelWidth=overview?50:61,labelHeight=overview?16:23;
  ctx.fillStyle='rgba(244,251,246,.97)';
  ctx.beginPath();ctx.roundRect(labelX-labelWidth/2,
   labelY-labelHeight/2,labelWidth,labelHeight,4);ctx.fill();
  ctx.strokeStyle='#315a50';ctx.lineWidth=overview?1:2;ctx.stroke();
  ctx.fillStyle='#1c503c';ctx.textAlign='center';ctx.textBaseline='middle';
  ctx.font='bold '+(overview?'8':'12')+'px Arial,sans-serif';
  ctx.fillText('発馬機',labelX,labelY+.5);
  ctx.restore();
  return Object.freeze({...geom,drawn:true,overview,leaderD});
 }
 global.RaceTracksideFurniture=Object.freeze({
  goal,startGate,gateGeometry,courseIndependent:true,
  sourceSvgUnchanged:true,horsePhysicsUnchanged:true
 });
})(typeof window!=='undefined'?window:globalThis);
