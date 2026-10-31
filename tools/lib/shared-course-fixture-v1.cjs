// Synthetic structural fixture only. No real additional course is admitted.
const fs=require('node:fs'),path=require('node:path');
const dir=path.resolve(__dirname,'../../docs/lab/shared-course');
const clone=x=>JSON.parse(JSON.stringify(x));
function fixture(loop=false){
 const spec=JSON.parse(fs.readFileSync(dir+'/kyoto-2000.spec.json','utf8'));
 const blueprint=JSON.parse(fs.readFileSync(dir+'/kyoto-inner-A.blueprint.json','utf8'));
 Object.assign(blueprint,{id:'structural_test',venue:'架空テスト',layout:'synthetic',turn:'左'});
 blueprint.source={...blueprint.source,url:'assets/test-only.svg',attribution:'synthetic test',reference:'https://example.invalid/structural-fixture',permission:'unknown'};
 const edge=(id,from,to,lengthM,a,b,kind='straight',surface='dirt')=>({id,from,to,lengthM,surface,kind,name:id,rails:[[0,...a],[lengthM,...b]],widthM:27,gradeProfile:[[0,0],[lengthM,0]],gradeAccuracy:'unknown',bend:kind==='turn'?.7:0});
 const a=[.1,.32,.1,.28],b=[.4,.32,.4,.28],c=[.7,.32,.7,.28],d=[.825,.32,.825,.28];
 const start=edge('pocket','start','merge',100,a,b,'chute','turf');
 const main=edge('main','merge','goal',loop?100:500,b,c);
 const runoff=edge('runoff','goal','end',125,c,d);
 const alternate=edge('alternative','start','merge',100,a,b,'straight','turf');
 blueprint.nodes=['start','merge','goal','end'];blueprint.edges=[start,main,runoff,alternate];
 let ids=['pocket','main'];
 if(loop){
  const circle=edge('lap','merge','merge',200,b,b,'turn','turf');circle.rails=[];
  for(let i=0;i<=32;i++){
   const angle=2*Math.PI*i/32;
   circle.rails.push([200*i/32,.4+.18*Math.sin(angle),.5-.18*Math.cos(angle),.4+.22*Math.sin(angle),.5-.22*Math.cos(angle)]);
  }
  circle.rails[0]=[0,...b];circle.rails[32]=[200,...b];blueprint.edges.push(circle);ids=['pocket','lap','lap','main'];
 }
 Object.assign(spec,{id:'structural_test',blueprintId:'structural_test',label:'架空の構造検査',adapter:'graph-v1',distanceM:600,edgeIds:ids,finalStraightM:loop?100:500,
  anchorsM:loop?[0,100,300,500,600]:[0,100,600],
  sections:loop?[{from:0,to:100,kind:'chute',name:'pocket'},{from:100,to:500,kind:'turn',name:'loop'},{from:500,to:600,kind:'straight',name:'home'}]:[{from:0,to:100,kind:'chute',name:'pocket'},{from:100,to:600,kind:'straight',name:'home'}]});
 Object.assign(spec.camera.lens,{referenceFromM:30,referenceToM:500,metrics:{thirdFourthTurn:[200,450],firstSecondTurn:[50,150],midStraight:[200,400],fullRace:[30,500]}});
 spec.mask.legacyCalibration.turnAnchorsM=[100,300,500];
 spec.status={numerical:false,replay:false,visualApproval:false,productionApproval:false};
 return {blueprint,spec};
}
module.exports={fixture,clone};
