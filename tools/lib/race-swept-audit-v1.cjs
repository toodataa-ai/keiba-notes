/* Diagnostic geometry only. Never corrects runner positions or finish times. */
'use strict';
// Open interval where |start + t * (end-start)| < clearance, t in [0,1].
function overlapInterval(start,end,clearance){
 if(![start,end,clearance].every(Number.isFinite)||clearance<=0)throw Error('AUDIT_INTERVAL_INVALID');
 const delta=end-start;
 if(Math.abs(delta)<1e-12)return Math.abs(start)<clearance?[0,1]:null;
 const a=(-clearance-start)/delta,b=(clearance-start)/delta;
 const low=Math.max(0,Math.min(a,b)),high=Math.min(1,Math.max(a,b));
 return high-low>1e-10?[low,high]:null;
}
function sweptRectangle(a0,a1,b0,b1,{length=2.55,width=.8,laneMetres=1.65,epsilon=1e-6,endFraction=1}={}){
 if(!(endFraction>0&&endFraction<=1))return null;
 const fore=overlapInterval(a0.d-b0.d,a1.d-b1.d,length-epsilon);
 if(!fore)return null;
 const side=overlapInterval((a0.lane-b0.lane)*laneMetres,(a1.lane-b1.lane)*laneMetres,width-epsilon);
 if(!side)return null;
 const from=Math.max(fore[0],side[0]),to=Math.min(fore[1],side[1],endFraction);
 return to-from>1e-10?{from,to}:null;
}
module.exports={overlapInterval,sweptRectangle};
