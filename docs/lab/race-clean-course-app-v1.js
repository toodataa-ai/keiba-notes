/* LAB v22: source-authenticated real-runner fixture + independent postrace benchmark in LAB only; original SVG untouched.
 * Source bitmap is never redrawn as an approximate course. A browser-local,
 * fourfold high-quality resample is a display cache, not a new detailed source.
 * Only synthetic 18-horse data; no official prediction/odds/bets/PDF changes.
 */
(function(){'use strict';
const $=id=>document.getElementById(id);
const model=window.RaceCleanCourse;
const turf=window.RaceCleanTurf;
// Actual Oct 18 entrants are used ONLY on explicit selection. The real
// finish positions / laps belong to a wholly separate holdout reference.
const FIXTURE_SYNTHETIC=window.RaceLab18Fixture;
const FIXTURE_REAL=window.RaceRealShuka2026Fixture;
const REAL_TRIAL='shuka2026';
let trialMode=new URLSearchParams(location.search).get('trial')===REAL_TRIAL?
 REAL_TRIAL:'synthetic';
let fixture=trialMode===REAL_TRIAL?FIXTURE_REAL:FIXTURE_SYNTHETIC;
let entries=fixture.horses();
let race={...fixture.entry(),horses:entries};
let postraceBenchmarkVisible=false;
const hud=window.RaceBroadcastHud,resultCache={signature:''};
const frameMotion=window.RaceFrameInterpolator;
const MOTION_INTERPOLATION_ENABLED=new URLSearchParams(location.search).get('motion')!=='legacy';
let framePrevious=null,frameCurrent=null;
function captureFrame(){return frameMotion.capture(engine.state.horses);}

function hudElements(){return {clock:$('clock'),split:$('splitTime'),splitLabel:$('splitLabel'),banner:$('finishBanner'),heading:$('finishHeading'),podium:$('finishPodium'),results:$('fullResults'),rows:$('resultsBody')}}
const trialIsReal=()=>trialMode===REAL_TRIAL;
// Ported faithfully from working Kyoto 1400 RaceSimNumbers.marker.
const JRA_WAKU=Object.freeze([
 {name:'白',fill:'#fffdf5',text:'#111827',border:'#111827'},
 {name:'黒',fill:'#15191f',text:'#ffffff',border:'#f4f4f5'},
 {name:'赤',fill:'#d9142f',text:'#ffffff',border:'#fff4f4'},
 {name:'青',fill:'#164bb8',text:'#ffffff',border:'#f1f5ff'},
 {name:'黄',fill:'#ffde30',text:'#171717',border:'#35301c'},
 {name:'緑',fill:'#1d8c49',text:'#ffffff',border:'#edfff4'},
 {name:'橙',fill:'#f9811f',text:'#111827',border:'#422509'},
 {name:'桃',fill:'#f4a1c5',text:'#171717',border:'#542e3f'}
]);
function jraWaku(number,fieldSize=18){
 // Only the separately flagged one-runner course demonstration gets a
 // neutral white marker. Official 8–18 runner JRA waku validation is unchanged.
 
 if(!Number.isInteger(number)||!Number.isInteger(fieldSize)||
   fieldSize<8||fieldSize>18||number<1||number>fieldSize)
   throw Error('JRA_WAKU_FIELD_INVALID');
 const base=Math.floor(fieldSize/8),extra=fieldSize%8;
 let first=1;
 for(let i=0;i<8;i++){
   const n=base+(i>=8-extra?1:0);
   if(number<first+n)return {waku:i+1,...JRA_WAKU[i]};
   first+=n;
 }
 throw Error('JRA_WAKU_NOT_FOUND');
}
function raceNumberMarker(ctx,number,x,y,scale,focused=false,leading=false,fieldSize=18,passing=false){
 if(!Number.isInteger(number)||number<1||!Number.isFinite(x)||!Number.isFinite(y))
  throw Error('SIM_NUMBER_POSITION_INVALID');
 // Equal diameter for all horses. Focus uses the same circumference:
 // a gold stroke, without any larger marker or external gold halo.
 const radius=13.5*scale;
 const waku=jraWaku(number,fieldSize);
 ctx.save();
 ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);
 ctx.fillStyle=waku.fill;ctx.fill();
 ctx.lineWidth=(focused?3.4:2.1)*scale;
 ctx.strokeStyle=focused?'#e9af30':waku.border;
 ctx.stroke();
 if(focused){
   // The inner hairline keeps the original JRA bracket border recognizable.
   ctx.beginPath();ctx.arc(x,y,radius-2.5*scale,0,Math.PI*2);
   ctx.lineWidth=.8*scale;ctx.strokeStyle=waku.border;ctx.stroke();
 }
 if(passing){
   // A thin ring around the genuine crossing point; no position offset.
   ctx.beginPath();ctx.arc(x,y,radius+7*scale,0,Math.PI*2);
   ctx.lineWidth=2.6*scale;ctx.strokeStyle='#b6f3a0';ctx.stroke();
 }
 ctx.textAlign='center';ctx.textBaseline='middle';
 ctx.fillStyle=waku.text;
 ctx.font='900 '+(number>9?16:18)*scale+'px Arial, sans-serif';
 ctx.fillText(String(number),x,y+.4*scale);
 ctx.restore();
 return {number,x,y,waku:waku.waku};
}

function waku(no){const w=jraWaku(no,race.field_size);return {fill:w.fill,ink:w.text};}
let engine,playing=false,last=0,acc=0,renderStamp=0,focusNo='leader',
 lastCamera=null,lastPaintCamera=null,lastLabelPositions=[],lastRenderedPoints=[],cameraRenderTime=0,
 visualLaneState=new Map(),visualRenderTime=null,
 finishSequenceActive=false,finishSequenceElapsedMs=0,finishSequenceDone=false;
const FINISH_SEQUENCE_MS=3200;
let vectorReady=false,originalError=false,turfReady=false,turfError=null,turfStats=null;
let lastGoalFrame=null,curveLensStats=null,curveLensError=null,
 sharedGeometryStats=null,sharedGeometryError=null;
const CURVE_LENS_ENABLED=new URLSearchParams(location.search).get('lens')!=='off';
// LAB v21 default: reusable course-independent arclength projection.
 // Append ?geometry=legacy to revert instantly; no production change.
const SHARED_IMAGE_GEOMETRY=new URLSearchParams(location.search).get('geometry')!=='legacy';
const SOURCE_VECTOR='assets/kyoto-umapot-course-clean-v8.svg';
function rebuildFixtureUi(){
 const focus=$('focus');
 focus.innerHTML='<option value="leader">先頭</option>';
 for(const h of entries){
  const opt=document.createElement('option');opt.value=String(h.number);
  opt.textContent=h.number+'番'+(trialIsReal()?' '+h.name:'');
  focus.appendChild(opt);
 }
 focus.value='leader';focusNo='leader';
 const grid=$('horseGrid');grid.innerHTML='';
 grid.classList.toggle('real-field',trialIsReal());
 for(const h of entries){
  const col=waku(h.number),chip=document.createElement('div');
  chip.className='horsechip'+(trialIsReal()?' is-real':'');
  chip.style.background=col.fill;chip.style.color=col.ink;
  const number=document.createElement('strong');number.textContent=h.number;
  chip.appendChild(number);
  if(trialIsReal()){
   const name=document.createElement('small');name.textContent=h.name;
   chip.appendChild(name);
  }
  chip.title=h.number+'番 '+h.name;
  grid.appendChild(chip);
 }
 const host=$('runningOrder');host.innerHTML='';delete host.dataset.ready;
 const real=trialIsReal();
 $('trialMode').value=trialMode;
 $('labDescription').textContent=real?
  '2026年10月18日・秋華賞｜発走前に記録された実出走馬17頭で仮想シミュレーション。実際のレースの再現映像ではありません。':
  'LAB開発中・非公式／架空18頭。実況も全体図も同じうまぽっと原画像を使用し、枠色の馬番丸そのものが走ります。正式予想・買い目・払戻とは無関係です。';
 $('horseGridTitle').textContent=real?'2026年秋華賞・実出走馬17頭':'架空18頭の馬番';
 $('trialDescription').textContent=real?
  '出走馬・前走位置取り・能力9項目は発走前保存データ。3歳牝馬・芝中距離の共通基準速度（暫定）を使用。実際の着順・時計・ラップは走行計算に使用しません。':
  '架空18頭の比較テスト。実レースデータは読み込んでいません。';
 $('benchmarkPanel').hidden=!real;
 $('benchmarkResults').hidden=true;
 $('compareBtn').textContent='JRA公式結果と比較（別データ）';
 postraceBenchmarkVisible=false;
}
function switchTrial(next){
 if(next!==REAL_TRIAL&&next!=='synthetic')return;
 trialMode=next;fixture=next===REAL_TRIAL?FIXTURE_REAL:FIXTURE_SYNTHETIC;
 entries=fixture.horses();
 race={...fixture.entry(),horses:entries};
 rebuildFixtureUi();
 reset();
}
function compareWithOfficialResult(){
 // Separate, postrace-only readout. Never call this function from reset,
 // physical stepping, lane control or prestart fixture construction.
 if(!trialIsReal())return;
 const ref=window.RaceRealShuka2026Reference;
 if(!ref||ref.race_id!==race.source_report?.match(/shuka-sho/)?.[0]&&
    ref.race_id!=='2026-10-18-shuka-sho')
  throw Error('OFFICIAL_POSTRACE_HOLDOUT_MISSING');
 const sim=RaceSimEngine.create({...race,horses:fixture.horses()},{seed:2026,bias:'neutral'});
 const orders=[],splitTargets=[1000,...ref.officialCorners.map(c=>c.distanceApprox)]
  .sort((a,b)=>a-b);
 let i=0,loops=0,splitTime=null,splitPace=null;
 while(i<splitTargets.length&&loops++<3200&&!sim.state.finished){
  if(sim.state.leader>=splitTargets[i]){
   const distance=splitTargets[i];
   if(distance===1000){splitTime=sim.state.t;splitPace=sim.state.splitPaceBand||sim.state.paceBand;}
   else orders.push({distance,order:sim.state.horses.slice()
    .sort((a,b)=>b.d-a.d||a.number-b.number).map(h=>h.number)});
   i++;
  }else sim.step(.08);
 }
 if(orders.length!==4||splitTime===null)throw Error('BENCHMARK_MILESTONE_MISSING');
 const root=$('benchmarkResults');root.innerHTML='';
 const note=document.createElement('p');
 note.textContent='観測されたJRA公式のコーナー通過順・ラップと仮想レースの隊列を照合します。実際の結果はエンジンへ入力していません。';
 root.appendChild(note);
 const table=document.createElement('table');table.className='benchmark-table';
 const thead=document.createElement('thead');
 thead.innerHTML='<tr><th>地点</th><th>JRA公式（先頭5頭）</th><th>仮想走行（先頭5頭）</th></tr>';
 table.appendChild(thead);
 const tbody=document.createElement('tbody');
 for(const corner of ref.officialCorners){
  const actual=corner.order.slice(0,5);
  const virtual=orders.find(o=>Math.abs(o.distance-corner.distanceApprox)<1e-6).order.slice(0,5);
  const row=document.createElement('tr');
  for(const value of [corner.label,actual.join('・'),virtual.join('・')]){
   const cell=document.createElement('td');cell.textContent=value;row.appendChild(cell);
  }
  tbody.appendChild(row);
 }
 table.appendChild(tbody);root.appendChild(table);
 const time=document.createElement('p');
 time.textContent='1000m通過（先頭）：JRA実際 '+ref.cumulative200m[4].toFixed(1)+'秒 ／ 仮想 '+
  splitTime.toFixed(1)+'秒（仮想ペース '+splitPace+'）。実際の通過地点とシミュレータの距離目盛りには近似差があります。';
 root.appendChild(time);
 const source=document.createElement('a');
 source.href=ref.source_url;source.target='_blank';source.rel='noopener noreferrer';
 source.textContent='出典：JRA 第31回秋華賞・公式レース結果';
 root.appendChild(source);
}
function reset(){
 engine=RaceSimEngine.create({...race,horses:fixture.horses()},{seed:2026,bias:'neutral'});
 playing=false;last=0;acc=0;lastCamera=null;lastPaintCamera=null;lastRenderedPoints=[];
 framePrevious=frameCurrent=captureFrame();
 cameraRenderTime=0;visualRenderTime=null;visualLaneState.clear();
 finishSequenceActive=false;finishSequenceElapsedMs=0;finishSequenceDone=false;
 const banner=$('finishBanner');if(banner)banner.hidden=true;
 resultCache.signature='';$('fullResults').hidden=true;$('resultsBody').replaceChildren();
 $('startBtn').textContent='▶ スタート';
 paint();
}
function advanceTo(distance){
 reset();
 let i=0;
 while(engine.state.leader<distance&&!engine.state.finished&&i++<1500)engine.step(.12);
 // Seek is a jump in simulation time. Do NOT interpolate the camera from
 // the starting gate across 900 metres: it leaves every horse off-screen.
 lastCamera=null;lastPaintCamera=null;cameraRenderTime=0;visualRenderTime=null;
 framePrevious=frameCurrent=captureFrame();acc=0;
 // A seek invalidates every previous rendered pose. Without this reset,
 // a paused view would retain the starting gate although physics advanced.
 lastRenderedPoints=[];visualLaneState.clear();
 finishSequenceActive=false;finishSequenceElapsedMs=0;finishSequenceDone=false;
 const banner=$('finishBanner');if(banner)banner.hidden=true;
 paint();return engine.state;
}
function sizeCanvas(canvas){
 const rect=canvas.getBoundingClientRect();
 const w=Math.max(1,rect.width),h=Math.max(1,rect.height);
 const dpr=Math.min(2.5,Math.max(1,window.devicePixelRatio||1));
 const pxW=Math.round(w*dpr),pxH=Math.round(h*dpr);
 if(canvas.width!==pxW||canvas.height!==pxH){canvas.width=pxW;canvas.height=pxH}
 const ctx=canvas.getContext('2d');
 ctx.setTransform(pxW/w,0,0,pxH/h,0,0);
 ctx.clearRect(0,0,w,h);
 return {ctx,w,h};
}
function pixelAlignedCamera(camera,ctx){
 // Safari composites the original SVG as a CSS transform while the horse
 // markers live on a high-DPI canvas. Without a shared device-pixel
 // translation the two independently rasterised layers can shimmer.
 // Keep camera scale and all original source coordinates IDENTICAL;
 // snap only their COMMON final screen translation to the device grid.
 const deviceScale=ctx.getTransform().a||Math.max(1,window.devicePixelRatio||1);
 const left=camera.cx-camera.x*camera.scale;
 const top=camera.cy-camera.y*camera.scale;
 const alignedLeft=Math.round(left*deviceScale)/deviceScale;
 const alignedTop=Math.round(top*deviceScale)/deviceScale;
 return {...camera,cx:camera.cx+alignedLeft-left,cy:camera.cy+alignedTop-top};
}
function backdrop(camera){
 // The photo and canvas must share EXACTLY the same affine projection.
 // This transform crops the unchanged image; it never draws new rail shapes.
 const left=camera.cx-camera.x*camera.scale;
 const top=camera.cy-camera.y*camera.scale;
 const transform='translate('+left+'px,'+top+'px) scale('+camera.scale+')';
 for(const id of ['liveCourseImage']){
  const element=$(id);
  if(element)element.style.transform=transform;
 }
}
function sourceImageReady(img){
 // Crucial Safari/WebKit fix: a responsive SVG <img> can report its
 // layout-scaled naturalWidth (368x255 on iPhone), despite the exact
 // original file being 620x430. Pixel-equality wrongly blocked painting.
 // The source viewBox and intended 620:430 coordinate space are unchanged.
 return Boolean(img&&img.complete&&img.naturalWidth>0&&img.naturalHeight>0&&
  Math.abs(img.naturalWidth/img.naturalHeight-620/430)<.025&&
  img.getAttribute('src')===SOURCE_VECTOR);
}
function verifyVectorSource(){
 const a=$('realCourseImage'),b=$('liveCourseImage');
 const sourceLoaded=sourceImageReady(a);
 const broadcastLoaded=sourceImageReady(b);
 vectorReady=sourceLoaded&&broadcastLoaded;
 // Do not let an unrelated viewport's computed SVG naturalWidth prevent
 // loading. Calibrate from the image's scalable source viewBox instead.
 if(sourceLoaded&&!turfReady&&!turfError){
  try{turfStats=turf.create(a);turfReady=true;}
  catch(err){
   turfError=String(err);console.error('KYOTO_TURF_MASK_INIT',err);
   const note=document.querySelector('.source-credit');
   if(note)note.textContent='コース初期化に失敗しました: '+turfError;
  }
 }
 if(turfReady&&!curveLensStats&&!curveLensError){
  try{curveLensStats=window.RaceCleanCurveCamera.profile(turf);}
  catch(err){curveLensError=String(err);console.error('LAB_CURVE_LENS_CALIBRATION',err);}
 }
 if(turfReady&&curveLensStats&&SHARED_IMAGE_GEOMETRY&&
    !sharedGeometryStats&&!sharedGeometryError){
  try{
   // Use the same generic mapper tested independently for Kyoto1400 and
   // Tokyo2000. Only named physically grounded course landmarks are data.
   // Pass existing (read-only) camera gain to the global optimizer.
   const anchors=[0,...model.sections.map(s=>s.to)];
   const shared=window.RaceCourseImageGeometry.build({
    distanceM:model.distance,anchorsM:anchors,
    pointAt:(d,lane)=>turf.pointAtImageDistance(d,lane),
    // Always fit geometry against the same reference lens, even if the
    // viewer selects lens=off. Toggling a CAMERA option must never move
    // horses along the source course illustration.
    displayGain:d=>window.RaceCleanCurveCamera.gain(d)
   });
   const safety=turf.activateSharedGeometry(shared);
   sharedGeometryStats={...safety,anchors};
   turfStats=turf.stats();
   // Source-pixel geometry changed but the image is untouched: rerun the
   // same source-derived lens profile with the newly mapped course.
   curveLensStats=window.RaceCleanCurveCamera.profile(turf);
  }catch(err){
   sharedGeometryError=String(err);
   console.error('LAB_GENERIC_IMAGE_GEOMETRY_BLOCKED',err);
  }
 }
 if(vectorReady)originalError=false;
}
function position(p,camera){
 return {x:camera.cx+(p.x-camera.x)*camera.scale,
         y:camera.cy+(p.y-camera.y)*camera.scale};
}
// For a crowd's leader camera, use SOFT race-order weights (no membership
// toggles when a horse crosses +/-80m or when the lead changes at the wire).
// The focal point can still follow an individually selected horse.
function cameraFor(points,w,h,chosen,autoLeader=true){
 let center=points.find(p=>p.number===chosen)||points[0];
 const leaderDistance=Math.max(...points.map(p=>p.d));
 if(autoLeader){
  // Lock the camera to the RACE DISTANCE instead of the physical pack's
  // moment-to-moment centroid. Group membership and overtakes cannot
  // make the entire course abruptly jump or appear to collapse.
  center=turf.point(Math.max(0,Math.min(2000,leaderDistance-10)),3);
 }
 // Fix the optical zoom; the old density-based group bounds changed camera
 // magnification at every overtake and caused visible frame-to-frame shakes.
 return {x:center.x,y:center.y,cx:w*.54,cy:h*.51,
  // Tighter normal broadcast. Fixed across overtakes to prevent breathing.
  scale:(w<540?8.8:9.7)*
   (CURVE_LENS_ENABLED&&curveLensStats?
    window.RaceCleanCurveCamera.gain(leaderDistance):1)};
}
// At 4x playback, physics advances in 80ms simulation steps. A canvas drawn
// between steps used to alternate between a stationary and jumping position.
// Extrapolate ONLY visual positions over the unconsumed simulation accumulator
// and low-pass rapid physical LANE reversals; physics state stays immutable.
function displayPoints(state){
 if(state.finished&&finishSequenceActive){
  // Extend the drawn run-off gently after the virtual results are locked.
  // This is a display-only coast, not an extra RaceSimEngine step.
  const progress=Math.min(1,finishSequenceElapsedMs/FINISH_SEQUENCE_MS);
  const coast=6*(1-Math.pow(1-progress,3));
  return state.horses.map(h=>{
   const d=(h.displayD??h.d)+coast;
   return {number:h.number,d,lane:h.lane,
    ...turf.point(d,h.lane),finished:true};
  });
 }
 if(!playing&&!state.finished){
  // On pause, retain exactly the last drawn positions. Resetting to the
  // unsmoothed physics samples made numbers snap sideways when stopping.
  return lastRenderedPoints.length?lastRenderedPoints:turf.runners(state);
 }
 if(state.finished){
  visualLaneState.clear();visualRenderTime=null;
  return turf.runners(state);
 }
 // Two confirmed physical poses are blended, rather than predicting forward
 // and then snapping towards a newer sample. No independent lane low-pass.
 if(MOTION_INTERPOLATION_ENABLED&&framePrevious&&frameCurrent){
  const alpha=acc/frameMotion.STEP_SECONDS;
  return frameMotion.interpolate(framePrevious,frameCurrent,alpha)
   .map(p=>({...p,...turf.point(p.d,p.lane)}));
 }
 const fraction=Math.max(0,Math.min(acc,.08));
 const simTime=state.t+fraction;
 const dt=visualRenderTime===null?0:Math.max(0,Math.min(.16,simTime-visualRenderTime));
 visualRenderTime=simTime;
 return state.horses.map(h=>{
  const trail=h.trail||[];
  const last=trail.at(-1),before=trail.at(-2);
  const travel=last&&before?Math.max(0,last.d-before.d):0;
  // Longitudinal and lateral filtering are DISPLAY-ONLY. Smooth the
  // fraction-to-fraction change in speed and lane across physics ticks.
  // Always apply the ORIGINAL turf.point(d,lane), so smoothing cannot
  // drag a number into white or distort the source course drawing.
  const predictedD=(h.displayD??h.d)+Math.min(1.7,travel/.08*fraction);
  const predictedLane=Math.max(0,Math.min(14,h.lane+(h.laneVelocity||0)*fraction));
  const previous=visualLaneState.get(h.number);
  const alongBlend=1-Math.exp(-dt/.070),laneBlend=1-Math.exp(-dt/.21);
  const smoothD=previous===undefined?predictedD:
    Math.max(previous.d,previous.d+(predictedD-previous.d)*alongBlend);
  const smoothLane=previous===undefined?predictedLane:
    previous.lane+(predictedLane-previous.lane)*laneBlend;
  visualLaneState.set(h.number,{d:smoothD,lane:smoothLane});
  return {number:h.number,d:smoothD,lane:smoothLane,
   ...turf.point(smoothD,smoothLane),finished:h.finished};
 });
}
// A circled number IS the moving horse (Kyoto 1400 contract). No pixel
// position displacement to evade overlap; dense packs may obscure neighbours.
function markers(ctx,points,loc,focused,mini=false){
 const sorted=points.map(p=>({...p,actual:position(p,loc)}))
  .sort((a,b)=>Number(a.number===focused)-Number(b.number===focused)||a.number-b.number);
 const displayed=[];
 for(const p of sorted){
  const x=p.actual.x,y=p.actual.y;
  // All 18 horses receive the same scale in each view, including focus.
  // No offset from the running coordinates and no larger highlighted marker.
  const compact=loc.w<540;
  // +14.7% on mobile and +10.5% desktop; mini overview unchanged.
  // Every horse (including focus) retains precisely the same radius.
  const scale=mini?.48:(points.length>=12?(compact?.78:.84):.90);
  const radius=13.5*scale;
  if(x+radius<0||x-radius>loc.w||y+radius<0||y-radius>loc.h)continue;
  raceNumberMarker(ctx,p.number,x,y,scale,p.number===focused,false,race.field_size,false);
  displayed.push({...p,x,y,r:radius});
 }
 return displayed;
}
function updateRunningOrder(points,chosen){
 const host=$('runningOrder');
 if(!host)return;
 if(!host.dataset.ready){
  for(const p of points){
   const btn=document.createElement('button');
   btn.type='button';btn.className='position-chip';btn.dataset.horse=p.number;
   const horse=entries.find(h=>h.number===p.number);
   btn.setAttribute('aria-label',p.number+'番'+(horse?' '+horse.name:'')+'を追跡');
   btn.addEventListener('click',()=>{
    focusNo=String(p.number);$('focus').value=focusNo;
    lastCamera=null;paint();
   });
   host.appendChild(btn);
  }
  host.dataset.ready='true';
 }
 const chips=new Map([...host.children].map(x=>[Number(x.dataset.horse),x]));
 const order=points.slice().sort((a,b)=>b.d-a.d||a.number-b.number);
 for(let i=0;i<order.length;i++){
  const p=order[i],chip=chips.get(p.number),col=waku(p.number);
  chip.textContent=String(p.number);
  chip.style.backgroundColor=col.fill;
  chip.style.color=col.ink;
  chip.classList.toggle('is-focus',p.number===chosen);
  const horse=entries.find(h=>h.number===p.number);
  chip.title=(i+1)+'番手・'+p.number+'番 '+(horse?.name||'')+'を追跡';
  host.appendChild(chip);
 }
 $('orderNote').textContent='左から先頭順 / '+order.length+'頭。タップで追跡';
}
function paint(){
 // Refuse to paint numbers using the obsolete JPEG-position centerline
 // while the real Umapot SVG green-corridor occupancy is loading.
 if(!engine||!turfReady)return;
 const state=engine.state,points=displayPoints(state);
 lastRenderedPoints=points;
 const chosen=focusNo==='leader'?state.leadingNo:Number(focusNo);
 const live=sizeCanvas($('broadcast'));
 // Transparent canvas: original Umapot image is the only course background.
 const target=cameraFor(points,live.w,live.h,chosen,focusNo==='leader');
 if(finishSequenceActive){
  // Ease from the horse-focused close camera to a wider finish tableau.
  const p=Math.min(1,finishSequenceElapsedMs/FINISH_SEQUENCE_MS);
  const eased=p*p*(3-2*p);
  target.scale*=1-.22*eased;
 }
 // Stabilize view with a real elapsed-time exponential filter; frame rate
 // changes do not change the amount of camera smoothing.
 const now=performance.now(),dt=cameraRenderTime?
  Math.min(.06,(now-cameraRenderTime)/1000):0;
 cameraRenderTime=now;
 if(!lastCamera)lastCamera=target;
 else {
  const blend=1-Math.exp(-dt/.20);
  lastCamera={...target,
   x:lastCamera.x+(target.x-lastCamera.x)*blend,
   y:lastCamera.y+(target.y-lastCamera.y)*blend,
   // Uniform crop zoom uses the exact SAME affine scale for both the
   // untouched source SVG and all 18 corresponding numbers.
   scale:lastCamera.scale+(target.scale-lastCamera.scale)*blend};
 }
 const paintCamera=pixelAlignedCamera(lastCamera,live.ctx);
 lastPaintCamera=paintCamera;
 backdrop(paintCamera);
 const labels=markers(live.ctx,points,{...paintCamera,w:live.w,h:live.h},chosen);
 lastLabelPositions=labels;
 // Kyoto1400 contract: exactly 80 metres from the finish, replace the
 // zoomed course with the right-to-left GOAL-board television camera.
 // RaceSimEngine.goalCamera was already computed on physical race distance.
 const goalCanvas=$('goalCamera');
 if(goalCanvas){
  const goalMode=Boolean(state.goalCamera||state.firstFinishTime!==null);
  goalCanvas.hidden=!goalMode;
  if(goalMode){
   const p=finishSequenceActive?
     Math.min(1,finishSequenceElapsedMs/FINISH_SEQUENCE_MS):0;
   const eased=p*p*(3-2*p);
   lastGoalFrame=window.RaceCleanGoalView.render({
    canvas:goalCanvas,points,leaderNo:state.leadingNo,focusedNo:chosen,
    paintNumber:raceNumberMarker,maxLane:14,distance:2000,turn:'右',
    fieldSize:race.field_size,pullback:1+.22*eased
   });
  }else lastGoalFrame=null;
 }
 const map=sizeCanvas($('overview'));
 // Transparent numbers over the ACTUAL original 620x430 course diagram.
 const overview={x:310,y:215,cx:map.w/2,cy:map.h/2,
  scale:Math.min(map.w/620,map.h/430),w:map.w,h:map.h};
 markers(map.ctx,points,overview,chosen,true);
 updateRunningOrder(points,chosen);
 $('progress').textContent=Math.round(state.leader)+'m / 2000m';
 hud.render(state,hudElements(),resultCache);
 $('section').textContent=(state.allCrossedAt!==null?'全馬ゴール・余走中':
   state.goalCamera?'ゴール板固定カメラ':model.center(state.leader).section)+
   ' ／ 内4列 '+state.horses.filter(h=>h.lane<=3.45).length+'頭'+
   ' ／ 内へ '+state.totalInsideMoves+'回';
 // Shared HUD shows each simulated horse at the actual wire crossing.

}
function tick(ts){
 if(!last)last=ts;
 let delta=Math.min(.06,(ts-last)/1000);last=ts;
 if(playing){
  if(!engine.state.finished){
   acc+=delta*Number($('speed').value);
   let count=0;
   while(acc>=frameMotion.STEP_SECONDS&&count++<8&&!engine.state.finished){
     framePrevious=frameCurrent;engine.step(frameMotion.STEP_SECONDS);
     frameCurrent=captureFrame();acc-=frameMotion.STEP_SECONDS;
    }
  }
  if(engine.state.finished){
   // The physics state is final. Keep the animation alive for a gentle
   // 3.2s real-time camera pullback and 6m display-only coasting.
   finishSequenceActive=true;
   finishSequenceElapsedMs=Math.min(FINISH_SEQUENCE_MS,
    finishSequenceElapsedMs+delta*1000);
   if(finishSequenceElapsedMs>=FINISH_SEQUENCE_MS){
    playing=false;finishSequenceDone=true;
    $('startBtn').textContent='▶ 再スタート';
   }
  }
  if(ts-renderStamp>14||finishSequenceDone){paint();renderStamp=ts}
 }
 requestAnimationFrame(tick);
}
function setup(){
 if(!hud||!frameMotion||!FIXTURE_REAL||FIXTURE_REAL.horses().length!==17)
  throw Error('REAL_SHUKA_PRESTART_FIXTURE_MISSING');
 for(const id of ['realCourseImage','liveCourseImage']){
  const img=$(id);
  if(!img)throw Error('ORIGINAL_VECTOR_MISSING');
  img.addEventListener('load',()=>{verifyVectorSource();paint()});
  img.addEventListener('error',()=>{originalError=true;vectorReady=false});
 }
 verifyVectorSource();
 rebuildFixtureUi();
 $('trialMode').addEventListener('change',e=>switchTrial(e.target.value));
 $('compareBtn').addEventListener('click',()=>{
  postraceBenchmarkVisible=!postraceBenchmarkVisible;
  $('benchmarkResults').hidden=!postraceBenchmarkVisible;
  $('compareBtn').textContent=postraceBenchmarkVisible?'結果比較を閉じる':
   'JRA公式結果と比較（別データ）';
  if(postraceBenchmarkVisible)compareWithOfficialResult();
 });
 $('focus').addEventListener('change',e=>{
  focusNo=e.target.value;lastCamera=null;lastPaintCamera=null;cameraRenderTime=0;
  visualLaneState.clear();visualRenderTime=null;paint();
 });
 $('startBtn').addEventListener('click',()=>{
  if(engine.state.finished)reset();
  playing=true;$('startBtn').textContent='▶ 再生中';
 });
 $('pauseBtn').addEventListener('click',()=>{
  playing=false;$('startBtn').textContent='▶ 再開';
 });
 $('resetBtn').addEventListener('click',reset);
 addEventListener('resize',()=>{lastCamera=null;lastPaintCamera=null;cameraRenderTime=0;paint()});
 reset();
 const params=new URLSearchParams(location.search);
 const checkpoint=Number(params.get('checkpoint'));
 if(params.has('checkpoint')&&Number.isFinite(checkpoint)&&checkpoint>=0&&checkpoint<=2000)
  advanceTo(checkpoint);
 requestAnimationFrame(tick);
}
window.CleanLab=Object.freeze({
 getState:()=>engine?.state,
 setTrial:mode=>{switchTrial(mode);return trialMode},
 trial:()=>({id:trialMode,fixtureId:fixture.id,fieldSize:race.field_size,
  names:entries.map(h=>({number:h.number,name:h.name,style:h.style})),
  prestart:trialIsReal(),postraceComparisonVisible:postraceBenchmarkVisible}),
 // Cheap, per-animation-frame diagnostic for REAL 4x playback QA.
 frameSample:()=>({t:engine?.state?.t??0,playing,zoom:lastCamera?.scale??0,
  camera:lastCamera?{x:lastCamera.x,y:lastCamera.y}:null,
  pixelCamera:lastPaintCamera?{x:lastPaintCamera.x,y:lastPaintCamera.y,
   cx:lastPaintCamera.cx,cy:lastPaintCamera.cy}:null,
  finishSequenceActive,finishSequenceDone,finishSequenceElapsedMs,
  horses:lastRenderedPoints.map(p=>({number:p.number,x:p.x,y:p.y,d:p.d,lane:p.lane})),
 motionModel:MOTION_INTERPOLATION_ENABLED?'fixed-pose-interpolation':'legacy',
 motionAlpha:acc/frameMotion.STEP_SECONDS}),
 inspect:()=>{
  const points=turfReady?(lastRenderedPoints.length?lastRenderedPoints:
  turf.runners(engine.state)):model.runners(engine.state);
  const selected=focusNo==='leader'?engine.state.leadingNo:Number(focusNo);
  const chosen=points.find(p=>p.number===selected)||points[0];
  const screen=lastPaintCamera?position(chosen,lastPaintCamera):null;
  const live=$('broadcast').getBoundingClientRect();
  const rect=$('overview').getBoundingClientRect();
  const image=$('realCourseImage');
  return {leader:engine.state.leader,positions:points,
 motionModel:MOTION_INTERPOLATION_ENABLED?'fixed-pose-interpolation':'legacy',
 motionAlpha:acc/frameMotion.STEP_SECONDS,
   nominalSpeedProfile:engine.state.nominalSpeedProfile,
   nominalCruiseSpeedMps:engine.state.nominalCruiseSpeedMps,
   trialMode,fixtureId:fixture.id,raceFieldSize:race.field_size,
   realPrestartOnly:trialIsReal(),
   originalImageSrc:image?.getAttribute('src')||null,
   originalLoaded:sourceImageReady(image),
   liveImageLoaded:sourceImageReady($('liveCourseImage')),
   sourceNaturalSize:image?{
    width:image.naturalWidth,height:image.naturalHeight}:null,
   liveImageSrc:$('liveCourseImage')?.getAttribute('src')||null,
   originalError,vectorReady,turfReady,turfError,turfStats,
   sharedGeometryRequested:SHARED_IMAGE_GEOMETRY,
   sharedGeometryEnabled:turf.sharedGeometryEnabled(),
   sharedGeometryStats,sharedGeometryError,
   cameraLensEnabled:CURVE_LENS_ENABLED,cameraLensReady:Boolean(curveLensStats),
   cameraLensError:curveLensError,cameraLensStats:curveLensStats,
   cameraLensGain:CURVE_LENS_ENABLED&&curveLensStats?
      window.RaceCleanCurveCamera.gain(engine.state.leader):1,
   rawPackPhysicalGapM:Math.max(...points.map(p=>p.d))-
      Math.min(...points.map(p=>p.d)),
   rawPackChordSourcePx:(()=>{const a=points.reduce((a,b)=>a.d>b.d?a:b);
      const b=points.reduce((a,b)=>a.d<b.d?a:b);
      return Math.hypot(a.x-b.x,a.y-b.y);})(),
   visualInterpolationEnabled:true,fixedCameraZoom:!finishSequenceActive,
   markerScaleMobile:.78,markerScaleDesktop:.84,miniMarkerScale:.48,
   foregroundCameraPixelSnapped:true,visualLongitudinalTau:.070,
   visualLateralTau:.21,cameraSmoothTau:.20,
   cameraSnapErrorPx:lastCamera&&lastPaintCamera?
    Math.hypot(lastPaintCamera.cx-lastCamera.cx,
      lastPaintCamera.cy-lastCamera.cy):0,
   goalBoardVisible:Boolean(!$('goalCamera')?.hidden),
   goalFrame:lastGoalFrame,goalCameraSwitchDistance:1920,
   finishSequenceActive,finishSequenceDone,finishSequenceElapsedMs,
   finishedBannerVisible:Boolean(!$('finishBanner')?.hidden),
   visualSimulationTime:visualRenderTime,
   displayedDeltas:points.map(p=>({
     number:p.number,d:p.d-(engine.state.horses.find(h=>h.number===p.number)?.displayD||0),
     lane:p.lane-(engine.state.horses.find(h=>h.number===p.number)?.lane||0)
   })),
   highResolutionMode:'publisher-original-svg-not-resampled-jpeg',
   broadcastClock:$('clock').textContent,splitClock:$('splitTime').textContent,
   podiumNames:$('finishPodium').textContent,allResultRows:$('resultsBody').children.length,
   resultsVisible:!$('fullResults').hidden,combinedRaceView:!!document.querySelector('.race-view-grid'),
   leaderboardDisplayed:false,
   normalBroadcastZoom:8.8,normalDesktopZoom:9.7,
   unchangedBackgroundAffineOnly:true,
   actualNumberCircles:true,paintedTrack:false,leaderLines:false,
   mapAspect:rect.width/Math.max(1,rect.height),
   zoom:lastCamera?.scale??0,
   visibleOrder:[...$('runningOrder').children].map(el=>Number(el.dataset.horse)),
   liveLabelPositions:lastLabelPositions.map(p=>({number:p.number,x:p.x,y:p.y,r:p.r,
     anchorX:p.actual.x,anchorY:p.actual.y})),
   directMarkerMaxError:lastLabelPositions.reduce((m,p)=>
     Math.max(m,Math.hypot(p.x-p.actual.x,p.y-p.actual.y)),0),
   turfBadCenters:turfReady?points.filter(p=>!turf.isGreen(p.x,p.y)).length:null,
   turfBadDiscs:turfReady?points.filter(p=>
     !turf.discOnTurf(p.x,p.y,
       13.5*(live.width<540?.78:.84)/Math.max(1.7,lastCamera?.scale||2.3)+.6)).length:null,
   calibratedRunPositions:turfReady,
   uniformMarkerRadiusPx:lastLabelPositions[0]?.r??null,
   markerRadiusSpreadPx:lastLabelPositions.length?
     Math.max(...lastLabelPositions.map(p=>p.r))-
     Math.min(...lastLabelPositions.map(p=>p.r)):0,
   focusedMarkerRadiusPx:lastLabelPositions.find(p=>p.number===selected)?.r??null,
   severeOverlapPairs:lastLabelPositions.reduce((n,a,i)=>n+
    lastLabelPositions.slice(i+1).filter(b=>
     Math.hypot(a.x-b.x,a.y-b.y)<.55*(a.r+b.r)).length,0),
   touchingPairs:lastLabelPositions.reduce((n,a,i)=>n+
    lastLabelPositions.slice(i+1).filter(b=>
     Math.hypot(a.x-b.x,a.y-b.y)<a.r+b.r).length,0),
   commonLaneController:Boolean(window.RaceLaneAI?.plan&&window.RaceLaneAI?.launchStepSafe),
   inwardMoves:engine.state.totalInsideMoves,
   outwardMoves:engine.state.totalOutsidePasses,
   insideFour:engine.state.horses.filter(h=>h.lane<=3.45).length,
   turfVisualWidthPx:model.widthPx,physicalWidthM:model.widthMetres,
    selectedHorse:selected,selectedScreen:screen,
    selectedVisible:Boolean(screen&&screen.x>=16&&screen.x<=live.width-16&&
     screen.y>=16&&screen.y<=live.height-16),
    imageCalls:vectorReady?1:0,section:model.center(engine.state.leader).section,
    fixedSegments:model.sections.filter(s=>s.kind==='straight').map(s=>[s.from,s.to])};
 },advanceTo
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);
else setup();
})();
