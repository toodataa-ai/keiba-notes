(function(){'use strict';
const model=window.RaceTokyo2000,race=model.race();
document.getElementById('checkpoints').textContent=model.checkpoints.map(d=>d>2000?'ゴール後':d.toLocaleString('ja-JP')+'m').join(' / ');
const keys={early:'先行力',cruise:'巡航速度',burst:'瞬発力',sustain:'持続力',stamina:'スタミナ',acceleration:'加速力'};
const colors=[['#fff','#111'],['#15191f','#fff'],['#d9142f','#fff'],['#164bb8','#fff'],['#ffde30','#111'],['#1d8c49','#fff'],['#f9811f','#111'],['#f4a1c5','#111']];
for(const horse of race.horses){
 const p=window.RaceSimAbility.profile(horse,race,0),card=document.createElement('article');card.className='horse';
 const h=document.createElement('h3'),b=document.createElement('span'),i=horse.number<=12?Math.floor((horse.number-1)/2):horse.number<=15?6:7;
 b.className='badge';b.textContent=horse.number;b.style.background=colors[i][0];b.style.color=colors[i][1];
 h.append(b,document.createTextNode(horse.name));const dl=document.createElement('dl');
 for(const [k,label] of Object.entries(keys)){const row=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=p.displaySix[k];row.append(dt,dd);dl.append(row);}
 card.append(h,dl);document.getElementById('abilities').append(card);
}
// Fail closed even if a user removes the disabled attribute in devtools.
document.getElementById('startBtn').addEventListener('click',()=>model.assertCanAnimate());
})();
