/* 買い目を 流し／フォーメーション／ボックス にまとめる表示用の部品（表示だけ。買い目・金額・結果は変えない）
   BetGroup.group(bets) -> [{kind:'box'|'nagashi'|'formation'|'single', type, text, stake, points, members:[元の番号]}] */
(function(){
  var ORDERED={'馬単':1,'三連単':1},K={'馬連':2,'ワイド':2,'馬単':2,'三連複':3,'三連単':3};
  function key(a,t){return (ORDERED[t]?a:a.slice().sort(function(x,y){return x-y})).join(',')}
  function perms(arr,k){if(k===0)return [[]];var out=[];arr.forEach(function(x,i){perms(arr.filter(function(_,j){return j!==i}),k-1).forEach(function(p){out.push([x].concat(p))})});return out}
  function combs(arr,k){if(k===0)return [[]];if(arr.length<k)return [];var out=[];for(var i=0;i<=arr.length-k;i++)combs(arr.slice(i+1),k-1).forEach(function(c){out.push([arr[i]].concat(c))});return out}
  function uniq(a){var s={};return a.filter(function(x){return s[x]?false:(s[x]=1)}).sort(function(x,y){return x-y})}
  function J(a){return a.join('・')}
  // 候補を作る：{cov:[キー...], label, kind, pri}
  function candidates(type,S){          // S: {キー:true}
    var k=K[type],ord=!!ORDERED[type],out=[],sels=Object.keys(S).map(function(s){return s.split(',').map(Number)}),H=uniq([].concat.apply([],sels));
    function has(a){return !!S[key(a,type)]}
    // ボックス：全部そろう最大の馬の組を探す（馬を減らしながら）
    var U=H.slice();
    function cnt(h,u){return sels.filter(function(s){return s.indexOf(h)>=0&&s.every(function(x){return u.indexOf(x)>=0})}).length}
    while(U.length>=k+(k===2?1:1)){
      var all=(ord?perms(U,k):combs(U,k)),ok=all.every(has);
      if(ok&&U.length>=3&&all.length>=3){out.push({cov:all.map(function(a){return key(a,type)}),kind:'box',pri:3,label:type+' ボックス '+U.join('-')});break}
      var worst=U.slice().sort(function(a,b){return cnt(a,U)-cnt(b,U)})[0];U=U.filter(function(x){return x!==worst});
    }
    if(k===2&&!ord){
      H.forEach(function(a){var P=uniq(sels.filter(function(s){return s.indexOf(a)>=0}).map(function(s){return s[0]===a?s[1]:s[0]}));
        if(P.length>=3)out.push({cov:P.map(function(p){return key([a,p],type)}),kind:'nagashi',pri:2,label:type+' 流し '+a+' → '+J(P)})})
    }
    if(k===2&&ord){
      var f2s={},s2f={};sels.forEach(function(s){(f2s[s[0]]=f2s[s[0]]||[]).push(s[1]);(s2f[s[1]]=s2f[s[1]]||[]).push(s[0])});
      function mk(map,firstCol){var grp={};Object.keys(map).forEach(function(a){var v=uniq(map[a]);(grp[v.join(',')]=grp[v.join(',')]||{v:v,keys:[]}).keys.push(+a)});
        Object.keys(grp).forEach(function(g){var F=grp[g].keys.sort(function(x,y){return x-y}),V=grp[g].v,cov=[];
          F.forEach(function(a){V.forEach(function(b){cov.push(firstCol?key([a,b],type):key([b,a],type))})});
          if(cov.length<3)return;
          var first=firstCol?F:V,second=firstCol?V:F,lab;
          if(first.length===1)lab=type+' 1着流し '+first[0]+' → '+J(second);
          else if(second.length===1)lab=type+' 2着流し '+J(first)+' → '+second[0];
          else lab=type+' フォーメーション 1着 '+J(first)+' → 2着 '+J(second);
          out.push({cov:cov,kind:(first.length===1||second.length===1)?'nagashi':'formation',pri:2,label:lab})})}
      mk(f2s,true);mk(s2f,false);
    }
    if(k===3&&!ord){
      // 2頭軸流し
      var pairs={};sels.forEach(function(s){combs(s,2).forEach(function(p){var kk=p.join(',');(pairs[kk]=pairs[kk]||[]).push(s.filter(function(x){return p.indexOf(x)<0})[0])})});
      Object.keys(pairs).forEach(function(kk){var P=uniq(pairs[kk]);if(P.length>=3){var ab=kk.split(',').map(Number);out.push({cov:P.map(function(p){return key(ab.concat([p]),type)}),kind:'nagashi',pri:2,label:type+' 2頭軸流し '+ab.join('-')+' → '+J(P)})}});
      // 1頭軸流し（相手の組がそろっている）
      H.forEach(function(a){var pr=sels.filter(function(s){return s.indexOf(a)>=0}).map(function(s){return s.filter(function(x){return x!==a})});
        var PH=uniq([].concat.apply([],pr)),V=PH.slice();
        function c2(h,u){return pr.filter(function(p){return p.indexOf(h)>=0&&p.every(function(x){return u.indexOf(x)>=0})}).length}
        while(V.length>=3){var all=combs(V,2);if(all.every(function(p){return has([a].concat(p))})){out.push({cov:all.map(function(p){return key([a].concat(p),type)}),kind:'nagashi',pri:1,label:type+' 1頭軸流し '+a+' → '+J(V)});break}
          var w=V.slice().sort(function(x,y){return c2(x,V)-c2(y,V)})[0];V=V.filter(function(x){return x!==w})}})
    }
    if(k===3&&ord){
      var byF={};sels.forEach(function(s){(byF[s[0]]=byF[s[0]]||[]).push([s[1],s[2]])});
      var grp={};Object.keys(byF).forEach(function(f){var pk=byF[f].map(function(p){return p.join(',')}).sort().join('|');(grp[pk]=grp[pk]||{pairs:byF[f],F:[]}).F.push(+f)});
      Object.keys(grp).forEach(function(g){var B=uniq(grp[g].pairs.map(function(p){return p[0]})),C=uniq(grp[g].pairs.map(function(p){return p[1]})),n=0;
        B.forEach(function(b){C.forEach(function(c){if(b!==c)n++})});
        if(n!==grp[g].pairs.length||n<2)return;var F=grp[g].F.sort(function(x,y){return x-y}),cov=[];
        F.forEach(function(f){grp[g].pairs.forEach(function(p){cov.push(key([f,p[0],p[1]],type))})});
        if(cov.length<3)return;
        out.push({cov:cov,kind:F.length===1&&B.join()===C.join()?'nagashi':'formation',pri:2,label:type+' フォーメーション 1着 '+J(F)+' → 2着 '+J(B)+' → 3着 '+J(C)})})
    }
    return out;
  }
  function group(bets){
    var res=[],by={},order=[];
    (bets||[]).forEach(function(b,i){var t=b.type,g=t+'|'+(b.stake_yen||0);if(!by[g]){by[g]={type:t,stake:b.stake_yen||0,items:[]};order.push(g)}by[g].items.push({sel:(b.selection||[]).map(Number),i:i})});
    order.forEach(function(g){var G=by[g],t=G.type;
      if(!K[t]){ // 単勝・複勝など：同じ金額をまとめる
        var nums=G.items.map(function(x){return x.sel.join('-')}),idx=G.items.map(function(x){return x.i});
        res.push({kind:'single',type:t,text:t+' '+nums.join('・'),stake:G.stake,points:idx.length,members:idx});return}
      var S={},at={};G.items.forEach(function(x){var k=key(x.sel,t);S[k]=true;at[k]=x.i});
      for(var guard=0;guard<30;guard++){
        var cs=candidates(t,S).map(function(c){c.cov=c.cov.filter(function(k){return S[k]});return c}).filter(function(c){return c.cov.length>=3});
        if(!cs.length)break;
        cs.sort(function(a,b){return b.cov.length-a.cov.length||b.pri-a.pri});
        var c=cs[0];res.push({kind:c.kind,type:t,text:c.label,stake:G.stake,points:c.cov.length,members:c.cov.map(function(k){return at[k]})});
        c.cov.forEach(function(k){delete S[k]});
      }
      var left=Object.keys(S).map(function(k){return {k:k,i:at[k]}}).sort(function(a,b){return a.i-b.i});
      if(left.length)res.push({kind:'single',type:t,text:t+' '+left.map(function(x){return x.k.split(',').join(ORDERED[t]?'→':'-')}).join('、'),stake:G.stake,points:left.length,members:left.map(function(x){return x.i})});
    });
    return res.sort(function(a,b){return Math.min.apply(null,a.members)-Math.min.apply(null,b.members)});
  }
  window.BetGroup={group:group};
})();

