/* Racing-lab scenario engine v0.1. Illustration ONLY: no predicted finish odds. */
(function(global){
'use strict';
const MARKS=['◎','○','▲','△','×'];
const GRADE={ 'A+':5,'A':4,'B+':3,'B':2,'B-':1,'C':0 };
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
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
 const seed=clamp(Math.floor(Number(options.seed)||1),1,999999);
 const pace=['S','M','H'].includes(options.pace)?options.pace:'M';
 const bias=['inner','neutral','outer'].includes(options.bias)?options.bias:'neutral';
 const rng=mulberry32(hash(data.id+'|'+seed));
 const mean=data.horses.reduce((s,h)=>s+(Number(h.win_pct)||0),0)/data.horses.length;
 const length=data.distance_m;
 const horses=data.horses.map((h,i)=>{
  const skill=clamp((Number(h.win_pct)||mean)-mean,-12,15);
  const paceGrade=GRADE[h.pace_grade]??2;
  const no=h.number;
  return { number:no,name:h.name,mark:h.mark,grade:h.grade,win_pct:h.win_pct,
   pace_grade:h.pace_grade,color:i,
   d:0,lane:(no-1)%8,desiredLane:(no-1)%8,stamina:0.9+rng()*.2,
   surge:(rng()-.5)*.46,tempo:(rng()-.5)*.28,ability:skill*.035,
   paceFit:((paceGrade-2)*.085)+(pace==='H'?(rng()-.5)*.14:0),
   lastChange:-20,blocked:false,lastBlocked:false,finished:false,finishTime:null,
   trail:[],events:0,phase:rng()*6,lateKick:(rng()-.5)*.4+clamp(skill,-7,9)*.018 };
 });
 const events=[];
 const state={id:data.id,seed,pace,bias,distance:length,venue:data.venue,race:data.race,
    t:0,progress:0,leader:0,finished:false,leaderFinished:false,horses,events,leadingNo:horses[0].number,
    tick:0,firstFinishTime:null};
 function log(kind,message,h){events.unshift({t:Math.round(state.t),kind,message,horse:h?.number??null});if(events.length>20)events.pop()}
 log('start','ゲートイン完了。展開は設定に応じた仮説です');
 const base=length/54;
 function step(delta){
  if(state.finished)return state;
  const dt=clamp(Number(delta)||0,0,.16);
  if(!dt)return state;
  state.t+=dt;
  const fraction=clamp(state.leader/length,0,1);
  const atTurn=(fraction>.18&&fraction<.43)||(fraction>.58&&fraction<.76);
  const paceEffect=pace==='H'? (fraction<.48?1.22:-.92):pace==='S'?(fraction<.55?-.82:1.06):0;
  const sorted=horses.slice().sort((a,b)=>b.d-a.d);
  for(const h of sorted){
   if(h.finished)continue;
   let nearby=horses.filter(x=>x!==h && !x.finished && x.d>=h.d-.35 && x.d<=h.d+7.2 && Math.abs(x.lane-h.lane)<.79);
   h.blocked=nearby.length>0 && fraction>.05 && fraction<.94;
   // Within the same race, check for a safe adjacent lane before overtaking.
   if(h.blocked && state.t-h.lastChange>2.0){
    const targets=[h.lane-1,h.lane+1].filter(l=>l>=0&&l<=7);
    targets.sort((a,b)=>{
      const aw=bias==='inner'?a:bias==='outer'?7-a:Math.abs(a-h.desiredLane);
      const bw=bias==='inner'?b:bias==='outer'?7-b:Math.abs(b-h.desiredLane);
      return aw-bw;
    });
    const free=targets.find(l=>horses.every(x=>x===h||x.finished||
       Math.abs(x.lane-l)>.85||Math.abs(x.d-h.d)>6));
    if(free!==undefined){
      h.desiredLane=free;h.lastChange=state.t;
      if(h.events<3&&fraction>.15){log('lane',h.number+'番 '+h.name+'が進路を変更',h);h.events++}
    }
   }
   if(!h.blocked && state.t-h.lastChange>3.1){
     const ideal=bias==='inner'?1.4:bias==='outer'?6.3:3.4;
     const target=clamp(Math.round(h.lane+Math.sign(ideal-h.lane)),0,7);
     if(horses.every(x=>x===h||x.finished||Math.abs(x.lane-target)>1.0||Math.abs(x.d-h.d)>5.5)){
       h.desiredLane=target;h.lastChange=state.t;
     }
   }
   const move=h.desiredLane-h.lane;
   h.lane+=clamp(move,-dt*.72,dt*.72);
   const groundBias=(bias==='inner'?(3.6-h.lane):bias==='outer'?(h.lane-3.6):0)*.045;
   const bendPenalty=atTurn?Math.max(0,h.lane-2)*.018:0;
   const staminaLoss=pace==='H'? Math.pow(fraction,1.9)*h.stamina*.28:Math.pow(fraction,2)*h.stamina*.16;
   const finishing=(fraction>.72)?h.lateKick*((fraction-.72)/.28):0;
   let speed=base+paceEffect+h.ability+h.surge+h.tempo*.35+h.paceFit+groundBias-bendPenalty-staminaLoss+finishing;
   if(h.blocked)speed-=clamp(1.2-(nearby[0]?.d-h.d||0)*.065,.30,1.2);
   speed=Math.max(base*.84,speed);
   const before=h.d;
   h.d+=speed*dt;
   if(h.d>=length){
     h.finishTime=state.t-dt+dt*clamp((length-before)/(h.d-before),0,1);
     h.d=length;
     h.finished=true;
     log('finish',h.number+'番 '+h.name+'がゴール',h);
     if(state.firstFinishTime===null)state.firstFinishTime=h.finishTime;
   }
   if(!h.lastBlocked&&h.blocked&&h.events<3&&fraction>.25){log('traffic',h.number+'番 '+h.name+'の前が詰まる',h);h.events++}
   h.lastBlocked=h.blocked;
   h.trail.push({d:h.d,lane:h.lane});
   if(h.trail.length>100)h.trail.shift();
  }
  const leaders=horses.slice().sort((a,b)=>b.d-a.d||a.finishTime-b.finishTime||a.number-b.number);
  state.leader=leaders[0].d;
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
 return {state,step,standings,rand:rng};
}
global.RaceSimEngine=Object.freeze({create,validData,hash,MARKS});
})(typeof window!=='undefined'?window:globalThis);
