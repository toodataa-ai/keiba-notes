/* Staging-only report-in-place preview. Production data/selection and common week.js remain unchanged. */
(() => {
  'use strict';
  const host=document.getElementById('weekPredictions');
  if (!host) return;
  const reportOverrides=new Map([
    ['reports/2026-10-12-october-stakes-v315-readable-v103.html','lab/jra-v315-20261012/tokyo11.html'],
    ['reports/2026-10-12-swan-stakes-v315-readable-v103.html','lab/jra-v315-20261012/kyoto11.html']
  ]);
  const pdfOverrides=new Map([
    ['pdfs/2026-10-12-october-stakes-v315-readable-v103.pdf','lab/jra-v315-20261012/tokyo11.pdf'],
    ['pdfs/2026-10-12-swan-stakes-v315-readable-v103.pdf','lab/jra-v315-20261012/kyoto11.pdf']
  ]);
  const simByReport=new Map([
    ['reports/2026-10-12-october-stakes-v315-readable-v103.html','2026-10-12-october-stakes'],
    ['reports/2026-10-12-swan-stakes-v315-readable-v103.html','2026-10-12-swan-stakes'],
    ['lab/jra-v315-20261012/tokyo11.html','2026-10-12-october-stakes'],
    ['lab/jra-v315-20261012/kyoto11.html','2026-10-12-swan-stakes']
  ]);
  const iconText='全頭診断をページ内で開く';
  let sequence=0;

  function setupCards(root) {
    for (const card of root.querySelectorAll('.race-card')) {
      const actions=card.querySelector('.actions');
      if(!actions)continue;
      let reportLink=null;
      for(const a of actions.querySelectorAll('a[href]')){
        const href=a.getAttribute('href')||'';
        if(href.endsWith('.pdf') && pdfOverrides.has(href))a.setAttribute('href',pdfOverrides.get(href));
        if(!href.endsWith('.html'))continue;
        if(!href.startsWith('reports/') && !href.startsWith('lab/jra-v315-20261012/'))continue;
        const dest=reportOverrides.get(href)||href;
        if(href!==dest)a.setAttribute('href',dest);
        reportLink=a;
      }
      if(reportLink){
        // Preview integration: keep both the established in-card report and original PDF link.
        const simRace=simByReport.get(reportLink.getAttribute('href')||'');
        if(simRace && actions.dataset.simulatorAdded!=='1'){
          const link=document.createElement('a');
          link.className='btn secondary';
          link.href='lab/race-simulator.html?race='+encodeURIComponent(simRace);
          link.textContent='レースシミュレーション';
          link.setAttribute('aria-label','仮想の位置取りと進路をレースアニメーションで確認');
          actions.append(link);
          actions.dataset.simulatorAdded='1';
        }
      }
      if(!reportLink || reportLink.dataset.inlinePreview==='1')continue;
      const id='stage-race-inline-'+(++sequence);
      const panel=document.createElement('div');
      panel.className='stage-inline-report';
      panel.id=id;panel.hidden=true;
      const bar=document.createElement('div');bar.className='stage-inline-report-head';
      const title=document.createElement('strong');title.textContent='全頭診断・購入セット（表示検証）';
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