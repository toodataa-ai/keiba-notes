/* Course-agnostic screen label deconfliction. Physical positions untouched. */
(function(g){'use strict';
const MAX=18,CANDIDATES=[0,-5,5,-9,9,-13,13,-18,18],CLEAR=24;
function overlap(pts,clear=CLEAR){let area=0,pairs=0;
 for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){
  const v=Math.max(0,clear-Math.hypot(pts[i].x-pts[j].x,pts[i].y-pts[j].y));
  if(v>1e-4){pairs++;area+=v*v}
 }return {pairs,penalty:Number(area.toFixed(4))}}
function create(){
 const prior=new Map();let result=null;
 function reset(){prior.clear();result=null}
 function layout(points,{normalAt,minimumDistance=CLEAR}={}){
  if(typeof normalAt!=='function')throw Error('NUMBER_NORMAL_REQUIRED');
  const all=points.map(p=>{const vec=normalAt(p),len=Math.hypot(vec.x,vec.y)||1;
   return {...p,nx:vec.x/len,ny:vec.y/len}
  }).sort((a,b)=>a.number-b.number);
  const old=all.map(h=>prior.get(h.number)||0),shift=old.slice();
  function cost(i,x){
   const h=all[i],px=h.x+h.nx*x,py=h.y+h.ny*x;
   let value=.04*x*x+.02*(x-old[i])**2;
   for(let j=0;j<all.length;j++){
    if(i===j)continue;
    const q=all[j],dx=px-q.x-q.nx*shift[j],dy=py-q.y-q.ny*shift[j];
    value+=2*Math.max(0,minimumDistance-Math.hypot(dx,dy))**2;
   }return value;
  }
  for(let pass=0;pass<3;pass++)for(let i=0;i<all.length;i++){
   let best=cost(i,shift[i]),picked=shift[i];
   for(const t of CANDIDATES){const v=cost(i,t);
    if(v<best-1e-8){best=v;picked=t}}
   shift[i]=picked;
  }
  const out=all.map((h,i)=>{
   const dx=Math.max(-MAX,Math.min(MAX,old[i]+(shift[i]-old[i])*.16));
   prior.set(h.number,dx);
   return {...h,anchorX:h.x,anchorY:h.y,x:h.x+h.nx*dx,y:h.y+h.ny*dx,labelOffset:dx}
  });
  const base=overlap(all,minimumDistance),after=overlap(out,minimumDistance);
  result={base,after,maxShiftPx:Math.max(0,...out.map(p=>Math.abs(p.labelOffset))),
   displaced:out.filter(p=>Math.abs(p.labelOffset)>2).length,physicalPositionsUnchanged:true};
  return out;
 }
 return Object.freeze({reset,layout,metrics:()=>result});
}
g.RaceMarkerVisibility=Object.freeze({create,overlap,maxOffsetPx:MAX,courseIndependent:true});
})(typeof window!=='undefined'?window:globalThis);
