/* Approved in-page report viewer: UI only, canonical bets/predictions unchanged. */
(() => {
  'use strict';
  const host=document.getElementById('weekPredictions');
  if (!host) return;
  const iconText='全頭診断をページ内で開く';
  let sequence=0;

  function setupCards(root) {
    for (const card of root.querySelectorAll('.race-card')) {
      const actions=card.querySelector('.actions');
      if(!actions)continue;
      let reportLink=null;
      for(const a of actions.querySelectorAll('a[href]')){
        const href=a.getAttribute('href')||'';
        
        if(!href.endsWith('.html'))continue;
        if(!href.startsWith('reports/'))continue;
        reportLink=a;
      }
      if(!reportLink || reportLink.dataset.inlinePreview==='1')continue;
      const id='jra-race-inline-'+(++sequence);
      const panel=document.createElement('div');
      panel.className='stage-inline-report';
      panel.id=id;panel.hidden=true;
      const bar=document.createElement('div');bar.className='stage-inline-report-head';
      const title=document.createElement('strong');title.textContent='全頭診断・購入セット';
      const close=document.createElement('button');close.type='button';close.className='stage-inline-close';close.textContent='閉じる';
      close.setAttribute('aria-label','全頭診断を閉じる');
      bar.append(title,close);
      const frame=document.createElement('iframe');
      frame.title='全頭診断レポート';
      frame.loading='lazy';
      frame.referrerPolicy='strict-origin-when-cross-origin';
      panel.append(bar,frame);
      card.append(panel);
      reportLink.dataset.inlinePreview='1';
      reportLink.setAttribute('aria-controls',id);
      reportLink.setAttribute('aria-expanded','false');
      reportLink.textContent=iconText;
      function closePanel(){
        panel.hidden=true;reportLink.setAttribute('aria-expanded','false');
        reportLink.textContent=iconText;
        reportLink.focus({preventScroll:true});
      }
      close.addEventListener('click',closePanel);
      reportLink.addEventListener('click',e=>{
        if(e.button!==0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey)return;
        e.preventDefault();
        if(!panel.hidden){closePanel();return;}
        panel.hidden=false;
        const src=reportLink.getAttribute('href');
        if(frame.getAttribute('src')!==src)frame.setAttribute('src',src);
        reportLink.setAttribute('aria-expanded','true');
        reportLink.textContent='全頭診断を閉じる';
        panel.scrollIntoView({block:'nearest',behavior:'smooth'});
      });
    }
  }
  const observer=new MutationObserver(()=>setupCards(host));
  observer.observe(host,{subtree:true,childList:true});
  setupCards(host);
})();