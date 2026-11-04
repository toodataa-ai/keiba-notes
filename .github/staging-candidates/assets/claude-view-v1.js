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
      try{history.replaceState(null,'',cl?'#claude':location.pathname+location.search)}catch(e){}
      if(cl&&!panel.dataset.loaded)load();
    }
    bC.addEventListener('click',function(){show('chatgpt')});bL.addEventListener('click',function(){show('claude')});
    function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
    function yen(n){return n==null?'—':Number(n).toLocaleString('ja-JP')+'円'}
    function pct(x){return x==null?'—':(x*100).toFixed(1)+'%'}
    function bet(b){return esc(b.type)+' '+esc(b.selection.join(b.type==='馬単'||b.type==='三連単'?'→':'-'))+'（'+yen(b.stake_yen)+'）'}
    function card(r){
      var h='<article class="pv-card"><h3>'+esc(r.race_name)+'</h3><p class="pv-meta">'+esc(r.date)+' '+esc(r.venue)+'　予想の版：'+esc(r.prompt_version||'—')+'</p>';
      h+='<ul class="pv-marks">'+r.marks.map(function(m){return '<li>'+esc(m.mark)+' '+esc(m.no)+' '+esc(m.name)+'</li>'}).join('')+'</ul>';
      h+='<p class="pv-bets">'+(r.bets.length?'仮想の買い目：'+r.bets.map(bet).join('、')+'（合計'+yen(r.total_stake_yen)+'）':'見送り')+'</p>';
      if(mode==='results'&&r.result){
        h+='<details class="spoiler-summary"><summary>結果を見る</summary><p class="pv-bets">3着内：'+r.result.finish_top3.join('・')+'　◎'+(r.result.honmei_win?'1着':r.result.honmei_top3?'3着内':'着外')+'　購入'+yen(r.result.stake_yen)+' → 払戻'+yen(r.result.payout_yen)+'</p></details>';
      }else if(mode==='results'){h+='<p class="pv-meta">結果の確認待ち</p>'}
      if(mode==='results'&&r.review){var v=r.review;h+='<details class="spoiler-summary"><summary>Claudeの反省会を見る</summary><div class="pv-bets"><p>'+esc(v.summary)+'</p>'+(v.honmei_result?'<p>◎の結果：'+esc(v.honmei_result)+'</p>':'')+(v.failure_types&&v.failure_types.length?'<p>失敗の分類：'+v.failure_types.map(esc).join('、')+'</p>':'')+(v.lessons&&v.lessons.length?'<p>学んだこと：</p><ul>'+v.lessons.map(function(x){return '<li>'+esc(x)+'</li>'}).join('')+'</ul>':'')+'</div></details>'}
      return h+'</article>';
    }
    function load(){
      panel.dataset.loaded='1';panel.innerHTML='<p class="muted">読み込み中…</p>';
      fetch('data/predictors/claude_status_v1.json',{cache:'no-store'}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(d){
        var rows=d.races||[];var s=d.summary||{};
        var h='<p class="pv-note">これは <strong>Claude</strong> の予想です。ChatGPT の成績とは合算せず、別々に集計します。対象は、JRAの毎開催日のメインレース（11R）です。買い目は「もし買ったら」の仮想で、実際には購入しません。発走前に保存し、あとから変えません。</p>';
        if(mode==='results'){
          h+='<details class="spoiler-summary"><summary>Claude の期間成績を見る<span class="spoiler-warning">的中率・払戻・回収率などの結果を表示します</span></summary><div class="pv-stats">'+
            '<div><span>評価済み</span><strong>'+esc(s.races||0)+'レース</strong></div><div><span>◎勝率 / 複勝率</span><strong>'+pct(s.honmei_win_rate)+' / '+pct(s.honmei_top3_rate)+'</strong></div>'+
            '<div><span>購入（仮想）</span><strong>'+yen(s.stake_yen)+'</strong></div><div><span>払戻</span><strong>'+yen(s.payout_yen)+'</strong></div><div><span>回収率</span><strong>'+pct(s.roi)+'</strong></div></div></details>';
          rows=rows.filter(function(r){return r.result});
        }
        h+=rows.length?rows.map(card).join(''):'<div class="pv-empty">'+(mode==='results'?'まだ結果の出た Claude の予想はありません。':'いま公開している Claude の予想はありません。ChatGPT と同じレースを対象に、次の開催から発走前に保存して、ここに表示します。')+'</div>';
        panel.innerHTML=h;
      }).catch(function(){panel.innerHTML='<div class="pv-empty">Claude のデータを読み込めませんでした。</div>'});
    }
    show(location.hash==='#claude'?'claude':'chatgpt');
  }catch(e){}
})();
