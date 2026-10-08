#!/usr/bin/env node
// End-to-end live Pages check: the JS actually deployed must match committed reviewed UI.
const fs=require('node:fs');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const path='docs/local-racing-shadow.html';
const local=fs.readFileSync(path,'utf8');
const extract=x=>x.match(/<script>\s*([\s\S]*?)<\/script>/)?.[1]||null;
const expected=extract(local);
assert(expected&&expected.includes('function raceReviewHtml'),'Reviewed UI absent in committed HTML');
const expectedHash=crypto.createHash('sha256').update(expected).digest('hex');
const url='https://toodataa-ai.github.io/keiba-notes/local-racing-shadow.html';
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function main(){
  for(let i=1;i<=15;i++){
    try{
      const r=await fetch(url+'?ui_audit='+Date.now(),{headers:{'Cache-Control':'no-cache'},signal:AbortSignal.timeout(16000)});
      if(!r.ok)throw new Error('HTTP '+r.status);
      const live=await r.text();
      const script=extract(live);
      if(!script)throw new Error('No inline script in deployed HTML');
      const actualHash=crypto.createHash('sha256').update(script).digest('hex');
      if(actualHash!==expectedHash)throw new Error('Published HTML script is stale/different');
      assert(script.includes('function raceReviewHtml'),'Missing structured review renderer');
      assert(!script.includes("rev?.summary||rev?.review||rev?.analysis||rev?.text"),'Legacy false-empty review logic still deployed');
      console.log(JSON.stringify({status:'VERIFIED',url,script_sha256:actualHash,
        review_renderer:'DEPLOYED',checked_at:new Date().toISOString()}));
      return;
    }catch(e){
      console.log('COMMITTED_NOT_PUBLISHED attempt '+i+'/15: '+e.message);
      if(i===15)throw e;
      await sleep(10000);
    }
  }
}
main().catch(e=>{console.error('BLOCKED_PUBLICATION: '+e.stack);process.exitCode=1});
