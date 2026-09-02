document.addEventListener('DOMContentLoaded', () => {
  const menu = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.main-nav');
  if (menu && nav) menu.addEventListener('click', () => { const open = nav.classList.toggle('open'); menu.setAttribute('aria-expanded', open ? 'true' : 'false'); });
  document.querySelectorAll('.toast').forEach((t,i) => setTimeout(() => { t.style.opacity='0'; t.style.transform='translateX(20px)'; setTimeout(()=>t.remove(),300); }, 3200+i*250));
  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => entries.forEach(e => {if(e.isIntersecting){e.target.classList.add('visible');observer.unobserve(e.target)}}), {threshold:.08}) : null;
  document.querySelectorAll('.reveal').forEach(el => observer ? observer.observe(el) : el.classList.add('visible'));
  document.querySelectorAll('.qty-form').forEach(form => { const input=form.querySelector('input'); const minus=form.querySelector('.qty-minus'); const plus=form.querySelector('.qty-plus'); if(minus) minus.onclick=()=>input.value=Math.max(0,(parseInt(input.value)||1)-1); if(plus) plus.onclick=()=>input.value=Math.min(parseInt(input.max)||999,(parseInt(input.value)||0)+1); });
  const checkout=document.querySelector('[data-demo-checkout]'); if(checkout) checkout.onclick=()=>alert('Demo checkout only - no payment is processed.');
  const contact=document.querySelector('[data-demo-contact]'); if(contact) contact.addEventListener('submit',e=>{e.preventDefault();alert('Thanks! This demo contact form is ready for a real email/database integration.');contact.reset();});
  const form=document.getElementById('supportForm'), input=document.getElementById('supportInput'), log=document.getElementById('chatLog');
  const answer=q=>{q=q.toLowerCase();if(q.includes('track')||q.includes('order'))return 'Order tracking is a demo in this version because the current database has no orders table. A production version would connect an orders module here.';if(q.includes('ship'))return 'Shipping information can be presented here instantly. This demo assumes standard delivery information rather than live courier data.';if(q.includes('pay'))return 'No real payment is processed in this local project. Checkout and payment messaging are intentionally demo-safe.';if(q.includes('return')||q.includes('refund'))return 'Returns and refunds can be handled through a policy knowledge base. This demo can answer policy questions but does not process refunds.';if(q.includes('product')||q.includes('stock')||q.includes('price'))return 'Use Products or Smart Search to see product descriptions, prices, ratings, brands and live stock from the connected catalogue.';return 'I can help with product information, order tracking demos, shipping, payments, returns and refunds.'};
  const add=(text,cls)=>{if(!log)return;const d=document.createElement('div');d.className=cls;d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight};
  if(form) form.addEventListener('submit',async e=>{e.preventDefault();const q=input.value.trim();if(!q)return;add(q,'user-bubble');input.value='';try{const r=await fetch('/api/support',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});if(!r.ok)throw new Error('Request failed');const data=await r.json();add(data.answer||'Sorry, I could not answer that.','bot-bubble')}catch(err){add(answer(q),'bot-bubble')}});
  document.querySelectorAll('[data-question]').forEach(b=>b.addEventListener('click',()=>{const map={product:'Tell me about product information',track:'How do I track an order?',shipping:'Tell me about shipping',payment:'How do payments work?',return:'What is the returns and refunds policy?'};const q=map[b.dataset.question];if(input){input.value=q;input.focus()}}));
});


// Module 8 visual experience enhancements — no external libraries.
(() => {
  const top = document.createElement('button');
  top.id = 'ssScrollTop'; top.type = 'button'; top.setAttribute('aria-label','Back to top'); top.innerHTML = '↑';
  document.body.appendChild(top);
  const onScroll = () => top.classList.toggle('show', window.scrollY > 420);
  window.addEventListener('scroll', onScroll, {passive:true}); onScroll();
  top.addEventListener('click', () => window.scrollTo({top:0, behavior:'smooth'}));

  document.querySelectorAll('.btn, .icon-link, .account-link').forEach(el => {
    el.addEventListener('pointerdown', e => {
      if (el.disabled) return;
      const r = document.createElement('span'); r.className='ss-ripple';
      const rect=el.getBoundingClientRect(); const size=Math.max(rect.width,rect.height);
      r.style.width=r.style.height=size+'px'; r.style.left=(e.clientX-rect.left-size/2)+'px'; r.style.top=(e.clientY-rect.top-size/2)+'px';
      el.appendChild(r); setTimeout(()=>r.remove(),500);
    });
  });
  document.querySelectorAll('.product-card, .category-card, .feature-card').forEach(card => {
    card.addEventListener('pointermove', e => {
      if (window.matchMedia('(max-width: 900px)').matches) return;
      const r=card.getBoundingClientRect(), x=(e.clientX-r.left)/r.width-.5, y=(e.clientY-r.top)/r.height-.5;
      card.style.transform=`perspective(900px) rotateX(${(-y*2.2).toFixed(2)}deg) rotateY(${(x*2.2).toFixed(2)}deg) translateY(-7px)`;
    });
    card.addEventListener('pointerleave',()=>{card.style.transform='';});
  });
  // Add a subtle page-load progress line without changing any application behavior.
  const bar=document.createElement('div'); bar.style.cssText='position:fixed;z-index:2500;left:0;top:0;width:0;height:2px;background:linear-gradient(90deg,#20c6f5,#6857f5,#ff5fa2);transition:width .25s ease;'; document.body.appendChild(bar);
  requestAnimationFrame(()=>{bar.style.width='100%'; setTimeout(()=>bar.remove(),420);});
})();
