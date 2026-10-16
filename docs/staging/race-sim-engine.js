/* Stage engine v0.22: six pre-race attributes, live fatigue and stage-only race dynamics. */
(function(global){
'use strict';
const MARKS=['◎','○','▲','△','×'];
const GRADE={ 'A+':5,'A':4,'B+':3,'B':2,'B-':1,'C':0 };
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
function smoothstep(v){const x=clamp(v,0,1);return x*x*(3-2*x)}
// Stage-only physical speed calibration, not a replay of race results.
// Tokyo turf 2000m starts from a pocket with a measured slow first furlong;
// the earlier common 17m/s baseline plus multiple ability increments made
// even a low-contest 1000m split implausibly fast. Reduce opening cruise and
// let a gradual late-race drive recover speed. No target result or fixed time.
// Kyoto and all other course physics retain their original speed baseline.
function sectionalSpeedAdjustment(profile,d){
 if(profile.id!=='tokyo_turf_2000')return 0;
 const f=clamp(d/profile.distance_m,0,1);
 return -1.20+1.50*smoothstep((f-.42)/.17);
}
// Display classification based on a simulated LINE-CROSSING split, not on
// the number of rivals attempting the lead. Provisional course-specific
// thresholds (not official JRA pace determination). Contest pressure is a
// separate physiological model and must not overwrite these labels.
function classifySplitPace(profile,seconds){
 if(!Number.isFinite(seconds)||seconds<=0)return null;
 const limits=profile.id==='tokyo_turf_2000'?[57.2,58.8]:
  profile.id==='kyoto_turf_outer_1400'?[34.2,35.3]:null;
 return limits?(seconds<limits[0]?'H':seconds<limits[1]?'M':'S'):null;
}
function startSpeedFactor(t){return .12+.88*smoothstep(t/2.9)}
function lateralSpeedAt(d){const leadIn=smoothstep(d/16);
 const taper=1-smoothstep((d-85)/35);
 return .65+3.0*leadIn*taper;
}
// Stamina, prior running style and scenario pace yield a gradual—not
// scripted—late-race speed difference. Every horse is determined at gate load.
// Gradual finish drives vary by style, but never dictate finishing rank.
// Provisional stage-only pace balance: leaders conserve energy under modest
// pressure, while closers can respond late. Race-day fluctuation is seeded.
const LATE_STYLE_DRIVE=Object.freeze({nige:.36,senko:.35,sashi:.17,oikomi:.44,unknown:.32});
/* Pace is created by the runners, rather than inferred from their finishing
   ranks or from popularity. Manual S/M/H is a +/- scenario modifier, not a
   frozen outcome. Near-front escape and stalker candidates raise pressure.
   These thresholds are transparent hypotheses, not learned coefficients. */
function contestedPace(horses,leader,mode){
 const active=horses.filter(h=>!h.finished&&leader-h.d<15);
 const escape=active.filter(h=>h.style==='nige'&&leader-h.d<=14);
 const stalk=active.filter(h=>h.style==='senko'&&leader-h.d<=9);
 const escapeCount=escape.length;
 const totalFighters=escapeCount+stalk.length;
 const offset=mode==='S'?-.19:mode==='H'?.23:0;
 const pressure=clamp(.13+Math.max(0,escapeCount-1)*.31+stalk.length*.105+offset,.025,1);
 return {pressure,escapeCount,stalkCount:stalk.length,totalFighters};
}
function band(pressure){return pressure>=.67?'H':pressure>=.35?'M':'S'}
// Shared downhill-to-straight closing opportunity, computed from registered
// geometry (not a special case for Kyoto). A horse must have pre-race evidence
// of late acceleration/sustained speed AND remain in a rear-running style.
// This is a *small* physically integrated speed term, not a changed finish
// rank or a target race result. The fixed coefficient is provisional pending
// multi-race historical out-of-sample validation.
const closingOpportunityCache=new WeakMap();
function closingTurnOpportunity(profile){
 if(closingOpportunityCache.has(profile))return closingOpportunityCache.get(profile);
 const geometry=global.RaceCourseGeometry;
 const straightEntry=profile.distance_m-profile.straight_m;
 const high=geometry.height(profile,Math.max(0,straightEntry-380));
 const exit=geometry.height(profile,straightEntry);
 const opportunity=clamp((high-exit)/4,0,1);
 closingOpportunityCache.set(profile,opportunity);
 return opportunity;
}
function closingTurnResponse(h,remaining,profile,pace){
 const downhill=closingTurnOpportunity(profile);
 if(downhill<=0)return 0;
 const role=h.style==='sashi'?.82:h.style==='oikomi'?1:0;
 if(!role)return 0;
 const traits=clamp((h.six.burst+h.six.sustain+h.six.acceleration-140)/35,.25,1);
 const strain=pace==='H'?1:pace==='M'?.72:.42;
 const ramp=smoothstep((profile.straight_m+100-remaining)/(profile.straight_m*.78+100));
 return .32*downhill*role*traits*strain*ramp;
}
function finishDrive(h,remaining,profile,pace){
 const stretch=profile.straight_m;
 // Begin wind-up on the final bend, reach full drive in the home straight.
 const ramp=smoothstep((stretch+130-remaining)/(stretch*.85+130));
 const reserve=(h.stamina-1)*.90+h.lateKick*1.25;
 const six=h.six;
 const burstPhase=smoothstep((stretch*.85-remaining)/(stretch*.68));
 const sustainPhase=smoothstep((stretch+115-remaining)/(stretch*.9+115));
 const accelerationPhase=smoothstep((stretch+65-remaining)/(stretch*.50+65));
 const highPaceTax=pace==='H'?(h.style==='nige'?.13:h.style==='senko'?.05:0):0;
 return ramp*(LATE_STYLE_DRIVE[h.style]??.27)+ramp*reserve-ramp*highPaceTax+
   (six.burst-50)*.008*burstPhase+
   (six.sustain-50)*.006*sustainPhase+
   (six.acceleration-50)*.004*accelerationPhase+
   closingTurnResponse(h,remaining,profile,pace);
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
 const pace='auto'; // The field itself always determines the pace.
 const bias=['inner','neutral','outer'].includes(options.bias)?options.bias:'neutral';
 const rng=mulberry32(hash(data.id+'|'+seed));
 const laneAI=global.RaceLaneAI;
 if(!laneAI)throw Error('LANE_AI_MISSING');
 const tactic=global.RaceRunnerStyle;
 if(!tactic)throw Error('RUNNER_STYLE_ENGINE_MISSING');
 const abilityModel=global.RaceSimAbility;
 if(!abilityModel)throw Error('SIM_ABILITY_MODEL_MISSING');
 const laneCfg=laneAI.config(profile);
 const maxNumber=Math.max(...data.horses.map(h=>h.number));
 const mean=data.horses.reduce((s,h)=>s+(Number(h.win_pct)||0),0)/data.horses.length;
 const length=data.distance_m;
 // Four distinct lines with fore-aft depth and stable gate-order grouping.
 // Preserve lateral order on the gate-to-pack merge: alternating targets
 // forced horses to cut across the full field and stall in outer lanes.
 const styleSlots=new Map();
 data.horses.slice().sort((a,b)=>a.number-b.number).forEach((h,i)=>{
   styleSlots.set(h.number,Math.min(3,Math.floor(i*4/data.horses.length))*1.10);
 });
 const horses=data.horses.map((h,i)=>{
  const skill=clamp((Number(h.win_pct)||mean)-mean,-12,15);
  const traits=abilityModel.profile(h,data,mean);
  const no=h.number;
  return { number:no,name:h.name,mark:h.mark,grade:h.grade,win_pct:h.win_pct,
   pace_grade:h.pace_grade,color:i,style:h.style||'unknown',styleMeta:h.styleMeta||null,
   abilityProfile:traits,
   d:0,lane:(no-1)*laneCfg.maxLane/Math.max(1,maxNumber-1),
   initialLane:(no-1)*laneCfg.maxLane/Math.max(1,maxNumber-1),
   launchTargetLane:styleSlots.get(no)??2,
   preferredLane:styleSlots.get(no)??2,
   desiredLane:(no-1)*laneCfg.maxLane/Math.max(1,maxNumber-1),
   launchMergeMoves:0,
   laneVelocity:0,laneChanges:0,inwardMoves:0,outwardMoves:0,trafficHoldSeconds:0,
   stamina:clamp(.90+traits.six.stamina*.002,.90,1.10),six:traits.six,
   launchVariation:traits.earlySpeed+(traits.six.early-50)*.007+(rng()-.5)*.30,
   surge:(rng()-.5)*.70,tempo:(rng()-.5)*.12,
   ability:traits.baseSpeed+traits.courseSpeed+(traits.six.cruise-50)*.004,paceFit:traits.paceSpeed,
   lastChange:-20,blocked:false,lastBlocked:false,finished:false,finishTime:null,
   displayD:0,runoffSpeed:0,
   trail:[],events:0,phase:rng()*6,lateKick:traits.kick+(rng()-.5)*.16,
   fatigue:0,effortDebt:0,distancePenaltyM:0,lastCourseSegment:'',gradeNow:0,turnNow:0 };
 });
 const RUNOFF_M=32;
 // All horses ease down after the wire on the SAME monotone runoff curve.
 // Their screen order then remains tied to the real fractional crossing
 // times instead of changing due to arbitrary post-race acceleration, and
 // the early finishers keep their elapsed head start at the final frame.
 function postFinishTravel(seconds){
  const t=Math.max(0,Number(seconds)||0);
  return (14.2/.12)*(1-Math.exp(-.12*t));
 }
 const events=[];
 const loggedLandmarks=new Set();
 // Record 1000m for races at least 1600m; opening 3F (600m) for shorter.
 const splitDistanceM=length>=1600?1000:600;
 const state={id:data.id,seed,pace,bias,distance:length,venue:data.venue,race:data.race,
    t:0,progress:0,leader:0,finished:false,leaderFinished:false,horses,events,leadingNo:horses[0].number,
    tick:0,firstFinishTime:null,splitTime:null,splitPaceBand:null,splitDistanceM,courseId:profile.id,courseMetrics:null,
    laneModel:'v0.9-four-wide-fore-aft-pack',laneCount:laneCfg.maxLane+1,
    totalLaneChanges:0,totalInsideMoves:0,totalOutsidePasses:0,trafficHolds:0,
    finalStraightPasses:0,lastOvertakeLog:-100,lastVisualPass:null,straightEntryOrder:null,
    runoffMeters:RUNOFF_M,allCrossedAt:null,displayFinished:false,goalCamera:false,
    pacePressure:.13,pacePeak:.13,paceBand:'S',peakPaceBand:'S',
    paceContestants:0,paceEscapers:0,paceStalkers:0,paceHistory:[],lastPaceLog:'S'};
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
  for(const h of horses){
   if(!h.finished)continue;
   // Continuous extrapolation from the INTERPOLATED wire-crossing instant:
   // same after-race easing for all runners, no 32m clamp, and no phantom
   // overtake after the official virtual finish order has been established.
   h.displayD=length+postFinishTravel(state.t-h.finishTime);
  }
  const fraction=clamp(state.leader/length,0,1);
  // Take one snapshot BEFORE any horse is advanced. Without this,
  // processing order changes the tactical contest and breaks determinism.
  const liveLeader=Math.max(...horses.map(h=>h.d));
  const contest=contestedPace(horses,liveLeader,pace);
  const paceAlpha=clamp(dt*1.8,0,1);
  state.pacePressure+=(contest.pressure-state.pacePressure)*paceAlpha;
  state.paceBand=band(state.pacePressure);
  state.paceContestants=contest.totalFighters;
  state.paceEscapers=contest.escapeCount;
  state.paceStalkers=contest.stalkCount;
  if(fraction<=.60){
    state.pacePeak=Math.max(state.pacePeak,state.pacePressure);
    state.peakPaceBand=band(state.pacePeak);
  }
  if(state.paceBand!==state.lastPaceLog&&state.leader>=80&&fraction<.65){
    log('pace',state.paceBand+'ペースへ変化：先頭争い'+contest.totalFighters+'頭・競り合い負荷'+Math.round(state.pacePressure*100)+'%');
    state.lastPaceLog=state.paceBand;
  }
  // Manual presets shift overall scenario slightly, while the field's
  // actual fight still determines the local acceleration and energy cost.
  const paceEffect=0; // No manual pace multiplier.
  const sorted=horses.slice().sort((a,b)=>b.d-a.d);
  const prior=horses.map(h=>({number:h.number,d:h.d,finished:h.finished}));
  for(const h of sorted){
   if(h.finished)continue;
   // Inside rail is preferred on every course, but NEVER at the expense
   // of cutting across occupied racing space. A blocked horse can choose
   // an outside passing route; faster finishers find inside gaps gradually.
   const m=geo.metrics(profile,h.d,h.lane);
   h.gradeNow=m.grade;h.turnNow=m.bend;h.lastCourseSegment=m.segment;
   const forming=state.leader<220;
   const choice=forming?null:laneAI.plan(h,horses,laneCfg,m,bias,state.t);
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
   let movement;
   if(forming){
     // The pack gently contracts during the opening 100m. Each style
     // has distinct inner-side "slots" so runners are not all assigned
     // to the identical rail coordinate. No lateral teleporting.
     const ratio=smoothstep(state.leader/90);
     const desired=h.initialLane+(h.launchTargetLane-h.initialLane)*ratio;
     const speed=lateralSpeedAt(state.leader);
     const amount=clamp(desired-h.lane,-dt*speed,dt*speed);
     const proposed=clamp(h.lane+amount,0,laneCfg.maxLane);
     const safe=laneAI.launchStepSafe(h,horses,proposed,laneCfg);
     movement=safe?proposed-h.lane:0;
     h.desiredLane=h.lane+movement;
     if(movement<-.00001 && h.launchMergeMoves===0){
       h.launchMergeMoves++;h.laneChanges++;h.inwardMoves++;
       state.totalLaneChanges++;state.totalInsideMoves++;
     }
   }else{
     // Apply the usual safe lane-change logic once gate formation ends.
     if(Math.abs(h.desiredLane-h.lane)>.05 &&
        !laneAI.laneSafe(h,horses,h.desiredLane,laneCfg)){
       h.desiredLane=h.lane;
     }
     const move=h.desiredLane-h.lane;
     // Tight turns discourage sudden sideways movement. Recheck occupancy
     // each frame because the corridor may have changed after route planning.
     const limit=dt*lateralSpeedAt(h.d)*(m.bend>.6?.86:1);
     const tentative=clamp(move,-limit,limit);
     const nextLane=clamp(h.lane+tentative,0,laneCfg.maxLane);
     const clear=laneAI.launchStepSafe(h,horses,nextLane,laneCfg);
     movement=clear?tentative:0;
     if(!clear)h.desiredLane=h.lane;
   }
   h.laneVelocity=movement/(dt||1);
   h.lane=clamp(h.lane+movement,0,laneCfg.maxLane);
   const groundBias=(bias==='inner'?(laneCfg.maxLane/2-h.lane):bias==='outer'?(h.lane-laneCfg.maxLane/2):0)*.026;
   // Separate geometry losses: turns cost extra metres for outer lanes, uphill
   // reduces instantaneous speed and drains a little energy, downhill can restore pace.
   // Coefficients are explicitly provisional; curvature/altitude breakpoints are estimates.
   const bendPenalty=m.bend*.10; // outer distance is already charged by pathStretch
   const hillEffect=m.grade>0? -26*m.grade:0;
   const downhillBoost=m.grade<0? Math.min(.25,Math.abs(m.grade)*12):0;
   h.fatigue+=Math.max(0,m.grade)*dt*6;
   h.fatigue=clamp(h.fatigue,0,.22);
   const leaderGap=Math.max(0,liveLeader-h.d);
   const onFront=(h.style==='nige'&&leaderGap<=16) ||
                 (h.style==='senko'&&leaderGap<=12) || (state.leader>60&&leaderGap<=3);
   const earlyDemand=(1-smoothstep((fraction-.38)/.25));
   // Sprinting to secure the lead has a real cost. It is charged ONLY to
   // horses actually contesting the front and persists into the straight.
   // A lone, uncontested leader can therefore conserve much more energy.
   if(onFront){
     const effortStyle=h.style==='nige'?1:h.style==='senko'?.58:.78;
     h.effortDebt=clamp(h.effortDebt+dt*earlyDemand*
       (state.pacePressure**1.30)*.039*effortStyle,0,2.8);
   }
   const lateExhaustion=1.0*h.effortDebt*smoothstep((fraction-.44)/.43)/h.stamina;
   const sprintDemand=onFront?state.pacePressure*earlyDemand*
       (h.style==='nige'?.78:.40):0;
   const staminaLoss=Math.pow(fraction,1.9)/h.stamina*
      (.13+.14*state.pacePeak);
   const remaining=length-h.d;
   // AUTO is a mode, not a pace grade. The observed high-pace pressure must
   // contribute to late fatigue even with the default automatic scenario.
   const finishing=finishDrive(h,remaining,profile,state.peakPaceBand);
   // Small slipstream benefit when tracking another runner (no artificial pass).
   const hasCover=!onFront&&horses.some(o=>o!==h&&!o.finished&&
     o.d-h.d>=3&&o.d-h.d<=11&&Math.abs(o.lane-h.lane)<1.35);
   const shelter=hasCover?.045:0;
   // Early cruising compresses speed variance; the late sprint reveals ability.
   const abilityRelease=.70+.30*smoothstep((fraction-.56)/.27);
   let speed=base+sectionalSpeedAdjustment(profile,h.d)+paceEffect+sprintDemand+shelter+h.ability*abilityRelease+h.surge+h.tempo*.35+h.paceFit+
     groundBias-bendPenalty-staminaLoss+finishing+hillEffect+downhillBoost-h.fatigue-lateExhaustion;
   // A runner self-selects a fore-aft position from its PREVIOUS race's
   // corner passage. No STEP1 marks, popularity, odds or target result.
   const leaderD=Math.max(...horses.map(o=>o.d));
   speed+=tactic.positionAdjustment(h.style,Math.max(0,leaderD-h.d),h.d,state.t,h.styleMeta);
   // Jockey keeps contact with a departing pack before the final sprint.
   // Chase costs effort, does not teleport or force a particular finish.
   const intendedGap=({nige:0,senko:5,sashi:12,oikomi:20,unknown:12})[h.style]??12;
   // Continue tactical pursuit farther through the home straight rather than
   // switching it off around 1750m and letting an implausible 30m+ leader
   // gap open on routine competitive stakes. This changes real travel speed,
   // not recorded finish times or ranks after the fact.
   const packWindow=smoothstep((fraction-.05)/.10)*(1-smoothstep((fraction-.90)/.12));
   const catchUp=clamp((leaderD-h.d-intendedGap)*.042,0,1.20)*packWindow;
   speed+=catchUp;
   h.effortDebt=clamp(h.effortDebt+dt*catchUp*.006,0,2.8);
   // Standing starts must build speed, not jump from 0 to ~17m/s.
   // Rider/runner launch variations allow the 18-horse field to stagger
   // naturally before safely merging towards the inner racing line.
   const gateFactor=startSpeedFactor(state.t);
   speed=(speed+(h.d<100?h.launchVariation:0))*gateFactor;
   if(h.blocked){
     const front=laneAI.nearestAhead(h,horses,h.lane);
     // No artificial deceleration merely because another horse is
     // 8–12m ahead. Brake only if materially boxed in.
     if(front){
       const gap=Math.max(0,front.d-h.d);
       if(gap<5.0)speed-=clamp((5-gap)*.18,.12,.75);
     }
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
   h.displayD=h.d;
   if(h.d>=length){
     h.finishTime=state.t-dt+dt*clamp((length-before)/(h.d-before),0,1);
     h.runoffSpeed=Math.max(11,speed/m.pathStretch);
     h.d=length;
     h.displayD=length+postFinishTravel(state.t-h.finishTime);
     h.finished=true;
     log('finish',h.number+'番 '+h.name+'がゴール板を通過',h);
     if(state.firstFinishTime===null||h.finishTime<state.firstFinishTime)state.firstFinishTime=h.finishTime;
   }
   // Path and separation events are emitted above; do not duplicate every tick.
   h.lastBlocked=h.blocked;
   h.trail.push({d:h.d,lane:h.lane});
   if(h.trail.length>100)h.trail.shift();
  }
  // Snapshot modeled ranks on entering the straight; never assign a target result.
  if(!state.straightEntryOrder && state.leader>=length-profile.straight_m){
    state.straightEntryOrder=horses.slice().sort((a,b)=>b.d-a.d||a.number-b.number).map(h=>h.number);
  }
  // Count actual longitudinal position crossings, not "cinematic" fake
  // passes. Do not count finish-line ties or movement between lanes alone.
  if(state.leader>=length-profile.straight_m){
    const old=new Map(prior.map(h=>[h.number,h]));
    let firstPass=null;
    for(let i=0;i<horses.length;i++)for(let j=i+1;j<horses.length;j++){
      const x=horses[i],y=horses[j],px=old.get(x.number),py=old.get(y.number);
      if(x.finished||y.finished||px.finished||py.finished)continue;
      if((px.d<py.d && x.d>y.d)||(py.d<px.d&&y.d>x.d)){
        state.finalStraightPasses++;
        if(!firstPass)firstPass=x.d>y.d?[x,y]:[y,x];
      }
    }
    if(firstPass && state.firstFinishTime===null && state.t-state.lastOvertakeLog>1.5){
      const [attacker,victim]=firstPass;
      // Display telemetry from a REAL longitudinal crossing only.
      // It never shifts any runner, modifies speed, rank or settlement.
      state.lastVisualPass={attackerNo:attacker.number,victimNo:victim.number,
        attackerName:attacker.name,t:state.t};
      log('pass',attacker.number+'番 '+attacker.name+'が直線で'+victim.number+'番をかわす',attacker);
      state.lastOvertakeLog=state.t;
    }
  }
  const leaders=horses.slice().sort((a,b)=>b.d-a.d||a.finishTime-b.finishTime||a.number-b.number);
  const previousLead=state.leader;
  state.leader=leaders[0].d;
  if(state.splitTime===null&&previousLead<splitDistanceM&&state.leader>=splitDistanceM){
    const fraction=clamp((splitDistanceM-previousLead)/(state.leader-previousLead||1),0,1);
    state.splitTime=state.t-dt+dt*fraction;
    state.splitPaceBand=classifySplitPace(profile,state.splitTime);
    log('split','前半'+splitDistanceM+'m通過');
  }
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
  state.goalCamera=state.leader>=length-80;
  state.tick++;
  if(state.tick%150===0){
    state.paceHistory.push({d:Math.round(state.leader),pressure:Number(state.pacePressure.toFixed(3)),
      grade:state.paceBand,contenders:state.paceContestants});
    if(state.paceHistory.length>60)state.paceHistory.shift();
  }
  if(state.tick%110===0&&!state.firstFinishTime)log('pace',Math.round(state.progress*100)+'%地点。先頭は'+state.leadingNo+'番');
  if(state.allCrossedAt===null&&horses.every(h=>h.finished)){
    state.allCrossedAt=state.t;log('finish','全馬がゴール板を通過・余走中');
  }
  if(horses.every(h=>h.finished&&h.displayD>=length+RUNOFF_M-1e-7)){
    state.finished=true;state.displayFinished=true;
    log('summary','全馬がゴールを駆け抜けました（仮想シミュレーション終了）');
  }
  return state;
 }
 function standings(){return horses.slice().sort((a,b)=>Number(b.finished)-Number(a.finished)||
     (a.finished&&b.finished?a.finishTime-b.finishTime:b.d-a.d)||a.number-b.number)}
 return {state,step,standings,rand:rng,course:profile,laneConfig:laneCfg};
}
global.RaceSimEngine=Object.freeze({create,validData,hash,MARKS,startSpeedFactor,lateralSpeedAt,finishDrive,closingTurnOpportunity,closingTurnResponse,contestedPace,band,sectionalSpeedAdjustment,classifySplitPace});
})(typeof window!=='undefined'?window:globalThis);
