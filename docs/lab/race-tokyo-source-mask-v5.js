/* Actual imported vector raster + full 2.55m x .8m body corners, not only centres.
 * A passing mask is a LAB schematic test, never official route approval. */
(function(g){'use strict';
function audit(vector,route,mark){
 const c=document.createElement('canvas');c.width=2480;c.height=Math.round(c.width*vector.height/vector.width);
 const ctx=c.getContext('2d',{willReadFrequently:true}),scale=c.width/vector.width;
 ctx.scale(scale,scale);vector.render(ctx);const pixels=ctx.getImageData(0,0,c.width,c.height).data;
 let samples=0,bad=0,folds=0,minJacobian=Infinity;const failures=[];
 function check(p){const x=Math.round(p.x*scale),y=Math.round(p.y*scale),i=4*(y*c.width+x);samples++;
  const r=pixels[i],gr=pixels[i+1],b=pixels[i+2],alpha=pixels[i+3];
  const green=alpha>240&&r<55&&gr>110&&b<155;
  const finish=p.x>=mark.x-1&&p.x<=mark.x+mark.width+1&&p.y>=mark.y-1&&p.y<=mark.y+mark.height+1&&alpha>240&&r<55&&gr<=176&&b<=90;
  if(!green&&!finish){bad++;if(failures.length<8)failures.push({x:p.x,y:p.y,r,gr,b,alpha});}
 }
 function bodyPoint(d,lane){
  const x=Math.max(0,Math.min(2120,d)),p=route.center(x),offset=9-18*lane/16;
  let dx=0,dy=0;if(d!==x){const a=route.center(x===0?.1:2119.9),sign=x===0?-1:1;
   dx=(p.x-a.x)*Math.abs(d-x)*10*sign;dy=(p.y-a.y)*Math.abs(d-x)*10*sign;
   // At the initial endpoint p-a already points backwards.
   if(x===0){dx=-dx;dy=-dy;}
  }
  return{x:p.x+dx+p.ty*offset,y:p.y+dy-p.tx*offset};
 }
 for(let lane=0;lane<=16;lane++)for(let d=0;d<=2120;d+=.25){
  const p=route.point(d,lane);check(p);
  for(const fore of [-1.275,1.275])for(const side of [-.4/1.65,.4/1.65])check(bodyPoint(d+fore,lane+side));
  const a=bodyPoint(d-.05,lane),b=bodyPoint(d+.05,lane),q=bodyPoint(d,lane+.01);
  const jac=((b.x-a.x)*(q.y-p.y)-(b.y-a.y)*(q.x-p.x))/.001;
  minJacobian=Math.min(minJacobian,jac);if(!Number.isFinite(jac)||jac<=0)folds++;
 }
 return{samples,bad,folds,minJacobian,failures,bodyLengthM:2.55,bodyWidthM:.8,stepM:.25,sourceScaleX:vector.scaleX,sourceScaleY:vector.scaleY,canAnimate:false};
}
g.RaceTokyoSourceMaskV5=Object.freeze({audit});
})(window);
