// Assemble preview-only copies from staging branch. The normal docs/index.html and
// docs/this-week.html are never overwritten or committed to production by this script.
import fs from 'node:fs';
import path from 'node:path';
const root='docs/staging';fs.mkdirSync(root,{recursive:true});
const preview=(source,target,{stageShortcut=false}={})=>{
 let content=fs.readFileSync(source,'utf8');
 if(content.includes('<base'))throw Error('Unexpected existing HTML base: '+source);
 content=content.replace('<head>','<head><base href="../">');
 content=content.replaceAll('href="index.html"','href="staging/index.html"')
   .replaceAll('href="this-week.html"','href="staging/this-week.html"');
 content=content.replace(/<script src="assets\/visitor-counter\.js[^"]*" defer><\/script>/g,'');
 fs.writeFileSync(target,content);
 if(content.includes('special-2026-10-11-tokyo12.html'))throw Error('temporary Tokyo12 still linked: '+target);
 if(source==='docs/index.html'&&content.includes('購入操作は最大3行＋'))throw Error('production homepage should have no test purchase entrance');
 if(source==='docs/this-week.html'&&content.includes('試験中：買いやすい3操作'))throw Error('weekly production candidate includes test promo');
 if(stageShortcut){
   const smallLink='<p style="font-size:11px;text-align:center;margin:18px 0 0"><a href="staging/purchase-preview.html" style="color:#bac4d3">検証用：購入方法のステージング比較を見る →</a></p>';
   const end='</div></header>';
   if(!content.includes(end))throw Error('missing stage-only footer position');
   content=content.replace(end,smallLink+'\n'+end);
   fs.writeFileSync(target,content);
 }

};
preview('docs/index.html',root+'/index.html',{stageShortcut:true});
preview('docs/this-week.html',root+'/this-week.html');
let p=fs.readFileSync(root+'/purchase-preview.html','utf8');
p=p.replace(/<script src="assets\/visitor-counter\.js" defer><\/script>/g,'');
fs.writeFileSync(root+'/purchase-preview.html',p);
const sources=['2026-10-12-october-stakes','2026-10-12-swan-stakes'];
for(const race of sources){
 const file=path.join(root,'data/three-plus-ana',race+'.json');
 const d=JSON.parse(fs.readFileSync(file,'utf8'));
 if(d.regular_commands.length>3||d.medium_command?.row!==4||d.large_command?.row!==5||
   !d.summary||d.summary.stake_yen>6000||d.formal_final_bets_unchanged!==true)
   throw Error('staging purchase safety invariant failed: '+race);
 for(const c of [d.medium_command,d.large_command]){
   if(c.method==='pass'&&c.stake_yen!==0)throw Error('ineligible special candidate charged budget');
   if(c.method!=='pass'&&c.points<1)throw Error('special candidate missing priced points');
 }
 console.log('STAGING_CHECK',race,'regular_ops',d.regular_commands.length,
   'medium',d.medium_command.method,'large',d.large_command.method,
   'total',d.summary.stake_yen);
}
console.log('JRA_STAGING_PAGESET_PREPARED',sources.length);

