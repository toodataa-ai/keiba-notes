// Frozen 2026-10-25 replay ONLY. Results and official snapshots are never written.
import fs from 'node:fs';
import crypto from 'node:crypto';
import {compareV316Shadow} from './jra-stake-optimizer-v316-shadow.mjs';
const entries=[
 {course:'新潟11R',race:'2026-10-25-lumiere-autumn-dash',
  source:'v3.13-run40141955617-attempt1.json',
  formal:'v3.15-run40142205087-attempt1-sealed.json'},
 {course:'京都11R',race:'2026-10-25-kikka-sho',
  source:'v3.13-run40141962432-attempt1.json',
  formal:'v3.15-run40142524663-attempt1-sealed.json'},
 {course:'東京11R',race:'2026-10-25-kannazuki-stakes',
  source:'v3.13-run40142225062-attempt1.json',
  formal:'v3.15-run40142746599-attempt1-sealed.json'}
];
const dir=process.argv[2]??'/tmp/jra-v316-shadow-results';
if(!dir.startsWith('/tmp/'))throw Error('report destination must be /tmp/ only');
fs.mkdirSync(dir,{recursive:true});
const out=[];
for(const entry of entries){
 const sourcePath='e2e_validation/predictions/'+entry.race+'/'+entry.source;
 const formalPath='e2e_validation/predictions/'+entry.race+'/'+entry.formal;
 const sourceBytes=fs.readFileSync(sourcePath);
 const formalBytes=fs.readFileSync(formalPath);
 const source=JSON.parse(sourceBytes),formal=JSON.parse(formalBytes);
 const sourceHash=crypto.createHash('sha256').update(sourceBytes).digest('hex');
 const formalHash=crypto.createHash('sha256').update(formalBytes).digest('hex');
 const result=compareV316Shadow({source,sourceBytes,formal});
 if(result.baseline?.stake_yen!==formal.total_stake_yen)
  throw Error('formal baseline mismatch '+entry.race);
 if(result.publication_allowed!==false||result.formal_unchanged!==true)
  throw Error('shadow output publication guard violated');
 const summary={
  course:entry.course,race:entry.race,model:'v3.13 SHA-pinned',
  formal_version:'v3.15',
  source_sha256:sourceHash,formal_sha256:formalHash,
  source_proof_commit:source.proof_commit,formal_proof_commit:formal.proof_commit,
  formal_stake_yen:result.baseline.stake_yen,
  shadow_stake_yen:result.candidate.stake_yen,
  formal_expected_profit_yen:result.baseline.scenarios.central.expected_net_profit_yen,
  shadow_expected_profit_yen:result.candidate.scenarios.central.expected_net_profit_yen,
  formal_low_expected_profit_yen:result.baseline.scenarios.low.expected_net_profit_yen,
  shadow_low_expected_profit_yen:result.candidate.scenarios.low.expected_net_profit_yen,
  formal_loss_probability:result.baseline.scenarios.central.loss_probability,
  shadow_loss_probability:result.candidate.scenarios.central.loss_probability,
  formal_low_loss_probability:result.baseline.scenarios.low.loss_probability,
  shadow_low_loss_probability:result.candidate.scenarios.low.loss_probability,
  hit_probability_unchanged:result.audit.unchanged_hit_probability,
  formal_ticket_count:formal.formal_bets.length,
  shadow_ticket_count:result.proposed_lines.length,
  command_stakes:result.commands.map(x=>({category:x.category,jra_input:x.jra_input,
    point_count:x.points,unit_stake_yen:x.unit_stake_yen,stake_yen:x.stake_yen})),
  shadow_proposal_available:result.shadow_proposal_available,
  reason:result.reason,audit:result.audit
 };
 out.push(summary);
 fs.writeFileSync(dir+'/'+entry.race+'.json',JSON.stringify({summary,result},null,2)+'\n');
 console.log('V316_SHADOW_REPLAY_RESULT '+JSON.stringify(summary));
}
fs.writeFileSync(dir+'/summary.json',JSON.stringify({
 as_of:'2026-10-25',study_scope:'frozen prestart only; no official mutation',
 approval_state:'SHADOW_PENDING_REVIEW',
 three_races:out,
 original_public_files_unchanged:true
},null,2)+'\n');
console.log('PASS_V316_REAL_REPLAY '+out.length+' immutable historical JRA races; publication untouched; 100-yen command increments bounded and audited');
