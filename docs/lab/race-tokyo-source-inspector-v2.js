/* Local original-source inspector: never uploads, stores or executes imported source. */
(function(g){'use strict';
const $=id=>document.getElementById(id),ui=$('sourceAuditFiles');if(!ui)return;
let source=null,route=null,data=null,snapshots=null,index=0,generation=0;
const checkpoints=[0,100,130,300,900,1145,1474.1,1600,1920,1950,1980,2000,2032];
const hex=bytes=>Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
async function loadFiles(files){
 const token=++generation;
 source=null;route=null;data=null;snapshots=null;inspector.lastView=null;inspector.lastRaster=null;$('sourceRasterResult').textContent='';$('sourceAuditViews').hidden=true;
 $('sourceAuditStatus').textContent='原図のハッシュと検査データを確認中…';
 try{
  const list=Array.from(files),json=list.find(f=>f.name==='audit-local.json'),svg=list.find(f=>f.name==='source-local.svg');
  if(list.length!==2||!json||!svg||json.size>2e6||svg.size>8e6)throw Error('指定のJSONとSVGの2ファイルを選択してください');
  const candidate=JSON.parse(await json.text()),built=g.RaceTokyoSourceAudit.build(candidate);
  const content=await svg.arrayBuffer(),sha=hex(await crypto.subtle.digest('SHA-256',content));
  if(sha!==candidate.sourceSvgSha256)throw Error('原図SVGのハッシュが一致しません');
  const shots=candidate.numericalCheckpoints;
  if(!Array.isArray(shots)||shots.length!==13)throw Error('共通エンジンの静止検査データがありません');
  for(const [i,s] of shots.entries()){
   if(s.distance!==checkpoints[i]||!Number.isFinite(s.t)||s.t<0||!Array.isArray(s.horses)||s.horses.length!==18||
     new Set(s.horses.map(h=>h.number)).size!==18)throw Error('静止検査データが不正です');
   for(const h of s.horses){if(!Number.isInteger(h.number)||h.number<1||h.number>18||
      !Number.isFinite(h.d)||h.d<0||h.d>2000)throw Error('馬番または距離が不正です');built.point(h.displayD,h.lane);}
  }
  const blob=URL.createObjectURL(new Blob([content],{type:'image/svg+xml'})),img=new Image();
  try{img.src=blob;await img.decode();}finally{URL.revokeObjectURL(blob);}
  if(token!==generation)return;
  if(Math.abs(img.naturalWidth/img.naturalHeight-built.width/built.height)>.003)
   throw Error('原図の縦横比が一致しません');
  source=img;route=built;data=candidate;snapshots=shots;index=0;
  $('sourceCheckpoint').replaceChildren(...checkpoints.map((d,i)=>{
   const opt=document.createElement('option');opt.value=i;opt.textContent=d>2000?'ゴール後':d+'m';return opt;
  }));
  $('sourceAuditViews').hidden=false;
  $('sourceAuditStatus').textContent='ローカル原図一致。静止照合のみ／走路・途中距離は未承認。';
  draw();
 }catch(e){if(token===generation)$('sourceAuditStatus').textContent='読込停止：'+e.message;}
}
function surface(id){const c=$(id),r=c.getBoundingClientRect(),w=r.width,h=r.height,px=Math.min(2,devicePixelRatio||1);
 c.width=Math.round(w*px);c.height=Math.round(h*px);const ctx=c.getContext('2d');ctx.setTransform(c.width/w,0,0,c.height/h,0,0);ctx.clearRect(0,0,w,h);return{ctx,w,h};}
function drawView(id,detail){
 const {ctx,w,h}=surface(id),shot=snapshots[index];
 const lead=shot.horses.reduce((a,b)=>b.displayD>a.displayD?b:a),center=route.point(lead.displayD,lead.lane);
 const scale=detail?w/135:Math.min(w/route.width,h/route.height),cx=detail?center.x:route.width/2,cy=detail?center.y:route.height/2;
 const project=p=>({x:w/2+(p.x-cx)*scale,y:h/2+(p.y-cy)*scale});
 ctx.save();ctx.translate(w/2-cx*scale,h/2-cy*scale);ctx.scale(scale,scale);
 ctx.drawImage(source,0,0,route.width,route.height);
 // Rails are an OVERLAY candidate, never painted into or substituted for the source.
 for(const side of ['inner','outer']){ctx.strokeStyle=side==='inner'?'#ffc64c':'#7356ee';ctx.lineWidth=(detail?1.2:.8)/scale;ctx.beginPath();
  for(let d=0;d<=2120;d+=1){const p=route.rail(d,side);if(!d)ctx.moveTo(p.x,p.y);else ctx.lineTo(p.x,p.y);}ctx.stroke();}
 ctx.restore();
 const colors=[['#fff','#111'],['#15191f','#fff'],['#d9142f','#fff'],['#164bb8','#fff'],['#ffde30','#111'],['#1d8c49','#fff'],['#f9811f','#111'],['#f4a1c5','#111']];
 const positions=[];
 for(const horse of shot.horses){
  const p=route.point(horse.displayD,horse.lane),q=project(p),n=horse.number,i=n<=12?Math.floor((n-1)/2):n<=15?6:7;
  const rad=detail?10:4.5;ctx.beginPath();ctx.arc(q.x,q.y,rad,0,2*Math.PI);ctx.fillStyle=colors[i][0];ctx.fill();ctx.strokeStyle='#26362f';ctx.lineWidth=1;ctx.stroke();
  ctx.font='bold '+(detail?11:6.5)+'px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=colors[i][1];ctx.fillText(n,q.x,q.y);
  positions.push({number:n,d:horse.d,displayD:horse.displayD,lane:horse.lane,x:p.x,y:p.y,screenX:q.x,screenY:q.y});
 }
 return{positions,scale,sourceScaleX:scale,sourceScaleY:scale};
}
function draw(){if(!source)return;
 const overview=drawView('sourceOverview',false),detail=drawView('sourceDetail',true),shot=snapshots[index];
 $('sourceSnapshotNote').textContent='指定 '+(shot.distance>2000?'ゴール後':shot.distance+'m')+' ／ 物理時刻 '+shot.t.toFixed(2)+'秒 ／ 描画先頭 '+Math.max(...shot.horses.map(h=>h.displayD)).toFixed(3)+'m。共通エンジンの静止状態。馬番は実距離・実レーンで投影し、重なり回避の移動はしていません。線は走路境界の候補です。';
 inspector.lastView={overview,detail,checkpoint:shot.distance,canAnimate:false};
}
function rasterAudit(){
 if(!source)throw Error('LOCAL_SOURCE_REQUIRED');
 const c=document.createElement('canvas');c.width=2480;c.height=Math.round(c.width*route.height/route.width);
 const ctx=c.getContext('2d',{willReadFrequently:true}),scale=c.width/route.width;
 ctx.drawImage(source,0,0,route.width*scale,route.height*scale);
 const pixels=ctx.getImageData(0,0,c.width,c.height).data,mark=data.finishMark;
 if(!mark||Object.values(mark).some(v=>!Number.isFinite(v)))throw Error('FINISH_MARK_INVALID');
 let samples=0,bad=0,finishInk=0;const failures=[];
 function check(p){
  const x=Math.round(p.x*scale),y=Math.round(p.y*scale),i=4*(y*c.width+x);samples++;
  const [r,gr,b]=pixels.slice(i,i+3);
  const green=r<55&&gr>110&&b<155;
  // SVG image rasterization can filter one source pixel around black finish ink.
  // Only black/green mixtures near the independently extracted finish rectangle qualify; white/dirt never do.
  const finish=p.x>=mark.x-1&&p.x<=mark.x+mark.width+1&&p.y>=mark.y-1&&p.y<=mark.y+mark.height+1&&r<55&&gr<=176&&b<=90;
  if(finish)finishInk++;
  if(!green&&!finish){bad++;if(failures.length<12)failures.push({x:p.x,y:p.y,r,gr,b});}
 }
 function disc(d,lane){const p=route.point(d,lane);check(p);for(let i=0;i<8;i++){const a=i*Math.PI/4;check({x:p.x+.6*Math.cos(a),y:p.y+.6*Math.sin(a)});}}
 for(let lane=0;lane<=16;lane++)for(let d=0;d<=2120;d+=.25)disc(d,lane);
 for(const s of snapshots)for(const horse of s.horses)disc(horse.displayD,horse.lane);
 const result={samples,bad,finishInk,finishAntialiasToleranceSourcePx:1,failures,canAnimate:false,sourceSvgSha256:data.sourceSvgSha256};
 inspector.lastRaster=result;
 $('sourceRasterResult').textContent='原図画素検査 '+samples.toLocaleString('ja-JP')+'点 ／ 芝帯外 '+bad+'点（ゴール線の黒色 '+finishInk+'点は別集計）。走路承認ではありません。';
 return result;
}
const inspector={loadFiles,draw,rasterAudit,lastView:null,lastRaster:null};g.RaceTokyoSourceInspector=inspector;
ui.addEventListener('change',()=>loadFiles(ui.files));
$('sourceCheckpoint').addEventListener('change',e=>{index=Number(e.target.value);draw();});
$('sourceRasterBtn').addEventListener('click',()=>{try{rasterAudit();}catch(e){$('sourceRasterResult').textContent='検査停止：'+e.message;}});
new ResizeObserver(draw).observe($('sourceAuditViews'));
})(window);