/* 「今週のAI予想」「過去の成績」に、ChatGPT / Claude の切り替えを足す。
   ChatGPT 側の表示は一切変えない（Claude 側は別のデータを読む）。成績は合算しない。 */
(function(){
  try{
    var tag=document.currentScript;var mode=(tag&&tag.dataset.view)||'week';
    var main=document.querySelector('main');if(!main)return;
    var css=document.createElement('style');
    css.textContent='main [hidden]{display:none!important}.pv-tabs{display:flex;gap:8px;margin:0 0 16px;flex-wrap:wrap}.pv-tabs button{font:inherit;font-size:15px;font-weight:700;min-height:44px;padding:0 18px;border-radius:22px;border:1px solid #c9ccd3;background:#fff;color:#17171a;cursor:pointer}.pv-tabs button[aria-pressed=true]{background:#17171a;color:#fff;border-color:#17171a}.pv-note{margin:0 0 14px;padding:10px 12px;border-radius:11px;background:#f4f6fb;border:1px solid #d9deea;font-size:14px;line-height:1.6}.pv-card{background:#fff;border:1px solid #e2e2e6;border-radius:14px;padding:13px 15px;margin-bottom:10px}.pv-card h3{margin:0 0 4px;font-size:17px}.pv-meta{color:#71717a;font-size:13px;margin:0 0 8px}.pv-marks{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px;padding:0;list-style:none}.pv-marks li{padding:4px 10px;border-radius:999px;background:#f3f3f5;font-size:14px}.pv-bets{margin:6px 0 0;font-size:14px;line-height:1.7}.pv-stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:0 0 16px}.pv-stats div{background:#fff;border:1px solid #e2e2e6;border-radius:14px;padding:12px 14px}.pv-stats span{display:block;color:#71717a;font-size:13px}.pv-stats strong{font-size:20px}.pv-empty{padding:18px;border:1px dashed #c9ccd3;border-radius:14px;color:#52525b;line-height:1.7}';
    document.head.appendChild(css);
    var kids=Array.prototype.slice.call(main.children).filter(function(k){return !(mode==='week'&&((k.querySelector&&k.querySelector('#weekSchedule'))||(k.tagName==='P'&&k.textContent.indexOf('発走前に確定して保存')>=0)))});/* 次回の対象レースの予定は ChatGPT と Claude で共通なので、切り替えても隠さない */
    var panel=document.createElement('div');panel.id='claudePanel';panel.hidden=true;
    var tabs=document.createElement('div');tabs.className='pv-tabs';tabs.setAttribute('role','group');tabs.setAttribute('aria-label','予想者の切り替え');
    function mk(label,key){var b=document.createElement('button');b.type='button';b.textContent=label;b.dataset.key=key;return b}
    var bC=mk('ChatGPTの予想','chatgpt'),bL=mk('Claudeの予想','claude');tabs.appendChild(bC);tabs.appendChild(bL);
    main.insertBefore(tabs,main.firstChild);main.appendChild(panel);
    function show(key){
      var cl=key==='claude';
      kids.forEach(function(k){if(k.dataset.pvWas===undefined)k.dataset.pvWas=k.hidden?'1':'0';k.hidden=cl?true:k.dataset.pvWas==='1'});
      panel.hidden=!cl;bC.setAttribute('aria-pressed',String(!cl));bL.setAttribute('aria-pressed',String(cl));
      try{history.replaceState(null,'',location.pathname+location.search+(cl?'#claude':''))}catch(e){}
      if(cl&&!panel.dataset.loaded)load();
    }
    bC.addEventListener('click',function(){show('chatgpt')});bL.addEventListener('click',function(){show('claude')});
    function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
    function yen(n){return n==null?'—':Number(n).toLocaleString('ja-JP')+'円'}
    function pct(x){return x==null?'—':(x*100).toFixed(1)+'%'}
    function bet(b){return esc(b.type)+' '+esc(b.selection.join(b.type==='馬単'||b.type==='三連単'?'→':'-'))+'（'+yen(b.stake_yen)+'）'}
    function grouped(bets){try{return window.BetGroup.group(bets).map(function(g){return esc(g.text)+'（'+(g.points>1?g.points+'点・各'+yen(g.stake):yen(g.stake))+'）'}).join('、')}catch(e){return bets.map(bet).join('、')}}
    function card(r){
      var h='<article class="pv-card"><h3>'+esc(r.race_name)+'</h3><p class="pv-meta">'+esc(r.date)+' '+esc(r.venue)+'　予想の版：'+esc(r.prompt_version||'—')+'</p>';
      h+='<ul class="pv-marks">'+r.marks.map(function(m){return '<li>'+esc(m.mark)+' '+esc(m.no)+' '+esc(m.name)+'</li>'}).join('')+'</ul>';
      h+='<p class="pv-bets">'+(r.bets.length?'仮想の買い目：'+grouped(r.bets)+'（合計'+yen(r.total_stake_yen)+'）':'見送り')+'</p>';
      if(mode==='results'&&r.result){
        h+='<details class="spoiler-summary"><summary>結果を見る</summary><p class="pv-bets">3着内：'+r.result.finish_top3.join('・')+'　◎'+(r.result.honmei_win?'1着':r.result.honmei_top3?'3着内':'着外')+'　購入'+yen(r.result.stake_yen)+' → 払戻'+yen(r.result.payout_yen)+'</p></details>';
      }else if(mode==='results'){h+='<p class="pv-meta">結果の確認待ち</p>'}
      if(mode==='results'&&r.review){var v=r.review;h+='<details class="spoiler-summary"><summary>Claudeの反省会を見る</summary><div class="pv-bets"><p>'+esc(v.summary)+'</p>'+(v.honmei_result?'<p>◎の結果：'+esc(v.honmei_result)+'</p>':'')+(v.failure_types&&v.failure_types.length?'<p>失敗の分類：'+v.failure_types.map(esc).join('、')+'</p>':'')+(v.lessons&&v.lessons.length?'<p>学んだこと：</p><ul>'+v.lessons.map(function(x){return '<li>'+esc(x)+'</li>'}).join('')+'</ul>':'')+'</div></details>'}
      if(r.report)h+='<p class="pv-bets"><a class="btn" href="'+esc(encodeURI(r.report))+'">予想詳細を見る</a></p>';
      return h+'</article>';
    }

    /* ---- 過去の成績：ChatGPT 側（results.js）と同じ部品・同じ並びで表示する ---- */
    function pctN(n,d){return d?(n/d*100).toFixed(1)+'%':'—'}
    function yenN(n){return isFinite(n)&&n!==null?Math.round(n).toLocaleString('ja-JP')+'円':'—'}
    function wkRange(s){var a=s.split('-').map(Number),dt=new Date(Date.UTC(a[0],a[1]-1,a[2])),back=(dt.getUTCDay()+6)%7,st=new Date(dt);st.setUTCDate(dt.getUTCDate()-back);var en=new Date(st);en.setUTCDate(st.getUTCDate()+6);function iso(d){return d.getUTCFullYear()+'-'+('0'+(d.getUTCMonth()+1)).slice(-2)+'-'+('0'+d.getUTCDate()).slice(-2)}return{key:iso(st),start:iso(st),end:iso(en)}}
    function pKey(m,r){if(m==='year')return r.date.slice(0,4);if(m==='month')return r.date.slice(0,7);if(m==='week')return wkRange(r.date).key;return 'all'}
    function pText(m,k,rows){if(m==='all')return '全期間';if(m==='year')return k+'年';if(m==='month'){var a=k.split('-');return a[0]+'年'+Number(a[1])+'月'}var s=rows.filter(function(r){return wkRange(r.date).key===k})[0];var w=s?wkRange(s.date):{start:k,end:k};return w.start+'〜'+w.end}
    var ORDERED={'馬単':1,'三連単':1};
    function selText(b){return (b.selection||[]).join(ORDERED[b.type]?'→':'-')}
    function fallbackHit(b,t){var s=b.selection||[];function has(n){return t.indexOf(n)>=0}
      if(b.type==='単勝')return s[0]===t[0];if(b.type==='複勝')return has(s[0]);
      if(b.type==='馬連')return s.length===2&&has(s[0])&&has(s[1])&&t.indexOf(s[0])<2&&t.indexOf(s[1])<2;
      if(b.type==='ワイド')return s.length===2&&has(s[0])&&has(s[1]);
      if(b.type==='馬単')return s[0]===t[0]&&s[1]===t[1];
      if(b.type==='三連複')return s.length===3&&s.every(has);
      if(b.type==='三連単')return s[0]===t[0]&&s[1]===t[1]&&s[2]===t[2];return false}
    function settled(r){/* 買い目ごとの的中・払戻。公開データに無い古い版でも、的中だけは着順から判定する */
      var br=r.result&&r.result.bet_results;
      return (r.bets||[]).map(function(b,i){
        var x=br&&br[i]&&br[i].type===b.type?br[i]:null;
        if(x)return{b:b,hit:!!x.hit,payout:Number(x.payout_yen||0),known:true};
        var h=fallbackHit(b,(r.result&&r.result.finish_top3)||[]);return{b:b,hit:h,payout:null,known:false}})}
    function betPanelC(r){
      var rows=settled(r);
      if(!rows.length)return '<div class="bet-panel"><div class="bet-empty">この予想は購入見送りで、買い目はありません（馬券0円）。</div></div>';
      var stake=Number(r.result.stake_yen||0),payout=Number(r.result.payout_yen||0),profit=payout-stake;
      var counts={},order=[];rows.forEach(function(x){if(!counts[x.b.type]){counts[x.b.type]=0;order.push(x.b.type)}counts[x.b.type]++});
      var summary=order.map(function(t){return t+counts[t]+'点'}).join('・');
      var groups;try{groups=window.BetGroup.group(r.bets)}catch(e){groups=rows.map(function(x,i){return{kind:'single',type:x.b.type,text:x.b.type+' '+selText(x.b),stake:x.b.stake_yen,points:1,members:[i]}})}
      var list=groups.map(function(g){
        var ms=g.members.map(function(i){return rows[i]}),hit=ms.some(function(x){return x.hit}),known=ms.every(function(x){return x.payout!=null}),pay0=ms.reduce(function(a,x){return a+(x.payout||0)},0),stk=ms.reduce(function(a,x){return a+Number(x.b.stake_yen||0)},0);
        var cls=hit?'hit':'miss',pay=known?'払戻 '+yenN(pay0):'払戻 —';
        var reason=(ms.length===1&&ms[0].b.reason)?'<span>理由 '+esc(ms[0].b.reason)+'</span>':'';
        var label=g.text.indexOf(g.type+' ')===0?g.text.slice(g.type.length+1):g.text;
        var sel=esc(label)+(g.points>1?'（'+g.points+'点・各'+yenN(g.stake)+'）':'');
        return '<div class="bet-row '+(hit?'is-hit':'')+'"><div class="bet-main"><span class="bet-type">'+esc(g.type)+'</span><span class="bet-selection">'+sel+'</span></div><span class="bet-status '+cls+'">'+(hit?'的中':'ハズレ')+'</span><div class="bet-money"><span>購入 '+yenN(stk)+'</span><span class="'+(hit&&pay0>0?'payout-hit':'')+'">'+esc(pay)+'</span>'+reason+'</div></div>'}).join('');
      return '<section class="bet-panel" aria-label="仮想の買い目"><div class="bet-panel-head"><strong>仮想の買い目（実際には購入していません）</strong><span>'+esc(summary)+' ／ '+rows.length+'点 / 発走前固定</span></div><div class="bet-list">'+list+'</div><div class="bet-total"><div><small>購入合計（仮想）</small><strong>'+yenN(stake)+'</strong></div><div><small>払戻合計</small><strong>'+yenN(payout)+'</strong></div><div><small>収支</small><strong class="'+(profit>0?'positive':profit<0?'negative':'')+'">'+yenN(profit)+'</strong></div></div></section>'}
    function reviewText(v){if(!v)return '';var t=v.summary||'';if(v.honmei_result)t+='\n\n◎の結果：'+v.honmei_result;if(v.failure_types&&v.failure_types.length)t+='\n失敗の分類：'+v.failure_types.join('、');if(v.lessons&&v.lessons.length)t+='\n\n学んだこと：\n'+v.lessons.map(function(x){return '・'+x}).join('\n');return t}
    function raceCardC(r){
      var pass=!(r.bets&&r.bets.length);var hit=!pass&&Number(r.result.payout_yen||0)>0;
      var mk={};(r.marks||[]).forEach(function(m){if(!mk[m.mark])mk[m.mark]=m});
      var marks='<div class="marks">'+['◎','○','▲'].map(function(k){var m=mk[k];return '<span class="mark"><b>'+k+'</b>'+(m?esc(m.no+' '+m.name):'—')+'</span>'}).join('')+'</div>';
      var outcome=pass?'<span class="status">購入見送り（馬券0円）</span>':hit?'<span class="status reviewed">的中あり</span>':'<span class="status">全買い目ハズレ</span>';
      var top3=(r.result.finish_top3||[]).join('・');
      var res='<div class="result-box result-summary"><b>レース結果</b><br>3着内（馬番）：'+esc(top3)+'　◎'+(r.result.honmei_win?'1着':r.result.honmei_top3?'3着内':'着外')+'</div>';
      var spoiler='<details class="race-spoiler"><summary>結果・馬券成績を見る<span class="spoiler-warning">着順・的中／ハズレ・払戻・収支を表示します</span></summary><div class="race-spoiler-body"><div class="result-outcome">'+outcome+'</div>'+res+betPanelC(r)+'</div></details>';
      var rv=r.review?'<details class="review-disclosure"><summary>反省会を見る</summary><div class="review-box">'+esc(reviewText(r.review))+'</div></details>':'';
      var act=r.report?'<div class="actions"><a class="btn" href="'+esc(encodeURI(r.report))+'">予想詳細を見る</a></div>':'';
      return '<article class="race-card"><div class="race-top"><div><div class="meta">'+esc(r.date)+' · '+esc(r.venue||'JRA')+' · '+esc(r.prompt_version||'—')+'</div><h3>'+esc(r.race_name||'')+'</h3></div><span class="status reviewed">'+(r.review?'回顧済み':'結果確認済み')+'</span></div>'+marks+spoiler+rv+act+'</article>'}
    function renderResults(all){
      var h='<p class="pv-note">これは <strong>Claude</strong> の予想です。ChatGPT の成績とは合算せず、別々に集計します。対象は、JRAの毎開催日のメインレース（11R）です。買い目は「もし買ったら」の仮想で、実際には購入しません。発走前に保存し、あとから変えません。</p>';
      if(!all.length){panel.innerHTML=h+'<div class="pv-empty">まだ結果の出た Claude の予想はありません。</div>';return}
      h+='<section class="period-panel"><div><h2>集計期間</h2></div><div class="period-controls"><select id="cvMode" aria-label="期間単位"><option value="all">全期間</option><option value="year">年別</option><option value="month">月別</option><option value="week">開催週別</option></select><select id="cvValue" aria-label="期間" disabled><option value="all">全期間</option></select></div><p id="cvLabel" class="period-label">全期間</p></section>'+
        '<details class="spoiler-summary"><summary>期間成績を見る<span class="spoiler-warning">的中率・払戻・回収率・収支などの結果を表示します</span></summary><div class="spoiler-body"><section class="results-stats" id="cvStats" aria-label="Claudeの期間成績"></section></div></details>'+
        '<section class="section-head"><div><h2>レース別の結果・反省会</h2></div></section><div id="cvList" class="race-list"></div>';
      panel.innerHTML=h;
      var mode=document.getElementById('cvMode'),value=document.getElementById('cvValue');
      function fill(){var m=mode.value;value.innerHTML='';if(m==='all'){value.disabled=true;value.innerHTML='<option value="all">全期間</option>';return}value.disabled=false;var seen={};all.forEach(function(r){seen[pKey(m,r)]=1});Object.keys(seen).sort().reverse().forEach(function(k){var o=document.createElement('option');o.value=k;o.textContent=pText(m,k,all);value.appendChild(o)})}
      function rowsNow(){return mode.value==='all'?all.slice():all.filter(function(r){return pKey(mode.value,r)===value.value})}
      function render(){
        var rs=rowsNow();document.getElementById('cvLabel').textContent=pText(mode.value,value.value,all);
        var bought=rs.filter(function(r){return Number(r.result.stake_yen||0)>0});
        var hits=bought.filter(function(r){return Number(r.result.payout_yen||0)>0}).length;
        var stake=0,payout=0;rs.forEach(function(r){stake+=Number(r.result.stake_yen||0);payout+=Number(r.result.payout_yen||0)});
        var profit=payout-stake;
        var hm=rs.filter(function(r){return r.result.honmei_win!==null&&r.result.honmei_win!==undefined});
        var wins=hm.filter(function(r){return r.result.honmei_win}).length,places=hm.filter(function(r){return r.result.honmei_top3}).length;
        document.getElementById('cvStats').innerHTML=
          '<article><span class="label">評価済み</span><strong>'+rs.length+'</strong><span class="unit">レース</span></article>'+
          '<article><span class="label">的中レース率（購入レース）</span><strong>'+pctN(hits,bought.length)+'</strong></article>'+
          '<article><span class="label">購入金額（仮想）</span><strong>'+yenN(stake)+'</strong></article>'+
          '<article><span class="label">払戻金額</span><strong>'+yenN(payout)+'</strong></article>'+
          '<article><span class="label">回収率</span><strong>'+(stake?(payout/stake*100).toFixed(1)+'%':'—')+'</strong></article>'+
          '<article><span class="label">収支</span><strong class="'+(profit>0?'positive':profit<0?'negative':'')+'">'+yenN(profit)+'</strong></article>'+
          '<article class="wide"><span class="label">◎勝率 / 複勝率</span><strong>'+(hm.length?pctN(wins,hm.length)+' / '+pctN(places,hm.length):'—')+'</strong></article>';
        document.getElementById('cvList').innerHTML=rs.length?rs.map(raceCardC).join(''):'<p class="muted">該当する成績はありません。</p>';
      }
      mode.addEventListener('change',function(){fill();render()});value.addEventListener('change',render);fill();render();
    }
    function load(){
      panel.dataset.loaded='1';panel.innerHTML='<p class="muted">読み込み中…</p>';
      fetch('data/predictors/claude_status_v1.json',{cache:'no-store'}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(d){
        var rows=d.races||[];var s=d.summary||{};
        if(mode==='results'){renderResults(rows.filter(function(r){return r.result}));return}
        rows=rows.filter(function(r){return !r.result});/* 今週：結果が出たレースは過去の成績へ */
        var h='<p class="pv-note">これは <strong>Claude</strong> の予想です。ChatGPT の成績とは合算せず、別々に集計します。対象は、JRAの毎開催日のメインレース（11R）です。買い目は「もし買ったら」の仮想で、実際には購入しません。発走前に保存し、あとから変えません。</p>';
        h+=rows.length?rows.map(card).join(''):'<div class="pv-empty">いま公開している Claude の予想はありません。ChatGPT と同じレースを対象に、次の開催から発走前に保存して、ここに表示します。</div>';
        panel.innerHTML=h;
      }).catch(function(){panel.innerHTML='<div class="pv-empty">Claude のデータを読み込めませんでした。</div>'});
    }
    show(location.hash==='#claude'?'claude':'chatgpt');
  }catch(e){}
})();
