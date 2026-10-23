/**
 * 灵小仙 · 全站桌宠 (MascotPet)
 * ============================================================
 * 悬浮于任意页面右下角的数字人桌宠:
 *   - 可拖拽移动(鼠标/触摸),闲置呼吸眨眼
 *   - 单击展开迷你对话面板,支持语音/文字提问
 *   - 语音回答+口型同步(Live2D Natori,失败降级PhotoHuman)
 *   - 双击直接跳转到完整导览页
 * 用法: 页面先引入 vendor(pixi/live2dcubismcore/cubism4) + live2d-human.js
 *       + live2d-guide.js (+ digital-human-v2.js 降级用)
 *       <script src="../assets/mascot.js"></script>
 * ============================================================
 */
(function (global) {
  'use strict';

  // guide.html 有完整数字人,不重复挂载
  if (location.pathname.indexOf('guide.html') !== -1) return;
  if (location.pathname.indexOf('admin') !== -1) return;
  if (typeof global.GuideHuman === 'undefined') return;

  var GOLD = '#C5A55A';

  // ================= 样式 =================
  var css = document.createElement('style');
  css.textContent = `
    #lxx-mascot { position:fixed; right:16px; bottom:96px; z-index:9990;
        cursor:grab; user-select:none; touch-action:none;
        filter:drop-shadow(0 4px 16px rgba(197,165,90,.45));
        transition:filter .3s; }
    #lxx-mascot.dragging { cursor:grabbing; transition:none; }
    #lxx-mascot:hover { filter:drop-shadow(0 6px 22px rgba(197,165,90,.65)); }
    #lxx-mascot .m-ring { position:absolute; inset:-6px; border-radius:50%;
        border:1.5px solid rgba(197,165,90,.5); border-top-color:rgba(223,201,138,.95);
        animation:lxxSpin 8s linear infinite; pointer-events:none; }
    @keyframes lxxSpin { to { transform:rotate(360deg); } }
    #lxx-mascot .m-tip { position:absolute; top:-38px; right:0; white-space:nowrap;
        background:rgba(16,26,51,.95); color:#EBDCB0; font-size:11px;
        padding:5px 12px; border-radius:12px; border:1px solid rgba(197,165,90,.35);
        animation:lxxBob 2.4s ease-in-out infinite; pointer-events:none; }
    @keyframes lxxBob { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
    #lxx-panel { position:fixed; right:14px; bottom:240px; z-index:9991; width:288px;
        background:linear-gradient(165deg,#101A33,#0A1226);
        border:1px solid rgba(197,165,90,.3); border-radius:18px;
        box-shadow:0 16px 48px rgba(0,0,0,.5); display:none; overflow:hidden; }
    #lxx-panel.open { display:block; animation:lxxIn .3s cubic-bezier(.22,.9,.32,1.15); }
    @keyframes lxxIn { from { opacity:0; transform:translateY(14px) scale(.94); } to { opacity:1; transform:none; } }
    #lxx-panel .p-head { padding:11px 14px; display:flex; align-items:center; gap:8px;
        background:rgba(197,165,90,.1); border-bottom:1px solid rgba(197,165,90,.18); }
    #lxx-panel .p-head .t { font-size:13px; color:#DFC98A; font-weight:600; letter-spacing:1px; }
    #lxx-panel .p-head .s { font-size:10px; color:#677EA8; margin-left:auto; }
    #lxx-panel .p-body { padding:12px 14px; max-height:220px; overflow-y:auto; }
    #lxx-panel .p-body::-webkit-scrollbar { display:none; }
    .lxx-msg { font-size:12px; line-height:1.7; padding:8px 12px; border-radius:12px; margin-bottom:8px;
        word-break:break-word; }
    .lxx-msg.user { background:rgba(138,113,48,.35); color:#F5EDD6; margin-left:36px; }
    .lxx-msg.bot { background:rgba(197,165,90,.08); border:1px solid rgba(197,165,90,.18);
        color:#F5F5F0; margin-right:36px; }
    #lxx-panel .p-input { display:flex; gap:6px; padding:10px 12px;
        border-top:1px solid rgba(197,165,90,.15); }
    #lxx-panel .p-input input { flex:1; min-width:0; background:rgba(255,255,255,.06);
        border:1px solid rgba(197,165,90,.25); border-radius:999px; padding:7px 14px;
        color:#F5F5F0; font-size:12px; outline:none; }
    #lxx-panel .p-input button { width:34px; height:34px; border-radius:50%; border:none;
        cursor:pointer; display:flex; align-items:center; justify-content:center; font-size:14px; }
    #lxx-mic { background:linear-gradient(135deg,#C5A55A,#A88B3E); color:#FFF; }
    #lxx-mic.listening { background:linear-gradient(135deg,#C25450,#A34340);
        animation:lxxPulse 1.1s infinite; }
    @keyframes lxxPulse { 0%,100%{box-shadow:0 0 0 0 rgba(194,82,80,.5)} 50%{box-shadow:0 0 0 8px rgba(194,82,80,0)} }
    #lxx-send { background:rgba(197,165,90,.2); color:#DFC98A; border:1px solid rgba(197,165,90,.4)!important; }
    #lxx-panel .p-more { display:block; text-align:center; font-size:11px; color:#96A6C4;
        padding:7px; cursor:pointer; border-top:1px solid rgba(197,165,90,.12); }
    #lxx-panel .p-more:hover { color:#DFC98A; }
  `;
  document.head.appendChild(css);

  // ================= 桌宠本体 =================
  var box = document.createElement('div');
  box.id = 'lxx-mascot';
  box.innerHTML = '<div class="m-ring"></div><div class="m-tip">点我,语音问小仙~</div><div class="m-dh"></div>';
  document.body.appendChild(box);

  // 首页已有AI卡Live2D数字人;同页第二个WebGL上下文会触发
  // "object does not belong to this context" 冲突(硬件GPU上桌宠变白).
  // 故首页桌宠用静态头像,其余页面用Live2D。
  var dh;
  if (document.getElementById('home-dh')) {
    box.querySelector('.m-dh').innerHTML =
      '<img src="' + (window.getLive2DAvatar ? getLive2DAvatar() : '../assets/natori-avatar.png') + '" alt="灵小仙" style="width:100%;height:100%;object-fit:cover;object-position:top">';
    dh = { setEmotion: function () {}, playAudio: function () { return Promise.resolve(); },
           stopAudio: function () {}, startTimeline: function () {}, stopSpeaking: function () {} };
  } else {
    dh = new GuideHuman(box.querySelector('.m-dh'), { size: 120, focus: 'face' });
    dh.setEmotion('calm');
  }

  // 首次提示5秒后消失
  var tip = box.querySelector('.m-tip');
  setTimeout(function () { tip.style.display = 'none'; }, 6000);

  // ================= 拖拽 + 单击区分 =================
  var dragging = false, moved = false, ox = 0, oy = 0;
  function pos(e) {
    var t = e.touches && e.touches[0];
    return { x: (t ? t.clientX : e.clientX), y: (t ? t.clientY : e.clientY) };
  }
  function down(e) {
    dragging = true; moved = false;
    var p = pos(e), r = box.getBoundingClientRect();
    ox = p.x - r.left; oy = p.y - r.top;
    box.classList.add('dragging');
  }
  function move(e) {
    if (!dragging) return;
    var p = pos(e);
    var nx = p.x - ox, ny = p.y - oy;
    if (Math.abs(nx - box.offsetLeft) + Math.abs(ny - box.offsetTop) > 6) moved = true;
    if (moved && e.cancelable) e.preventDefault();
    box.style.left = Math.max(0, Math.min(innerWidth - 108, nx)) + 'px';
    box.style.top = Math.max(0, Math.min(innerHeight - 150, ny)) + 'px';
    box.style.right = 'auto'; box.style.bottom = 'auto';
  }
  function up() {
    box.classList.remove('dragging');
    setTimeout(function () { dragging = false; }, 0);
  }
  box.addEventListener('mousedown', down);
  box.addEventListener('touchstart', down, { passive: true });
  document.addEventListener('mousemove', move);
  document.addEventListener('touchmove', move, { passive: false });
  document.addEventListener('mouseup', up);
  document.addEventListener('touchend', up);

  box.addEventListener('click', function () {
    if (moved) return;                 // 拖拽后不算点击
    togglePanel();
  });
  box.addEventListener('dblclick', function () {
    location.href = 'guide.html';
  });

  // ================= 对话面板 =================
  var panel = document.createElement('div');
  panel.id = 'lxx-panel';
  panel.innerHTML =
    '<div class="p-head"><span class="t">🪷 灵小仙</span><span class="s" id="lxx-st">随时问~</span></div>' +
    '<div class="p-body" id="lxx-body">' +
      '<div class="lxx-msg bot">阿弥陀佛!有什么关于灵山胜境的问题,尽管问我~</div>' +
    '</div>' +
    '<div class="p-input">' +
      '<button id="lxx-mic" title="语音提问">🎙</button>' +
      '<input id="lxx-text" type="text" placeholder="输入问题,回车发送..." autocomplete="off">' +
      '<button id="lxx-send" title="发送">➤</button>' +
    '</div>' +
    '<span class="p-more" id="lxx-more">进入完整导览页 ›</span>';
  document.body.appendChild(panel);

  function togglePanel() {
    if (panel.classList.contains('open')) stopMini();
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
      tip.style.display = 'none';
      setTimeout(function () { document.getElementById('lxx-text').focus(); }, 200);
    }
  }
  document.getElementById('lxx-more').onclick = function () { location.href = 'guide.html'; };

  // ================= 问答链路(复用SSE管线) =================
  var tid = localStorage.getItem('lingshan_tid') || 'guest';
  var client = new GuideRuntime.ChatClient(), asking = false, miniMedia = null, miniRAF = 0, miniEpoch = 0, miniSendTimer = null;

  function addMsg(text, who) {
    var body = document.getElementById('lxx-body'), div = document.createElement('div');
    div.className = 'lxx-msg ' + who; div.textContent = text;
    body.appendChild(div); body.scrollTop = body.scrollHeight; return div;
  }
  function stopMini() {
    client.cancel(); asking = false; miniEpoch++; clearTimeout(miniSendTimer);
    if (rec) { rec._active = false; try { rec.abort(); } catch (_) {} }
    dh.stopAudio(); cancelAnimationFrame(miniRAF);
    if (miniMedia) { miniMedia.pause(); miniMedia.removeAttribute('src'); miniMedia.load(); miniMedia = null; }
    if (window.dh && window.dh.setMouthOpen) window.dh.setMouthOpen(0);
  }
  function playMini(item, signal) {
    if (!item.audio_url) return Promise.resolve();
    var url = new URL(item.audio_url, location.href);
    if (url.origin !== location.origin || url.pathname.indexOf('/api/tts/audio/') !== 0) return Promise.reject(new Error('invalid audio URL'));
    return new Promise(function (resolve, reject) {
      var settled = false, timer = null, audio = null;
      function finish(error) {
        if (settled) return; settled = true;
        clearTimeout(timer); cancelAnimationFrame(miniRAF); signal.removeEventListener('abort', abort);
        if (audio) { audio.onended = audio.onerror = null; audio.pause(); audio.removeAttribute('src'); audio.load(); }
        if (miniMedia === audio) miniMedia = null;
        if (window.dh && window.dh.setMouthOpen) window.dh.setMouthOpen(0);
        if (error) reject(error); else resolve();
      }
      function abort() { dh.stopAudio(); finish(new DOMException('Cancelled', 'AbortError')); }
      if (signal.aborted) { abort(); return; }
      signal.addEventListener('abort', abort, { once: true });
      timer = setTimeout(function () { dh.stopAudio(); finish(new Error('播放超时')); }, 60000);
      if (!document.getElementById('home-dh')) { dh.playAudio(url.href, item.visemes).then(function () { finish(); }, finish); return; }
      // Home keeps its original static floating portrait; drive the existing main Live2D canvas.
      audio = new Audio(url.href); miniMedia = audio;
      audio.onended = function () { finish(); }; audio.onerror = function () { finish(new Error('语音不可用')); };
      audio.play().then(function () {
        function mouth() {
          if (settled || signal.aborted) return;
          var ms = audio.currentTime * 1000, value = 0;
          if (!audio.paused && !audio.ended && !audio.seeking && audio.readyState >= 3) (item.visemes || []).forEach(function (v) { if (v.t <= ms && ms < v.t + v.d) value = v.v === 'sil' ? 0 : 0.5; });
          if (window.dh && window.dh.setMouthOpen) window.dh.setMouthOpen(value);
          miniRAF = requestAnimationFrame(mouth);
        }
        mouth();
      }).catch(function () { finish(new Error('浏览器阻止播放')); });
    });
  }
  function ask(q) {
    if (!q.trim()) return;
    stopMini(); asking = true; addMsg(q, 'user');
    document.getElementById('lxx-text').value = '';
    dh.setEmotion('think'); document.getElementById('lxx-st').textContent = '检索中...';
    var botMsg = addMsg('...', 'bot'), full = '';
    void client.start({ message:q, tourist_id:tid, interest:sessionStorage.getItem('lingshan_interest') || undefined }, {
      play: playMini,
      onEvent: function (evt) {
        if (evt.type === 'delta') { full += evt.text; botMsg.textContent = full; }
        else if (evt.type === 'emotion') dh.setEmotion(evt.emotion);
        else if (evt.type === 'done') { full = evt.full_text; botMsg.textContent = full; botMsg.dataset.outcome = evt.status; document.getElementById('lxx-st').textContent = evt.mode === 'demo' ? '演示 · 合成测试音' : '回答已结束'; }
        else if (evt.type === 'error') { botMsg.dataset.outcome = evt.partial ? 'partial' : 'failed'; document.getElementById('lxx-st').textContent = '回答中断'; }
      },
      onCancel: function () { document.getElementById('lxx-st').textContent = '已停止'; },
      onError: function () { botMsg.textContent = full || '服务未连接，请到导览页查看文字资料。'; document.getElementById('lxx-st').textContent = '回答未完成'; asking = false; },
      onAudioError: function () { document.getElementById('lxx-st').textContent = '文字保留 · 语音不可用'; },
      onFinish: function () { asking = false; dh.setEmotion('calm'); }
    });
  }
  document.getElementById('lxx-send').onclick = function () { ask(document.getElementById('lxx-text').value); };
  document.getElementById('lxx-text').addEventListener('keydown', function (e) { if (e.key === 'Enter') ask(this.value); });
  var stopButton = document.createElement('button'); stopButton.textContent = '■'; stopButton.title = '停止讲解'; stopButton.setAttribute('aria-label', '停止讲解'); stopButton.onclick = stopMini;
  stopButton.style.cssText = 'border:0;background:transparent;color:#DFC98A;cursor:pointer'; panel.querySelector('.p-head').appendChild(stopButton);
  window.addEventListener('pagehide', function () { stopMini(); if (dh.destroy) dh.destroy(); });
  document.addEventListener('visibilitychange', function () { if (document.hidden) stopMini(); });

  // ================= 语音输入 =================
  var micBtn = document.getElementById('lxx-mic');
  var SR = global.SpeechRecognition || global.webkitSpeechRecognition;
  if (SR) {
    var rec = new SR();
    rec.lang = 'zh-CN'; rec.continuous = false; rec.interimResults = true;
    rec.onstart = function () { micBtn.classList.add('listening'); };
    rec.onresult = function (e) {
      if (!rec._active) return;
      var t = '';
      for (var i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript;
      document.getElementById('lxx-text').value = t;
    };
    rec.onend = function () {
      micBtn.classList.remove('listening');
      var v = document.getElementById('lxx-text').value.trim();
      var wasActive = rec._active; rec._active = false; var epoch = miniEpoch;
      if (wasActive && v) miniSendTimer = setTimeout(function () { if (epoch === miniEpoch) ask(v); }, 250);
    };
    rec.onerror = function () { rec._active = false; micBtn.classList.remove('listening'); };
    micBtn.onclick = function () { stopMini(); rec._active = true; try { rec.start(); } catch (e) { rec._active = false; } };
  } else {
    micBtn.style.display = 'none';
  }

  // 打招呼(仅文字气泡,不发声)
  global.mascotSay = function (text, sec) {
    tip.textContent = text;
    tip.style.display = 'block';
    clearTimeout(tip._t);
    tip._t = setTimeout(function () { tip.style.display = 'none'; }, (sec || 4) * 1000);
  };
})(window);
