import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.mjs';

function fakeDB(){
  const records=new Map();
  return {
    records,
    prepare(sql){
      const args={};
      return {
        bind(...params){args.params=params;return this;},
        async run(){
          assert.match(sql,/ON CONFLICT/);
          const [day,event]=args.params;
          const k=day+'|'+event;
          records.set(k,(records.get(k)||0)+1);
          return {success:true};
        },
        async all(){
          const rows=[...records].map(([key,count])=>{
            const [day,event]=key.split('|');return {day,event,count};
          });
          if(sql.includes('GROUP BY')){
            const grouped=new Map();
            for(const r of rows){
              const v=grouped.get(r.event)||{event:r.event,total:0,today:0};
              v.total+=r.count;if(r.day===args.params[0])v.today+=r.count;
              grouped.set(r.event,v);
            }
            return {results:[...grouped.values()]};
          }
          const [start,end]=args.params;
          return {results:rows.filter(r=>r.day>=start&&r.day<=end)};
        }
      };
    }
  };
}
const request=(path,method='GET',payload=null,origin='https://toodataa-ai.github.io')=>{
  const headers={Origin:origin};
  if(payload!==null)headers['Content-Type']='text/plain';
  return new Request('https://keiba-test.invalid'+path,{method,headers,
    ...(payload!==null?{body:JSON.stringify(payload)}:{})});
};
test('missing D1 returns 503, no synthetic zero counts',async()=>{
  const r=await worker.fetch(request('/stats'),{});
  assert.equal(r.status,503);
});
test('isolated count totals and history preserve only observed days',async()=>{
  const DB=fakeDB();
  const payload={site:'keiba-notes',event:'page_home'};
  const success=await worker.fetch(request('/collect','POST',payload),{DB});
  assert.equal(success.status,200);
  const second=await worker.fetch(request('/collect','POST',{site:'keiba-notes',event:'session_start'}),{DB});
  assert.equal(second.status,200);
  const today=await (await worker.fetch(request('/stats'),{DB})).json();
  assert.equal(today.site,'keiba-notes');
  assert.equal(today.totals.page_home,1);
  assert.equal(today.today.session_start,1);
  assert.equal(today.today.page_results,0);
  const history=await (await worker.fetch(request('/history?days=30'),{DB})).json();
  assert.equal(history.recorded_days,1);
  assert.equal(history.rows[0].counts.page_home,1);
  assert.equal(history.rows[0].counts.session_start,1);
});
test('origin rejection, cross-site events and extra payload fields are forbidden',async()=>{
  const DB=fakeDB();
  const p={site:'keiba-notes',event:'page_home'};
  assert.equal((await worker.fetch(request('/collect','POST',p,'https://evil.invalid'),{DB})).status,403);
  assert.equal((await worker.fetch(request('/collect','POST',{site:'tokyo-family-events-ai',event:'page_home'}),{DB})).status,400);
  assert.equal((await worker.fetch(request('/collect','POST',{...p,email:'someone@invalid.test'}),{DB})).status,400);
  assert.equal((await worker.fetch(request('/history?days=999'),{DB})).status,400);
  assert.equal((await worker.fetch(request('/history?days=30&extra=1'),{DB})).status,400);
  assert.equal(DB.records.size,0);
});
