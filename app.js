(function(){
  var root = document.documentElement;
  var app = document.querySelector('.app');
  var TABS = ['MARKET','CULTURE','SCIENCE','NEWSLETTERS'];

  /* ---- theme ---- */
  var toggle = document.getElementById('themeToggle');
  function current(){ var s = root.getAttribute('data-theme'); if(s) return s;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; }
  try{ var saved = localStorage.getItem('winefeed-theme'); if(saved) root.setAttribute('data-theme', saved); }catch(e){}
  if(toggle) toggle.addEventListener('click', function(){
    var next = current() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try{ localStorage.setItem('winefeed-theme', next); }catch(e){}
  });

  /* ---- deck ---- */
  var track = document.getElementById('track');
  var deck = document.getElementById('deck');
  var slides = track ? [].slice.call(track.querySelectorAll('.slide')) : [];
  var tabs = [].slice.call(document.querySelectorAll('.tab'));
  var dotsWrap = document.querySelector('.dots');
  var counter = document.getElementById('counter');
  var tabname = document.getElementById('tabname');
  var N = slides.length;
  var idx = 0;

  // tabs can hold a variable number of stories (>=1, up to 5) -> derive everything
  // from each slide's data-tab instead of assuming a fixed count per tab.
  var tabIdx = slides.map(function(s){ return parseInt(s.getAttribute('data-tab'), 10) || 0; });
  function tabOf(i){ return tabIdx[i] || 0; }
  function firstOfTab(t){ var k = tabIdx.indexOf(t); return k < 0 ? 0 : k; }
  function countOfTab(t){ var c = 0; for(var k=0;k<tabIdx.length;k++){ if(tabIdx[k]===t) c++; } return c; }
  function withinOf(i){ var t = tabIdx[i], c = 0; for(var k=0;k<=i;k++){ if(tabIdx[k]===t) c++; } return c - 1; }
  function pad2(n){ return String(n).padStart(2,'0'); }

  function render(){
    track.style.transform = 'translateX(' + (-idx * 100) + '%)';
    var ti = tabOf(idx), within = withinOf(idx), cnt = countOfTab(ti);
    tabs.forEach(function(t,k){ var on = k === ti; t.classList.toggle('is-active', on); t.setAttribute('aria-selected', on ? 'true':'false'); });
    if(dotsWrap){
      if(dotsWrap.children.length !== cnt){
        dotsWrap.innerHTML = '';
        for(var q=0;q<cnt;q++){ var s = document.createElement('span'); s.className = 'dot-i'; dotsWrap.appendChild(s); }
      }
      for(var d=0;d<dotsWrap.children.length;d++){ dotsWrap.children[d].classList.toggle('on', d === within); }
    }
    if(counter) counter.textContent = pad2(within+1) + ' / ' + pad2(cnt);
    if(tabname) tabname.textContent = TABS[ti] || '';
  }
  function go(i){ if(!N) return; idx = ((i % N) + N) % N; render(); }

  var prev = document.getElementById('prevBtn'), next = document.getElementById('nextBtn');
  if(prev) prev.addEventListener('click', function(){ go(idx-1); });
  if(next) next.addEventListener('click', function(){ go(idx+1); });
  tabs.forEach(function(t,k){ t.addEventListener('click', function(){ go(firstOfTab(k)); }); });
  document.addEventListener('keydown', function(e){
    if(e.key === 'ArrowRight'){ go(idx+1); }
    else if(e.key === 'ArrowLeft'){ go(idx-1); }
  });

  /* ---- swipe (pointer) ---- */
  var dragging = false, decided = false, sx = 0, sy = 0, dx = 0, w = 0;
  if(deck){
    deck.addEventListener('pointerdown', function(e){
      if(e.target.closest('a,button,input')) return;   // let interactive elements work
      dragging = true; decided = false; sx = e.clientX; sy = e.clientY; dx = 0; w = deck.clientWidth || 1;
    });
    deck.addEventListener('pointermove', function(e){
      if(!dragging) return;
      var mx = e.clientX - sx, my = e.clientY - sy;
      if(!decided){
        if(Math.abs(mx) < 6 && Math.abs(my) < 6) return;
        if(Math.abs(my) > Math.abs(mx)){ dragging = false; return; }  // vertical scroll, bail
        decided = true; track.classList.add('dragging');
        try{ deck.setPointerCapture(e.pointerId); }catch(_){}
      }
      dx = mx;
      track.style.transform = 'translateX(' + (-idx * w + dx) + 'px)';
    });
    function end(){
      if(!dragging) return; dragging = false;
      track.classList.remove('dragging');
      var th = Math.max(48, w * 0.16);
      if(dx < -th) go(idx+1);
      else if(dx > th) go(idx-1);
      else render();
      dx = 0;
    }
    deck.addEventListener('pointerup', end);
    deck.addEventListener('pointercancel', end);
  }

  render();

  /* ---- Klaviyo subscribe (client API) ---- */
  var form = document.getElementById('subForm');
  if(form && app){
    var pub = app.getAttribute('data-kpub') || '';
    var list = app.getAttribute('data-klist') || '';
    var wrap = form; var msg = document.getElementById('subMsg');
    form.addEventListener('submit', function(e){
      e.preventDefault();
      var email = (document.getElementById('subEmail')||{}).value || '';
      if(!email || email.indexOf('@') < 1) return;
      if(!pub || !list){ if(msg) msg.textContent = 'Coming soon'; wrap.classList.add('done'); return; }
      var body = { data:{ type:'subscription',
        attributes:{ custom_source:'winefeed', profile:{ data:{ type:'profile', attributes:{ email:email } } } },
        relationships:{ list:{ data:{ type:'list', id:list } } } } };
      fetch('https://a.klaviyo.com/client/subscriptions/?company_id=' + encodeURIComponent(pub), {
        method:'POST',
        headers:{ 'Content-Type':'application/json', 'revision':'2024-10-15' },
        body: JSON.stringify(body)
      }).then(function(r){
        if(msg) msg.textContent = (r.ok || r.status === 202) ? 'Subscribed ✓' : 'Try again';
        if(r.ok || r.status === 202) wrap.classList.add('done');
      }).catch(function(){ if(msg) msg.textContent = 'Try again'; });
    });
  }
})();
