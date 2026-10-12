/* Racing-lab scenario engine v0.5. Smooth gate acceleration and bounded 100m inward formation; NOT calibrated odds. */
(function(global){
'use strict';
const MARKS=['◎','○','▲','△','×'];
const GRADE={ 'A+':5,'A':4,'B+':3,'B':2,'B-':1,'C':0 };
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
function smoothstep(v){const x=clamp(v,0,1);return x*x*(3-2*x)}
function startSpeedFactor(t){return .12+.88*smoothstep(t/2.9)}
function lateralSpeedAt(d){const leadIn=smoothstep(d/16);
 const taper=1-smoothstep((d-85)/35);
 return .65+3.0*leadIn*taper;
}
function mulberry32(a){return function(){let t=a+=0x6D2B79F5;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return((t^(t>>>14))>>>0)/4294967296}}
function hash(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}
function validData(data){
 if(!data || !Number.isFinite(data.distance_m)||data.distance_m<600||data.distance_m>4000)throw Error('距離データが不正です');
 if(!Array.isArray(data.horses)||data.horses.length<2||data.horses.length>24)throw Error('出走頭数が不正です');
 const nos=new Set();
 for(const h of data.horses){
  if(!Number.isInteger(h.number)||h.number<1||h.number>30||nos.has(h.number))throw Error('馬番が重複または不正です');
  if(typeof h.name!=='string'||!h.name.trim())throw Error('馬名が不足しています');
  if(!MARKS.includes(h.mark))throw Error('予想印が確認できません');
  nos.add(h.number);
 }
}
function create(data,options={}){
 validData(data);
 const geo=global.RaceCourseGeometry;
 const profile=geo&&geo.get(data.course_id);
 if(!profile || profile.distance_m!==data.distance_m || profile.venue!==data.venue || profile.turn!==data.turn)
   throw Error('COURSE_PROFILE_MISMATCH: このコースの測定値・条件を確認できません');
 const seed=clamp(Math.floor(Number(options.seed)||1),1,999999);
 const pace=['S','M','H'].includes(options.pace)?options.pace:'M';
 const bias=['inner','neutral','outer'].includes(options.bias)?options.bias:'neutral';
 const rng=mulberry32(hash(data.id+'|'+seed));
 const laneAI=global.RaceLaneAI;
 if(!laneAI)throw Error('LANE_AI_MISSING');
 const laneCfg=laneAI.config(profile);
 const maxNumber=Math.max(...data.horses.map(h=>h.number));
 const mean=data.horses.reduce((s,h)=>s+(Number(h.win_pct)||0),0)/data.horses.length;
 const length=data.distance_m;
 const horses=data.horses.map((h,i)=>{
  const skill=clamp((Number(h.win_pct)||mean)-mean,-12,15);
  const paceGrade=GRADE[h.pace_grade]??2;
  const no=h.number;
  return { number:no,name:h.name,mark:h.mark,grade:h.grade,win_pct:h.win_pct,
   pace_grade:h.pace_grade,color:i,
   d:0,lane:(no-1)*laneCfg.maxLane/Math.max(1,maxNumber-1),
   desiredLane:(no-1)*laneCfg.maxLane/Math.max(1,maxNumber-1),
   laneVelocity:0,laneChanges:0,inwardMoves:0,outwardMoves:0,trafficHoldSeconds:0,
   stamina:0.9+rng()*.2,
   launchVariation:(rng()-.5)*1.6,
   surge:(rng()-.5)*.46,tempo:(rng()-.5)*.28,ability:skill*.035,
   paceFit:((paceGrade-2)*.085)+(pace==='H'?(rng()-.5)*.14:0),
   lastChange:-20,blocked:false,lastBlocked:false,finished:false,finishTime:null,
   trail:[],events:0,phase:rng()*6,lateKick:(rng()-.5)*.4+clamp(skill,-7,9)*.018,
   fatigue:0,distancePenaltyM:0,lastCourseSegment:'',gradeNow:0,turnNow:0 };
 });
 const events=[];
 const loggedLandmarks=new Set();
 const state={id:data.id,seed,pace,bias,distance:length,venue:data.venue,race:data.race,
    t:0,progress:0,leader:0,finished:false,leaderFinished:false,horses,events,leadingNo:horses[0].number,
    tick:0,firstFinishTime:null,courseId:profile.id,courseMetrics:null,
    laneModel:'v0.5-early-inside',laneCount:laneCfg.maxLane+1,
    totalLaneChanges:0,totalInsideMoves:0,totalOutsidePasses:0,trafficHolds:0};
 function log(kind,message,h){events.unshift({t:Math.round(state.t),kind,message,horse:h?.number??null});if(events.length>20)events.pop()}
 log('start','ゲートイン完了。'+profile.venue+' '+profile.course+'のコース形状を反映した仮説です');
 // A representative 17 m/s illustrates realistic race-duration scale
 // (~118s for 2000m, ~82s for 1400m), NOT official lap or winner timing.
 const base=17.0;
 function step(delta){
  if(state.finished)return state;
  const dt=clamp(Number(delta)||0,0,.16);
  if(!dt)return state;
  state.t+=dt;
  const fraction=clamp(state.leader/length,0,1);
  const paceEffect=pace==='H'? (fraction<.48?1.22:-.92):pace==='S'?(fraction<.55?-.82:1.06):0;
  const sorted=horses.slice().sort((a,b)=>b.d-a.d);
  for(const h of sorted){
   if(h.finished)continue;
   // Inside rail is preferred on every course, but NEVER at the expense
   // of cutting across occupied racing space. A blocked horse can choose
   // an outside passing route; faster finishers find inside gaps gradually.
   const m=geo.metrics(profile,h.d,h.lane);
   h.gradeNow=m.grade;h.turnNow=m.bend;h.lastCourseSegment=m.segment;
   const choice=laneAI.plan(h,horses,laneCfg,m,bias,state.t);
   if(choice){
     h.desiredLane=choice.lane;h.lastChange=state.t;
     h.laneChanges++;state.totalLaneChanges++;
     if(choice.mode==='inward'){h.inwardMoves++;state.totalInsideMoves++}
     else {h.outwardMoves++;state.totalOutsidePasses++}
     if(h.events<5){
        log('lane',h.number+'番 '+h.name+(choice.mode==='inward'?'が内の空いた進路へ':'が外の進路で前をかわす'),h);
        h.events++;
     }
   }
   // A planned crossing must remain safe throughout, including after other
   // horses advance. Abort rather than cutting across a horse next to it.
   if(Math.abs(h.desiredLane-h.lane)>.05 &&
      !laneAI.laneSafe(h,horses,h.desiredLane,laneCfg)){
       h.desiredLane=h.lane;
   }
   const move=h.desiredLane-h.lane;
   // Allow an early, progressively accelerating lane convergence (gate
   // release -> ~100m). The move never jumps: it is limited per tick and
   // every proposed crossing must pass the safety corridor checks above.
   const lateralSpeed=lateralSpeedAt(h.d);
   const laneAdvance=clamp(move,-dt*lateralSpeed,dt*lateralSpeed);
   h.laneVelocity=laneAdvance/(dt||1);
   h.lane=clamp(h.lane+laneAdvance,0,laneCfg.maxLane);
   const groundBias=(bias==='inner'?(laneCfg.maxLane/2-h.lane):bias==='outer'?(h.lane-laneCfg.maxLane/2):0)*.026;
   // Separate geometry losses: turns cost extra metres for outer lanes, uphill
   // reduces instantaneous speed and drains a little energy, downhill can restore pace.
   // Coefficients are explicitly provisional; curvature/altitude breakpoints are estimates.
   const bendPenalty=m.bend*(.10+Math.max(0,h.lane-1)*.025);
   const hillEffect=m.grade>0? -26*m.grade:0;
   const downhillBoost=m.grade<0? Math.min(.25,Math.abs(m.grade)*12):0;
   h.fatigue+=Math.max(0,m.grade)*dt*6;
   h.fatigue=clamp(h.fatigue,0,.22);
   const staminaLoss=pace==='H'? Math.pow(fraction,1.9)*h.stamina*.28:Math.pow(fraction,2)*h.stamina*.16;
   const remaining=length-h.d;
   const finalStretch=m.isFinalStraight?clamp(1-remaining/profile.straight_m,0,1):0;
   const finishing=finalStretch*h.lateKick;
   let speed=base+paceEffect+h.ability+h.surge+h.tempo*.35+h.paceFit+groundBias-bendPenalty-staminaLoss+finishing+hillEffect+downhillBoost-h.fatigue;
   // Standing starts must build speed, not jump from 0 to ~17m/s.
   // Rider/runner launch variations allow the 18-horse field to stagger
   // naturally before safely merging towards the inner racing line.
   const gateFactor=startSpeedFactor(state.t);
   speed=(speed+(h.d<100?h.launchVariation:0))*gateFactor;
   if(h.blocked){
     const front=laneAI.nearestAhead(h,horses,h.lane);
     const gap=front?Math.max(0,front.d-h.d):7.2;
     speed-=clamp(1.2-gap*.065,.30,1.2);
   }
   speed=Math.max(base*.84*startSpeedFactor(state.t),speed);
   const before=h.d;
   const physical=speed*dt;
   const proposed=physical/m.pathStretch;
   const safe=laneAI.throttle(h,horses,proposed,dt,laneCfg);
   if(safe.held){
     h.blocked=true;
     h.trafficHoldSeconds+=dt;state.trafficHolds++;
     if(!h.lastBlocked&&h.events<6&&fraction>.04){
       log('traffic',h.number+'番 '+h.name+'は前が詰まり、進路を探す',h);
       h.events++;
     }
   }else if(!choice){h.blocked=false}
   h.distancePenaltyM+=safe.distance*(m.pathStretch-1);
   h.d+=safe.distance;
   if(h.d>=length){
     h.finishTime=state.t-dt+dt*clamp((length-before)/(h.d-before),0,1);
     h.d=length;
     h.finished=true;
     log('finish',h.number+'番 '+h.name+'がゴール',h);
     if(state.firstFinishTime===null)state.firstFinishTime=h.finishTime;
   }
   // Path and separation events are emitted above; do not duplicate every tick.
   h.lastBlocked=h.blocked;
   h.trail.push({d:h.d,lane:h.lane});
   if(h.trail.length>100)h.trail.shift();
  }
  const leaders=horses.slice().sort((a,b)=>b.d-a.d||a.finishTime-b.finishTime||a.number-b.number);
  const previousLead=state.leader;
  state.leader=leaders[0].d;
  state.courseMetrics=geo.metrics(profile,state.leader,leaders[0].lane);
  for(const marker of profile.landmarks){
    if(marker.d<=0 || marker.d>=length || loggedLandmarks.has(marker.d))continue;
    if(previousLead<marker.d && state.leader>=marker.d){
      loggedLandmarks.add(marker.d);
      const label=marker.label;
      const m=geo.metrics(profile,marker.d,leaders[0].lane);
      const note= m.grade>.001?'（上り坂でスタミナ消耗）':m.grade<-.001?'（下りで加速しやすい）':
                  m.kind==='turn'?'（外側の距離ロスに注意）':'';
      log('course',label+note+'／'+profile.venue+'芝コース');
    }
  }
  state.leadingNo=leaders[0].number;
  state.progress=clamp(state.leader/length,0,1);
  state.tick++;
  if(state.tick%110===0&&!state.firstFinishTime)log('pace',Math.round(state.progress*100)+'%地点。先頭は'+state.leadingNo+'番');
  if(horses.every(h=>h.finished) || (state.firstFinishTime!==null&&state.t>state.firstFinishTime+15)){
    state.finished=true;
    horses.forEach(h=>{if(!h.finished){h.finished=true;h.finishTime=state.t+(length-h.d)/base}});
    log('summary','シミュレーション終了。着順は予測の保証ではありません');
  }
  return state;
 }
 function standings(){return horses.slice().sort((a,b)=>Number(b.finished)-Number(a.finished)||
     (a.finished&&b.finished?a.finishTime-b.finishTime:b.d-a.d)||a.number-b.number)}
 return {state,step,standings,rand:rng,course:profile,laneConfig:laneCfg};
}
global.RaceSimEngine=Object.freeze({create,validData,hash,MARKS,startSpeedFactor,lateralSpeedAt});
})(typeof window!=='undefined'?window:globalThis);
