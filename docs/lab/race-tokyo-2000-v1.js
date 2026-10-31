/* Tokyo-only LAB preparation. No route is certified by this module. */
(function(g){'use strict';
const id='tokyo_turf_2000';
const checkpoints=Object.freeze([0,100,130,300,900,1145,1474.1,1600,1920,1950,1980,2000,2032]);
const status=Object.freeze({courseId:id,canAnimate:false,approval:'not_approved',
 reason:'実コースの進入角・距離境界は未確定（PPTX発走目印は一致）',source:'https://umapot.com/?p=13273',
 archive:'https://umapot.com/data/powerpoint/tokyo_couse/tokyo_couse.zip',
 terms:'https://umapot.com/?page_id=116'});
function assertCanAnimate(){throw Error('TOKYO_ORIGINAL_ROUTE_UNVERIFIED');}
function race(){return {...g.RaceLab18Fixture.entry(),id:'lab-tokyo-2000-synthetic-18-v1',
 venue:'東京',race:'東京芝2000m・架空18頭',turn:'左',course_id:id,
 labAbilityScale:'90-v1',labTokyoAbility90:true,
 horses:g.RaceLab18Fixture.horses({abilityScale:'90-v1'})};}
// Separate broadcast orientation: camera right-to-left need not equal map turn.
const camera=Object.freeze({cutRemainingM:80,spanM:100,screenTurn:'右',courseTurn:'左'});
function goalPosition(d,lane,width,height,maxLane=16){
 return g.RaceCleanGoalView.goalScreenPosition(d,lane,2000,width,height,maxLane,camera.screenTurn,1,camera.spanM);
}
function create(){assertCanAnimate(); /* No hidden query-string bypass or engine construction. */}
g.RaceTokyo2000=Object.freeze({id,status,checkpoints,camera,race,goalPosition,assertCanAnimate,create});
})(typeof window!=='undefined'?window:globalThis);
