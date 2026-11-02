/* 「一番上へ」「トップページへ」の浮かぶボタン。少し下へスクロールすると出る。 */
(function(){
  try{
    var path=location.pathname||'';
        var css=document.createElement('style');
    css.textContent=
      '.pgnav{position:fixed;right:12px;bottom:calc(env(safe-area-inset-bottom,0px) + 84px);z-index:50;display:flex;flex-direction:column;gap:8px;opacity:0;pointer-events:none;transform:translateY(8px);transition:opacity .2s,transform .2s}'+
      '.pgnav.on{opacity:1;pointer-events:auto;transform:none}'+
      '.pgnav a,.pgnav button{font:inherit;font-size:13px;font-weight:700;line-height:1;min-height:44px;min-width:44px;padding:0 14px;border-radius:22px;border:1px solid #c9ccd3;background:rgba(255,255,255,.96);color:#19191d;box-shadow:0 2px 8px rgba(0,0,0,.18);text-decoration:none;display:flex;align-items:center;justify-content:center;gap:6px;cursor:pointer}'+
      '@media(prefers-reduced-motion:reduce){.pgnav{transition:none}}';
    document.head.appendChild(css);
    var box=document.createElement('div');
    box.className='pgnav';
    box.setAttribute('role','navigation');
    box.setAttribute('aria-label','ページ移動');
    var up=document.createElement('button');
    up.type='button';
    up.textContent='↑ 一番上へ';
    up.addEventListener('click',function(){
      var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
      window.scrollTo({top:0,behavior:reduce?'auto':'smooth'});
    });
    box.appendChild(up);
    document.body.appendChild(box);
    function sync(){box.classList.toggle('on',(window.scrollY||document.documentElement.scrollTop)>400)}
    window.addEventListener('scroll',sync,{passive:true});
    sync();
  }catch(e){}
})();
