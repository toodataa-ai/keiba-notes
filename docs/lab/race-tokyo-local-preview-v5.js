/* Local-source LAB evaluation. Never enables the old unapproved geometry.
 * Source, safety and repeatability checks precede every seed's cached replay. */
(function(g){'use strict';
const $=id=>document.getElementById(id),STEP=.08;
let generation=0,ready=null,playing=false,time=0,wall=null,camera=null,lastFrame=null;
const colors=[['#fff','#111'],['#15191f','#fff'],['#d9142f','#fff'],['#164bb8','#fff'],['#ffde30','#111'],['#1d8c49','#fff'],['#f9811f','#111'],['#f4a1c5','#111']];
const ui={start:$('startBtn'),prepare:$('prepareLocalBtn'),speed:$('playSpeed'),seed:$('previewSeed'),reset:$('resetLocalBtn'),status:$('localPreviewStatus')};
const hud={clock:$('raceClock'),split:$('raceSplit'),splitLabel:$('raceSplitLabel'),banner:$('raceBanner'),heading:$('raceHeading'),podium:$('racePodium'),results:$('raceResults'),rows:$('raceRows')},hudCache={};
function lock(){generation++;ready=null;playing=false;wall=null;camera=null;time=0;lastFrame=null;
 ui.start.disabled=true;ui.speed.disabled=true;ui.reset.disabled=true;$('previewCheckpoint').disabled=true;ui.start.textContent='走行ロック中';
 ui.prepare.disabled=!g.RaceTokyoSourceInspector.getLocalInputs();ui.seed.disabled=false;hud.banner.hidden=true;hud.results.hidden=true;
 $('previewWarning').textContent='原図・走路・安全監査待ち。評価再生は無効です。';
 for(const id of ['liveBroadcast','liveOverview']){const c=$(id);c.getContext('2d').clearRect(0,0,c.width,c.height);}
}
async function prepare(){
 lock();const token=generation,inputs=g.RaceTokyoSourceInspector.getLocalInputs();if(!inputs)return;
 ui.prepare.disabled=true;ui.seed.disabled=true;
 try{
  const seed=Number(ui.seed.value);if(!Number.isInteger(seed)||seed<1||seed>999999)throw Error('シードは1〜999999の整数にしてください');
  ui.status.textContent='原図と走路の固定ハッシュを照合中…';
  const session=await g.RaceTokyoSourcePhysicsV5.prepare(inputs.manifest);
  if(token!==generation)return;
  const vector=g.RaceTokyoSourceVectorV5.compile(inputs.svg),route=g.RaceTokyoSourcePhysicsV5.inspect(session);
  await new Promise(r=>setTimeout(r,0));ui.status.textContent='原図ベクター上で芝帯・馬体四隅・走路の折返しを検査中…';
  const mask=g.RaceTokyoSourceMaskV5.audit(vector,route,inputs.manifest.finishMark);
  if(mask.bad||mask.folds||mask.sourceScaleX!==mask.sourceScaleY)throw Error('原図の走路監査に不合格：'+JSON.stringify(mask));
  if(token!==generation)return;
  ui.status.textContent='共通エンジンで全18頭の完走・余走とフレーム間の安全性を検査中…';
  const a=await g.RaceTokyoSafetyV5.run(session,seed);if(token!==generation)return;
  ui.status.textContent='同一シードを再計算し、全フレームと時計の再現性を検査中…';
  const b=await g.RaceTokyoSafetyV5.run(session,seed);if(token!==generation)return;
  if(JSON.stringify(a)!==JSON.stringify(b))throw Error('同一シードの再現性が一致しません');
  ready={vector,route,frames:a.frames,summary:a.summary,result:a.result,mask,session,seed};
  ui.start.disabled=false;ui.speed.disabled=false;ui.reset.disabled=false;$('previewCheckpoint').disabled=false;ui.seed.disabled=false;ui.prepare.disabled=false;
  ui.start.textContent='評価再生';ui.status.textContent='端末内監査合格：芝帯外0、走路折返し0、フレーム間重なり0、全18頭完走・余走、全フレーム再現一致。シード '+seed+'。';
  $('previewWarning').textContent='端末内の評価再生のみ有効。距離配分・勾配・半径は近似です。正式走路は未承認・目視承認待ち。STAGING・本番には移行しません。';
  draw(true);
 }catch(e){if(token===generation){lock();ui.status.textContent='評価再生を停止：'+e.message;}}
}
function surface(canvas){const r=canvas.getBoundingClientRect(),w=Math.max(1,r.width),h=Math.max(1,r.height),dpr=Math.min(2.5,g.devicePixelRatio||1);
 const pw=Math.round(w*dpr),ph=Math.round(h*dpr);if(canvas.width!==pw||canvas.height!==ph){canvas.width=pw;canvas.height=ph;}
 const ctx=canvas.getContext('2d');ctx.setTransform(pw/w,0,0,ph/h,0,0);ctx.clearRect(0,0,w,h);return{ctx,w,h};}
function number(ctx,n,x,y,scale=1){const i=n<=12?Math.floor((n-1)/2):n<=15?6:7,r=12*scale;
 ctx.save();ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=colors[i][0];ctx.fill();ctx.lineWidth=Math.max(.6,scale);ctx.strokeStyle='#1c3025';ctx.stroke();ctx.fillStyle=colors[i][1];ctx.font='bold '+(13*scale)+'px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(n,x,y);ctx.restore();}
function frame(){const frames=ready.frames,i=Math.min(frames.length-1,Math.floor(time/STEP)),a=frames[i],b=frames[Math.min(i+1,frames.length-1)],alpha=Math.max(0,Math.min(1,(time-a.t)/(b.t-a.t||STEP)));
 const points=g.RaceFrameInterpolator.interpolate(a.horses,b.horses,alpha);
 return{a,b,alpha,points,leader:Math.max(...points.map(p=>p.d))};}
function mapped(canvas,points,cam,overview){const {ctx,w,h}=surface(canvas),route=ready.route;
 const scale=overview?Math.min(w/ready.vector.width,h/ready.vector.height):(w<500?8:10),cx=overview?ready.vector.width/2:cam.x,cy=overview?ready.vector.height/2:cam.y,angle=overview?0:cam.angle;
 const cos=Math.cos(angle),sin=Math.sin(angle),project=p=>({x:w/2+scale*(cos*(p.x-cx)-sin*(p.y-cy)),y:h/2+scale*(sin*(p.x-cx)+cos*(p.y-cy))});
 ctx.fillStyle='#edf2e8';ctx.fillRect(0,0,w,h);ctx.save();ctx.translate(w/2,h/2);ctx.rotate(angle);ctx.scale(scale,scale);ctx.translate(-cx,-cy);ready.vector.render(ctx);ctx.restore();
 const positions=points.map(p=>{const world=route.point(p.d,p.lane),q=project(world);number(ctx,p.number,q.x,q.y,overview?.38:.83);return{...p,worldX:world.x,worldY:world.y,x:q.x,y:q.y};});
 return{positions,sourceScaleX:scale,sourceScaleY:scale,angle,scale};}
function draw(reset=false,elapsed=0){if(!ready)return;const f=frame(),lead=f.points.reduce((a,b)=>b.d>a.d?b:a),route=ready.route,p=route.center(lead.d);
 const center=f.points.reduce((v,h)=>{const q=route.point(h.d,h.lane);v.x+=q.x/18;v.y+=q.y/18;return v;},{x:0,y:0});
 let angle=Math.PI-Math.atan2(p.ty,p.tx);
 if(camera){while(angle-camera.angle>Math.PI)angle-=2*Math.PI;while(angle-camera.angle< -Math.PI)angle+=2*Math.PI;}
 if(reset||!camera)camera={...center,angle};else{const k=1-Math.exp(-Math.max(0,elapsed)/.22);camera.x+=(center.x-camera.x)*k;camera.y+=(center.y-camera.y)*k;camera.angle+=(angle-camera.angle)*k;}
 const overview=mapped($('liveOverview'),f.points,camera,true);let broadcast;
 if(f.leader>=1920){const goal=g.RaceCleanGoalView.render({canvas:$('liveBroadcast'),points:f.points,leaderNo:lead.number,focusedNo:null,paintNumber:number,maxLane:16,distance:2000,turn:'右',screenSpan:100});
  const r=$('liveBroadcast').getBoundingClientRect();broadcast={...goal,positions:f.points.map(q=>({...q,...g.RaceCleanGoalView.goalScreenPosition(q.d,q.lane,2000,r.width,r.height,16,'右',1,100)}))};
 }else broadcast=mapped($('liveBroadcast'),f.points,camera,false);
 const occurred=x=>x!==null&&x<=time+1e-9?x:null;
 const hstate={...f.b,t:time,firstFinishTime:occurred(f.b.firstFinishTime),splitTime:occurred(f.b.splitTime),allCrossedAt:occurred(f.b.allCrossedAt),
  horses:f.b.horses.map(h=>({...h,finishTime:occurred(h.finishTime)}))};g.RaceBroadcastHud.render(hstate,hud,hudCache);
 hud.banner.hidden=hstate.allCrossedAt===null;
 $('cameraMode').textContent=f.leader>=1920?'固定ゴール前カメラ / 横幅100m / 右→左':'原図追跡カメラ / 実走路は左回り';
 $('raceProgress').textContent='先頭 '+Math.min(2000,f.leader).toFixed(1)+'m / 2,000m';
 lastFrame={time,leaderD:f.leader,points:f.points,overview,broadcast,camera:{...camera},courseTurn:'左',screenTurn:'右',goalSpanM:100,seed:ready.seed};
}
function seek(distance){$('previewCheckpoint').value=String(distance);if(!ready)throw Error('TOKYO_LOCAL_AUDITS_REQUIRED');playing=false;wall=null;ui.start.textContent='評価再生';
 const frames=ready.frames;let i=frames.findIndex(f=>Math.max(...f.horses.map(h=>h.d))>=distance);
 if(i<0)i=frames.length-1;const b=frames[i],a=frames[Math.max(0,i-1)],da=Math.max(...a.horses.map(h=>h.d)),db=Math.max(...b.horses.map(h=>h.d));
 time=a.t+(b.t-a.t)*Math.max(0,Math.min(1,(distance-da)/(db-da||1)));draw(true);return lastFrame;}
function toggle(){if(!ready)return;if(time>=ready.frames.at(-1).t){time=0;camera=null;}playing=!playing;wall=null;ui.start.textContent=playing?'一時停止':'評価再生';}
function tick(now){if(playing&&ready){if(wall!==null){const elapsed=Math.max(0,Math.min(.1,(now-wall)/1000))*Number(ui.speed.value);time=Math.min(ready.frames.at(-1).t,time+elapsed);draw(false,elapsed);
 if(time>=ready.frames.at(-1).t){playing=false;ui.start.textContent='最初から評価再生';}}wall=now;}requestAnimationFrame(tick);}
ui.prepare.addEventListener('click',prepare);ui.start.addEventListener('click',toggle);ui.reset.addEventListener('click',()=>seek(0));
ui.seed.addEventListener('input',()=>{lock();ui.status.textContent='シード変更後は端末内監査をやり直してください。';});
$('previewCheckpoint').addEventListener('change',e=>seek(Number(e.target.value)));
window.addEventListener('tokyo-source-clear',()=>{lock();ui.status.textContent='原図未読込。';});window.addEventListener('tokyo-source-ready',()=>{lock();ui.status.textContent='原図読込済み。端末内監査を実行すると評価再生を準備します。';});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&playing){playing=false;wall=null;ui.start.textContent='評価再生';}});
new ResizeObserver(()=>draw()).observe($('liveBroadcast'));
g.RaceTokyoLocalPreviewV5=Object.freeze({prepare,seek,draw:()=>draw(),get lastFrame(){return lastFrame;},get audit(){return ready?JSON.parse(JSON.stringify({summary:ready.summary,mask:ready.mask,result:ready.result,session:ready.session})):null;},get isPlaying(){return playing;}});
lock();requestAnimationFrame(tick);
})(window);
