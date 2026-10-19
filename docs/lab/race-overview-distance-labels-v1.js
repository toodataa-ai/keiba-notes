/* Distance ticks aligned with the original course SVG, course-agnostic. */
(function(g){'use strict';
function draw({ctx,point,distance,width,height,interval=200}){
 if(!ctx||typeof point!=='function'||!(distance>0))throw Error('DISTANCE_MAP_INPUT');
 const stops=[0];for(let d=interval;d<distance;d+=interval)stops.push(d);
 stops.push(distance);const used=[];
 ctx.save();ctx.textBaseline='middle';ctx.textAlign='center';
 for(const d of stops){
  const a=point(d,0),b=point(d,14);
  let dx=b.x-a.x,dy=b.y-a.y,len=Math.hypot(dx,dy)||1;dx/=len;dy/=len;
  let x=(b.x+dx*22)*width/620,y=(b.y+dy*22)*height/430;
  x=Math.max(26,Math.min(width-26,x));y=Math.max(11,Math.min(height-11,y));
  for(let j=0;j<6&&used.some(p=>Math.hypot(x-p.x,y-p.y)<24);j++){
   x=Math.max(26,Math.min(width-26,x+dx*8));
   y=Math.max(11,Math.min(height-11,y+dy*8));
  }
  const label=d===0?'開始':d===distance?'GOAL':d+'m';
  const w=d===0?30:36;
  ctx.fillStyle='rgba(253,255,252,.93)';
  ctx.strokeStyle='#558469';ctx.lineWidth=.8;
  ctx.beginPath();ctx.roundRect(x-w/2,y-8,w,16,4);ctx.fill();ctx.stroke();
  ctx.fillStyle='#20523a';ctx.font='bold 9.5px Arial,sans-serif';
  ctx.fillText(label,x,y+.5);used.push({d,x,y});
 }
 ctx.restore();return used;
}
g.RaceOverviewDistanceLabels=Object.freeze({draw,courseIndependent:true,sourceSvgUntouched:true});
})(typeof window!=='undefined'?window:globalThis);
