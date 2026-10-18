/* LAB v5: source-registered, INDEPENDENT inner/outer turf rails.
 * A compact 60-knot image trace derived from the 620x430 original Umapot
 * diagram. Color/shape comparisons recorded in KYOTO_DUAL_RAIL_SHAPE_AUDIT_V5.
 * Neither route nor label positioning affects the unchanged RaceSimEngine,
 * official predictions, odds, final_bets, PDFs or results. */
(function(global){'use strict';
const id='kyoto_turf_inner_2000',DISTANCE=2000,WIDTH_M=27;
const JRA_DIMENSIONS=Object.freeze({distanceM:2000,lapInnerA:1782.8,
 firstTurnDistanceM:308.7,homeStraightA:328.4,
 minTurfWidthM:27,maxTurfWidthM:38,elevationInnerM:3.1});
const sections=Object.freeze([
 {from:0,to:308.7,kind:'straight',name:'スタート後の直線'},
 {from:308.7,to:530,kind:'turn',name:'1コーナー'},
 {from:530,to:720,kind:'turn',name:'2コーナー'},
 {from:720,to:1270,kind:'straight',name:'向正面'},
 {from:1270,to:1435,kind:'turn',name:'3コーナー'},
 {from:1435,to:1671.6,kind:'turn',name:'4コーナー'},
 {from:1671.6,to:2000,kind:'straight',name:'最後の直線'}
]);
// [race metres, inner.x, inner.y, outer.x, outer.y]. Image pixel space.
// Both rail paths come from distinct outlines of the INNER green turf, rather
// than from offsetting a model centerline with a constant 16px corridor.
// The derivative is C1-continuous, with no section-boundary resets.
const K=[[0,350,306.5,350,328.5],[100,304.6,306.5,304.6,328.5],[146,283.8,305.5,283.8,328.5],[200,259.3,305.5,259.3,328.5],[250,236.6,304.9,236.6,328.1],[272,226.6,302.4,226.6,327.2],[290,218.5,298.8,218.5,325.8],[309,210,295.8,209.6,322.9],[330,201.9,293.3,198.4,317.9],[360,193.8,285.3,185.1,308.1],[378,191.6,279.2,178.7,301.7],[400,188.5,273.1,171.7,293],[419,185.2,267.7,166.5,284.1],[450,180.7,256,159.7,267.5],[480,178.2,242.4,155.4,249.6],[500,178.4,232.6,154.8,236.9],[530,181.1,218.1,155,218.3],[564,187.2,203.6,149.8,202.2],[600,198.2,189.8,160.4,186.4],[650,215.1,176.3,177.8,169.3],[700,235.2,169.7,198.4,159.9],[720,243.5,168.4,207,157.6],[748,253.6,166.7,218.8,154.3],[774,262.2,164.7,236.7,154],[800,271.1,162.5,243.8,149.2],[838,284.7,159.3,252.9,140],[863,294.1,157.3,269.1,139.7],[900,308.3,154.1,290.7,138.9],[953,329.1,149.3,311.6,128.7],[1000,348,145,334.6,123.6],[1100,389.7,135.8,383.5,113.7],[1200,432.6,128.2,431.8,103.8],[1246,451.9,130.8,453.8,99.8],[1270,461.8,135.4,466.1,98.4],[1300,478.4,143,491.7,107.4],[1323,489.1,151.5,509.4,119.3],[1335,493.4,157.3,517.2,127.5],[1350,497.7,164.9,521.7,142.2],[1363,501.2,171.6,523.6,155.3],[1377,505,179,528.2,166.3],[1400,511,192.1,534.6,184.9],[1417,514.5,202.8,539.6,199],[1435,516.9,214.5,543,214.3],[1457,518.2,224.8,544.3,227.7],[1500,518,244,543.7,252.9],[1523,516.4,253.6,545.2,268.1],[1536,515.1,258.7,546,277.5],[1550,513.5,263.8,544.1,286.5],[1570,510.8,270.2,537.8,297],[1600,506.9,278.5,526.7,310.9],[1628,503.3,287.6,514.9,323.7],[1638,501.1,290.5,509.9,327.6],[1650,497.6,293,503,329.7],[1672,489.4,296.4,489.8,329],[1700,473,302.3,473,328.4],[1719,461.7,305.3,461.7,328.5],[1749,443.8,306.6,443.8,328.5],[1800,413.4,306.5,413.4,328.5],[1900,353.7,306.5,353.7,328.5],[2000,294,306.5,294,328.5]];
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const secants=K.slice(1).map((r,i)=>r.slice(1).map((v,c)=>
 (v-K[i][c+1])/(r[0]-K[i][0])));
const tangents=K.map((r,i)=>{
 if(i===0)return secants[0];
 if(i===K.length-1)return secants.at(-1);
 const h0=K[i][0]-K[i-1][0],h1=K[i+1][0]-K[i][0];
 return secants[i-1].map((a,c)=>(a*h1+secants[i][c]*h0)/(h0+h1));
});
function railCoordinates(distance){
 const d=clamp(Number(distance)||0,0,DISTANCE);
 let lo=0,hi=K.length-1;
 while(lo<hi){const mid=(lo+hi)>>1;if(K[mid][0]<d)lo=mid+1;else hi=mid}
 const i=Math.min(K.length-2,Math.max(0,lo-1));
 const a=K[i],b=K[i+1],h=b[0]-a[0],t=clamp((d-a[0])/h,0,1);
 const t2=t*t,t3=t2*t;
 const h00=2*t3-3*t2+1,h10=t3-2*t2+t,h01=-2*t3+3*t2,h11=t3-t2;
 const val=[];
 for(let j=1;j<=4;j++)val.push(h00*a[j]+h10*h*tangents[i][j-1]+
  h01*b[j]+h11*h*tangents[i+1][j-1]);
 if(distance>DISTANCE){
  const extra=Math.min(45,distance-DISTANCE);
  const last=tangents.at(-1);
  for(let j=0;j<4;j++)val[j]+=last[j]*extra;
 }
 return {inner:{x:val[0],y:val[1]},outer:{x:val[2],y:val[3]}};
}
function segment(d){
 return sections.find(s=>d<=s.to+1e-8)||sections.at(-1);
}
function center(d){
 const c=railCoordinates(d),x=(c.inner.x+c.outer.x)/2,
  y=(c.inner.y+c.outer.y)/2;
 const a=railCoordinates(Math.max(0,d-.5)),b=railCoordinates(Math.min(2000,d+.5));
 const dx=(b.inner.x+b.outer.x-a.inner.x-a.outer.x)/2,
  dy=(b.inner.y+b.outer.y-a.inner.y-a.outer.y)/2;
 const m=Math.hypot(dx,dy)||1,s=segment(d);
 return {x,y,tx:dx/m,ty:dy/m,kind:s.kind,section:s.name};
}
function rails(d){
 const r=railCoordinates(d);
 return {...r,center:center(d),
  widthPx:Math.hypot(r.outer.x-r.inner.x,r.outer.y-r.inner.y),
  widthMetres:WIDTH_M};
}
function fraction(lane){
 return clamp((1.8+Math.max(0,Number(lane)||0)*1.65)/WIDTH_M,.025,.95);
}
function point(d,lane=0){
 const r=rails(d),f=fraction(lane);
 return {x:r.inner.x+(r.outer.x-r.inner.x)*f,
  y:r.inner.y+(r.outer.y-r.inner.y)*f,d,lane,section:r.center.section};
}
function runners(state){
 return state.horses.map(h=>({number:h.number,d:h.displayD??h.d,lane:h.lane,
  ...point(h.displayD??h.d,h.lane),finished:h.finished}));
}
function validate(){
 if(K.length!==60||K[0][0]!==0||K.at(-1)[0]!==2000)throw Error('DUAL_RAIL_KNOTS');
 for(let i=1;i<K.length;i++)if(K[i][0]<=K[i-1][0])throw Error('DUAL_RAIL_ORDER');
 for(let d=0;d<=2000;d+=1){
  const r=rails(d),w=r.widthPx;
  if(!Number.isFinite(w)||w<17||w>39)throw Error('DUAL_RAIL_WIDTH_'+d+'_'+w);
  if(![r.inner.x,r.inner.y,r.outer.x,r.outer.y].every(Number.isFinite))
   throw Error('DUAL_RAIL_NAN_'+d);
  if(d>0){
   const p=rails(d-1);
   for(const key of ['inner','outer']){
    if(Math.hypot(r[key].x-p[key].x,r[key].y-p[key].y)>1.5)
     throw Error('DUAL_RAIL_DISCONTINUITY_'+key+'_'+d);
   }
  }
 }
 return true;
}
const api=Object.freeze({id,distance:DISTANCE,widthPx:22,
 widthMetres:WIDTH_M,jraDimensions:JRA_DIMENSIONS,
 sourceImageSize:{width:620,height:430},
 illustratedRouteModel:'Two traced source-image green rails, independent C1 splines, not surveyed coordinates',
 sections,segment,center,rails,fraction,point,runners,validate,
 railCoordinates,railKnotCount:K.length,densePointCount:2001,denseSpacingM:1});
api.validate();
global.RaceCleanCourse=api;
})(typeof window!=='undefined'?window:globalThis);
