/* Compile a locally verified Cairo SVG into Canvas vectors. No bundled artwork,
 * DOM insertion, scripts, external references or nonuniform image scaling. */
(function(g){'use strict';
function compile(text){
 const doc=new DOMParser().parseFromString(text,'image/svg+xml');
 if(doc.querySelector('parsererror'))throw Error('TOKYO_VECTOR_PARSE');
 const root=doc.documentElement,allowed=new Set(['svg','defs','g','path','use','clipPath']);
 const ids=new Map();
 for(const e of root.querySelectorAll('*')){
  if(!allowed.has(e.localName))throw Error('TOKYO_VECTOR_ELEMENT');
  for(const a of e.attributes)if(/^on/i.test(a.name)||/url\((?!#[^)]+\))/.test(a.value))throw Error('TOKYO_VECTOR_EXTERNAL');
  if(e.id)ids.set(e.id,e);
 }
 const box=root.getAttribute('viewBox').split(/\s+/).map(Number);
 if(box.length!==4||box.some(x=>!Number.isFinite(x))||box[0]||box[1]||box[2]<=0||box[3]<=0)throw Error('TOKYO_VECTOR_VIEWBOX');
 function transform(e){
  const raw=e.getAttribute('transform');if(!raw)return null;
  const m=/^matrix\(([^)]+)\)$/.exec(raw),values=m?.[1].split(/[,\s]+/).filter(Boolean).map(Number);
  if(!values||values.length!==6||values.some(x=>!Number.isFinite(x)))throw Error('TOKYO_VECTOR_TRANSFORM');return values;
 }
 const attributes=['fill','fill-opacity','fill-rule','stroke','stroke-opacity','stroke-width','stroke-linecap','stroke-linejoin','stroke-miterlimit'];
 function node(e,ancestors=new Set()){
  if(ancestors.has(e))throw Error('TOKYO_VECTOR_CYCLE');
  const next=new Set(ancestors);next.add(e);
  if(e.localName==='defs')return()=>{};
  const styles=Object.fromEntries(attributes.filter(k=>e.hasAttribute(k)).map(k=>[k,e.getAttribute(k)]));
  const matrix=transform(e),path=e.localName==='path'?new Path2D(e.getAttribute('d')):null;
  let clipping=null;
  if(e.hasAttribute('clip-path')){
   const id=/^url\(#([^)]*)\)$/.exec(e.getAttribute('clip-path'))?.[1],clip=ids.get(id);
   if(!clip||clip.localName!=='clipPath'||clip.children.length!==1||clip.firstElementChild.localName!=='path')throw Error('TOKYO_VECTOR_CLIP');
   clipping={path:new Path2D(clip.firstElementChild.getAttribute('d')),rule:clip.firstElementChild.getAttribute('clip-rule')||'nonzero'};
  }
  let children;
  if(e.localName==='use'){
   const ref=e.getAttributeNS('http://www.w3.org/1999/xlink','href')||e.getAttribute('href');
   if(!ref?.startsWith('#')||!ids.has(ref.slice(1)))throw Error('TOKYO_VECTOR_REFERENCE');
   children=[node(ids.get(ref.slice(1)),next)];
  }else children=Array.from(e.children).map(c=>node(c,next));
  const x=Number(e.getAttribute('x')||0),y=Number(e.getAttribute('y')||0);
  return(ctx,parent)=>{
   const style={...parent,...styles};ctx.save();
   if(matrix)ctx.transform(...matrix);
   if(e.localName==='use')ctx.translate(x,y);
   if(clipping)ctx.clip(clipping.path,clipping.rule);
   if(path){
    if(style.fill!=='none'){ctx.fillStyle=style.fill||'#000';ctx.globalAlpha=Number(style['fill-opacity']??1);ctx.fill(path,style['fill-rule']||'nonzero');}
    if(style.stroke&&style.stroke!=='none'){
     ctx.strokeStyle=style.stroke;ctx.globalAlpha=Number(style['stroke-opacity']??1);ctx.lineWidth=Number(style['stroke-width']||1);
     ctx.lineCap=style['stroke-linecap']||'butt';ctx.lineJoin=style['stroke-linejoin']||'miter';ctx.miterLimit=Number(style['stroke-miterlimit']||4);ctx.stroke(path);
    }
   }
   for(const c of children)c(ctx,style);ctx.restore();
  };
 }
 const draw=node(root),width=620,height=620*9/13,scale=Math.min(width/box[2],height/box[3]);
 return Object.freeze({width,height,scaleX:scale,scaleY:scale,
  render(ctx){ctx.save();ctx.translate((width-box[2]*scale)/2,(height-box[3]*scale)/2);ctx.scale(scale,scale);draw(ctx,{});ctx.restore();}});
}
g.RaceTokyoSourceVectorV5=Object.freeze({compile});
})(window);
