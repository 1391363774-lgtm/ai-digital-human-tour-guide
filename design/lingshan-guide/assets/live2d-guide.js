/* ============================================================
 * GuideHuman — Live2D 数字人(兼容 PhotoHuman 全套接口)
 * 让 guide-app.js / mascot.js 无需改动即可用 Live2D Natori
 * 接口: setEmotion / playAudio(→Promise) / stopAudio
 *       / startTimeline / stopSpeaking
 * 降级: Live2D 不可用时自动回退到 PhotoHuman(老照片立绘引擎)
 * 依赖: live2d-human.js (Live2DHuman) + digital-human-v2.js (PhotoHuman)
 * ============================================================ */
(function () {
  'use strict';

  // 可切换的 Live2D 形象(后台"启用此形象"写入 localStorage 'lingshan_l2d')
  var LIVE2D_MODELS = {
    natori: '../assets/live2d/natori/Natori.model3.json',
    haru:   '../assets/live2d/haru/Haru.model3.json',
    hiyori: '../assets/live2d/hiyori/Hiyori.model3.json'
  };
  function getLive2DModel() {
    var k = localStorage.getItem('lingshan_l2d') || 'natori';
    return LIVE2D_MODELS[k] || LIVE2D_MODELS.natori;
  }
  var LIVE2D_AVATARS = {
    natori: '../assets/natori-avatar.png',
    haru:   '../assets/haru-avatar.png',
    hiyori: '../assets/hiyori-avatar.png'
  };
  function getLive2DAvatar() {
    var k = localStorage.getItem('lingshan_l2d') || 'natori';
    return LIVE2D_AVATARS[k] || LIVE2D_AVATARS.natori;
  }
  window.LIVE2D_MODELS = LIVE2D_MODELS;
  window.getLive2DModel = getLive2DModel;
  window.LIVE2D_AVATARS = LIVE2D_AVATARS;
  window.getLive2DAvatar = getLive2DAvatar;

  // 视素→嘴张度(与 digital-human-v2.js 的 VISEMES 一致)
  var VISEMES = { sil: 0.00, MM: 0.03, AA: 1.00, EH: 0.52, II: 0.34, OO: 0.70, UU: 0.48 };

  // 业务表情 → Natori 表情文件名
  var EMOTION_MAP = {
    welcome: 'Smile', happy: 'Smile', calm: 'Normal',
    think: 'Normal', sorry: 'Sad', surprise: 'Surprised'
  };

  function GuideHuman(container, opts) {
    opts = opts || {};
    this.opts = opts;
    this.audio = null;
    this.visemes = [];
    this.playStart = 0;
    this.speaking = false;
    this.raf = 0;
    this._lastEmotion = 'welcome';
    this._fallback = null;   // PhotoHuman 实例(降级时)
    this._l2d = null;        // Live2DHuman 实例

    var el = typeof container === 'string' ? document.getElementById(container) : container;
    if (!el) return;
    if (!el.id) el.id = 'gh-' + Math.random().toString(36).slice(2, 9);
    this.el = el;

    if (typeof Live2DHuman === 'undefined') { this._useFallback(); return; }

    var self = this;
    var size = opts.size || 280;
    this.size = size;
    this._l2d = new Live2DHuman(el.id, {
      model: opts.model || getLive2DModel(),
      width: size, height: Math.round(size * 1.05),
      fit: opts.fit || 0.95,
      focus: opts.focus || null,
      zoom: opts.zoom || null,
      expression: 'Smile',
      onReady: function () {
        if (self._lastEmotion) self._applyEmotion(self._lastEmotion);
      },
      onError: function () { self._useFallback(); }
    });
  }

  // 降级到 PhotoHuman(保持接口一致)
  GuideHuman.prototype._useFallback = function () {
    if (this._fallback || typeof PhotoHuman === 'undefined') return;
    if (this._l2d) { try { this._l2d.destroy(); } catch (e) {} this._l2d = null; }
    this.el.innerHTML = '';
    this._fallback = new PhotoHuman(this.el, this.opts);
  };

  GuideHuman.prototype._applyEmotion = function (name) {
    if (this._fallback) { this._fallback.setEmotion(name); return; }
    if (!this._l2d) return;
    var exp = EMOTION_MAP[name] || 'Normal';
    this._l2d.setExpression(exp);
  };

  GuideHuman.prototype.setEmotion = function (name) {
    this._lastEmotion = name;
    this._applyEmotion(name);
  };

  // 直接设置 Live2D 表情(导览页表情测试按钮用,绕过业务emotion映射)
  GuideHuman.prototype.setExpression = function (name) {
    if (this._l2d) this._l2d.setExpression(name);
  };

  // 热切换 Live2D 模型(导览页形象切换用)
  GuideHuman.prototype.switchModel = function (modelKey) {
    this.stopAudio();
    if (this._fallback) return;            // 降级态无法切换
    var path = (window.LIVE2D_MODELS && LIVE2D_MODELS[modelKey]) || getLive2DModel();
    var emo = this._lastEmotion;
    if (this._l2d) { try { this._l2d.destroy(); } catch (e) {} this._l2d = null; }
    this.el.innerHTML = '';
    var self = this;
    this._l2d = new Live2DHuman(this.el.id, {
      model: path,
      width: this.size, height: Math.round(this.size * 1.05),
      fit: this.opts.fit || 0.95,
      expression: 'Smile',
      onReady: function () { if (emo) self._applyEmotion(emo); },
      onError: function () { self._useFallback(); }
    });
  };

  // ---------- 口型驱动 ----------
  function currentViseme(visemes, ms) {
    if (!visemes.length) return 0;
    var lo = 0, hi = visemes.length - 1, cur = null;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      if (visemes[mid].t <= ms) { cur = visemes[mid]; lo = mid + 1; }
      else hi = mid - 1;
    }
    if (!cur) return 0;
    var v = cur.v;
    return (v in VISEMES) ? VISEMES[v] : 0.4;
  }

  GuideHuman.prototype._mouth = function (v) {
    if (this._fallback) { this._fallback.setViseme && this._fallback.setViseme('_open'); }
    // Live2D 嘴型(Live2DHuman 内部缓存模型)
    if (!this._l2d) return;
    this._l2d.setMouthOpen(Math.max(0, Math.min(1, v)));
  };

  GuideHuman.prototype._drive = function () {
    var self = this;
    cancelAnimationFrame(this.raf);
    function tick() {
      if (!self.speaking) { self._mouth(0); return; }
      var ms = self.audio
        ? self.audio.currentTime * 1000
        : (performance.now() - self.playStart);
      self._mouth(currentViseme(self.visemes, ms));
      self.raf = requestAnimationFrame(tick);
    }
    tick();
  };

  // ---------- 在线音频 + 视素口型 ----------
  GuideHuman.prototype.playAudio = function (url, visemes) {
    if (this._fallback) return this._fallback.playAudio(url, visemes);
    this.stopAudio();
    var self = this, a = new Audio(), epoch = this._playEpoch;
    this.audio = a; this.visemes = visemes || [];
    return new Promise(function (resolve, reject) {
      var settled = false;
      function finish(error) {
        if (settled) return; settled = true;
        a.onended = a.onerror = null;
        try { a.pause(); a.removeAttribute('src'); a.load(); } catch (_) {}
        if (self.audio === a) { self.audio = null; self.speaking = false; self._mouth(0); cancelAnimationFrame(self.raf); }
        self._settle = null;
        if (error) reject(error); else resolve();
      }
      self._settle = function () { finish(); };
      a.onended = function () { if (epoch === self._playEpoch) finish(); };
      a.onerror = function () { if (epoch === self._playEpoch) finish(new Error('音频加载失败')); };
      a.src = url;
      a.play().then(function () {
        if (epoch !== self._playEpoch || settled) return;
        self.speaking = true; self._drive();
      }).catch(function () { if (epoch === self._playEpoch) finish(new Error('浏览器阻止播放，请先点击页面')); });
    });
  };

  GuideHuman.prototype.stopAudio = function () {
    this._playEpoch = (this._playEpoch || 0) + 1;
    clearTimeout(this._timelineTimer); this._timelineTimer = null;
    cancelAnimationFrame(this.raf); this.speaking = false;
    if (this._settle) this._settle();
    if (this.audio) {
      this.audio.onended = this.audio.onerror = null;
      try { this.audio.pause(); this.audio.removeAttribute('src'); this.audio.load(); } catch (_) {}
      this.audio = null;
    }
    this._mouth(0);
    if (this._fallback && this._fallback.stopAudio) this._fallback.stopAudio();
  };

  // ---------- 浏览器 TTS 兜底口型(离线模式) ----------
  GuideHuman.prototype.startTimeline = function (visemes, durationMs) {
    if (this._fallback) return this._fallback.startTimeline(visemes, durationMs);
    var self = this;
    this.visemes = visemes || [];
    this.playStart = performance.now();
    this.speaking = true;
    this._drive();
    clearTimeout(this._timelineTimer);
    var epoch = this._playEpoch;
    this._timelineTimer = setTimeout(function () {
      if (epoch === self._playEpoch && self.speaking) { self.speaking = false; self._mouth(0); }
    }, durationMs || 3000);
  };

  GuideHuman.prototype.stopSpeaking = function () {
    this.stopAudio();
    if (this._fallback) this._fallback.stopSpeaking && this._fallback.stopSpeaking();
  };

  GuideHuman.prototype.destroy = function () {
    this.stopAudio();
    if (this._l2d) this._l2d.destroy();
    if (this._fallback && this._fallback.destroy) this._fallback.destroy();
    this._l2d = this._fallback = null;
  };
  window.GuideHuman = GuideHuman;
})();
