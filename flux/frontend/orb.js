/* One continuous clock and one shared plasma surface for all visible Flux orbs. */
'use strict';
window.FluxOrb = (() => {
  const profiles = {
    idle:      {speed:.42, lift:1, energy:.24, spread:1, swirl:.25, pulse:.12},
    listening: {speed:.78, lift:1.4, energy:.56, spread:1.015, swirl:.47, pulse:.4},
    thinking:  {speed:1.05, lift:.6, energy:.64, spread:.99, swirl:1.1, pulse:.2},
    speaking:  {speed:1.15, lift:1.15, energy:.82, spread:1.025, swirl:.55, pulse:1},
    error:     {speed:.27, lift:.5, energy:.25, spread:.99, swirl:.2, pulse:.1}
  };
  const tracked = new Map();
  const systemMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let current = {...profiles.idle}, target = profiles.idle;
  let phase=0, previous=0, frame=0, level=0, audio=0, soften=false, replyUntil=0, lastRender=0;
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      const layers=tracked.get(entry.target);
      if (layers) layers.visible=entry.isIntersecting;
    }
  });
  function element(className) {const e=document.createElement('span');e.className=className;return e;}
  function mount(root) {
    if (tracked.has(root)) return root;
    root.classList.add('orb-live');
    root.setAttribute('role','img');
    root.setAttribute('aria-label','Flux');
    let image = root.querySelector('img');
    if(!image){image=document.createElement('img');image.src='../assets/flux-orb.png';image.alt='';}
    const core=element('orb-core'),canvas=document.createElement('canvas');canvas.className='orb-plasma';
    const miniature=root.classList.contains('orb-small')||root.classList.contains('brand-orb');
    canvas.width=canvas.height=miniature?80:320;
    image.className='orb-source';core.append(image,canvas);root.replaceChildren(core);
    const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
    tracked.set(root,{core,canvas,ctx,visible:true});
    observer.observe(root);
    start();
    return root;
  }
  function create(className='') {const root=document.createElement('span');root.className='orb '+className;return mount(root);}
  function release(root) {observer.unobserve(root);tracked.delete(root);}
  function start(){if(!frame&&!document.hidden)frame=requestAnimationFrame(tick);}
  function tick(now){
    frame=0;
    const dt=previous?Math.min((now-previous)/1000,.05):1/60;previous=now;
    const blend=1-Math.exp(-dt*3.8);
    const destination=target===profiles.idle&&now<replyUntil?profiles.speaking:target;
    for(const key in current)current[key]+=(destination[key]-current[key])*blend;
    audio+=(level-audio)*(1-Math.exp(-dt*8));
    const reduced=soften||systemMotion.matches;
    phase+=dt*(reduced?.12:current.speed);
    const drift=Math.sin(phase*.71), breath=Math.sin(phase*1.19+.7);
    const anyVisible=[...tracked].some(([root,l])=>root.isConnected&&l.visible);
    const interval=FluxPlasma.cost>18?50:1000/30;
    const redraw=anyVisible&&now-lastRender>=interval&&FluxPlasma.render(phase,current,audio,reduced);
    if(redraw)lastRender=now;
    for(const [root,l] of tracked){
      if(!root.isConnected){release(root);continue;}
      if(!l.visible)continue;
      const miniature=root.classList.contains('orb-small')||root.classList.contains('brand-orb');
      const motion=reduced?.08:miniature?.5:1;
      // Position is secondary: the canvas changes even with this transform removed.
      const scale=1+((current.spread-1)+breath*.003)*motion;
      l.core.style.transform=`translate3d(0,${drift*.6*current.lift*motion}px,0) scale(${scale})`;
      if(redraw){
        l.ctx.clearRect(0,0,l.canvas.width,l.canvas.height);
        l.ctx.drawImage(FluxPlasma.surface,0,0,l.canvas.width,l.canvas.height);
        root.dataset.rendered='true';
      }
    }
    start();
  }
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden){cancelAnimationFrame(frame);frame=0;previous=0;}else start();
  });
  return {
    mount,create,release,
    setState(name){target=profiles[name]||profiles.idle;},
    respond(){replyUntil=performance.now()+1000;start();},
    setLevel(value){level=Math.min(1,Math.max(0,Number(value)||0));},
    reduce(value){soften=!!value;},
    // Used by desktop checks to verify the clock stays alive during a blocked LLM worker.
    get phase(){return phase;}
  };
})();
