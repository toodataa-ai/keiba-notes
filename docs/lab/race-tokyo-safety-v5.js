/* Conservative LAB checks in race metres. No renderer, result target or approval. */
(function(g){'use strict';
function interval(a,b,limit){const v=b-a;if(Math.abs(v)<1e-14)return Math.abs(a)<limit?[0,1]:null;
 const x=(-limit-a)/v,y=(limit-a)/v,lo=Math.max(0,Math.min(x,y)),hi=Math.min(1,Math.max(x,y));return hi>lo?[lo,hi]:null;}
function overlap(a,b,c,d){const fore=interval(a.d-c.d,b.d-d.d,2.55-1e-6),side=interval((a.lane-c.lane)*1.65,(b.lane-d.lane)*1.65,.8-1e-6);
 return fore&&side&&Math.min(fore[1],side[1])>Math.max(fore[0],side[0]);}
const pose=sim=>sim.state.horses.map(h=>({number:h.number,d:h.displayD,lane:h.lane,finished:h.finished,finishTime:h.finishTime,name:h.name,runoffSpeed:h.runoffSpeed}));
async function run(session,seed,{yieldEvery=40}={}){
 const data={...g.RaceTokyo2000.race({motion:'bounded-lateral-v4'}),labTokyoSourceModel:'source-linked-v5'};
 const sim=g.RaceSimEngine.create(data,{seed,bias:'neutral',labTokyoSourceSession:session});
 let before=pose(sim),ticks=0,hits=0,bounds=0,backward=0,maxLateral=0,maxJump=0,vel=Array(18).fill(0);
 const frames=[];
 function capture(){frames.push({t:sim.state.t,horses:pose(sim),firstFinishTime:sim.state.firstFinishTime,
  splitTime:sim.state.splitTime,splitDistanceM:sim.state.splitDistanceM,allCrossedAt:sim.state.allCrossedAt,finished:sim.state.finished});}
 capture();
 while(!sim.state.finished&&ticks<5000){
  sim.step(.08);ticks++;const after=pose(sim);
  for(let i=0;i<18;i++){
   const a=before[i],b=after[i],v=(b.lane-a.lane)*1.65/.08;
   if(!a.finished){maxLateral=Math.max(maxLateral,Math.abs(v));maxJump=Math.max(maxJump,Math.abs(v-vel[i]));}
   if(!Number.isFinite(b.d)||b.d<0||b.d>2120||!Number.isFinite(b.lane)||b.lane<0||b.lane>16)bounds++;
   if(b.d<a.d-1e-9)backward++;vel[i]=v;
   for(let j=0;j<i;j++)if(overlap(a,b,before[j],after[j]))hits++;
  }
  before=after;capture();if(yieldEvery&&ticks%yieldEvery===0)await new Promise(r=>setTimeout(r,0));
 }
 const result=sim.standings().map(h=>({number:h.number,finishTime:h.finishTime,gap:h.finishTime-sim.state.firstFinishTime}));
 const summary={ticks,hits,bounds,backward,maxLateralMps:maxLateral,maxVelocityJumpMps:maxJump,emergencyStops:sim.labTokyoMotionStats.emergencyStops,
  all18Finished:sim.state.horses.every(h=>h.finished),all18RunoffComplete:sim.state.finished&&sim.state.horses.every(h=>h.displayD>=2032),seed,stepSeconds:.08};
 if(hits||bounds||backward||maxLateral>1.2+1e-8||maxJump>.064+1e-8||summary.emergencyStops||!summary.all18Finished||!summary.all18RunoffComplete)
  throw Error('TOKYO_SOURCE_MOTION_AUDIT_FAILED: '+JSON.stringify(summary));
 return{frames,result,summary};
}
g.RaceTokyoSafetyV5=Object.freeze({interval,overlap,run});
})(typeof window!=='undefined'?window:globalThis);
